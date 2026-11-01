"""Known-truth controlled simulation specified in protocol version 0.1."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Literal

import numpy as np
import pandas as pd
from numpy.typing import NDArray
from scipy.special import expit
from scipy.stats import norm

from evidence_defeat.seeds import derive_replicate_seed, named_generators

OutcomeType = Literal["binary", "continuous"]
BaselineShape = Literal["linear", "nonlinear"]
EffectStrength = Literal["absent", "moderate", "strong"]
DefectAllocation = Literal["equal", "group_concentrated"]
DefectType = Literal[
    "none",
    "clean_control",
    "record_adequacy",
    "reference_support",
    "model_multiplicity",
    "decision_uncertainty",
    "combined",
]

DEFECT_COLUMNS = (
    "record_adequacy",
    "reference_support",
    "model_multiplicity",
    "decision_uncertainty",
)

ALLOWED_OUTCOME_TYPES = {"binary", "continuous"}
ALLOWED_BASELINE_SHAPES = {"linear", "nonlinear"}
ALLOWED_EFFECT_STRENGTHS = {"absent", "moderate", "strong"}
ALLOWED_DEFECT_ALLOCATIONS = {"equal", "group_concentrated"}
ALLOWED_DEFECT_TYPES = {
    "none",
    "clean_control",
    "record_adequacy",
    "reference_support",
    "model_multiplicity",
    "decision_uncertainty",
    "combined",
}


@dataclass(frozen=True)
class SimulationScenario:
    """One fully identified scenario and replicate."""

    scenario_id: str
    sample_size: int
    defect: DefectType
    replicate_id: int
    outcome_type: OutcomeType = "binary"
    baseline_shape: BaselineShape = "nonlinear"
    effect_strength: EffectStrength = "moderate"
    group_prevalence: float = 0.20
    defect_allocation: DefectAllocation = "equal"
    group_prognostic_coefficient: float = 0.0

    def __post_init__(self) -> None:
        if not self.scenario_id:
            raise ValueError("scenario_id must not be empty")
        if self.sample_size < 1:
            raise ValueError("sample_size must be positive")
        if self.replicate_id < 0:
            raise ValueError("replicate_id must be non-negative")
        if not 0.0 < self.group_prevalence < 1.0:
            raise ValueError("group_prevalence must lie strictly between zero and one")
        _validate_choice("defect", self.defect, ALLOWED_DEFECT_TYPES)
        _validate_choice("outcome_type", self.outcome_type, ALLOWED_OUTCOME_TYPES)
        _validate_choice("baseline_shape", self.baseline_shape, ALLOWED_BASELINE_SHAPES)
        _validate_choice(
            "effect_strength", self.effect_strength, ALLOWED_EFFECT_STRENGTHS
        )
        _validate_choice(
            "defect_allocation",
            self.defect_allocation,
            ALLOWED_DEFECT_ALLOCATIONS,
        )


def _validate_choice(name: str, value: str, allowed: set[str]) -> None:
    if value not in allowed:
        choices = ", ".join(sorted(allowed))
        raise ValueError(f"{name} must be one of: {choices}")


@dataclass(frozen=True)
class SimulationData:
    """Observed data, latent truth and generated defect labels."""

    scenario: SimulationScenario
    seed: int
    observed: pd.DataFrame
    latent_covariates: NDArray[np.float64]
    complete_covariates: NDArray[np.float64]
    defects: pd.DataFrame
    record_completeness: NDArray[np.float64]
    mu0: NDArray[np.float64]
    mu1: NDArray[np.float64]
    tau_target: NDArray[np.float64]
    tau_true: NDArray[np.float64]
    optimal_action: NDArray[np.int8]
    materially_actionable: NDArray[np.bool_] | None


def generate_simulation(
    scenario: SimulationScenario,
    simulation_config: dict[str, Any],
) -> SimulationData:
    """Generate one replicate without fitting or evaluating any policy."""

    master_seed = int(simulation_config["reproducibility"]["master_seed"])
    seed = derive_replicate_seed(
        master_seed, scenario.scenario_id, scenario.replicate_id
    )
    streams = named_generators(seed)
    n = scenario.sample_size

    group = (
        streams["group"].binomial(1, scenario.group_prevalence, size=n).astype(np.int8)
    )
    latent = streams["covariates"].normal(size=(n, 10)).astype(float)
    defects = _generate_defects(
        scenario, simulation_config, latent, group, streams["defect_flags"]
    )

    complete = latent.copy()
    support_flag = defects["reference_support"].to_numpy(dtype=bool)
    complete[support_flag, :3] += 4.0

    eta = _baseline_predictor(complete, scenario.baseline_shape)
    eta = eta + scenario.group_prognostic_coefficient * group
    tau_binary = _binary_effect_surface(scenario, complete, latent, defects)
    tau_target = tau_binary if scenario.outcome_type == "binary" else 4.0 * tau_binary

    if scenario.outcome_type == "binary":
        mu0 = 0.10 + 0.70 * expit(eta)
        mu1 = np.clip(mu0 + tau_target, 0.01, 0.99)
    elif scenario.outcome_type == "continuous":
        mu0 = 0.50 * eta
        mu1 = mu0 + tau_target
    else:  # pragma: no cover - Literal and dataclass validation guard this path
        raise ValueError(f"Unsupported outcome type: {scenario.outcome_type}")

    tau_true = mu1 - mu0
    treatment = streams["treatment"].binomial(1, 0.5, size=n).astype(np.int8)
    observed_mean = np.where(treatment == 1, mu1, mu0)
    if scenario.outcome_type == "binary":
        outcome = streams["outcome"].binomial(1, observed_mean, size=n).astype(np.int8)
        delta = float(simulation_config["materiality"]["binary_utility_delta"])
        materially_actionable: NDArray[np.bool_] | None = np.abs(tau_true) >= delta
    else:
        outcome = observed_mean + streams["outcome"].normal(size=n)
        materially_actionable = None

    observed_x = complete.copy()
    record_flag = defects["record_adequacy"].to_numpy(dtype=bool)
    observed_x[record_flag, :3] = np.nan
    record_completeness = np.mean(~np.isnan(observed_x), axis=1)

    frame = pd.DataFrame(observed_x, columns=[f"x{j}" for j in range(1, 11)])
    frame.insert(0, "row_id", np.arange(n, dtype=np.int64))
    frame["group"] = group
    frame["treatment"] = treatment
    frame["outcome"] = outcome

    return SimulationData(
        scenario=scenario,
        seed=seed,
        observed=frame,
        latent_covariates=latent,
        complete_covariates=complete,
        defects=defects,
        record_completeness=record_completeness,
        mu0=mu0,
        mu1=mu1,
        tau_target=tau_target,
        tau_true=tau_true,
        optimal_action=(tau_true > 0.0).astype(np.int8),
        materially_actionable=materially_actionable,
    )


def _baseline_predictor(
    x: NDArray[np.float64], shape: BaselineShape
) -> NDArray[np.float64]:
    if shape == "linear":
        return -0.40 + 0.45 * x[:, 0] - 0.35 * x[:, 1] + 0.25 * x[:, 2] + 0.20 * x[:, 3]
    if shape == "nonlinear":
        return (
            -0.40
            + 0.55 * np.sin(x[:, 0])
            + 0.35 * (x[:, 1] ** 2 - 1.0) / math.sqrt(2.0)
            - 0.40 * x[:, 2] * x[:, 3]
            + 0.25 * (x[:, 4] > 0.0)
        )
    raise ValueError(f"Unsupported baseline shape: {shape}")


def _base_binary_effect(
    x: NDArray[np.float64], strength: EffectStrength
) -> NDArray[np.float64]:
    if strength == "absent":
        return np.full(x.shape[0], 0.04)
    if strength == "moderate":
        h_linear = (x[:, 0] + x[:, 1]) / math.sqrt(2.0)
        return np.clip(0.01 + 0.05 * h_linear, -0.12, 0.12)
    if strength == "strong":
        denominator = math.sqrt((1.0 - math.exp(-2.0)) / 2.0 + 0.25 + 0.25)
        h_nonlinear = (
            np.sin(x[:, 0])
            + 0.5 * (x[:, 1] ** 2 - 1.0) / math.sqrt(2.0)
            + 0.5 * x[:, 2] * x[:, 3]
        ) / denominator
        return np.clip(0.01 + 0.09 * h_nonlinear, -0.18, 0.18)
    raise ValueError(f"Unsupported effect strength: {strength}")


def _binary_effect_surface(
    scenario: SimulationScenario,
    complete: NDArray[np.float64],
    latent: NDArray[np.float64],
    defects: pd.DataFrame,
) -> NDArray[np.float64]:
    if scenario.defect == "clean_control":
        return np.where(complete[:, 0] >= 0.0, 0.06, -0.06)

    tau = _base_binary_effect(complete, scenario.effect_strength)
    d = defects["record_adequacy"].to_numpy(dtype=bool)
    o = defects["reference_support"].to_numpy(dtype=bool)
    m = defects["model_multiplicity"].to_numpy(dtype=bool)
    u = defects["decision_uncertainty"].to_numpy(dtype=bool)

    if scenario.defect == "decision_uncertainty":
        tau = np.where(complete[:, 0] >= 0.0, 0.08, -0.08)
        tau[u] = np.where(complete[u, 0] >= 0.0, 0.03, -0.03)
        return tau

    if scenario.defect in {"model_multiplicity", "combined"}:
        tau[m] = np.where(complete[m, 0] * complete[m, 1] > 0.0, 0.10, -0.06)
    if scenario.defect in {"record_adequacy", "combined"}:
        tau[d] = np.where(latent[d, 0] > -0.50, 0.08, -0.08)
    if scenario.defect in {"reference_support", "combined"}:
        tau[o] = -0.08
    if scenario.defect == "combined":
        lower_priority = u & ~m & ~d & ~o
        tau[lower_priority] = np.where(
            complete[lower_priority, 0] >= 0.0,
            0.03,
            -0.03,
        )
    return tau


def _generate_defects(
    scenario: SimulationScenario,
    simulation_config: dict[str, Any],
    x: NDArray[np.float64],
    group: NDArray[np.int8],
    rng: np.random.Generator,
) -> pd.DataFrame:
    flags = {
        name: np.zeros(scenario.sample_size, dtype=bool) for name in DEFECT_COLUMNS
    }
    if scenario.defect in {"none", "clean_control"}:
        return pd.DataFrame(flags)

    if scenario.defect == "combined":
        rates = simulation_config["combined_defects"]["prevalence"]
        active = set(DEFECT_COLUMNS)
    else:
        rates = {
            scenario.defect: simulation_config["single_defects"][scenario.defect][
                "overall_prevalence"
            ]
        }
        active = {scenario.defect}

    if "record_adequacy" in active:
        p0, p1 = _group_probabilities(
            float(rates["record_adequacy"]), scenario, simulation_config
        )
        flags["record_adequacy"] = rng.random(scenario.sample_size) < np.where(
            group == 1, p1, p0
        )
    if "reference_support" in active:
        p0, p1 = _group_probabilities(
            float(rates["reference_support"]), scenario, simulation_config
        )
        flags["reference_support"] = rng.random(scenario.sample_size) < np.where(
            group == 1, p1, p0
        )
    if "model_multiplicity" in active:
        p0, p1 = _group_probabilities(
            float(rates["model_multiplicity"]), scenario, simulation_config
        )
        threshold = np.where(group == 1, norm.ppf(1.0 - p1), norm.ppf(1.0 - p0))
        flags["model_multiplicity"] = x[:, 4] > threshold
    if "decision_uncertainty" in active:
        p0, p1 = _group_probabilities(
            float(rates["decision_uncertainty"]), scenario, simulation_config
        )
        threshold = np.where(
            group == 1,
            norm.ppf((1.0 + p1) / 2.0),
            norm.ppf((1.0 + p0) / 2.0),
        )
        flags["decision_uncertainty"] = np.abs(x[:, 5]) <= threshold
    return pd.DataFrame(flags)


def _group_probabilities(
    overall: float,
    scenario: SimulationScenario,
    simulation_config: dict[str, Any],
) -> tuple[float, float]:
    if scenario.defect_allocation == "equal":
        return overall, overall
    ratio = float(
        simulation_config["defect_allocation"]["group_concentrated"][
            "concentration_ratio"
        ]
    )
    q = scenario.group_prevalence
    p0 = overall / ((1.0 - q) + ratio * q)
    p1 = ratio * p0
    if not 0.0 <= p0 <= 1.0 or not 0.0 <= p1 <= 1.0:
        raise ValueError(
            "Requested group concentration produces an invalid probability"
        )
    return p0, p1
