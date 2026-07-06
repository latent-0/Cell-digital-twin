"""Baseline rate constants for the mechanistic ODE core.

Values are chosen (and unit-tested) so the unperturbed cell rests at the
homeostatic steady state [ATP=1, ROS=0.05, GSH=1, CASP=0, MEM=1]. Time is in
hours. Parameters are literature-informed placeholders; Phase 4 calibrates them
against reference-toxin data (see docs/PLAN.md §7).
"""

from __future__ import annotations

from dataclasses import dataclass, fields


@dataclass
class Params:
    # --- ATP / mitochondrial bioenergetics ---
    k_atp_prod: float = 1.0     # max ATP production (ETC-driven)
    k_atp_use: float = 1.0      # basal ATP consumption

    # --- ROS / oxidative stress ---
    k_ros_basal: float = 0.10   # baseline ROS generation
    k_ros_etc: float = 1.0      # extra ROS leak from a dysfunctional ETC
    k_ros_scav: float = 2.0     # GSH-dependent ROS scavenging
    ros_input_scale: float = 1.5  # per-unit-occupancy ROS from oxidative toxins

    # --- Glutathione buffer ---
    k_gsh_syn: float = 0.55     # GSH synthesis (balances baseline turnover+oxidation)
    k_gsh_deg: float = 0.50     # GSH turnover
    k_gsh_ox: float = 1.0       # GSH consumed while scavenging ROS
    gsh_consume_scale: float = 1.0  # per-unit-occupancy GSH drain from depleters

    # --- Apoptosis / caspase decision ---
    k_casp_on: float = 0.5      # trigger-driven activation
    k_casp_fb: float = 0.3      # positive feedback (commitment)
    k_casp_off: float = 0.05    # deactivation
    ros_thresh: float = 0.30    # ROS above which apoptosis is triggered
    atp_thresh: float = 0.40    # ATP below which apoptosis is triggered
    w_ros: float = 1.0
    w_atp: float = 1.0

    # --- Membrane integrity / necrosis ---
    k_mem_lpo: float = 1.0      # lipid-peroxidation damage (ROS x low-GSH)
    k_mem_rep: float = 0.20     # membrane repair
    k_necro: float = 1.0        # necrosis from catastrophic ATP loss
    atp_necro: float = 0.20     # ATP below which necrosis kicks in
    mem_input_scale: float = 2.0  # per-unit-occupancy damage from disruptors

    def with_overrides(self, overrides: dict[str, float]) -> "Params":
        valid = {f.name for f in fields(self)}
        data = {f.name: getattr(self, f.name) for f in fields(self)}
        for k, v in overrides.items():
            if k in valid:
                data[k] = float(v)
        return Params(**data)


#: Homeostatic steady state the unperturbed cell should rest at.
BASELINE_STATE = {
    "atp": 1.0,
    "ros": 0.05,
    "gsh": 1.0,
    "caspase": 0.0,
    "membrane": 1.0,
}

STATE_ORDER = ("atp", "ros", "gsh", "caspase", "membrane")
