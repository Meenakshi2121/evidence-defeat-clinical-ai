"""Evidence-defeat framework for responsible treatment-policy deferral."""

from evidence_defeat.config import ProjectConfig, load_project_config
from evidence_defeat.simulation import (
    SimulationData,
    SimulationScenario,
    generate_simulation,
)

__version__ = "0.1.0"

__all__ = [
    "ProjectConfig",
    "SimulationData",
    "SimulationScenario",
    "generate_simulation",
    "load_project_config",
]
