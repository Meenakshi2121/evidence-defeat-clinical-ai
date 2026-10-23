from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from evidence_defeat.config import (
    DevelopmentConfig,
    ProjectConfig,
    candidate_analysis_config,
    load_development_config,
    load_project_config,
)
from evidence_defeat.diagnostics import canonical_sha256
from evidence_defeat.validation import (
    PilotScenarioSpec,
    ValidationConfig,
    execute_blinded_pilot_scenario,
    load_validation_config,
    plan_blinded_pilot,
    summarise_blinded_pilot_reports,
    validate_validation_config,
)
from evidence_defeat.validation_cli import _validate_output_location, build_parser

PROJECT_ROOT = Path(__file__).resolve().parents[1]
pytestmark = [
    pytest.mark.filterwarnings(
        "ignore:Could not generate out-of-bag predictions.*:UserWarning"
    ),
]


def test_committed_validation_plan_is_frozen_and_complete() -> None:
    project = load_project_config(PROJECT_ROOT)
    development = load_development_config(PROJECT_ROOT, project=project)
    validation = load_validation_config(
        PROJECT_ROOT,
        project=project,
        development=development,
    )

    specs = plan_blinded_pilot(validation)

    assert len(specs) == 10
    assert sum(len(item.replicate_ids) for item in specs) == 250
    assert all(item.replicate_ids == tuple(range(100000, 100025)) for item in specs)
    assert {(item.defect, item.sample_size) for item in specs} == {
        (defect, sample_size)
        for defect in (
            "record_adequacy",
            "reference_support",
            "model_multiplicity",
            "decision_uncertainty",
            "combined",
        )
        for sample_size in (500, 2000)
    }


def test_changed_frozen_analysis_hash_is_rejected() -> None:
    project = load_project_config(PROJECT_ROOT)
    development = load_development_config(PROJECT_ROOT, project=project)
    original = load_validation_config(
        PROJECT_ROOT,
        project=project,
        development=development,
    )
    changed = deepcopy(original.document)
    changed["freeze"]["configuration_sha256"]["analysis"] = "0" * 64

    with pytest.raises(ValueError, match="frozen configuration hash changed"):
        validate_validation_config(
            project,
            development,
            ValidationConfig(changed),
        )


@pytest.fixture(scope="module")
def reduced_pilot_inputs() -> tuple[
    ProjectConfig,
    DevelopmentConfig,
    ValidationConfig,
    PilotScenarioSpec,
]:
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
    document["stage_e_blinded_variance_pilot"]["replicate_ids"] = [100000, 100001]
    document["stage_e_blinded_variance_pilot"]["replicates_per_scenario"] = 2
    first = deepcopy(
        document["stage_f_confirmatory_validation"]["primary_scenarios"][0]
    )
    first["sample_size"] = 180
    document["stage_f_confirmatory_validation"]["primary_scenarios"] = [first]
    config = ValidationConfig(document)
    spec = PilotScenarioSpec(
        scenario_id=first["id"],
        defect=first["defect"],
        sample_size=180,
        replicate_ids=(100000, 100001),
    )
    return project, development, config, spec


def test_pilot_report_discloses_variance_but_not_effect_direction(
    reduced_pilot_inputs: tuple[
        ProjectConfig,
        DevelopmentConfig,
        ValidationConfig,
        PilotScenarioSpec,
    ],
) -> None:
    project, development, validation, spec = reduced_pilot_inputs
    report = execute_blinded_pilot_scenario(
        project,
        development,
        validation,
        spec,
        code_commit="a" * 40,
        git_branch="protocol-v0.1",
        repository_clean_at_start=True,
    )
    encoded = str(report)

    assert report["passed"]
    assert report["scientific_effect_results_exposed"] is False
    assert "paired_primary_contrast_standard_deviation" in report["permitted_results"]
    assert "primary_material_unsafe_acceptance_contrast" not in encoded
    assert "replicate_contrasts" not in encoded
    assert "method_rankings" not in report
    assert report["fingerprint"]["replicate_count"] == 2


def test_variance_only_summary_uses_largest_required_count() -> None:
    project = load_project_config(PROJECT_ROOT)
    development = load_development_config(PROJECT_ROOT, project=project)
    validation = load_validation_config(
        PROJECT_ROOT,
        project=project,
        development=development,
    )
    reports = []
    for position, spec in enumerate(plan_blinded_pilot(validation)):
        reports.append(
            {
                "stage": "stage_e_blinded_variance_pilot",
                "scientific_effect_results_exposed": False,
                "passed": True,
                "fingerprint": {
                    "scenario_id": spec.scenario_id,
                    "code_commit": "b" * 40,
                    "configuration_sha256": {"combined": "c" * 64},
                },
                "permitted_results": {
                    "paired_primary_contrast_standard_deviation": 0.01,
                    "target_mcse_per_scenario": 0.0025,
                    "required_replicates_uncapped": 1000 + position,
                    "required_replicates_after_cap": 1000 + position,
                    "target_reachable_within_cap": True,
                },
            }
        )

    summary = summarise_blinded_pilot_reports(reports, validation)

    assert summary["final_replicates_per_confirmatory_scenario"] == 1009
    assert summary["scientific_effect_results_exposed"] is False
    assert summary["stage_f_execution_authorised"] is False
    assert "mean" not in str(summary).lower()


def test_validation_cli_declares_stage_e_commands() -> None:
    help_text = build_parser().format_help()

    for command in ("pilot-plan", "pilot-batch", "pilot-run", "pilot-summarize"):
        assert command in help_text


def test_stage_e_output_stays_in_ignored_tree(tmp_path: Path) -> None:
    root = tmp_path.resolve()
    allowed = root / "results" / "validation" / "stage-e" / "report.json"
    _validate_output_location(root, allowed.resolve())

    with pytest.raises(RuntimeError, match="must remain under"):
        _validate_output_location(root, (root / "report.json").resolve())
