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
from evidence_defeat.folds import OuterFold, iter_outer_folds, make_outer_fold_ids
from evidence_defeat.learners import (
    ESTIMATOR_ORDER,
    LearnerSeeds,
    TreatmentEffectPredictions,
    fit_predict_prespecified_learners,
)
from evidence_defeat.preprocessing import (
    CovariateSchema,
    FittedPreprocessor,
    fit_preprocessor,
    observed_covariate_mask,
)
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
    "ESTIMATOR_ORDER",
    "CovariateSchema",
    "DecisionCertaintyResult",
    "FittedPreprocessor",
    "GateSelections",
    "LearnerSeeds",
    "ModelMultiplicityResult",
    "OuterFold",
    "ProjectConfig",
    "RecordAdequacyResult",
    "ReferenceSupportResult",
    "SimulationData",
    "SimulationScenario",
    "TreatmentEffectPredictions",
    "apply_deferral_policy",
    "construct_gate",
    "decision_certainty_check",
    "fit_predict_prespecified_learners",
    "fit_preprocessor",
    "generate_simulation",
    "iter_outer_folds",
    "load_project_config",
    "make_outer_fold_ids",
    "match_coverage_within_folds",
    "model_multiplicity_check",
    "observed_covariate_mask",
    "record_adequacy_check",
    "reference_support_check",
    "uncertainty_only_at_matched_coverage",
]
