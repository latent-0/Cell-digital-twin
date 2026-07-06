"""Differentiable (JAX) reimplementation of the mechanistic ODE core.

This mirrors celltwin.engine.ode exactly so that NumPyro/HMC can take gradients
through the forward model. It is validated against the SciPy engine in
backend/tests/test_jax_ode.py (viability agreement within a small tolerance).
"""

from __future__ import annotations

from dataclasses import fields

import jax
import jax.numpy as jnp

from ..engine.params import BASELINE_STATE, STATE_ORDER, Params

jax.config.update("jax_enable_x64", True)

# Order of coupling processes in the modifier vector.
PROCESS_ORDER = (
    "etc", "atp_synthesis", "ros_production", "gsh_synthesis",
    "gsh_pool", "membrane", "apoptosis", "dna",
)


def default_params() -> dict:
    """Baseline rate constants as a plain dict (single source: engine.params)."""
    p = Params()
    return {f.name: float(getattr(p, f.name)) for f in fields(p)}


def _relu(x):
    return jnp.maximum(x, 0.0)


def rhs(y, t, p, mods):
    """dy/dt; `p` is a params dict, `mods` a dict of process modifiers (see below)."""
    atp, ros, gsh, casp, mem = y
    atp = jnp.maximum(atp, 0.0)
    ros = jnp.maximum(ros, 0.0)
    gsh = jnp.maximum(gsh, 0.0)

    etc = mods["etc_activity"]
    atp_synth = mods["atp_synth_mod"]

    atp_prod = p["k_atp_prod"] * etc * atp_synth
    d_atp = atp_prod - p["k_atp_use"] * atp

    ros_prod = p["k_ros_basal"] + p["k_ros_etc"] * (1.0 - etc) + p["ros_input_scale"] * mods["ros_input"]
    ros_scav = (p["k_ros_scav0"] + p["k_ros_scav"] * gsh) * ros
    d_ros = ros_prod - ros_scav

    gsh_syn = p["k_gsh_syn"] * mods["gsh_synth_mod"]
    d_gsh = gsh_syn - p["k_gsh_deg"] * gsh - p["k_gsh_ox"] * ros * gsh - p["gsh_consume_scale"] * mods["gsh_extra"] * gsh

    trigger = (
        p["w_ros"] * _relu(ros - p["ros_thresh"])
        + p["w_atp"] * _relu(p["atp_thresh"] - atp)
        + p["w_apop"] * mods["apop_input"]
        + p["w_dna"] * mods["dna_input"]
    )
    d_casp = p["k_casp_on"] * trigger * (1.0 - casp) + p["k_casp_fb"] * casp * (1.0 - casp) - p["k_casp_off"] * casp

    damage = p["k_mem_lpo"] * ros * _relu(1.0 - gsh) + p["mem_input_scale"] * mods["mem_input"] + p["k_necro"] * _relu(p["atp_necro"] - atp)
    d_mem = p["k_mem_rep"] * (1.0 - mem) - damage * mem

    return jnp.array([d_atp, d_ros, d_gsh, d_casp, d_mem])


def _baseline():
    return jnp.array([BASELINE_STATE[k] for k in STATE_ORDER])


def _rk4_step(y, h, p, mods):
    k1 = rhs(y, 0.0, p, mods)
    k2 = rhs(y + 0.5 * h * k1, 0.0, p, mods)
    k3 = rhs(y + 0.5 * h * k2, 0.0, p, mods)
    k4 = rhs(y + h * k3, 0.0, p, mods)
    return y + (h / 6.0) * (k1 + 2 * k2 + 2 * k3 + k4)


#: Fixed step count for the RK4 integrator (0.1 h steps over 24 h). Chosen so the
#: JAX model matches the SciPy (LSODA) engine to <1e-2 in viability; using a
#: fixed-step scan makes reverse-mode gradients stable for HMC (unlike an
#: adaptive solver's adjoint).
DEFAULT_STEPS = 240


def integrate(p, mods, duration_h, n_steps=DEFAULT_STEPS):
    """Integrate to `duration_h` with fixed-step RK4; return the final state."""
    h = duration_h / n_steps

    def step(y, _):
        y = _rk4_step(y, h, p, mods)
        return y, None

    y_final, _ = jax.lax.scan(step, _baseline(), None, length=n_steps)
    return y_final


def integrate_traj(p, mods, duration_h, n_steps=DEFAULT_STEPS):
    """Integrate with fixed-step RK4; return (times, trajectory)."""
    h = duration_h / n_steps

    def step(y, _):
        y = _rk4_step(y, h, p, mods)
        return y, y

    y0 = _baseline()
    _, ys = jax.lax.scan(step, y0, None, length=n_steps)
    ts = jnp.linspace(h, duration_h, n_steps)
    ys = jnp.concatenate([y0[None, :], ys], axis=0)
    ts = jnp.concatenate([jnp.array([0.0]), ts])
    return ts, ys


def viability(final_state):
    atp, ros, gsh, casp, mem = final_state
    v = jnp.clip(mem, 0.0, 1.0) * (1.0 - jnp.clip(casp, 0.0, 1.0))
    return jnp.clip(v, 0.0, 1.0)


def hill_occupancy(dose, ic50, hill, emax):
    d = jnp.power(jnp.maximum(dose, 1e-12), hill)
    return jnp.where(dose > 0, emax * d / (jnp.power(ic50, hill) + d), 0.0)


def build_modifiers(target_specs, potency, dose, cyp, bioactivation):
    """Turn a toxin's (static) targets + a potency scale into a modifiers dict.

    target_specs: tuple of (process, ic50, hill, emax). `potency` scales ic50
    (the inferred parameter). `dose` is a scalar. `bioactivation` gates by `cyp`.
    """
    mods = {
        "etc_activity": jnp.array(1.0),
        "atp_synth_mod": jnp.array(1.0),
        "ros_input": jnp.array(0.0),
        "gsh_synth_mod": jnp.array(1.0),
        "gsh_extra": jnp.array(0.0),
        "mem_input": jnp.array(0.0),
        "apop_input": jnp.array(0.0),
        "dna_input": jnp.array(0.0),
    }
    gate = cyp if bioactivation else 1.0
    for process, ic50, hill, emax in target_specs:
        occ = hill_occupancy(dose, ic50 * potency, hill, emax) * gate
        if process == "etc":
            mods["etc_activity"] = mods["etc_activity"] * (1.0 - occ)
        elif process == "atp_synthesis":
            mods["atp_synth_mod"] = mods["atp_synth_mod"] * (1.0 - occ)
        elif process == "ros_production":
            mods["ros_input"] = mods["ros_input"] + occ
        elif process == "gsh_synthesis":
            mods["gsh_synth_mod"] = mods["gsh_synth_mod"] * (1.0 - occ)
        elif process == "gsh_pool":
            mods["gsh_extra"] = mods["gsh_extra"] + occ
        elif process == "membrane":
            mods["mem_input"] = mods["mem_input"] + occ
        elif process == "apoptosis":
            mods["apop_input"] = mods["apop_input"] + occ
        elif process == "dna":
            mods["dna_input"] = mods["dna_input"] + occ
    return mods


def predict_viability_at_dose(target_specs, potency, dose, p, cyp, bioactivation, duration_h):
    mods = build_modifiers(target_specs, potency, dose, cyp, bioactivation)
    return viability(integrate(p, mods, duration_h))


def predict_dose_response(target_specs, potency, doses, p, cyp, bioactivation, duration_h):
    """Vectorized viability over a dose array (jax.vmap)."""
    fn = lambda d: predict_viability_at_dose(target_specs, potency, d, p, cyp, bioactivation, duration_h)
    return jax.vmap(fn)(doses)
