from __future__ import annotations

import numpy as np
import pytest

from evidence_defeat.checks import (
    decision_certainty_check,
    model_multiplicity_check,
    prescribed_neighbour_count,
    record_adequacy_check,
    reference_support_check,
)


def test_record_adequacy_uses_preimputation_fraction_and_invalid_values() -> None:
    observed = np.array(
        [
            [True, True, True, True, False],
            [True, True, True, False, False],
            [True, True, True, True, True],
        ]
    )
    invalid = np.array([False, False, True])

    result = record_adequacy_check(
        observed,
        invalid,
        minimum_observed_fraction=0.80,
    )

    np.testing.assert_allclose(result.observed_fraction, [0.8, 0.6, 1.0])
    np.testing.assert_array_equal(result.passes, [True, False, False])
    np.testing.assert_array_equal(result.invalid_present, invalid)


def test_record_adequacy_requires_boolean_masks() -> None:
    with pytest.raises(TypeError, match="must be Boolean"):
        record_adequacy_check([[1, 1], [1, 0]])


@pytest.mark.parametrize(
    ("n_train", "expected"),
    [(1, 10), (100, 10), (101, 11), (2_500, 50), (10_000, 50)],
)
def test_neighbour_count_uses_locked_formula(n_train: int, expected: int) -> None:
    assert prescribed_neighbour_count(n_train) == expected


def test_reference_support_flags_a_separated_heldout_point() -> None:
    rng = np.random.default_rng(8128)
    train = rng.normal(0.0, 0.40, size=(200, 3))
    treatment = np.tile([0, 1], 100)
    heldout = np.array([[0.0, 0.0, 0.0], [8.0, 8.0, 8.0]])

    result = reference_support_check(train, treatment, heldout)

    assert result.neighbours == 15
    assert result.training_scores.shape == (200,)
    np.testing.assert_array_equal(result.passes, [True, False])
    assert result.score[0] <= result.threshold < result.score[1]
    np.testing.assert_allclose(
        result.score,
        np.maximum(result.arm_0_mean_distance, result.arm_1_mean_distance),
    )


def test_reference_support_requires_enough_rows_in_each_arm() -> None:
    train = np.arange(40, dtype=float).reshape(20, 2)
    treatment = np.array([0] * 10 + [1] * 10)

    with pytest.raises(ValueError, match="more than k"):
        reference_support_check(train, treatment, [[0.0, 0.0]])


def test_model_multiplicity_requires_two_supporters_and_no_opposition() -> None:
    estimates = np.array(
        [
            [0.06, 0.04, 0.03],
            [0.06, 0.04, -0.05],
            [-0.06, -0.03, 0.00],
            [0.01, 0.04, 0.03],
            [0.06, 0.01, 0.00],
            [0.06, 0.02, -0.02],
        ]
    )

    result = model_multiplicity_check(estimates, materiality_margin=0.02)

    np.testing.assert_array_equal(
        result.passes,
        [True, False, True, True, False, False],
    )
    np.testing.assert_array_equal(result.primary_action, [1, 1, 0, 1, 1, 1])
    np.testing.assert_array_equal(result.supporting_estimators, [3, 2, 2, 2, 1, 1])
    np.testing.assert_array_equal(result.opposing_estimators, [0, 1, 0, 0, 0, 0])
    np.testing.assert_array_equal(result.directions[-1], [1, 0, 0])


def test_decision_certainty_requires_strict_clearance_of_margin() -> None:
    result = decision_certainty_check(
        [0.021, -0.10, 0.020, -0.10, -0.01],
        [0.10, -0.021, 0.10, -0.020, 0.04],
        materiality_margin=0.02,
    )

    np.testing.assert_array_equal(result.passes, [True, True, False, False, False])
    np.testing.assert_allclose(result.interval_width, [0.079, 0.079, 0.08, 0.08, 0.05])


def test_decision_certainty_rejects_reversed_bounds() -> None:
    with pytest.raises(ValueError, match="cannot exceed"):
        decision_certainty_check([0.2], [0.1], materiality_margin=0.02)
