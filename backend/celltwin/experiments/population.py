"""Cell-population layer — heterogeneity smooths dose-response into real sigmoids.

A single deterministic twin dies switch-like: below a threshold dose it lives,
above it it dies, with little in between. Real tissue is a *population* of cells
that vary in sensitivity, so at any dose some are already dead and some still
alive — the population-average viability traces the smooth sigmoid a real assay
measures.

Heterogeneity is modeled as a per-cell log-normal sensitivity multiplier
(median 1): a cell with sensitivity ``s`` experiences effective dose ``s*dose``.

(Adapted from the parallel `blc5xp` implementation into this engine.)
"""

from __future__ import annotations

import math
from typing import Callable

import numpy as np

from ..engine.simulate import simulate
from ..schemas import CellModel, Exposure, SimulationRequest, Toxin

# viability engine: effective dose -> single-cell viability in [0, 1]
ViabilityFn = Callable[[float], float]


def _sigma_from_cv(cv: float) -> float:
    """Log-normal shape parameter giving coefficient-of-variation ``cv``."""
    return math.sqrt(math.log(1.0 + cv * cv))


class CellPopulation:
    """A heterogeneous population of single-cell twins sharing one network."""

    def __init__(self, viability_fn: ViabilityFn, *, n_cells: int = 200, cv: float = 0.4, seed: int = 0):
        if cv < 0:
            raise ValueError("cv (biological variability) must be >= 0")
        self.viability_fn = viability_fn
        self.n_cells = n_cells
        self.cv = cv
        rng = np.random.default_rng(seed)
        self.sensitivity = (
            np.ones(n_cells) if cv == 0
            else rng.lognormal(mean=0.0, sigma=_sigma_from_cv(cv), size=n_cells)
        )

    @classmethod
    def for_toxin(
        cls, cell: CellModel, toxin: Toxin, toxins: dict[str, Toxin],
        *, hours: float = 24.0, cyp_activity: float | None = None, **kw,
    ) -> "CellPopulation":
        def vf(dose: float) -> float:
            req = SimulationRequest(
                cell_id=cell.id, exposures=[Exposure(toxin_id=toxin.id, dose=dose)],
                duration_h=hours, n_points=30, cyp_activity=cyp_activity,
            )
            return simulate(req, cell, toxins).final_viability
        return cls(vf, **kw)

    def response(self, dose: float, *, death_threshold: float = 0.5) -> dict:
        vs = np.array([self.viability_fn(float(s * dose)) for s in self.sensitivity])
        return {
            "dose": float(dose),
            "mean_viability": float(vs.mean()),
            "surviving_fraction": float(np.mean(vs > death_threshold)),
        }

    def dose_response(self, doses, *, death_threshold: float = 0.5) -> list[dict]:
        return [self.response(float(d), death_threshold=death_threshold) for d in doses]
