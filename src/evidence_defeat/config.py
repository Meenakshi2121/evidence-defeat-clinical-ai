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

    if _require(analysis, "gate", "combination") != "logical_and":
        raise ConfigurationError("The primary gate must use logical AND")
    if _require(analysis, "gate", "weighted_compensation") is not False:
        raise ConfigurationError("Weighted compensation must remain disabled")
    if (
        _require(analysis, "comparators", "uncertainty_only", "matched_coverage")
        is not True
    ):
        raise ConfigurationError("Uncertainty-only comparison must match coverage")
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
