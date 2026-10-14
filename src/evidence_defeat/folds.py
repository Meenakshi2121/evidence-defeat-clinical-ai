"""Deterministic, treatment-stratified outer-fold assignment."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray
from sklearn.model_selection import StratifiedKFold


@dataclass(frozen=True)
class OuterFold:
    """Training and held-out row positions for one outer fold."""

    fold_id: int
    training_indices: NDArray[np.int64]
    heldout_indices: NDArray[np.int64]


def make_outer_fold_ids(
    treatment: ArrayLike,
    row_ids: ArrayLike,
    *,
    n_splits: int = 5,
    seed: int = 20261013,
) -> NDArray[np.int16]:
    """Assign every row to one deterministic treatment-stratified fold.

    Rows are sorted by the string representation of their identifier before
    splitting, then assignments are mapped back to the supplied row order.
    Outcomes and group labels are intentionally absent from this interface.
    """

    assigned_treatment = _binary_treatment(treatment)
    identifiers = _unique_identifiers(row_ids, assigned_treatment.shape[0])
    if not isinstance(n_splits, int) or isinstance(n_splits, bool) or n_splits < 2:
        raise ValueError("n_splits must be an integer of at least two")
    if not isinstance(seed, int) or isinstance(seed, bool) or seed < 0:
        raise ValueError("seed must be a non-negative integer")

    counts = np.bincount(assigned_treatment, minlength=2)
    if np.any(counts < n_splits):
        raise ValueError("each treatment arm must contain at least n_splits rows")

    stable_order = np.argsort(identifiers, kind="stable")
    ordered_treatment = assigned_treatment[stable_order]
    splitter = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=seed)
    fold_ids = np.full(assigned_treatment.shape[0], -1, dtype=np.int16)
    placeholder = np.zeros((assigned_treatment.shape[0], 1), dtype=np.int8)
    for fold_id, (_, heldout_positions) in enumerate(
        splitter.split(placeholder, ordered_treatment)
    ):
        fold_ids[stable_order[heldout_positions]] = fold_id

    if np.any(fold_ids < 0):  # pragma: no cover - defensive invariant
        raise RuntimeError("internal error: at least one row has no outer fold")
    return fold_ids


def iter_outer_folds(fold_ids: ArrayLike) -> tuple[OuterFold, ...]:
    """Convert a complete fold vector into explicit train/held-out indices."""

    folds = np.asarray(fold_ids)
    if folds.ndim != 1 or folds.shape[0] < 2:
        raise ValueError(
            "fold_ids must be a one-dimensional array with at least two rows"
        )
    if folds.dtype == np.bool_ or not np.issubdtype(folds.dtype, np.integer):
        raise TypeError("fold_ids must contain integers")
    unique = np.unique(folds)
    if unique.shape[0] < 2 or not np.array_equal(unique, np.arange(unique.shape[0])):
        raise ValueError("fold_ids must be contiguous integers beginning at zero")

    positions = np.arange(folds.shape[0], dtype=np.int64)
    result = []
    for fold_id in unique:
        heldout = positions[folds == fold_id]
        training = positions[folds != fold_id]
        if heldout.size == 0 or training.size == 0:  # pragma: no cover
            raise RuntimeError("internal error: an outer split is empty")
        result.append(
            OuterFold(
                fold_id=int(fold_id),
                training_indices=training,
                heldout_indices=heldout,
            )
        )
    return tuple(result)


def _binary_treatment(values: ArrayLike) -> NDArray[np.int64]:
    array = np.asarray(values)
    if array.ndim != 1 or array.shape[0] < 2:
        raise ValueError("treatment must be a one-dimensional array")
    if not np.isin(array, (0, 1)).all():
        raise ValueError("treatment must contain only zero and one")
    return array.astype(np.int64, copy=False)


def _unique_identifiers(values: ArrayLike, expected_size: int) -> NDArray[np.str_]:
    array = np.asarray(values)
    if array.ndim != 1 or array.shape[0] != expected_size:
        raise ValueError("row_ids must have one entry per row")
    identifiers = array.astype(str)
    if np.unique(identifiers).shape[0] != expected_size:
        raise ValueError("row_ids must be unique after string conversion")
    return identifiers
