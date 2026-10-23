"""Command-line orchestration for the blinded Stage E variance pilot."""

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
from evidence_defeat.diagnostics import repository_state, write_json_atomic
from evidence_defeat.validation import (
    execute_blinded_pilot_scenario,
    load_validation_config,
    plan_blinded_pilot,
    select_blinded_pilot_scenario,
    summarise_blinded_pilot_reports,
    validation_configuration_hashes,
)

_FROZEN_FILES = (
    "config/validation.yaml",
    "protocol/protocol_v1.0.md",
    "protocol/stage_d_freeze_record_v1.0.md",
    "protocol/amendments_v1.0.md",
)


def build_parser() -> argparse.ArgumentParser:
    """Build the Stage E command-line parser."""

    parser = argparse.ArgumentParser(
        prog="evidence-defeat-validate",
        description=(
            "Run the protocol-v1.0 blinded variance pilot without disclosing "
            "mean effects, method rankings, or group differences."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    plan = subparsers.add_parser("pilot-plan", help="validate and list Stage E groups")
    plan.add_argument("--root", default=".", help="repository root")

    batch = subparsers.add_parser(
        "pilot-batch",
        help="run or resume all ten blinded Stage E scenario groups",
    )
    batch.add_argument("--root", default=".", help="repository root")
    batch.add_argument(
        "--output",
        default=None,
        help="new or resumable directory under results/validation/stage-e",
    )

    run = subparsers.add_parser(
        "pilot-run",
        help="run one complete 25-replicate blinded scenario group",
    )
    run.add_argument("--root", default=".", help="repository root")
    run.add_argument("--scenario-id", required=True)
    run.add_argument("--output", required=True, help="new report JSON path")

    summary = subparsers.add_parser(
        "pilot-summarize",
        help="derive the variance-only replicate-count decision",
    )
    summary.add_argument("--root", default=".", help="repository root")
    summary.add_argument("--input", required=True, help="Stage E batch directory")

    worker = subparsers.add_parser(
        "_pilot-worker",
        help="internal isolated Stage E worker",
    )
    worker.add_argument("--root", required=True)
    worker.add_argument("--scenario-id", required=True)
    worker.add_argument("--output", required=True)
    worker.add_argument("--expected-commit", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run one Stage E command and return a shell-compatible status."""

    arguments = build_parser().parse_args(argv)
    try:
        if arguments.command == "pilot-plan":
            return _plan(Path(arguments.root))
        if arguments.command == "pilot-batch":
            return _batch(
                Path(arguments.root),
                None if arguments.output is None else Path(arguments.output),
            )
        if arguments.command == "pilot-run":
            return _run_requested_scenario(
                Path(arguments.root),
                arguments.scenario_id,
                Path(arguments.output),
            )
        if arguments.command == "pilot-summarize":
            return _summarize(Path(arguments.root), Path(arguments.input))
        if arguments.command == "_pilot-worker":
            return _run_worker(
                Path(arguments.root),
                arguments.scenario_id,
                Path(arguments.output),
                arguments.expected_commit,
            )
    except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    raise RuntimeError("unreachable command")  # pragma: no cover


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
    freeze = _freeze_state(root, validation.document["freeze"]["protocol_tag"])
    specs = plan_blinded_pilot(validation)
    payload = {
        "stage": "stage_e_blinded_variance_pilot",
        "scientific_status": "variance_only_blinded",
        "scientific_effect_results_will_be_exposed": False,
        "eligible_for_confirmatory_evidence": False,
        "candidate_id": "C002",
        "repository_clean": state.clean,
        "code_commit": state.commit,
        "git_branch": state.branch,
        "freeze": freeze,
        "configuration_sha256": validation_configuration_hashes(
            project,
            development,
            validation,
        ),
        "scenario_group_count": len(specs),
        "total_replicate_count": sum(len(item.replicate_ids) for item in specs),
        "scenario_groups": [
            {
                "scenario_id": item.scenario_id,
                "defect": item.defect,
                "sample_size": item.sample_size,
                "replicate_count": len(item.replicate_ids),
                "replicate_id_first": item.replicate_ids[0],
                "replicate_id_last": item.replicate_ids[-1],
            }
            for item in specs
        ],
        "permitted_disclosures": validation.document["stage_e_blinded_variance_pilot"][
            "permitted_outputs"
        ],
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    ready = state.clean and freeze["tag_is_ancestor"] and freeze["frozen_files_match"]
    return 0 if ready else 1


def _batch(root: Path, requested_output: Path | None) -> int:
    root = root.resolve()
    project, development, validation = _load(root)
    state = repository_state(root)
    if not state.clean:
        raise RuntimeError("commit or remove repository changes before Stage E")
    freeze = _freeze_state(root, validation.document["freeze"]["protocol_tag"])
    if not freeze["tag_is_ancestor"] or not freeze["frozen_files_match"]:
        raise RuntimeError("protocol-v1.0 is absent, unrelated, or modified")
    specs = plan_blinded_pilot(validation)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    output = (
        requested_output
        if requested_output is not None
        else root
        / "results"
        / "validation"
        / "stage-e"
        / f"{state.commit[:12]}-{timestamp}"
    ).resolve()
    _validate_output_location(root, output)
    reports_dir = output / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    plan_identity = {
        "candidate_id": "C002",
        "code_commit": state.commit,
        "protocol_tag_commit": freeze["tag_commit"],
        "configuration_sha256": validation_configuration_hashes(
            project,
            development,
            validation,
        ),
        "scenario_ids": [item.scenario_id for item in specs],
    }
    plan_path = output / "pilot_plan.json"
    if plan_path.exists():
        if json.loads(plan_path.read_text(encoding="utf-8")) != plan_identity:
            raise RuntimeError("existing output belongs to a different Stage E plan")
    else:
        write_json_atomic(plan_path, plan_identity)

    started = datetime.now(UTC)
    completed_reports: list[str] = []
    print(f"Stage E output: {output}", flush=True)
    print(
        "BLINDED: only contrast standard deviations, runtime, and memory will "
        "be saved. Mean effects and rankings remain undisclosed.",
        flush=True,
    )
    for position, spec in enumerate(specs, start=1):
        report_path = reports_dir / f"{spec.scenario_id}.json"
        if report_path.exists():
            existing = json.loads(report_path.read_text(encoding="utf-8"))
            if (
                existing.get("fingerprint", {}).get("scenario_id") != spec.scenario_id
                or existing.get("fingerprint", {}).get("code_commit") != state.commit
                or not existing.get("passed", False)
            ):
                raise RuntimeError(f"cannot resume from invalid report: {report_path}")
            print(f"[{position}/{len(specs)}] SKIP completed {spec.scenario_id}")
            completed_reports.append(report_path.name)
            continue
        print(f"[{position}/{len(specs)}] {spec.scenario_id}", flush=True)
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "evidence_defeat.validation_cli",
                "_pilot-worker",
                "--root",
                str(root),
                "--scenario-id",
                spec.scenario_id,
                "--output",
                str(report_path),
                "--expected-commit",
                state.commit,
            ],
            cwd=root,
            check=False,
        )
        if completed.returncode != 0:
            _write_manifest(
                output,
                plan_identity,
                started,
                completed_reports,
                status="failed",
            )
            raise RuntimeError(f"Stage E stopped after failure in {spec.scenario_id}")
        completed_reports.append(report_path.name)
        _write_manifest(
            output,
            plan_identity,
            started,
            completed_reports,
            status="running",
        )

    reports = _load_reports(output)
    summary = summarise_blinded_pilot_reports(reports, validation)
    write_json_atomic(output / "summary.json", summary)
    _write_manifest(
        output,
        plan_identity,
        started,
        completed_reports,
        status="complete",
    )
    print(f"Stage E complete. Variance-only summary: {output / 'summary.json'}")
    return 0


def _run_requested_scenario(root: Path, scenario_id: str, output: Path) -> int:
    root = root.resolve()
    output = output.resolve()
    _validate_output_location(root, output)
    state = repository_state(root)
    if not state.clean:
        raise RuntimeError("commit or remove repository changes before Stage E")
    return _run_worker(root, scenario_id, output, state.commit)


def _run_worker(
    root: Path,
    scenario_id: str,
    output: Path,
    expected_commit: str,
) -> int:
    root = root.resolve()
    output = output.resolve()
    _validate_output_location(root, output)
    project, development, validation = _load(root)
    state = repository_state(root)
    if state.commit != expected_commit:
        raise RuntimeError("code commit changed after the Stage E run began")
    if not state.clean:
        raise RuntimeError("repository became dirty during the Stage E run")
    freeze = _freeze_state(root, validation.document["freeze"]["protocol_tag"])
    if not freeze["tag_is_ancestor"] or not freeze["frozen_files_match"]:
        raise RuntimeError("protocol-v1.0 integrity check failed")
    if output.exists():
        raise RuntimeError(f"Stage E report already exists: {output}")
    spec = select_blinded_pilot_scenario(validation, scenario_id)
    report = execute_blinded_pilot_scenario(
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


def _summarize(root: Path, input_directory: Path) -> int:
    root = root.resolve()
    _, _, validation = _load(root)
    reports = _load_reports(input_directory)
    summary = summarise_blinded_pilot_reports(reports, validation)
    path = input_directory / "summary.json"
    write_json_atomic(path, summary)
    print(f"Stage E variance-only summary written: {path}")
    return 0


def _load_reports(output: Path) -> list[dict[str, Any]]:
    paths = sorted((output / "reports").glob("*.json"))
    if not paths:
        raise ValueError(f"no Stage E reports found under {output / 'reports'}")
    return [json.loads(path.read_text(encoding="utf-8")) for path in paths]


def _freeze_state(root: Path, tag: str) -> dict[str, Any]:
    tag_result = subprocess.run(
        ["git", "rev-list", "-n", "1", tag],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    tag_commit = tag_result.stdout.strip() if tag_result.returncode == 0 else ""
    ancestor = False
    frozen_files_match = False
    if tag_commit:
        ancestor = (
            subprocess.run(
                ["git", "merge-base", "--is-ancestor", tag, "HEAD"],
                cwd=root,
                check=False,
            ).returncode
            == 0
        )
        frozen_files_match = (
            subprocess.run(
                ["git", "diff", "--quiet", tag, "--", *_FROZEN_FILES],
                cwd=root,
                check=False,
            ).returncode
            == 0
        )
    return {
        "protocol_tag": tag,
        "tag_commit": tag_commit,
        "tag_is_ancestor": ancestor,
        "frozen_files_match": frozen_files_match,
    }


def _write_manifest(
    output: Path,
    plan_identity: dict[str, Any],
    started: datetime,
    completed_reports: list[str],
    *,
    status: str,
) -> None:
    payload = {
        "schema_version": "1.0",
        "stage": "stage_e_blinded_variance_pilot_batch",
        "scientific_status": "variance_only_blinded",
        "scientific_effect_results_exposed": False,
        "eligible_for_confirmatory_evidence": False,
        "status": status,
        "started_at_utc": started.isoformat().replace("+00:00", "Z"),
        "updated_at_utc": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        **plan_identity,
        "expected_scenario_count": len(plan_identity["scenario_ids"]),
        "completed_scenario_count": len(completed_reports),
        "reports": completed_reports,
    }
    write_json_atomic(output / "manifest.json", payload)


def _validate_output_location(root: Path, output: Path) -> None:
    configured_root = (root / "results" / "validation" / "stage-e").resolve()
    if output.is_relative_to(root) and not output.is_relative_to(configured_root):
        raise RuntimeError(
            f"an output inside the repository must remain under {configured_root}"
        )


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
