from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from evidence_defeat.config import (
    DevelopmentConfig,
    ProjectConfig,
    load_development_config,
    load_project_config,
)
from evidence_defeat.development import (
    execute_development_run,
    plan_development_runs,
    summarise_development_reports,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
pytestmark = [
    pytest.mark.filterwarnings(
        "ignore:Could not generate out-of-bag predictions.*:UserWarning"
    ),
]


@pytest.fixture(scope="module")
def reduced_development_inputs() -> tuple[ProjectConfig, DevelopmentConfig]:
    """Use small models to test orchestration, never scientific performance."""

    original = load_project_config(PROJECT_ROOT)
    development = load_development_config(PROJECT_ROOT, project=original)
    analysis = deepcopy(original.analysis)
    analysis["cross_fitting"]["outer_folds"] = 3
    analysis["cross_fitting"]["inner_folds"] = 2
    analysis["comparators"]["random_deferral"]["repetitions"] = 5
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
        simulation=deepcopy(original.simulation),
        poc=deepcopy(original.poc),
        development_validation=deepcopy(original.development_validation),
    )
    bank = deepcopy(development.bank)
    bank["tiers"]["screening"]["replicate_ids"] = [200000]
    scenario = bank["tiers"]["screening"]["scenarios"][0]
    scenario["sample_size"] = 180
    bank["tiers"]["screening"]["scenarios"] = [scenario]
    reduced_development = DevelopmentConfig(
        bank=bank,
        candidates=deepcopy(development.candidates),
    )
    return project, reduced_development


def test_end_to_end_development_report_is_explicitly_nonconfirmatory(
    reduced_development_inputs: tuple[ProjectConfig, DevelopmentConfig],
) -> None:
    project, development = reduced_development_inputs
    spec = plan_development_runs(
        project,
        development,
        "C000",
        tier="screening",
    )[0]

    report = execute_development_run(
        project,
        development,
        spec,
        code_commit="c" * 40,
        git_branch="protocol-v0.1",
        repository_clean_at_start=True,
    )
    payload = report.to_dict()

    assert report.passed
    assert all(item.passed for item in report.invariants)
    assert report.scientific_results_exposed
    assert not report.eligible_for_confirmatory_evidence
    assert report.scientific_status == "exploratory_unblinded_development_only"
    assert report.fingerprint.replicate_id == 200000
    assert report.fingerprint.scenario_id.startswith("dev_v0_1__")
    assert set(report.fingerprint.configuration_sha256) == {
        "analysis",
        "simulation",
        "poc",
        "development_validation",
        "development_bank",
        "development_candidates",
        "candidate_effective_analysis",
        "combined",
    }
    assert "complete_gate" in payload["results"]["methods"]
    assert "uncertainty_only" in payload["results"]["methods"]
    assert "raw" in payload["results"]["fairness_audit"]
    assert "evidence_standardised" in payload["results"]["fairness_audit"]


def test_development_summary_is_descriptive_not_a_weighted_decision(
    reduced_development_inputs: tuple[ProjectConfig, DevelopmentConfig],
) -> None:
    project, development = reduced_development_inputs
    spec = plan_development_runs(
        project,
        development,
        "C000",
        tier="screening",
    )[0]
    report = execute_development_run(
        project,
        development,
        spec,
        code_commit="d" * 40,
        git_branch="protocol-v0.1",
        repository_clean_at_start=True,
    )

    summary = summarise_development_reports(
        [report.to_dict()],
        candidate_id="C000",
        tier="screening",
    )

    scenario = summary["scenarios"][spec.scenario.scenario_id]
    assert summary["run_count"] == 1
    assert summary["eligible_for_confirmatory_evidence"] is False
    assert scenario["primary_contrast"]["n"] == 1
    assert "check_recovery" in scenario
    assert "fairness_standardisation" in scenario
    assert "No automatic pass/fail or weighted score" in summary["candidate_decision"]


def test_dirty_repository_is_rejected_before_development_execution(
    reduced_development_inputs: tuple[ProjectConfig, DevelopmentConfig],
) -> None:
    project, development = reduced_development_inputs
    spec = plan_development_runs(
        project,
        development,
        "C000",
        tier="screening",
    )[0]

    with pytest.raises(RuntimeError, match="clean Git repository"):
        execute_development_run(
            project,
            development,
            spec,
            code_commit="e" * 40,
            git_branch="protocol-v0.1",
            repository_clean_at_start=False,
        )
