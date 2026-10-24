"""One-time Stage F confirmatory controlled-validation execution."""

from __future__ import annotations

import math
import os
import platform
import re
import sys
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any

import numpy as np
from scipy.stats import t as student_t

from evidence_defeat.config import (
    DevelopmentConfig,
    ProjectConfig,
    candidate_analysis_config,
)
from evidence_defeat.development import (
    _check_recovery,
    _estimate_summary,
    _fairness_audit,
    _fairness_standardisation_summary,
    _group_gap_summary,
    _json_safe,
    _scenario_summary,
)
from evidence_defeat.diagnostics import (
    InvariantResult,
    ResourceUsage,
    array_sha256,
    package_versions,
    process_peak_rss_mb,
    simulation_data_sha256,
)
from evidence_defeat.evaluation import evaluate_cross_fitted_policies
from evidence_defeat.known_truth import (
    evaluate_cross_fitted_known_truth,
    evaluate_random_deferral_known_truth,
)
from evidence_defeat.pipeline import run_cross_fitted_construction
from evidence_defeat.preprocessing import CovariateSchema
from evidence_defeat.simulation import SimulationScenario, generate_simulation
from evidence_defeat.validation import (
    ValidationConfig,
    validation_configuration_hashes,
)

_COMMIT_PATTERN = re.compile(r"^[0-9a-f]{40}(?:[0-9a-f]{24})?$")
_ESSENTIAL_CHECKS = (
    "record_adequacy",
    "reference_support",
    "model_multiplicity",
)


@dataclass(frozen=True)
class ConfirmatoryRunSpec:
    """One immutable Stage F scenario-replicate unit."""

    scenario_id: str
    defect: str
    sample_size: int
    replicate_id: int
    run_id: str


def plan_confirmatory_runs(
    config: ValidationConfig,
) -> tuple[ConfirmatoryRunSpec, ...]:
    """Expand the locked ten-cell, 10,000-run Stage F primary grid."""

    stage_f = config.document["stage_f_confirmatory_validation"]
    first = int(stage_f["replicate_id_start"])
    count = int(stage_f["final_replicate_count"])
    if count != int(stage_f["minimum_replicates_per_scenario"]):
        raise RuntimeError("Stage F count differs from the blinded locked decision")
    specs = []
    for item in stage_f["primary_scenarios"]:
        scenario_id = str(item["id"])
        for replicate_id in range(first, first + count):
            specs.append(
                ConfirmatoryRunSpec(
                    scenario_id=scenario_id,
                    defect=str(item["defect"]),
                    sample_size=int(item["sample_size"]),
                    replicate_id=replicate_id,
                    run_id=(f"stage_f__C002__{scenario_id}__replicate_{replicate_id}"),
                )
            )
    expected_count = len(stage_f["primary_scenarios"]) * count
    if len(specs) != expected_count:
        raise RuntimeError("Stage F primary grid expansion is incomplete")
    if len({item.run_id for item in specs}) != len(specs):
        raise RuntimeError("Stage F run identifiers are not unique")
    return tuple(specs)


def select_confirmatory_run(
    config: ValidationConfig,
    scenario_id: str,
    replicate_id: int,
) -> ConfirmatoryRunSpec:
    """Resolve exactly one prespecified Stage F run."""

    stage_f = config.document["stage_f_confirmatory_validation"]
    first = int(stage_f["replicate_id_start"])
    count = int(stage_f["final_replicate_count"])
    if not first <= replicate_id < first + count:
        raise ValueError("replicate_id is outside the locked Stage F namespace")
    matches = [
        item for item in stage_f["primary_scenarios"] if str(item["id"]) == scenario_id
    ]
    if len(matches) != 1:
        raise ValueError(f"unknown Stage F scenario: {scenario_id}")
    raw = matches[0]
    return ConfirmatoryRunSpec(
        scenario_id=scenario_id,
        defect=str(raw["defect"]),
        sample_size=int(raw["sample_size"]),
        replicate_id=replicate_id,
        run_id=f"stage_f__C002__{scenario_id}__replicate_{replicate_id}",
    )


def execute_confirmatory_run(
    project: ProjectConfig,
    development: DevelopmentConfig,
    config: ValidationConfig,
    spec: ConfirmatoryRunSpec,
    *,
    code_commit: str,
    git_branch: str,
    repository_clean_at_start: bool,
) -> dict[str, Any]:
    """Execute one frozen Stage F replicate and retain its complete results."""

    if not _COMMIT_PATTERN.fullmatch(code_commit):
        raise ValueError("code_commit must be a full lowercase Git hash")
    if not git_branch:
        raise ValueError("git_branch must not be empty")
    if repository_clean_at_start is not True:
        raise RuntimeError("Stage F requires a clean Git repository")
    planned = select_confirmatory_run(
        config,
        spec.scenario_id,
        spec.replicate_id,
    )
    if planned != spec:
        raise RuntimeError("Stage F run differs from the locked plan")

    started = datetime.now(UTC)
    start_counter = time.perf_counter()
    analysis = candidate_analysis_config(project, development, "C002")
    common = config.document["stage_f_confirmatory_validation"]["common_parameters"]
    scenario = SimulationScenario(
        scenario_id=spec.scenario_id,
        sample_size=spec.sample_size,
        defect=spec.defect,
        replicate_id=spec.replicate_id,
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
    construction = run_cross_fitted_construction(
        covariates,
        outcome,
        treatment,
        row_ids,
        schema=schema,
        trial_id="controlled_confirmatory_simulation",
        run_id=spec.run_id,
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
        documented_treatment_probability=float(common["treatment_probability"]),
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
    hashes = validation_configuration_hashes(project, development, config)
    invariants = _confirmatory_invariants(
        construction,
        truth,
        spec,
        config,
        hashes,
    )
    completed = datetime.now(UTC)
    payload = {
        "schema_version": "1.0",
        "stage": "stage_f_confirmatory_validation",
        "scientific_status": "confirmatory_unblinded",
        "scientific_results_exposed": True,
        "eligible_for_confirmatory_evidence": True,
        "started_at_utc": started.isoformat().replace("+00:00", "Z"),
        "completed_at_utc": completed.isoformat().replace("+00:00", "Z"),
        "passed": all(item.passed for item in invariants),
        "fingerprint": {
            "candidate_id": "C002",
            "scenario_id": spec.scenario_id,
            "defect": spec.defect,
            "sample_size": spec.sample_size,
            "replicate_id": spec.replicate_id,
            "replicate_seed": generated.seed,
            "run_id": spec.run_id,
            "configuration_sha256": hashes,
            "generated_data_sha256": simulation_data_sha256(generated),
            "fold_assignments_sha256": array_sha256(construction.fold_ids),
            "code_commit": code_commit,
            "git_branch": git_branch,
            "repository_clean_at_start": repository_clean_at_start,
        },
        "resource_usage": asdict(
            ResourceUsage(
                wall_clock_seconds=time.perf_counter() - start_counter,
                process_peak_rss_mb_at_completion=process_peak_rss_mb(),
                cpu_count=os.cpu_count(),
                operating_system=f"{platform.system()} {platform.release()}",
                machine=platform.machine(),
                python_version=sys.version.split()[0],
                package_versions=package_versions(),
            )
        ),
        "invariants": [asdict(item) for item in invariants],
        "results": {
            "primary_material_unsafe_acceptance_contrast": (
                truth.primary_material_unsafe_acceptance_contrast
            ),
            "methods": {
                name: asdict(metrics) for name, metrics in truth.metrics.items()
            },
            "random_deferral": {
                "mean_material_unsafe_acceptance": (
                    random_truth.mean_material_unsafe_acceptance
                ),
                "mean_deployed_policy_utility": (
                    random_truth.mean_deployed_policy_utility
                ),
            },
            "check_recovery": {name: asdict(item) for name, item in recovery.items()},
            "check_failure_rates": {
                name: float((~values).mean())
                for name, values in construction.checks.items()
            },
            "fairness_audit": asdict(fairness),
        },
    }
    return _json_safe(payload)


def summarise_confirmatory_reports(
    reports: list[dict[str, Any]],
    config: ValidationConfig,
) -> dict[str, Any]:
    """Unblind Stage F once, but only after all 10,000 reports are complete."""

    expected_specs = plan_confirmatory_runs(config)
    expected_ids = {item.run_id for item in expected_specs}
    if len(reports) != len(expected_specs):
        raise ValueError("Stage F summary requires every prespecified primary report")
    seen: set[str] = set()
    commits: set[str] = set()
    hashes: set[str] = set()
    for report in reports:
        if report.get("stage") != "stage_f_confirmatory_validation":
            raise ValueError("summary input contains a non-Stage F report")
        if report.get("eligible_for_confirmatory_evidence") is not True:
            raise ValueError("summary input is not confirmatory evidence")
        if not report.get("passed", False):
            raise ValueError("failed Stage F reports cannot enter the summary")
        fingerprint = report["fingerprint"]
        run_id = str(fingerprint["run_id"])
        if run_id in seen:
            raise ValueError("summary input contains duplicate Stage F runs")
        seen.add(run_id)
        commits.add(str(fingerprint["code_commit"]))
        hashes.add(str(fingerprint["configuration_sha256"]["combined"]))
    if seen != expected_ids:
        raise ValueError("Stage F report set differs from the locked run set")
    if len(commits) != 1 or len(hashes) != 1:
        raise ValueError("Stage F reports mix code or configuration versions")

    scenarios: dict[str, list[dict[str, Any]]] = {}
    for report in reports:
        scenario_id = str(report["fingerprint"]["scenario_id"])
        scenarios.setdefault(scenario_id, []).append(report)
    expected_per_scenario = int(
        config.document["stage_f_confirmatory_validation"]["final_replicate_count"]
    )
    if set(scenarios) != {item.scenario_id for item in expected_specs} or any(
        len(items) != expected_per_scenario for items in scenarios.values()
    ):
        raise ValueError("Stage F scenario cells are incomplete or unbalanced")

    primary_values = [
        float(item["results"]["primary_material_unsafe_acceptance_contrast"])
        for item in reports
    ]
    primary = _estimate_summary(primary_values)
    scenario_primary = {
        scenario_id: _estimate_summary(
            [
                float(item["results"]["primary_material_unsafe_acceptance_contrast"])
                for item in items
            ]
        )
        for scenario_id, items in sorted(scenarios.items())
    }
    equal_weight_mean = float(
        np.mean([item["mean"] for item in scenario_primary.values()])
    )
    if not math.isclose(
        float(primary["mean"]),
        equal_weight_mean,
        rel_tol=0.0,
        abs_tol=1e-15,
    ):
        raise RuntimeError("equal scenario weighting was not preserved")
    coverages = [
        float(item["results"]["methods"]["complete_gate"]["coverage"])
        for item in reports
    ]
    coverage = _estimate_summary(coverages)
    upper_below_zero = float(primary["confidence_interval_upper"]) < 0.0
    floor = float(config.document["guardrails"]["mean_coverage_floor"])
    coverage_passed = float(coverage["mean"]) >= floor

    summary = {
        "schema_version": "1.0",
        "stage": "stage_f_confirmatory_validation_summary",
        "scientific_status": "confirmatory_unblinded_complete",
        "scientific_results_exposed": True,
        "eligible_for_confirmatory_evidence": True,
        "candidate_id": "C002",
        "code_commit": next(iter(commits)),
        "configuration_combined_sha256": next(iter(hashes)),
        "run_count": len(reports),
        "scenario_count": len(scenarios),
        "primary_estimand": {
            "definition": (
                "C002 minus uncertainty-only material unsafe acceptance at "
                "exact matched coverage"
            ),
            "negative_values_favour_C002": True,
            "equal_weight_per_scenario": True,
            "estimate": primary,
            "scenario_estimates": scenario_primary,
        },
        "coverage_guardrail": {
            "minimum_mean_coverage": floor,
            "estimate": coverage,
            "passed": coverage_passed,
        },
        "confirmatory_decision": {
            "upper_95_percent_confidence_limit_below_zero": upper_below_zero,
            "coverage_floor_satisfied": coverage_passed,
            "primary_claim_supported": upper_below_zero and coverage_passed,
        },
        "scenarios": {
            scenario_id: _scenario_summary(items)
            for scenario_id, items in sorted(scenarios.items())
        },
        "secondary_policy_contrasts": _secondary_policy_contrasts(reports),
        "mechanism_ablations": _mechanism_ablations(reports),
        "fairness_audit": {
            "role": "secondary_safety_and_access_audit",
            "fairness_guarantee_claimed": False,
            "weighted_composite_used": False,
            "raw_complete_gate_group_gaps": _group_gap_summary(
                reports,
                audit_name="raw",
            ),
            "evidence_standardised_complete_gate_group_gaps": (
                _group_gap_summary(
                    reports,
                    audit_name="evidence_standardised",
                )
            ),
            "standardisation": _fairness_standardisation_summary(reports),
        },
        "claim_boundary": {
            "controlled_simulation_only": True,
            "clinical_effectiveness_claimed": False,
            "public_trial_validation_still_required": True,
        },
    }
    return _json_safe(summary)


def _confirmatory_invariants(
    construction: Any,
    truth: Any,
    spec: ConfirmatoryRunSpec,
    config: ValidationConfig,
    hashes: dict[str, str],
) -> tuple[InvariantResult, ...]:
    expected_evidence = np.logical_and.reduce(
        [construction.checks[name] for name in _ESSENTIAL_CHECKS]
    )
    expected_complete = (
        expected_evidence & construction.gate.graded_uncertainty_acceptance
    )
    complete = truth.metrics["complete_gate"]
    uncertainty = truth.metrics["uncertainty_only"]
    stage_f = config.document["stage_f_confirmatory_validation"]
    first = int(stage_f["replicate_id_start"])
    last = first + int(stage_f["final_replicate_count"]) - 1
    exact_fold_coverage = all(
        int(construction.gate.complete[construction.fold_ids == fold_id].sum())
        == int(
            construction.uncertainty_only_acceptance[
                construction.fold_ids == fold_id
            ].sum()
        )
        for fold_id in np.unique(construction.fold_ids)
    )
    return (
        InvariantResult(
            "confirmatory_scenario_namespace",
            spec.scenario_id.startswith("confirmatory_v1__"),
        ),
        InvariantResult(
            "confirmatory_replicate_namespace",
            first <= spec.replicate_id <= last,
        ),
        InvariantResult(
            "three_essential_checks",
            construction.gate.essential_checks == _ESSENTIAL_CHECKS,
        ),
        InvariantResult(
            "graded_uncertainty_enabled",
            construction.gate.graded_uncertainty_applied,
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
            "paired_primary_contrast_definition",
            math.isclose(
                truth.primary_material_unsafe_acceptance_contrast,
                complete.material_unsafe_acceptance
                - uncertainty.material_unsafe_acceptance,
                rel_tol=0.0,
                abs_tol=1e-15,
            ),
        ),
        InvariantResult(
            "locked_configuration_hashes_complete",
            set(hashes)
            == {
                "analysis",
                "simulation",
                "candidate_effective_analysis",
                "validation",
                "combined",
            },
        ),
        InvariantResult(
            "weighted_fairness_composite_absent",
            config.document["guardrails"]["weighted_fairness_composite"] is False,
        ),
    )


def _secondary_policy_contrasts(
    reports: list[dict[str, Any]],
) -> dict[str, dict[str, float | int | None]]:
    def method_difference(
        left: str,
        right: str,
        metric: str,
    ) -> list[float]:
        return [
            float(item["results"]["methods"][left][metric])
            - float(item["results"]["methods"][right][metric])
            for item in reports
        ]

    return {
        "utility_C002_minus_uncertainty_only": _estimate_summary(
            method_difference(
                "complete_gate",
                "uncertainty_only",
                "deployed_policy_utility",
            )
        ),
        "utility_C002_minus_population_default": _estimate_summary(
            method_difference(
                "complete_gate",
                "population_default",
                "deployed_policy_utility",
            )
        ),
        "utility_C002_minus_ungated_individualisation": _estimate_summary(
            method_difference(
                "complete_gate",
                "ungated_individualisation",
                "deployed_policy_utility",
            )
        ),
        "unsafe_acceptance_C002_minus_matched_random": _estimate_summary(
            [
                float(
                    item["results"]["methods"]["complete_gate"][
                        "material_unsafe_acceptance"
                    ]
                )
                - float(
                    item["results"]["random_deferral"][
                        "mean_material_unsafe_acceptance"
                    ]
                )
                for item in reports
            ]
        ),
        "utility_C002_minus_matched_random": _estimate_summary(
            [
                float(
                    item["results"]["methods"]["complete_gate"][
                        "deployed_policy_utility"
                    ]
                )
                - float(
                    item["results"]["random_deferral"]["mean_deployed_policy_utility"]
                )
                for item in reports
            ]
        ),
    }


def _mechanism_ablations(reports: list[dict[str, Any]]) -> dict[str, Any]:
    raw: dict[str, dict[str, Any]] = {}
    p_values: dict[str, float] = {}
    for check in _ESSENTIAL_CHECKS:
        method = f"without_{check}"
        values = [
            float(
                item["results"]["methods"]["complete_gate"][
                    "material_unsafe_acceptance"
                ]
            )
            - float(item["results"]["methods"][method]["material_unsafe_acceptance"])
            for item in reports
        ]
        estimate = _estimate_summary(values)
        p_value = _two_sided_one_sample_p_value(values)
        raw[check] = {
            "contrast": "C002_minus_leave_one_check_out",
            "negative_values_support_a_safety_contribution": True,
            "estimate": estimate,
            "p_value_unadjusted": p_value,
        }
        p_values[check] = p_value
    adjusted = _holm_adjust(p_values)
    for check in _ESSENTIAL_CHECKS:
        raw[check]["p_value_holm"] = adjusted[check]
    return {
        "multiplicity_adjustment": "Holm_across_three_essential_checks",
        "comparisons": raw,
    }


def _two_sided_one_sample_p_value(values: list[float]) -> float:
    array = np.asarray(values, dtype=float)
    if array.size < 2 or not np.isfinite(array).all():
        raise ValueError("mechanism p-value requires at least two finite values")
    standard_deviation = float(array.std(ddof=1))
    mean = float(array.mean())
    if standard_deviation == 0.0:
        return 1.0 if mean == 0.0 else 0.0
    statistic = mean / (standard_deviation / math.sqrt(array.size))
    return float(2.0 * student_t.sf(abs(statistic), df=array.size - 1))


def _holm_adjust(p_values: dict[str, float]) -> dict[str, float]:
    ordered = sorted(p_values, key=p_values.get)
    total = len(ordered)
    result: dict[str, float] = {}
    running = 0.0
    for position, name in enumerate(ordered):
        candidate = min(1.0, (total - position) * p_values[name])
        running = max(running, candidate)
        result[name] = running
    return result
