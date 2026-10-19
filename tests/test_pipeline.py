from __future__ import annotations

import inspect
from copy import deepcopy
from pathlib import Path

import numpy as np
import pytest

from evidence_defeat.config import load_project_config
from evidence_defeat.pipeline import (
    construct_outer_fold,
    run_cross_fitted_construction,
    scale_training_utility,
)
from evidence_defeat.preprocessing import CovariateSchema
from evidence_defeat.simulation import SimulationScenario, generate_simulation

PROJECT_ROOT = Path(__file__).resolve().parents[1]
pytestmark = [
    pytest.mark.filterwarnings(
        "ignore:Could not generate out-of-bag predictions.*:UserWarning"
    ),
]


@pytest.fixture(scope="module")
def diagnostic_configs() -> tuple[dict, dict]:
    """Reduce computation for a software integration test only."""

    project = load_project_config(PROJECT_ROOT)
    analysis = deepcopy(project.analysis)
    analysis["cross_fitting"]["outer_folds"] = 3

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
    return analysis, project.simulation


def test_binary_utility_is_not_rescaled() -> None:
    utility = np.array([0, 1, 1, 0], dtype=float)

    scaled, metadata = scale_training_utility(utility, outcome_type="binary")

    np.testing.assert_array_equal(scaled, utility)
    assert metadata.center == 0.0
    assert metadata.scale == 1.0
    assert metadata.ddof == 0


def test_continuous_utility_uses_training_sample_standard_deviation() -> None:
    utility = np.array([2.0, 4.0, 8.0, 10.0])

    scaled, metadata = scale_training_utility(
        utility,
        outcome_type="continuous",
        ddof=1,
    )

    assert scaled.mean() == pytest.approx(0.0, abs=1e-15)
    assert scaled.std(ddof=1) == pytest.approx(1.0)
    assert metadata.center == pytest.approx(utility.mean())
    assert metadata.scale == pytest.approx(utility.std(ddof=1))
    assert metadata.ddof == 1


def test_constant_continuous_utility_is_rejected() -> None:
    with pytest.raises(ValueError, match="positive variance"):
        scale_training_utility(
            np.ones(5),
            outcome_type="continuous",
            ddof=1,
        )


def test_outer_fold_constructor_cannot_receive_heldout_outcomes() -> None:
    parameters = inspect.signature(construct_outer_fold).parameters

    assert "heldout_outcome" not in parameters
    assert "heldout_utility" not in parameters
    assert "training_utility" in parameters


def test_cross_fitted_construction_is_complete_and_matches_fold_coverage(
    diagnostic_configs: tuple[dict, dict],
) -> None:
    analysis, simulation = diagnostic_configs
    generated = generate_simulation(
        SimulationScenario(
            scenario_id="pipeline-record-check",
            sample_size=300,
            defect="record_adequacy",
            replicate_id=0,
        ),
        simulation,
    )
    covariate_names = tuple(f"x{number}" for number in range(1, 11))
    schema = CovariateSchema(
        continuous=covariate_names,
        categorical=("group",),
    )
    frame = generated.observed

    result = run_cross_fitted_construction(
        frame.loc[:, list(schema.columns)],
        frame["outcome"].to_numpy(),
        frame["treatment"].to_numpy(),
        frame["row_id"].to_numpy(),
        schema=schema,
        trial_id="simulation",
        run_id="pipeline-record-check-0",
        outcome_type="binary",
        analysis_config=analysis,
    )

    assert result.predictions.effect_matrix.shape == (300, 3)
    assert result.outcome_type == "binary"
    assert result.schema == schema
    np.testing.assert_array_equal(result.treatment, frame["treatment"])
    assert np.isfinite(result.predictions.effect_matrix).all()
    assert np.isfinite(result.predictions.primary_interval_lower).all()
    assert np.isfinite(result.predictions.primary_interval_upper).all()
    assert len(result.folds) == 3
    np.testing.assert_array_equal(result.row_ids, frame["row_id"].astype(str))

    expected_complete = np.logical_and.reduce(
        [result.checks[name] for name in result.gate.essential_checks]
    )
    np.testing.assert_array_equal(result.gate.complete, expected_complete)
    for check in result.checks.values():
        assert check.dtype == np.bool_
        assert check.shape == (300,)

    for fold_id in np.unique(result.fold_ids):
        in_fold = result.fold_ids == fold_id
        assert result.uncertainty_only_acceptance[in_fold].sum() == (
            result.gate.complete[in_fold].sum()
        )

    record_defect = generated.defects["record_adequacy"].to_numpy(dtype=bool)
    assert record_defect.any()
    assert not result.checks["record_adequacy"][record_defect].any()
    np.testing.assert_allclose(result.record_observed_fraction[record_defect], 8 / 11)
