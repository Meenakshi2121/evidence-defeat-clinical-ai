"""Deterministic treatment-stratified participant bootstrap utilities."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray


@dataclass(frozen=True)
class StratifiedBootstrapSample:
    """Source positions and unique identifiers for one bootstrap resample."""

    source_indices: NDArray[np.int64]
    row_ids: NDArray[np.str_]
    treatment_counts: tuple[int, int]
    seed: int
    repetition_id: int


def treatment_stratified_bootstrap(
    treatment: ArrayLike,
    row_ids: ArrayLike,
    *,
    seed: int,
    repetition_id: int,
) -> StratifiedBootstrapSample:
    """Resample within treatment arms while preserving each arm's size."""

    assigned = np.asarray(treatment)
    if assigned.ndim != 1 or assigned.shape[0] < 2:
        raise ValueError("treatment must be a one-dimensional array")
    if not np.isin(assigned, (0, 1)).all():
        raise ValueError("treatment must contain only zero and one")
    assigned = assigned.astype(np.int8, copy=False)
    identifiers = np.asarray(row_ids).astype(str)
    if identifiers.ndim != 1 or identifiers.shape[0] != assigned.shape[0]:
        raise ValueError("row_ids must have one entry per row")
    if np.unique(identifiers).shape[0] != identifiers.shape[0]:
        raise ValueError("row_ids must be unique before resampling")
    if not isinstance(seed, int) or isinstance(seed, bool) or not 0 <= seed < 2**32:
        raise ValueError("seed must be a uint32 integer")
    if (
        not isinstance(repetition_id, int)
        or isinstance(repetition_id, bool)
        or repetition_id < 0
    ):
        raise ValueError("repetition_id must be a non-negative integer")

    rng = np.random.default_rng(seed)
    sampled_by_arm = []
    counts = []
    for arm in (0, 1):
        positions = np.flatnonzero(assigned == arm)
        if positions.shape[0] < 1:
            raise ValueError("both treatment arms must be present")
        counts.append(int(positions.shape[0]))
        sampled_by_arm.append(
            rng.choice(positions, size=positions.shape[0], replace=True)
        )
    sampled = np.concatenate(sampled_by_arm).astype(np.int64, copy=False)
    sampled = sampled[rng.permutation(sampled.shape[0])]
    bootstrap_ids = np.asarray(
        [
            (
                f"bootstrap_{repetition_id:03d}_draw_{draw:06d}_"
                f"source_{identifiers[source]}"
            )
            for draw, source in enumerate(sampled)
        ],
        dtype=str,
    )
    if np.unique(bootstrap_ids).shape[0] != bootstrap_ids.shape[0]:  # pragma: no cover
        raise RuntimeError("bootstrap identifiers are not unique")
    return StratifiedBootstrapSample(
        source_indices=sampled,
        row_ids=bootstrap_ids,
        treatment_counts=(counts[0], counts[1]),
        seed=seed,
        repetition_id=repetition_id,
    )
