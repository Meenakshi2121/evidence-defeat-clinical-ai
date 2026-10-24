"""Resumable orchestration for the one-time Stage F validation."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from evidence_defeat.config import load_development_config, load_project_config
from evidence_defeat.confirmatory import (
    execute_confirmatory_run,
    plan_confirmatory_runs,
    select_confirmatory_run,
    summarise_confirmatory_reports,
)
from evidence_defeat.diagnostics import repository_state, write_json_atomic
from evidence_defeat.validation import (
    load_validation_config,
    validation_configuration_hashes,
)

_RUNNER_TAG = "stage-f-runner-v1.0"
_DEFAULT_OUTPUT = "results/validation/stage-f/c002-confirmatory-v1.0"
_AUTHORISED_FILES = (
    "config/analysis.yaml",
    "config/development_candidates.yaml",
    "config/validation.yaml",
    "protocol/protocol_v1.0.md",
    "protocol/stage_d_freeze_record_v1.0.md",
    "protocol/amendments_v1.0.md",
    "protocol/stage_e_variance_pilot_v1.0.md",
    "protocol/stage_e_variance_record_v1.0.md",
)


def build_parser() -> argparse.ArgumentParser:
    """Build the Stage F command-line parser."""

    parser = argparse.ArgumentParser(
        prog="evidence-defeat-confirm",
        description=(
            "Execute the frozen C002 Stage F grid with resumable per-replicate "
            "checkpoints and one-time complete-grid unblinding."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    plan = subparsers.add_parser("plan", help="validate and display the Stage F grid")
    plan.add_argument("--root", default=".", help="repository root")

    initialise = subparsers.add_parser(
        "init",
        help="create the immutable Stage F execution identity",
    )
    _root_and_output_arguments(initialise)

    scenario = subparsers.add_parser(
        "run-scenario",
        help="run or resume one complete 1,000-replicate scenario cell",
    )
    _root_and_output_arguments(scenario)
    scenario.add_argument("--scenario-id", required=True)
    scenario.add_argument(
        "--max-new-runs",
        type=int,
        default=None,
        help="optional result-independent checkpoint limit for this invocation",
    )

    status = subparsers.add_parser(
        "status",
        help="show completion counts without displaying scientific results",
    )
    status.add_argument("--root", default=".", help="repository root")
    status.add_argument("--input", default=_DEFAULT_OUTPUT)

    summary = subparsers.add_parser(
        "summarize",
        help="unblind once after all 10,000 primary reports are complete",
    )
    summary.add_argument("--root", default=".", help="repository root")
    summary.add_argument("--input", default=_DEFAULT_OUTPUT)

    worker = subparsers.add_parser("_run-one", help="internal Stage F worker")
    worker.add_argument("--root", required=True)
    worker.add_argument("--scenario-id", required=True)
    worker.add_argument("--replicate-id", required=True, type=int)
    worker.add_argument("--output", required=True)
    worker.add_argument("--expected-commit", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run a Stage F command and return a shell-compatible status."""

    arguments = build_parser().parse_args(argv)
    try:
        if arguments.command == "plan":
            return _plan(Path(arguments.root))
        if arguments.command == "init":
            return _initialise(Path(arguments.root), Path(arguments.output))
        if arguments.command == "run-scenario":
            return _run_scenario(
                Path(arguments.root),
                Path(arguments.output),
                arguments.scenario_id,
                arguments.max_new_runs,
            )
        if arguments.command == "status":
            return _status(Path(arguments.root), Path(arguments.input))
        if arguments.command == "summarize":
            return _summarize(Path(arguments.root), Path(arguments.input))
        if arguments.command == "_run-one":
            return _run_one(
                Path(arguments.root),
                arguments.scenario_id,
                arguments.replicate_id,
                Path(arguments.output),
                arguments.expected_commit,
            )
    except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    raise RuntimeError("unreachable command")  # pragma: no cover


def _root_and_output_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--root", default=".", help="repository root")
    parser.add_argument("--output", default=_DEFAULT_OUTPUT)


def _load(root: Path) -> tuple[Any, Any, Any]:
    project = load_project_config(root)
    development = load_development_config(root, project=project)
    validation = load_validation_config(
        root,
        project=project,
        development=development,
    )
    return project, development, validation


def _plan(root: Path) -> int:
    root = root.resolve()
    project, development, validation = _load(root)
    state = repository_state(root)
    readiness = _readiness(root, validation, state.commit)
    specs = plan_confirmatory_runs(validation)
    groups = _scenario_groups(specs)
    payload = {
        "stage": "stage_f_confirmatory_validation",
        "scientific_status": "confirmatory_not_started",
        "candidate_id": "C002",
        "repository_clean": state.clean,
        "code_commit": state.commit,
        "git_branch": state.branch,
        "readiness": readiness,
        "configuration_sha256": validation_configuration_hashes(
            project,
            development,
            validation,
        ),
        "scenario_count": len(groups),
        "replicates_per_scenario": 1000,
        "total_run_count": len(specs),
        "replicate_id_first": min(item.replicate_id for item in specs),
        "replicate_id_last": max(item.replicate_id for item in specs),
        "scenarios": [
            {
                "scenario_id": scenario_id,
                "defect": items[0].defect,
                "sample_size": items[0].sample_size,
                "replicate_count": len(items),
            }
            for scenario_id, items in sorted(groups.items())
        ],
        "unblinding_rule": "summary_requires_all_10000_primary_reports",
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if state.clean and readiness["ready"] else 1


def _initialise(root: Path, requested_output: Path) -> int:
    root = root.resolve()
    output = _resolve_output(root, requested_output)
    project, development, validation = _load(root)
    state = repository_state(root)
    _require_ready(root, validation, state)
    specs = plan_confirmatory_runs(validation)
    identity = _plan_identity(
        project,
        development,
        validation,
        state.commit,
        specs,
    )
    _ensure_plan(output, identity)
    print(f"Stage F execution identity ready: {output / 'plan.json'}")
    print("Scientific results remain sealed until all 10,000 runs complete.")
    return 0


def _run_scenario(
    root: Path,
    requested_output: Path,
    scenario_id: str,
    max_new_runs: int | None,
) -> int:
    root = root.resolve()
    output = _resolve_output(root, requested_output)
    if max_new_runs is not None and max_new_runs < 1:
        raise ValueError("max-new-runs must be a positive integer")
    project, development, validation = _load(root)
    state = repository_state(root)
    _require_ready(root, validation, state)
    specs = [
        item
        for item in plan_confirmatory_runs(validation)
        if item.scenario_id == scenario_id
    ]
    if not specs:
        raise ValueError(f"unknown Stage F scenario: {scenario_id}")
    identity = _plan_identity(
        project,
        development,
        validation,
        state.commit,
        plan_confirmatory_runs(validation),
    )
    _require_existing_plan(output, identity)
    reports_dir = output / "reports" / scenario_id
    reports_dir.mkdir(parents=True, exist_ok=True)
    completed = _validated_completed_reports(
        reports_dir,
        specs,
        expected_commit=state.commit,
        expected_configuration_hash=identity["configuration_sha256"]["combined"],
    )
    print(
        f"Stage F {scenario_id}: {len(completed)}/{len(specs)} already complete",
        flush=True,
    )
    new_run_count = 0
    for position, spec in enumerate(specs, start=1):
        if spec.replicate_id in completed:
            continue
        report_path = reports_dir / f"replicate_{spec.replicate_id}.json"
        print(
            f"[{position}/{len(specs)}] replicate {spec.replicate_id}",
            flush=True,
        )
        completed_process = subprocess.run(
            [
                sys.executable,
                "-m",
                "evidence_defeat.confirmatory_cli",
                "_run-one",
                "--root",
                str(root),
                "--scenario-id",
                scenario_id,
                "--replicate-id",
                str(spec.replicate_id),
                "--output",
                str(report_path),
                "--expected-commit",
                state.commit,
            ],
            cwd=root,
            check=False,
        )
        if completed_process.returncode != 0:
            _write_scenario_manifest(
                output,
                scenario_id,
                specs,
                state.commit,
                status="failed",
            )
            raise RuntimeError(
                f"Stage F stopped after replicate {spec.replicate_id} failed"
            )
        new_run_count += 1
        _write_scenario_manifest(
            output,
            scenario_id,
            specs,
            state.commit,
            status="running",
        )
        if max_new_runs is not None and new_run_count >= max_new_runs:
            print(
                f"Checkpoint limit reached after {new_run_count} new runs. "
                "Rerun the same command to resume.",
                flush=True,
            )
            return 0
    _write_scenario_manifest(
        output,
        scenario_id,
        specs,
        state.commit,
        status="complete",
    )
    print(f"Stage F scenario complete: {scenario_id}", flush=True)
    return 0


def _run_one(
    root: Path,
    scenario_id: str,
    replicate_id: int,
    requested_output: Path,
    expected_commit: str,
) -> int:
    root = root.resolve()
    output = requested_output.resolve()
    _validate_output_location(root, output)
    project, development, validation = _load(root)
    state = repository_state(root)
    if state.commit != expected_commit:
        raise RuntimeError("code commit changed after Stage F execution began")
    _require_ready(root, validation, state)
    if output.exists():
        raise RuntimeError(f"Stage F report already exists: {output}")
    spec = select_confirmatory_run(validation, scenario_id, replicate_id)
    report = execute_confirmatory_run(
        project,
        development,
        validation,
        spec,
        code_commit=state.commit,
        git_branch=state.branch,
        repository_clean_at_start=state.clean,
    )
    write_json_atomic(output, report)
    print("PASS" if report["passed"] else "FAIL", flush=True)
    return 0 if report["passed"] else 2


def _status(root: Path, requested_input: Path) -> int:
    root = root.resolve()
    output = _resolve_output(root, requested_input)
    project, development, validation = _load(root)
    specs = plan_confirmatory_runs(validation)
    state = repository_state(root)
    identity = _plan_identity(
        project,
        development,
        validation,
        state.commit,
        specs,
    )
    _require_existing_plan(output, identity)
    groups = _scenario_groups(specs)
    status = {}
    total = 0
    for scenario_id, items in sorted(groups.items()):
        completed = _validated_completed_reports(
            output / "reports" / scenario_id,
            items,
            expected_commit=state.commit,
            expected_configuration_hash=identity["configuration_sha256"]["combined"],
        )
        status[scenario_id] = {
            "completed": len(completed),
            "expected": len(items),
        }
        total += len(completed)
    payload = {
        "stage": "stage_f_confirmatory_validation",
        "scientific_results_displayed": False,
        "completed_run_count": total,
        "expected_run_count": len(specs),
        "ready_to_unblind": total == len(specs),
        "scenarios": status,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


def _summarize(root: Path, requested_input: Path) -> int:
    root = root.resolve()
    output = _resolve_output(root, requested_input)
    project, development, validation = _load(root)
    state = repository_state(root)
    _require_ready(root, validation, state)
    specs = plan_confirmatory_runs(validation)
    identity = _plan_identity(
        project,
        development,
        validation,
        state.commit,
        specs,
    )
    _require_existing_plan(output, identity)
    summary_path = output / "summary.json"
    if summary_path.exists():
        raise RuntimeError("Stage F summary already exists; unblinding is one-time")
    reports = []
    for spec in specs:
        path = (
            output
            / "reports"
            / spec.scenario_id
            / f"replicate_{spec.replicate_id}.json"
        )
        if not path.exists():
            raise RuntimeError(
                "Stage F remains incomplete; status must reach 10000/10000"
            )
        reports.append(json.loads(path.read_text(encoding="utf-8")))
    summary = summarise_confirmatory_reports(reports, validation)
    write_json_atomic(summary_path, summary)
    print("Stage F complete and now unblinded.")
    print(f"Confirmatory summary: {summary_path}")
    return 0


def _plan_identity(
    project: Any,
    development: Any,
    validation: Any,
    code_commit: str,
    specs: tuple[Any, ...],
) -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "stage": "stage_f_confirmatory_validation_plan",
        "candidate_id": "C002",
        "code_commit": code_commit,
        "runner_tag": _RUNNER_TAG,
        "authorisation_tag": validation.document["stage_f_confirmatory_validation"][
            "authorisation_tag"
        ],
        "configuration_sha256": validation_configuration_hashes(
            project,
            development,
            validation,
        ),
        "scenario_ids": sorted({item.scenario_id for item in specs}),
        "replicate_id_first": min(item.replicate_id for item in specs),
        "replicate_id_last": max(item.replicate_id for item in specs),
        "replicates_per_scenario": 1000,
        "expected_run_count": len(specs),
        "unblinding_rule": "all_10000_primary_reports_required",
    }


def _ensure_plan(output: Path, identity: dict[str, Any]) -> None:
    output.mkdir(parents=True, exist_ok=True)
    path = output / "plan.json"
    if path.exists():
        existing = json.loads(path.read_text(encoding="utf-8"))
        if existing != identity:
            raise RuntimeError("existing output belongs to a different Stage F plan")
        return
    if any(output.iterdir()):
        raise RuntimeError("Stage F output is non-empty but has no valid plan")
    write_json_atomic(path, identity)


def _require_existing_plan(output: Path, identity: dict[str, Any]) -> None:
    path = output / "plan.json"
    if not path.exists():
        raise RuntimeError("run 'evidence-defeat-confirm init' first")
    if json.loads(path.read_text(encoding="utf-8")) != identity:
        raise RuntimeError("Stage F output identity differs from the current plan")


def _validated_completed_reports(
    reports_dir: Path,
    specs: list[Any],
    *,
    expected_commit: str,
    expected_configuration_hash: str,
) -> set[int]:
    if not reports_dir.exists():
        return set()
    planned = {item.replicate_id: item for item in specs}
    completed: set[int] = set()
    for path in sorted(reports_dir.glob("replicate_*.json")):
        report = json.loads(path.read_text(encoding="utf-8"))
        fingerprint = report.get("fingerprint", {})
        replicate_id = int(fingerprint.get("replicate_id", -1))
        if replicate_id not in planned:
            raise RuntimeError(f"unexpected Stage F report: {path}")
        spec = planned[replicate_id]
        if (
            report.get("stage") != "stage_f_confirmatory_validation"
            or report.get("passed") is not True
            or fingerprint.get("run_id") != spec.run_id
            or fingerprint.get("code_commit") != expected_commit
            or fingerprint.get("configuration_sha256", {}).get("combined")
            != expected_configuration_hash
        ):
            raise RuntimeError(f"invalid Stage F checkpoint: {path}")
        if replicate_id in completed:
            raise RuntimeError("duplicate Stage F replicate report")
        completed.add(replicate_id)
    return completed


def _write_scenario_manifest(
    output: Path,
    scenario_id: str,
    specs: list[Any],
    code_commit: str,
    *,
    status: str,
) -> None:
    reports_dir = output / "reports" / scenario_id
    completed = len(list(reports_dir.glob("replicate_*.json")))
    payload = {
        "schema_version": "1.0",
        "stage": "stage_f_confirmatory_scenario_execution",
        "scientific_results_displayed": False,
        "scenario_id": scenario_id,
        "code_commit": code_commit,
        "status": status,
        "completed_run_count": completed,
        "expected_run_count": len(specs),
        "updated_at_utc": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
    }
    write_json_atomic(output / "manifests" / f"{scenario_id}.json", payload)


def _scenario_groups(specs: tuple[Any, ...]) -> dict[str, list[Any]]:
    groups: dict[str, list[Any]] = {}
    for spec in specs:
        groups.setdefault(spec.scenario_id, []).append(spec)
    return groups


def _readiness(root: Path, validation: Any, head_commit: str) -> dict[str, Any]:
    authorisation_tag = validation.document["stage_f_confirmatory_validation"][
        "authorisation_tag"
    ]
    authorisation_commit = _tag_commit(root, authorisation_tag)
    runner_commit = _tag_commit(root, _RUNNER_TAG)
    authorisation_is_ancestor = bool(authorisation_commit) and _is_ancestor(
        root,
        authorisation_tag,
        "HEAD",
    )
    authorised_files_match = bool(authorisation_commit) and (
        subprocess.run(
            ["git", "diff", "--quiet", authorisation_tag, "--", *_AUTHORISED_FILES],
            cwd=root,
            check=False,
        ).returncode
        == 0
    )
    runner_is_exact_head = bool(runner_commit) and runner_commit == head_commit
    return {
        "authorisation_tag": authorisation_tag,
        "authorisation_tag_commit": authorisation_commit,
        "authorisation_tag_is_ancestor": authorisation_is_ancestor,
        "authorised_files_match_tag": authorised_files_match,
        "runner_tag": _RUNNER_TAG,
        "runner_tag_commit": runner_commit,
        "runner_tag_is_exact_head": runner_is_exact_head,
        "ready": (
            authorisation_is_ancestor
            and authorised_files_match
            and runner_is_exact_head
        ),
    }


def _require_ready(root: Path, validation: Any, state: Any) -> None:
    if not state.clean:
        raise RuntimeError("commit or remove repository changes before Stage F")
    readiness = _readiness(root, validation, state.commit)
    if not readiness["ready"]:
        raise RuntimeError(
            "Stage F requires the exact public stage-f-runner-v1.0 commit and "
            "unchanged Stage E-authorised files"
        )


def _tag_commit(root: Path, tag: str) -> str:
    result = subprocess.run(
        ["git", "rev-list", "-n", "1", tag],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def _is_ancestor(root: Path, ancestor: str, descendant: str) -> bool:
    return (
        subprocess.run(
            ["git", "merge-base", "--is-ancestor", ancestor, descendant],
            cwd=root,
            check=False,
        ).returncode
        == 0
    )


def _resolve_output(root: Path, requested: Path) -> Path:
    output = requested if requested.is_absolute() else root / requested
    output = output.resolve()
    _validate_output_location(root, output)
    return output


def _validate_output_location(root: Path, output: Path) -> None:
    configured_root = (root / "results" / "validation" / "stage-f").resolve()
    if output.is_relative_to(root) and not output.is_relative_to(configured_root):
        raise RuntimeError(
            f"an output inside the repository must remain under {configured_root}"
        )


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
