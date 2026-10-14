from __future__ import annotations

import numpy as np
import pytest

from evidence_defeat.policy_disagreement import (
    policy_vote_disagreement,
    select_near_optimal_candidates,
)


def test_one_standard_error_rule_uses_best_candidate_standard_error() -> None:
    selection = select_near_optimal_candidates(
        [0.50, 0.47, 0.41, 0.30],
        [0.04, 0.01, 0.20, 0.01],
        minimum_count=2,
    )

    assert selection.best_candidate_index == 0
    assert selection.threshold == pytest.approx(0.46)
    np.testing.assert_array_equal(selection.retained, [True, True, False, False])
    assert selection.fallback_used is False


def test_near_optimal_fallback_includes_next_best_candidates() -> None:
    selection = select_near_optimal_candidates(
        [0.50, 0.40, 0.30, 0.20],
        [0.01, 0.01, 0.01, 0.01],
        minimum_count=3,
    )

    np.testing.assert_array_equal(selection.retained, [True, True, True, False])
    assert selection.fallback_used is True


def test_vote_disagreement_has_expected_binary_range() -> None:
    actions = np.array(
        [
            [0, 0, 1, 1],
            [0, 1, 1, 0],
            [0, 0, 1, 0],
            [0, 1, 1, 1],
        ],
        dtype=np.int8,
    )

    disagreement = policy_vote_disagreement(actions)

    np.testing.assert_allclose(disagreement, [0.0, 0.5, 0.0, 0.5])


def test_vote_disagreement_rejects_nonbinary_actions() -> None:
    with pytest.raises(ValueError, match="zero and one"):
        policy_vote_disagreement([[0, 2], [1, 0]])
