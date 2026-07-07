"""Simulation orchestration: request -> coupling -> ODE integration -> result."""

from __future__ import annotations

import numpy as np
from scipy.integrate import solve_ivp

from ..readouts.mechanism import attribute
from ..schemas import (
    CellModel,
    SimulationRequest,
    SimulationResult,
    TimePoint,
    Toxin,
)
from .coupling import Modifiers, build_modifiers
from .ode import baseline_state, rhs, viability
from .params import STATE_ORDER, Params


def run_modifiers(mods: Modifiers, params: Params | None = None, duration_h: float = 24.0) -> dict:
    """Integrate the ODE core directly from a Modifiers bundle (no toxin coupling).

    Returns the end-state readouts + viability. Used by the ML surrogate (which
    learns modifiers -> readouts) and any low-level engine consumer.
    """
    p = params or Params()
    sol = solve_ivp(
        rhs, (0.0, duration_h), baseline_state(), args=(p, mods),
        method="LSODA", rtol=1e-6, atol=1e-9, max_step=duration_h / 20.0,
    )
    if not sol.success:
        raise RuntimeError(f"ODE integration failed: {sol.message}")
    atp, ros, gsh, casp, mem = sol.y[:, -1]
    return {
        "atp": float(max(atp, 0.0)), "ros": float(max(ros, 0.0)), "gsh": float(max(gsh, 0.0)),
        "caspase": float(np.clip(casp, 0, 1)), "membrane": float(np.clip(mem, 0, 1)),
        "viability": viability(atp, ros, gsh, casp, mem),
    }


def simulate(
    request: SimulationRequest,
    cell: CellModel,
    toxins: dict[str, Toxin],
) -> SimulationResult:
    """Run the coupled hybrid engine for one exposure scenario."""
    params = Params().with_overrides(cell.parameters)
    cyp = request.cyp_activity if request.cyp_activity is not None else cell.cyp_activity
    mods = build_modifiers(cell, request.exposures, toxins, cyp)

    t_eval = np.linspace(0.0, request.duration_h, request.n_points)
    sol = solve_ivp(
        rhs,
        (0.0, request.duration_h),
        baseline_state(),
        args=(params, mods),
        method="LSODA",
        t_eval=t_eval,
        rtol=1e-6,
        atol=1e-9,
        max_step=request.duration_h / 20.0,
    )
    if not sol.success:
        raise RuntimeError(f"ODE integration failed: {sol.message}")

    trajectory: list[TimePoint] = []
    for i, t in enumerate(sol.t):
        atp, ros, gsh, casp, mem = sol.y[:, i]
        trajectory.append(
            TimePoint(
                t=float(t),
                atp=float(max(atp, 0.0)),
                ros=float(max(ros, 0.0)),
                gsh=float(max(gsh, 0.0)),
                caspase=float(np.clip(casp, 0.0, 1.0)),
                membrane=float(np.clip(mem, 0.0, 1.0)),
                viability=viability(atp, ros, gsh, casp, mem),
            )
        )

    final = {k: float(sol.y[j, -1]) for j, k in enumerate(STATE_ORDER)}
    final_via = trajectory[-1].viability
    mech = attribute(final, mods)

    return SimulationResult(
        cell_id=cell.id,
        exposures=request.exposures,
        duration_h=request.duration_h,
        trajectory=trajectory,
        final_viability=final_via,
        mechanism=mech,
    )
