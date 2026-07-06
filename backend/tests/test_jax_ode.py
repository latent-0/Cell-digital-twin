"""The JAX forward model must match the SciPy engine (so HMC infers the real model)."""

import pytest

from celltwin.engine.simulate import simulate
from celltwin.inference.jax_ode import default_params, predict_viability_at_dose
from celltwin.inference.specs import target_specs
from celltwin.model.registry import load_all_toxins, load_cell
from celltwin.schemas import Exposure, SimulationRequest

CASES = [
    ("rotenone", 50.0), ("rotenone", 5.0), ("hydrogen_peroxide", 400.0),
    ("cyanide", 500.0), ("staurosporine", 0.05), ("doxorubicin", 1.0),
    ("acetaminophen", 20000.0), ("triton_x100", 60.0), ("cisplatin", 20.0),
    ("fccp", 10.0),
]


@pytest.mark.parametrize("toxin_id,dose", CASES)
def test_jax_matches_scipy(toxin_id, dose):
    cell = load_cell("hepatocyte")
    toxins = load_all_toxins()
    toxin = toxins[toxin_id]

    scipy_v = simulate(
        SimulationRequest(exposures=[Exposure(toxin_id=toxin_id, dose=dose)], duration_h=24),
        cell, toxins,
    ).final_viability

    jax_v = float(predict_viability_at_dose(
        target_specs(toxin, cell), 1.0, dose, default_params(),
        cell.cyp_activity, toxin.requires_bioactivation, 24.0,
    ))

    assert abs(scipy_v - jax_v) < 0.02, f"{toxin_id}@{dose}: scipy={scipy_v} jax={jax_v}"


def test_jax_control_healthy():
    cell = load_cell("hepatocyte")
    v = float(predict_viability_at_dose((), 1.0, 0.0, default_params(), 1.0, False, 24.0))
    assert v > 0.99
