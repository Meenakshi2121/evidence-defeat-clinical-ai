"""Non-compensatory gate construction and exact-coverage selection."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping
from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray
from scipy.stats import norm

from evidence_defeat.seeds import derive_random_deferral_seed

CHECK_NAMES = (
    "record_adequacy",
    "reference_support",
    "model_multiplicity",
    "decision_uncertainty",
)


@dataclass(frozen=True)
class GateSelections:
    """Complete, single-check and leave-one-check-out selections."""

    checks: Mapping[str, NDArray[np.bool_]]
    essential_checks: tuple[str, ...]
    evidence_qualified: NDArray[np.bool_]
    graded_uncertainty_applied: bool
    graded_uncertainty_acceptance: NDArray[np.bool_]
    complete: NDArray[np.bool_]
    single_check: Mapping[str, NDArray[np.bool_]]
    leave_one_out: Mapping[str, NDArray[np.bool_]]


@dataclass(frozen=True)
class RandomDeferralSelections:
    """Exact-coverage selections across deterministic random repetitions."""

    acceptance: NDArray[np.bool_]
    repetition_seeds: NDArray[np.uint32]


def construct_gate(
    record_adequacy: ArrayLike,
    reference_support: ArrayLike,
    model_multiplicity: ArrayLike,
    decision_uncertainty: ArrayLike,
    *,
    decision_uncertainty_essential: bool = True,
    graded_uncertainty_acceptance: ArrayLike | None = None,
) -> GateSelections:
    """Construct the logical-AND gate and candidate-specific ablations.

    Decision uncertainty is always computed and remains available as a
    diagnostic selector. Candidate C001 makes it non-essential so the complete
    gate represents the three Nyaya-inspired evidence-defeat conditions while
    uncertainty remains an external matched-coverage comparator.
    """

    if not isinstance(decision_uncertainty_essential, bool):
        raise TypeError("decision_uncertainty_essential must be Boolean")

    raw = {
        "record_adequacy": record_adequacy,
        "reference_support": reference_support,
        "model_multiplicity": model_multiplicity,
        "decision_uncertainty": decision_uncertainty,
    }
    checks = {name: _boolean_vector(name, raw[name]) for name in CHECK_NAMES}
    sizes = {array.shape[0] for array in checks.values()}
    if len(sizes) != 1:
        raise ValueError("all checks must have the same number of rows")

    essential_checks = (
        CHECK_NAMES
        if decision_uncertainty_essential
        else tuple(name for name in CHECK_NAMES if name != "decision_uncertainty")
    )
    evidence_qualified = np.logical_and.reduce(
        [checks[name] for name in essential_checks]
    )
    if graded_uncertainty_acceptance is None:
        graded_acceptance = np.ones(next(iter(sizes)), dtype=bool)
        graded_applied = False
    else:
        graded_acceptance = _boolean_vector(
            "graded_uncertainty_acceptance",
            graded_uncertainty_acceptance,
        )
        if graded_acceptance.shape[0] != next(iter(sizes)):
            raise ValueError(
                "graded_uncertainty_acceptance must match the check row count"
            )
        graded_applied = True

    complete = evidence_qualified & graded_acceptance
    single_check = {name: checks[name].copy() for name in CHECK_NAMES}
    leave_one_out = {
        f"without_{omitted}": np.logical_and.reduce(
            [checks[name] for name in essential_checks if name != omitted]
        )
        & graded_acceptance
        for omitted in essential_checks
    }
    return GateSelections(
        checks=checks,
        essential_checks=essential_checks,
        evidence_qualified=evidence_qualified,
        graded_uncertainty_applied=graded_applied,
        graded_uncertainty_acceptance=graded_acceptance,
        complete=complete,
        single_check=single_check,
        leave_one_out=leave_one_out,
    )


def graded_uncertainty_acceptance(
    effect: ArrayLike,
    interval_lower: ArrayLike,
    interval_upper: ArrayLike,
    *,
    retention_fraction: float,
    trial_ids: ArrayLike | str,
    row_ids: ArrayLike,
    master_seed: int,
    materiality_margin: float,
    interval_alpha: float = 0.05,
) -> NDArray[np.bool_]:
    """Retain the highest uncertainty scores at a fixed fold-level fraction.

    The fraction is applied to every held-out fold independently by the caller.
    It is a graded second-stage filter, not a compensatory score: downstream
    construction still requires every essential evidence check to pass.
    """

    if (
        not isinstance(retention_fraction, (int, float))
        or isinstance(retention_fraction, bool)
        or not math.isfinite(float(retention_fraction))
        or not 0.0 < float(retention_fraction) <= 1.0
    ):
        raise ValueError("retention_fraction must lie inside (0, 1]")
    score = uncertainty_ranking_score(
        effect,
        interval_lower,
        interval_upper,
        materiality_margin=materiality_margin,
        interval_alpha=interval_alpha,
    )
    accept_count = math.floor(float(retention_fraction) * score.shape[0])
    return select_exact_count(
        score,
        accept_count,
        trial_ids=trial_ids,
        row_ids=row_ids,
        master_seed=master_seed,
        accept_highest=True,
    )


def apply_deferral_policy(
    accepts_individualisation: ArrayLike,
    individualised_action: ArrayLike,
    default_action: ArrayLike | int,
) -> NDArray[np.int8]:
    """Apply individualised actions when accepted and the default otherwise."""

    accepts = _boolean_vector("accepts_individualisation", accepts_individualisation)
    individualised = _binary_action_vector(
        "individualised_action",
        individualised_action,
        accepts.shape[0],
    )
    default = np.asarray(default_action)
    if default.ndim == 0:
        if default.item() not in (0, 1):
            raise ValueError("default_action must contain only zero and one")
        default = np.full(accepts.shape[0], default.item(), dtype=np.int8)
    else:
        default = _binary_action_vector("default_action", default, accepts.shape[0])
    return np.where(accepts, individualised, default).astype(np.int8)


def uncertainty_ranking_score(
    effect: ArrayLike,
    interval_lower: ArrayLike,
    interval_upper: ArrayLike,
    *,
    materiality_margin: float,
    interval_alpha: float = 0.05,
) -> NDArray[np.float64]:
    """Calculate (absolute effect - delta) divided by interval-derived SE."""

    estimate = _finite_float_vector("effect", effect)
    lower = _finite_float_vector("interval_lower", interval_lower)
    upper = _finite_float_vector("interval_upper", interval_upper)
    if estimate.shape != lower.shape or estimate.shape != upper.shape:
        raise ValueError("effect and interval arrays must have equal shapes")
    if np.any(lower >= upper):
        raise ValueError("each interval must have strictly positive width")
    if materiality_margin < 0.0 or not math.isfinite(materiality_margin):
        raise ValueError("materiality_margin must be finite and non-negative")
    if not 0.0 < interval_alpha < 1.0:
        raise ValueError("interval_alpha must lie strictly between zero and one")

    critical_value = float(norm.ppf(1.0 - interval_alpha / 2.0))
    standard_error = (upper - lower) / (2.0 * critical_value)
    return (np.abs(estimate) - materiality_margin) / standard_error


def deterministic_tie_keys(
    trial_ids: ArrayLike | str,
    row_ids: ArrayLike,
    master_seed: int,
    *,
    size: int | None = None,
) -> NDArray[np.str_]:
    """Create ascending SHA-256 keys from canonical JSON identifier tuples."""

    if not isinstance(master_seed, int) or isinstance(master_seed, bool):
        raise TypeError("master_seed must be an integer")
    if master_seed < 0:
        raise ValueError("master_seed must be non-negative")

    rows = _identifier_vector("row_ids", row_ids, size=size)
    trials = _identifier_vector("trial_ids", trial_ids, size=rows.shape[0])
    pairs = list(zip(trials, rows))
    if len(set(pairs)) != len(pairs):
        raise ValueError("trial_id and row_id pairs must be unique")

    keys = []
    for trial_id, row_id in pairs:
        payload = json.dumps(
            [trial_id, row_id, master_seed],
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        keys.append(hashlib.sha256(payload).hexdigest())
    return np.asarray(keys, dtype=str)


def select_exact_count(
    ranking_score: ArrayLike,
    accept_count: int,
    *,
    trial_ids: ArrayLike | str,
    row_ids: ArrayLike,
    master_seed: int,
    accept_highest: bool = True,
) -> NDArray[np.bool_]:
    """Select an exact count, breaking score ties by the locked hash rule."""

    score = _finite_float_vector("ranking_score", ranking_score)
    if not isinstance(accept_count, int) or isinstance(accept_count, bool):
        raise TypeError("accept_count must be an integer")
    if not 0 <= accept_count <= score.shape[0]:
        raise ValueError("accept_count must lie between zero and the row count")
    keys = deterministic_tie_keys(
        trial_ids,
        row_ids,
        master_seed,
        size=score.shape[0],
    )

    primary_order = -score if accept_highest else score
    order = np.lexsort((keys, primary_order))
    selected = np.zeros(score.shape[0], dtype=bool)
    selected[order[:accept_count]] = True
    return selected


def match_coverage_within_folds(
    ranking_score: ArrayLike,
    target_acceptance: ArrayLike,
    fold_ids: ArrayLike,
    *,
    trial_ids: ArrayLike | str,
    row_ids: ArrayLike,
    master_seed: int,
    accept_highest: bool = True,
) -> NDArray[np.bool_]:
    """Match the target number accepted separately inside every held-out fold."""

    score = _finite_float_vector("ranking_score", ranking_score)
    target = _boolean_vector("target_acceptance", target_acceptance)
    if score.shape != target.shape:
        raise ValueError("ranking_score and target_acceptance must have equal shapes")
    folds = np.asarray(fold_ids)
    if folds.ndim != 1 or folds.shape[0] != score.shape[0]:
        raise ValueError("fold_ids must have one entry per row")
    if folds.dtype == np.bool_ or not np.issubdtype(folds.dtype, np.integer):
        raise TypeError("fold_ids must contain integers")
    if np.any(folds < 0):
        raise ValueError("fold_ids must be non-negative")
    rows = _identifier_vector("row_ids", row_ids, size=score.shape[0])
    trials = _identifier_vector("trial_ids", trial_ids, size=score.shape[0])

    selected = np.zeros(score.shape[0], dtype=bool)
    for fold in np.unique(folds):
        in_fold = folds == fold
        fold_selection = select_exact_count(
            score[in_fold],
            int(target[in_fold].sum()),
            trial_ids=trials[in_fold],
            row_ids=rows[in_fold],
            master_seed=master_seed,
            accept_highest=accept_highest,
        )
        selected[in_fold] = fold_selection
        if selected[in_fold].sum() != target[in_fold].sum():  # pragma: no cover
            raise RuntimeError("internal error: exact fold coverage was not matched")
    return selected


def uncertainty_only_at_matched_coverage(
    effect: ArrayLike,
    interval_lower: ArrayLike,
    interval_upper: ArrayLike,
    complete_gate: ArrayLike,
    fold_ids: ArrayLike,
    *,
    trial_ids: ArrayLike | str,
    row_ids: ArrayLike,
    master_seed: int,
    materiality_margin: float,
    interval_alpha: float = 0.05,
) -> NDArray[np.bool_]:
    """Construct the uncertainty-only comparator at exact gate coverage."""

    score = uncertainty_ranking_score(
        effect,
        interval_lower,
        interval_upper,
        materiality_margin=materiality_margin,
        interval_alpha=interval_alpha,
    )
    return match_coverage_within_folds(
        score,
        complete_gate,
        fold_ids,
        trial_ids=trial_ids,
        row_ids=row_ids,
        master_seed=master_seed,
        accept_highest=True,
    )


def random_deferral_at_matched_coverage(
    complete_gate: ArrayLike,
    fold_ids: ArrayLike,
    *,
    trial_ids: ArrayLike | str,
    row_ids: ArrayLike,
    master_seed: int,
    run_id: str,
    repetitions: int = 100,
) -> RandomDeferralSelections:
    """Select hash-randomised participants at exact gate coverage per fold."""

    target = _boolean_vector("complete_gate", complete_gate)
    folds = np.asarray(fold_ids)
    if folds.ndim != 1 or folds.shape[0] != target.shape[0]:
        raise ValueError("fold_ids must have one entry per row")
    if not run_id:
        raise ValueError("run_id must not be empty")
    if not isinstance(repetitions, int) or isinstance(repetitions, bool):
        raise TypeError("repetitions must be an integer")
    if repetitions < 1:
        raise ValueError("repetitions must be positive")

    acceptance = np.zeros((repetitions, target.shape[0]), dtype=bool)
    seeds = np.zeros(repetitions, dtype=np.uint32)
    tied_scores = np.zeros(target.shape[0], dtype=float)
    for repetition_id in range(repetitions):
        seed = derive_random_deferral_seed(master_seed, run_id, repetition_id)
        seeds[repetition_id] = seed
        acceptance[repetition_id] = match_coverage_within_folds(
            tied_scores,
            target,
            folds,
            trial_ids=trial_ids,
            row_ids=row_ids,
            master_seed=seed,
            accept_highest=True,
        )
    return RandomDeferralSelections(
        acceptance=acceptance,
        repetition_seeds=seeds,
    )


def _boolean_vector(name: str, values: ArrayLike) -> NDArray[np.bool_]:
    array = np.asarray(values)
    if array.dtype != np.bool_:
        raise TypeError(f"{name} must be Boolean")
    if array.ndim != 1 or array.shape[0] < 1:
        raise ValueError(f"{name} must be a non-empty one-dimensional array")
    return array.copy()


def _binary_action_vector(
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


def _finite_float_vector(name: str, values: ArrayLike) -> NDArray[np.float64]:
    array = np.asarray(values, dtype=float)
    if array.ndim != 1 or array.shape[0] < 1:
        raise ValueError(f"{name} must be a non-empty one-dimensional array")
    if not np.isfinite(array).all():
        raise ValueError(f"{name} must contain only finite values")
    return array


def _identifier_vector(
    name: str,
    values: ArrayLike | str,
    *,
    size: int | None,
) -> NDArray[np.str_]:
    array = np.asarray(values)
    if array.ndim == 0:
        if size is None:
            raise ValueError(f"size is required when {name} is scalar")
        array = np.repeat(array, size)
    if array.ndim != 1 or array.shape[0] < 1:
        raise ValueError(f"{name} must be a non-empty one-dimensional array")
    if size is not None and array.shape[0] != size:
        raise ValueError(f"{name} must have one entry per row")
    return array.astype(str)
