"""Coupling contract: toxins + doses -> process modifiers on the ODE system.

This is the bridge described in docs/PLAN.md §3. The relation graph decides
*what* each toxin perturbs (which process a targeted node maps to); the Hill
equation decides *how strongly* (fractional target engagement at the given
dose); the result is a small set of modifiers the ODE right-hand side reads.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..schemas import CellModel, Effect, Exposure, Toxin


def hill_occupancy(dose: float, ic50: float, hill: float, emax: float = 1.0) -> float:
    """Fractional target engagement (0..emax) via the Hill equation."""
    if dose <= 0:
        return 0.0
    d = dose ** hill
    return emax * d / (ic50 ** hill + d)


@dataclass
class Modifiers:
    """Aggregate process modifiers read by the ODE right-hand side."""

    etc_activity: float = 1.0     # multiplier on ETC-driven ATP production (0..1)
    atp_synth_mod: float = 1.0    # multiplier on ATP synthesis (uncouplers) (0..1)
    ros_input: float = 0.0        # additive ROS generation from oxidative toxins
    gsh_synth_mod: float = 1.0    # multiplier on GSH synthesis (0..1)
    gsh_extra: float = 0.0        # extra GSH consumption from depleters
    mem_input: float = 0.0        # direct membrane damage from disruptors
    #: Per-process total engagement, for mechanism attribution / debugging.
    engagement: dict[str, float] = field(default_factory=dict)


#: Which process a node maps to -> how it enters the ODE system, given effect.
_PROCESS_KEYS = {
    "etc",             # electron transport chain complexes
    "atp_synthesis",   # ATP synthase / proton gradient (uncouplers)
    "ros_production",  # direct oxidative stressors
    "gsh_synthesis",   # inhibitors of GSH synthesis
    "gsh_pool",        # direct GSH depleters / reactive-metabolite conjugation
    "membrane",        # membrane disruptors
}


def build_modifiers(
    cell: CellModel,
    exposures: list[Exposure],
    toxins: dict[str, Toxin],
    cyp_activity: float = 1.0,
) -> Modifiers:
    """Combine every (toxin, dose) exposure into a single Modifiers bundle."""
    mods = Modifiers()

    for exp in exposures:
        toxin = toxins[exp.toxin_id]
        for tgt in toxin.targets:
            occ = hill_occupancy(exp.dose, tgt.ic50, tgt.hill, tgt.emax)
            if toxin.requires_bioactivation:
                occ *= cyp_activity  # no CYP -> no reactive metabolite -> no effect
            if occ <= 0:
                continue

            process = cell.resolve_process(tgt.node)
            if process is None or process not in _PROCESS_KEYS:
                # Unmapped node: recorded for attribution but has no dynamic effect.
                mods.engagement[tgt.node] = mods.engagement.get(tgt.node, 0.0) + occ
                continue

            mods.engagement[process] = mods.engagement.get(process, 0.0) + occ

            if process == "etc":
                mods.etc_activity *= (1.0 - occ)
            elif process == "atp_synthesis":
                mods.atp_synth_mod *= (1.0 - occ)
            elif process == "ros_production":
                mods.ros_input += occ
            elif process == "gsh_synthesis":
                mods.gsh_synth_mod *= (1.0 - occ)
            elif process == "gsh_pool":
                mods.gsh_extra += occ
            elif process == "membrane":
                mods.mem_input += occ

    return mods
