"""Blinded Stage E variance pilot for the frozen C002 validation protocol."""

from __future__ import annotations

import hashlib
import math
import os
import platform
import re
import sys
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

from evidence_defeat.config import (
    DevelopmentConfig,
    ProjectConfig,
    candidate_analysis_config,
    load_yaml,
)
from evidence_defeat.diagnostics import (
    InvariantResult,
    ResourceUsage,
    array_sha256,
    canonical_sha256,
    package_versions,
    process_peak_rss_mb,
    simulation_data_sha256,
)
from evidence_defeat.evaluation import evaluate_cross_fitted_policies
from evidence_defeat.known_truth import evaluate_cross_fitted_known_truth
from evidence_defeat.pipeline import run_cross_fitted_construction
from evidence_defeat.preprocessing import CovariateSchema
from evidence_defeat.simulation import SimulationScenario, generate_simulation

_COMMIT_PATTERN = re.compile(r"^[0-9a-f]{40}(?:[0-9a-f]{24})?$")
_PRIMARY_DEFECTS = (
    "record_adequacy",
    "reference_support",
    "model_multiplicity",
    "decision_uncertainty",
    "combined",
)
_PRIMARY_SAMPLE_SIZES = (500, 2000)
_ESSENTIAL_CHECKS = (
    "record_adequacy",
    "reference_support",
    "model_multiplicity",
)
_DECLARED_ESSENTIAL_CHECKS = (
    "record_adequacy",
    "reference_population_support",
    "estimator_action_agreement",
)


@dataclass(frozen=True)
class ValidationConfig:
    """Frozen protocol-v1.0 validation mapping."""

    document: dict[str, Any]


@dataclass(frozen=True)
class PilotScenarioSpec:
    """One Stage E scenario containing its complete blinded replicate set."""

    scenario_id: str
    defect: str
    sample_size: int
    replicate_ids: tuple[int, ...]


@dataclass(frozen=True)
class _PilotReplicateResult:
    contrast: float
    generated_data_sha256: str
    fold_assignments_sha256: str
    invariants: tuple[InvariantResult, ...]


def load_validation_config(
    root: str | Path,
    *,
    project: ProjectConfig,
    development: DevelopmentConfig,
) -> ValidationConfig:
    """Load and validate the Stage D frozen validation specification."""

    document = load_yaml(Path(root) / "config" / "validation.yaml")
    config = ValidationConfig(document=document)
    validate_validation_config(project, development, config)
    return config


def validate_validation_config(
    project: ProjectConfig,
    development: DevelopmentConfig,
    config: ValidationConfig,
) -> None:
    """Reject any change to the frozen candidate or Stage E disclosure boundary."""

    document = config.document
    if _need(document, "schema_version") != "1.0":
        raise ValueError("validation schema version must remain 1.0")
    if _need(document, "status") != "frozen_on_protocol_v1_0_tag":
        raise ValueError("validation configuration is not frozen")

    freeze = _need(document, "freeze")
    if _need(freeze, "candidate_id") != "C002":
        raise ValueError("C002 must remain the frozen candidate")
    if _need(freeze, "protocol_tag") != "protocol-v1.0":
        raise ValueError("the frozen protocol tag has changed")
    if _need(freeze, "no_result_contingent_changes") is not True:
        raise ValueError("result-contingent changes must remain prohibited")

    actual_hashes = validation_configuration_hashes(project, development, config)
    frozen_hashes = _need(freeze, "configuration_sha256")
    for key in ("analysis", "candidate_effective_analysis", "simulation"):
        if _need(frozen_hashes, key) != actual_hashes[key]:
            raise ValueError(f"frozen configuration hash changed: {key}")

    analysis = candidate_analysis_config(project, development, "C002")
    uncertainty = _need(analysis, "gate", "uncertainty")
    graded = _need(uncertainty, "graded_filter")
    if _need(uncertainty, "essential") is not False:
        raise ValueError("C002 must use three essential evidence checks")
    if _need(graded, "enabled") is not True:
        raise ValueError("C002 graded uncertainty must remain enabled")
    if not math.isclose(float(_need(graded, "retention_fraction")), 0.80):
        raise ValueError("C002 retention fraction must remain 0.80")

    rule = _need(document, "candidate_rule")
    if tuple(_need(rule, "essential_checks")) != _DECLARED_ESSENTIAL_CHECKS:
        raise ValueError("C002 essential checks have changed")
    if _need(rule, "failed_essential_check_can_be_rescued") is not False:
        raise ValueError("a failed essential check cannot be rescued")
    if _need(rule, "deferral_means_treatment_delay") is not False:
        raise ValueError("deferral cannot be defined as treatment delay")

    estimand = _need(document, "primary_estimand")
    expected_estimand = {
        "metric": "material_unsafe_acceptance_population_denominator",
        "contrast": "C002_minus_uncertainty_only_at_exact_matched_coverage",
        "scenario_weighting": "equal_weight_per_scenario",
        "support_rule": "upper_confidence_limit_below_zero",
        "interpretation": "negative_values_favour_C002",
    }
    for key, expected in expected_estimand.items():
        if _need(estimand, key) != expected:
            raise ValueError(f"primary estimand changed: {key}")

    guardrails = _need(document, "guardrails")
    if not math.isclose(float(_need(guardrails, "mean_coverage_floor")), 0.25):
        raise ValueError("the validation coverage floor has changed")
    if _need(guardrails, "weighted_fairness_composite") is not False:
        raise ValueError("weighted fairness cannot enter validation")

    pilot = _need(document, "stage_e_blinded_variance_pilot")
    bounds = _need(pilot, "replicate_ids")
    if bounds != [100000, 100024]:
        raise ValueError("Stage E replicate namespace has changed")
    if _need(pilot, "replicates_per_scenario") != 25:
        raise ValueError("Stage E must retain 25 replicates per scenario")
    if _need(pilot, "permitted_outputs") != [
        "paired_primary_contrast_standard_deviation",
        "runtime",
        "memory",
    ]:
        raise ValueError("Stage E permitted outputs have changed")
    if _need(pilot, "prohibited_outputs") != [
        "mean_effect_estimates",
        "method_rankings",
        "group_differences",
    ]:
        raise ValueError("Stage E prohibited outputs have changed")
    if _need(pilot, "scientific_method_changes_allowed") is not False:
        raise ValueError("Stage E cannot alter the scientific method")

    completion = _need(document, "stage_e_completion")
    expected_completion = {
        "status": "complete_blinded_variance_only",
        "completed_date": "2026-10-24",
        "pilot_code_commit": "525788bd24428a684ecc1941c7441e5ee60e9a72",
        "pilot_code_tag": "stage-e-pilot-code-v1.0",
        "pilot_configuration_combined_sha256": (
            "fc46b71a41e3cf0827c2e044edff35f7cb7bc8be0d25fd29107ad4098a5baa44"
        ),
        "summary_sha256": (
            "f9c28d5dfb1c0be2c4a8ea3769ae395d4263b919f7e5b936a063262b25271a15"
        ),
        "scenario_count": 10,
        "total_pilot_replicates": 250,
        "all_scenario_groups_passed": True,
        "target_mcse_reachable_within_cap_for_all_scenarios": True,
        "scientific_effect_results_exposed": False,
        "locked_final_replicates_per_confirmatory_scenario": 1000,
        "permitted_decision": "monte_carlo_replicate_count_only",
    }
    for key, expected in expected_completion.items():
        if _need(completion, key) != expected:
            raise ValueError(f"Stage E completion record changed: {key}")

    stage_f = _need(document, "stage_f_confirmatory_validation")
    raw_scenarios = _need(stage_f, "primary_scenarios")
    if not isinstance(raw_scenarios, list) or len(raw_scenarios) != 10:
        raise ValueError("Stage F must contain ten primary scenarios")
    observed_cells = {
        (_need(item, "defect"), int(_need(item, "sample_size")))
        for item in raw_scenarios
    }
    expected_cells = {
        (defect, sample_size)
        for defect in _PRIMARY_DEFECTS
        for sample_size in _PRIMARY_SAMPLE_SIZES
    }
    if observed_cells != expected_cells:
        raise ValueError("the frozen primary scenario grid has changed")
    scenario_ids = [_need(item, "id") for item in raw_scenarios]
    if len(set(scenario_ids)) != len(scenario_ids) or not all(
        item.startswith("confirmatory_v1__") for item in scenario_ids
    ):
        raise ValueError("validation scenario identifiers are invalid")
    if _need(stage_f, "replicate_id_start") != 300000:
        raise ValueError("Stage F replicate namespace has changed")
    if _need(stage_f, "minimum_replicates_per_scenario") != 1000:
        raise ValueError("Stage F minimum replicate count has changed")
    if _need(stage_f, "maximum_replicates_per_scenario") != 5000:
        raise ValueError("Stage F maximum replicate count has changed")
    if _need(stage_f, "final_replicate_count") != 1000:
        raise ValueError("Stage F final replicate count has changed")
    if _need(stage_f, "authorisation_tag") != "stage-e-variance-complete-v1.0":
        raise ValueError("Stage F authorisation tag has changed")


def validation_configuration_hashes(
    project: ProjectConfig,
    development: DevelopmentConfig,
    config: ValidationConfig,
) -> dict[str, str]:
    """Return hashes identifying the frozen Stage E inputs."""

    documents = {
        "analysis": project.analysis,
        "simulation": project.simulation,
        "candidate_effective_analysis": candidate_analysis_config(
            project,
            development,
            "C002",
        ),
        "validation": config.document,
    }
    result = {name: canonical_sha256(value) for name, value in documents.items()}
    result["combined"] = canonical_sha256(documents)
    return result


def plan_blinded_pilot(config: ValidationConfig) -> tuple[PilotScenarioSpec, ...]:
    """Expand the ten Stage E scenario groups without exposing results."""

    pilot = config.document["stage_e_blinded_variance_pilot"]
    first, last = (int(value) for value in pilot["replicate_ids"])
    replicate_ids = tuple(range(first, last + 1))
    if len(replicate_ids) != int(pilot["replicates_per_scenario"]):
        raise RuntimeError("Stage E replicate bounds disagree with the declared count")
    return tuple(
        PilotScenarioSpec(
            scenario_id=str(item["id"]),
            defect=str(item["defect"]),
            sample_size=int(item["sample_size"]),
            replicate_ids=replicate_ids,
        )
        for item in config.document["stage_f_confirmatory_validation"][
            "primary_scenarios"
        ]
    )


def select_blinded_pilot_scenario(
    config: ValidationConfig,
    scenario_id: str,
) -> PilotScenarioSpec:
    """Resolve one exact Stage E scenario group."""

    matches = [
        item for item in plan_blinded_pilot(config) if item.scenario_id == scenario_id
    ]
    if len(matches) != 1:
        raise ValueError(f"unknown Stage E scenario: {scenario_id}")
    return matches[0]


def execute_blinded_pilot_scenario(
    project: ProjectConfig,
    development: DevelopmentConfig,
    config: ValidationConfig,
    spec: PilotScenarioSpec,
    *,
    code_commit: str,
    git_branch: str,
    repository_clean_at_start: bool,
) -> dict[str, Any]:
    """Run one 25-replicate group and disclose variance only."""

    if not _COMMIT_PATTERN.fullmatch(code_commit):
        raise ValueError("code_commit must be a full lowercase Git hash")
    if not git_branch:
        raise ValueError("git_branch must not be empty")
    if repository_clean_at_start is not True:
        raise RuntimeError("Stage E requires a clean Git repository")
    planned = select_blinded_pilot_scenario(config, spec.scenario_id)
    if planned != spec:
        raise RuntimeError("Stage E scenario differs from the frozen plan")

    started = datetime.now(UTC)
    start_counter = time.perf_counter()
    contrasts: list[float] = []
    data_hashes: list[str] = []
    fold_hashes: list[str] = []
    replicate_invariants: list[InvariantResult] = []
    for replicate_id in spec.replicate_ids:
        result = _execute_pilot_replicate(
            project,
            development,
            config,
            spec,
            replicate_id,
        )
        failed = [item.name for item in result.invariants if not item.passed]
        if failed:
            raise RuntimeError(
                f"Stage E replicate {replicate_id} failed invariants: {failed}"
            )
        contrasts.append(result.contrast)
        data_hashes.append(result.generated_data_sha256)
        fold_hashes.append(result.fold_assignments_sha256)
        replicate_invariants.extend(result.invariants)

    contrast_array = np.asarray(contrasts, dtype=float)
    standard_deviation = float(np.std(contrast_array, ddof=1))
    pilot = config.document["stage_e_blinded_variance_pilot"]
    target = float(pilot["primary_target_mcse_per_scenario"])
    minimum = int(
        config.document["stage_f_confirmatory_validation"][
            "minimum_replicates_per_scenario"
        ]
    )
    maximum = int(pilot["maximum_replicates"])
    variance_required = math.ceil((standard_deviation / target) ** 2)
    uncapped_required = max(minimum, variance_required)
    capped_required = min(maximum, uncapped_required)
    hashes = validation_configuration_hashes(project, development, config)
    completed = datetime.now(UTC)
    invariants = (
        InvariantResult(
            "all_replicate_invariants_passed",
            all(item.passed for item in replicate_invariants),
        ),
        InvariantResult(
            "replicate_count_matches_frozen_plan",
            len(contrasts) == len(spec.replicate_ids),
        ),
        InvariantResult(
            "variance_is_finite_and_nonnegative",
            math.isfinite(standard_deviation) and standard_deviation >= 0.0,
        ),
        InvariantResult("effect_direction_not_disclosed", True),
        InvariantResult("individual_contrasts_not_persisted", True),
    )
    resource = ResourceUsage(
        wall_clock_seconds=time.perf_counter() - start_counter,
        process_peak_rss_mb_at_completion=process_peak_rss_mb(),
        cpu_count=os.cpu_count(),
        operating_system=f"{platform.system()} {platform.release()}",
        machine=platform.machine(),
        python_version=sys.version.split()[0],
        package_versions=package_versions(),
    )
    return {
        "schema_version": "1.0",
        "stage": "stage_e_blinded_variance_pilot",
        "scientific_status": "variance_only_blinded",
        "scientific_effect_results_exposed": False,
        "eligible_for_confirmatory_evidence": False,
        "started_at_utc": started.isoformat().replace("+00:00", "Z"),
        "completed_at_utc": completed.isoformat().replace("+00:00", "Z"),
        "passed": all(item.passed for item in invariants),
        "fingerprint": {
            "candidate_id": "C002",
            "scenario_id": spec.scenario_id,
            "defect": spec.defect,
            "sample_size": spec.sample_size,
            "replicate_id_first": spec.replicate_ids[0],
            "replicate_id_last": spec.replicate_ids[-1],
            "replicate_count": len(spec.replicate_ids),
            "configuration_sha256": hashes,
            "generated_data_collection_sha256": _sequence_sha256(data_hashes),
            "fold_assignment_collection_sha256": _sequence_sha256(fold_hashes),
            "code_commit": code_commit,
            "git_branch": git_branch,
            "repository_clean_at_start": repository_clean_at_start,
        },
        "permitted_results": {
            "paired_primary_contrast_standard_deviation": standard_deviation,
            "target_mcse_per_scenario": target,
            "required_replicates_uncapped": uncapped_required,
            "required_replicates_after_cap": capped_required,
            "target_reachable_within_cap": uncapped_required <= maximum,
        },
        "resource_usage": asdict(resource),
        "invariants": [asdict(item) for item in invariants],
        "prohibited_outputs_omitted": list(pilot["prohibited_outputs"]),
    }


def summarise_blinded_pilot_reports(
    reports: list[dict[str, Any]],
    config: ValidationConfig,
) -> dict[str, Any]:
    """Combine all scenario variances without revealing an effect direction."""

    if not reports:
        raise ValueError("at least one Stage E report is required")
    expected = {item.scenario_id for item in plan_blinded_pilot(config)}
    seen: set[str] = set()
    commits: set[str] = set()
    combined_hashes: set[str] = set()
    scenario_results: dict[str, dict[str, Any]] = {}
    prohibited_keys = {
        "mean_effect_estimates",
        "method_rankings",
        "group_differences",
        "replicate_contrasts",
        "primary_material_unsafe_acceptance_contrast",
        "methods",
    }
    for report in reports:
        if report.get("stage") != "stage_e_blinded_variance_pilot":
            raise ValueError("summary input contains a non-Stage E report")
        if not report.get("passed", False):
            raise ValueError("failed Stage E reports cannot determine replication")
        if report.get("scientific_effect_results_exposed") is not False:
            raise ValueError("Stage E report exposed scientific effect results")
        if _contains_any_key(report, prohibited_keys):
            raise ValueError("Stage E report contains a prohibited output")
        fingerprint = report["fingerprint"]
        scenario_id = fingerprint["scenario_id"]
        if scenario_id in seen:
            raise ValueError("duplicate Stage E scenario report")
        seen.add(scenario_id)
        commits.add(fingerprint["code_commit"])
        combined_hashes.add(fingerprint["configuration_sha256"]["combined"])
        scenario_results[scenario_id] = dict(report["permitted_results"])
    if seen != expected:
        missing = sorted(expected - seen)
        extra = sorted(seen - expected)
        raise ValueError(
            f"Stage E report set is incomplete; missing={missing}, extra={extra}"
        )
    if len(commits) != 1 or len(combined_hashes) != 1:
        raise ValueError("Stage E reports do not share one code and configuration")

    final_count = max(
        int(item["required_replicates_after_cap"]) for item in scenario_results.values()
    )
    all_reachable = all(
        bool(item["target_reachable_within_cap"]) for item in scenario_results.values()
    )
    return {
        "schema_version": "1.0",
        "stage": "stage_e_blinded_variance_pilot_summary",
        "scientific_status": "variance_only_blinded",
        "scientific_effect_results_exposed": False,
        "eligible_for_confirmatory_evidence": False,
        "candidate_id": "C002",
        "scenario_count": len(scenario_results),
        "replicates_per_pilot_scenario": 25,
        "code_commit": next(iter(commits)),
        "configuration_combined_sha256": next(iter(combined_hashes)),
        "scenario_variances": dict(sorted(scenario_results.items())),
        "final_replicates_per_confirmatory_scenario": final_count,
        "target_mcse_reachable_within_cap_for_all_scenarios": all_reachable,
        "stage_f_execution_authorised": False,
        "next_action": (
            "Commit and tag this variance-only replicate-count decision before "
            "starting Stage F. No scientific method may change."
        ),
    }


def _execute_pilot_replicate(
    project: ProjectConfig,
    development: DevelopmentConfig,
    config: ValidationConfig,
    spec: PilotScenarioSpec,
    replicate_id: int,
) -> _PilotReplicateResult:
    analysis = candidate_analysis_config(project, development, "C002")
    common = config.document["stage_f_confirmatory_validation"]["common_parameters"]
    scenario = SimulationScenario(
        scenario_id=spec.scenario_id,
        sample_size=spec.sample_size,
        defect=spec.defect,
        replicate_id=replicate_id,
        outcome_type=str(common["outcome_type"]),
        baseline_shape=str(common["baseline_shape"]),
        effect_strength=str(common["effect_strength"]),
        group_prevalence=float(common["group_prevalence"]),
        defect_allocation=str(common["defect_allocation"]),
        group_prognostic_coefficient=0.0,
    )
    generated = generate_simulation(scenario, project.simulation)
    frame = generated.observed
    schema = CovariateSchema(
        continuous=tuple(f"x{number}" for number in range(1, 11)),
        categorical=("group",),
    )
    covariates = frame.loc[:, list(schema.columns)]
    outcome = frame["outcome"].to_numpy()
    treatment = frame["treatment"].to_numpy(dtype=np.int8)
    row_ids = frame["row_id"].to_numpy()
    run_id = f"stage_e__C002__{spec.scenario_id}__replicate_{replicate_id}"
    construction = run_cross_fitted_construction(
        covariates,
        outcome,
        treatment,
        row_ids,
        schema=schema,
        trial_id="controlled_validation_simulation",
        run_id=run_id,
        outcome_type=scenario.outcome_type,
        analysis_config=analysis,
    )
    evaluation = evaluate_cross_fitted_policies(
        construction,
        covariates,
        outcome,
        treatment,
        row_ids,
        schema=schema,
        outcome_type=scenario.outcome_type,
        analysis_config=analysis,
        documented_treatment_probability=0.5,
    )
    truth = evaluate_cross_fitted_known_truth(
        construction,
        evaluation,
        generated.mu0,
        generated.mu1,
        analysis_config=analysis,
    )
    expected_evidence = np.logical_and.reduce(
        [construction.checks[name] for name in _ESSENTIAL_CHECKS]
    )
    expected_complete = (
        expected_evidence & construction.gate.graded_uncertainty_acceptance
    )
    complete = truth.metrics["complete_gate"]
    uncertainty = truth.metrics["uncertainty_only"]
    exact_fold_coverage = all(
        int(construction.gate.complete[construction.fold_ids == fold_id].sum())
        == int(
            construction.uncertainty_only_acceptance[
                construction.fold_ids == fold_id
            ].sum()
        )
        for fold_id in np.unique(construction.fold_ids)
    )
    invariants = (
        InvariantResult(
            "stage_e_scenario_namespace",
            spec.scenario_id.startswith("confirmatory_v1__"),
        ),
        InvariantResult(
            "stage_e_replicate_namespace", 100000 <= replicate_id <= 100024
        ),
        InvariantResult(
            "three_essential_checks",
            construction.gate.essential_checks == _ESSENTIAL_CHECKS,
        ),
        InvariantResult(
            "graded_uncertainty_enabled", construction.gate.graded_uncertainty_applied
        ),
        InvariantResult(
            "essential_gate_is_logical_and",
            bool(
                np.array_equal(expected_evidence, construction.gate.evidence_qualified)
            ),
        ),
        InvariantResult(
            "graded_filter_is_subordinate",
            bool(np.array_equal(expected_complete, construction.gate.complete)),
        ),
        InvariantResult("exact_matched_coverage_within_fold", exact_fold_coverage),
        InvariantResult(
            "unsafe_acceptance_population_denominator",
            all(
                math.isclose(
                    metric.material_unsafe_acceptance,
                    metric.unsafe_accepted_count / metric.sample_size,
                    rel_tol=0.0,
                    abs_tol=1e-15,
                )
                for metric in (complete, uncertainty)
            ),
        ),
        InvariantResult(
            "paired_contrast_definition",
            math.isclose(
                truth.primary_material_unsafe_acceptance_contrast,
                complete.material_unsafe_acceptance
                - uncertainty.material_unsafe_acceptance,
                rel_tol=0.0,
                abs_tol=1e-15,
            ),
        ),
    )
    return _PilotReplicateResult(
        contrast=float(truth.primary_material_unsafe_acceptance_contrast),
        generated_data_sha256=simulation_data_sha256(generated),
        fold_assignments_sha256=array_sha256(construction.fold_ids),
        invariants=invariants,
    )


def _need(mapping: dict[str, Any], *keys: str) -> Any:
    current: Any = mapping
    traversed: list[str] = []
    for key in keys:
        traversed.append(key)
        if not isinstance(current, dict) or key not in current:
            raise ValueError(f"missing validation key: {'.'.join(traversed)}")
        current = current[key]
    return current


def _sequence_sha256(values: list[str]) -> str:
    payload = "\n".join(values).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _contains_any_key(value: Any, prohibited: set[str]) -> bool:
    if isinstance(value, dict):
        return any(
            key in prohibited or _contains_any_key(item, prohibited)
            for key, item in value.items()
        )
    if isinstance(value, list):
        return any(_contains_any_key(item, prohibited) for item in value)
    return False
