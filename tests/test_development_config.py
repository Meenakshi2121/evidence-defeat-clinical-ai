from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import pytest

from evidence_defeat.config import (
    ConfigurationError,
    DevelopmentConfig,
    candidate_analysis_config,
    load_development_config,
    load_project_config,
    validate_development_config,
    validate_project_config,
)
from evidence_defeat.development import (
    plan_development_runs,
    select_development_run,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_committed_development_bank_and_candidates_are_valid() -> None:
    project = load_project_config(PROJECT_ROOT)
    development = load_development_config(PROJECT_ROOT, project=project)

    screening = plan_development_runs(
        project,
        development,
        "C000",
        tier="screening",
    )

    assert len(screening) == 60
    assert {item.scenario.replicate_id for item in screening} == set(
        range(200000, 200010)
    )
    assert all(item.scenario.scenario_id.startswith("dev_v0_1__") for item in screening)
    assert all(item.candidate_id == "C000" for item in screening)
    assert len({item.run_id for item in screening}) == len(screening)
    assert plan_development_runs(project, development, "C000") == screening

    revised = plan_development_runs(
        project,
        development,
        "C001",
        tier="screening",
    )
    assert len(revised) == 60
    assert all(item.candidate_id == "C001" for item in revised)


def test_baseline_cannot_enter_later_tiers_before_retention() -> None:
    project = load_project_config(PROJECT_ROOT)
    development = load_development_config(PROJECT_ROOT, project=project)

    with pytest.raises(ValueError, match="not authorised"):
        plan_development_runs(
            project,
            development,
            "C000",
            tier="fairness_stress",
        )


def test_rejected_c001_cannot_reenter_fairness_stress() -> None:
    project = load_project_config(PROJECT_ROOT)
    development = load_development_config(PROJECT_ROOT, project=project)

    with pytest.raises(ValueError, match="not eligible"):
        plan_development_runs(
            project,
            development,
            "C001",
            tier="fairness_stress",
        )


def test_rejected_c001_cannot_reenter_finalist_robustness() -> None:
    project = load_project_config(PROJECT_ROOT)
    development = load_development_config(PROJECT_ROOT, project=project)

    with pytest.raises(ValueError, match="not eligible"):
        plan_development_runs(
            project,
            development,
            "C001",
            tier="finalist_robustness",
        )


def test_screening_run_can_be_selected_without_opening_later_tiers() -> None:
    project = load_project_config(PROJECT_ROOT)
    development = load_development_config(PROJECT_ROOT, project=project)
    planned = plan_development_runs(
        project,
        development,
        "C000",
        tier="screening",
    )[0]

    selected = select_development_run(
        project,
        development,
        "C000",
        planned.run_id,
    )

    assert selected == planned


def test_c002_uses_only_authorised_fresh_revision_tiers() -> None:
    project = load_project_config(PROJECT_ROOT)
    development = load_development_config(PROJECT_ROOT, project=project)

    planned = plan_development_runs(
        project,
        development,
        "C002",
        tier="revision_screening",
    )

    assert len(planned) == 35
    assert {item.scenario.replicate_id for item in planned} == set(
        range(230000, 230005)
    )
    assert all("revision_" in item.scenario.scenario_id for item in planned)
    assert all(item.candidate_id == "C002" for item in planned)

    fairness = plan_development_runs(
        project,
        development,
        "C002",
        tier="revision_fairness_stress",
    )
    assert len(fairness) == 30
    assert {item.scenario.replicate_id for item in fairness} == set(
        range(240000, 240005)
    )
    assert all(
        item.scenario.scenario_id.startswith("dev_v0_1__revision_fair_")
        for item in fairness
    )
    assert all(item.candidate_id == "C002" for item in fairness)
    assert all(item.scenario.sample_size == 2000 for item in fairness)

    robustness = plan_development_runs(
        project,
        development,
        "C002",
        tier="revision_finalist_robustness",
    )
    assert len(robustness) == 25
    assert {item.scenario.replicate_id for item in robustness} == set(
        range(250000, 250005)
    )
    assert all(
        item.scenario.scenario_id.startswith("dev_v0_1__revision_robust_")
        for item in robustness
    )
    assert all(item.candidate_id == "C002" for item in robustness)
    assert all(item.scenario.sample_size == 2000 for item in robustness)
    assert development.candidates["candidates"]["C002"]["status"] == "finalist"

    with pytest.raises(ValueError, match="not authorised"):
        plan_development_runs(project, development, "C002", tier="screening")


def test_prohibited_candidate_override_is_rejected() -> None:
    project = load_project_config(PROJECT_ROOT)
    original = load_development_config(PROJECT_ROOT, project=project)
    candidates = deepcopy(original.candidates)
    candidates["candidates"]["C000"]["analysis_overrides"] = {
        "known_truth_evaluation.primary_metric": "accepted_only"
    }

    with pytest.raises(ConfigurationError, match="prohibited overrides"):
        validate_development_config(
            project,
            DevelopmentConfig(bank=deepcopy(original.bank), candidates=candidates),
        )


def test_candidate_analysis_is_a_deep_copy_of_the_locked_base() -> None:
    project = load_project_config(PROJECT_ROOT)
    development = load_development_config(PROJECT_ROOT, project=project)

    effective = candidate_analysis_config(project, development, "C000")
    effective["gate"]["record_adequacy"]["observed_fraction_minimum"] = 0.1

    assert (
        project.analysis["gate"]["record_adequacy"]["observed_fraction_minimum"] != 0.1
    )


def test_c001_changes_only_uncertainty_essential_status() -> None:
    project = load_project_config(PROJECT_ROOT)
    development = load_development_config(PROJECT_ROOT, project=project)

    baseline = candidate_analysis_config(project, development, "C000")
    revised = candidate_analysis_config(project, development, "C001")

    assert baseline["gate"]["uncertainty"]["essential"] is True
    assert revised["gate"]["uncertainty"]["essential"] is False
    revised["gate"]["uncertainty"]["essential"] = True
    assert revised == baseline


def test_c002_adds_only_prespecified_hierarchical_uncertainty() -> None:
    project = load_project_config(PROJECT_ROOT)
    development = load_development_config(PROJECT_ROOT, project=project)

    c001 = candidate_analysis_config(project, development, "C001")
    c002 = candidate_analysis_config(project, development, "C002")

    assert c002["gate"]["uncertainty"]["essential"] is False
    assert c002["gate"]["uncertainty"]["graded_filter"]["enabled"] is True
    assert c002["gate"]["uncertainty"]["graded_filter"]["retention_fraction"] == 0.80
    c002["gate"]["uncertainty"]["graded_filter"]["enabled"] = False
    c002["gate"]["uncertainty"]["graded_filter"]["retention_fraction"] = 1.0
    assert c002 == c001


def test_non_boolean_uncertainty_essential_override_is_rejected() -> None:
    project = load_project_config(PROJECT_ROOT)
    original = load_development_config(PROJECT_ROOT, project=project)
    candidates = deepcopy(original.candidates)
    candidates["candidates"]["C001"]["analysis_overrides"] = {
        "gate.uncertainty.essential": 0
    }

    with pytest.raises(ConfigurationError, match="essential flag must be Boolean"):
        validate_development_config(
            project,
            DevelopmentConfig(bank=deepcopy(original.bank), candidates=candidates),
        )


def test_invalid_graded_uncertainty_fraction_is_rejected() -> None:
    project = load_project_config(PROJECT_ROOT)
    original = load_development_config(PROJECT_ROOT, project=project)
    candidates = deepcopy(original.candidates)
    candidates["candidates"]["C002"]["analysis_overrides"][
        "gate.uncertainty.graded_filter.retention_fraction"
    ] = 0.0

    with pytest.raises(ConfigurationError, match="Graded retention"):
        validate_development_config(
            project,
            DevelopmentConfig(bank=deepcopy(original.bank), candidates=candidates),
        )


def test_evidence_state_can_truthfully_record_stage_c_unblinding() -> None:
    project = load_project_config(PROJECT_ROOT)
    governance = deepcopy(project.development_validation)
    governance["current_evidence_state"][
        "scientific_performance_unblinded_in_this_repository"
    ] = True

    validate_project_config(replace(project, development_validation=governance))
