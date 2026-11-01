from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from evidence_defeat.config import load_project_config
from evidence_defeat.simulation import SimulationScenario, generate_simulation

PROJECT_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def simulation_config() -> dict:
    return load_project_config(PROJECT_ROOT).simulation


def _scenario(
    defect: str,
    *,
    sample_size: int = 10_000,
    replicate_id: int = 0,
    scenario_id: str | None = None,
    **kwargs,
) -> SimulationScenario:
    return SimulationScenario(
        scenario_id=scenario_id or f"test-{defect}-{sample_size}",
        sample_size=sample_size,
        defect=defect,
        replicate_id=replicate_id,
        **kwargs,
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("defect", "misspelled_defect"),
        ("outcome_type", "count"),
        ("baseline_shape", "curved"),
        ("effect_strength", "extreme"),
        ("defect_allocation", "biased"),
    ],
)
def test_invalid_scenario_choices_are_rejected(field: str, value: str) -> None:
    arguments = {
        "scenario_id": "invalid-scenario",
        "sample_size": 100,
        "defect": "none",
        "replicate_id": 0,
    }
    arguments[field] = value

    with pytest.raises(ValueError, match=field):
        SimulationScenario(**arguments)


def test_same_scenario_and_replicate_are_bitwise_reproducible(
    simulation_config,
) -> None:
    scenario = _scenario("combined", sample_size=2_000)
    first = generate_simulation(scenario, simulation_config)
    second = generate_simulation(scenario, simulation_config)

    assert first.seed == second.seed
    pd.testing.assert_frame_equal(first.observed, second.observed)
    pd.testing.assert_frame_equal(first.defects, second.defects)
    np.testing.assert_array_equal(first.tau_true, second.tau_true)


def test_replicate_identifier_changes_generated_data(simulation_config) -> None:
    first = generate_simulation(_scenario("none", replicate_id=0), simulation_config)
    second = generate_simulation(_scenario("none", replicate_id=1), simulation_config)

    assert first.seed != second.seed
    assert not np.array_equal(first.latent_covariates, second.latent_covariates)


def test_binary_means_and_truth_are_valid(simulation_config) -> None:
    generated = generate_simulation(_scenario("combined"), simulation_config)

    assert np.all((generated.mu0 >= 0.01) & (generated.mu0 <= 0.99))
    assert np.all((generated.mu1 >= 0.01) & (generated.mu1 <= 0.99))
    np.testing.assert_allclose(generated.tau_true, generated.mu1 - generated.mu0)
    np.testing.assert_array_equal(
        generated.optimal_action,
        (generated.tau_true > 0).astype(np.int8),
    )
    assert generated.materially_actionable is not None


def test_randomised_treatment_is_balanced_and_independent_streamed(
    simulation_config,
) -> None:
    generated = generate_simulation(
        _scenario("none", sample_size=50_000), simulation_config
    )

    treatment_rate = generated.observed["treatment"].mean()
    assert treatment_rate == pytest.approx(0.5, abs=0.01)


def test_record_defect_masks_three_action_relevant_covariates(
    simulation_config,
) -> None:
    generated = generate_simulation(
        _scenario("record_adequacy", sample_size=30_000), simulation_config
    )
    flag = generated.defects["record_adequacy"].to_numpy(dtype=bool)

    assert flag.mean() == pytest.approx(0.20, abs=0.015)
    assert generated.observed.loc[flag, ["x1", "x2", "x3"]].isna().all().all()
    assert not generated.observed.loc[~flag, ["x1", "x2", "x3"]].isna().any().any()
    np.testing.assert_allclose(generated.record_completeness[flag], 0.70)
    expected = np.where(generated.latent_covariates[flag, 0] > -0.50, 0.08, -0.08)
    np.testing.assert_allclose(generated.tau_target[flag], expected)


def test_support_defect_creates_rare_shifted_component_and_reversal(
    simulation_config,
) -> None:
    generated = generate_simulation(
        _scenario("reference_support", sample_size=50_000), simulation_config
    )
    flag = generated.defects["reference_support"].to_numpy(dtype=bool)
    difference = generated.complete_covariates - generated.latent_covariates

    assert flag.mean() == pytest.approx(0.02, abs=0.004)
    np.testing.assert_allclose(difference[flag, :3], 4.0)
    np.testing.assert_allclose(difference[~flag], 0.0)
    np.testing.assert_allclose(generated.tau_target[flag], -0.08)


def test_multiplicity_defect_has_quadrant_effect(simulation_config) -> None:
    generated = generate_simulation(
        _scenario("model_multiplicity", sample_size=30_000), simulation_config
    )
    flag = generated.defects["model_multiplicity"].to_numpy(dtype=bool)
    x = generated.complete_covariates
    expected = np.where(x[flag, 0] * x[flag, 1] > 0.0, 0.10, -0.06)

    assert flag.mean() == pytest.approx(0.25, abs=0.015)
    np.testing.assert_allclose(generated.tau_target[flag], expected)


def test_uncertainty_defect_uses_near_margin_effect(simulation_config) -> None:
    generated = generate_simulation(
        _scenario("decision_uncertainty", sample_size=30_000), simulation_config
    )
    flag = generated.defects["decision_uncertainty"].to_numpy(dtype=bool)

    assert flag.mean() == pytest.approx(0.30, abs=0.015)
    np.testing.assert_allclose(np.abs(generated.tau_target[flag]), 0.03)
    np.testing.assert_allclose(np.abs(generated.tau_target[~flag]), 0.08)


def test_combined_effect_priority_is_respected(simulation_config) -> None:
    generated = generate_simulation(
        _scenario("combined", sample_size=80_000), simulation_config
    )
    flags = generated.defects
    o = flags["reference_support"].to_numpy(dtype=bool)
    d = flags["record_adequacy"].to_numpy(dtype=bool) & ~o
    m = flags["model_multiplicity"].to_numpy(dtype=bool) & ~d & ~o
    u = flags["decision_uncertainty"].to_numpy(dtype=bool) & ~m & ~d & ~o

    assert all(mask.any() for mask in (o, d, m, u))
    np.testing.assert_allclose(generated.tau_target[o], -0.08)
    expected_d = np.where(generated.latent_covariates[d, 0] > -0.50, 0.08, -0.08)
    np.testing.assert_allclose(generated.tau_target[d], expected_d)
    expected_m = np.where(
        generated.complete_covariates[m, 0] * generated.complete_covariates[m, 1] > 0,
        0.10,
        -0.06,
    )
    np.testing.assert_allclose(generated.tau_target[m], expected_m)
    np.testing.assert_allclose(np.abs(generated.tau_target[u]), 0.03)


def test_group_concentrated_defect_preserves_overall_rate(simulation_config) -> None:
    generated = generate_simulation(
        _scenario(
            "record_adequacy",
            sample_size=80_000,
            group_prevalence=0.50,
            defect_allocation="group_concentrated",
        ),
        simulation_config,
    )
    group = generated.observed["group"].to_numpy()
    flag = generated.defects["record_adequacy"].to_numpy(dtype=bool)
    rate0 = flag[group == 0].mean()
    rate1 = flag[group == 1].mean()

    assert flag.mean() == pytest.approx(0.20, abs=0.01)
    assert rate1 / rate0 == pytest.approx(4.0, rel=0.12)


def test_clean_control_has_no_generated_defects(simulation_config) -> None:
    generated = generate_simulation(_scenario("clean_control"), simulation_config)

    assert not generated.defects.to_numpy().any()
    np.testing.assert_allclose(np.abs(generated.tau_target), 0.06)


def test_continuous_effect_is_four_times_binary_target(simulation_config) -> None:
    common = {
        "defect": "combined",
        "sample_size": 5_000,
        "scenario_id": "same-streams-for-scale-test",
        "replicate_id": 4,
    }
    binary = generate_simulation(
        SimulationScenario(**common, outcome_type="binary"), simulation_config
    )
    continuous = generate_simulation(
        SimulationScenario(**common, outcome_type="continuous"), simulation_config
    )

    np.testing.assert_array_equal(
        binary.complete_covariates, continuous.complete_covariates
    )
    pd.testing.assert_frame_equal(binary.defects, continuous.defects)
    np.testing.assert_allclose(continuous.tau_target, 4.0 * binary.tau_target)
    assert continuous.materially_actionable is None
