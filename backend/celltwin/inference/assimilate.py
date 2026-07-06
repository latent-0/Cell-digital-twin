"""Sequential data assimilation via a particle filter.

This is what makes the model a *twin* rather than a static simulator: given a
stream of noisy measurements from a cell (e.g. ATP and ROS over time under an
unknown insult), it jointly infers the latent cell state and the unknown
exposure severity online, with the posterior tightening as data arrive.

Gradient-free, so it runs directly on the NumPy engine (no JAX needed).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np

from ..engine.coupling import Modifiers
from ..engine.ode import baseline_state, rhs
from ..engine.params import Params


def _rk4(y: np.ndarray, t0: float, t1: float, p: Params, m: Modifiers, n: int = 20) -> np.ndarray:
    h = (t1 - t0) / n
    for _ in range(n):
        k1 = rhs(0.0, y, p, m)
        k2 = rhs(0.0, y + 0.5 * h * k1, p, m)
        k3 = rhs(0.0, y + 0.5 * h * k2, p, m)
        k4 = rhs(0.0, y + h * k3, p, m)
        y = y + (h / 6.0) * (k1 + 2 * k2 + 2 * k3 + k4)
    return y


def etc_severity_modifiers(theta: float) -> Modifiers:
    """Default parameterization: theta in (0,1) is fractional Complex I inhibition."""
    return Modifiers(etc_activity=float(np.clip(1.0 - theta, 1e-6, 1.0)))


def _systematic_resample(weights: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    n = len(weights)
    positions = (rng.random() + np.arange(n)) / n
    cumsum = np.cumsum(weights)
    cumsum[-1] = 1.0
    idx = np.searchsorted(cumsum, positions)
    return idx


@dataclass
class AssimilationResult:
    times: np.ndarray
    theta_mean: np.ndarray          # posterior mean severity per observation time
    theta_ci90: np.ndarray          # (T, 2) credible interval
    state_mean: np.ndarray          # (T, 5) filtered latent state
    final_theta_median: float


def particle_filter(
    obs_times: np.ndarray,
    observations: np.ndarray,          # (T, k) measured values
    obs_indices: list[int],            # which state vars are measured (0=ATP,1=ROS,...)
    obs_noise: float = 0.05,
    n_particles: int = 2000,
    theta_walk: float = 0.05,          # random-walk SD on logit(theta) for online tracking
    theta_to_modifiers: Callable[[float], Modifiers] = etc_severity_modifiers,
    params: Params | None = None,
    seed: int = 0,
) -> AssimilationResult:
    p = params or Params()
    rng = np.random.default_rng(seed)
    obs_idx = np.asarray(obs_indices)

    # Particles: latent state + logit(theta) (theta in (0,1)).
    states = np.tile(baseline_state(), (n_particles, 1))
    z = rng.normal(0.0, 1.5, size=n_particles)  # broad prior on logit(theta)

    T = len(obs_times)
    theta_mean = np.zeros(T)
    theta_ci = np.zeros((T, 2))
    state_mean = np.zeros((T, 5))

    t_prev = 0.0
    for k in range(T):
        t_now = float(obs_times[k])
        theta = 1.0 / (1.0 + np.exp(-z))
        # Predict each particle forward with its own severity.
        for i in range(n_particles):
            m = theta_to_modifiers(float(theta[i]))
            states[i] = _rk4(states[i], t_prev, t_now, p, m)
        # Weight by observation likelihood.
        pred = states[:, obs_idx]
        resid = observations[k][None, :] - pred
        logw = -0.5 * np.sum((resid / obs_noise) ** 2, axis=1)
        logw -= logw.max()
        w = np.exp(logw)
        w /= w.sum()

        theta_mean[k] = float(np.sum(w * theta))
        order = np.argsort(theta)
        cw = np.cumsum(w[order])
        theta_ci[k] = [
            float(theta[order][np.searchsorted(cw, 0.05)]),
            float(theta[order][np.searchsorted(cw, 0.95)]),
        ]
        state_mean[k] = w @ states

        # Resample + jitter theta (random walk keeps the filter adaptive).
        idx = _systematic_resample(w, rng)
        states = states[idx]
        z = z[idx] + rng.normal(0.0, theta_walk, size=n_particles)
        t_prev = t_now

    final_theta = 1.0 / (1.0 + np.exp(-z))
    return AssimilationResult(
        times=np.asarray(obs_times),
        theta_mean=theta_mean,
        theta_ci90=theta_ci,
        state_mean=state_mean,
        final_theta_median=float(np.median(final_theta)),
    )


def synth_observations(
    true_theta: float,
    obs_times: np.ndarray,
    obs_indices: list[int],
    obs_noise: float = 0.05,
    theta_to_modifiers: Callable[[float], Modifiers] = etc_severity_modifiers,
    params: Params | None = None,
    seed: int = 0,
) -> np.ndarray:
    """Generate a noisy measured trajectory from a known severity (for recovery tests)."""
    p = params or Params()
    rng = np.random.default_rng(seed)
    m = theta_to_modifiers(true_theta)
    y = baseline_state()
    obs = []
    t_prev = 0.0
    for t in obs_times:
        y = _rk4(y, t_prev, float(t), p, m)
        obs.append(y[np.asarray(obs_indices)] + rng.normal(0, obs_noise, size=len(obs_indices)))
        t_prev = float(t)
    return np.array(obs)
