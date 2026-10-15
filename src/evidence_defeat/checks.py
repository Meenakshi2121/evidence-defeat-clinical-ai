"""Pure, outcome-blind implementations of the four evidence checks."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray
from sklearn.neighbors import NearestNeighbors


@dataclass(frozen=True)
class RecordAdequacyResult:
    """Record-completeness evidence and the resulting Boolean check."""

    passes: NDArray[np.bool_]
    observed_fraction: NDArray[np.float64]
    invalid_present: NDArray[np.bool_]


@dataclass(frozen=True)
class ReferenceSupportResult:
    """Arm-specific neighbour distances and training-calibrated support check."""

    passes: NDArray[np.bool_]
    score: NDArray[np.float64]
    arm_0_mean_distance: NDArray[np.float64]
    arm_1_mean_distance: NDArray[np.float64]
    threshold: float
    training_scores: NDArray[np.float64]
    neighbours: int


@dataclass(frozen=True)
class ModelMultiplicityResult:
    """Material direction votes and action-stability check."""

    passes: NDArray[np.bool_]
    directions: NDArray[np.int8]
    primary_action: NDArray[np.int8]
    supporting_estimators: NDArray[np.int64]
    opposing_estimators: NDArray[np.int64]


@dataclass(frozen=True)
class DecisionCertaintyResult:
    """Whether the primary interval clears the clinical indifference region."""

    passes: NDArray[np.bool_]
    interval_width: NDArray[np.float64]


def record_adequacy_check(
    observed_mask: ArrayLike,
    invalid_mask: ArrayLike | None = None,
    *,
    minimum_observed_fraction: float = 0.80,
) -> RecordAdequacyResult:
    """Pass records that are sufficiently observed and contain no invalid value."""

    observed = _boolean_matrix("observed_mask", observed_mask)
    if not 0.0 <= minimum_observed_fraction <= 1.0:
        raise ValueError("minimum_observed_fraction must lie in [0, 1]")

    if invalid_mask is None:
        invalid_present = np.zeros(observed.shape[0], dtype=bool)
    else:
        invalid = np.asarray(invalid_mask)
        if invalid.dtype != np.bool_:
            raise TypeError("invalid_mask must be Boolean")
        if invalid.ndim == 1:
            if invalid.shape[0] != observed.shape[0]:
                raise ValueError("invalid_mask row count must match observed_mask")
            invalid_present = invalid.copy()
        elif invalid.ndim == 2:
            if invalid.shape != observed.shape:
                raise ValueError(
                    "two-dimensional invalid_mask must match observed_mask"
                )
            invalid_present = invalid.any(axis=1)
        else:
            raise ValueError("invalid_mask must be one- or two-dimensional")

    fraction = observed.mean(axis=1)
    passes = (fraction >= minimum_observed_fraction) & ~invalid_present
    return RecordAdequacyResult(
        passes=passes,
        observed_fraction=fraction,
        invalid_present=invalid_present,
    )


def prescribed_neighbour_count(n_train: int) -> int:
    """Return k = min(50, max(10, ceiling(sqrt(n_train))))."""

    if not isinstance(n_train, int) or isinstance(n_train, bool) or n_train < 1:
        raise ValueError("n_train must be a positive integer")
    return min(50, max(10, math.ceil(math.sqrt(n_train))))


def reference_support_check(
    training_covariates: ArrayLike,
    training_treatment: ArrayLike,
    heldout_covariates: ArrayLike,
    *,
    pass_quantile: float = 0.975,
) -> ReferenceSupportResult:
    """Calculate the prespecified arm-specific mean-kNN support check.

    Inputs must already have been transformed using the outer-training-fold
    preprocessing pipeline. Calibration scores exclude each training row from
    its own treatment arm.
    """

    train = _finite_float_matrix("training_covariates", training_covariates)
    heldout = _finite_float_matrix("heldout_covariates", heldout_covariates)
    if heldout.shape[1] != train.shape[1]:
        raise ValueError("training and held-out covariates must have equal columns")
    if not 0.0 < pass_quantile < 1.0:
        raise ValueError("pass_quantile must lie strictly between zero and one")

    treatment = np.asarray(training_treatment)
    if treatment.ndim != 1 or treatment.shape[0] != train.shape[0]:
        raise ValueError("training_treatment must have one entry per training row")
    if not np.isin(treatment, (0, 1)).all():
        raise ValueError("training_treatment must contain only zero and one")
    treatment = treatment.astype(np.int8, copy=False)

    neighbours = prescribed_neighbour_count(train.shape[0])
    arm_0 = train[treatment == 0]
    arm_1 = train[treatment == 1]
    if arm_0.shape[0] <= neighbours or arm_1.shape[0] <= neighbours:
        raise ValueError(
            "each treatment arm must contain more than k rows for leave-one-out calibration"
        )

    model_0 = NearestNeighbors(metric="euclidean").fit(arm_0)
    model_1 = NearestNeighbors(metric="euclidean").fit(arm_1)

    train_dist_0 = model_0.kneighbors(
        train,
        n_neighbors=neighbours + 1,
        return_distance=True,
    )[0]
    train_dist_1 = model_1.kneighbors(
        train,
        n_neighbors=neighbours + 1,
        return_distance=True,
    )[0]

    train_mean_0 = train_dist_0[:, :neighbours].mean(axis=1)
    train_mean_1 = train_dist_1[:, :neighbours].mean(axis=1)
    own_arm_0 = treatment == 0
    own_arm_1 = ~own_arm_0
    train_mean_0[own_arm_0] = train_dist_0[own_arm_0, 1 : neighbours + 1].mean(axis=1)
    train_mean_1[own_arm_1] = train_dist_1[own_arm_1, 1 : neighbours + 1].mean(axis=1)
    training_scores = np.maximum(train_mean_0, train_mean_1)
    threshold = float(np.quantile(training_scores, pass_quantile, method="linear"))

    heldout_dist_0 = model_0.kneighbors(
        heldout,
        n_neighbors=neighbours,
        return_distance=True,
    )[0]
    heldout_dist_1 = model_1.kneighbors(
        heldout,
        n_neighbors=neighbours,
        return_distance=True,
    )[0]
    heldout_mean_0 = heldout_dist_0.mean(axis=1)
    heldout_mean_1 = heldout_dist_1.mean(axis=1)
    score = np.maximum(heldout_mean_0, heldout_mean_1)

    return ReferenceSupportResult(
        passes=score <= threshold,
        score=score,
        arm_0_mean_distance=heldout_mean_0,
        arm_1_mean_distance=heldout_mean_1,
        threshold=threshold,
        training_scores=training_scores,
        neighbours=neighbours,
    )


def model_multiplicity_check(
    effect_estimates: ArrayLike,
    *,
    materiality_margin: float,
    primary_index: int = 0,
    minimum_supporting_estimators: int = 2,
) -> ModelMultiplicityResult:
    """Require material corroboration and prohibit material opposition."""

    estimates = _finite_float_matrix("effect_estimates", effect_estimates)
    n_estimators = estimates.shape[1]
    if materiality_margin < 0.0 or not math.isfinite(materiality_margin):
        raise ValueError("materiality_margin must be finite and non-negative")
    if not 0 <= primary_index < n_estimators:
        raise ValueError("primary_index is outside the estimator columns")
    if not 1 <= minimum_supporting_estimators <= n_estimators:
        raise ValueError("minimum_supporting_estimators is invalid")

    directions = np.zeros(estimates.shape, dtype=np.int8)
    directions[estimates > materiality_margin] = 1
    directions[estimates < -materiality_margin] = -1

    primary_action = (estimates[:, primary_index] > 0.0).astype(np.int8)
    primary_direction = np.where(primary_action == 1, 1, -1).astype(np.int8)
    supporting = (directions == primary_direction[:, None]).sum(axis=1)
    opposing = (directions == -primary_direction[:, None]).sum(axis=1)
    passes = (supporting >= minimum_supporting_estimators) & (opposing == 0)

    return ModelMultiplicityResult(
        passes=passes,
        directions=directions,
        primary_action=primary_action,
        supporting_estimators=supporting,
        opposing_estimators=opposing,
    )


def decision_certainty_check(
    interval_lower: ArrayLike,
    interval_upper: ArrayLike,
    *,
    materiality_margin: float,
) -> DecisionCertaintyResult:
    """Pass intervals entirely above +delta or entirely below -delta."""

    lower = _finite_float_vector("interval_lower", interval_lower)
    upper = _finite_float_vector("interval_upper", interval_upper)
    if lower.shape != upper.shape:
        raise ValueError("interval bounds must have equal shapes")
    if np.any(lower > upper):
        raise ValueError("interval_lower cannot exceed interval_upper")
    if materiality_margin < 0.0 or not math.isfinite(materiality_margin):
        raise ValueError("materiality_margin must be finite and non-negative")

    passes = (lower > materiality_margin) | (upper < -materiality_margin)
    return DecisionCertaintyResult(passes=passes, interval_width=upper - lower)


def _boolean_matrix(name: str, values: ArrayLike) -> NDArray[np.bool_]:
    array = np.asarray(values)
    if array.dtype != np.bool_:
        raise TypeError(f"{name} must be Boolean")
    if array.ndim != 2 or array.shape[0] < 1 or array.shape[1] < 1:
        raise ValueError(f"{name} must be a non-empty two-dimensional array")
    return array.copy()


def _finite_float_matrix(name: str, values: ArrayLike) -> NDArray[np.float64]:
    array = np.asarray(values, dtype=float)
    if array.ndim != 2 or array.shape[0] < 1 or array.shape[1] < 1:
        raise ValueError(f"{name} must be a non-empty two-dimensional array")
    if not np.isfinite(array).all():
        raise ValueError(f"{name} must contain only finite values")
    return array


def _finite_float_vector(name: str, values: ArrayLike) -> NDArray[np.float64]:
    array = np.asarray(values, dtype=float)
    if array.ndim != 1 or array.shape[0] < 1:
        raise ValueError(f"{name} must be a non-empty one-dimensional array")
    if not np.isfinite(array).all():
        raise ValueError(f"{name} must contain only finite values")
    return array
