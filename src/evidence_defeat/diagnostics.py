"""Disclosure-safe orchestration for pre-lock proof-of-concept runs."""

from __future__ import annotations

import hashlib
import inspect
import json
import math
import os
import platform
import re
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from numpy.typing import NDArray

from evidence_defeat.config import ProjectConfig
from evidence_defeat.evaluation import evaluate_cross_fitted_policies
from evidence_defeat.folds import make_outer_fold_ids
from evidence_defeat.known_truth import (
    KnownTruthEvaluation,
    RandomDeferralKnownTruthEvaluation,
    evaluate_cross_fitted_known_truth,
    evaluate_random_deferral_known_truth,
)
from evidence_defeat.pipeline import (
    CrossFittedConstruction,
    construct_outer_fold,
    run_cross_fitted_construction,
)
from evidence_defeat.preprocessing import CovariateSchema
from evidence_defeat.seeds import named_generators
from evidence_defeat.simulation import (
    SimulationData,
    SimulationScenario,
    generate_simulation,
)

SMOKE_SCENARIO_DEFECTS = {
    "clean_control": "clean_control",
    "record_adequacy": "record_adequacy",
    "reference_support": "reference_support",
    "model_multiplicity": "model_multiplicity",
    "decision_uncertainty": "decision_uncertainty",
    "combined": "combined",
}

PACKAGE_DISTRIBUTIONS = (
    "evidence-defeat-clinical-ai",
    "econml",
    "numpy",
    "pandas",
    "scipy",
    "scikit-learn",
    "statsmodels",
    "PyYAML",
)

_COMMIT_PATTERN = re.compile(r"^[0-9a-f]{40}(?:[0-9a-f]{24})?$")


@dataclass(frozen=True)
class SmokeRunSpec:
    """One run authorised by the diagnostic-only Stage A configuration."""

    scenario_name: str
    scenario: SimulationScenario
    run_id: str


@dataclass(frozen=True)
class GitState:
    """Repository identity recorded before a diagnostic run."""

    commit: str
    branch: str
    clean: bool


@dataclass(frozen=True)
class InvariantResult:
    """One required software property and its Boolean status."""

    name: str
    passed: bool


@dataclass(frozen=True)
class RunFingerprint:
    """Inputs and environment needed to identify one diagnostic run."""

    scenario_id: str
    scenario_name: str
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
class ResourceUsage:
    """Non-scientific timing and environment information."""

    wall_clock_seconds: float
    process_peak_rss_mb_at_completion: float | None
    cpu_count: int | None
    operating_system: str
    machine: str
    python_version: str
    package_versions: dict[str, str]


@dataclass(frozen=True)
class DiagnosticRunReport:
    """Disclosure-safe result of one proof-of-concept run."""

    schema_version: str
    stage: str
    scientific_status: str
    eligible_for_paper_effect_estimates: bool
    started_at_utc: str
    completed_at_utc: str
    passed: bool
    fingerprint: RunFingerprint
    resource_usage: ResourceUsage
    invariants: tuple[InvariantResult, ...]

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible report with no scientific estimates."""

        return asdict(self)


def canonical_sha256(value: Any) -> str:
    """Hash a JSON-compatible value using one canonical representation."""

    encoded = json.dumps(
        value,
        sort_keys=True,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def configuration_hashes(project: ProjectConfig) -> dict[str, str]:
    """Hash every configuration document and their labelled combination."""

    documents = {
        "analysis": project.analysis,
        "simulation": project.simulation,
        "poc": project.poc,
        "development_validation": project.development_validation,
    }
    result = {name: canonical_sha256(value) for name, value in documents.items()}
    result["combined"] = canonical_sha256(documents)
    return result


def plan_smoke_runs(project: ProjectConfig) -> tuple[SmokeRunSpec, ...]:
    """Expand the frozen Stage A scenario and replicate grid."""

    smoke = project.poc["software_smoke"]
    sample_size = _positive_integer("software_smoke.sample_size", smoke["sample_size"])
    scenario_names = smoke["scenarios"]
    replicate_ids = smoke["replicate_ids"]
    if not isinstance(scenario_names, list) or not scenario_names:
        raise ValueError("software_smoke.scenarios must be a non-empty list")
    if len(set(scenario_names)) != len(scenario_names):
        raise ValueError("software_smoke.scenarios must not contain duplicates")
    unknown = set(scenario_names) - set(SMOKE_SCENARIO_DEFECTS)
    if unknown:
        raise ValueError(f"unsupported smoke scenarios: {sorted(unknown)}")
    if not isinstance(replicate_ids, list) or not replicate_ids:
        raise ValueError("software_smoke.replicate_ids must be a non-empty list")
    if len(set(replicate_ids)) != len(replicate_ids):
        raise ValueError("software_smoke.replicate_ids must not contain duplicates")

    defaults = project.simulation["scenario_defaults"]
    specs = []
    for scenario_name in scenario_names:
        for raw_replicate_id in replicate_ids:
            replicate_id = _non_negative_integer(
                "software_smoke.replicate_id", raw_replicate_id
            )
            scenario_id = f"poc_smoke_{scenario_name}_n{sample_size}"
            scenario = SimulationScenario(
                scenario_id=scenario_id,
                sample_size=sample_size,
                defect=SMOKE_SCENARIO_DEFECTS[scenario_name],
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
            run_id = f"stage_a__{scenario_id}__replicate_{replicate_id}"
            specs.append(SmokeRunSpec(scenario_name, scenario, run_id))
    return tuple(specs)


def select_smoke_run(
    project: ProjectConfig,
    scenario_name: str,
    replicate_id: int,
) -> SmokeRunSpec:
    """Resolve exactly one authorised Stage A run."""

    matches = [
        spec
        for spec in plan_smoke_runs(project)
        if spec.scenario_name == scenario_name
        and spec.scenario.replicate_id == replicate_id
    ]
    if len(matches) != 1:
        raise ValueError("scenario and replicate are not in the Stage A plan")
    return matches[0]


def repository_state(project_root: str | Path) -> GitState:
    """Read the full Git commit, branch and cleanliness without mutating Git."""

    root = Path(project_root).resolve()
    commit = _git_output(root, "rev-parse", "HEAD")
    branch = _git_output(root, "rev-parse", "--abbrev-ref", "HEAD")
    status = _git_output(
        root,
        "status",
        "--porcelain=v1",
        "--untracked-files=all",
        strip=False,
    )
    if not _COMMIT_PATTERN.fullmatch(commit):
        raise RuntimeError("Git did not return a full SHA-1 or SHA-256 commit")
    return GitState(commit=commit, branch=branch, clean=not status.strip())


def execute_diagnostic_run(
    project: ProjectConfig,
    spec: SmokeRunSpec,
    *,
    code_commit: str,
    git_branch: str,
    repository_clean_at_start: bool,
) -> DiagnosticRunReport:
    """Execute one complete Stage A replicate and expose diagnostics only."""

    if not _COMMIT_PATTERN.fullmatch(code_commit):
        raise ValueError("code_commit must be a full lowercase Git commit hash")
    if not git_branch:
        raise ValueError("git_branch must not be empty")
    if repository_clean_at_start is not True:
        raise RuntimeError("diagnostic runs require a clean Git repository")

    started = datetime.now(UTC)
    start_counter = time.perf_counter()
    generated = generate_simulation(spec.scenario, project.simulation)
    repeated = generate_simulation(spec.scenario, project.simulation)
    alternate_scenario = SimulationScenario(
        **{
            **asdict(spec.scenario),
            "replicate_id": spec.scenario.replicate_id + 1_000_000,
        }
    )
    alternate = generate_simulation(alternate_scenario, project.simulation)

    frame = generated.observed
    schema = CovariateSchema(
        continuous=tuple(f"x{number}" for number in range(1, 11)),
        categorical=("group",),
    )
    covariates = frame.loc[:, list(schema.columns)]
    outcome = frame["outcome"].to_numpy()
    treatment = frame["treatment"].to_numpy()
    row_ids = frame["row_id"].to_numpy()
    construction = run_cross_fitted_construction(
        covariates,
        outcome,
        treatment,
        row_ids,
        schema=schema,
        trial_id="controlled_simulation",
        run_id=spec.run_id,
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
    known_truth = evaluate_cross_fitted_known_truth(
        construction,
        evaluation,
        generated.mu0,
        generated.mu1,
        analysis_config=project.analysis,
    )
    random_truth = evaluate_random_deferral_known_truth(
        construction,
        evaluation,
        generated.mu0,
        generated.mu1,
        analysis_config=project.analysis,
    )

    config_hashes = configuration_hashes(project)
    fingerprint = RunFingerprint(
        scenario_id=spec.scenario.scenario_id,
        scenario_name=spec.scenario_name,
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
    invariants = _evaluate_invariants(
        project,
        generated,
        repeated,
        alternate,
        construction,
        known_truth,
        random_truth,
        fingerprint,
    )
    completed = datetime.now(UTC)
    elapsed = time.perf_counter() - start_counter
    report = DiagnosticRunReport(
        schema_version="0.1",
        stage="software_smoke",
        scientific_status="diagnostic_only_prelock",
        eligible_for_paper_effect_estimates=False,
        started_at_utc=started.isoformat().replace("+00:00", "Z"),
        completed_at_utc=completed.isoformat().replace("+00:00", "Z"),
        passed=all(item.passed for item in invariants),
        fingerprint=fingerprint,
        resource_usage=ResourceUsage(
            wall_clock_seconds=elapsed,
            process_peak_rss_mb_at_completion=process_peak_rss_mb(),
            cpu_count=os.cpu_count(),
            operating_system=f"{platform.system()} {platform.release()}",
            machine=platform.machine(),
            python_version=platform.python_version(),
            package_versions=package_versions(),
        ),
        invariants=invariants,
    )
    assert_disclosure_safe_report(report.to_dict())
    return report


def simulation_data_sha256(data: SimulationData) -> str:
    """Hash all generated observed and latent arrays without serialising them."""

    digest = hashlib.sha256()
    digest.update(
        json.dumps(
            asdict(data.scenario),
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    )
    digest.update(str(data.seed).encode("ascii"))
    _update_frame_digest(digest, data.observed)
    _update_array_digest(digest, "latent_covariates", data.latent_covariates)
    _update_array_digest(digest, "complete_covariates", data.complete_covariates)
    _update_frame_digest(digest, data.defects)
    _update_array_digest(digest, "record_completeness", data.record_completeness)
    _update_array_digest(digest, "mu0", data.mu0)
    _update_array_digest(digest, "mu1", data.mu1)
    _update_array_digest(digest, "tau_target", data.tau_target)
    _update_array_digest(digest, "tau_true", data.tau_true)
    _update_array_digest(digest, "optimal_action", data.optimal_action)
    if data.materially_actionable is not None:
        _update_array_digest(
            digest,
            "materially_actionable",
            data.materially_actionable,
        )
    return digest.hexdigest()


def array_sha256(values: NDArray[Any]) -> str:
    """Hash an array after stable dtype normalisation."""

    digest = hashlib.sha256()
    _update_array_digest(digest, "array", np.asarray(values))
    return digest.hexdigest()


def write_json_atomic(path: str | Path, payload: dict[str, Any]) -> None:
    """Write formatted JSON by atomic replacement and refuse non-finite values."""

    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    encoded = json.dumps(
        payload,
        sort_keys=True,
        indent=2,
        allow_nan=False,
    )
    temporary.write_text(encoded + "\n", encoding="utf-8")
    temporary.replace(destination)


def _evaluate_invariants(
    project: ProjectConfig,
    generated: SimulationData,
    repeated: SimulationData,
    alternate: SimulationData,
    construction: CrossFittedConstruction,
    known_truth: KnownTruthEvaluation,
    random_truth: RandomDeferralKnownTruthEvaluation,
    fingerprint: RunFingerprint,
) -> tuple[InvariantResult, ...]:
    n = generated.scenario.sample_size
    same_generation = simulation_data_sha256(generated) == simulation_data_sha256(
        repeated
    )
    configured_probability = float(
        project.simulation["scenario_defaults"]["treatment_probability"]
    )
    regenerated_treatment = (
        named_generators(generated.seed)["treatment"]
        .binomial(1, configured_probability, size=n)
        .astype(np.int8)
    )
    observed_treatment = generated.observed["treatment"].to_numpy(dtype=np.int8)
    expected_folds = make_outer_fold_ids(
        observed_treatment,
        generated.observed["row_id"].to_numpy(),
        n_splits=int(project.analysis["cross_fitting"]["outer_folds"]),
        seed=int(project.analysis["cross_fitting"]["primary_seed"]),
    )
    fold_reproducible = np.array_equal(expected_folds, construction.fold_ids)
    different_stream = generated.seed != alternate.seed and simulation_data_sha256(
        generated
    ) != simulation_data_sha256(alternate)

    if generated.scenario.outcome_type == "binary":
        mean_domain = bool(
            np.all((generated.mu0 >= 0.01) & (generated.mu0 <= 0.99))
            and np.all((generated.mu1 >= 0.01) & (generated.mu1 <= 0.99))
        )
        expected_margin = float(
            project.analysis["outcome"]["binary_materiality_margin"]
        )
        aligned_margin = np.allclose(known_truth.materiality_margin, expected_margin)
    else:
        mean_domain = bool(
            np.isfinite(generated.mu0).all() and np.isfinite(generated.mu1).all()
        )
        expected_margins = np.full(n, np.nan)
        margin_sd = float(
            project.analysis["outcome"]["continuous_materiality_margin_sd"]
        )
        for fold in construction.folds:
            expected_margins[construction.fold_ids == fold.fold_id] = (
                margin_sd * fold.outcome_scaling.scale
            )
        aligned_margin = np.allclose(
            known_truth.materiality_margin,
            expected_margins,
        )

    construction_parameters = inspect.signature(construct_outer_fold).parameters
    no_heldout_outcome_interface = not {
        "heldout_outcome",
        "heldout_utility",
    }.intersection(construction_parameters)
    checks_boolean = all(
        values.dtype == np.bool_ and values.shape == (n,)
        for values in construction.checks.values()
    )
    expected_gate = np.logical_and.reduce(list(construction.checks.values()))
    logical_and_gate = checks_boolean and np.array_equal(
        construction.gate.complete,
        expected_gate,
    )

    uncertainty_matches = _selection_matches_by_fold(
        construction.uncertainty_only_acceptance[None, :],
        construction.gate.complete,
        construction.fold_ids,
    )
    random_matches = _selection_matches_by_fold(
        random_truth.selections.acceptance,
        construction.gate.complete,
        construction.fold_ids,
    )
    denominator_correct = all(
        math.isclose(
            item.material_unsafe_acceptance,
            item.unsafe_accepted_count / item.sample_size,
            rel_tol=0.0,
            abs_tol=1e-15,
        )
        for item in (
            *known_truth.metrics.values(),
            *random_truth.metrics,
        )
    )
    fingerprint_complete = (
        bool(fingerprint.scenario_id)
        and bool(fingerprint.run_id)
        and fingerprint.sample_size == n
        and fingerprint.replicate_seed == generated.seed
        and set(fingerprint.configuration_sha256)
        == {
            "analysis",
            "simulation",
            "poc",
            "development_validation",
            "combined",
        }
        and all(
            re.fullmatch(r"[0-9a-f]{64}", value)
            for value in fingerprint.configuration_sha256.values()
        )
        and bool(re.fullmatch(r"[0-9a-f]{64}", fingerprint.generated_data_sha256))
        and bool(re.fullmatch(r"[0-9a-f]{64}", fingerprint.fold_assignments_sha256))
        and bool(_COMMIT_PATTERN.fullmatch(fingerprint.code_commit))
        and fingerprint.repository_clean_at_start
    )

    return (
        InvariantResult(
            "same_seed_reproduces_generated_arrays",
            same_generation,
        ),
        InvariantResult("fold_assignments_are_deterministic", fold_reproducible),
        InvariantResult(
            "different_replicate_identifier_changes_stream",
            different_stream,
        ),
        InvariantResult("conditional_means_have_valid_domain", mean_domain),
        InvariantResult(
            "treatment_uses_independent_half_probability_stream",
            configured_probability == 0.5
            and np.array_equal(regenerated_treatment, observed_treatment),
        ),
        InvariantResult(
            "heldout_outcomes_absent_from_gate_fold_interface",
            no_heldout_outcome_interface,
        ),
        InvariantResult(
            "uncertainty_comparator_matches_coverage_within_fold",
            uncertainty_matches,
        ),
        InvariantResult(
            "random_comparator_matches_coverage_within_fold",
            random_matches,
        ),
        InvariantResult("complete_gate_is_boolean_logical_and", logical_and_gate),
        InvariantResult(
            "unsafe_acceptance_uses_population_denominator",
            denominator_correct,
        ),
        InvariantResult(
            "truth_and_estimates_use_aligned_materiality_scale",
            bool(aligned_margin),
        ),
        InvariantResult("run_fingerprint_is_complete", fingerprint_complete),
    )


def _selection_matches_by_fold(
    selections: NDArray[np.bool_],
    target: NDArray[np.bool_],
    fold_ids: NDArray[np.int16],
) -> bool:
    if selections.ndim != 2 or selections.shape[1] != target.shape[0]:
        return False
    for fold_id in np.unique(fold_ids):
        in_fold = fold_ids == fold_id
        target_count = int(target[in_fold].sum())
        if not np.all(selections[:, in_fold].sum(axis=1) == target_count):
            return False
    return True


def assert_disclosure_safe_report(payload: dict[str, Any]) -> None:
    """Reject diagnostic payloads containing scientific result fields."""

    forbidden_keys = {
        "metrics",
        "policy_values",
        "method_rankings",
        "primary_contrast",
        "coverage",
        "unsafe_acceptance_rate",
        "utility",
        "regret",
        "effect_estimate",
    }
    present = _all_mapping_keys(payload).intersection(forbidden_keys)
    if present:
        raise RuntimeError(f"diagnostic report exposes scientific fields: {present}")


def _all_mapping_keys(value: Any) -> set[str]:
    if isinstance(value, dict):
        keys = {str(key) for key in value}
        for item in value.values():
            keys.update(_all_mapping_keys(item))
        return keys
    if isinstance(value, (list, tuple)):
        keys: set[str] = set()
        for item in value:
            keys.update(_all_mapping_keys(item))
        return keys
    return set()


def _git_output(
    root: Path,
    *arguments: str,
    strip: bool = True,
) -> str:
    completed = subprocess.run(
        ["git", *arguments],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip() if strip else completed.stdout


def package_versions() -> dict[str, str]:
    """Return the reproducibility package-version fingerprint."""

    versions = {}
    for distribution in PACKAGE_DISTRIBUTIONS:
        try:
            versions[distribution] = version(distribution)
        except PackageNotFoundError:
            if distribution == "evidence-defeat-clinical-ai":
                versions[distribution] = "source-tree"
            else:  # pragma: no cover - locked runtime contains all dependencies
                versions[distribution] = "not-installed"
    return versions


def process_peak_rss_mb() -> float | None:
    """Return the current process peak resident memory on Linux."""

    if sys.platform.startswith("linux"):
        status_path = Path("/proc/self/status")
        try:
            for line in status_path.read_text(encoding="utf-8").splitlines():
                if line.startswith("VmHWM:"):
                    return float(line.split()[1]) / 1024.0
        except OSError:  # pragma: no cover - unusual Linux container
            return None
    return None


def _update_frame_digest(digest: Any, frame: pd.DataFrame) -> None:
    digest.update(
        json.dumps(list(map(str, frame.columns)), separators=(",", ":")).encode("utf-8")
    )
    for column in frame.columns:
        _update_array_digest(digest, str(column), frame[column].to_numpy())


def _update_array_digest(digest: Any, name: str, values: NDArray[Any]) -> None:
    array = np.asarray(values)
    digest.update(name.encode("utf-8"))
    digest.update(json.dumps(list(array.shape), separators=(",", ":")).encode("ascii"))
    if array.dtype.kind == "b":
        normalised = np.ascontiguousarray(array.astype(np.uint8))
        kind = "bool"
        payload = normalised.tobytes()
    elif array.dtype.kind in "iu":
        normalised = np.ascontiguousarray(array.astype("<i8"))
        kind = "integer"
        payload = normalised.tobytes()
    elif array.dtype.kind in "fc":
        normalised = np.ascontiguousarray(array.astype("<f8"))
        normalised[np.isnan(normalised)] = np.nan
        kind = "float64"
        payload = normalised.tobytes()
    else:
        kind = "string"
        payload = json.dumps(
            array.astype(str).ravel().tolist(),
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
    digest.update(kind.encode("ascii"))
    digest.update(payload)


def _positive_integer(name: str, value: Any) -> int:
    integer = _non_negative_integer(name, value)
    if integer < 1:
        raise ValueError(f"{name} must be positive")
    return integer


def _non_negative_integer(name: str, value: Any) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")
    return value
