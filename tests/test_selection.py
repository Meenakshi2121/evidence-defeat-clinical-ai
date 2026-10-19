from __future__ import annotations

import hashlib

import numpy as np
import pytest

from evidence_defeat.selection import (
    apply_deferral_policy,
    construct_gate,
    deterministic_tie_keys,
    match_coverage_within_folds,
    random_deferral_at_matched_coverage,
    select_exact_count,
    uncertainty_only_at_matched_coverage,
    uncertainty_ranking_score,
)


def test_complete_gate_is_logical_and_and_ablations_are_named() -> None:
    record = np.array([True, True, True, False])
    support = np.array([True, True, False, True])
    multiplicity = np.array([True, False, True, True])
    uncertainty = np.array([True, True, True, True])

    result = construct_gate(record, support, multiplicity, uncertainty)

    assert result.essential_checks == (
        "record_adequacy",
        "reference_support",
        "model_multiplicity",
        "decision_uncertainty",
    )
    np.testing.assert_array_equal(result.complete, [True, False, False, False])
    np.testing.assert_array_equal(result.single_check["record_adequacy"], record)
    np.testing.assert_array_equal(
        result.leave_one_out["without_record_adequacy"],
        [True, False, False, True],
    )
    np.testing.assert_array_equal(
        result.leave_one_out["without_reference_support"],
        [True, False, True, False],
    )
    np.testing.assert_array_equal(
        result.leave_one_out["without_model_multiplicity"],
        [True, True, False, False],
    )
    np.testing.assert_array_equal(
        result.leave_one_out["without_decision_uncertainty"],
        [True, False, False, False],
    )


def test_three_check_gate_retains_uncertainty_as_nonessential_diagnostic() -> None:
    record = np.array([True, True, False, True])
    support = np.array([True, False, True, True])
    multiplicity = np.array([True, True, True, False])
    uncertainty = np.array([False, True, True, True])

    result = construct_gate(
        record,
        support,
        multiplicity,
        uncertainty,
        decision_uncertainty_essential=False,
    )

    assert result.essential_checks == (
        "record_adequacy",
        "reference_support",
        "model_multiplicity",
    )
    np.testing.assert_array_equal(result.complete, [True, False, False, False])
    np.testing.assert_array_equal(
        result.single_check["decision_uncertainty"], uncertainty
    )
    assert "without_decision_uncertainty" not in result.leave_one_out


def test_gate_rejects_non_boolean_uncertainty_essential_flag() -> None:
    checks = np.ones(2, dtype=bool)

    with pytest.raises(TypeError, match="essential must be Boolean"):
        construct_gate(
            checks,
            checks,
            checks,
            checks,
            decision_uncertainty_essential=1,
        )


def test_gate_rejects_non_boolean_checks() -> None:
    with pytest.raises(TypeError, match="must be Boolean"):
        construct_gate([1, 0], np.ones(2, bool), np.ones(2, bool), np.ones(2, bool))


def test_deferral_policy_uses_default_only_for_deferred_rows() -> None:
    policy = apply_deferral_policy(
        np.array([True, False, True, False]),
        [1, 1, 0, 0],
        default_action=1,
    )

    np.testing.assert_array_equal(policy, [1, 1, 0, 1])


def test_tie_key_matches_locked_canonical_json_rule() -> None:
    observed = deterministic_tie_keys("IST", [42], 20261013)[0]
    expected = hashlib.sha256(b'["IST","42",20261013]').hexdigest()

    assert observed == expected


def test_exact_selection_is_invariant_to_input_order() -> None:
    row_ids = np.array([10, 11, 12, 13, 14])
    scores = np.ones(5)
    first = select_exact_count(
        scores,
        2,
        trial_ids="trial-a",
        row_ids=row_ids,
        master_seed=20261013,
    )

    permutation = np.array([3, 0, 4, 1, 2])
    second = select_exact_count(
        scores[permutation],
        2,
        trial_ids="trial-a",
        row_ids=row_ids[permutation],
        master_seed=20261013,
    )

    assert set(row_ids[first]) == set(row_ids[permutation][second])
    keys = deterministic_tie_keys("trial-a", row_ids, 20261013)
    expected_rows = set(row_ids[np.argsort(keys)[:2]])
    assert set(row_ids[first]) == expected_rows


def test_duplicate_identifiers_are_rejected() -> None:
    with pytest.raises(ValueError, match="must be unique"):
        select_exact_count(
            [0.1, 0.2],
            1,
            trial_ids=["trial-a", "trial-a"],
            row_ids=[7, 7],
            master_seed=1,
        )


def test_coverage_is_matched_exactly_inside_each_fold() -> None:
    scores = np.array([0.9, 0.8, 0.7, 0.6, 0.1, 0.2, 0.3, 0.4])
    target = np.array([True, False, False, False, True, True, False, False])
    folds = np.array([0, 0, 0, 0, 1, 1, 1, 1])

    selected = match_coverage_within_folds(
        scores,
        target,
        folds,
        trial_ids="trial-a",
        row_ids=np.arange(8),
        master_seed=20261013,
    )

    assert selected[folds == 0].sum() == 1
    assert selected[folds == 1].sum() == 2
    np.testing.assert_array_equal(
        selected, [True, False, False, False, False, False, True, True]
    )


def test_coverage_matching_rejects_non_integer_fold_identifiers() -> None:
    with pytest.raises(TypeError, match="must contain integers"):
        match_coverage_within_folds(
            [0.1, 0.2],
            np.array([True, False]),
            [0.0, np.nan],
            trial_ids="trial-a",
            row_ids=[0, 1],
            master_seed=20261013,
        )


def test_uncertainty_ranking_uses_interval_derived_standard_error() -> None:
    score = uncertainty_ranking_score(
        [0.08, 0.04],
        [0.04, 0.00],
        [0.12, 0.08],
        materiality_margin=0.02,
    )

    assert score[0] / score[1] == pytest.approx(3.0)


def test_uncertainty_comparator_matches_gate_count_by_fold() -> None:
    effect = np.array([0.10, 0.08, 0.04, -0.03, -0.09, 0.06])
    lower = effect - 0.02
    upper = effect + 0.02
    gate = np.array([False, True, False, True, True, False])
    folds = np.array([0, 0, 0, 1, 1, 1])

    selected = uncertainty_only_at_matched_coverage(
        effect,
        lower,
        upper,
        gate,
        folds,
        trial_ids="trial-a",
        row_ids=np.arange(6),
        master_seed=20261013,
        materiality_margin=0.02,
    )

    np.testing.assert_array_equal(selected, [True, False, False, False, True, True])
    for fold in (0, 1):
        assert selected[folds == fold].sum() == gate[folds == fold].sum()


def test_uncertainty_score_rejects_zero_width_intervals() -> None:
    with pytest.raises(ValueError, match="strictly positive width"):
        uncertainty_ranking_score(
            [0.05],
            [0.05],
            [0.05],
            materiality_margin=0.02,
        )


def test_random_deferral_matches_gate_count_in_every_fold_and_repetition() -> None:
    gate = np.array([True, False, False, False, True, True, False, False])
    folds = np.repeat([0, 1], 4)

    result = random_deferral_at_matched_coverage(
        gate,
        folds,
        trial_ids="trial-a",
        row_ids=np.arange(8),
        master_seed=20261013,
        run_id="random-smoke",
        repetitions=12,
    )

    assert result.acceptance.shape == (12, 8)
    assert result.repetition_seeds.shape == (12,)
    assert np.unique(result.repetition_seeds).shape[0] == 12
    for selected in result.acceptance:
        for fold in (0, 1):
            in_fold = folds == fold
            assert selected[in_fold].sum() == gate[in_fold].sum()


def test_random_deferral_is_reproducible_and_row_order_invariant() -> None:
    row_ids = np.arange(12)
    gate = np.array([True, False, False, False, True, False] * 2)
    folds = np.repeat([0, 1], 6)
    first = random_deferral_at_matched_coverage(
        gate,
        folds,
        trial_ids="trial-a",
        row_ids=row_ids,
        master_seed=20261013,
        run_id="order-check",
        repetitions=5,
    )
    permutation = np.array([8, 0, 11, 3, 6, 1, 9, 2, 7, 4, 10, 5])
    second = random_deferral_at_matched_coverage(
        gate[permutation],
        folds[permutation],
        trial_ids="trial-a",
        row_ids=row_ids[permutation],
        master_seed=20261013,
        run_id="order-check",
        repetitions=5,
    )

    np.testing.assert_array_equal(first.repetition_seeds, second.repetition_seeds)
    for repetition_id in range(5):
        assert set(row_ids[first.acceptance[repetition_id]]) == set(
            row_ids[permutation][second.acceptance[repetition_id]]
        )
