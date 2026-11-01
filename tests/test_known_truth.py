from __future__ import annotations

import math

import numpy as np
import pytest

from evidence_defeat.known_truth import evaluate_known_truth_method


def test_material_unsafe_acceptance_uses_population_denominator() -> None:
    mu0 = np.full(4, 0.5)
    mu1 = np.array([0.6, 0.6, 0.4, 0.51])
    acceptance = np.array([True, False, True, True])
    individualised = np.array([0, 0, 1, 0])
    default = np.zeros(4, dtype=np.int8)
    deployed = np.where(acceptance, individualised, default)

    result = evaluate_known_truth_method(
        "test-method",
        acceptance,
        individualised,
        deployed,
        default,
        mu0,
        mu1,
        materiality_margin=0.02,
    )

    assert result.sample_size == 4
    assert result.accepted_count == 3
    assert result.actionable_count == 3
    assert result.accepted_actionable_count == 2
    assert result.unsafe_accepted_count == 2
    assert result.coverage == pytest.approx(0.75)
    assert result.material_unsafe_acceptance == pytest.approx(2 / 4)
    assert result.accepted_actionable_error_rate == pytest.approx(2 / 2)


def test_known_truth_utility_and_regret_signs_are_explicit() -> None:
    mu0 = np.full(4, 0.5)
    mu1 = np.array([0.6, 0.6, 0.4, 0.51])
    acceptance = np.array([True, False, True, True])
    individualised = np.array([0, 0, 1, 0])
    default = np.zeros(4, dtype=np.int8)
    deployed = np.where(acceptance, individualised, default)

    result = evaluate_known_truth_method(
        "test-method",
        acceptance,
        individualised,
        deployed,
        default,
        mu0,
        mu1,
        materiality_margin=0.02,
    )

    assert result.deployed_policy_utility == pytest.approx(0.475)
    assert result.oracle_policy_utility == pytest.approx(0.5525)
    assert result.oracle_regret == pytest.approx(0.0775)
    assert result.default_policy_utility == pytest.approx(0.5)
    assert result.regret_relative_to_default == pytest.approx(0.025)
    assert result.utility_gain_vs_default == pytest.approx(-0.025)


def test_accepted_error_is_unavailable_when_denominator_is_zero() -> None:
    result = evaluate_known_truth_method(
        "default-only",
        np.zeros(3, dtype=bool),
        np.ones(3, dtype=np.int8),
        np.zeros(3, dtype=np.int8),
        np.zeros(3, dtype=np.int8),
        np.zeros(3),
        np.ones(3),
        materiality_margin=0.02,
    )

    assert result.material_unsafe_acceptance == 0.0
    assert math.isnan(result.accepted_actionable_error_rate)


def test_row_specific_materiality_margin_is_respected() -> None:
    result = evaluate_known_truth_method(
        "varying-margin",
        np.ones(2, dtype=bool),
        np.zeros(2, dtype=np.int8),
        np.zeros(2, dtype=np.int8),
        np.zeros(2, dtype=np.int8),
        np.zeros(2),
        np.array([0.05, 0.05]),
        materiality_margin=np.array([0.04, 0.06]),
    )

    assert result.actionable_count == 1
    assert result.unsafe_accepted_count == 1
    assert result.material_unsafe_acceptance == pytest.approx(0.5)
