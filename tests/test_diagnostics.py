from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from evidence_defeat.config import ProjectConfig, load_project_config
from evidence_defeat.diagnostics import (
    canonical_sha256,
    execute_diagnostic_run,
    plan_smoke_runs,
    select_smoke_run,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
pytestmark = [
    pytest.mark.filterwarnings(
        "ignore:Could not generate out-of-bag predictions.*:UserWarning"
    ),
]


def test_canonical_hash_is_invariant_to_mapping_order() -> None:
    first = {"b": [2, 3], "a": {"d": 4, "c": 1}}
    second = {"a": {"c": 1, "d": 4}, "b": [2, 3]}

    assert canonical_sha256(first) == canonical_sha256(second)
    assert len(canonical_sha256(first)) == 64


def test_stage_a_plan_contains_the_frozen_twelve_runs() -> None:
    project = load_project_config(PROJECT_ROOT)

    specs = plan_smoke_runs(project)

    assert len(specs) == 12
    assert {spec.scenario_name for spec in specs} == {
        "clean_control",
        "record_adequacy",
        "reference_support",
        "model_multiplicity",
        "decision_uncertainty",
        "combined",
    }
    assert {spec.scenario.replicate_id for spec in specs} == {0, 1}
    assert {spec.scenario.sample_size for spec in specs} == {500}
    assert len({spec.run_id for spec in specs}) == 12


def test_unplanned_diagnostic_run_is_rejected() -> None:
    project = load_project_config(PROJECT_ROOT)

    with pytest.raises(ValueError, match="not in the Stage A plan"):
        select_smoke_run(project, "combined", 999)


@pytest.fixture(scope="module")
def reduced_diagnostic_project() -> ProjectConfig:
    """Use small models only to test orchestration, never scientific results."""

    original = load_project_config(PROJECT_ROOT)
    analysis = deepcopy(original.analysis)
    simulation = deepcopy(original.simulation)
    poc = deepcopy(original.poc)
    poc["software_smoke"]["sample_size"] = 180
    poc["software_smoke"]["scenarios"] = ["clean_control"]
    poc["software_smoke"]["replicate_ids"] = [0]
    analysis["cross_fitting"]["outer_folds"] = 3
    analysis["comparators"]["random_deferral"]["repetitions"] = 5

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
    return ProjectConfig(analysis=analysis, simulation=simulation, poc=poc)


def test_end_to_end_diagnostic_report_is_passed_and_disclosure_safe(
    reduced_diagnostic_project: ProjectConfig,
) -> None:
    spec = plan_smoke_runs(reduced_diagnostic_project)[0]

    report = execute_diagnostic_run(
        reduced_diagnostic_project,
        spec,
        code_commit="a" * 40,
        git_branch="protocol-v0.1",
        repository_clean_at_start=True,
    )
    payload = report.to_dict()

    assert report.passed
    assert all(item.passed for item in report.invariants)
    assert report.eligible_for_paper_effect_estimates is False
    assert report.fingerprint.sample_size == 180
    assert set(report.fingerprint.configuration_sha256) == {
        "analysis",
        "simulation",
        "poc",
        "combined",
    }
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
