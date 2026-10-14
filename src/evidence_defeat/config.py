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
    """The three configuration documents needed before a diagnostic run."""

    analysis: dict[str, Any]
    simulation: dict[str, Any]
    poc: dict[str, Any]


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

    for prevalence in _all_declared_prevalences(simulation):
        if not 0.0 <= prevalence <= 1.0:
            raise ConfigurationError(f"Defect prevalence outside [0,1]: {prevalence}")


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
    )
    validate_project_config(config)
    return config
