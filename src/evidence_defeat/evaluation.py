"""Training-only defaults and cross-fitted AIPW policy evaluation."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
from numpy.typing import ArrayLike, NDArray
from scipy.stats import norm

from evidence_defeat.folds import iter_outer_folds, make_outer_fold_ids
from evidence_defeat.learners import build_outcome_regression
from evidence_defeat.pipeline import (
    CrossFittedConstruction,
    OutcomeScaling,
    scale_training_utility,
)
from evidence_defeat.preprocessing import CovariateSchema, fit_preprocessor
from evidence_defeat.seeds import derive_model_seed
from evidence_defeat.selection import apply_deferral_policy


@dataclass(frozen=True)
class FoldPolicyNuisance:
    """Default decision and held-out nuisance predictions from one outer fold."""

    fold_id: int
    default_action: int
    default_effect: float
    treatment_0_value: float
    treatment_1_value: float
    propensity_treatment_1: float
    propensity_source: str
    propensity_was_clipped: bool
    training_mu0: NDArray[np.float64]
    training_mu1: NDArray[np.float64]
    heldout_mu0: NDArray[np.float64]
    heldout_mu1: NDArray[np.float64]
    outcome_scaling: OutcomeScaling


@dataclass(frozen=True)
class PolicyValueEstimate:
    """AIPW value and its policy-conditional diagnostic standard error."""

    policy_name: str
    value: float
    conditional_standard_error: float
    sample_size: int


@dataclass(frozen=True)
class PolicyValueContrast:
    """Paired AIPW contrast based on row-level score differences."""

    policy_a: str
    policy_b: str
    estimate: float
    conditional_standard_error: float
    confidence_level: float
    confidence_interval_lower: float
    confidence_interval_upper: float


@dataclass(frozen=True)
class CrossFittedPolicyEvaluation:
    """Row-aligned policies, nuisance predictions and AIPW scores."""

    trial_id: str
    run_id: str
    row_ids: NDArray[np.str_]
    fold_ids: NDArray[np.int16]
    scaled_utility: NDArray[np.float64]
    mu0: NDArray[np.float64]
    mu1: NDArray[np.float64]
    propensity_treatment_1: NDArray[np.float64]
    default_action: NDArray[np.int8]
    default_effect: NDArray[np.float64]
    policies: Mapping[str, NDArray[np.int8]]
    contributions: Mapping[str, NDArray[np.float64]]
    estimates: Mapping[str, PolicyValueEstimate]
    folds: tuple[FoldPolicyNuisance, ...]

    def contrast(
        self,
        policy_a: str,
        policy_b: str,
        *,
        confidence_level: float = 0.95,
    ) -> PolicyValueContrast:
        """Estimate a paired policy-a minus policy-b contrast.

        This interval conditions on the fitted policies. The protocol's final
        inference instead repeats the complete pipeline in a bootstrap.
        """

        if policy_a not in self.contributions or policy_b not in self.contributions:
            raise KeyError("both policies must be present in the evaluation")
        if not 0.0 < confidence_level < 1.0:
            raise ValueError("confidence_level must lie strictly between zero and one")
        difference = self.contributions[policy_a] - self.contributions[policy_b]
        estimate = float(difference.mean())
        standard_error = _standard_error(difference)
        critical_value = float(norm.ppf(0.5 + confidence_level / 2.0))
        return PolicyValueContrast(
            policy_a=policy_a,
            policy_b=policy_b,
            estimate=estimate,
            conditional_standard_error=standard_error,
            confidence_level=confidence_level,
            confidence_interval_lower=estimate - critical_value * standard_error,
            confidence_interval_upper=estimate + critical_value * standard_error,
        )


def aipw_policy_contributions(
    policy_action: ArrayLike,
    utility_outcome: ArrayLike,
    treatment: ArrayLike,
    mu0: ArrayLike,
    mu1: ArrayLike,
    propensity_treatment_1: ArrayLike | float,
) -> NDArray[np.float64]:
    """Return one randomisation-aware AIPW value score per participant."""

    outcome = _finite_vector("utility_outcome", utility_outcome)
    n = outcome.shape[0]
    policy = _binary_vector("policy_action", policy_action, n)
    assigned = _binary_vector("treatment", treatment, n)
    untreated_mean = _finite_vector("mu0", mu0, n)
    treated_mean = _finite_vector("mu1", mu1, n)
    probability_1 = _probability_vector(propensity_treatment_1, n)

    selected_mean = np.where(policy == 1, treated_mean, untreated_mean)
    observed_mean = np.where(assigned == 1, treated_mean, untreated_mean)
    observed_probability = np.where(assigned == 1, probability_1, 1.0 - probability_1)
    follows_policy = assigned == policy
    contribution = (
        selected_mean
        + follows_policy * (outcome - observed_mean) / observed_probability
    )
    if not np.isfinite(contribution).all():  # pragma: no cover - validated inputs
        raise RuntimeError("AIPW calculation returned non-finite contributions")
    return contribution.astype(float, copy=False)


def aipw_treatment_values(
    utility_outcome: ArrayLike,
    treatment: ArrayLike,
    mu0: ArrayLike,
    mu1: ArrayLike,
    propensity_treatment_1: ArrayLike | float,
) -> tuple[float, float]:
    """Estimate population values under treatment 0 and treatment 1."""

    outcome = _finite_vector("utility_outcome", utility_outcome)
    n = outcome.shape[0]
    value_0 = aipw_policy_contributions(
        np.zeros(n, dtype=np.int8),
        outcome,
        treatment,
        mu0,
        mu1,
        propensity_treatment_1,
    ).mean()
    value_1 = aipw_policy_contributions(
        np.ones(n, dtype=np.int8),
        outcome,
        treatment,
        mu0,
        mu1,
        propensity_treatment_1,
    ).mean()
    return float(value_0), float(value_1)


def select_population_default(
    treatment_0_value: float,
    treatment_1_value: float,
    *,
    materiality_margin: float,
) -> int:
    """Use treatment 1 only when its advantage strictly clears the margin."""

    values = np.asarray([treatment_0_value, treatment_1_value], dtype=float)
    if not np.isfinite(values).all():
        raise ValueError("treatment values must be finite")
    if not math.isfinite(materiality_margin) or materiality_margin < 0.0:
        raise ValueError("materiality_margin must be finite and non-negative")
    return int(treatment_1_value - treatment_0_value > materiality_margin)


def fit_outer_fold_policy_nuisance(
    *,
    training_covariates: pd.DataFrame,
    training_utility: ArrayLike,
    training_treatment: ArrayLike,
    training_row_ids: ArrayLike,
    heldout_covariates: pd.DataFrame,
    schema: CovariateSchema,
    run_id: str,
    fold_id: int,
    outcome_type: str,
    analysis_config: dict[str, Any],
    documented_treatment_probability: float | None = None,
) -> FoldPolicyNuisance:
    """Fit a training-only default and held-out outcome regressions.

    Held-out outcomes are deliberately absent from this interface. They are
    used only after all decisions and nuisance predictions have been fixed.
    """

    n_train = len(training_covariates)
    if n_train < 2 or len(heldout_covariates) < 1:
        raise ValueError("training and held-out covariates must be non-empty")
    utility = _finite_vector("training_utility", training_utility, n_train)
    assigned = _binary_vector("training_treatment", training_treatment, n_train)
    identifiers = _unique_string_ids(training_row_ids, n_train)
    if not run_id:
        raise ValueError("run_id must not be empty")
    if not isinstance(fold_id, int) or isinstance(fold_id, bool) or fold_id < 0:
        raise ValueError("fold_id must be a non-negative integer")

    scaled_utility, scaling = scale_training_utility(
        utility,
        outcome_type=outcome_type,
        ddof=int(analysis_config["outcome"]["continuous_scaling_sd_ddof"]),
    )
    probability_1, source, was_clipped = _resolve_propensity(
        assigned,
        documented_treatment_probability,
        analysis_config,
    )
    inner_mu0, inner_mu1 = _inner_cross_fitted_outcome_predictions(
        training_covariates,
        scaled_utility,
        assigned,
        identifiers,
        schema=schema,
        run_id=run_id,
        outer_fold_id=fold_id,
        analysis_config=analysis_config,
    )
    value_0, value_1 = aipw_treatment_values(
        scaled_utility,
        assigned,
        inner_mu0,
        inner_mu1,
        probability_1,
    )
    margin = _materiality_margin(analysis_config, outcome_type)
    default_action = select_population_default(
        value_0,
        value_1,
        materiality_margin=margin,
    )

    preprocessor = fit_preprocessor(training_covariates, schema)
    x_train = preprocessor.transform(training_covariates)
    x_heldout = preprocessor.transform(heldout_covariates)
    heldout_mu0, heldout_mu1 = _fit_arm_models_and_predict(
        x_train,
        scaled_utility,
        assigned,
        x_heldout,
        analysis_config=analysis_config,
        run_id=run_id,
        outer_fold_id=fold_id,
        stage="outer",
    )
    return FoldPolicyNuisance(
        fold_id=fold_id,
        default_action=default_action,
        default_effect=value_1 - value_0,
        treatment_0_value=value_0,
        treatment_1_value=value_1,
        propensity_treatment_1=probability_1,
        propensity_source=source,
        propensity_was_clipped=was_clipped,
        training_mu0=inner_mu0,
        training_mu1=inner_mu1,
        heldout_mu0=heldout_mu0,
        heldout_mu1=heldout_mu1,
        outcome_scaling=scaling,
    )


def evaluate_cross_fitted_policies(
    construction: CrossFittedConstruction,
    covariates: pd.DataFrame,
    utility_outcome: ArrayLike,
    treatment: ArrayLike,
    row_ids: ArrayLike,
    *,
    schema: CovariateSchema,
    outcome_type: str,
    analysis_config: dict[str, Any],
    documented_treatment_probability: float | None = None,
) -> CrossFittedPolicyEvaluation:
    """Estimate deterministic policy values after construction is complete."""

    if not isinstance(covariates, pd.DataFrame):
        raise TypeError("covariates must be a pandas DataFrame")
    n = len(covariates)
    if n < 2:
        raise ValueError("at least two rows are required")
    outcome = _finite_vector("utility_outcome", utility_outcome, n)
    assigned = _binary_vector("treatment", treatment, n)
    identifiers = _unique_string_ids(row_ids, n)
    if not np.array_equal(identifiers, construction.row_ids):
        raise ValueError("evaluation row_ids do not match construction row_ids")
    if not np.array_equal(assigned, construction.treatment):
        raise ValueError("evaluation treatment does not match construction treatment")
    if outcome_type != construction.outcome_type:
        raise ValueError("evaluation outcome_type does not match construction")
    if schema != construction.schema:
        raise ValueError("evaluation schema does not match construction schema")
    if construction.fold_ids.shape != (n,):
        raise ValueError("construction fold_ids do not match evaluation rows")

    scaled_outcome = np.full(n, np.nan)
    mu0 = np.full(n, np.nan)
    mu1 = np.full(n, np.nan)
    probability_1 = np.full(n, np.nan)
    default_action = np.zeros(n, dtype=np.int8)
    default_effect = np.full(n, np.nan)
    fold_results: list[FoldPolicyNuisance] = []
    construction_folds = {fold.fold_id: fold for fold in construction.folds}

    for split in iter_outer_folds(construction.fold_ids):
        nuisance = fit_outer_fold_policy_nuisance(
            training_covariates=covariates.iloc[split.training_indices],
            training_utility=outcome[split.training_indices],
            training_treatment=assigned[split.training_indices],
            training_row_ids=identifiers[split.training_indices],
            heldout_covariates=covariates.iloc[split.heldout_indices],
            schema=schema,
            run_id=construction.run_id,
            fold_id=split.fold_id,
            outcome_type=outcome_type,
            analysis_config=analysis_config,
            documented_treatment_probability=documented_treatment_probability,
        )
        if split.fold_id not in construction_folds:
            raise ValueError("construction is missing an outer-fold result")
        _assert_same_scaling(
            nuisance.outcome_scaling,
            construction_folds[split.fold_id].outcome_scaling,
        )
        heldout = split.heldout_indices
        scaled_outcome[heldout] = _apply_scaling(
            outcome[heldout],
            outcome_type,
            nuisance.outcome_scaling,
        )
        mu0[heldout] = nuisance.heldout_mu0
        mu1[heldout] = nuisance.heldout_mu1
        probability_1[heldout] = nuisance.propensity_treatment_1
        default_action[heldout] = nuisance.default_action
        default_effect[heldout] = nuisance.default_effect
        fold_results.append(nuisance)

    _require_complete("scaled utility", scaled_outcome)
    _require_complete("mu0", mu0)
    _require_complete("mu1", mu1)
    _require_complete("propensity", probability_1)
    policies = _construct_policies(construction, default_action)
    contributions = {
        name: aipw_policy_contributions(
            action,
            scaled_outcome,
            assigned,
            mu0,
            mu1,
            probability_1,
        )
        for name, action in policies.items()
    }
    estimates = {
        name: PolicyValueEstimate(
            policy_name=name,
            value=float(scores.mean()),
            conditional_standard_error=_standard_error(scores),
            sample_size=n,
        )
        for name, scores in contributions.items()
    }
    return CrossFittedPolicyEvaluation(
        trial_id=construction.trial_id,
        run_id=construction.run_id,
        row_ids=identifiers,
        fold_ids=construction.fold_ids.copy(),
        scaled_utility=scaled_outcome,
        mu0=mu0,
        mu1=mu1,
        propensity_treatment_1=probability_1,
        default_action=default_action,
        default_effect=default_effect,
        policies=policies,
        contributions=contributions,
        estimates=estimates,
        folds=tuple(fold_results),
    )


def _inner_cross_fitted_outcome_predictions(
    covariates: pd.DataFrame,
    utility: NDArray[np.float64],
    treatment: NDArray[np.int8],
    row_ids: NDArray[np.str_],
    *,
    schema: CovariateSchema,
    run_id: str,
    outer_fold_id: int,
    analysis_config: dict[str, Any],
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    fold_ids = make_inner_fold_ids(
        treatment,
        row_ids,
        run_id=run_id,
        outer_fold_id=outer_fold_id,
        analysis_config=analysis_config,
    )
    mu0 = np.full(len(covariates), np.nan)
    mu1 = np.full(len(covariates), np.nan)
    for split in iter_outer_folds(fold_ids):
        preprocessor = fit_preprocessor(
            covariates.iloc[split.training_indices],
            schema,
        )
        x_train = preprocessor.transform(covariates.iloc[split.training_indices])
        x_heldout = preprocessor.transform(covariates.iloc[split.heldout_indices])
        predicted_0, predicted_1 = _fit_arm_models_and_predict(
            x_train,
            utility[split.training_indices],
            treatment[split.training_indices],
            x_heldout,
            analysis_config=analysis_config,
            run_id=run_id,
            outer_fold_id=outer_fold_id,
            stage=f"inner_{split.fold_id}",
        )
        mu0[split.heldout_indices] = predicted_0
        mu1[split.heldout_indices] = predicted_1
    _require_complete("inner mu0", mu0)
    _require_complete("inner mu1", mu1)
    return mu0, mu1


def make_inner_fold_ids(
    treatment: ArrayLike,
    row_ids: ArrayLike,
    *,
    run_id: str,
    outer_fold_id: int,
    analysis_config: dict[str, Any],
) -> NDArray[np.int16]:
    """Create the shared deterministic inner folds for policy evaluation."""

    if not run_id:
        raise ValueError("run_id must not be empty")
    if (
        not isinstance(outer_fold_id, int)
        or isinstance(outer_fold_id, bool)
        or outer_fold_id < 0
    ):
        raise ValueError("outer_fold_id must be a non-negative integer")
    inner_seed = derive_model_seed(
        int(analysis_config["master_seed"]),
        run_id,
        outer_fold_id,
        "aipw_inner_folds",
    )
    return make_outer_fold_ids(
        treatment,
        row_ids,
        n_splits=int(analysis_config["cross_fitting"]["inner_folds"]),
        seed=inner_seed,
    )


def _fit_arm_models_and_predict(
    training_covariates: NDArray[np.float64],
    utility: NDArray[np.float64],
    treatment: NDArray[np.int8],
    prediction_covariates: NDArray[np.float64],
    *,
    analysis_config: dict[str, Any],
    run_id: str,
    outer_fold_id: int,
    stage: str,
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    predictions = []
    for arm in (0, 1):
        in_arm = treatment == arm
        if in_arm.sum() < 2:
            raise ValueError(
                "each training treatment arm must contain at least two rows"
            )
        seed = derive_model_seed(
            int(analysis_config["master_seed"]),
            run_id,
            outer_fold_id,
            f"aipw_{stage}_arm_{arm}",
        )
        model = build_outcome_regression(analysis_config, seed)
        model.fit(training_covariates[in_arm], utility[in_arm])
        prediction = np.asarray(model.predict(prediction_covariates), dtype=float)
        if (
            prediction.ndim != 1
            or prediction.shape[0] != prediction_covariates.shape[0]
        ):
            raise RuntimeError("outcome model did not return one prediction per row")
        if not np.isfinite(prediction).all():
            raise RuntimeError("outcome model returned non-finite predictions")
        predictions.append(prediction)
    return predictions[0], predictions[1]


def _construct_policies(
    construction: CrossFittedConstruction,
    default_action: NDArray[np.int8],
) -> dict[str, NDArray[np.int8]]:
    individualised = construction.individualised_action
    policies = {
        "population_default": default_action.copy(),
        "ungated_individualisation": individualised.copy(),
        "complete_gate": apply_deferral_policy(
            construction.gate.complete,
            individualised,
            default_action,
        ),
        "uncertainty_only": apply_deferral_policy(
            construction.uncertainty_only_acceptance,
            individualised,
            default_action,
        ),
    }
    policies.update(
        {
            f"single_{name}": apply_deferral_policy(
                accepts,
                individualised,
                default_action,
            )
            for name, accepts in construction.gate.single_check.items()
        }
    )
    policies.update(
        {
            name: apply_deferral_policy(
                accepts,
                individualised,
                default_action,
            )
            for name, accepts in construction.gate.leave_one_out.items()
        }
    )
    return policies


def _resolve_propensity(
    training_treatment: NDArray[np.int8],
    documented_probability: float | None,
    analysis_config: dict[str, Any],
) -> tuple[float, str, bool]:
    if documented_probability is None:
        raw_probability = float(training_treatment.mean())
        source = "outer_training_treatment_fraction"
    else:
        if isinstance(documented_probability, bool):
            raise TypeError("documented_treatment_probability must be numeric")
        raw_probability = float(documented_probability)
        source = "documented_randomisation_probability"
    if not math.isfinite(raw_probability) or not 0.0 < raw_probability < 1.0:
        raise ValueError("treatment probability must lie strictly between zero and one")
    lower, upper = map(float, analysis_config["propensity"]["clip"])
    if not 0.0 < lower < upper < 1.0:
        raise ValueError("propensity clip bounds must lie inside (0, 1)")
    clipped = float(np.clip(raw_probability, lower, upper))
    return clipped, source, clipped != raw_probability


def _apply_scaling(
    utility: NDArray[np.float64],
    outcome_type: str,
    scaling: OutcomeScaling,
) -> NDArray[np.float64]:
    if outcome_type == "binary":
        if not np.isin(utility, (0.0, 1.0)).all():
            raise ValueError("binary utility must contain only zero and one")
        return utility.copy()
    if outcome_type == "continuous":
        return (utility - scaling.center) / scaling.scale
    raise ValueError("outcome_type must be binary or continuous")


def _assert_same_scaling(first: OutcomeScaling, second: OutcomeScaling) -> None:
    if (
        first.ddof != second.ddof
        or not math.isclose(
            first.center,
            second.center,
            rel_tol=0.0,
            abs_tol=1e-12,
        )
        or not math.isclose(first.scale, second.scale, rel_tol=0.0, abs_tol=1e-12)
    ):
        raise ValueError("evaluation and construction outcome scaling differ")


def _materiality_margin(analysis_config: dict[str, Any], outcome_type: str) -> float:
    if outcome_type == "binary":
        return float(analysis_config["outcome"]["binary_materiality_margin"])
    if outcome_type == "continuous":
        return float(analysis_config["outcome"]["continuous_materiality_margin_sd"])
    raise ValueError("outcome_type must be binary or continuous")


def _standard_error(values: NDArray[np.float64]) -> float:
    if values.shape[0] < 2:
        raise ValueError("at least two rows are required for a standard error")
    return float(values.std(ddof=1) / math.sqrt(values.shape[0]))


def _require_complete(name: str, values: NDArray[np.float64]) -> None:
    if not np.isfinite(values).all():
        raise RuntimeError(f"{name} predictions are incomplete")


def _finite_vector(
    name: str,
    values: ArrayLike,
    expected_size: int | None = None,
) -> NDArray[np.float64]:
    array = np.asarray(values, dtype=float)
    if array.ndim != 1 or array.shape[0] < 1:
        raise ValueError(f"{name} must be a non-empty one-dimensional array")
    if expected_size is not None and array.shape[0] != expected_size:
        raise ValueError(f"{name} must have one entry per row")
    if not np.isfinite(array).all():
        raise ValueError(f"{name} must contain only finite values")
    return array


def _binary_vector(
    name: str,
    values: ArrayLike,
    expected_size: int,
) -> NDArray[np.int8]:
    array = np.asarray(values)
    if array.ndim != 1 or array.shape[0] != expected_size:
        raise ValueError(f"{name} must have one entry per row")
    if not np.isin(array, (0, 1)).all():
        raise ValueError(f"{name} must contain only zero and one")
    return array.astype(np.int8, copy=False)


def _probability_vector(
    values: ArrayLike | float,
    expected_size: int,
) -> NDArray[np.float64]:
    array = np.asarray(values, dtype=float)
    if array.ndim == 0:
        array = np.full(expected_size, float(array))
    if array.ndim != 1 or array.shape[0] != expected_size:
        raise ValueError("propensity must be scalar or have one entry per row")
    if not np.isfinite(array).all() or np.any((array <= 0.0) | (array >= 1.0)):
        raise ValueError("propensity must lie strictly between zero and one")
    return array


def _unique_string_ids(values: ArrayLike, expected_size: int) -> NDArray[np.str_]:
    array = np.asarray(values)
    if array.ndim != 1 or array.shape[0] != expected_size:
        raise ValueError("row_ids must have one entry per row")
    identifiers = array.astype(str)
    if np.unique(identifiers).shape[0] != expected_size:
        raise ValueError("row_ids must be unique after string conversion")
    return identifiers
