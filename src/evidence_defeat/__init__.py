"""Evidence-defeat framework for responsible treatment-policy deferral."""

from evidence_defeat.checks import (
    DecisionCertaintyResult,
    ModelMultiplicityResult,
    RecordAdequacyResult,
    ReferenceSupportResult,
    decision_certainty_check,
    model_multiplicity_check,
    record_adequacy_check,
    reference_support_check,
)
from evidence_defeat.config import ProjectConfig, load_project_config
from evidence_defeat.selection import (
    GateSelections,
    apply_deferral_policy,
    construct_gate,
    match_coverage_within_folds,
    uncertainty_only_at_matched_coverage,
)
from evidence_defeat.simulation import (
    SimulationData,
    SimulationScenario,
    generate_simulation,
)

__version__ = "0.1.0"

__all__ = [
    "DecisionCertaintyResult",
    "GateSelections",
    "ModelMultiplicityResult",
    "ProjectConfig",
    "RecordAdequacyResult",
    "ReferenceSupportResult",
    "SimulationData",
    "SimulationScenario",
    "apply_deferral_policy",
    "construct_gate",
    "decision_certainty_check",
    "generate_simulation",
    "load_project_config",
    "match_coverage_within_folds",
    "model_multiplicity_check",
    "record_adequacy_check",
    "reference_support_check",
    "uncertainty_only_at_matched_coverage",
]
