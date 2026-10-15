from __future__ import annotations

from pathlib import Path

import pytest

from evidence_defeat.development_cli import (
    _validate_output_location,
    build_parser,
    re_sub_non_filename,
)


def test_stage_c_cli_declares_plan_batch_run_and_summary_commands() -> None:
    parser = build_parser()

    for command in ("plan", "batch", "run", "summarize"):
        assert command in parser.format_help()


def test_in_repository_output_must_remain_in_ignored_stage_c_tree(
    tmp_path: Path,
) -> None:
    root = tmp_path.resolve()
    allowed = root / "results" / "development" / "stage-c" / "report.json"
    _validate_output_location(root, allowed.resolve())

    with pytest.raises(RuntimeError, match="must remain under"):
        _validate_output_location(root, (root / "report.json").resolve())


def test_run_identifier_maps_to_a_portable_filename() -> None:
    assert re_sub_non_filename("stage_c__C000/a:b") == "stage_c__C000_a_b"
