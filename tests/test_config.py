from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import pytest

from evidence_defeat.config import (
    ConfigurationError,
    load_project_config,
    validate_project_config,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_project_configuration_is_valid() -> None:
    config = load_project_config(PROJECT_ROOT)

    assert config.analysis["gate"]["combination"] == "logical_and"
    assert config.simulation["confirmatory_primary_safety_grid"]["scenario_count"] == 10
    assert config.poc["scientific_status"]["confirmatory_evidence"] is False
    assert config.poc["reporting"]["scientific_results_exposed"] is False
    assert config.poc["stage_b_reporting"]["scientific_results_exposed"] is False
    assert (
        config.development_validation["phase_boundaries"]["development"]["status"]
        == "blocked_pending_reviewed_development_bank"
    )


def test_mismatched_master_seed_is_rejected() -> None:
    original = load_project_config(PROJECT_ROOT)
    simulation = deepcopy(original.simulation)
    simulation["reproducibility"]["master_seed"] += 1

    with pytest.raises(ConfigurationError, match="master seeds must match"):
        validate_project_config(replace(original, simulation=simulation))


def test_compensatory_gate_is_rejected() -> None:
    original = load_project_config(PROJECT_ROOT)
    analysis = deepcopy(original.analysis)
    analysis["gate"]["combination"] = "weighted_sum"

    with pytest.raises(ConfigurationError, match="logical AND"):
        validate_project_config(replace(original, analysis=analysis))


def test_unmatched_uncertainty_comparator_is_rejected() -> None:
    original = load_project_config(PROJECT_ROOT)
    analysis = deepcopy(original.analysis)
    analysis["comparators"]["uncertainty_only"]["matched_coverage"] = False

    with pytest.raises(ConfigurationError, match="must match coverage"):
        validate_project_config(replace(original, analysis=analysis))


def test_changed_tie_breaking_rule_is_rejected() -> None:
    original = load_project_config(PROJECT_ROOT)
    analysis = deepcopy(original.analysis)
    analysis["comparators"]["tie_breaking"] = "row_order"

    with pytest.raises(ConfigurationError, match="tie-breaking rule"):
        validate_project_config(replace(original, analysis=analysis))


def test_outcome_stratified_outer_folds_are_rejected() -> None:
    original = load_project_config(PROJECT_ROOT)
    analysis = deepcopy(original.analysis)
    analysis["cross_fitting"]["outer_stratification"] = "treatment_and_outcome"

    with pytest.raises(ConfigurationError, match="treatment only"):
        validate_project_config(replace(original, analysis=analysis))


def test_changed_model_seed_rule_is_rejected() -> None:
    original = load_project_config(PROJECT_ROOT)
    analysis = deepcopy(original.analysis)
    analysis["reproducibility"]["model_seed_rule"] = "global_rng"

    with pytest.raises(ConfigurationError, match="model-seed derivation"):
        validate_project_config(replace(original, analysis=analysis))


def test_population_sd_scaling_is_rejected() -> None:
    original = load_project_config(PROJECT_ROOT)
    analysis = deepcopy(original.analysis)
    analysis["outcome"]["continuous_scaling_sd_ddof"] = 0

    with pytest.raises(ConfigurationError, match="ddof=1"):
        validate_project_config(replace(original, analysis=analysis))


def test_changed_policy_evaluation_structure_is_rejected() -> None:
    original = load_project_config(PROJECT_ROOT)
    analysis = deepcopy(original.analysis)
    analysis["policy_evaluation"]["outcome_regression_structure"] = "pooled_model"

    with pytest.raises(ConfigurationError, match="Policy-evaluation choice"):
        validate_project_config(replace(original, analysis=analysis))


def test_default_using_heldout_outcomes_is_rejected() -> None:
    original = load_project_config(PROJECT_ROOT)
    analysis = deepcopy(original.analysis)
    analysis["default_policy"]["held_out_outcomes_used"] = True

    with pytest.raises(ConfigurationError, match="Population-default choice"):
        validate_project_config(replace(original, analysis=analysis))


def test_invalid_propensity_clip_is_rejected() -> None:
    original = load_project_config(PROJECT_ROOT)
    analysis = deepcopy(original.analysis)
    analysis["propensity"]["clip"] = [0.0, 1.0]

    with pytest.raises(ConfigurationError, match="Propensity clipping"):
        validate_project_config(replace(original, analysis=analysis))


def test_unmatched_random_deferral_is_rejected() -> None:
    original = load_project_config(PROJECT_ROOT)
    analysis = deepcopy(original.analysis)
    analysis["comparators"]["random_deferral"]["matched_coverage"] = False

    with pytest.raises(ConfigurationError, match="Random deferral must match"):
        validate_project_config(replace(original, analysis=analysis))


def test_changed_policy_disagreement_candidate_count_is_rejected() -> None:
    original = load_project_config(PROJECT_ROOT)
    analysis = deepcopy(original.analysis)
    analysis["comparators"]["near_optimal_policy_disagreement"][
        "bootstrap_candidates_per_learner"
    ] = 10

    with pytest.raises(ConfigurationError, match="comparator choice"):
        validate_project_config(replace(original, analysis=analysis))


def test_exposing_scientific_results_during_poc_is_rejected() -> None:
    original = load_project_config(PROJECT_ROOT)
    poc = deepcopy(original.poc)
    poc["reporting"]["scientific_results_exposed"] = True

    with pytest.raises(ConfigurationError, match="POC reporting choice"):
        validate_project_config(replace(original, poc=poc))


def test_exposing_scientific_results_during_stage_b_is_rejected() -> None:
    original = load_project_config(PROJECT_ROOT)
    poc = deepcopy(original.poc)
    poc["stage_b_reporting"]["scientific_results_exposed"] = True

    with pytest.raises(ConfigurationError, match="Stage B reporting choice"):
        validate_project_config(replace(original, poc=poc))


def test_changed_stage_a_sample_size_is_rejected() -> None:
    original = load_project_config(PROJECT_ROOT)
    poc = deepcopy(original.poc)
    poc["software_smoke"]["sample_size"] = 1000

    with pytest.raises(ConfigurationError, match="Stage A smoke-test choice"):
        validate_project_config(replace(original, poc=poc))


def test_accepted_only_primary_safety_denominator_is_rejected() -> None:
    original = load_project_config(PROJECT_ROOT)
    analysis = deepcopy(original.analysis)
    analysis["known_truth_evaluation"]["primary_metric"] = (
        "material_error_among_accepted"
    )

    with pytest.raises(ConfigurationError, match="population denominator"):
        validate_project_config(replace(original, analysis=analysis))


def test_validation_data_cannot_be_reused_for_development() -> None:
    original = load_project_config(PROJECT_ROOT)
    governance = deepcopy(original.development_validation)
    governance["phase_boundaries"]["development"]["permitted_data"].append(
        "reserved_validation_simulation_bank"
    )

    with pytest.raises(ConfigurationError, match="only its synthetic development"):
        validate_project_config(replace(original, development_validation=governance))


def test_development_results_cannot_be_labelled_confirmatory() -> None:
    original = load_project_config(PROJECT_ROOT)
    governance = deepcopy(original.development_validation)
    governance["phase_boundaries"]["development"][
        "eligible_for_confirmatory_evidence"
    ] = True

    with pytest.raises(ConfigurationError, match="cannot be confirmatory"):
        validate_project_config(replace(original, development_validation=governance))


def test_validation_must_be_one_time_and_registered() -> None:
    original = load_project_config(PROJECT_ROOT)
    governance = deepcopy(original.development_validation)
    governance["phase_boundaries"]["independent_validation"][
        "run_once_after_registration"
    ] = False

    with pytest.raises(ConfigurationError, match="boundary changed"):
        validate_project_config(replace(original, development_validation=governance))


def test_weighted_fairness_selection_is_rejected() -> None:
    original = load_project_config(PROJECT_ROOT)
    governance = deepcopy(original.development_validation)
    governance["candidate_selection"]["weighted_composite_score"] = True

    with pytest.raises(ConfigurationError, match="Candidate-selection safeguard"):
        validate_project_config(replace(original, development_validation=governance))
