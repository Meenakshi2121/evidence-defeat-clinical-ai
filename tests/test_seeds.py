from __future__ import annotations

import hashlib

import numpy as np

from evidence_defeat.seeds import derive_replicate_seed, named_generators


def test_seed_matches_prespecified_sha256_rule() -> None:
    master_seed = 20261013
    scenario_id = "primary_record_500"
    replicate_id = 7
    digest = hashlib.sha256(
        f"{master_seed}|{scenario_id}|{replicate_id}".encode()
    ).digest()
    expected = int.from_bytes(digest[:8], "big") % (2**32)

    assert derive_replicate_seed(master_seed, scenario_id, replicate_id) == expected


def test_seed_is_deterministic_and_identifiers_matter() -> None:
    first = derive_replicate_seed(20261013, "scenario-a", 1)

    assert first == derive_replicate_seed(20261013, "scenario-a", 1)
    assert first != derive_replicate_seed(20261013, "scenario-a", 2)
    assert first != derive_replicate_seed(20261013, "scenario-b", 1)


def test_named_streams_are_reproducible_and_distinct() -> None:
    first = named_generators(12345)
    second = named_generators(12345)

    for name in first:
        np.testing.assert_array_equal(
            first[name].normal(size=20), second[name].normal(size=20)
        )

    streams = named_generators(12345)
    assert not np.array_equal(
        streams["group"].integers(0, 2**31, size=20),
        streams["covariates"].integers(0, 2**31, size=20),
    )


def test_invalid_seed_inputs_are_rejected() -> None:
    for args in [(-1, "scenario", 0), (1, "scenario", -1), (1, "", 0)]:
        try:
            derive_replicate_seed(*args)
        except ValueError:
            pass
        else:  # pragma: no cover - explicit failure branch
            raise AssertionError(f"Expected ValueError for {args}")
