from __future__ import annotations

import inspect
from copy import deepcopy
from pathlib import Path

import numpy as np
import pytest

from evidence_defeat.config import load_project_config
from evidence_defeat.evaluation import (
    aipw_policy_contributions,
    aipw_treatment_values,
    evaluate_cross_fitted_policies,
    fit_outer_fold_policy_nuisance,
    select_population_default,
)
from evidence_defeat.pipeline import run_cross_fitted_construction
from evidence_defeat.preprocessing import CovariateSchema
from evidence_defeat.simulation import SimulationScenario, generate_simulation

PROJECT_ROOT = Path(__file__).resolve().parents[1]
pytestmark = [
    pytest.mark.filterwarnings(
        "ignore:Could not generate out-of-bag predictions.*:UserWarning"
    ),
    pytest.mark.filterwarnings("ignore:'penalty' was deprecated.*:FutureWarning"),
]


@pytest.fixture(scope="module")
def diagnostic_analysis() -> dict:
    """Reduce computation for software integration tests only."""

    analysis = deepcopy(load_project_config(PROJECT_ROOT).analysis)
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
    return analysis


@pytest.fixture(scope="module")
def integrated_evaluation(diagnostic_analysis: dict):
    project = load_project_config(PROJECT_ROOT)
    generated = generate_simulation(
        SimulationScenario(
            scenario_id="evaluation-record-check",
            sample_size=240,
            defect="record_adequacy",
            replicate_id=0,
        ),
        project.simulation,
    )
    schema = CovariateSchema(
        continuous=tuple(f"x{number}" for number in range(1, 11)),
        categorical=("group",),
    )
    frame = generated.observed
    covariates = frame.loc[:, list(schema.columns)]
    construction = run_cross_fitted_construction(
        covariates,
        frame["outcome"].to_numpy(),
        frame["treatment"].to_numpy(),
        frame["row_id"].to_numpy(),
        schema=schema,
        trial_id="simulation",
        run_id="evaluation-record-check-0",
        outcome_type="binary",
        analysis_config=diagnostic_analysis,
    )
    gate_before_evaluation = construction.gate.complete.copy()
    evaluation = evaluate_cross_fitted_policies(
        construction,
        covariates,
        frame["outcome"].to_numpy(),
        frame["treatment"].to_numpy(),
        frame["row_id"].to_numpy(),
        schema=schema,
        outcome_type="binary",
        analysis_config=diagnostic_analysis,
        documented_treatment_probability=0.5,
    )
    return generated, construction, evaluation, gate_before_evaluation


def test_aipw_recovers_constant_treatment_values_with_wrong_regression() -> None:
    treatment = np.tile([0, 1], 4)
    outcome = treatment.astype(float)
    wrong_mu0 = np.full(8, 0.5)
    wrong_mu1 = np.full(8, 0.5)

    value_0, value_1 = aipw_treatment_values(
        outcome,
        treatment,
        wrong_mu0,
        wrong_mu1,
        0.5,
    )

    assert value_0 == pytest.approx(0.0)
    assert value_1 == pytest.approx(1.0)


def test_policy_contribution_uses_only_outcomes_matching_the_policy() -> None:
    treatment = np.array([0, 1, 0, 1])
    outcome = treatment.astype(float)
    policy = np.array([0, 1, 1, 0])

    contributions = aipw_policy_contributions(
        policy,
        outcome,
        treatment,
        mu0=np.full(4, 0.5),
        mu1=np.full(4, 0.5),
        propensity_treatment_1=0.5,
    )

    np.testing.assert_allclose(contributions, [-0.5, 1.5, 0.5, 0.5])
    assert contributions.mean() == pytest.approx(0.5)


def test_population_default_requires_strict_material_advantage() -> None:
    assert select_population_default(0.0, 0.02, materiality_margin=0.02) == 0
    assert select_population_default(0.0, 0.020001, materiality_margin=0.02) == 1
    assert select_population_default(0.5, 0.4, materiality_margin=0.02) == 0


def test_default_constructor_cannot_receive_heldout_outcomes() -> None:
    parameters = inspect.signature(fit_outer_fold_policy_nuisance).parameters

    assert "heldout_outcome" not in parameters
    assert "heldout_utility" not in parameters
    assert "training_utility" in parameters


def test_integrated_evaluation_constructs_all_deterministic_policies(
    integrated_evaluation,
) -> None:
    _, construction, evaluation, gate_before = integrated_evaluation

    expected_names = {
        "population_default",
        "ungated_individualisation",
        "complete_gate",
        "uncertainty_only",
        *(f"single_{name}" for name in construction.gate.single_check),
        *construction.gate.leave_one_out,
    }
    assert set(evaluation.policies) == expected_names
    np.testing.assert_array_equal(construction.gate.complete, gate_before)
    np.testing.assert_array_equal(
        evaluation.policies["complete_gate"],
        np.where(
            construction.gate.complete,
            construction.individualised_action,
            evaluation.default_action,
        ),
    )
    np.testing.assert_array_equal(
        evaluation.policies["uncertainty_only"],
        np.where(
            construction.uncertainty_only_acceptance,
            construction.individualised_action,
            evaluation.default_action,
        ),
    )


def test_defaults_and_nuisance_predictions_are_outer_fold_specific(
    integrated_evaluation,
) -> None:
    _, _, evaluation, _ = integrated_evaluation

    assert np.isfinite(evaluation.mu0).all()
    assert np.isfinite(evaluation.mu1).all()
    assert np.isfinite(evaluation.scaled_utility).all()
    for fold in evaluation.folds:
        in_fold = evaluation.fold_ids == fold.fold_id
        assert np.unique(evaluation.default_action[in_fold]).tolist() == [
            fold.default_action
        ]
        np.testing.assert_allclose(
            evaluation.default_effect[in_fold],
            fold.default_effect,
        )
        np.testing.assert_allclose(evaluation.propensity_treatment_1[in_fold], 0.5)
        assert fold.propensity_source == "documented_randomisation_probability"
        assert fold.propensity_was_clipped is False


def test_policy_values_and_paired_contrast_are_finite(integrated_evaluation) -> None:
    _, _, evaluation, _ = integrated_evaluation

    for name, estimate in evaluation.estimates.items():
        assert estimate.policy_name == name
        assert np.isfinite(estimate.value)
        assert np.isfinite(estimate.conditional_standard_error)
        assert estimate.sample_size == 240

    contrast = evaluation.contrast("complete_gate", "population_default")
    expected_scores = (
        evaluation.contributions["complete_gate"]
        - evaluation.contributions["population_default"]
    )
    assert contrast.estimate == pytest.approx(expected_scores.mean())
    assert contrast.conditional_standard_error == pytest.approx(
        expected_scores.std(ddof=1) / np.sqrt(expected_scores.shape[0])
    )
    assert contrast.confidence_interval_lower <= contrast.estimate
    assert contrast.estimate <= contrast.confidence_interval_upper


def test_evaluation_rejects_treatment_mismatched_to_construction(
    integrated_evaluation,
    diagnostic_analysis: dict,
) -> None:
    generated, construction, _, _ = integrated_evaluation
    schema = construction.schema
    frame = generated.observed
    mismatched = frame["treatment"].to_numpy().copy()
    mismatched[0] = 1 - mismatched[0]

    with pytest.raises(ValueError, match="treatment does not match"):
        evaluate_cross_fitted_policies(
            construction,
            frame.loc[:, list(schema.columns)],
            frame["outcome"].to_numpy(),
            mismatched,
            frame["row_id"].to_numpy(),
            schema=schema,
            outcome_type="binary",
            analysis_config=diagnostic_analysis,
            documented_treatment_probability=0.5,
        )
