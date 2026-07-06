"""celltwin -- a cell digital twin for toxicology screening.

Hybrid engine: a typed relation graph (what a toxin perturbs) coupled to a
mechanistic ODE core (how the perturbation plays out over time), producing
viability, dose-response, mechanism attribution, and combination-synergy
readouts. See docs/PLAN.md.
"""

from .schemas import (
    CellModel,
    Exposure,
    SimulationRequest,
    SimulationResult,
    Toxin,
)

__version__ = "0.1.0"

__all__ = [
    "CellModel",
    "Toxin",
    "Exposure",
    "SimulationRequest",
    "SimulationResult",
    "__version__",
]
