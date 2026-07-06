"""Prior specification for Bayesian calibration.

Priors here are *weakly informative* and encode real biology: a toxin's potency
is known to order-of-magnitude, so we place a log-normal on a potency multiplier
centered at 1.0 (i.e. on the point-calibrated value). Widening `potency_log_sd`
weakens the prior; prior-sensitivity analysis (diagnostics.py) sweeps it.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PotencyPrior:
    #: SD of Normal on log(potency multiplier). 0.7 => ~2x either side (1 sigma).
    potency_log_sd: float = 0.7
    #: Prior scale (HalfNormal) on assay observation noise (viability units).
    obs_noise_scale: float = 0.1


@dataclass(frozen=True)
class HierPrior:
    """Hierarchical (partial-pooling) prior across toxins."""
    mu_log_sd: float = 0.7        # population-mean log-potency prior SD
    tau_scale: float = 0.5        # HalfNormal scale on between-toxin SD
    obs_noise_scale: float = 0.1
