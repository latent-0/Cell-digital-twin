"""Mechanism attribution: given a trajectory, explain *why* the cell died.

Converts the end-state of the ODE run into interpretable death-mode fractions
and a short narrative, using both the dynamic markers and the toxin engagement.
"""

from __future__ import annotations

import numpy as np

from ..engine.coupling import Modifiers
from ..engine.params import BASELINE_STATE
from ..schemas import MechanismAttribution


def attribute(final: dict[str, float], mods: Modifiers) -> MechanismAttribution:
    atp = final["atp"]
    ros = final["ros"]
    gsh = final["gsh"]
    casp = final["caspase"]
    mem = final["membrane"]

    # Death-mode magnitudes (0..1).
    apoptotic = float(np.clip(casp, 0.0, 1.0))
    necrotic = float(np.clip(1.0 - mem, 0.0, 1.0))

    # Upstream driver magnitudes relative to baseline.
    energy_failure = float(np.clip((BASELINE_STATE["atp"] - atp) / BASELINE_STATE["atp"], 0.0, 1.0))
    oxidative_stress = float(
        np.clip(
            0.5 * np.clip((ros - BASELINE_STATE["ros"]) / max(BASELINE_STATE["ros"], 1e-6), 0.0, 1.0)
            + 0.5 * np.clip((BASELINE_STATE["gsh"] - gsh) / BASELINE_STATE["gsh"], 0.0, 1.0),
            0.0,
            1.0,
        )
    )

    modes = {
        "apoptosis": apoptotic,
        "necrosis": necrotic,
        "energy failure": energy_failure,
        "oxidative stress": oxidative_stress,
    }
    dominant = max(modes, key=modes.get)
    if modes[dominant] < 0.05:
        dominant = "none (cell healthy)"

    engaged = ", ".join(sorted(mods.engagement)) if mods.engagement else "none"
    narrative = (
        f"Dominant outcome: {dominant}. "
        f"Death markers -> apoptosis {apoptotic:.0%}, necrosis {necrotic:.0%}. "
        f"Drivers -> energy failure {energy_failure:.0%}, oxidative stress {oxidative_stress:.0%}. "
        f"Toxin-engaged processes: {engaged}."
    )

    return MechanismAttribution(
        dominant=dominant,
        apoptotic=apoptotic,
        necrotic=necrotic,
        energy_failure=energy_failure,
        oxidative_stress=oxidative_stress,
        narrative=narrative,
    )
