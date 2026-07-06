"""Bridge pydantic Toxin/CellModel into the static specs the JAX model needs."""

from __future__ import annotations

from ..schemas import CellModel, Toxin


def target_specs(toxin: Toxin, cell: CellModel) -> tuple:
    """Return a tuple of (process, ic50, hill, emax) for each resolvable target.

    Uses the toxin as loaded (i.e. with any calibration overlay already applied),
    so an inferred potency multiplier is centered on the point-calibrated value.
    """
    specs = []
    for tgt in toxin.targets:
        process = cell.resolve_process(tgt.node)
        if process is None:
            continue
        specs.append((process, float(tgt.ic50), float(tgt.hill), float(tgt.emax)))
    return tuple(specs)
