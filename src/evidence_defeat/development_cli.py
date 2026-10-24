"""Command-line orchestration for transparent Stage C development runs."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

from evidence_defeat.config import load_development_config, load_project_config
from evidence_defeat.development import (
    development_configuration_hashes,
    execute_development_run,
    load_reports_from_directory,
    plan_development_runs,
    select_development_run,
    summarise_development_reports,
)
from evidence_defeat.diagnostics import repository_state, write_json_atomic


def build_parser() -> argparse.ArgumentParser:
    """Build the Stage C command-line parser."""

    parser = argparse.ArgumentParser(
        prog="evidence-defeat-dev",
        description=(
            "Run explicitly unblinded Stage C development simulations. "
            "Outputs are exploratory and cannot validate the final framework."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    plan = subparsers.add_parser("plan", help="validate and list Stage C runs")
    _common_candidate_tier_arguments(plan)

    batch = subparsers.add_parser(
        "batch",
        help="run or safely resume one complete candidate tier",
    )
    _common_candidate_tier_arguments(batch)
    batch.add_argument(
        "--output",
        default=None,
        help="new or resumable directory; defaults under results/development/stage-c",
    )

    single = subparsers.add_parser(
        "run",
        help="run one authorised Stage C unit",
    )
    single.add_argument("--root", default=".", help="repository root")
    single.add_argument("--candidate", required=True)
    single.add_argument("--run-id", required=True)
    single.add_argument("--output", required=True, help="new report JSON path")

    summary = subparsers.add_parser(
        "summarize",
        help="recreate a non-confirmatory summary from a batch directory",
    )
    summary.add_argument("--root", default=".", help="repository root")
    summary.add_argument("--candidate", required=True)
    summary.add_argument("--tier", required=True)
    summary.add_argument("--input", required=True, help="batch output directory")

    worker = subparsers.add_parser(
        "_run-one",
        help="internal isolated Stage C worker",
    )
    worker.add_argument("--root", required=True)
    worker.add_argument("--candidate", required=True)
    worker.add_argument("--run-id", required=True)
    worker.add_argument("--output", required=True)
    worker.add_argument("--expected-commit", required=True)
    return parser


def _common_candidate_tier_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--root", default=".", help="repository root")
    parser.add_argument("--candidate", required=True)
    parser.add_argument(
        "--tier",
        default="screening",
        choices=(
            "screening",
            "fairness_stress",
            "finalist_robustness",
            "revision_screening",
            "revision_fairness_stress",
            "revision_finalist_robustness",
        ),
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Run one Stage C command and return a shell-compatible status."""

    arguments = build_parser().parse_args(argv)
    try:
        if arguments.command == "plan":
            return _plan(
                Path(arguments.root),
                arguments.candidate,
                arguments.tier,
            )
        if arguments.command == "batch":
            return _batch(
                Path(arguments.root),
                arguments.candidate,
                arguments.tier,
                None if arguments.output is None else Path(arguments.output),
            )
        if arguments.command == "run":
            return _run_requested_unit(
                Path(arguments.root),
                arguments.candidate,
                arguments.run_id,
                Path(arguments.output),
            )
        if arguments.command == "summarize":
            return _summarize(
                Path(arguments.root),
                arguments.candidate,
                arguments.tier,
                Path(arguments.input),
            )
        if arguments.command == "_run-one":
            return _run_one(
                Path(arguments.root),
                arguments.candidate,
                arguments.run_id,
                Path(arguments.output),
                arguments.expected_commit,
            )
    except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    raise RuntimeError("unreachable command")  # pragma: no cover


def _plan(root: Path, candidate_id: str, tier: str) -> int:
    project = load_project_config(root)
    development = load_development_config(root, project=project)
    state = repository_state(root)
    specs = plan_development_runs(
        project,
        development,
        candidate_id,
        tier=tier,
    )
    payload = {
        "stage": "stage_c_development",
        "scientific_status": "exploratory_unblinded_development_only",
        "scientific_results_will_be_exposed": True,
        "eligible_for_confirmatory_evidence": False,
        "stage_c_scientific_unblinding_authorised": project.development_validation[
            "current_evidence_state"
        ]["stage_c_scientific_unblinding_authorised"],
        "candidate_id": candidate_id,
        "tier": tier,
        "repository_clean": state.clean,
        "code_commit": state.commit,
        "git_branch": state.branch,
        "configuration_sha256": development_configuration_hashes(
            project,
            development,
            candidate_id,
        ),
        "run_count": len(specs),
        "runs": [
            {
                "run_id": spec.run_id,
                "scenario_id": spec.scenario.scenario_id,
                "defect": spec.scenario.defect,
                "sample_size": spec.scenario.sample_size,
                "replicate_id": spec.scenario.replicate_id,
            }
            for spec in specs
        ],
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if state.clean else 1


def _batch(
    root: Path,
    candidate_id: str,
    tier: str,
    requested_output: Path | None,
) -> int:
    root = root.resolve()
    project = load_project_config(root)
    development = load_development_config(root, project=project)
    state = repository_state(root)
    if not state.clean:
        raise RuntimeError("commit or remove repository changes before Stage C")
    specs = plan_development_runs(
        project,
        development,
        candidate_id,
        tier=tier,
    )
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    output = (
        requested_output
        if requested_output is not None
        else root
        / development.bank["reporting"]["output_root"]
        / candidate_id
        / f"{state.commit[:12]}-{timestamp}-{tier}"
    ).resolve()
    configured_root = (root / development.bank["reporting"]["output_root"]).resolve()
    if output.is_relative_to(root) and not output.is_relative_to(configured_root):
        raise RuntimeError(
            f"an output inside the repository must remain under {configured_root}"
        )
    reports_dir = output / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    plan_identity = {
        "candidate_id": candidate_id,
        "tier": tier,
        "code_commit": state.commit,
        "configuration_sha256": development_configuration_hashes(
            project,
            development,
            candidate_id,
        ),
        "run_ids": [spec.run_id for spec in specs],
    }
    plan_path = output / "batch_plan.json"
    if plan_path.exists():
        existing_plan = json.loads(plan_path.read_text(encoding="utf-8"))
        if existing_plan != plan_identity:
            raise RuntimeError("existing output belongs to a different Stage C plan")
    else:
        write_json_atomic(plan_path, plan_identity)

    started = datetime.now(UTC)
    completed_reports: list[str] = []
    print(f"Stage C output: {output}", flush=True)
    print(
        "WARNING: this command exposes exploratory scientific results. "
        "They are not independent validation.",
        flush=True,
    )
    for position, spec in enumerate(specs, start=1):
        report_path = reports_dir / f"{_safe_filename(spec.run_id)}.json"
        if report_path.exists():
            existing = json.loads(report_path.read_text(encoding="utf-8"))
            if (
                existing.get("fingerprint", {}).get("run_id") != spec.run_id
                or existing.get("fingerprint", {}).get("code_commit") != state.commit
                or not existing.get("passed", False)
            ):
                raise RuntimeError(f"cannot resume from invalid report: {report_path}")
            print(f"[{position}/{len(specs)}] SKIP completed {spec.run_id}")
            completed_reports.append(report_path.name)
            continue
        print(f"[{position}/{len(specs)}] {spec.run_id}", flush=True)
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "evidence_defeat.development_cli",
                "_run-one",
                "--root",
                str(root),
                "--candidate",
                candidate_id,
                "--run-id",
                spec.run_id,
                "--output",
                str(report_path),
                "--expected-commit",
                state.commit,
            ],
            cwd=root,
            check=False,
        )
        if completed.returncode != 0:
            _write_batch_manifest(
                output,
                plan_identity,
                started,
                completed_reports,
                status="failed",
            )
            raise RuntimeError(f"Stage C stopped after failure in {spec.run_id}")
        completed_reports.append(report_path.name)
        _write_batch_manifest(
            output,
            plan_identity,
            started,
            completed_reports,
            status="running",
        )

    reports = load_reports_from_directory(output)
    summary = summarise_development_reports(
        reports,
        candidate_id=candidate_id,
        tier=tier,
    )
    write_json_atomic(output / "summary.json", summary)
    _write_batch_manifest(
        output,
        plan_identity,
        started,
        completed_reports,
        status="complete",
    )
    print(f"Stage C batch complete. Summary: {output / 'summary.json'}")
    print(
        "Governance follow-up: after inspecting the results, set "
        "scientific_performance_unblinded_in_this_repository to true and append "
        "the C000 post-run record before proposing another candidate."
    )
    return 0


def _run_requested_unit(
    root: Path,
    candidate_id: str,
    run_id: str,
    output: Path,
) -> int:
    root = root.resolve()
    output = output.resolve()
    _validate_output_location(root, output)
    state = repository_state(root)
    if not state.clean:
        raise RuntimeError("commit or remove repository changes before Stage C")
    return _run_one(root, candidate_id, run_id, output, state.commit)


def _run_one(
    root: Path,
    candidate_id: str,
    run_id: str,
    output: Path,
    expected_commit: str,
) -> int:
    root = root.resolve()
    output = output.resolve()
    _validate_output_location(root, output)
    project = load_project_config(root)
    development = load_development_config(root, project=project)
    state = repository_state(root)
    if state.commit != expected_commit:
        raise RuntimeError("code commit changed after the Stage C batch began")
    if not state.clean:
        raise RuntimeError("repository became dirty during the Stage C run")
    if output.exists():
        raise RuntimeError(f"Stage C report already exists: {output}")
    spec = select_development_run(
        project,
        development,
        candidate_id,
        run_id,
    )
    report = execute_development_run(
        project,
        development,
        spec,
        code_commit=state.commit,
        git_branch=state.branch,
        repository_clean_at_start=state.clean,
    )
    write_json_atomic(output, report.to_dict())
    print("PASS" if report.passed else "FAIL", flush=True)
    return 0 if report.passed else 2


def _summarize(
    root: Path,
    candidate_id: str,
    tier: str,
    input_directory: Path,
) -> int:
    project = load_project_config(root)
    development = load_development_config(root, project=project)
    plan_development_runs(project, development, candidate_id, tier=tier)
    reports = load_reports_from_directory(input_directory)
    summary = summarise_development_reports(
        reports,
        candidate_id=candidate_id,
        tier=tier,
    )
    path = input_directory / "summary.json"
    write_json_atomic(path, summary)
    print(f"Stage C summary written: {path}")
    return 0


def _write_batch_manifest(
    output: Path,
    plan_identity: dict,
    started: datetime,
    completed_reports: list[str],
    *,
    status: str,
) -> None:
    payload = {
        "schema_version": "0.1",
        "stage": "stage_c_development_batch",
        "scientific_status": "exploratory_unblinded_development_only",
        "eligible_for_confirmatory_evidence": False,
        "status": status,
        "started_at_utc": started.isoformat().replace("+00:00", "Z"),
        "updated_at_utc": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        **plan_identity,
        "expected_run_count": len(plan_identity["run_ids"]),
        "completed_run_count": len(completed_reports),
        "reports": completed_reports,
        "governance_followup_required": (
            "After first scientific inspection, set "
            "current_evidence_state."
            "scientific_performance_unblinded_in_this_repository=true and append "
            "the candidate post-run record."
        ),
    }
    write_json_atomic(output / "manifest.json", payload)


def _safe_filename(run_id: str) -> str:
    return re_sub_non_filename(run_id)


def re_sub_non_filename(value: str) -> str:
    """Map a run identifier to a portable filename without losing readability."""

    return "".join(
        character if character.isalnum() or character in "-_" else "_"
        for character in value
    )


def _validate_output_location(root: Path, output: Path) -> None:
    """Keep in-repository reports inside the ignored Stage C result tree."""

    configured_root = (root / "results" / "development" / "stage-c").resolve()
    if output.is_relative_to(root) and not output.is_relative_to(configured_root):
        raise RuntimeError(
            f"an output inside the repository must remain under {configured_root}"
        )


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
