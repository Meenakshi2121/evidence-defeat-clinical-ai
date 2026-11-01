from __future__ import annotations

from collections.abc import Mapping

import numpy as np
import pytest

from evidence_defeat.fairness import audit_known_truth_groups


def _row_metrics(score: np.ndarray) -> Mapping[str, Mapping[str, np.ndarray]]:
    acceptance = score > 0.0
    unsafe = acceptance & (score < 0.35)
    utility = 0.55 + 0.04 * np.tanh(score)
    return {
        "complete_gate": {
            "coverage": acceptance.astype(float),
            "deferral": (~acceptance).astype(float),
            "material_unsafe_acceptance": unsafe.astype(float),
            "deployed_policy_utility": utility,
            "oracle_regret": 0.65 - utility,
            "regret_relative_to_default": 0.57 - utility,
        }
    }


def test_fairness_audit_reports_raw_and_standardised_gaps_separately() -> None:
    rng = np.random.default_rng(44)
    n = 600
    group = np.repeat([0, 1], n // 2)
    fold_ids = np.tile(np.arange(5), n // 5)
    evidence = rng.normal(size=(n, 4))
    evidence[:, 0] += 1.25 * group
    evidence[:, 1] -= 0.50 * group

    result = audit_known_truth_groups(
        group,
        fold_ids,
        evidence,
        _row_metrics(evidence[:, 0]),
        evidence_score_names=("D", "O", "M", "U"),
        minimum_group_n=100,
        truncation_percentiles=(1.0, 99.0),
        balance_threshold=0.20,
    )

    raw_gap = result.raw["complete_gate"].coverage.gap_group_1_minus_group_0
    standardised = result.evidence_standardised
    assert standardised is not None
    standardised_gap = standardised["complete_gate"].coverage.gap_group_1_minus_group_0
    assert raw_gap > 0.25
    assert abs(standardised_gap) < abs(raw_gap)
    assert result.standardisation.eligible
    assert result.standardisation.group_0_n == 300
    assert result.standardisation.group_1_n == 300
    assert 0.0 < result.standardisation.propensity_min < 1.0
    assert 0.0 < result.standardisation.propensity_max < 1.0
    assert result.standardisation.weight_min > 0.0
    assert result.standardisation.weight_max > 0.0
    assert "weighted_composite" not in result.to_dict()


def test_standardisation_is_withheld_when_a_group_is_too_small() -> None:
    rng = np.random.default_rng(7)
    n = 60
    group = np.zeros(n, dtype=np.int8)
    group[-5:] = 1
    evidence = rng.normal(size=(n, 4))

    result = audit_known_truth_groups(
        group,
        np.tile(np.arange(3), n // 3),
        evidence,
        _row_metrics(evidence[:, 0]),
        evidence_score_names=("D", "O", "M", "U"),
        minimum_group_n=10,
        truncation_percentiles=(1.0, 99.0),
        balance_threshold=0.10,
    )

    assert result.raw["complete_gate"].coverage.group_1 >= 0.0
    assert result.evidence_standardised is None
    assert not result.standardisation.eligible
    assert "minimum group size" in result.standardisation.reason


def test_fairness_audit_rejects_missing_metric_fields() -> None:
    with pytest.raises(ValueError, match="required fields"):
        audit_known_truth_groups(
            [0, 0, 1, 1],
            [0, 1, 0, 1],
            np.ones((4, 1)),
            {"gate": {"coverage": np.ones(4)}},
            evidence_score_names=("D",),
            minimum_group_n=1,
            truncation_percentiles=(1.0, 99.0),
            balance_threshold=0.10,
        )
