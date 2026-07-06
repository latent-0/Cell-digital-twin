"""Bayesian calibration & data-assimilation tests (parameter recovery)."""

import numpy as np
import pytest

from celltwin.experiments.screen import dose_response
from celltwin.inference.assimilate import particle_filter, synth_observations
from celltwin.inference.calibrate_bayes import fit_toxin, synth_dose_response
from celltwin.inference.diagnostics import identifiability, prior_predictive
from celltwin.model.registry import load_all_toxins, load_cell


@pytest.fixture(scope="module")
def rotenone_fit():
    cell = load_cell("hepatocyte")
    toxins = load_all_toxins()
    rot = toxins["rotenone"]
    m0 = dose_response(rot, cell, toxins).ic50
    doses, obs = synth_dose_response(rot, cell, center_ic50=m0, true_potency=0.7, seed=1)
    fit = fit_toxin(rot, cell, doses, obs, base_model_ic50=m0,
                    num_warmup=200, num_samples=300, seed=0)
    return m0, fit


def test_nuts_converges_and_recovers_potency(rotenone_fit):
    _m0, fit = rotenone_fit
    assert fit.r_hat_potency < 1.1
    # true potency was 0.7 -> posterior should cover it
    recovered = float(np.median(fit.potency_samples))
    assert 0.5 < recovered < 0.95


def test_ic50_has_credible_interval(rotenone_fit):
    _m0, fit = rotenone_fit
    lo, hi = fit.ic50_ci90
    assert lo < fit.ic50_median < hi
    assert hi > lo > 0


def test_identifiability_reports_shrinkage(rotenone_fit):
    _m0, fit = rotenone_fit
    ident = identifiability(fit)
    assert 0.0 <= ident["shrinkage"] <= 1.0
    assert ident["verdict"]


def test_prior_predictive_is_plausible():
    cell = load_cell("hepatocyte")
    toxins = load_all_toxins()
    doses = np.logspace(-1, 3, 12)
    pp = prior_predictive(toxins["rotenone"], cell, doses, n_samples=50)
    # a prior-plausible dose-response spans healthy->dead across the dose range
    assert pp["median"][0] > 0.8
    assert pp["median"][-1] < 0.2


def test_particle_filter_recovers_severity_and_tightens():
    obs_times = np.linspace(2, 24, 8)
    obs = synth_observations(0.7, obs_times, obs_indices=[0, 1], obs_noise=0.05, seed=3)
    res = particle_filter(obs_times, obs, obs_indices=[0, 1], obs_noise=0.05,
                          n_particles=800, seed=1)
    assert abs(res.final_theta_median - 0.7) < 0.1              # recovers truth
    early = res.theta_ci90[0, 1] - res.theta_ci90[0, 0]
    late = res.theta_ci90[-1, 1] - res.theta_ci90[-1, 0]
    assert late < early                                         # posterior tightens
