from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from evidence_defeat.config import ProjectConfig, load_project_config
from evidence_defeat.feasibility import (
    TimingRunSpec,
    execute_timing_run,
    plan_stage_b_runs,
    select_stage_b_run,
)
from evidence_defeat.simulation import SimulationScenario

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_stage_b_plan_contains_two_comparator_and_five_bootstrap_units() -> None:
    project = load_project_config(PROJECT_ROOT)

    specs = plan_stage_b_runs(project)

    assert len(specs) == 7
    assert [spec.timing_id for spec in specs[:2]] == [
        "full_comparator_n500",
        "full_comparator_n2000",
    ]
    assert {spec.scenario.replicate_id for spec in specs[:2]} == {900001}
    assert [spec.bootstrap_repetition for spec in specs[2:]] == list(range(5))
    assert {spec.scenario.replicate_id for spec in specs[2:]} == {900002}


def test_unplanned_stage_b_identifier_is_rejected() -> None:
    project = load_project_config(PROJECT_ROOT)

    try:
        select_stage_b_run(project, "not-planned")
    except ValueError as error:
        assert "not in the Stage B plan" in str(error)
    else:  # pragma: no cover
        raise AssertionError("unplanned timing identifier was accepted")


def test_reduced_stage_b_report_is_passed_and_disclosure_safe() -> None:
    original = load_project_config(PROJECT_ROOT)
    analysis = deepcopy(original.analysis)
    analysis["cross_fitting"]["outer_folds"] = 2
    analysis["cross_fitting"]["inner_folds"] = 2
    analysis["comparators"]["near_optimal_policy_disagreement"][
        "bootstrap_candidates_per_learner"
    ] = 1
    analysis["comparators"]["near_optimal_policy_disagreement"][
        "minimum_near_optimal_policies"
    ] = 2
    nuisance = analysis["nuisance_outcome_model"]["parameters"]
    nuisance["max_iter"] = 20
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
    )
    spec = TimingRunSpec(
        timing_id="test_full_comparator",
        component="full_comparator",
        scenario=SimulationScenario(
            scenario_id="test_stage_b_combined_n160",
            sample_size=160,
            defect="combined",
            replicate_id=999001,
        ),
        bootstrap_repetition=None,
    )

    report = execute_timing_run(
        project,
        spec,
        code_commit="b" * 40,
        git_branch="protocol-v0.1",
        repository_clean_at_start=True,
    )
    payload = report.to_dict()

    assert report.passed
    assert all(item.passed for item in report.invariants)
    assert report.eligible_for_paper_effect_estimates is False
    forbidden = {
        "metrics",
        "policy_values",
        "method_rankings",
        "primary_contrast",
        "coverage",
        "unsafe_acceptance_rate",
        "utility",
        "regret",
        "effect_estimate",
    }
    assert not (_mapping_keys(payload) & forbidden)


def _mapping_keys(value) -> set[str]:
    if isinstance(value, dict):
        result = set(value)
        for item in value.values():
            result.update(_mapping_keys(item))
        return result
    if isinstance(value, list):
        result: set[str] = set()
        for item in value:
            result.update(_mapping_keys(item))
        return result
    return set()
