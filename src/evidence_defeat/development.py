"""Transparent Stage C development-bank execution and descriptive summaries."""

from __future__ import annotations

import json
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
from scipy.stats import t as student_t

from evidence_defeat.config import (
    DevelopmentConfig,
    ProjectConfig,
    candidate_analysis_config,
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
from evidence_defeat.fairness import FairnessAudit, audit_known_truth_groups
from evidence_defeat.known_truth import (
    KnownTruthEvaluation,
    deterministic_acceptances,
    evaluate_cross_fitted_known_truth,
    evaluate_random_deferral_known_truth,
    original_scale_materiality_margin,
)
from evidence_defeat.pipeline import (
    CrossFittedConstruction,
    run_cross_fitted_construction,
)
from evidence_defeat.preprocessing import CovariateSchema
from evidence_defeat.selection import uncertainty_ranking_score
from evidence_defeat.simulation import SimulationScenario, generate_simulation

_COMMIT_PATTERN = re.compile(r"^[0-9a-f]{40}(?:[0-9a-f]{24})?$")


@dataclass(frozen=True)
class DevelopmentRunSpec:
    """One candidate, scenario, and replicate authorised for Stage C."""

    candidate_id: str
    tier: str
    scenario: SimulationScenario
    run_id: str


@dataclass(frozen=True)
class DevelopmentFingerprint:
    """Immutable identities needed to reproduce one Stage C run."""

    candidate_id: str
    tier: str
    scenario_id: str
    defect: str
    sample_size: int
    replicate_id: int
    replicate_seed: int
    run_id: str
    configuration_sha256: dict[str, str]
    generated_data_sha256: str
    fold_assignments_sha256: str
    code_commit: str
    git_branch: str
    repository_clean_at_start: bool


@dataclass(frozen=True)
class CheckRecovery:
    """Recovery of one generated defect by its corresponding failed check."""

    check_name: str
    generated_defect_count: int
    generated_nondefect_count: int
    check_failure_count: int
    sensitivity_to_generated_defect: float | None
    specificity_for_generated_nondefect: float | None


@dataclass(frozen=True)
class DevelopmentScientificResults:
    """Complete non-confirmatory metric profile for one development run."""

    essential_checks: tuple[str, ...]
    graded_uncertainty_filter_enabled: bool
    graded_uncertainty_retention_fraction: float
    primary_material_unsafe_acceptance_contrast: float
    methods: dict[str, dict[str, Any]]
    random_deferral: dict[str, float]
    check_recovery: dict[str, CheckRecovery]
    check_failure_rates: dict[str, float]
    fairness_audit: FairnessAudit


@dataclass(frozen=True)
class DevelopmentRunReport:
    """One explicitly unblinded, non-confirmatory Stage C report."""

    schema_version: str
    stage: str
    scientific_status: str
    scientific_results_exposed: bool
    eligible_for_confirmatory_evidence: bool
    started_at_utc: str
    completed_at_utc: str
    passed: bool
    fingerprint: DevelopmentFingerprint
    resource_usage: ResourceUsage
    invariants: tuple[InvariantResult, ...]
    results: DevelopmentScientificResults

    def to_dict(self) -> dict[str, Any]:
        """Return strict JSON data, replacing undefined ratios with null."""

        return _json_safe(asdict(self))


def development_configuration_hashes(
    project: ProjectConfig,
    development: DevelopmentConfig,
    candidate_id: str,
) -> dict[str, str]:
    """Hash base, Stage C, and candidate-effective configurations."""

    effective_analysis = candidate_analysis_config(project, development, candidate_id)
    documents = {
        "analysis": project.analysis,
        "simulation": project.simulation,
        "poc": project.poc,
        "development_validation": project.development_validation,
        "development_bank": development.bank,
        "development_candidates": development.candidates,
        "candidate_effective_analysis": effective_analysis,
    }
    result = {name: canonical_sha256(value) for name, value in documents.items()}
    result["combined"] = canonical_sha256(documents)
    return result


def plan_development_runs(
    project: ProjectConfig,
    development: DevelopmentConfig,
    candidate_id: str,
    *,
    tier: str | None = None,
) -> tuple[DevelopmentRunSpec, ...]:
    """Expand the committed Stage C grid for one eligible candidate."""

    register = development.candidates["candidates"]
    if candidate_id not in register:
        raise ValueError(f"unknown Stage C candidate: {candidate_id}")
    candidate = register[candidate_id]
    tiers = development.bank["tiers"]
    authorised_tiers = set(candidate["authorised_tiers"])
    if tier is not None and tier not in authorised_tiers:
        raise ValueError(
            f"tier {tier!r} is not authorised for candidate {candidate_id}"
        )
    selected_tiers = (
        [
            name
            for name, values in tiers.items()
            if name in authorised_tiers
            and _candidate_in_scope(candidate["status"], values["candidate_scope"])
        ]
        if tier is None
        else [tier]
    )
    if any(name not in tiers for name in selected_tiers):
        raise ValueError("requested tier is not in the Stage C development bank")

    specs: list[DevelopmentRunSpec] = []
    for tier_name in selected_tiers:
        tier_config = tiers[tier_name]
        _assert_candidate_scope(candidate["status"], tier_config["candidate_scope"])
        for raw_scenario in tier_config["scenarios"]:
            for replicate_id in tier_config["replicate_ids"]:
                scenario = SimulationScenario(
                    scenario_id=str(raw_scenario["id"]),
                    sample_size=int(raw_scenario["sample_size"]),
                    defect=raw_scenario["defect"],
                    replicate_id=int(replicate_id),
                    outcome_type=raw_scenario["outcome_type"],
                    baseline_shape=raw_scenario["baseline_shape"],
                    effect_strength=raw_scenario["effect_strength"],
                    group_prevalence=float(raw_scenario["group_prevalence"]),
                    defect_allocation=raw_scenario["defect_allocation"],
                    group_prognostic_coefficient=float(
                        raw_scenario["group_prognostic_coefficient"]
                    ),
                )
                run_id = (
                    f"stage_c__{candidate_id}__{tier_name}__"
                    f"{scenario.scenario_id}__replicate_{scenario.replicate_id}"
                )
                specs.append(
                    DevelopmentRunSpec(
                        candidate_id=candidate_id,
                        tier=tier_name,
                        scenario=scenario,
                        run_id=run_id,
                    )
                )
    if len({spec.run_id for spec in specs}) != len(specs):
        raise RuntimeError("Stage C run identifiers are not unique")
    return tuple(specs)


def select_development_run(
    project: ProjectConfig,
    development: DevelopmentConfig,
    candidate_id: str,
    run_id: str,
) -> DevelopmentRunSpec:
    """Resolve exactly one authorised Stage C run."""

    prefix = f"stage_c__{candidate_id}__"
    if not run_id.startswith(prefix):
        raise ValueError("run_id is not authorised for this Stage C candidate")
    tier, separator, _ = run_id.removeprefix(prefix).partition("__")
    if not separator:
        raise ValueError("run_id is not authorised for this Stage C candidate")
    matches = [
        spec
        for spec in plan_development_runs(
            project,
            development,
            candidate_id,
            tier=tier,
        )
        if spec.run_id == run_id
    ]
    if len(matches) != 1:
        raise ValueError("run_id is not authorised for this Stage C candidate")
    return matches[0]


def execute_development_run(
    project: ProjectConfig,
    development: DevelopmentConfig,
    spec: DevelopmentRunSpec,
    *,
    code_commit: str,
    git_branch: str,
    repository_clean_at_start: bool,
) -> DevelopmentRunReport:
    """Execute one development-bank unit and expose its full metric profile."""

    if not _COMMIT_PATTERN.fullmatch(code_commit):
        raise ValueError("code_commit must be a full lowercase Git hash")
    if not git_branch:
        raise ValueError("git_branch must not be empty")
    if repository_clean_at_start is not True:
        raise RuntimeError("Stage C runs require a clean Git repository")
    prefix = development.bank["separation"]["scenario_id_prefix"]
    if not spec.scenario.scenario_id.startswith(prefix):
        raise RuntimeError("Stage C scenario escaped the development namespace")

    started = datetime.now(UTC)
    start_counter = time.perf_counter()
    analysis = candidate_analysis_config(project, development, spec.candidate_id)
    generated = generate_simulation(spec.scenario, project.simulation)
    frame = generated.observed
    schema = CovariateSchema(
        continuous=tuple(f"x{number}" for number in range(1, 11)),
        categorical=("group",),
    )
    covariates = frame.loc[:, list(schema.columns)]
    outcome = frame["outcome"].to_numpy()
    treatment = frame["treatment"].to_numpy(dtype=np.int8)
    row_ids = frame["row_id"].to_numpy()
    construction = run_cross_fitted_construction(
        covariates,
        outcome,
        treatment,
        row_ids,
        schema=schema,
        trial_id="controlled_development_simulation",
        run_id=spec.run_id,
        outcome_type=spec.scenario.outcome_type,
        analysis_config=analysis,
    )
    evaluation = evaluate_cross_fitted_policies(
        construction,
        covariates,
        outcome,
        treatment,
        row_ids,
        schema=schema,
        outcome_type=spec.scenario.outcome_type,
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
    random_truth = evaluate_random_deferral_known_truth(
        construction,
        evaluation,
        generated.mu0,
        generated.mu1,
        analysis_config=analysis,
    )
    fairness = _fairness_audit(
        construction,
        evaluation,
        generated.mu0,
        generated.mu1,
        frame["group"].to_numpy(dtype=np.int8),
        analysis,
    )
    recovery = _check_recovery(construction, generated.defects)
    config_hashes = development_configuration_hashes(
        project,
        development,
        spec.candidate_id,
    )
    fingerprint = DevelopmentFingerprint(
        candidate_id=spec.candidate_id,
        tier=spec.tier,
        scenario_id=spec.scenario.scenario_id,
        defect=spec.scenario.defect,
        sample_size=spec.scenario.sample_size,
        replicate_id=spec.scenario.replicate_id,
        replicate_seed=generated.seed,
        run_id=spec.run_id,
        configuration_sha256=config_hashes,
        generated_data_sha256=simulation_data_sha256(generated),
        fold_assignments_sha256=array_sha256(construction.fold_ids),
        code_commit=code_commit,
        git_branch=git_branch,
        repository_clean_at_start=repository_clean_at_start,
    )
    invariants = _development_invariants(
        project,
        development,
        construction,
        truth,
        spec,
        config_hashes,
    )
    results = DevelopmentScientificResults(
        essential_checks=construction.gate.essential_checks,
        graded_uncertainty_filter_enabled=construction.gate.graded_uncertainty_applied,
        graded_uncertainty_retention_fraction=float(
            analysis["gate"]["uncertainty"]["graded_filter"]["retention_fraction"]
        ),
        primary_material_unsafe_acceptance_contrast=(
            truth.primary_material_unsafe_acceptance_contrast
        ),
        methods={name: asdict(metrics) for name, metrics in truth.metrics.items()},
        random_deferral={
            "mean_material_unsafe_acceptance": (
                random_truth.mean_material_unsafe_acceptance
            ),
            "mean_deployed_policy_utility": random_truth.mean_deployed_policy_utility,
        },
        check_recovery=recovery,
        check_failure_rates={
            name: float((~values).mean())
            for name, values in construction.checks.items()
        },
        fairness_audit=fairness,
    )
    completed = datetime.now(UTC)
    return DevelopmentRunReport(
        schema_version="0.1",
        stage="stage_c_development",
        scientific_status="exploratory_unblinded_development_only",
        scientific_results_exposed=True,
        eligible_for_confirmatory_evidence=False,
        started_at_utc=started.isoformat().replace("+00:00", "Z"),
        completed_at_utc=completed.isoformat().replace("+00:00", "Z"),
        passed=all(item.passed for item in invariants),
        fingerprint=fingerprint,
        resource_usage=ResourceUsage(
            wall_clock_seconds=time.perf_counter() - start_counter,
            process_peak_rss_mb_at_completion=process_peak_rss_mb(),
            cpu_count=os.cpu_count(),
            operating_system=f"{platform.system()} {platform.release()}",
            machine=platform.machine(),
            python_version=sys.version.split()[0],
            package_versions=package_versions(),
        ),
        invariants=invariants,
        results=results,
    )


def summarise_development_reports(
    reports: list[dict[str, Any]],
    *,
    candidate_id: str,
    tier: str,
) -> dict[str, Any]:
    """Create a descriptive, non-decisional summary for one candidate tier."""

    if not reports:
        raise ValueError("at least one Stage C report is required")
    seen: set[str] = set()
    for report in reports:
        if report.get("stage") != "stage_c_development":
            raise ValueError("summary input contains a non-Stage C report")
        fingerprint = report["fingerprint"]
        if fingerprint["candidate_id"] != candidate_id:
            raise ValueError("summary input mixes candidate identifiers")
        if fingerprint["tier"] != tier:
            raise ValueError("summary input mixes development tiers")
        if not report.get("passed", False):
            raise ValueError("failed Stage C runs cannot enter a scientific summary")
        run_id = fingerprint["run_id"]
        if run_id in seen:
            raise ValueError("summary input contains duplicate run identifiers")
        seen.add(run_id)

    scenarios: dict[str, list[dict[str, Any]]] = {}
    for report in reports:
        scenario_id = report["fingerprint"]["scenario_id"]
        scenarios.setdefault(scenario_id, []).append(report)
    return {
        "schema_version": "0.1",
        "stage": "stage_c_development_summary",
        "scientific_status": "exploratory_unblinded_development_only",
        "eligible_for_confirmatory_evidence": False,
        "candidate_id": candidate_id,
        "tier": tier,
        "run_count": len(reports),
        "scenario_count": len(scenarios),
        "primary_contrast_overall": _estimate_summary(
            [
                item["results"]["primary_material_unsafe_acceptance_contrast"]
                for item in reports
            ]
        ),
        "scenarios": {
            scenario_id: _scenario_summary(items)
            for scenario_id, items in sorted(scenarios.items())
        },
        "candidate_decision": (
            "No automatic pass/fail or weighted score. Review the complete safety, "
            "utility, access, fairness, stability, and complexity profile and record "
            "retain/revise/reject in the append-only candidate log."
        ),
    }


def load_reports_from_directory(path: str | Path) -> list[dict[str, Any]]:
    """Load Stage C report JSON files from one batch output directory."""

    root = Path(path)
    report_paths = sorted((root / "reports").glob("*.json"))
    if not report_paths:
        raise ValueError(f"no Stage C reports found under {root / 'reports'}")
    return [json.loads(item.read_text(encoding="utf-8")) for item in report_paths]


def _fairness_audit(
    construction: CrossFittedConstruction,
    evaluation: Any,
    mu0: np.ndarray,
    mu1: np.ndarray,
    group: np.ndarray,
    analysis: dict[str, Any],
) -> FairnessAudit:
    effect = np.asarray(mu1, dtype=float) - np.asarray(mu0, dtype=float)
    optimal = (effect > 0.0).astype(np.int8)
    margin = original_scale_materiality_margin(construction, analysis)
    actionable = np.abs(effect) >= margin
    oracle_utility = np.maximum(mu0, mu1)
    default_utility = np.where(evaluation.default_action == 1, mu1, mu0)
    acceptances = deterministic_acceptances(construction)
    row_metrics: dict[str, dict[str, np.ndarray]] = {}
    for method, acceptance in acceptances.items():
        deployed_action = evaluation.policies[method]
        deployed_utility = np.where(deployed_action == 1, mu1, mu0)
        unsafe = (
            acceptance & actionable & (construction.individualised_action != optimal)
        )
        row_metrics[method] = {
            "coverage": acceptance.astype(float),
            "deferral": (~acceptance).astype(float),
            "material_unsafe_acceptance": unsafe.astype(float),
            "deployed_policy_utility": deployed_utility,
            "oracle_regret": oracle_utility - deployed_utility,
            "regret_relative_to_default": default_utility - deployed_utility,
        }
    estimator_count = construction.predictions.effect_matrix.shape[1]
    if construction.outcome_type == "binary":
        construction_margin = float(analysis["outcome"]["binary_materiality_margin"])
    else:
        construction_margin = float(
            analysis["outcome"]["continuous_materiality_margin_sd"]
        )
    certainty_score = uncertainty_ranking_score(
        construction.predictions.primary_effect,
        construction.predictions.primary_interval_lower,
        construction.predictions.primary_interval_upper,
        materiality_margin=construction_margin,
        interval_alpha=float(analysis["learners"]["primary"]["interval_alpha_primary"]),
    )
    evidence_scores = np.column_stack(
        [
            construction.record_observed_fraction,
            construction.support_score,
            construction.multiplicity_opposing_estimators / estimator_count,
            -certainty_score,
        ]
    )
    fairness = analysis["fairness_audit"]
    evidence_score_names = tuple(fairness["evidence_scores"])
    if evidence_score_names != (
        "record_completeness",
        "support_distance",
        "estimator_disagreement",
        "decision_uncertainty",
    ):
        raise RuntimeError("configured fairness evidence scores have changed")
    percentiles = fairness["weight_truncation_percentiles"]
    return audit_known_truth_groups(
        group,
        construction.fold_ids,
        evidence_scores,
        row_metrics,
        evidence_score_names=evidence_score_names,
        minimum_group_n=int(fairness["minimum_group_n"]),
        truncation_percentiles=(float(percentiles[0]), float(percentiles[1])),
        balance_threshold=float(fairness["balance_threshold_absolute_smd"]),
    )


def _check_recovery(
    construction: CrossFittedConstruction,
    defect_frame: Any,
) -> dict[str, CheckRecovery]:
    result = {}
    for name, passes in construction.checks.items():
        defects = defect_frame[name].to_numpy(dtype=bool)
        failures = ~passes
        positive_count = int(defects.sum())
        negative_count = int((~defects).sum())
        sensitivity = float(failures[defects].mean()) if positive_count else None
        specificity = float(passes[~defects].mean()) if negative_count else None
        result[name] = CheckRecovery(
            check_name=name,
            generated_defect_count=positive_count,
            generated_nondefect_count=negative_count,
            check_failure_count=int(failures.sum()),
            sensitivity_to_generated_defect=sensitivity,
            specificity_for_generated_nondefect=specificity,
        )
    return result


def _development_invariants(
    project: ProjectConfig,
    development: DevelopmentConfig,
    construction: CrossFittedConstruction,
    truth: KnownTruthEvaluation,
    spec: DevelopmentRunSpec,
    hashes: dict[str, str],
) -> tuple[InvariantResult, ...]:
    expected_evidence_qualified = np.logical_and.reduce(
        [construction.checks[name] for name in construction.gate.essential_checks]
    )
    expected_complete = (
        expected_evidence_qualified & construction.gate.graded_uncertainty_acceptance
    )
    methods = truth.metrics
    governance_metric = project.development_validation["phase_boundaries"][
        "independent_validation"
    ]["primary_metric"]
    return (
        InvariantResult(
            "development_namespace_only",
            spec.scenario.scenario_id.startswith(
                development.bank["separation"]["scenario_id_prefix"]
            ),
        ),
        InvariantResult(
            "validation_sources_remain_prohibited",
            all(
                development.bank["separation"][key] is False
                for key in (
                    "reserved_validation_grid_access",
                    "rct_bench_patient_level_access",
                    "real_trial_outcome_access",
                )
            ),
        ),
        InvariantResult(
            "evidence_qualification_is_logical_and_of_essential_checks",
            bool(
                np.array_equal(
                    expected_evidence_qualified,
                    construction.gate.evidence_qualified,
                )
            ),
        ),
        InvariantResult(
            "complete_gate_applies_graded_uncertainty_after_evidence_checks",
            bool(np.array_equal(expected_complete, construction.gate.complete)),
        ),
        InvariantResult(
            "uncertainty_comparator_has_exact_matched_coverage",
            bool(
                np.array_equal(
                    np.bincount(
                        construction.fold_ids,
                        weights=construction.gate.complete.astype(int),
                    ),
                    np.bincount(
                        construction.fold_ids,
                        weights=construction.uncertainty_only_acceptance.astype(int),
                    ),
                )
            ),
        ),
        InvariantResult(
            "unsafe_acceptance_uses_population_denominator",
            governance_metric == "material_unsafe_acceptance_population_denominator"
            and all(
                math.isclose(
                    item["material_unsafe_acceptance"],
                    item["unsafe_accepted_count"] / item["sample_size"],
                    rel_tol=0.0,
                    abs_tol=1e-15,
                )
                for item in (asdict(metric) for metric in methods.values())
            ),
        ),
        InvariantResult(
            "configuration_hashes_complete",
            set(hashes)
            == {
                "analysis",
                "simulation",
                "poc",
                "development_validation",
                "development_bank",
                "development_candidates",
                "candidate_effective_analysis",
                "combined",
            },
        ),
        InvariantResult(
            "development_not_confirmatory",
            development.bank["eligible_for_confirmatory_evidence"] is False,
        ),
        InvariantResult(
            "scientific_unblinding_was_authorised",
            project.development_validation["current_evidence_state"][
                "stage_c_scientific_unblinding_authorised"
            ]
            is True,
        ),
    )


def _scenario_summary(reports: list[dict[str, Any]]) -> dict[str, Any]:
    method_names = sorted(reports[0]["results"]["methods"])
    check_names = sorted(reports[0]["results"]["check_recovery"])
    return {
        "replicate_count": len(reports),
        "defect": reports[0]["fingerprint"]["defect"],
        "sample_size": reports[0]["fingerprint"]["sample_size"],
        "primary_contrast": _estimate_summary(
            [
                item["results"]["primary_material_unsafe_acceptance_contrast"]
                for item in reports
            ]
        ),
        "methods": {
            method: {
                metric: _estimate_summary(
                    [item["results"]["methods"][method][metric] for item in reports]
                )
                for metric in (
                    "coverage",
                    "material_unsafe_acceptance",
                    "deployed_policy_utility",
                    "oracle_regret",
                    "regret_relative_to_default",
                )
            }
            for method in method_names
        },
        "matched_random_deferral": {
            metric: _estimate_summary(
                [item["results"]["random_deferral"][metric] for item in reports]
            )
            for metric in (
                "mean_material_unsafe_acceptance",
                "mean_deployed_policy_utility",
            )
        },
        "check_failure_rates": {
            check: _estimate_summary(
                [item["results"]["check_failure_rates"][check] for item in reports]
            )
            for check in check_names
        },
        "check_recovery": {
            check: {
                metric: _optional_estimate_summary(
                    [
                        item["results"]["check_recovery"][check][metric]
                        for item in reports
                    ]
                )
                for metric in (
                    "sensitivity_to_generated_defect",
                    "specificity_for_generated_nondefect",
                )
            }
            for check in check_names
        },
        "raw_complete_gate_group_gaps": _group_gap_summary(
            reports,
            audit_name="raw",
        ),
        "evidence_standardised_complete_gate_group_gaps": _group_gap_summary(
            reports,
            audit_name="evidence_standardised",
        ),
        "fairness_standardisation": _fairness_standardisation_summary(reports),
    }


def _group_gap_summary(
    reports: list[dict[str, Any]],
    *,
    audit_name: str,
) -> dict[str, Any] | None:
    audits = [item["results"]["fairness_audit"][audit_name] for item in reports]
    available = [item for item in audits if item is not None]
    if not available:
        return None
    metric_names = (
        "coverage",
        "deferral",
        "material_unsafe_acceptance",
        "deployed_policy_utility",
        "oracle_regret",
        "regret_relative_to_default",
    )
    return {
        "available_run_count": len(available),
        "total_run_count": len(reports),
        "metrics": {
            metric: _estimate_summary(
                [
                    item["complete_gate"][metric]["gap_group_1_minus_group_0"]
                    for item in available
                ]
            )
            for metric in metric_names
        },
    }


def _fairness_standardisation_summary(
    reports: list[dict[str, Any]],
) -> dict[str, Any]:
    statuses = [
        item["results"]["fairness_audit"]["standardisation"] for item in reports
    ]
    eligible = [item for item in statuses if item["eligible"]]
    balance_values = [
        item["max_absolute_standardised_mean_difference"] for item in eligible
    ]
    return {
        "eligible_run_count": len(eligible),
        "total_run_count": len(reports),
        "balance_passed_run_count": sum(
            item["balance_passed"] is True for item in eligible
        ),
        "max_absolute_standardised_mean_difference": (
            _estimate_summary(balance_values) if balance_values else None
        ),
    }


def _optional_estimate_summary(
    values: list[float | None],
) -> dict[str, float | int | None] | None:
    available = [float(value) for value in values if value is not None]
    return _estimate_summary(available) if available else None


def _estimate_summary(values: list[float]) -> dict[str, float | int | None]:
    array = np.asarray(values, dtype=float)
    if array.ndim != 1 or array.size < 1 or not np.isfinite(array).all():
        raise ValueError("summary values must be non-empty and finite")
    mean = float(array.mean())
    if array.size == 1:
        return {
            "n": 1,
            "mean": mean,
            "sd": None,
            "mcse": None,
            "confidence_interval_lower": None,
            "confidence_interval_upper": None,
        }
    sd = float(array.std(ddof=1))
    mcse = sd / math.sqrt(array.size)
    critical = float(student_t.ppf(0.975, df=array.size - 1))
    return {
        "n": int(array.size),
        "mean": mean,
        "sd": sd,
        "mcse": mcse,
        "confidence_interval_lower": mean - critical * mcse,
        "confidence_interval_upper": mean + critical * mcse,
    }


def _assert_candidate_scope(status: str, scope: str) -> None:
    if _candidate_in_scope(status, scope):
        return
    raise ValueError(
        f"candidate status {status!r} is not eligible for tier scope {scope!r}"
    )


def _candidate_in_scope(status: str, scope: str) -> bool:
    if scope == "all_candidates":
        return True
    if scope == "retained_candidates_only":
        return status in {"retained", "finalist"}
    if scope == "finalists_only":
        return status == "finalist"
    return False


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value
