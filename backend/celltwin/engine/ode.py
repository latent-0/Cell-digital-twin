"""Mechanistic ODE core of the cell digital twin.

Five coupled state variables capture the dominant axes of cytotoxicity:

    ATP  -- mitochondrial bioenergetics (energy charge)
    ROS  -- reactive oxygen species (oxidative stress)
    GSH  -- glutathione buffer (antioxidant capacity)
    CASP -- caspase / apoptosis commitment (programmed death)
    MEM  -- plasma-membrane integrity (necrotic death)

The system rests at the homeostatic steady state defined in params.BASELINE_STATE
and is driven away from it by toxin-derived Modifiers (see engine.coupling).
"""

from __future__ import annotations

import numpy as np

from .coupling import Modifiers
from .params import BASELINE_STATE, STATE_ORDER, Params


def _relu(x: float) -> float:
    return x if x > 0.0 else 0.0


def rhs(t: float, y: np.ndarray, p: Params, m: Modifiers) -> np.ndarray:
    """Right-hand side dy/dt for the ODE system."""
    atp, ros, gsh, casp, mem = y
    atp = max(atp, 0.0)
    ros = max(ros, 0.0)
    gsh = max(gsh, 0.0)

    # --- ATP: production (ETC x synthase) minus consumption ---
    atp_prod = p.k_atp_prod * m.etc_activity * m.atp_synth_mod
    d_atp = atp_prod - p.k_atp_use * atp

    # --- ROS: basal + ETC leak + toxin input, scavenged by GSH ---
    ros_prod = (
        p.k_ros_basal
        + p.k_ros_etc * (1.0 - m.etc_activity)
        + p.ros_input_scale * m.ros_input
    )
    ros_scav = p.k_ros_scav * ros * gsh
    d_ros = ros_prod - ros_scav

    # --- GSH: synthesis minus turnover, ROS-scavenging cost, and depleters ---
    gsh_syn = p.k_gsh_syn * m.gsh_synth_mod
    d_gsh = (
        gsh_syn
        - p.k_gsh_deg * gsh
        - p.k_gsh_ox * ros * gsh
        - p.gsh_consume_scale * m.gsh_extra * gsh
    )

    # --- Caspase: triggered by high ROS, low ATP, direct inducers, or DNA damage ---
    trigger = (
        p.w_ros * _relu(ros - p.ros_thresh)
        + p.w_atp * _relu(p.atp_thresh - atp)
        + p.w_apop * m.apop_input
        + p.w_dna * m.dna_input
    )
    d_casp = (
        p.k_casp_on * trigger * (1.0 - casp)
        + p.k_casp_fb * casp * (1.0 - casp)
        - p.k_casp_off * casp
    )

    # --- Membrane: repair vs lipid peroxidation, disruptors, and necrosis ---
    damage = (
        p.k_mem_lpo * ros * _relu(1.0 - gsh)
        + p.mem_input_scale * m.mem_input
        + p.k_necro * _relu(p.atp_necro - atp)
    )
    d_mem = p.k_mem_rep * (1.0 - mem) - damage * mem

    return np.array([d_atp, d_ros, d_gsh, d_casp, d_mem])


def baseline_state() -> np.ndarray:
    return np.array([BASELINE_STATE[k] for k in STATE_ORDER], dtype=float)


def viability(atp: float, ros: float, gsh: float, casp: float, mem: float) -> float:
    """Cell viability (0..1): survives only if it neither apoptoses nor lyses."""
    v = np.clip(mem, 0.0, 1.0) * (1.0 - np.clip(casp, 0.0, 1.0))
    return float(np.clip(v, 0.0, 1.0))
