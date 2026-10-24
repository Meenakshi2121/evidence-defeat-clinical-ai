"""Raw and evidence-standardised group audits for known-truth development runs."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from typing import Any

import numpy as np
from numpy.typing import ArrayLike, NDArray
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler


@dataclass(frozen=True)
class GroupMetricValues:
    """Metric means for groups zero and one, plus group-one minus group-zero."""

    group_0: float
    group_1: float
    gap_group_1_minus_group_0: float


@dataclass(frozen=True)
class MethodGroupAudit:
    """Raw or evidence-standardised metrics for one deployed method."""

    coverage: GroupMetricValues
    deferral: GroupMetricValues
    material_unsafe_acceptance: GroupMetricValues
    deployed_policy_utility: GroupMetricValues
    oracle_regret: GroupMetricValues
    regret_relative_to_default: GroupMetricValues


@dataclass(frozen=True)
class EvidenceStandardisation:
    """Diagnostics for cross-fitted group-propensity standardisation."""

    eligible: bool
    reason: str | None
    group_0_n: int
    group_1_n: int
    propensity_min: float | None
    propensity_max: float | None
    weight_min: float | None
    weight_max: float | None
    max_absolute_standardised_mean_difference: float | None
    balance_threshold: float
    balance_passed: bool | None


@dataclass(frozen=True)
class FairnessAudit:
    """Separate raw and evidence-standardised group results."""

    evidence_score_names: tuple[str, ...]
    raw: Mapping[str, MethodGroupAudit]
    evidence_standardised: Mapping[str, MethodGroupAudit] | None
    standardisation: EvidenceStandardisation

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible representation."""

        return asdict(self)


def audit_known_truth_groups(
    group: ArrayLike,
    fold_ids: ArrayLike,
    evidence_scores: ArrayLike,
    row_metrics: Mapping[str, Mapping[str, ArrayLike]],
    *,
    evidence_score_names: tuple[str, ...],
    minimum_group_n: int,
    truncation_percentiles: tuple[float, float],
    balance_threshold: float,
) -> FairnessAudit:
    """Audit group gaps before and after standardising evidence conditions.

    The standardisation model predicts group membership from outcome-blind,
    cross-fitted evidence scores. Stabilised inverse-probability weights then
    map both groups to the pooled evidence-score distribution. This is an audit
    of access and harm conditional on evidence conditions; it is not a fairness
    guarantee and it is never collapsed into a weighted composite.
    """

    labels = _binary_vector("group", group)
    n = labels.shape[0]
    folds = _fold_vector(fold_ids, n)
    scores = _finite_matrix("evidence_scores", evidence_scores, n)
    if len(evidence_score_names) != scores.shape[1]:
        raise ValueError("evidence_score_names must match evidence-score columns")
    if len(set(evidence_score_names)) != len(evidence_score_names):
        raise ValueError("evidence_score_names must be unique")
    if (
        not isinstance(minimum_group_n, int)
        or isinstance(minimum_group_n, bool)
        or minimum_group_n < 1
    ):
        raise ValueError("minimum_group_n must be a positive integer")
    lower_percentile, upper_percentile = truncation_percentiles
    if not 0.0 <= lower_percentile < upper_percentile <= 100.0:
        raise ValueError("weight truncation percentiles are invalid")
    if not math.isfinite(balance_threshold) or balance_threshold < 0.0:
        raise ValueError("balance_threshold must be finite and non-negative")

    metrics = _validated_row_metrics(row_metrics, n)
    raw = {
        method: _method_audit(labels, values, weights=None)
        for method, values in metrics.items()
    }
    group_0_n = int((labels == 0).sum())
    group_1_n = int((labels == 1).sum())
    if min(group_0_n, group_1_n) < minimum_group_n:
        status = EvidenceStandardisation(
            eligible=False,
            reason=(
                "minimum group size not met: "
                f"group_0={group_0_n}, group_1={group_1_n}, "
                f"required={minimum_group_n}"
            ),
            group_0_n=group_0_n,
            group_1_n=group_1_n,
            propensity_min=None,
            propensity_max=None,
            weight_min=None,
            weight_max=None,
            max_absolute_standardised_mean_difference=None,
            balance_threshold=float(balance_threshold),
            balance_passed=None,
        )
        return FairnessAudit(
            evidence_score_names=evidence_score_names,
            raw=raw,
            evidence_standardised=None,
            standardisation=status,
        )

    propensities = _cross_fitted_group_propensity(labels, folds, scores)
    marginal_1 = float(labels.mean())
    weights = np.where(
        labels == 1,
        marginal_1 / propensities,
        (1.0 - marginal_1) / (1.0 - propensities),
    )
    lower, upper = np.percentile(weights, [lower_percentile, upper_percentile])
    weights = np.clip(weights, lower, upper)
    if not np.isfinite(weights).all() or np.any(weights <= 0.0):
        raise RuntimeError("evidence-standardisation weights are invalid")

    standardised = {
        method: _method_audit(labels, values, weights=weights)
        for method, values in metrics.items()
    }
    balance = _maximum_absolute_smd(scores, labels, weights)
    status = EvidenceStandardisation(
        eligible=True,
        reason=None,
        group_0_n=group_0_n,
        group_1_n=group_1_n,
        propensity_min=float(propensities.min()),
        propensity_max=float(propensities.max()),
        weight_min=float(weights.min()),
        weight_max=float(weights.max()),
        max_absolute_standardised_mean_difference=balance,
        balance_threshold=float(balance_threshold),
        balance_passed=balance <= balance_threshold,
    )
    return FairnessAudit(
        evidence_score_names=evidence_score_names,
        raw=raw,
        evidence_standardised=standardised,
        standardisation=status,
    )


def _cross_fitted_group_propensity(
    group: NDArray[np.int8],
    fold_ids: NDArray[np.int16],
    evidence_scores: NDArray[np.float64],
) -> NDArray[np.float64]:
    propensities = np.full(group.shape[0], np.nan)
    for fold_id in np.unique(fold_ids):
        heldout = fold_ids == fold_id
        training = ~heldout
        if np.unique(group[training]).size != 2:
            raise ValueError("each propensity-training split must contain both groups")
        scaler = StandardScaler().fit(evidence_scores[training])
        x_training = scaler.transform(evidence_scores[training])
        x_heldout = scaler.transform(evidence_scores[heldout])
        model = LogisticRegression(
            C=1.0,
            solver="lbfgs",
            max_iter=2000,
            fit_intercept=True,
            random_state=0,
        ).fit(x_training, group[training])
        propensities[heldout] = model.predict_proba(x_heldout)[:, 1]
    if not np.isfinite(propensities).all():
        raise RuntimeError("cross-fitted group propensities are incomplete")
    return np.clip(propensities, 0.05, 0.95)


def _method_audit(
    group: NDArray[np.int8],
    metrics: Mapping[str, NDArray[np.float64]],
    *,
    weights: NDArray[np.float64] | None,
) -> MethodGroupAudit:
    return MethodGroupAudit(
        coverage=_group_values(metrics["coverage"], group, weights),
        deferral=_group_values(metrics["deferral"], group, weights),
        material_unsafe_acceptance=_group_values(
            metrics["material_unsafe_acceptance"], group, weights
        ),
        deployed_policy_utility=_group_values(
            metrics["deployed_policy_utility"], group, weights
        ),
        oracle_regret=_group_values(metrics["oracle_regret"], group, weights),
        regret_relative_to_default=_group_values(
            metrics["regret_relative_to_default"], group, weights
        ),
    )


def _group_values(
    values: NDArray[np.float64],
    group: NDArray[np.int8],
    weights: NDArray[np.float64] | None,
) -> GroupMetricValues:
    means = []
    for label in (0, 1):
        selected = group == label
        if weights is None:
            mean = float(values[selected].mean())
        else:
            mean = float(np.average(values[selected], weights=weights[selected]))
        means.append(mean)
    return GroupMetricValues(
        group_0=means[0],
        group_1=means[1],
        gap_group_1_minus_group_0=means[1] - means[0],
    )


def _maximum_absolute_smd(
    scores: NDArray[np.float64],
    group: NDArray[np.int8],
    weights: NDArray[np.float64],
) -> float:
    values = []
    for column in range(scores.shape[1]):
        group_values = []
        group_variances = []
        for label in (0, 1):
            selected = group == label
            x = scores[selected, column]
            w = weights[selected]
            mean = float(np.average(x, weights=w))
            variance = float(np.average((x - mean) ** 2, weights=w))
            group_values.append(mean)
            group_variances.append(variance)
        pooled = math.sqrt((group_variances[0] + group_variances[1]) / 2.0)
        difference = abs(group_values[1] - group_values[0])
        values.append(0.0 if pooled == 0.0 else difference / pooled)
    return float(max(values, default=0.0))


def _validated_row_metrics(
    row_metrics: Mapping[str, Mapping[str, ArrayLike]],
    n: int,
) -> dict[str, dict[str, NDArray[np.float64]]]:
    required = {
        "coverage",
        "deferral",
        "material_unsafe_acceptance",
        "deployed_policy_utility",
        "oracle_regret",
        "regret_relative_to_default",
    }
    if not row_metrics:
        raise ValueError("row_metrics must contain at least one method")
    result: dict[str, dict[str, NDArray[np.float64]]] = {}
    for method, values in row_metrics.items():
        if set(values) != required:
            raise ValueError(f"row metrics for {method} do not match required fields")
        result[method] = {
            name: _finite_vector(f"{method}.{name}", raw, n)
            for name, raw in values.items()
        }
    return result


def _binary_vector(name: str, values: ArrayLike) -> NDArray[np.int8]:
    array = np.asarray(values)
    if array.ndim != 1 or array.shape[0] < 2:
        raise ValueError(f"{name} must be a one-dimensional vector")
    if not np.isin(array, (0, 1)).all():
        raise ValueError(f"{name} must contain only zero and one")
    if np.unique(array).size != 2:
        raise ValueError(f"{name} must contain both groups")
    return array.astype(np.int8, copy=False)


def _fold_vector(values: ArrayLike, n: int) -> NDArray[np.int16]:
    array = np.asarray(values)
    if array.ndim != 1 or array.shape[0] != n:
        raise ValueError("fold_ids must have one value per row")
    if np.unique(array).size < 2:
        raise ValueError("at least two folds are required")
    return array.astype(np.int16, copy=False)


def _finite_matrix(
    name: str,
    values: ArrayLike,
    n: int,
) -> NDArray[np.float64]:
    array = np.asarray(values, dtype=float)
    if array.ndim != 2 or array.shape[0] != n or array.shape[1] < 1:
        raise ValueError(f"{name} must be a matrix with one row per participant")
    if not np.isfinite(array).all():
        raise ValueError(f"{name} must be finite")
    return array


def _finite_vector(
    name: str,
    values: ArrayLike,
    n: int,
) -> NDArray[np.float64]:
    array = np.asarray(values, dtype=float)
    if array.ndim != 1 or array.shape[0] != n:
        raise ValueError(f"{name} must have one value per participant")
    if not np.isfinite(array).all():
        raise ValueError(f"{name} must be finite")
    return array
