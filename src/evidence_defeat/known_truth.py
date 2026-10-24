"""Known-counterfactual safety, utility and regret estimands."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import ArrayLike, NDArray

from evidence_defeat.evaluation import CrossFittedPolicyEvaluation
from evidence_defeat.pipeline import CrossFittedConstruction
from evidence_defeat.selection import (
    RandomDeferralSelections,
    random_deferral_at_matched_coverage,
)


@dataclass(frozen=True)
class KnownTruthMetrics:
    """Prespecified known-truth estimands for one deployed policy."""

    method_name: str
    sample_size: int
    accepted_count: int
    actionable_count: int
    accepted_actionable_count: int
    unsafe_accepted_count: int
    coverage: float
    material_unsafe_acceptance: float
    accepted_actionable_error_rate: float
    deployed_policy_utility: float
    oracle_policy_utility: float
    oracle_regret: float
    default_policy_utility: float
    regret_relative_to_default: float
    utility_gain_vs_default: float


@dataclass(frozen=True)
class KnownTruthEvaluation:
    """Metrics for all deterministic methods and the primary paired contrast."""

    metrics: Mapping[str, KnownTruthMetrics]
    optimal_action: NDArray[np.int8]
    materiality_margin: NDArray[np.float64]
    primary_material_unsafe_acceptance_contrast: float


@dataclass(frozen=True)
class RandomDeferralKnownTruthEvaluation:
    """Known-truth results from all matched random-deferral repetitions."""

    selections: RandomDeferralSelections
    deployed_policies: NDArray[np.int8]
    metrics: tuple[KnownTruthMetrics, ...]

    @property
    def mean_material_unsafe_acceptance(self) -> float:
        """Average population-denominator unsafe acceptance across repetitions."""

        return float(
            np.mean([item.material_unsafe_acceptance for item in self.metrics])
        )

    @property
    def mean_deployed_policy_utility(self) -> float:
        """Average known-truth policy utility across repetitions."""

        return float(np.mean([item.deployed_policy_utility for item in self.metrics]))


def evaluate_known_truth_method(
    method_name: str,
    acceptance: ArrayLike,
    individualised_action: ArrayLike,
    deployed_action: ArrayLike,
    default_action: ArrayLike,
    mu0: ArrayLike,
    mu1: ArrayLike,
    materiality_margin: ArrayLike | float,
) -> KnownTruthMetrics:
    """Evaluate one method against known potential-outcome means.

    Material unsafe acceptance always uses the complete population as its
    denominator, not only accepted or actionable rows.
    """

    if not method_name:
        raise ValueError("method_name must not be empty")
    untreated_mean = _finite_vector("mu0", mu0)
    n = untreated_mean.shape[0]
    treated_mean = _finite_vector("mu1", mu1, n)
    accepts = _boolean_vector("acceptance", acceptance, n)
    individualised = _binary_vector(
        "individualised_action",
        individualised_action,
        n,
    )
    deployed = _binary_vector("deployed_action", deployed_action, n)
    default = _binary_vector("default_action", default_action, n)
    margin = _margin_vector(materiality_margin, n)

    effect = treated_mean - untreated_mean
    optimal = (effect > 0.0).astype(np.int8)
    actionable = np.abs(effect) >= margin
    wrong_individualised = individualised != optimal
    unsafe_accepted = accepts & actionable & wrong_individualised
    accepted_actionable = accepts & actionable

    deployed_utility = float(
        np.where(deployed == 1, treated_mean, untreated_mean).mean()
    )
    oracle_utility = float(np.maximum(untreated_mean, treated_mean).mean())
    default_utility = float(np.where(default == 1, treated_mean, untreated_mean).mean())
    accepted_actionable_count = int(accepted_actionable.sum())
    if accepted_actionable_count:
        accepted_error = float(unsafe_accepted.sum() / accepted_actionable_count)
    else:
        accepted_error = math.nan

    return KnownTruthMetrics(
        method_name=method_name,
        sample_size=n,
        accepted_count=int(accepts.sum()),
        actionable_count=int(actionable.sum()),
        accepted_actionable_count=accepted_actionable_count,
        unsafe_accepted_count=int(unsafe_accepted.sum()),
        coverage=float(accepts.mean()),
        material_unsafe_acceptance=float(unsafe_accepted.mean()),
        accepted_actionable_error_rate=accepted_error,
        deployed_policy_utility=deployed_utility,
        oracle_policy_utility=oracle_utility,
        oracle_regret=oracle_utility - deployed_utility,
        default_policy_utility=default_utility,
        regret_relative_to_default=default_utility - deployed_utility,
        utility_gain_vs_default=deployed_utility - default_utility,
    )


def evaluate_cross_fitted_known_truth(
    construction: CrossFittedConstruction,
    evaluation: CrossFittedPolicyEvaluation,
    mu0: ArrayLike,
    mu1: ArrayLike,
    *,
    analysis_config: dict[str, Any],
) -> KnownTruthEvaluation:
    """Evaluate every deterministic policy produced by the pipeline."""

    _validate_linked_results(construction, evaluation)
    n = construction.row_ids.shape[0]
    untreated_mean = _finite_vector("mu0", mu0, n)
    treated_mean = _finite_vector("mu1", mu1, n)
    margin = original_scale_materiality_margin(construction, analysis_config)
    acceptances = deterministic_acceptances(construction)
    if set(acceptances) != set(evaluation.policies):
        raise ValueError("acceptance and deployed-policy method names differ")

    metrics = {
        name: evaluate_known_truth_method(
            name,
            acceptances[name],
            construction.individualised_action,
            evaluation.policies[name],
            evaluation.default_action,
            untreated_mean,
            treated_mean,
            margin,
        )
        for name in evaluation.policies
    }
    primary_contrast = (
        metrics["complete_gate"].material_unsafe_acceptance
        - metrics["uncertainty_only"].material_unsafe_acceptance
    )
    return KnownTruthEvaluation(
        metrics=metrics,
        optimal_action=(treated_mean > untreated_mean).astype(np.int8),
        materiality_margin=margin,
        primary_material_unsafe_acceptance_contrast=primary_contrast,
    )


def evaluate_random_deferral_known_truth(
    construction: CrossFittedConstruction,
    evaluation: CrossFittedPolicyEvaluation,
    mu0: ArrayLike,
    mu1: ArrayLike,
    *,
    analysis_config: dict[str, Any],
    repetitions: int | None = None,
) -> RandomDeferralKnownTruthEvaluation:
    """Evaluate deterministic pseudo-random deferral at matched coverage."""

    _validate_linked_results(construction, evaluation)
    n = construction.row_ids.shape[0]
    untreated_mean = _finite_vector("mu0", mu0, n)
    treated_mean = _finite_vector("mu1", mu1, n)
    margin = original_scale_materiality_margin(construction, analysis_config)
    if repetitions is None:
        repetitions = int(
            analysis_config["comparators"]["random_deferral"]["repetitions"]
        )
    selections = random_deferral_at_matched_coverage(
        construction.gate.complete,
        construction.fold_ids,
        trial_ids=construction.trial_id,
        row_ids=construction.row_ids,
        master_seed=int(analysis_config["master_seed"]),
        run_id=construction.run_id,
        repetitions=repetitions,
    )
    deployed = np.where(
        selections.acceptance,
        construction.individualised_action[None, :],
        evaluation.default_action[None, :],
    ).astype(np.int8)
    metrics = tuple(
        evaluate_known_truth_method(
            f"random_deferral_{repetition_id:03d}",
            selections.acceptance[repetition_id],
            construction.individualised_action,
            deployed[repetition_id],
            evaluation.default_action,
            untreated_mean,
            treated_mean,
            margin,
        )
        for repetition_id in range(repetitions)
    )
    return RandomDeferralKnownTruthEvaluation(
        selections=selections,
        deployed_policies=deployed,
        metrics=metrics,
    )


def deterministic_acceptances(
    construction: CrossFittedConstruction,
) -> dict[str, NDArray[np.bool_]]:
    """Return acceptance indicators aligned with deterministic policy names."""

    n = construction.row_ids.shape[0]
    acceptances = {
        "population_default": np.zeros(n, dtype=bool),
        "ungated_individualisation": np.ones(n, dtype=bool),
        "complete_gate": construction.gate.complete.copy(),
        "uncertainty_only": construction.uncertainty_only_acceptance.copy(),
    }
    acceptances.update(
        {
            f"single_{name}": values.copy()
            for name, values in construction.gate.single_check.items()
        }
    )
    acceptances.update(
        {
            name: values.copy()
            for name, values in construction.gate.leave_one_out.items()
        }
    )
    return acceptances


def original_scale_materiality_margin(
    construction: CrossFittedConstruction,
    analysis_config: dict[str, Any],
) -> NDArray[np.float64]:
    """Return each row's margin on the original known-outcome scale."""

    n = construction.row_ids.shape[0]
    if construction.outcome_type == "binary":
        margin = float(analysis_config["outcome"]["binary_materiality_margin"])
        return np.full(n, margin, dtype=float)
    if construction.outcome_type != "continuous":
        raise ValueError("construction outcome_type must be binary or continuous")

    margin_sd = float(analysis_config["outcome"]["continuous_materiality_margin_sd"])
    margins = np.full(n, np.nan)
    for fold in construction.folds:
        in_fold = construction.fold_ids == fold.fold_id
        margins[in_fold] = margin_sd * fold.outcome_scaling.scale
    if not np.isfinite(margins).all():
        raise RuntimeError("continuous materiality margins are incomplete")
    return margins


def _validate_linked_results(
    construction: CrossFittedConstruction,
    evaluation: CrossFittedPolicyEvaluation,
) -> None:
    if construction.trial_id != evaluation.trial_id:
        raise ValueError("construction and evaluation trial identifiers differ")
    if construction.run_id != evaluation.run_id:
        raise ValueError("construction and evaluation run identifiers differ")
    if not np.array_equal(construction.row_ids, evaluation.row_ids):
        raise ValueError("construction and evaluation row identifiers differ")
    if not np.array_equal(construction.fold_ids, evaluation.fold_ids):
        raise ValueError("construction and evaluation folds differ")


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


def _boolean_vector(
    name: str,
    values: ArrayLike,
    expected_size: int,
) -> NDArray[np.bool_]:
    array = np.asarray(values)
    if array.dtype != np.bool_:
        raise TypeError(f"{name} must be Boolean")
    if array.ndim != 1 or array.shape[0] != expected_size:
        raise ValueError(f"{name} must have one entry per row")
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


def _margin_vector(
    values: ArrayLike | float,
    expected_size: int,
) -> NDArray[np.float64]:
    array = np.asarray(values, dtype=float)
    if array.ndim == 0:
        array = np.full(expected_size, float(array))
    if array.ndim != 1 or array.shape[0] != expected_size:
        raise ValueError("materiality_margin must be scalar or have one entry per row")
    if not np.isfinite(array).all() or np.any(array < 0.0):
        raise ValueError("materiality_margin must be finite and non-negative")
    return array
