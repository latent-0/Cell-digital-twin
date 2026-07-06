"""Engine behavior tests (Phase 1): steady state, coupling, dynamics."""

import numpy as np

from celltwin.engine.coupling import build_modifiers, hill_occupancy
from celltwin.engine.ode import baseline_state, rhs
from celltwin.engine.params import BASELINE_STATE, Params
from celltwin.engine.simulate import simulate
from celltwin.experiments.screen import dose_response
from celltwin.schemas import Exposure, SimulationRequest


def test_hill_occupancy_monotonic():
    assert hill_occupancy(0, 1, 1) == 0.0
    lo = hill_occupancy(0.5, 1, 1)
    mid = hill_occupancy(1.0, 1, 1)
    hi = hill_occupancy(2.0, 1, 1)
    assert 0 < lo < mid < hi < 1
    assert abs(mid - 0.5) < 1e-9  # at IC50, half-max


def test_baseline_is_steady_state():
    """The unperturbed cell must rest at homeostasis (dy/dt ~ 0)."""
    from celltwin.engine.coupling import Modifiers

    y0 = baseline_state()
    dy = rhs(0.0, y0, Params(), Modifiers())
    assert np.allclose(dy, 0.0, atol=1e-9), f"baseline not steady: {dy}"


def test_control_stays_healthy(cell, toxins):
    req = SimulationRequest(exposures=[], duration_h=48)
    res = simulate(req, cell, toxins)
    assert res.final_viability > 0.99
    final = res.trajectory[-1]
    assert abs(final.atp - BASELINE_STATE["atp"]) < 0.02
    assert abs(final.gsh - BASELINE_STATE["gsh"]) < 0.05


def test_toxin_reduces_viability(cell, toxins):
    ic50 = dose_response(toxins["rotenone"], cell, toxins).ic50
    req = SimulationRequest(exposures=[Exposure(toxin_id="rotenone", dose=ic50 * 30)], duration_h=24)
    assert simulate(req, cell, toxins).final_viability < 0.1


def test_dose_monotonicity(cell, toxins):
    """Higher dose -> equal or lower viability (doses spanning the IC50)."""
    ic50 = dose_response(toxins["rotenone"], cell, toxins).ic50
    doses = [0.0] + list(np.logspace(np.log10(ic50 / 100), np.log10(ic50 * 100), 6))
    vias = []
    for d in doses:
        req = SimulationRequest(exposures=[Exposure(toxin_id="rotenone", dose=d)], duration_h=24)
        vias.append(simulate(req, cell, toxins).final_viability)
    for a, b in zip(vias, vias[1:]):
        assert b <= a + 1e-6, f"non-monotonic dose-response: {vias}"


def test_modifiers_default_neutral(cell, toxins):
    mods = build_modifiers(cell, [], toxins)
    assert mods.etc_activity == 1.0
    assert mods.ros_input == 0.0
    assert mods.gsh_extra == 0.0
