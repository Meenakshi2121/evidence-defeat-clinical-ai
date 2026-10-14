"""Deterministic, named random streams for reproducible simulation."""

from __future__ import annotations

import hashlib
from collections.abc import Sequence

import numpy as np
from numpy.random import Generator

DEFAULT_STREAM_NAMES = (
    "group",
    "covariates",
    "defect_flags",
    "treatment",
    "outcome",
)


def derive_replicate_seed(master_seed: int, scenario_id: str, replicate_id: int) -> int:
    """Derive one uint32 seed from the prespecified SHA-256 rule."""

    if master_seed < 0 or replicate_id < 0:
        raise ValueError("master_seed and replicate_id must be non-negative")
    if not scenario_id:
        raise ValueError("scenario_id must not be empty")
    payload = f"{master_seed}|{scenario_id}|{replicate_id}".encode()
    first_eight = hashlib.sha256(payload).digest()[:8]
    return int.from_bytes(first_eight, byteorder="big", signed=False) % (2**32)


def named_generators(
    seed: int,
    names: Sequence[str] = DEFAULT_STREAM_NAMES,
) -> dict[str, Generator]:
    """Spawn independent generators in a fixed, explicit name order."""

    if len(set(names)) != len(names):
        raise ValueError("Random stream names must be unique")
    children = np.random.SeedSequence(seed).spawn(len(names))
    return {name: np.random.default_rng(child) for name, child in zip(names, children)}
