from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from evidence_defeat.config import (
    ConfigurationError,
    ProjectConfig,
    load_project_config,
    validate_project_config,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_project_configuration_is_valid() -> None:
    config = load_project_config(PROJECT_ROOT)

    assert config.analysis["gate"]["combination"] == "logical_and"
    assert config.simulation["confirmatory_primary_safety_grid"]["scenario_count"] == 10
    assert config.poc["scientific_status"]["confirmatory_evidence"] is False


def test_mismatched_master_seed_is_rejected() -> None:
    original = load_project_config(PROJECT_ROOT)
    simulation = deepcopy(original.simulation)
    simulation["reproducibility"]["master_seed"] += 1

    with pytest.raises(ConfigurationError, match="master seeds must match"):
        validate_project_config(
            ProjectConfig(original.analysis, simulation, original.poc)
        )


def test_compensatory_gate_is_rejected() -> None:
    original = load_project_config(PROJECT_ROOT)
    analysis = deepcopy(original.analysis)
    analysis["gate"]["combination"] = "weighted_sum"

    with pytest.raises(ConfigurationError, match="logical AND"):
        validate_project_config(
            ProjectConfig(analysis, original.simulation, original.poc)
        )


def test_unmatched_uncertainty_comparator_is_rejected() -> None:
    original = load_project_config(PROJECT_ROOT)
    analysis = deepcopy(original.analysis)
    analysis["comparators"]["uncertainty_only"]["matched_coverage"] = False

    with pytest.raises(ConfigurationError, match="must match coverage"):
        validate_project_config(
            ProjectConfig(analysis, original.simulation, original.poc)
        )


def test_changed_tie_breaking_rule_is_rejected() -> None:
    original = load_project_config(PROJECT_ROOT)
    analysis = deepcopy(original.analysis)
    analysis["comparators"]["tie_breaking"] = "row_order"

    with pytest.raises(ConfigurationError, match="tie-breaking rule"):
        validate_project_config(
            ProjectConfig(analysis, original.simulation, original.poc)
        )


def test_outcome_stratified_outer_folds_are_rejected() -> None:
    original = load_project_config(PROJECT_ROOT)
    analysis = deepcopy(original.analysis)
    analysis["cross_fitting"]["outer_stratification"] = "treatment_and_outcome"

    with pytest.raises(ConfigurationError, match="treatment only"):
        validate_project_config(
            ProjectConfig(analysis, original.simulation, original.poc)
        )
