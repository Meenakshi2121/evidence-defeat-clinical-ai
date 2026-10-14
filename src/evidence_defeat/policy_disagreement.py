"""Coverage-matched near-optimal-policy disagreement comparator."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
from numpy.typing import ArrayLike, NDArray

from evidence_defeat.bootstrap import treatment_stratified_bootstrap
from evidence_defeat.evaluation import (
    CrossFittedPolicyEvaluation,
    aipw_policy_contributions,
    make_inner_fold_ids,
)
from evidence_defeat.folds import iter_outer_folds
from evidence_defeat.learners import ESTIMATOR_ORDER, fit_predict_effect_learner
from evidence_defeat.pipeline import CrossFittedConstruction, scale_training_utility
from evidence_defeat.preprocessing import CovariateSchema, fit_preprocessor
from evidence_defeat.seeds import derive_model_seed
from evidence_defeat.selection import select_exact_count


@dataclass(frozen=True)
class NearOptimalSelection:
    """Candidate-retention decision under the prespecified one-SE rule."""

    retained: NDArray[np.bool_]
    best_candidate_index: int
    threshold: float
    fallback_used: bool


@dataclass(frozen=True)
class FoldPolicyDisagreement:
    """Disclosure-sensitive internal comparator results for one outer fold."""

    fold_id: int
    heldout_row_ids: NDArray[np.str_]
    acceptance: NDArray[np.bool_]
    disagreement_score: NDArray[np.float64]
    candidate_count: int
    retained_count: int
    fallback_used: bool


@dataclass(frozen=True)
class CrossFittedPolicyDisagreement:
    """Row-aligned policy-disagreement acceptance from every outer fold."""

    acceptance: NDArray[np.bool_]
    disagreement_score: NDArray[np.float64]
    fold_ids: NDArray[np.int16]
    folds: tuple[FoldPolicyDisagreement, ...]


def select_near_optimal_candidates(
    values: ArrayLike,
    standard_errors: ArrayLike,
    *,
    minimum_count: int,
) -> NearOptimalSelection:
    """Retain candidates within one best-policy SE, with a ranked fallback."""

    estimated_values = _finite_vector("values", values)
    errors = _finite_vector("standard_errors", standard_errors)
    if estimated_values.shape != errors.shape:
        raise ValueError("values and standard_errors must have equal shapes")
    if np.any(errors < 0.0):
        raise ValueError("standard_errors must be non-negative")
    if (
        not isinstance(minimum_count, int)
        or isinstance(minimum_count, bool)
        or not 1 <= minimum_count <= estimated_values.shape[0]
    ):
        raise ValueError("minimum_count must lie within the candidate count")

    best_index = int(np.argmax(estimated_values))
    threshold = float(estimated_values[best_index] - errors[best_index])
    retained = estimated_values >= threshold
    fallback = int(retained.sum()) < minimum_count
    if fallback:
        order = np.lexsort((np.arange(estimated_values.shape[0]), -estimated_values))
        retained = np.zeros(estimated_values.shape[0], dtype=bool)
        retained[order[:minimum_count]] = True
    return NearOptimalSelection(
        retained=retained,
        best_candidate_index=best_index,
        threshold=threshold,
        fallback_used=fallback,
    )


def policy_vote_disagreement(candidate_actions: ArrayLike) -> NDArray[np.float64]:
    """Return one minus the largest binary action-vote share per participant."""

    actions = np.asarray(candidate_actions)
    if actions.ndim != 2 or actions.shape[0] < 1 or actions.shape[1] < 1:
        raise ValueError("candidate_actions must be a non-empty two-dimensional array")
    if not np.isin(actions, (0, 1)).all():
        raise ValueError("candidate_actions must contain only zero and one")
    treatment_one_share = actions.astype(float).mean(axis=0)
    result = 1.0 - np.maximum(treatment_one_share, 1.0 - treatment_one_share)
    if np.any((result < 0.0) | (result > 0.5)):  # pragma: no cover
        raise RuntimeError("binary vote disagreement lies outside [0, 0.5]")
    return result


def run_cross_fitted_policy_disagreement(
    construction: CrossFittedConstruction,
    evaluation: CrossFittedPolicyEvaluation,
    covariates: pd.DataFrame,
    utility_outcome: ArrayLike,
    treatment: ArrayLike,
    row_ids: ArrayLike,
    *,
    schema: CovariateSchema,
    outcome_type: str,
    analysis_config: dict[str, Any],
) -> CrossFittedPolicyDisagreement:
    """Build the prespecified comparator without using outer-heldout outcomes."""

    if not isinstance(covariates, pd.DataFrame):
        raise TypeError("covariates must be a pandas DataFrame")
    n = len(covariates)
    outcome = _finite_vector("utility_outcome", utility_outcome, n)
    assigned = _binary_vector("treatment", treatment, n)
    identifiers = _unique_ids(row_ids, n)
    _validate_linked_inputs(
        construction,
        evaluation,
        identifiers,
        assigned,
        schema,
        outcome_type,
    )

    specification = analysis_config["comparators"]["near_optimal_policy_disagreement"]
    if specification["candidate_value_estimator"] != "inner_cross_fitted_aipw":
        raise ValueError(
            "candidate value estimator must remain inner-cross-fitted AIPW"
        )
    learners = tuple(specification["candidate_learners"])
    if learners != ESTIMATOR_ORDER:
        raise ValueError(
            "candidate learners must match the prespecified estimator order"
        )
    candidates_per_learner = _positive_integer(
        "bootstrap_candidates_per_learner",
        specification["bootstrap_candidates_per_learner"],
    )
    minimum_retained = _positive_integer(
        "minimum_near_optimal_policies",
        specification["minimum_near_optimal_policies"],
    )
    candidate_count = len(learners) * candidates_per_learner
    if minimum_retained > candidate_count:
        raise ValueError("minimum retained policies exceeds candidate count")

    acceptance = np.zeros(n, dtype=bool)
    disagreement = np.full(n, np.nan)
    fold_results: list[FoldPolicyDisagreement] = []
    evaluation_folds = {fold.fold_id: fold for fold in evaluation.folds}
    construction_folds = {fold.fold_id: fold for fold in construction.folds}

    for outer_split in iter_outer_folds(construction.fold_ids):
        fold_id = outer_split.fold_id
        if fold_id not in evaluation_folds or fold_id not in construction_folds:
            raise ValueError("linked results are missing an outer fold")
        training = outer_split.training_indices
        heldout = outer_split.heldout_indices
        training_covariates = covariates.iloc[training]
        heldout_covariates = covariates.iloc[heldout]
        training_treatment = assigned[training]
        training_row_ids = identifiers[training]
        scaled_utility, scaling = scale_training_utility(
            outcome[training],
            outcome_type=outcome_type,
            ddof=int(analysis_config["outcome"]["continuous_scaling_sd_ddof"]),
        )
        construction_scaling = construction_folds[fold_id].outcome_scaling
        if (
            scaling.ddof != construction_scaling.ddof
            or not math.isclose(scaling.center, construction_scaling.center)
            or not math.isclose(scaling.scale, construction_scaling.scale)
        ):
            raise ValueError("comparator and construction outcome scaling differ")

        nuisance = evaluation_folds[fold_id]
        if nuisance.training_mu0.shape != (training.shape[0],) or (
            nuisance.training_mu1.shape != (training.shape[0],)
        ):
            raise ValueError("inner nuisance predictions do not match training rows")
        inner_fold_ids = make_inner_fold_ids(
            training_treatment,
            training_row_ids,
            run_id=construction.run_id,
            outer_fold_id=fold_id,
            analysis_config=analysis_config,
        )

        values = np.zeros(candidate_count, dtype=float)
        errors = np.zeros(candidate_count, dtype=float)
        heldout_actions = np.zeros(
            (candidate_count, heldout.shape[0]),
            dtype=np.int8,
        )
        candidate_position = 0
        for learner_id in learners:
            for bootstrap_id in range(candidates_per_learner):
                training_actions, candidate_heldout_actions = _fit_candidate_policy(
                    learner_id=learner_id,
                    bootstrap_id=bootstrap_id,
                    training_covariates=training_covariates,
                    scaled_training_utility=scaled_utility,
                    training_treatment=training_treatment,
                    training_row_ids=training_row_ids,
                    heldout_covariates=heldout_covariates,
                    inner_fold_ids=inner_fold_ids,
                    schema=schema,
                    run_id=construction.run_id,
                    outer_fold_id=fold_id,
                    outcome_type=outcome_type,
                    analysis_config=analysis_config,
                )
                contributions = aipw_policy_contributions(
                    training_actions,
                    scaled_utility,
                    training_treatment,
                    nuisance.training_mu0,
                    nuisance.training_mu1,
                    nuisance.propensity_treatment_1,
                )
                values[candidate_position] = float(contributions.mean())
                errors[candidate_position] = _standard_error(contributions)
                heldout_actions[candidate_position] = candidate_heldout_actions
                candidate_position += 1

        selection = select_near_optimal_candidates(
            values,
            errors,
            minimum_count=minimum_retained,
        )
        fold_disagreement = policy_vote_disagreement(
            heldout_actions[selection.retained]
        )
        fold_acceptance = select_exact_count(
            fold_disagreement,
            int(construction.gate.complete[heldout].sum()),
            trial_ids=construction.trial_id,
            row_ids=identifiers[heldout],
            master_seed=int(analysis_config["master_seed"]),
            accept_highest=False,
        )
        acceptance[heldout] = fold_acceptance
        disagreement[heldout] = fold_disagreement
        fold_results.append(
            FoldPolicyDisagreement(
                fold_id=fold_id,
                heldout_row_ids=identifiers[heldout].copy(),
                acceptance=fold_acceptance,
                disagreement_score=fold_disagreement,
                candidate_count=candidate_count,
                retained_count=int(selection.retained.sum()),
                fallback_used=selection.fallback_used,
            )
        )

    if not np.isfinite(disagreement).all():
        raise RuntimeError("policy-disagreement scores are incomplete")
    _assert_exact_fold_coverage(
        acceptance,
        construction.gate.complete,
        construction.fold_ids,
    )
    return CrossFittedPolicyDisagreement(
        acceptance=acceptance,
        disagreement_score=disagreement,
        fold_ids=construction.fold_ids.copy(),
        folds=tuple(fold_results),
    )


def _fit_candidate_policy(
    *,
    learner_id: str,
    bootstrap_id: int,
    training_covariates: pd.DataFrame,
    scaled_training_utility: NDArray[np.float64],
    training_treatment: NDArray[np.int8],
    training_row_ids: NDArray[np.str_],
    heldout_covariates: pd.DataFrame,
    inner_fold_ids: NDArray[np.int16],
    schema: CovariateSchema,
    run_id: str,
    outer_fold_id: int,
    outcome_type: str,
    analysis_config: dict[str, Any],
) -> tuple[NDArray[np.int8], NDArray[np.int8]]:
    cross_fitted_actions = np.zeros(len(training_covariates), dtype=np.int8)
    for inner_split in iter_outer_folds(inner_fold_ids):
        stage = f"inner_{inner_split.fold_id}"
        predicted_effect = _fit_bootstrap_effects(
            learner_id=learner_id,
            bootstrap_id=bootstrap_id,
            base_positions=inner_split.training_indices,
            prediction_positions=inner_split.heldout_indices,
            training_covariates=training_covariates,
            scaled_training_utility=scaled_training_utility,
            training_treatment=training_treatment,
            training_row_ids=training_row_ids,
            external_prediction_covariates=None,
            schema=schema,
            run_id=run_id,
            outer_fold_id=outer_fold_id,
            stage=stage,
            outcome_type=outcome_type,
            analysis_config=analysis_config,
        )
        cross_fitted_actions[inner_split.heldout_indices] = (
            predicted_effect > 0.0
        ).astype(np.int8)

    heldout_effect = _fit_bootstrap_effects(
        learner_id=learner_id,
        bootstrap_id=bootstrap_id,
        base_positions=np.arange(len(training_covariates), dtype=np.int64),
        prediction_positions=None,
        training_covariates=training_covariates,
        scaled_training_utility=scaled_training_utility,
        training_treatment=training_treatment,
        training_row_ids=training_row_ids,
        external_prediction_covariates=heldout_covariates,
        schema=schema,
        run_id=run_id,
        outer_fold_id=outer_fold_id,
        stage="outer_full",
        outcome_type=outcome_type,
        analysis_config=analysis_config,
    )
    return cross_fitted_actions, (heldout_effect > 0.0).astype(np.int8)


def _fit_bootstrap_effects(
    *,
    learner_id: str,
    bootstrap_id: int,
    base_positions: NDArray[np.int64],
    prediction_positions: NDArray[np.int64] | None,
    training_covariates: pd.DataFrame,
    scaled_training_utility: NDArray[np.float64],
    training_treatment: NDArray[np.int8],
    training_row_ids: NDArray[np.str_],
    external_prediction_covariates: pd.DataFrame | None,
    schema: CovariateSchema,
    run_id: str,
    outer_fold_id: int,
    stage: str,
    outcome_type: str,
    analysis_config: dict[str, Any],
) -> NDArray[np.float64]:
    master_seed = int(analysis_config["master_seed"])
    bootstrap_seed = derive_model_seed(
        master_seed,
        run_id,
        outer_fold_id,
        f"near_optimal_bootstrap:{learner_id}:{bootstrap_id}:{stage}",
    )
    local_sample = treatment_stratified_bootstrap(
        training_treatment[base_positions],
        training_row_ids[base_positions],
        seed=bootstrap_seed,
        repetition_id=bootstrap_id,
    )
    sampled_positions = base_positions[local_sample.source_indices]
    fit_frame = training_covariates.iloc[sampled_positions].reset_index(drop=True)
    preprocessor = fit_preprocessor(fit_frame, schema)
    x_fit = preprocessor.transform(fit_frame)
    if external_prediction_covariates is None:
        if prediction_positions is None:  # pragma: no cover - internal contract
            raise RuntimeError("prediction positions are missing")
        prediction_frame = training_covariates.iloc[prediction_positions]
    else:
        if prediction_positions is not None:  # pragma: no cover - internal contract
            raise RuntimeError("two prediction sources were supplied")
        prediction_frame = external_prediction_covariates
    x_prediction = preprocessor.transform(prediction_frame)
    model_seed = derive_model_seed(
        master_seed,
        run_id,
        outer_fold_id,
        f"near_optimal_model:{learner_id}:{bootstrap_id}:{stage}",
    )
    return fit_predict_effect_learner(
        learner_id,
        x_fit,
        scaled_training_utility[sampled_positions],
        training_treatment[sampled_positions],
        x_prediction,
        analysis_config=analysis_config,
        random_state=model_seed,
        outcome_type=outcome_type,
    )


def _assert_exact_fold_coverage(
    acceptance: NDArray[np.bool_],
    target: NDArray[np.bool_],
    fold_ids: NDArray[np.int16],
) -> None:
    for fold_id in np.unique(fold_ids):
        in_fold = fold_ids == fold_id
        if acceptance[in_fold].sum() != target[in_fold].sum():
            raise RuntimeError("policy-disagreement comparator did not match coverage")


def _validate_linked_inputs(
    construction: CrossFittedConstruction,
    evaluation: CrossFittedPolicyEvaluation,
    row_ids: NDArray[np.str_],
    treatment: NDArray[np.int8],
    schema: CovariateSchema,
    outcome_type: str,
) -> None:
    if construction.trial_id != evaluation.trial_id:
        raise ValueError("construction and evaluation trial identifiers differ")
    if construction.run_id != evaluation.run_id:
        raise ValueError("construction and evaluation run identifiers differ")
    if not np.array_equal(row_ids, construction.row_ids) or not np.array_equal(
        row_ids,
        evaluation.row_ids,
    ):
        raise ValueError("row identifiers do not match linked results")
    if not np.array_equal(treatment, construction.treatment):
        raise ValueError("treatment does not match construction")
    if schema != construction.schema or outcome_type != construction.outcome_type:
        raise ValueError("schema or outcome type does not match construction")


def _standard_error(values: NDArray[np.float64]) -> float:
    if values.shape[0] < 2:
        raise ValueError("at least two contributions are required")
    return float(values.std(ddof=1) / math.sqrt(values.shape[0]))


def _positive_integer(name: str, value: Any) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise ValueError(f"{name} must be a positive integer")
    return value


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


def _unique_ids(values: ArrayLike, expected_size: int) -> NDArray[np.str_]:
    array = np.asarray(values)
    if array.ndim != 1 or array.shape[0] != expected_size:
        raise ValueError("row_ids must have one entry per row")
    identifiers = array.astype(str)
    if np.unique(identifiers).shape[0] != expected_size:
        raise ValueError("row_ids must be unique")
    return identifiers
