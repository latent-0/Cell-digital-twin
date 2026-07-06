"""Screening tests (Phase 2): dose-response/IC50, mechanism, synergy."""

from celltwin.engine.simulate import simulate
from celltwin.experiments.screen import combination, dose_response
from celltwin.schemas import Exposure, SimulationRequest


def _mechanism_for(cell, toxins, toxin_id, dose, cyp=1.0):
    req = SimulationRequest(
        exposures=[Exposure(toxin_id=toxin_id, dose=dose)], duration_h=24, cyp_activity=cyp
    )
    return simulate(req, cell, toxins).mechanism


def test_ic50_detected_and_ordered(cell, toxins):
    rot = dose_response(toxins["rotenone"], cell, toxins)
    h2o2 = dose_response(toxins["hydrogen_peroxide"], cell, toxins)
    assert rot.ic50 is not None and h2o2.ic50 is not None
    # Rotenone (nM-active Complex I inhibitor) is far more potent than H2O2.
    assert rot.ic50 < h2o2.ic50


def test_dose_response_curve_spans_full_effect(cell, toxins):
    dr = dose_response(toxins["rotenone"], cell, toxins)
    vias = [p.viability for p in dr.curve]
    assert max(vias) > 0.95  # low doses safe
    assert min(vias) < 0.10  # high doses lethal


def test_mechanism_energy_failure_for_mito_toxin(cell, toxins):
    ic50 = dose_response(toxins["rotenone"], cell, toxins).ic50
    m = _mechanism_for(cell, toxins, "rotenone", ic50 * 30)
    assert m.dominant == "energy failure"
    assert m.energy_failure > 0.5


def test_mechanism_necrosis_for_detergent(cell, toxins):
    m = _mechanism_for(cell, toxins, "triton_x100", 200.0)
    assert m.dominant == "necrosis"
    assert m.necrotic > 0.5


def test_apap_is_cyp_gated(cell, toxins):
    """APAP overdose is toxic with CYP, protected without it (metabolism-dependent)."""
    with_cyp = _mechanism_for(cell, toxins, "acetaminophen", 8000.0, cyp=1.0)
    without_cyp = _mechanism_for(cell, toxins, "acetaminophen", 8000.0, cyp=0.0)
    assert with_cyp.oxidative_stress > 0.1
    assert without_cyp.dominant.startswith("none")


def test_bso_synergizes_with_h2o2(cell, toxins):
    """GSH-synthesis blockade sensitizes cells to an oxidant (known biology)."""
    combo = [
        Exposure(toxin_id="bso", dose=150.0),
        Exposure(toxin_id="hydrogen_peroxide", dose=280.0),
    ]
    res = combination(combo, cell, toxins, duration_h=24)
    assert res.synergy > 0.1
    assert "synerg" in res.interpretation


def test_combination_of_one_is_additive(cell, toxins):
    res = combination([Exposure(toxin_id="rotenone", dose=0.05)], cell, toxins)
    assert abs(res.synergy) < 1e-6
