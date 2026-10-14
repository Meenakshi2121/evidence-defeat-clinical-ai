from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import numpy as np
import pytest
from scipy.special import expit

from evidence_defeat.config import load_project_config
from evidence_defeat.learners import (
    ESTIMATOR_ORDER,
    LearnerSeeds,
    build_causal_forest,
    build_doubly_robust,
    build_interaction_learner,
    fit_predict_prespecified_learners,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
pytestmark = [
    pytest.mark.filterwarnings(
        "ignore:Could not generate out-of-bag predictions.*:UserWarning"
    ),
    pytest.mark.filterwarnings("ignore:'penalty' was deprecated.*:FutureWarning"),
]


@pytest.fixture(scope="module")
def diagnostic_config() -> dict:
    """Reduced computation for software tests; never used for scientific runs."""

    analysis = deepcopy(load_project_config(PROJECT_ROOT).analysis)
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


def _binary_data(seed: int = 91) -> tuple[np.ndarray, ...]:
    rng = np.random.default_rng(seed)
    x = rng.normal(size=(300, 5))
    treatment = rng.binomial(1, 0.5, size=300)
    probability = expit(-0.30 + 0.35 * x[:, 0] + treatment * (0.80 + 0.30 * x[:, 1]))
    outcome = rng.binomial(1, probability)
    return x[:240], outcome[:240], treatment[:240], x[240:]


def test_learner_seeds_are_separate_and_reproducible() -> None:
    first = LearnerSeeds.derive(20261013, "simulation-0", 2)
    second = LearnerSeeds.derive(20261013, "simulation-0", 2)

    assert first == second
    assert len(set(first.__dict__.values())) == len(ESTIMATOR_ORDER)


def test_factories_read_locked_estimator_classes_and_parameters() -> None:
    analysis = load_project_config(PROJECT_ROOT).analysis
    seeds = LearnerSeeds.derive(20261013, "factory-test", 0)

    forest = build_causal_forest(analysis, seeds.causal_forest_dml)
    interaction = build_interaction_learner(
        analysis,
        seeds.penalised_interaction,
        "binary",
    )
    doubly_robust = build_doubly_robust(analysis, seeds.boosted_dr_learner)

    assert forest.model.n_estimators == 1000
    assert forest.model.subforest_size == 4
    assert interaction.model.C == 1.0
    assert doubly_robust.model.min_propensity == 0.05


def test_all_learners_return_one_finite_effect_per_heldout_row(
    diagnostic_config: dict,
) -> None:
    x_train, y_train, a_train, x_heldout = _binary_data()
    seeds = LearnerSeeds.derive(20261013, "binary-smoke", 0)

    predictions = fit_predict_prespecified_learners(
        x_train,
        y_train,
        a_train,
        x_heldout,
        analysis_config=diagnostic_config,
        seeds=seeds,
        outcome_type="binary",
        interval_alpha=0.05,
    )

    assert predictions.effect_matrix.shape == (60, 3)
    assert np.isfinite(predictions.effect_matrix).all()
    assert np.isfinite(predictions.primary_interval_lower).all()
    assert np.isfinite(predictions.primary_interval_upper).all()
    assert np.all(
        predictions.primary_interval_lower <= predictions.primary_interval_upper
    )
    assert np.all(np.abs(predictions.interaction_effect) <= 1.0)
    np.testing.assert_array_equal(
        predictions.effect_matrix[:, 0],
        predictions.primary_effect,
    )


def test_same_seeds_reproduce_all_heldout_predictions(
    diagnostic_config: dict,
) -> None:
    x_train, y_train, a_train, x_heldout = _binary_data(seed=123)
    seeds = LearnerSeeds.derive(20261013, "reproducibility-smoke", 1)

    first = fit_predict_prespecified_learners(
        x_train,
        y_train,
        a_train,
        x_heldout[:15],
        analysis_config=diagnostic_config,
        seeds=seeds,
        outcome_type="binary",
    )
    second = fit_predict_prespecified_learners(
        x_train,
        y_train,
        a_train,
        x_heldout[:15],
        analysis_config=diagnostic_config,
        seeds=seeds,
        outcome_type="binary",
    )

    np.testing.assert_allclose(first.effect_matrix, second.effect_matrix, atol=0.0)
    np.testing.assert_allclose(
        first.primary_interval_lower,
        second.primary_interval_lower,
        atol=0.0,
    )
    np.testing.assert_allclose(
        first.primary_interval_upper,
        second.primary_interval_upper,
        atol=0.0,
    )


def test_continuous_interaction_effect_is_predicted_mean_difference(
    diagnostic_config: dict,
) -> None:
    rng = np.random.default_rng(31337)
    x = rng.normal(size=(500, 4))
    treatment = rng.binomial(1, 0.5, size=500)
    true_effect = 0.50 + 0.30 * x[:, 1]
    outcome = 0.20 * x[:, 0] + treatment * true_effect
    learner = build_interaction_learner(
        diagnostic_config,
        random_state=17,
        outcome_type="continuous",
    ).fit(x, outcome, treatment)

    predicted = learner.predict(x)

    assert np.corrcoef(predicted, true_effect)[0, 1] > 0.99
    assert np.mean(np.abs(predicted - true_effect)) < 0.02


def test_binary_pipeline_rejects_nonbinary_outcome(diagnostic_config: dict) -> None:
    x_train, y_train, a_train, x_heldout = _binary_data()
    y_train = y_train.astype(float)
    y_train[0] = 0.5

    with pytest.raises(ValueError, match="binary outcome"):
        fit_predict_prespecified_learners(
            x_train,
            y_train,
            a_train,
            x_heldout,
            analysis_config=diagnostic_config,
            seeds=LearnerSeeds.derive(20261013, "invalid-outcome", 0),
            outcome_type="binary",
        )
