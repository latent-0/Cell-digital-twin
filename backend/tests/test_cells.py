"""Multi-cell-type tests: inheritance, CYP gating, and tissue selectivity."""

import pytest

from celltwin.engine.simulate import simulate
from celltwin.experiments.screen import dose_response
from celltwin.model.registry import list_cells, list_toxins, load_all_toxins, load_cell, validate_cell
from celltwin.schemas import Exposure, SimulationRequest

ALL_CELLS = list_cells()
ALL_TOXINS = list_toxins()


def _via(cell_id, toxin_id, dose, cyp=None):
    cell = load_cell(cell_id)
    req = SimulationRequest(
        exposures=[Exposure(toxin_id=toxin_id, dose=dose)], duration_h=24, cyp_activity=cyp
    )
    return simulate(req, cell, load_all_toxins()).final_viability


@pytest.mark.parametrize("cell_id", ALL_CELLS)
def test_all_cells_valid(cell_id):
    cell = load_cell(cell_id)
    assert validate_cell(cell) == []
    assert len(cell.nodes) > 0 and len(cell.relations) > 0


def test_extends_inherits_graph():
    base = load_cell("hepatocyte")
    child = load_cell("cardiomyocyte")
    assert len(child.nodes) == len(base.nodes)          # graph inherited
    assert child.cyp_activity < base.cyp_activity        # own physiology
    assert child.parameters["atp_thresh"] != 0           # own overrides applied


@pytest.mark.parametrize("cell_id", ALL_CELLS)
def test_all_cells_control_survive(cell_id):
    req = SimulationRequest(exposures=[], duration_h=24)
    assert simulate(req, load_cell(cell_id), load_all_toxins()).final_viability > 0.95


# BSO is a sensitizer (blocks GSH synthesis) -- tolerated alone by design, so it
# is not expected to be directly lethal. Its effect is validated via synergy.
_SENSITIZERS = {"bso"}


@pytest.mark.parametrize("toxin_id", ALL_TOXINS)
def test_every_toxin_runs_and_kills_at_high_dose(toxin_id):
    """Every directly-cytotoxic toxin must integrate cleanly and kill at a large dose."""
    tox = load_all_toxins()[toxin_id]
    max_ic50 = max(t.ic50 for t in tox.targets)
    v = _via("hepatocyte", toxin_id, max_ic50 * 1000, cyp=1.0)
    assert 0.0 <= v <= 1.0
    if toxin_id not in _SENSITIZERS:
        assert v < 0.5, f"{toxin_id} not lethal at high dose (viability {v:.2f})"


def test_genotoxic_and_apoptotic_mechanisms():
    tox = load_all_toxins()
    cell = load_cell("hepatocyte")
    for tid, dose in [("staurosporine", 1.0), ("etoposide", 100.0), ("cisplatin", 200.0)]:
        req = SimulationRequest(exposures=[Exposure(toxin_id=tid, dose=dose)], duration_h=24)
        m = simulate(req, cell, tox).mechanism
        assert m.dominant == "apoptosis"


def test_ccl4_requires_cyp():
    """Carbon tetrachloride is CYP-bioactivated: toxic with CYP, safe without."""
    assert _via("hepatocyte", "carbon_tetrachloride", 20000, cyp=1.0) < 0.3
    assert _via("hepatocyte", "carbon_tetrachloride", 20000, cyp=0.0) > 0.95


def test_apap_liver_selective():
    """APAP is far more toxic to high-CYP hepatocytes than to low-CYP neurons."""
    tox = load_all_toxins()
    dose = dose_response(tox["acetaminophen"], load_cell("hepatocyte"), tox).ic50 * 1.2
    assert _via("hepatocyte", "acetaminophen", dose) < _via("neuron", "acetaminophen", dose)


def test_rotenone_neuron_more_vulnerable_than_cancer():
    tox = load_all_toxins()
    dose = dose_response(tox["rotenone"], load_cell("hepatocyte"), tox).ic50
    assert _via("neuron", "rotenone", dose) < _via("cancer_cell", "rotenone", dose)


def test_cisplatin_tubule_selective_over_cancer():
    tox = load_all_toxins()
    tub = dose_response(tox["cisplatin"], load_cell("proximal_tubule"), tox)
    can = dose_response(tox["cisplatin"], load_cell("cancer_cell"), tox)
    assert tub.ic50 < can.ic50  # kidney tubule more sensitive than resistant tumor


def test_cancer_resists_apoptosis_inducer():
    tox = load_all_toxins()
    normal = dose_response(tox["staurosporine"], load_cell("hepatocyte"), tox)
    cancer = dose_response(tox["staurosporine"], load_cell("cancer_cell"), tox)
    assert cancer.ic50 > normal.ic50
