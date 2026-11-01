from __future__ import annotations

import numpy as np
import pytest

from evidence_defeat.bootstrap import treatment_stratified_bootstrap


def test_stratified_bootstrap_is_reproducible_and_preserves_arm_sizes() -> None:
    treatment = np.array([0] * 30 + [1] * 20, dtype=np.int8)
    row_ids = np.array([f"row-{index}" for index in range(50)])

    first = treatment_stratified_bootstrap(
        treatment,
        row_ids,
        seed=1234,
        repetition_id=2,
    )
    second = treatment_stratified_bootstrap(
        treatment,
        row_ids,
        seed=1234,
        repetition_id=2,
    )

    np.testing.assert_array_equal(first.source_indices, second.source_indices)
    np.testing.assert_array_equal(first.row_ids, second.row_ids)
    assert first.treatment_counts == (30, 20)
    sampled_treatment = treatment[first.source_indices]
    assert np.bincount(sampled_treatment, minlength=2).tolist() == [30, 20]
    assert np.unique(first.row_ids).shape[0] == 50


def test_stratified_bootstrap_changes_with_seed() -> None:
    treatment = np.tile([0, 1], 30)
    row_ids = np.arange(treatment.shape[0])

    first = treatment_stratified_bootstrap(
        treatment,
        row_ids,
        seed=1,
        repetition_id=0,
    )
    second = treatment_stratified_bootstrap(
        treatment,
        row_ids,
        seed=2,
        repetition_id=0,
    )

    assert not np.array_equal(first.source_indices, second.source_indices)


def test_stratified_bootstrap_requires_both_treatment_arms() -> None:
    with pytest.raises(ValueError, match="both treatment arms"):
        treatment_stratified_bootstrap(
            np.zeros(20, dtype=np.int8),
            np.arange(20),
            seed=1,
            repetition_id=0,
        )
