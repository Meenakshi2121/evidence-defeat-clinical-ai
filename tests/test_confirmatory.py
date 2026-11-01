from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from evidence_defeat.config import (
    ProjectConfig,
    candidate_analysis_config,
    load_development_config,
    load_project_config,
)
from evidence_defeat.confirmatory import (
    _holm_adjust,
    execute_confirmatory_run,
    plan_confirmatory_runs,
    select_confirmatory_run,
    summarise_confirmatory_reports,
)
from evidence_defeat.confirmatory_cli import _validate_output_location, build_parser
from evidence_defeat.diagnostics import canonical_sha256
from evidence_defeat.validation import ValidationConfig, load_validation_config

PROJECT_ROOT = Path(__file__).resolve().parents[1]
pytestmark = [
    pytest.mark.filterwarnings(
        "ignore:Could not generate out-of-bag predictions.*:UserWarning"
    ),
]


def test_locked_confirmatory_plan_has_exact_frozen_run_set() -> None:
    project = load_project_config(PROJECT_ROOT)
    development = load_development_config(PROJECT_ROOT, project=project)
    validation = load_validation_config(
        PROJECT_ROOT,
        project=project,
        development=development,
    )

    specs = plan_confirmatory_runs(validation)

    assert len(specs) == 10_000
    assert len({item.run_id for item in specs}) == 10_000
    assert {item.replicate_id for item in specs} == set(range(300000, 301000))
    assert len({item.scenario_id for item in specs}) == 10
    assert all(item.run_id.startswith("stage_f__C002__") for item in specs)


def test_confirmatory_selection_rejects_unplanned_replicate() -> None:
    project = load_project_config(PROJECT_ROOT)
    development = load_development_config(PROJECT_ROOT, project=project)
    validation = load_validation_config(
        PROJECT_ROOT,
        project=project,
        development=development,
    )

    with pytest.raises(ValueError, match="outside the locked"):
        select_confirmatory_run(
            validation,
            "confirmatory_v1__record_adequacy_n500",
            301000,
        )


@pytest.fixture(scope="module")
def reduced_confirmatory_inputs() -> tuple[ProjectConfig, object, ValidationConfig]:
    original_project = load_project_config(PROJECT_ROOT)
    development = load_development_config(PROJECT_ROOT, project=original_project)
    original_validation = load_validation_config(
        PROJECT_ROOT,
        project=original_project,
        development=development,
    )
    analysis = deepcopy(original_project.analysis)
    analysis["cross_fitting"]["outer_folds"] = 3
    analysis["cross_fitting"]["inner_folds"] = 2
    analysis["comparators"]["random_deferral"]["repetitions"] = 2
    analysis["fairness_audit"]["minimum_group_n"] = 10
    nuisance = analysis["nuisance_outcome_model"]["parameters"]
    nuisance["max_iter"] = 30
    nuisance["min_samples_leaf"] = 5
    primary = analysis["learners"]["primary"]["parameters"]
    primary["n_estimators"] = 20
    primary["cv"] = 2
    primary["max_depth"] = 5
    primary["min_samples_split"] = 10
    primary["min_samples_leaf"] = 5
    primary["n_jobs"] = 1
    doubly_robust = analysis["learners"]["doubly_robust"]
    doubly_robust["parameters"]["cv"] = 2
    final = doubly_robust["final_model"]["parameters"]
    final["n_estimators"] = 20
    final["min_samples_leaf"] = 5
    final["n_jobs"] = 1
    project = ProjectConfig(
        analysis=analysis,
        simulation=deepcopy(original_project.simulation),
        poc=deepcopy(original_project.poc),
        development_validation=deepcopy(original_project.development_validation),
    )
    document = deepcopy(original_validation.document)
    effective = candidate_analysis_config(project, development, "C002")
    document["freeze"]["configuration_sha256"]["analysis"] = canonical_sha256(
        project.analysis
    )
    document["freeze"]["configuration_sha256"]["candidate_effective_analysis"] = (
        canonical_sha256(effective)
    )
    first = deepcopy(
        document["stage_f_confirmatory_validation"]["primary_scenarios"][0]
    )
    first["sample_size"] = 180
    stage_f = document["stage_f_confirmatory_validation"]
    stage_f["primary_scenarios"] = [first]
    stage_f["minimum_replicates_per_scenario"] = 2
    stage_f["maximum_replicates_per_scenario"] = 2
    stage_f["final_replicate_count"] = 2
    return project, development, ValidationConfig(document)


def test_reduced_confirmatory_execution_and_complete_only_summary(
    reduced_confirmatory_inputs: tuple[ProjectConfig, object, ValidationConfig],
) -> None:
    project, development, validation = reduced_confirmatory_inputs
    specs = plan_confirmatory_runs(validation)
    reports = [
        execute_confirmatory_run(
            project,
            development,
            validation,
            spec,
            code_commit="d" * 40,
            git_branch="protocol-v0.1",
            repository_clean_at_start=True,
        )
        for spec in specs
    ]

    assert all(item["passed"] for item in reports)
    assert all(item["eligible_for_confirmatory_evidence"] for item in reports)
    assert all(
        item["results"]["methods"]["complete_gate"]["coverage"]
        == item["results"]["methods"]["uncertainty_only"]["coverage"]
        for item in reports
    )
    with pytest.raises(ValueError, match="every prespecified"):
        summarise_confirmatory_reports(reports[:1], validation)

    summary = summarise_confirmatory_reports(reports, validation)

    assert summary["run_count"] == 2
    assert summary["scenario_count"] == 1
    assert summary["eligible_for_confirmatory_evidence"] is True
    assert isinstance(
        summary["confirmatory_decision"]["primary_claim_supported"],
        bool,
    )
    assert summary["fairness_audit"]["weighted_composite_used"] is False
    assert summary["claim_boundary"]["clinical_effectiveness_claimed"] is False


def test_holm_adjustment_is_monotone_in_ordered_p_values() -> None:
    adjusted = _holm_adjust({"a": 0.01, "b": 0.03, "c": 0.20})

    assert adjusted == pytest.approx({"a": 0.03, "b": 0.06, "c": 0.20})


def test_confirmatory_cli_declares_controlled_unblinding_commands() -> None:
    help_text = build_parser().format_help()

    for command in ("plan", "init", "run-scenario", "status", "summarize"):
        assert command in help_text


def test_stage_f_output_stays_in_ignored_tree(tmp_path: Path) -> None:
    root = tmp_path.resolve()
    allowed = root / "results" / "validation" / "stage-f" / "report.json"
    _validate_output_location(root, allowed.resolve())

    with pytest.raises(RuntimeError, match="must remain under"):
        _validate_output_location(root, (root / "report.json").resolve())
