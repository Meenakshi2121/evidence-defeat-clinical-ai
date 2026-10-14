"""Command-line entry points for disclosure-safe diagnostic runs."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

from evidence_defeat.config import load_project_config
from evidence_defeat.diagnostics import (
    configuration_hashes,
    execute_diagnostic_run,
    plan_smoke_runs,
    repository_state,
    select_smoke_run,
    write_json_atomic,
)


def build_parser() -> argparse.ArgumentParser:
    """Build the project command-line parser."""

    parser = argparse.ArgumentParser(
        prog="evidence-defeat-poc",
        description="Run pre-lock diagnostics without exposing scientific results.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    plan = subparsers.add_parser("plan", help="validate and list Stage A runs")
    plan.add_argument("--root", default=".", help="repository root")

    smoke = subparsers.add_parser(
        "smoke",
        help="run the complete Stage A diagnostic grid",
    )
    smoke.add_argument("--root", default=".", help="repository root")
    smoke.add_argument(
        "--output",
        default=None,
        help="new output directory; defaults under results/poc/stage-a",
    )

    single = subparsers.add_parser(
        "_run-one",
        help="internal isolated-run worker",
    )
    single.add_argument("--root", required=True)
    single.add_argument("--output", required=True)
    single.add_argument("--scenario", required=True)
    single.add_argument("--replicate", required=True, type=int)
    single.add_argument("--expected-commit", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run one command and return a shell-compatible exit status."""

    arguments = build_parser().parse_args(argv)
    try:
        if arguments.command == "plan":
            return _plan(Path(arguments.root))
        if arguments.command == "smoke":
            return _smoke(
                Path(arguments.root),
                None if arguments.output is None else Path(arguments.output),
            )
        if arguments.command == "_run-one":
            return _run_one(
                Path(arguments.root),
                Path(arguments.output),
                arguments.scenario,
                arguments.replicate,
                arguments.expected_commit,
            )
    except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    raise RuntimeError("unreachable command")  # pragma: no cover


def _plan(root: Path) -> int:
    project = load_project_config(root)
    state = repository_state(root)
    specs = plan_smoke_runs(project)
    payload = {
        "stage": "software_smoke",
        "scientific_status": "diagnostic_only_prelock",
        "eligible_for_paper_effect_estimates": False,
        "repository_clean": state.clean,
        "code_commit": state.commit,
        "git_branch": state.branch,
        "configuration_sha256": configuration_hashes(project),
        "run_count": len(specs),
        "runs": [
            {
                "scenario": spec.scenario_name,
                "scenario_id": spec.scenario.scenario_id,
                "sample_size": spec.scenario.sample_size,
                "replicate_id": spec.scenario.replicate_id,
                "run_id": spec.run_id,
            }
            for spec in specs
        ],
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if state.clean else 1


def _smoke(root: Path, requested_output: Path | None) -> int:
    root = root.resolve()
    project = load_project_config(root)
    state = repository_state(root)
    if not state.clean:
        raise RuntimeError("commit or remove repository changes before diagnostics")
    specs = plan_smoke_runs(project)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    output = (
        requested_output
        if requested_output is not None
        else root / "results" / "poc" / "stage-a" / f"{state.commit[:12]}-{timestamp}"
    ).resolve()
    configured_output_root = (root / project.poc["reporting"]["output_root"]).resolve()
    if output.is_relative_to(root) and not output.is_relative_to(
        configured_output_root
    ):
        raise RuntimeError(
            "an output inside the repository must remain under "
            f"{configured_output_root}"
        )
    if output.exists() and any(output.iterdir()):
        raise RuntimeError(f"output directory is not empty: {output}")
    output.mkdir(parents=True, exist_ok=True)
    print(f"Diagnostic output: {output}", flush=True)

    started = datetime.now(UTC)
    report_paths = []
    for position, spec in enumerate(specs, start=1):
        filename = f"{spec.scenario_name}__replicate_{spec.scenario.replicate_id}.json"
        report_path = output / filename
        print(
            f"[{position}/{len(specs)}] {spec.scenario_name} "
            f"replicate {spec.scenario.replicate_id}",
            flush=True,
        )
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "evidence_defeat.cli",
                "_run-one",
                "--root",
                str(root),
                "--output",
                str(report_path),
                "--scenario",
                spec.scenario_name,
                "--replicate",
                str(spec.scenario.replicate_id),
                "--expected-commit",
                state.commit,
            ],
            cwd=root,
            check=False,
        )
        if completed.returncode != 0:
            raise RuntimeError(
                f"diagnostic failed for {spec.scenario_name} replicate "
                f"{spec.scenario.replicate_id}; all later runs were stopped"
            )
        report_paths.append(filename)

    manifest = {
        "schema_version": "0.1",
        "stage": "software_smoke",
        "scientific_status": "diagnostic_only_prelock",
        "eligible_for_paper_effect_estimates": False,
        "started_at_utc": started.isoformat().replace("+00:00", "Z"),
        "completed_at_utc": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "code_commit": state.commit,
        "git_branch": state.branch,
        "configuration_sha256": configuration_hashes(project),
        "expected_run_count": len(specs),
        "completed_run_count": len(report_paths),
        "all_invariants_passed": True,
        "reports": report_paths,
    }
    write_json_atomic(output / "manifest.json", manifest)
    print(f"Stage A diagnostics passed. Manifest: {output / 'manifest.json'}")
    return 0


def _run_one(
    root: Path,
    output: Path,
    scenario_name: str,
    replicate_id: int,
    expected_commit: str,
) -> int:
    root = root.resolve()
    project = load_project_config(root)
    state = repository_state(root)
    if state.commit != expected_commit:
        raise RuntimeError("code commit changed after the Stage A run began")
    if not state.clean:
        raise RuntimeError("repository became dirty during the Stage A run")
    spec = select_smoke_run(project, scenario_name, replicate_id)
    try:
        report = execute_diagnostic_run(
            project,
            spec,
            code_commit=state.commit,
            git_branch=state.branch,
            repository_clean_at_start=state.clean,
        )
    except Exception as error:
        failure = {
            "schema_version": "0.1",
            "stage": "software_smoke",
            "scientific_status": "diagnostic_only_prelock",
            "eligible_for_paper_effect_estimates": False,
            "completed_at_utc": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "status": "software_failure",
            "scenario": scenario_name,
            "replicate_id": replicate_id,
            "run_id": spec.run_id,
            "code_commit": state.commit,
            "git_branch": state.branch,
            "error_type": type(error).__name__,
            "error_message": str(error)[:500],
        }
        write_json_atomic(output, failure)
        raise
    write_json_atomic(output, report.to_dict())
    print("PASS" if report.passed else "FAIL", flush=True)
    return 0 if report.passed else 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
