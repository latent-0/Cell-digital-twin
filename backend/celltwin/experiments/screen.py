"""Screening experiments: dose-response curves and combination (synergy) tests."""

from __future__ import annotations

from typing import Optional

import numpy as np

from ..engine.simulate import simulate
from ..schemas import (
    CellModel,
    CombinationResult,
    DoseResponsePoint,
    DoseResponseResult,
    Exposure,
    SimulationRequest,
    Toxin,
)


def _viability_at(
    cell: CellModel,
    toxins: dict[str, Toxin],
    exposures: list[Exposure],
    duration_h: float,
    cyp_activity: float,
) -> float:
    req = SimulationRequest(
        cell_id=cell.id,
        exposures=exposures,
        duration_h=duration_h,
        n_points=60,
        cyp_activity=cyp_activity,
    )
    return simulate(req, cell, toxins).final_viability


def _auto_dose_range(toxin: Toxin, n: int) -> np.ndarray:
    """Log-spaced doses spanning ~3 logs each side of the toxin's median IC50."""
    ic50s = [t.ic50 for t in toxin.targets] or [1.0]
    center = float(np.exp(np.mean(np.log(ic50s))))
    return np.concatenate(([0.0], np.logspace(np.log10(center / 1e3), np.log10(center * 1e3), n - 1)))


def _interp_ic50(doses: np.ndarray, via: np.ndarray) -> Optional[float]:
    """Dose at 50% viability, by log-linear interpolation on the first crossing."""
    for i in range(1, len(doses)):
        if via[i - 1] >= 0.5 >= via[i] and doses[i] > 0:
            d0, d1 = doses[i - 1], doses[i]
            v0, v1 = via[i - 1], via[i]
            if v0 == v1:
                return float(d1)
            ld0 = np.log10(d0) if d0 > 0 else np.log10(d1) - 3
            frac = (v0 - 0.5) / (v0 - v1)
            return float(10 ** (ld0 + frac * (np.log10(d1) - ld0)))
    return None


def _fit_hill(doses: np.ndarray, via: np.ndarray, ic50: Optional[float]) -> Optional[float]:
    """Estimate a cytotoxic Hill slope from the curve around the IC50."""
    if ic50 is None:
        return None
    mask = doses > 0
    d, v = doses[mask], np.clip(via[mask], 1e-3, 1 - 1e-3)
    frac_dead = 1.0 - v
    # logit(frac_dead) = hill * (log10(dose) - log10(ic50))
    y = np.log(frac_dead / (1.0 - frac_dead))
    x = np.log10(d) - np.log10(ic50)
    keep = np.isfinite(y) & np.isfinite(x)
    if keep.sum() < 2:
        return None
    slope = np.polyfit(x[keep], y[keep], 1)[0] / np.log(10)
    return float(abs(slope))


def dose_response(
    toxin: Toxin,
    cell: CellModel,
    toxins: dict[str, Toxin],
    doses: Optional[list[float]] = None,
    duration_h: float = 24.0,
    n_doses: int = 24,
    cyp_activity: float = 1.0,
) -> DoseResponseResult:
    dose_arr = np.array(doses) if doses is not None else _auto_dose_range(toxin, n_doses)
    via = np.array(
        [
            _viability_at(cell, toxins, [Exposure(toxin_id=toxin.id, dose=float(d))], duration_h, cyp_activity)
            for d in dose_arr
        ]
    )
    ic50 = _interp_ic50(dose_arr, via)
    hill = _fit_hill(dose_arr, via, ic50)
    curve = [DoseResponsePoint(dose=float(d), viability=float(v)) for d, v in zip(dose_arr, via)]
    return DoseResponseResult(
        toxin_id=toxin.id,
        cell_id=cell.id,
        duration_h=duration_h,
        curve=curve,
        ic50=ic50,
        hill=hill,
    )


def combination(
    exposures: list[Exposure],
    cell: CellModel,
    toxins: dict[str, Toxin],
    duration_h: float = 24.0,
    cyp_activity: float = 1.0,
) -> CombinationResult:
    """Score synergy vs a Bliss-independence baseline (on the killing fraction)."""
    observed = _viability_at(cell, toxins, exposures, duration_h, cyp_activity)

    # Bliss expectation: survivals multiply (kills act independently).
    survival_product = 1.0
    for exp in exposures:
        v = _viability_at(cell, toxins, [exp], duration_h, cyp_activity)
        survival_product *= v
    expected = survival_product

    # synergy > 0 means observed killing exceeds independent expectation.
    synergy = expected - observed
    if synergy > 0.05:
        interp = "synergistic (combined toxicity exceeds independent effects)"
    elif synergy < -0.05:
        interp = "antagonistic (combined toxicity less than independent effects)"
    else:
        interp = "additive (consistent with independent effects)"

    return CombinationResult(
        cell_id=cell.id,
        exposures=exposures,
        observed_viability=observed,
        expected_bliss=expected,
        synergy=synergy,
        interpretation=interp,
    )
