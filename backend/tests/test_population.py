"""Cell-population layer: heterogeneity smooths dose-response (salvaged from blc5xp)."""

import numpy as np

from celltwin.experiments.population import CellPopulation
from celltwin.experiments.screen import dose_response
from celltwin.model.registry import load_all_toxins, load_cell


def test_population_readouts_bounded(cell, toxins):
    pop = CellPopulation.for_toxin(cell, toxins["rotenone"], toxins, n_cells=60, cv=0.4)
    r = pop.response(25.0)
    assert 0.0 <= r["mean_viability"] <= 1.0
    assert 0.0 <= r["surviving_fraction"] <= 1.0


def test_cv_zero_matches_single_cell(cell, toxins):
    """With no variability the population equals the single-cell twin."""
    pop = CellPopulation.for_toxin(cell, toxins["rotenone"], toxins, n_cells=10, cv=0.0)
    single = dose_response(toxins["rotenone"], cell, toxins, doses=[25.0]).curve[0].viability
    assert abs(pop.response(25.0)["mean_viability"] - single) < 1e-6


def test_population_is_monotonic_and_smoother(cell, toxins):
    pop = CellPopulation.for_toxin(cell, toxins["rotenone"], toxins, n_cells=80, cv=0.5, seed=1)
    doses = [5, 15, 25, 40, 70]
    vs = [r["mean_viability"] for r in pop.dose_response(doses)]
    for a, b in zip(vs, vs[1:]):
        assert b <= a + 1e-6  # monotonic non-increasing
    # heterogeneity spreads death across doses: intermediate doses are partial
    assert 0.05 < vs[2] < 0.95


def test_negative_cv_rejected(cell, toxins):
    import pytest
    with pytest.raises(ValueError):
        CellPopulation(lambda d: 1.0, cv=-0.1)
