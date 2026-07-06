"""Bayesian calibration of toxin potency via NumPyro/HMC over the JAX ODE.

The forward model is the differentiable mechanistic engine (jax_ode), so NUTS
takes true gradients through the ODE. We infer a per-toxin potency multiplier
(centered on the point-calibrated value) and the assay noise, yielding a
posterior over the cytotoxic IC50 -- i.e. IC50 *with credible intervals*.
"""

from __future__ import annotations

from dataclasses import dataclass

import jax
import jax.numpy as jnp
import numpy as np
import numpyro
import numpyro.distributions as dist
from numpyro.infer import MCMC, NUTS

from ..schemas import CellModel, Toxin
from .jax_ode import default_params, predict_dose_response
from .priors import HierPrior, PotencyPrior
from .specs import target_specs


@dataclass
class PosteriorFit:
    toxin_id: str
    cell_id: str
    potency_samples: np.ndarray     # posterior of the potency multiplier
    ic50_samples: np.ndarray        # implied cytotoxic IC50 posterior (uM)
    sigma_samples: np.ndarray       # assay-noise posterior
    ic50_median: float
    ic50_ci90: tuple[float, float]  # 5th, 95th percentile
    r_hat_potency: float
    prior_log_sd: float

    def summary(self) -> str:
        lo, hi = self.ic50_ci90
        return (
            f"{self.toxin_id} on {self.cell_id}: "
            f"IC50 = {self.ic50_median:.3g} uM (90% CI {lo:.3g}-{hi:.3g}); "
            f"potency x{np.median(self.potency_samples):.2f}; "
            f"R-hat={self.r_hat_potency:.3f}"
        )


def _model_factory(specs, base_ic50_scale, doses, obs, p, cyp, bioact, duration_h, prior: PotencyPrior):
    doses_j = jnp.asarray(doses)
    obs_j = jnp.asarray(obs)

    def model():
        log_pot = numpyro.sample("log_potency", dist.Normal(0.0, prior.potency_log_sd))
        potency = numpyro.deterministic("potency", jnp.exp(log_pot))
        sigma = numpyro.sample("sigma", dist.HalfNormal(prior.obs_noise_scale))
        pred = predict_dose_response(specs, potency, doses_j, p, cyp, bioact, duration_h)
        # observations may be a (n_rep, n_dose) matrix; broadcast.
        numpyro.sample("obs", dist.Normal(pred, sigma), obs=obs_j)

    return model


def fit_toxin(
    toxin: Toxin,
    cell: CellModel,
    doses: np.ndarray,
    observed: np.ndarray,
    base_model_ic50: float,
    prior: PotencyPrior = PotencyPrior(),
    duration_h: float = 24.0,
    num_warmup: int = 400,
    num_samples: int = 800,
    seed: int = 0,
) -> PosteriorFit:
    """Run NUTS to infer the potency multiplier from dose-response observations.

    `base_model_ic50` is the model's cytotoxic IC50 at potency=1 (from the SciPy
    dose_response); the implied IC50 posterior is base_model_ic50 * potency.
    """
    specs = target_specs(toxin, cell)
    p = default_params()
    model = _model_factory(
        specs, 1.0, doses, observed, p, cell.cyp_activity,
        toxin.requires_bioactivation, duration_h, prior,
    )
    kernel = NUTS(model)
    mcmc = MCMC(kernel, num_warmup=num_warmup, num_samples=num_samples, num_chains=1, progress_bar=False)
    mcmc.run(jax.random.PRNGKey(seed))

    samples = mcmc.get_samples()
    potency = np.asarray(samples["potency"])
    sigma = np.asarray(samples["sigma"])
    ic50 = base_model_ic50 * potency

    # R-hat via numpyro's summary (single chain -> split R-hat).
    try:
        import numpyro.diagnostics as diag
        r_hat = float(diag.split_gelman_rubin(np.asarray(samples["log_potency"])[None, :]))
    except Exception:
        r_hat = float("nan")

    return PosteriorFit(
        toxin_id=toxin.id,
        cell_id=cell.id,
        potency_samples=potency,
        ic50_samples=ic50,
        sigma_samples=sigma,
        ic50_median=float(np.median(ic50)),
        ic50_ci90=(float(np.percentile(ic50, 5)), float(np.percentile(ic50, 95))),
        r_hat_potency=r_hat,
        prior_log_sd=prior.potency_log_sd,
    )


def fit_toxins_hierarchical(
    items: list[dict],
    prior: HierPrior = HierPrior(),
    duration_h: float = 24.0,
    num_warmup: int = 400,
    num_samples: int = 800,
    seed: int = 0,
) -> dict:
    """Partial-pooling calibration across toxins.

    Each item: {toxin, cell, doses, observed, base_model_ic50}. Per-toxin
    log-potencies are drawn from a shared population Normal(mu, tau), so data
    from one toxin informs the others -- turning the toxin panel into a
    shared-information asset (the key strength of the hierarchical framing).
    """
    p = default_params()
    prepared = []
    for it in items:
        prepared.append((
            target_specs(it["toxin"], it["cell"]),
            jnp.asarray(it["doses"]),
            jnp.asarray(it["observed"]),
            it["cell"].cyp_activity,
            it["toxin"].requires_bioactivation,
            it["toxin"].id,
            it["base_model_ic50"],
        ))
    n = len(prepared)

    def model():
        mu = numpyro.sample("mu", dist.Normal(0.0, prior.mu_log_sd))
        tau = numpyro.sample("tau", dist.HalfNormal(prior.tau_scale))
        sigma = numpyro.sample("sigma", dist.HalfNormal(prior.obs_noise_scale))
        with numpyro.plate("toxin", n):
            log_pot = numpyro.sample("log_potency", dist.Normal(mu, tau))
        for i, (specs, doses, obs, cyp, bioact, _tid, _m0) in enumerate(prepared):
            pred = predict_dose_response(specs, jnp.exp(log_pot[i]), doses, p, cyp, bioact, duration_h)
            numpyro.sample(f"obs_{i}", dist.Normal(pred, sigma), obs=obs)

    mcmc = MCMC(NUTS(model), num_warmup=num_warmup, num_samples=num_samples, num_chains=1, progress_bar=False)
    mcmc.run(jax.random.PRNGKey(seed))
    s = mcmc.get_samples()
    log_pot = np.asarray(s["log_potency"])  # (num_samples, n)
    out = {"mu": np.asarray(s["mu"]), "tau": np.asarray(s["tau"]), "toxins": {}}
    for i, (_specs, _d, _o, _c, _b, tid, m0) in enumerate(prepared):
        ic50 = m0 * np.exp(log_pot[:, i])
        out["toxins"][tid] = {
            "ic50_median": float(np.median(ic50)),
            "ic50_ci90": (float(np.percentile(ic50, 5)), float(np.percentile(ic50, 95))),
            "potency_median": float(np.median(np.exp(log_pot[:, i]))),
        }
    return out


def synth_dose_response(
    toxin: Toxin,
    cell: CellModel,
    center_ic50: float,
    true_potency: float = 1.0,
    n_doses: int = 8,
    n_rep: int = 3,
    noise: float = 0.05,
    span: float = 30.0,
    duration_h: float = 24.0,
    seed: int = 0,
) -> tuple[np.ndarray, np.ndarray]:
    """Model-based pseudo-observations for pipeline validation.

    Generates a noisy dose-response FROM the mechanistic model at a known
    `true_potency`, so a correct inference recovers that potency (a standard
    parameter-recovery check). Doses are spaced around `center_ic50`.
    """
    rng = np.random.default_rng(seed)
    p = default_params()
    specs = target_specs(toxin, cell)
    doses = np.logspace(np.log10(center_ic50 / span), np.log10(center_ic50 * span), n_doses)
    truth = np.asarray(
        predict_dose_response(
            specs, true_potency, jnp.asarray(doses), p,
            cell.cyp_activity, toxin.requires_bioactivation, duration_h,
        )
    )
    obs = np.clip(truth[None, :] + rng.normal(0, noise, size=(n_rep, n_doses)), 0.0, 1.0)
    return doses, obs
