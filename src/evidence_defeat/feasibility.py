"""Disclosure-safe Stage B comparator and bootstrap timing runs."""

from __future__ import annotations

import os
import platform
import re
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any, Literal

import numpy as np
import pandas as pd
from numpy.typing import NDArray

from evidence_defeat.bootstrap import treatment_stratified_bootstrap
from evidence_defeat.config import ProjectConfig
from evidence_defeat.diagnostics import (
    InvariantResult,
    ResourceUsage,
    array_sha256,
    assert_disclosure_safe_report,
    configuration_hashes,
    package_versions,
    process_peak_rss_mb,
    simulation_data_sha256,
)
from evidence_defeat.evaluation import (
    aipw_policy_contributions,
    evaluate_cross_fitted_policies,
)
from evidence_defeat.pipeline import run_cross_fitted_construction
from evidence_defeat.policy_disagreement import (
    CrossFittedPolicyDisagreement,
    run_cross_fitted_policy_disagreement,
)
from evidence_defeat.preprocessing import CovariateSchema
from evidence_defeat.seeds import derive_model_seed
from evidence_defeat.selection import apply_deferral_policy
from evidence_defeat.simulation import (
    SimulationData,
    SimulationScenario,
    generate_simulation,
)

TimingComponent = Literal["full_comparator", "full_pipeline_bootstrap"]
_COMMIT_PATTERN = re.compile(r"^[0-9a-f]{40}(?:[0-9a-f]{24})?$")


@dataclass(frozen=True)
class TimingRunSpec:
    """One authorised disclosure-safe Stage B timing unit."""

    timing_id: str
    component: TimingComponent
    scenario: SimulationScenario
    bootstrap_repetition: int | None


@dataclass(frozen=True)
class TimingFingerprint:
    """Inputs identifying one Stage B timing unit."""

    timing_id: str
    component: str
    scenario_id: str
    sample_size: int
    replicate_id: int
    replicate_seed: int
    bootstrap_repetition: int | None
    configuration_sha256: dict[str, str]
    generated_data_sha256: str
    resample_indices_sha256: str | None
    fold_assignments_sha256: str
    code_commit: str
    git_branch: str
    repository_clean_at_start: bool


@dataclass(frozen=True)
class TimingRunReport:
    """Disclosure-safe resource and invariant report for one timing unit."""

    schema_version: str
    stage: str
    scientific_status: str
    eligible_for_paper_effect_estimates: bool
    started_at_utc: str
    completed_at_utc: str
    passed: bool
    fingerprint: TimingFingerprint
    resource_usage: ResourceUsage
    invariants: tuple[InvariantResult, ...]

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible report with scientific results omitted."""

        return asdict(self)


def plan_stage_b_runs(project: ProjectConfig) -> tuple[TimingRunSpec, ...]:
    """Expand the exact Stage B units declared in the POC configuration."""

    defaults = project.simulation["scenario_defaults"]
    timing = project.poc["full_comparator_timing"]
    bootstrap = project.poc["bootstrap_timing"]
    if timing["scenarios"] != ["combined"]:
        raise ValueError("Stage B comparator timing must use only combined")
    if timing["replicate_ids"] != [900001]:
        raise ValueError("Stage B comparator replicate identifier has changed")
    if bootstrap["scenario"] != "combined":
        raise ValueError("Stage B bootstrap timing must use combined")

    result: list[TimingRunSpec] = []
    for sample_size in timing["sample_sizes"]:
        scenario = _timing_scenario(
            defaults,
            sample_size=int(sample_size),
            replicate_id=900001,
            scenario_id=f"poc_timing_combined_n{int(sample_size)}",
        )
        result.append(
            TimingRunSpec(
                timing_id=f"full_comparator_n{int(sample_size)}",
                component="full_comparator",
                scenario=scenario,
                bootstrap_repetition=None,
            )
        )

    repetitions = int(bootstrap["bootstrap_repetitions"])
    for repetition_id in range(repetitions):
        sample_size = int(bootstrap["sample_size"])
        scenario = _timing_scenario(
            defaults,
            sample_size=sample_size,
            replicate_id=int(bootstrap["replicate_id"]),
            scenario_id=f"poc_bootstrap_combined_n{sample_size}",
        )
        result.append(
            TimingRunSpec(
                timing_id=f"full_pipeline_bootstrap_{repetition_id}",
                component="full_pipeline_bootstrap",
                scenario=scenario,
                bootstrap_repetition=repetition_id,
            )
        )
    return tuple(result)


def select_stage_b_run(project: ProjectConfig, timing_id: str) -> TimingRunSpec:
    """Resolve exactly one authorised Stage B timing identifier."""

    matches = [
        spec for spec in plan_stage_b_runs(project) if spec.timing_id == timing_id
    ]
    if len(matches) != 1:
        raise ValueError("timing_id is not in the Stage B plan")
    return matches[0]


def execute_timing_run(
    project: ProjectConfig,
    spec: TimingRunSpec,
    *,
    code_commit: str,
    git_branch: str,
    repository_clean_at_start: bool,
) -> TimingRunReport:
    """Execute one complete Stage B timing unit and conceal method results."""

    if not _COMMIT_PATTERN.fullmatch(code_commit):
        raise ValueError("code_commit must be a full lowercase Git commit hash")
    if not git_branch:
        raise ValueError("git_branch must not be empty")
    if repository_clean_at_start is not True:
        raise RuntimeError("timing runs require a clean Git repository")

    started = datetime.now(UTC)
    start_counter = time.perf_counter()
    generated = generate_simulation(spec.scenario, project.simulation)
    frame, row_ids, resample_hash, bootstrap_invariants = _analysis_sample(
        generated,
        spec,
        project,
    )
    schema = CovariateSchema(
        continuous=tuple(f"x{number}" for number in range(1, 11)),
        categorical=("group",),
    )
    covariates = frame.loc[:, list(schema.columns)]
    outcome = frame["outcome"].to_numpy()
    treatment = frame["treatment"].to_numpy(dtype=np.int8)
    run_id = f"stage_b__{spec.timing_id}"
    construction = run_cross_fitted_construction(
        covariates,
        outcome,
        treatment,
        row_ids,
        schema=schema,
        trial_id="controlled_simulation",
        run_id=run_id,
        outcome_type=spec.scenario.outcome_type,
        analysis_config=project.analysis,
    )
    evaluation = evaluate_cross_fitted_policies(
        construction,
        covariates,
        outcome,
        treatment,
        row_ids,
        schema=schema,
        outcome_type=spec.scenario.outcome_type,
        analysis_config=project.analysis,
        documented_treatment_probability=0.5,
    )
    disagreement = run_cross_fitted_policy_disagreement(
        construction,
        evaluation,
        covariates,
        outcome,
        treatment,
        row_ids,
        schema=schema,
        outcome_type=spec.scenario.outcome_type,
        analysis_config=project.analysis,
    )
    deployed = apply_deferral_policy(
        disagreement.acceptance,
        construction.individualised_action,
        evaluation.default_action,
    )
    comparator_scores = aipw_policy_contributions(
        deployed,
        evaluation.scaled_utility,
        treatment,
        evaluation.mu0,
        evaluation.mu1,
        evaluation.propensity_treatment_1,
    )

    fingerprint = TimingFingerprint(
        timing_id=spec.timing_id,
        component=spec.component,
        scenario_id=spec.scenario.scenario_id,
        sample_size=spec.scenario.sample_size,
        replicate_id=spec.scenario.replicate_id,
        replicate_seed=generated.seed,
        bootstrap_repetition=spec.bootstrap_repetition,
        configuration_sha256=configuration_hashes(project),
        generated_data_sha256=simulation_data_sha256(generated),
        resample_indices_sha256=resample_hash,
        fold_assignments_sha256=array_sha256(construction.fold_ids),
        code_commit=code_commit,
        git_branch=git_branch,
        repository_clean_at_start=repository_clean_at_start,
    )
    invariants = (
        *bootstrap_invariants,
        *_timing_invariants(
            project,
            construction.gate.complete,
            construction.fold_ids,
            disagreement,
            comparator_scores,
            fingerprint,
        ),
    )
    completed = datetime.now(UTC)
    report = TimingRunReport(
        schema_version="0.1",
        stage="computational_feasibility",
        scientific_status="diagnostic_only_prelock",
        eligible_for_paper_effect_estimates=False,
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
            python_version=platform.python_version(),
            package_versions=package_versions(),
        ),
        invariants=invariants,
    )
    payload = report.to_dict()
    assert_disclosure_safe_report(payload)
    return report


def _analysis_sample(
    generated: SimulationData,
    spec: TimingRunSpec,
    project: ProjectConfig,
) -> tuple[pd.DataFrame, NDArray[np.str_], str | None, tuple[InvariantResult, ...]]:
    frame = generated.observed.copy()
    original_treatment = frame["treatment"].to_numpy(dtype=np.int8)
    original_row_ids = frame["row_id"].to_numpy().astype(str)
    if spec.component == "full_comparator":
        return frame, original_row_ids, None, ()
    if spec.bootstrap_repetition is None:  # pragma: no cover - dataclass contract
        raise RuntimeError("bootstrap repetition is missing")

    seed = derive_model_seed(
        int(project.analysis["master_seed"]),
        f"stage_b__{spec.timing_id}",
        spec.bootstrap_repetition,
        "full_pipeline_bootstrap_resample",
    )
    sample = treatment_stratified_bootstrap(
        original_treatment,
        original_row_ids,
        seed=seed,
        repetition_id=spec.bootstrap_repetition,
    )
    resampled = frame.iloc[sample.source_indices].reset_index(drop=True)
    resampled["row_id"] = sample.row_ids
    resampled_treatment = resampled["treatment"].to_numpy(dtype=np.int8)
    expected_counts = np.bincount(original_treatment, minlength=2)
    observed_counts = np.bincount(resampled_treatment, minlength=2)
    invariants = (
        InvariantResult(
            "bootstrap_preserves_treatment_stratum_sizes",
            bool(np.array_equal(expected_counts, observed_counts)),
        ),
        InvariantResult(
            "bootstrap_row_identifiers_are_unique",
            np.unique(sample.row_ids).shape[0] == sample.row_ids.shape[0],
        ),
    )
    return (
        resampled,
        sample.row_ids,
        array_sha256(sample.source_indices),
        invariants,
    )


def _timing_invariants(
    project: ProjectConfig,
    target_acceptance: NDArray[np.bool_],
    fold_ids: NDArray[np.int16],
    disagreement: CrossFittedPolicyDisagreement,
    comparator_scores: NDArray[np.float64],
    fingerprint: TimingFingerprint,
) -> tuple[InvariantResult, ...]:
    matched = True
    for fold_id in np.unique(fold_ids):
        in_fold = fold_ids == fold_id
        matched = matched and (
            disagreement.acceptance[in_fold].sum() == target_acceptance[in_fold].sum()
        )
    expected_candidates = len(
        project.analysis["comparators"]["near_optimal_policy_disagreement"][
            "candidate_learners"
        ]
    ) * int(
        project.analysis["comparators"]["near_optimal_policy_disagreement"][
            "bootstrap_candidates_per_learner"
        ]
    )
    minimum = int(
        project.analysis["comparators"]["near_optimal_policy_disagreement"][
            "minimum_near_optimal_policies"
        ]
    )
    candidate_counts = all(
        fold.candidate_count == expected_candidates for fold in disagreement.folds
    )
    retained_counts = all(fold.retained_count >= minimum for fold in disagreement.folds)
    fingerprint_complete = (
        fingerprint.sample_size == target_acceptance.shape[0]
        and bool(re.fullmatch(r"[0-9a-f]{64}", fingerprint.generated_data_sha256))
        and bool(re.fullmatch(r"[0-9a-f]{64}", fingerprint.fold_assignments_sha256))
        and (
            fingerprint.resample_indices_sha256 is None
            or bool(re.fullmatch(r"[0-9a-f]{64}", fingerprint.resample_indices_sha256))
        )
        and set(fingerprint.configuration_sha256)
        == {"analysis", "simulation", "poc", "combined"}
        and bool(_COMMIT_PATTERN.fullmatch(fingerprint.code_commit))
        and fingerprint.repository_clean_at_start
    )
    return (
        InvariantResult(
            "policy_disagreement_matches_gate_coverage_within_fold",
            bool(matched),
        ),
        InvariantResult(
            "configured_candidate_count_fitted_in_every_fold",
            candidate_counts,
        ),
        InvariantResult(
            "minimum_near_optimal_policy_count_retained",
            retained_counts,
        ),
        InvariantResult(
            "policy_disagreement_scores_are_finite",
            bool(np.isfinite(disagreement.disagreement_score).all()),
        ),
        InvariantResult(
            "comparator_aipw_scores_are_finite",
            bool(np.isfinite(comparator_scores).all()),
        ),
        InvariantResult("timing_fingerprint_is_complete", fingerprint_complete),
    )


def _timing_scenario(
    defaults: dict[str, Any],
    *,
    sample_size: int,
    replicate_id: int,
    scenario_id: str,
) -> SimulationScenario:
    return SimulationScenario(
        scenario_id=scenario_id,
        sample_size=sample_size,
        defect="combined",
        replicate_id=replicate_id,
        outcome_type=defaults["outcome_type"],
        baseline_shape=defaults["baseline_shape"],
        effect_strength=defaults["effect_strength"],
        group_prevalence=float(defaults["group_prevalence"]),
        defect_allocation=defaults["defect_allocation"],
        group_prognostic_coefficient=float(
            defaults.get("baseline_group_coefficient", 0.0)
        ),
    )
