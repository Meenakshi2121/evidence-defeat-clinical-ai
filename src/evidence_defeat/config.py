"""Load and validate the project's prespecified configuration files."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


class ConfigurationError(ValueError):
    """Raised when a project configuration violates a locked invariant."""


@dataclass(frozen=True)
class ProjectConfig:
    """The configuration documents needed before a diagnostic run."""

    analysis: dict[str, Any]
    simulation: dict[str, Any]
    poc: dict[str, Any]
    development_validation: dict[str, Any]


def load_yaml(path: str | Path) -> dict[str, Any]:
    """Load one YAML mapping without applying defaults silently."""

    config_path = Path(path)
    with config_path.open(encoding="utf-8") as stream:
        loaded = yaml.safe_load(stream)
    if not isinstance(loaded, dict):
        raise ConfigurationError(f"{config_path} must contain a YAML mapping")
    return loaded


def _require(mapping: dict[str, Any], *keys: str) -> Any:
    current: Any = mapping
    traversed: list[str] = []
    for key in keys:
        traversed.append(key)
        if not isinstance(current, dict) or key not in current:
            raise ConfigurationError(
                f"Missing configuration key: {'.'.join(traversed)}"
            )
        current = current[key]
    return current


def validate_project_config(config: ProjectConfig) -> None:
    """Validate cross-file invariants that must hold before any simulation."""

    analysis = config.analysis
    simulation = config.simulation
    poc = config.poc
    development_validation = config.development_validation

    master_seed = _require(analysis, "master_seed")
    if not isinstance(master_seed, int) or isinstance(master_seed, bool):
        raise ConfigurationError("analysis.master_seed must be an integer")
    if _require(simulation, "reproducibility", "master_seed") != master_seed:
        raise ConfigurationError("Analysis and simulation master seeds must match")

    if _require(analysis, "cross_fitting", "outer_stratification") != "treatment_only":
        raise ConfigurationError("Outer folds must be stratified by treatment only")
    if (
        _require(analysis, "cross_fitting", "outer_splitter")
        != "sklearn.model_selection.StratifiedKFold"
    ):
        raise ConfigurationError("The outer-fold splitter has changed")
    if _require(analysis, "cross_fitting", "outer_shuffle") is not True:
        raise ConfigurationError("Outer-fold shuffling must remain enabled")
    if (
        _require(analysis, "cross_fitting", "row_order_before_split")
        != "ascending_string_row_id"
    ):
        raise ConfigurationError("The pre-split row-order rule has changed")
    inner_folds = _require(analysis, "cross_fitting", "inner_folds")
    if (
        not isinstance(inner_folds, int)
        or isinstance(inner_folds, bool)
        or inner_folds < 2
    ):
        raise ConfigurationError("At least two inner folds are required")

    if _require(analysis, "gate", "combination") != "logical_and":
        raise ConfigurationError("The primary gate must use logical AND")
    if _require(analysis, "gate", "weighted_compensation") is not False:
        raise ConfigurationError("Weighted compensation must remain disabled")
    if (
        _require(analysis, "comparators", "uncertainty_only", "matched_coverage")
        is not True
    ):
        raise ConfigurationError("Uncertainty-only comparison must match coverage")
    policy_disagreement = _require(
        analysis,
        "comparators",
        "near_optimal_policy_disagreement",
    )
    expected_policy_disagreement = {
        "matched_coverage": True,
        "exact_replication_claimed": False,
        "bootstrap_candidates_per_learner": 20,
        "candidate_learners": [
            "causal_forest_dml",
            "penalised_interaction",
            "boosted_dr_learner",
        ],
        "candidate_value_estimator": "inner_cross_fitted_aipw",
        "near_optimal_rule": "within_one_standard_error_of_best_training_value",
        "minimum_near_optimal_policies": 5,
        "fallback_if_fewer": "include_next_best_until_five_and_flag",
        "disagreement_score": (
            "1-max(vote_fraction_treatment_0,vote_fraction_treatment_1)"
        ),
        "accept": "lowest_scores_to_exact_gate_count_within_outer_fold",
    }
    for key, expected in expected_policy_disagreement.items():
        if _require(policy_disagreement, key) != expected:
            raise ConfigurationError(
                f"Policy-disagreement comparator choice has changed: {key}"
            )
    random_deferral = _require(analysis, "comparators", "random_deferral")
    if _require(random_deferral, "matched_coverage") is not True:
        raise ConfigurationError("Random deferral must match gate coverage")
    repetitions = _require(random_deferral, "repetitions")
    if (
        not isinstance(repetitions, int)
        or isinstance(repetitions, bool)
        or repetitions < 1
    ):
        raise ConfigurationError("Random-deferral repetitions must be positive")
    if _require(random_deferral, "seeds") != "derived_from_master_seed":
        raise ConfigurationError("Random-deferral seeds must be derived reproducibly")
    known_truth = _require(analysis, "known_truth_evaluation")
    if _require(known_truth, "primary_metric") != (
        "material_unsafe_acceptance_population_denominator"
    ):
        raise ConfigurationError(
            "Unsafe acceptance must use the population denominator"
        )
    if _require(known_truth, "primary_contrast") != (
        "complete_gate_minus_uncertainty_only_at_matched_coverage"
    ):
        raise ConfigurationError("The primary known-truth contrast has changed")
    if _require(known_truth, "regret_relative_to_default_sign") != (
        "default_utility_minus_deployed_utility"
    ):
        raise ConfigurationError("Relative-to-default regret sign has changed")
    expected_tie_rule = (
        "ascending_sha256_hex(canonical_json([trial_id,row_id,master_seed]))"
    )
    if _require(analysis, "comparators", "tie_breaking") != expected_tie_rule:
        raise ConfigurationError("The deterministic tie-breaking rule has changed")
    expected_model_seed_rule = (
        "int.from_bytes(first_8_bytes(sha256(canonical_json([master_seed,run_id,"
        "fold_id,learner_id]))),big) modulo 2^32"
    )
    if _require(analysis, "reproducibility", "model_seed_rule") != (
        expected_model_seed_rule
    ):
        raise ConfigurationError("The model-seed derivation rule has changed")
    if (
        _require(analysis, "nuisance_outcome_model", "parameters", "random_state")
        != "derived_from_master_seed"
    ):
        raise ConfigurationError("The nuisance learner must use a derived seed")
    if _require(analysis, "outcome", "continuous_scaling_sd_ddof") != 1:
        raise ConfigurationError(
            "Continuous outcomes must use the outer-training sample SD with ddof=1"
        )

    evaluation = _require(analysis, "policy_evaluation")
    expected_evaluation_choices = {
        "outcome_regression_structure": "separate_models_by_treatment_arm",
        "default_nuisance_predictions": (
            "inner_cross_fitted_within_outer_training_fold"
        ),
        "heldout_nuisance_predictions": "fit_on_complete_outer_training_fold",
        "propensity_source_order": (
            "documented_randomisation_probability_else_outer_training_fraction"
        ),
        "conditional_standard_errors_are_final_inference": False,
    }
    for key, expected in expected_evaluation_choices.items():
        if _require(evaluation, key) != expected:
            raise ConfigurationError(f"Policy-evaluation choice has changed: {key}")

    expected_default_choices = {
        "estimator": "training_fold_aipw_population_mean_difference",
        "treatment_1_rule": (
            "estimated_mean_utility_difference_greater_than_materiality_margin"
        ),
        "otherwise": 0,
        "held_out_outcomes_used": False,
    }
    default_policy = _require(analysis, "default_policy")
    for key, expected in expected_default_choices.items():
        if _require(default_policy, key) != expected:
            raise ConfigurationError(f"Population-default choice has changed: {key}")
    if _require(analysis, "real_outcome_evaluation", "estimator") != (
        "cross_fitted_aipw"
    ):
        raise ConfigurationError(
            "Real-outcome evaluation must remain cross-fitted AIPW"
        )

    propensity_clip = _require(analysis, "propensity", "clip")
    if (
        not isinstance(propensity_clip, list)
        or len(propensity_clip) != 2
        or not 0.0 < float(propensity_clip[0]) < float(propensity_clip[1]) < 1.0
    ):
        raise ConfigurationError("Propensity clipping bounds must lie inside (0, 1)")

    forest = _require(analysis, "learners", "primary", "parameters")
    trees = _require(forest, "n_estimators")
    subforest = _require(forest, "subforest_size")
    if not isinstance(trees, int) or not isinstance(subforest, int):
        raise ConfigurationError("Forest and subforest sizes must be integers")
    if trees <= 0 or subforest <= 0 or trees % subforest:
        raise ConfigurationError(
            "Forest size must be positive and divisible by subforest size"
        )

    binary_delta = _require(simulation, "materiality", "binary_utility_delta")
    if binary_delta != _require(analysis, "outcome", "binary_materiality_margin"):
        raise ConfigurationError("Binary materiality margins disagree across files")
    continuous_delta = _require(
        simulation, "materiality", "continuous_utility_delta_training_sd"
    )
    if continuous_delta != _require(
        analysis, "outcome", "continuous_materiality_margin_sd"
    ):
        raise ConfigurationError("Continuous materiality margins disagree across files")

    primary = _require(simulation, "confirmatory_primary_safety_grid")
    expected_count = len(_require(primary, "include_defects")) * len(
        _require(primary, "sample_sizes")
    )
    if _require(primary, "scenario_count") != expected_count:
        raise ConfigurationError(
            "Primary scenario_count does not match its declared grid"
        )

    if _require(poc, "scientific_status", "confirmatory_evidence") is not False:
        raise ConfigurationError("Proof-of-concept runs must remain non-confirmatory")
    for prohibited_key in (
        "threshold_tuning_allowed",
        "learner_selection_allowed",
        "scenario_dropping_allowed",
    ):
        if _require(poc, "scientific_status", prohibited_key) is not False:
            raise ConfigurationError(
                f"poc.scientific_status.{prohibited_key} must be false"
            )

    smoke = _require(poc, "software_smoke")
    expected_smoke_choices = {
        "sample_size": 500,
        "replicate_ids": [0, 1],
        "scenarios": [
            "clean_control",
            "record_adequacy",
            "reference_support",
            "model_multiplicity",
            "decision_uncertainty",
            "combined",
        ],
        "use_locked_analysis_hyperparameters": True,
        "include_comparators": [
            "population_default",
            "ungated_individualisation",
            "uncertainty_only",
            "random_deferral",
            "single_check_selectors",
            "leave_one_check_out_ablations",
        ],
        "exclude_for_smoke": [
            "near_optimal_policy_disagreement",
            "full_pipeline_bootstrap",
        ],
    }
    for key, expected in expected_smoke_choices.items():
        if _require(smoke, key) != expected:
            raise ConfigurationError(f"Stage A smoke-test choice has changed: {key}")

    timing = _require(poc, "full_comparator_timing")
    expected_timing_choices = {
        "scenarios": ["combined"],
        "sample_sizes": [500, 2000],
        "replicate_ids": [900001],
        "include_near_optimal_policy_disagreement": True,
        "include_full_pipeline_bootstrap": False,
    }
    for key, expected in expected_timing_choices.items():
        if _require(timing, key) != expected:
            raise ConfigurationError(f"Stage B timing choice has changed: {key}")

    bootstrap_timing = _require(poc, "bootstrap_timing")
    expected_bootstrap_choices = {
        "scenario": "combined",
        "sample_size": 2000,
        "replicate_id": 900002,
        "bootstrap_repetitions": 5,
        "repeat_complete_pipeline": True,
        "extrapolation_only": True,
    }
    for key, expected in expected_bootstrap_choices.items():
        if _require(bootstrap_timing, key) != expected:
            raise ConfigurationError(
                f"Stage B bootstrap-timing choice has changed: {key}"
            )

    reporting = _require(poc, "reporting")
    expected_reporting_choices = {
        "output_root": "results/poc/stage-a",
        "require_clean_git": True,
        "process_isolation_per_run": True,
        "scientific_results_exposed": False,
    }
    for key, expected in expected_reporting_choices.items():
        if _require(reporting, key) != expected:
            raise ConfigurationError(f"POC reporting choice has changed: {key}")
    expected_saved_fields = {
        "run_status_and_timestamps",
        "invariant_statuses",
        "run_fingerprint",
        "wall_clock_seconds",
        "process_peak_rss_mb",
        "computing_environment",
    }
    saved_fields = _require(reporting, "save_only")
    if not isinstance(saved_fields, list) or set(saved_fields) != expected_saved_fields:
        raise ConfigurationError("POC reporting save_only fields have changed")

    stage_b_reporting = _require(poc, "stage_b_reporting")
    expected_stage_b_reporting = {
        "output_root": "results/poc/stage-b",
        "require_clean_git": True,
        "process_isolation_per_run": True,
        "scientific_results_exposed": False,
    }
    for key, expected in expected_stage_b_reporting.items():
        if _require(stage_b_reporting, key) != expected:
            raise ConfigurationError(f"Stage B reporting choice has changed: {key}")
    stage_b_saved_fields = _require(stage_b_reporting, "save_only")
    if (
        not isinstance(stage_b_saved_fields, list)
        or set(stage_b_saved_fields) != expected_saved_fields
    ):
        raise ConfigurationError("Stage B reporting save_only fields have changed")

    _validate_development_validation(
        development_validation,
        analysis=analysis,
        simulation=simulation,
    )

    for prevalence in _all_declared_prevalences(simulation):
        if not 0.0 <= prevalence <= 1.0:
            raise ConfigurationError(f"Defect prevalence outside [0,1]: {prevalence}")


def _validate_development_validation(
    governance: dict[str, Any],
    *,
    analysis: dict[str, Any],
    simulation: dict[str, Any],
) -> None:
    """Enforce separation between adaptive development and final validation."""

    if _require(governance, "schema_version") != "0.2":
        raise ConfigurationError("Development/validation schema version has changed")
    if _require(governance, "status") != "draft_prelock_amendment":
        raise ConfigurationError("Development/validation amendment status has changed")

    evidence_state = _require(governance, "current_evidence_state")
    expected_evidence_state = {
        "scientific_performance_unblinded_in_this_repository": False,
        "stage_a_and_b_outputs_are_diagnostic_only": True,
        "rct_bench_patient_level_files_opened": False,
        "confirmatory_validation_started": False,
    }
    for key, expected in expected_evidence_state.items():
        if _require(evidence_state, key) is not expected:
            raise ConfigurationError(
                f"Current evidence-state declaration changed: {key}"
            )

    phases = _require(governance, "phase_boundaries")
    diagnostics = _require(phases, "diagnostics")
    expected_diagnostics = {
        "stages": ["stage_a", "stage_b"],
        "scientific_results_exposed": False,
        "eligible_for_candidate_selection": False,
        "eligible_for_confirmatory_evidence": False,
    }
    for key, expected in expected_diagnostics.items():
        if _require(diagnostics, key) != expected:
            raise ConfigurationError(f"Diagnostic-phase boundary changed: {key}")

    development = _require(phases, "development")
    if _require(development, "stage") != "stage_c":
        raise ConfigurationError("Development must remain Stage C")
    if _require(development, "status") != ("blocked_pending_reviewed_development_bank"):
        raise ConfigurationError(
            "Stage C must remain blocked until its development bank is reviewed"
        )
    if _require(development, "scientific_results_exposed") is not True:
        raise ConfigurationError("Stage C must be explicitly declared unblinded")
    if _require(development, "eligible_for_confirmatory_evidence") is not False:
        raise ConfigurationError("Development results cannot be confirmatory evidence")

    permitted_data = _require(development, "permitted_data")
    prohibited_data = _require(development, "prohibited_data")
    if permitted_data != ["controlled_synthetic_development_bank"]:
        raise ConfigurationError("Stage C may use only its synthetic development bank")
    expected_prohibited_data = {
        "reserved_validation_simulation_bank",
        "rct_bench_patient_level_files",
        "real_trial_outcomes",
    }
    if not isinstance(prohibited_data, list) or set(prohibited_data) != (
        expected_prohibited_data
    ):
        raise ConfigurationError("Stage C prohibited-data boundary has changed")
    if set(permitted_data) & set(prohibited_data):
        raise ConfigurationError("Development and prohibited data must be disjoint")

    bank = _require(development, "development_bank_requirement")
    if _require(bank, "specification_required_before_first_run") is not True:
        raise ConfigurationError(
            "A reviewed development-bank specification is required"
        )
    if _require(bank, "separate_scenario_ids_and_replicate_namespace") is not True:
        raise ConfigurationError(
            "Development and validation namespaces must be separate"
        )
    if _require(bank, "configuration_file") != "not_yet_created":
        raise ConfigurationError(
            "Stage C cannot be enabled by naming an unreviewed development bank"
        )

    freeze = _require(phases, "development_freeze")
    if _require(freeze, "stage") != "stage_d":
        raise ConfigurationError("Development freeze must remain Stage D")
    expected_freeze_requirements = {
        "one_final_candidate_identifier",
        "clean_git_commit",
        "configuration_hashes",
        "complete_candidate_history",
        "written_selection_rationale",
        "supervisor_and_statistical_review",
        "registered_protocol_v1_0",
    }
    freeze_requirements = _require(freeze, "requirements")
    if not isinstance(freeze_requirements, list) or set(freeze_requirements) != (
        expected_freeze_requirements
    ):
        raise ConfigurationError("Development-freeze requirements have changed")

    pilot = _require(phases, "blinded_variance_pilot")
    expected_pilot = {
        "stage": "stage_e",
        "runs_after_development_freeze": True,
        "permitted_disclosures": [
            "paired_primary_contrast_standard_deviation",
            "runtime",
            "memory",
        ],
        "prohibited_disclosures": [
            "mean_effect_estimates",
            "method_rankings",
            "group_differences",
        ],
        "adaptations_after_pilot": [
            "monte_carlo_replicate_count",
            "computational_batching",
        ],
        "scientific_method_changes_allowed": False,
    }
    for key, expected in expected_pilot.items():
        if _require(pilot, key) != expected:
            raise ConfigurationError(f"Blinded-pilot boundary changed: {key}")

    validation = _require(phases, "independent_validation")
    expected_validation_choices = {
        "stage": "stage_f",
        "run_once_after_registration": True,
        "development_data_reuse": False,
        "confidence_interval": "two_sided_95_percent",
        "support_rule": "upper_confidence_limit_below_zero",
        "report_regardless_of_result": True,
        "change_after_unblinding": (
            "new_framework_version_and_new_independent_validation"
        ),
    }
    for key, expected in expected_validation_choices.items():
        if _require(validation, key) != expected:
            raise ConfigurationError(f"Independent-validation boundary changed: {key}")
    validation_sources = _require(validation, "sources")
    if _require(validation_sources, "reserved_validation_simulation_bank") != (
        "confirmatory_primary_safety_grid"
    ):
        raise ConfigurationError("The reserved simulation validation bank changed")
    if "confirmatory_primary_safety_grid" not in simulation:
        raise ConfigurationError("The reserved simulation validation bank is missing")
    for source in ("rct_shaped_semisynthetic", "real_rct_outcomes"):
        if _require(validation_sources, source) != "unopened_until_development_freeze":
            raise ConfigurationError(f"Validation source opened too early: {source}")

    known_truth = _require(analysis, "known_truth_evaluation")
    if _require(validation, "primary_metric") != _require(
        known_truth, "primary_metric"
    ):
        raise ConfigurationError("Validation primary metric disagrees with analysis")
    if _require(validation, "primary_contrast") != _require(
        known_truth, "primary_contrast"
    ):
        raise ConfigurationError("Validation primary contrast disagrees with analysis")

    audit = _require(governance, "development_audit")
    expected_audit_flags = {
        "require_candidate_id": True,
        "require_parent_candidate_id": True,
        "require_pre_run_rationale": True,
        "require_clean_git_commit": True,
        "require_configuration_hashes": True,
        "retain_all_candidate_results": True,
        "retain_unsuccessful_candidates": True,
        "prohibit_relabelling_as_confirmatory": True,
    }
    for key, expected in expected_audit_flags.items():
        if _require(audit, key) is not expected:
            raise ConfigurationError(f"Development-audit safeguard changed: {key}")
    expected_metrics = {
        "material_unsafe_acceptance_population_denominator",
        "coverage",
        "deployed_policy_utility",
        "oracle_regret",
        "regret_relative_to_default",
        "raw_group_differences",
        "evidence_standardised_group_differences",
        "scenario_and_seed_stability",
    }
    mandatory_metrics = _require(audit, "mandatory_metrics")
    if not isinstance(mandatory_metrics, list) or set(mandatory_metrics) != (
        expected_metrics
    ):
        raise ConfigurationError("Development metric profile has changed")

    selection = _require(governance, "candidate_selection")
    expected_selection = {
        "weighted_composite_score": False,
        "inspect_complete_metric_profile": True,
        "require_safety_utility_access_fairness_tradeoff": True,
        "prefer_pareto_nondominated_candidates": True,
        "simplicity_breaks_practical_ties": True,
        "final_choice_requires_written_rationale": True,
        "development_success_is_confirmatory_evidence": False,
    }
    for key, expected in expected_selection.items():
        if _require(selection, key) is not expected:
            raise ConfigurationError(f"Candidate-selection safeguard changed: {key}")

    fairness = _require(governance, "fairness")
    expected_fairness = {
        "role": "safety_and_access_audit",
        "weighted_fairness_composite": False,
        "report_raw_and_evidence_standardised_separately": True,
        "aggregate_improvement_cannot_hide_group_harm": True,
    }
    for key, expected in expected_fairness.items():
        if _require(fairness, key) != expected:
            raise ConfigurationError(f"Fairness-audit safeguard changed: {key}")
    if _require(analysis, "fairness_audit", "weighted_composite_primary") is not False:
        raise ConfigurationError("Analysis and governance fairness rules disagree")


def _all_declared_prevalences(simulation: dict[str, Any]) -> list[float]:
    values: list[float] = []
    for defect in _require(simulation, "single_defects").values():
        values.append(float(_require(defect, "overall_prevalence")))
    for value in _require(simulation, "combined_defects", "prevalence").values():
        values.append(float(value))
    return values


def load_project_config(root: str | Path = ".") -> ProjectConfig:
    """Load and validate all pre-lock project configuration documents."""

    project_root = Path(root)
    config = ProjectConfig(
        analysis=load_yaml(project_root / "config" / "analysis.yaml"),
        simulation=load_yaml(project_root / "config" / "simulation_scenarios.yaml"),
        poc=load_yaml(project_root / "config" / "poc.yaml"),
        development_validation=load_yaml(
            project_root / "config" / "development_validation.yaml"
        ),
    )
    validate_project_config(config)
    return config
