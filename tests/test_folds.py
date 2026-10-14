from __future__ import annotations

import numpy as np
import pytest

from evidence_defeat.folds import iter_outer_folds, make_outer_fold_ids


def test_outer_folds_are_reproducible_stratified_and_complete() -> None:
    treatment = np.tile([0, 1], 50)
    row_ids = np.arange(100)

    first = make_outer_fold_ids(treatment, row_ids, n_splits=5, seed=20261013)
    second = make_outer_fold_ids(treatment, row_ids, n_splits=5, seed=20261013)

    np.testing.assert_array_equal(first, second)
    assert set(first) == {0, 1, 2, 3, 4}
    for fold_id in range(5):
        heldout = first == fold_id
        assert heldout.sum() == 20
        assert treatment[heldout].sum() == 10


def test_fold_membership_is_invariant_to_incidental_row_order() -> None:
    treatment = np.tile([0, 1], 50)
    row_ids = np.arange(100)
    original = make_outer_fold_ids(treatment, row_ids, seed=20261013)

    permutation = np.random.default_rng(77).permutation(100)
    reordered = make_outer_fold_ids(
        treatment[permutation],
        row_ids[permutation],
        seed=20261013,
    )
    reordered_by_id = dict(zip(row_ids[permutation], reordered))

    for row_id, fold_id in zip(row_ids, original):
        assert reordered_by_id[row_id] == fold_id


def test_different_fold_seed_changes_membership() -> None:
    treatment = np.tile([0, 1], 50)
    row_ids = np.arange(100)

    first = make_outer_fold_ids(treatment, row_ids, seed=20261013)
    second = make_outer_fold_ids(treatment, row_ids, seed=1729)

    assert not np.array_equal(first, second)


def test_explicit_outer_splits_have_no_train_test_overlap() -> None:
    fold_ids = np.tile(np.arange(5), 20)
    splits = iter_outer_folds(fold_ids)
    all_heldout = []

    for split in splits:
        assert np.intersect1d(split.training_indices, split.heldout_indices).size == 0
        assert split.training_indices.size + split.heldout_indices.size == 100
        all_heldout.extend(split.heldout_indices.tolist())

    assert sorted(all_heldout) == list(range(100))


def test_outer_folds_reject_duplicate_identifiers() -> None:
    with pytest.raises(ValueError, match="must be unique"):
        make_outer_fold_ids([0, 1, 0, 1], [1, 1, 2, 3], n_splits=2)


def test_outer_folds_require_enough_rows_per_treatment_arm() -> None:
    with pytest.raises(ValueError, match="at least n_splits"):
        make_outer_fold_ids([0, 0, 0, 1, 1], np.arange(5), n_splits=3)
