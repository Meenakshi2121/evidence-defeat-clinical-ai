"""Leakage-controlled construction of gates and matched comparators."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
from numpy.typing import ArrayLike, NDArray

from evidence_defeat.checks import (
    DecisionCertaintyResult,
    ModelMultiplicityResult,
    RecordAdequacyResult,
    ReferenceSupportResult,
    decision_certainty_check,
    model_multiplicity_check,
    record_adequacy_check,
    reference_support_check,
)
from evidence_defeat.folds import iter_outer_folds, make_outer_fold_ids
from evidence_defeat.learners import (
    LearnerSeeds,
    TreatmentEffectPredictions,
    fit_predict_prespecified_learners,
)
from evidence_defeat.preprocessing import (
    CovariateSchema,
    fit_preprocessor,
    observed_covariate_mask,
)
from evidence_defeat.selection import (
    GateSelections,
    construct_gate,
    graded_uncertainty_acceptance,
    uncertainty_only_at_matched_coverage,
)


@dataclass(frozen=True)
class OutcomeScaling:
    """Outer-training-fold orientation-preserving outcome scaling."""

    center: float
    scale: float
    ddof: int


@dataclass(frozen=True)
class FoldConstruction:
    """All outcome-blind held-out construction outputs for one outer fold."""

    fold_id: int
    heldout_row_ids: NDArray[np.str_]
    predictions: TreatmentEffectPredictions
    record: RecordAdequacyResult
    support: ReferenceSupportResult
    multiplicity: ModelMultiplicityResult
    certainty: DecisionCertaintyResult
    gate: GateSelections
    individualised_action: NDArray[np.int8]
    uncertainty_only_acceptance: NDArray[np.bool_]
    preprocessing_features: tuple[str, ...]
    outcome_scaling: OutcomeScaling


@dataclass(frozen=True)
class CrossFittedConstruction:
    """Row-aligned outputs assembled from every held-out outer fold."""

    trial_id: str
    run_id: str
    outcome_type: str
    schema: CovariateSchema
    row_ids: NDArray[np.str_]
    fold_ids: NDArray[np.int16]
    treatment: NDArray[np.int8]
    predictions: TreatmentEffectPredictions
    checks: Mapping[str, NDArray[np.bool_]]
    gate: GateSelections
    individualised_action: NDArray[np.int8]
    uncertainty_only_acceptance: NDArray[np.bool_]
    record_observed_fraction: NDArray[np.float64]
    record_invalid_present: NDArray[np.bool_]
    support_score: NDArray[np.float64]
    support_threshold: NDArray[np.float64]
    multiplicity_supporting_estimators: NDArray[np.int64]
    multiplicity_opposing_estimators: NDArray[np.int64]
    interval_width: NDArray[np.float64]
    folds: tuple[FoldConstruction, ...]


def construct_outer_fold(
    *,
    training_covariates: pd.DataFrame,
    training_utility: ArrayLike,
    training_treatment: ArrayLike,
    heldout_covariates: pd.DataFrame,
    heldout_row_ids: ArrayLike,
    heldout_invalid_mask: ArrayLike | None,
    schema: CovariateSchema,
    trial_id: str,
    run_id: str,
    fold_id: int,
    outcome_type: str,
    analysis_config: dict[str, Any],
) -> FoldConstruction:
    """Construct one held-out fold without accepting its observed outcomes."""

    if not trial_id or not run_id:
        raise ValueError("trial_id and run_id must not be empty")
    if not isinstance(fold_id, int) or isinstance(fold_id, bool) or fold_id < 0:
        raise ValueError("fold_id must be a non-negative integer")
    training_utility_array = np.asarray(training_utility)
    training_treatment_array = np.asarray(training_treatment)
    if training_utility_array.ndim != 1:
        raise ValueError("training utility must be one-dimensional")
    if training_treatment_array.ndim != 1:
        raise ValueError("training treatment must be one-dimensional")
    if len(training_covariates) != training_utility_array.shape[0]:
        raise ValueError("training utility row count does not match covariates")
    if len(training_covariates) != training_treatment_array.shape[0]:
        raise ValueError("training treatment row count does not match covariates")
    if len(heldout_covariates) < 1:
        raise ValueError("heldout_covariates must contain at least one row")

    heldout_ids = _unique_string_ids(heldout_row_ids, len(heldout_covariates))
    scaled_utility, scaling = scale_training_utility(
        training_utility,
        outcome_type=outcome_type,
        ddof=int(analysis_config["outcome"]["continuous_scaling_sd_ddof"]),
    )
    materiality_margin = _materiality_margin(analysis_config, outcome_type)

    preprocessor = fit_preprocessor(training_covariates, schema)
    x_train = preprocessor.transform(training_covariates)
    x_heldout = preprocessor.transform(heldout_covariates)

    seeds = LearnerSeeds.derive(
        int(analysis_config["master_seed"]),
        run_id,
        fold_id,
    )
    predictions = fit_predict_prespecified_learners(
        x_train,
        scaled_utility,
        training_treatment,
        x_heldout,
        analysis_config=analysis_config,
        seeds=seeds,
        outcome_type=outcome_type,
    )

    record_config = analysis_config["gate"]["record_adequacy"]
    record = record_adequacy_check(
        observed_covariate_mask(heldout_covariates, schema),
        heldout_invalid_mask,
        minimum_observed_fraction=float(record_config["observed_fraction_minimum"]),
    )
    support_config = analysis_config["gate"]["reference_support"]
    support = reference_support_check(
        x_train,
        training_treatment,
        x_heldout,
        pass_quantile=float(support_config["pass_quantile"]),
    )
    multiplicity_config = analysis_config["gate"]["multiplicity"]
    multiplicity = model_multiplicity_check(
        predictions.effect_matrix,
        materiality_margin=materiality_margin,
        primary_index=0,
        minimum_supporting_estimators=int(
            multiplicity_config["minimum_estimators_supporting_primary_action"]
        ),
    )
    certainty = decision_certainty_check(
        predictions.primary_interval_lower,
        predictions.primary_interval_upper,
        materiality_margin=materiality_margin,
    )
    graded_config = analysis_config["gate"]["uncertainty"]["graded_filter"]
    graded_acceptance = (
        graded_uncertainty_acceptance(
            predictions.primary_effect,
            predictions.primary_interval_lower,
            predictions.primary_interval_upper,
            retention_fraction=float(graded_config["retention_fraction"]),
            trial_ids=trial_id,
            row_ids=heldout_ids,
            master_seed=int(analysis_config["master_seed"]),
            materiality_margin=materiality_margin,
            interval_alpha=float(
                analysis_config["learners"]["primary"]["interval_alpha_primary"]
            ),
        )
        if graded_config["enabled"]
        else None
    )
    gate = construct_gate(
        record.passes,
        support.passes,
        multiplicity.passes,
        certainty.passes,
        decision_uncertainty_essential=analysis_config["gate"]["uncertainty"][
            "essential"
        ],
        graded_uncertainty_acceptance=graded_acceptance,
    )

    fold_labels = np.full(len(heldout_covariates), fold_id, dtype=np.int16)
    uncertainty_only = uncertainty_only_at_matched_coverage(
        predictions.primary_effect,
        predictions.primary_interval_lower,
        predictions.primary_interval_upper,
        gate.complete,
        fold_labels,
        trial_ids=trial_id,
        row_ids=heldout_ids,
        master_seed=int(analysis_config["master_seed"]),
        materiality_margin=materiality_margin,
        interval_alpha=float(
            analysis_config["learners"]["primary"]["interval_alpha_primary"]
        ),
    )
    if uncertainty_only.sum() != gate.complete.sum():  # pragma: no cover
        raise RuntimeError("uncertainty-only coverage does not equal gate coverage")

    return FoldConstruction(
        fold_id=fold_id,
        heldout_row_ids=heldout_ids,
        predictions=predictions,
        record=record,
        support=support,
        multiplicity=multiplicity,
        certainty=certainty,
        gate=gate,
        individualised_action=(predictions.primary_effect > 0.0).astype(np.int8),
        uncertainty_only_acceptance=uncertainty_only,
        preprocessing_features=preprocessor.feature_names(),
        outcome_scaling=scaling,
    )


def run_cross_fitted_construction(
    covariates: pd.DataFrame,
    utility_outcome: ArrayLike,
    treatment: ArrayLike,
    row_ids: ArrayLike,
    *,
    schema: CovariateSchema,
    trial_id: str,
    run_id: str,
    outcome_type: str,
    analysis_config: dict[str, Any],
    invalid_mask: ArrayLike | None = None,
    fold_ids: ArrayLike | None = None,
) -> CrossFittedConstruction:
    """Run every outer fold and assemble row-aligned construction outputs."""

    if not isinstance(covariates, pd.DataFrame) or len(covariates) < 2:
        raise ValueError("covariates must be a DataFrame with at least two rows")
    n = len(covariates)
    outcome = _finite_vector("utility_outcome", utility_outcome, n)
    assigned_treatment = _binary_vector("treatment", treatment, n)
    identifiers = _unique_string_ids(row_ids, n)
    if invalid_mask is None:
        invalid = np.zeros((n, len(schema.columns)), dtype=bool)
    else:
        invalid = np.asarray(invalid_mask)
        if invalid.dtype != np.bool_:
            raise TypeError("invalid_mask must be Boolean")
        if invalid.shape != (n, len(schema.columns)):
            raise ValueError("invalid_mask must match rows and schema columns")

    if fold_ids is None:
        assigned_folds = make_outer_fold_ids(
            assigned_treatment,
            identifiers,
            n_splits=int(analysis_config["cross_fitting"]["outer_folds"]),
            seed=int(analysis_config["cross_fitting"]["primary_seed"]),
        )
    else:
        supplied = np.asarray(fold_ids)
        if supplied.ndim != 1 or supplied.shape[0] != n:
            raise ValueError("fold_ids must have one entry per row")
        iter_outer_folds(supplied)
        assigned_folds = supplied.astype(np.int16, copy=True)

    primary_effect = np.full(n, np.nan)
    lower = np.full(n, np.nan)
    upper = np.full(n, np.nan)
    interaction_effect = np.full(n, np.nan)
    doubly_robust_effect = np.full(n, np.nan)
    check_arrays = {
        "record_adequacy": np.zeros(n, dtype=bool),
        "reference_support": np.zeros(n, dtype=bool),
        "model_multiplicity": np.zeros(n, dtype=bool),
        "decision_uncertainty": np.zeros(n, dtype=bool),
    }
    individualised_action = np.zeros(n, dtype=np.int8)
    uncertainty_only = np.zeros(n, dtype=bool)
    graded_uncertainty = np.zeros(n, dtype=bool)
    observed_fraction = np.full(n, np.nan)
    invalid_present = np.zeros(n, dtype=bool)
    support_score = np.full(n, np.nan)
    support_threshold = np.full(n, np.nan)
    supporting = np.zeros(n, dtype=np.int64)
    opposing = np.zeros(n, dtype=np.int64)
    interval_width = np.full(n, np.nan)
    fold_results = []

    for split in iter_outer_folds(assigned_folds):
        fold = construct_outer_fold(
            training_covariates=covariates.iloc[split.training_indices],
            training_utility=outcome[split.training_indices],
            training_treatment=assigned_treatment[split.training_indices],
            heldout_covariates=covariates.iloc[split.heldout_indices],
            heldout_row_ids=identifiers[split.heldout_indices],
            heldout_invalid_mask=invalid[split.heldout_indices],
            schema=schema,
            trial_id=trial_id,
            run_id=run_id,
            fold_id=split.fold_id,
            outcome_type=outcome_type,
            analysis_config=analysis_config,
        )
        heldout = split.heldout_indices
        primary_effect[heldout] = fold.predictions.primary_effect
        lower[heldout] = fold.predictions.primary_interval_lower
        upper[heldout] = fold.predictions.primary_interval_upper
        interaction_effect[heldout] = fold.predictions.interaction_effect
        doubly_robust_effect[heldout] = fold.predictions.doubly_robust_effect
        for name, values in fold.gate.checks.items():
            check_arrays[name][heldout] = values
        individualised_action[heldout] = fold.individualised_action
        uncertainty_only[heldout] = fold.uncertainty_only_acceptance
        graded_uncertainty[heldout] = fold.gate.graded_uncertainty_acceptance
        observed_fraction[heldout] = fold.record.observed_fraction
        invalid_present[heldout] = fold.record.invalid_present
        support_score[heldout] = fold.support.score
        support_threshold[heldout] = fold.support.threshold
        supporting[heldout] = fold.multiplicity.supporting_estimators
        opposing[heldout] = fold.multiplicity.opposing_estimators
        interval_width[heldout] = fold.certainty.interval_width
        fold_results.append(fold)

    predictions = TreatmentEffectPredictions(
        primary_effect=primary_effect,
        primary_interval_lower=lower,
        primary_interval_upper=upper,
        interaction_effect=interaction_effect,
        doubly_robust_effect=doubly_robust_effect,
    )
    gate = construct_gate(
        **check_arrays,
        decision_uncertainty_essential=analysis_config["gate"]["uncertainty"][
            "essential"
        ],
        graded_uncertainty_acceptance=(
            graded_uncertainty
            if analysis_config["gate"]["uncertainty"]["graded_filter"]["enabled"]
            else None
        ),
    )
    _validate_assembled_outputs(
        predictions,
        gate,
        uncertainty_only,
        assigned_folds,
    )
    return CrossFittedConstruction(
        trial_id=trial_id,
        run_id=run_id,
        outcome_type=outcome_type,
        schema=schema,
        row_ids=identifiers,
        fold_ids=assigned_folds,
        treatment=assigned_treatment.copy(),
        predictions=predictions,
        checks=check_arrays,
        gate=gate,
        individualised_action=individualised_action,
        uncertainty_only_acceptance=uncertainty_only,
        record_observed_fraction=observed_fraction,
        record_invalid_present=invalid_present,
        support_score=support_score,
        support_threshold=support_threshold,
        multiplicity_supporting_estimators=supporting,
        multiplicity_opposing_estimators=opposing,
        interval_width=interval_width,
        folds=tuple(fold_results),
    )


def scale_training_utility(
    utility: ArrayLike,
    *,
    outcome_type: str,
    ddof: int = 1,
) -> tuple[NDArray[np.float64], OutcomeScaling]:
    """Scale continuous utility using training rows; leave binary utility intact."""

    values = np.asarray(utility, dtype=float)
    if values.ndim != 1 or values.shape[0] < 2 or not np.isfinite(values).all():
        raise ValueError("training utility must be a finite one-dimensional array")
    if outcome_type == "binary":
        if not np.isin(values, (0.0, 1.0)).all():
            raise ValueError("binary utility must contain only zero and one")
        return values.copy(), OutcomeScaling(center=0.0, scale=1.0, ddof=0)
    if outcome_type != "continuous":
        raise ValueError("outcome_type must be binary or continuous")
    if (
        not isinstance(ddof, int)
        or isinstance(ddof, bool)
        or not 0 <= ddof < len(values)
    ):
        raise ValueError("ddof must be a valid non-negative integer")
    center = float(values.mean())
    scale = float(values.std(ddof=ddof))
    if not math.isfinite(scale) or scale <= 0.0:
        raise ValueError("continuous training utility must have positive variance")
    return (values - center) / scale, OutcomeScaling(center, scale, ddof)


def _materiality_margin(analysis_config: dict[str, Any], outcome_type: str) -> float:
    if outcome_type == "binary":
        return float(analysis_config["outcome"]["binary_materiality_margin"])
    if outcome_type == "continuous":
        return float(analysis_config["outcome"]["continuous_materiality_margin_sd"])
    raise ValueError("outcome_type must be binary or continuous")


def _finite_vector(
    name: str, values: ArrayLike, expected_size: int
) -> NDArray[np.float64]:
    array = np.asarray(values, dtype=float)
    if array.ndim != 1 or array.shape[0] != expected_size:
        raise ValueError(f"{name} must have one entry per row")
    if not np.isfinite(array).all():
        raise ValueError(f"{name} must contain only finite values")
    return array


def _binary_vector(
    name: str, values: ArrayLike, expected_size: int
) -> NDArray[np.int8]:
    array = np.asarray(values)
    if array.ndim != 1 or array.shape[0] != expected_size:
        raise ValueError(f"{name} must have one entry per row")
    if not np.isin(array, (0, 1)).all():
        raise ValueError(f"{name} must contain only zero and one")
    return array.astype(np.int8, copy=False)


def _unique_string_ids(values: ArrayLike, expected_size: int) -> NDArray[np.str_]:
    array = np.asarray(values)
    if array.ndim != 1 or array.shape[0] != expected_size:
        raise ValueError("row_ids must have one entry per row")
    identifiers = array.astype(str)
    if np.unique(identifiers).shape[0] != expected_size:
        raise ValueError("row_ids must be unique after string conversion")
    return identifiers


def _validate_assembled_outputs(
    predictions: TreatmentEffectPredictions,
    gate: GateSelections,
    uncertainty_only: NDArray[np.bool_],
    fold_ids: NDArray[np.int16],
) -> None:
    if not np.isfinite(predictions.effect_matrix).all():
        raise RuntimeError("cross-fitted effect matrix is incomplete")
    if (
        not np.isfinite(predictions.primary_interval_lower).all()
        or not np.isfinite(predictions.primary_interval_upper).all()
    ):
        raise RuntimeError("cross-fitted interval arrays are incomplete")
    for fold_id in np.unique(fold_ids):
        in_fold = fold_ids == fold_id
        if uncertainty_only[in_fold].sum() != gate.complete[in_fold].sum():
            raise RuntimeError("matched coverage differs inside an outer fold")
