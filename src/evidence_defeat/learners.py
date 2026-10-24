"""Adapters for the three prespecified conditional-effect learners."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Literal

import numpy as np
from econml.dml import CausalForestDML
from econml.dr import DRLearner
from numpy.typing import ArrayLike, NDArray
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import LogisticRegression, Ridge

from evidence_defeat.seeds import derive_model_seed

OutcomeType = Literal["binary", "continuous"]
ESTIMATOR_ORDER = (
    "causal_forest_dml",
    "penalised_interaction",
    "boosted_dr_learner",
)


@dataclass(frozen=True)
class LearnerSeeds:
    """Separate deterministic random states for the three estimators."""

    causal_forest_dml: int
    penalised_interaction: int
    boosted_dr_learner: int

    @classmethod
    def derive(
        cls,
        master_seed: int,
        run_id: str,
        fold_id: int,
    ) -> LearnerSeeds:
        return cls(
            **{
                learner_id: derive_model_seed(
                    master_seed,
                    run_id,
                    fold_id,
                    learner_id,
                )
                for learner_id in ESTIMATOR_ORDER
            }
        )


@dataclass(frozen=True)
class TreatmentEffectPredictions:
    """Held-out effects on one common utility-difference scale."""

    primary_effect: NDArray[np.float64]
    primary_interval_lower: NDArray[np.float64]
    primary_interval_upper: NDArray[np.float64]
    interaction_effect: NDArray[np.float64]
    doubly_robust_effect: NDArray[np.float64]

    @property
    def effect_matrix(self) -> NDArray[np.float64]:
        """Return columns in the locked estimator order."""

        return np.column_stack(
            [
                self.primary_effect,
                self.interaction_effect,
                self.doubly_robust_effect,
            ]
        )


class CausalForestEffectLearner:
    """CausalForestDML adapter exposing effect and pointwise interval."""

    def __init__(self, model: CausalForestDML) -> None:
        self.model = model
        self._feature_count: int | None = None

    def fit(
        self,
        covariates: ArrayLike,
        outcome: ArrayLike,
        treatment: ArrayLike,
    ) -> CausalForestEffectLearner:
        x, y, a = _training_arrays(covariates, outcome, treatment)
        self.model.fit(y, a, X=x)
        self._feature_count = x.shape[1]
        return self

    def predict(
        self,
        covariates: ArrayLike,
        *,
        interval_alpha: float = 0.05,
    ) -> tuple[
        NDArray[np.float64],
        NDArray[np.float64],
        NDArray[np.float64],
    ]:
        x = _prediction_matrix(covariates, self._feature_count)
        if not 0.0 < interval_alpha < 1.0:
            raise ValueError("interval_alpha must lie strictly between zero and one")
        effect = self.predict_effect(x)
        lower_raw, upper_raw = self.model.effect_interval(x, alpha=interval_alpha)
        lower = _one_effect_per_row(
            "causal-forest lower interval", lower_raw, x.shape[0]
        )
        upper = _one_effect_per_row(
            "causal-forest upper interval", upper_raw, x.shape[0]
        )
        if np.any(lower > upper):
            raise RuntimeError("causal-forest interval bounds are reversed")
        return effect, lower, upper

    def predict_effect(self, covariates: ArrayLike) -> NDArray[np.float64]:
        """Return point effects without computing an inference interval."""

        x = _prediction_matrix(covariates, self._feature_count)
        return _one_effect_per_row(
            "causal-forest effect",
            self.model.effect(x),
            x.shape[0],
        )


class PenalisedInteractionEffectLearner:
    """Treatment-interaction model with effects on the mean/probability scale."""

    def __init__(
        self, model: LogisticRegression | Ridge, outcome_type: OutcomeType
    ) -> None:
        if outcome_type not in {"binary", "continuous"}:
            raise ValueError("outcome_type must be binary or continuous")
        self.model = model
        self.outcome_type = outcome_type
        self._feature_count: int | None = None

    def fit(
        self,
        covariates: ArrayLike,
        outcome: ArrayLike,
        treatment: ArrayLike,
    ) -> PenalisedInteractionEffectLearner:
        x, y, a = _training_arrays(covariates, outcome, treatment)
        if self.outcome_type == "binary" and not np.isin(y, (0.0, 1.0)).all():
            raise ValueError("binary outcome must contain only zero and one")
        self.model.fit(_interaction_design(x, a), y)
        self._feature_count = x.shape[1]
        return self

    def predict(self, covariates: ArrayLike) -> NDArray[np.float64]:
        x = _prediction_matrix(covariates, self._feature_count)
        treated = _interaction_design(x, np.ones(x.shape[0], dtype=np.int8))
        untreated = _interaction_design(x, np.zeros(x.shape[0], dtype=np.int8))
        if self.outcome_type == "binary":
            treated_mean = self.model.predict_proba(treated)[:, 1]
            untreated_mean = self.model.predict_proba(untreated)[:, 1]
        else:
            treated_mean = self.model.predict(treated)
            untreated_mean = self.model.predict(untreated)
        effect = np.asarray(treated_mean - untreated_mean, dtype=float)
        return _one_effect_per_row("interaction-model effect", effect, x.shape[0])


class DoublyRobustEffectLearner:
    """DRLearner adapter exposing held-out conditional effects."""

    def __init__(self, model: DRLearner) -> None:
        self.model = model
        self._feature_count: int | None = None

    def fit(
        self,
        covariates: ArrayLike,
        outcome: ArrayLike,
        treatment: ArrayLike,
    ) -> DoublyRobustEffectLearner:
        x, y, a = _training_arrays(covariates, outcome, treatment)
        self.model.fit(y, a, X=x)
        self._feature_count = x.shape[1]
        return self

    def predict(self, covariates: ArrayLike) -> NDArray[np.float64]:
        x = _prediction_matrix(covariates, self._feature_count)
        return _one_effect_per_row(
            "doubly robust effect",
            self.model.effect(x),
            x.shape[0],
        )


def build_causal_forest(
    analysis_config: dict[str, Any],
    random_state: int,
) -> CausalForestEffectLearner:
    """Build the primary learner from the locked configuration."""

    primary = analysis_config["learners"]["primary"]
    _expect(primary, "class", "econml.dml.CausalForestDML")
    parameters = _seeded_parameters(primary["parameters"], random_state)
    model = CausalForestDML(
        model_y=build_outcome_regression(analysis_config, random_state),
        model_t=DummyClassifier(**primary["treatment_model"]["parameters"]),
        **parameters,
    )
    return CausalForestEffectLearner(model)


def build_interaction_learner(
    analysis_config: dict[str, Any],
    random_state: int,
    outcome_type: OutcomeType,
) -> PenalisedInteractionEffectLearner:
    """Build the prespecified logistic or ridge interaction learner."""

    interaction = analysis_config["learners"]["interaction_model"]
    if outcome_type == "binary":
        specification = interaction["binary_outcome"]
        _expect(specification, "class", "sklearn.linear_model.LogisticRegression")
        _expect(specification, "effect_scale", "predicted_probability_difference")
        model: LogisticRegression | Ridge = LogisticRegression(
            **_seeded_parameters(specification["parameters"], random_state)
        )
    elif outcome_type == "continuous":
        specification = interaction["continuous_outcome"]
        _expect(specification, "class", "sklearn.linear_model.Ridge")
        _expect(specification, "effect_scale", "predicted_mean_difference")
        model = Ridge(**_seeded_parameters(specification["parameters"], random_state))
    else:
        raise ValueError("outcome_type must be binary or continuous")
    return PenalisedInteractionEffectLearner(model, outcome_type)


def build_doubly_robust(
    analysis_config: dict[str, Any],
    random_state: int,
) -> DoublyRobustEffectLearner:
    """Build the boosted-regression DR learner from locked configuration."""

    specification = analysis_config["learners"]["doubly_robust"]
    _expect(specification, "class", "econml.dr.DRLearner")
    final_specification = specification["final_model"]
    _expect(
        final_specification,
        "class",
        "sklearn.ensemble.RandomForestRegressor",
    )
    model = DRLearner(
        model_propensity=DummyClassifier(
            **specification["propensity_model"]["parameters"]
        ),
        model_regression=build_outcome_regression(analysis_config, random_state),
        model_final=RandomForestRegressor(
            **_seeded_parameters(final_specification["parameters"], random_state)
        ),
        **_seeded_parameters(specification["parameters"], random_state),
    )
    return DoublyRobustEffectLearner(model)


def fit_predict_prespecified_learners(
    training_covariates: ArrayLike,
    training_outcome: ArrayLike,
    training_treatment: ArrayLike,
    heldout_covariates: ArrayLike,
    *,
    analysis_config: dict[str, Any],
    seeds: LearnerSeeds,
    outcome_type: OutcomeType,
    interval_alpha: float | None = None,
) -> TreatmentEffectPredictions:
    """Fit on one outer-training fold and predict on its held-out fold.

    For continuous outcomes, callers must first orient and standardise the
    outcome using that outer training fold. Held-out outcomes are deliberately
    not accepted by this function.
    """

    x_train, y_train, a_train = _training_arrays(
        training_covariates,
        training_outcome,
        training_treatment,
    )
    x_heldout = _prediction_matrix(heldout_covariates, x_train.shape[1])
    if outcome_type == "binary" and not np.isin(y_train, (0.0, 1.0)).all():
        raise ValueError("binary outcome must contain only zero and one")
    if outcome_type not in {"binary", "continuous"}:
        raise ValueError("outcome_type must be binary or continuous")
    if interval_alpha is None:
        interval_alpha = float(
            analysis_config["learners"]["primary"]["interval_alpha_primary"]
        )

    primary = build_causal_forest(
        analysis_config,
        seeds.causal_forest_dml,
    ).fit(x_train, y_train, a_train)
    interaction = build_interaction_learner(
        analysis_config,
        seeds.penalised_interaction,
        outcome_type,
    ).fit(x_train, y_train, a_train)
    doubly_robust = build_doubly_robust(
        analysis_config,
        seeds.boosted_dr_learner,
    ).fit(x_train, y_train, a_train)

    primary_effect, lower, upper = primary.predict(
        x_heldout,
        interval_alpha=interval_alpha,
    )
    result = TreatmentEffectPredictions(
        primary_effect=primary_effect,
        primary_interval_lower=lower,
        primary_interval_upper=upper,
        interaction_effect=interaction.predict(x_heldout),
        doubly_robust_effect=doubly_robust.predict(x_heldout),
    )
    if not np.isfinite(result.effect_matrix).all():
        raise RuntimeError("at least one learner returned a non-finite effect")
    return result


def fit_predict_effect_learner(
    learner_id: str,
    training_covariates: ArrayLike,
    training_outcome: ArrayLike,
    training_treatment: ArrayLike,
    prediction_covariates: ArrayLike,
    *,
    analysis_config: dict[str, Any],
    random_state: int,
    outcome_type: OutcomeType,
) -> NDArray[np.float64]:
    """Fit one prespecified learner and return point effects only.

    This is used by the policy-disagreement comparator, which needs many
    candidate policies but does not use candidate-specific confidence
    intervals.
    """

    x_train, y_train, a_train = _training_arrays(
        training_covariates,
        training_outcome,
        training_treatment,
    )
    x_prediction = _prediction_matrix(prediction_covariates, x_train.shape[1])
    if outcome_type == "binary" and not np.isin(y_train, (0.0, 1.0)).all():
        raise ValueError("binary outcome must contain only zero and one")
    if outcome_type not in {"binary", "continuous"}:
        raise ValueError("outcome_type must be binary or continuous")

    if learner_id == "causal_forest_dml":
        learner = build_causal_forest(analysis_config, random_state).fit(
            x_train,
            y_train,
            a_train,
        )
        return learner.predict_effect(x_prediction)
    if learner_id == "penalised_interaction":
        learner = build_interaction_learner(
            analysis_config,
            random_state,
            outcome_type,
        ).fit(x_train, y_train, a_train)
        return learner.predict(x_prediction)
    if learner_id == "boosted_dr_learner":
        learner = build_doubly_robust(analysis_config, random_state).fit(
            x_train,
            y_train,
            a_train,
        )
        return learner.predict(x_prediction)
    raise ValueError(f"unknown learner_id: {learner_id}")


def build_outcome_regression(
    analysis_config: dict[str, Any],
    random_state: int,
) -> HistGradientBoostingRegressor:
    """Build the shared prespecified nuisance outcome regressor."""

    specification = analysis_config["nuisance_outcome_model"]
    _expect(
        specification,
        "class",
        "sklearn.ensemble.HistGradientBoostingRegressor",
    )
    return HistGradientBoostingRegressor(
        **_seeded_parameters(specification["parameters"], random_state)
    )


def _seeded_parameters(parameters: dict[str, Any], random_state: int) -> dict[str, Any]:
    if not isinstance(random_state, int) or isinstance(random_state, bool):
        raise TypeError("random_state must be an integer")
    if not 0 <= random_state < 2**32:
        raise ValueError("random_state must be a uint32 value")
    result = deepcopy(parameters)
    if result.get("random_state") == "derived_from_master_seed":
        result["random_state"] = random_state
    return result


def _expect(mapping: dict[str, Any], key: str, expected: Any) -> None:
    if mapping.get(key) != expected:
        raise ValueError(f"expected {key}={expected!r}, found {mapping.get(key)!r}")


def _training_arrays(
    covariates: ArrayLike,
    outcome: ArrayLike,
    treatment: ArrayLike,
) -> tuple[NDArray[np.float64], NDArray[np.float64], NDArray[np.int8]]:
    x = _finite_matrix("covariates", covariates)
    y = _finite_vector("outcome", outcome)
    a_raw = np.asarray(treatment)
    if a_raw.ndim != 1:
        raise ValueError("treatment must be one-dimensional")
    if x.shape[0] != y.shape[0] or x.shape[0] != a_raw.shape[0]:
        raise ValueError("training arrays must have equal row counts")
    if not np.isin(a_raw, (0, 1)).all():
        raise ValueError("treatment must contain only zero and one")
    a = a_raw.astype(np.int8, copy=False)
    if np.unique(a).shape[0] != 2:
        raise ValueError("both treatment arms must be present")
    return x, y, a


def _prediction_matrix(
    covariates: ArrayLike,
    expected_features: int | None,
) -> NDArray[np.float64]:
    if expected_features is None:
        raise RuntimeError("learner must be fitted before prediction")
    x = _finite_matrix("covariates", covariates)
    if x.shape[1] != expected_features:
        raise ValueError("prediction covariates have the wrong number of columns")
    return x


def _finite_matrix(name: str, values: ArrayLike) -> NDArray[np.float64]:
    array = np.asarray(values, dtype=float)
    if array.ndim != 2 or array.shape[0] < 1 or array.shape[1] < 1:
        raise ValueError(f"{name} must be a non-empty two-dimensional array")
    if not np.isfinite(array).all():
        raise ValueError(f"{name} must contain only finite values")
    return array


def _finite_vector(name: str, values: ArrayLike) -> NDArray[np.float64]:
    array = np.asarray(values, dtype=float)
    if array.ndim != 1 or array.shape[0] < 1:
        raise ValueError(f"{name} must be a non-empty one-dimensional array")
    if not np.isfinite(array).all():
        raise ValueError(f"{name} must contain only finite values")
    return array


def _interaction_design(
    covariates: NDArray[np.float64],
    treatment: NDArray[np.int8],
) -> NDArray[np.float64]:
    treatment_column = treatment.astype(float)[:, None]
    return np.column_stack(
        [covariates, treatment_column, covariates * treatment_column]
    )


def _one_effect_per_row(
    name: str,
    values: ArrayLike,
    expected_rows: int,
) -> NDArray[np.float64]:
    array = np.asarray(values, dtype=float).squeeze()
    if array.ndim == 0 and expected_rows == 1:
        array = array.reshape(1)
    if array.ndim != 1 or array.shape[0] != expected_rows:
        raise RuntimeError(f"{name} did not return one value per row")
    if not np.isfinite(array).all():
        raise RuntimeError(f"{name} returned non-finite values")
    return array
