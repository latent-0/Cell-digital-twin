"""Typed schemas (pydantic v2) for the cell digital twin.

These are the contract shared by the biology data files (YAML), the simulation
engine, and the API. Everything that crosses a module boundary is one of these.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# --------------------------------------------------------------------------- #
# Relation graph (the "relations" layer)
# --------------------------------------------------------------------------- #
class NodeType(str, Enum):
    gene = "gene"
    mrna = "mrna"
    protein = "protein"
    metabolite = "metabolite"
    organelle = "organelle"
    phenotype = "phenotype"
    process = "process"


class RelationType(str, Enum):
    activates = "activates"
    inhibits = "inhibits"
    catalyzes = "catalyzes"
    transcribes = "transcribes"
    translates = "translates"
    transports = "transports"
    binds = "binds"
    produces = "produces"
    consumes = "consumes"
    damages = "damages"


class Node(BaseModel):
    id: str
    label: str
    type: NodeType
    #: Which engine "process" this node couples to, if any. This is the bridge
    #: from the relation graph to the mechanistic ODE layer.
    process: Optional[str] = None
    compartment: Optional[str] = None


class Relation(BaseModel):
    source: str
    target: str
    type: RelationType
    #: +1 (activating) or -1 (inhibiting); used by graph propagation.
    sign: int = 1
    weight: float = 1.0


class CellModel(BaseModel):
    """A cell type: its relation graph plus optional ODE parameter overrides."""

    id: str
    name: str
    description: str = ""
    nodes: list[Node] = Field(default_factory=list)
    relations: list[Relation] = Field(default_factory=list)
    #: Maps a node id -> engine process key (e.g. "etc", "gsh_pool"). Falls back
    #: to each node's own `process` field when absent here.
    process_map: dict[str, str] = Field(default_factory=dict)
    #: Optional overrides for engine rate constants (see engine.params.Params).
    parameters: dict[str, float] = Field(default_factory=dict)
    #: Baseline CYP450 (bioactivation) capacity of this cell type. Hepatocytes
    #: are high; most other cell types are low. A request may override it.
    cyp_activity: float = 1.0

    def resolve_process(self, node_id: str) -> Optional[str]:
        if node_id in self.process_map:
            return self.process_map[node_id]
        for n in self.nodes:
            if n.id == node_id:
                return n.process
        return None


# --------------------------------------------------------------------------- #
# Toxins (the "toxins" layer)
# --------------------------------------------------------------------------- #
class Effect(str, Enum):
    inhibit = "inhibit"
    produce = "produce"
    consume = "consume"
    damage = "damage"


class Target(BaseModel):
    """A single molecular target of a toxin and how strongly it is engaged."""

    node: str = Field(..., description="Node id in the cell's relation graph.")
    effect: Effect
    ic50: float = Field(..., gt=0, description="Concentration for half-max effect (uM).")
    hill: float = Field(1.0, gt=0, description="Hill coefficient (dose-response steepness).")
    emax: float = Field(1.0, ge=0, le=1, description="Max fractional engagement (0..1).")


class Toxin(BaseModel):
    id: str
    name: str
    toxin_class: str = ""
    description: str = ""
    targets: list[Target] = Field(default_factory=list)
    #: If true, effect scales with metabolic (CYP) bioactivation, e.g. APAP->NAPQI.
    requires_bioactivation: bool = False


class Exposure(BaseModel):
    """One toxin applied at a dose (used for single and combination runs)."""

    toxin_id: str
    dose: float = Field(..., ge=0, description="Concentration (uM).")


# --------------------------------------------------------------------------- #
# Simulation requests & results
# --------------------------------------------------------------------------- #
class SimulationRequest(BaseModel):
    cell_id: str = "hepatocyte"
    exposures: list[Exposure] = Field(default_factory=list)
    duration_h: float = Field(24.0, gt=0, description="Exposure duration (hours).")
    n_points: int = Field(100, ge=2, le=5000)
    #: Relative CYP450 activity (bioactivation). None => use the cell's default.
    cyp_activity: Optional[float] = Field(None, ge=0)


class TimePoint(BaseModel):
    t: float
    atp: float
    ros: float
    gsh: float
    caspase: float
    membrane: float
    viability: float


class MechanismAttribution(BaseModel):
    dominant: str
    apoptotic: float
    necrotic: float
    energy_failure: float
    oxidative_stress: float
    narrative: str


class SimulationResult(BaseModel):
    cell_id: str
    exposures: list[Exposure]
    duration_h: float
    trajectory: list[TimePoint]
    final_viability: float
    mechanism: MechanismAttribution


class DoseResponsePoint(BaseModel):
    dose: float
    viability: float


class DoseResponseResult(BaseModel):
    toxin_id: str
    cell_id: str
    duration_h: float
    curve: list[DoseResponsePoint]
    ic50: Optional[float]  # cytotoxic IC50 (dose at 50% viability), None if not reached
    hill: Optional[float]


class CombinationResult(BaseModel):
    cell_id: str
    exposures: list[Exposure]
    observed_viability: float
    expected_bliss: float
    #: >0 => synergy (more killing than independent), <0 => antagonism.
    synergy: float
    interpretation: str
