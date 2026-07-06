"""Bayesian workflow diagnostics.

These make the prior-dependence question concrete and honest:
 - prior_predictive: does the prior imply biologically plausible dose-responses?
 - prior_sensitivity: how much does the posterior move as the prior widens?
 - identifiability: is a parameter constrained by the data or by the prior?
"""

from __future__ import annotations

from dataclasses import dataclass

import jax.numpy as jnp
import numpy as np

from ..schemas import CellModel, Toxin
from .calibrate_bayes import PosteriorFit, fit_toxin
from .jax_ode import default_params, predict_dose_response
from .priors import PotencyPrior
from .specs import target_specs


def prior_predictive(
    toxin: Toxin, cell: CellModel, doses: np.ndarray,
    prior: PotencyPrior = PotencyPrior(), n_samples: int = 200,
    duration_h: float = 24.0, seed: int = 0,
) -> dict:
    """Sample potencies from the prior and return the implied dose-response band."""
    rng = np.random.default_rng(seed)
    p = default_params()
    specs = target_specs(toxin, cell)
    log_pot = rng.normal(0.0, prior.potency_log_sd, size=n_samples)
    curves = []
    for lp in log_pot:
        v = predict_dose_response(
            specs, float(np.exp(lp)), jnp.asarray(doses), p,
            cell.cyp_activity, toxin.requires_bioactivation, duration_h,
        )
        curves.append(np.asarray(v))
    curves = np.stack(curves)
    return {
        "doses": doses,
        "median": np.median(curves, axis=0),
        "lo": np.percentile(curves, 5, axis=0),
        "hi": np.percentile(curves, 95, axis=0),
        "implied_potency_ci90": (float(np.exp(np.percentile(log_pot, 5))),
                                 float(np.exp(np.percentile(log_pot, 95)))),
    }


@dataclass
class SensitivityRow:
    prior_log_sd: float
    ic50_median: float
    ic50_ci90: tuple[float, float]


def prior_sensitivity(
    toxin: Toxin, cell: CellModel, doses: np.ndarray, observed: np.ndarray,
    base_model_ic50: float, sds=(0.3, 0.7, 1.5), duration_h: float = 24.0,
    num_warmup: int = 300, num_samples: int = 500, seed: int = 0,
) -> list[SensitivityRow]:
    """Refit under progressively weaker priors; report how the IC50 posterior moves."""
    rows: list[SensitivityRow] = []
    for sd in sds:
        fit = fit_toxin(
            toxin, cell, doses, observed, base_model_ic50,
            prior=PotencyPrior(potency_log_sd=sd), duration_h=duration_h,
            num_warmup=num_warmup, num_samples=num_samples, seed=seed,
        )
        rows.append(SensitivityRow(sd, fit.ic50_median, fit.ic50_ci90))
    return rows


def identifiability(fit: PosteriorFit) -> dict:
    """Prior-vs-posterior variance shrinkage on log-potency.

    shrinkage ~1 => data-constrained; ~0 => prior-dominated (report, don't hide).
    """
    post_sd = float(np.std(np.log(fit.potency_samples)))
    prior_sd = fit.prior_log_sd
    shrinkage = 1.0 - post_sd / prior_sd if prior_sd > 0 else float("nan")
    if shrinkage > 0.7:
        verdict = "well constrained by data"
    elif shrinkage > 0.3:
        verdict = "partially constrained"
    else:
        verdict = "prior-dominated (weak data constraint)"
    return {
        "prior_log_sd": prior_sd,
        "posterior_log_sd": post_sd,
        "shrinkage": shrinkage,
        "verdict": verdict,
    }
