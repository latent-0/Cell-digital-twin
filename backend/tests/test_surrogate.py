"""ML surrogate: learned emulator of the ODE endpoints (salvaged from blc5xp).

The surrogate is a fast approximation. It is accurate for the graded endpoints
(ATP/GSH/membrane); viability/caspase are switch-like and only moderately
emulated, so we assert the robust claims, not perfection.
"""

import numpy as np

from celltwin.model.registry import load_all_toxins, load_cell
from celltwin.surrogate import (
    FEATURES, READOUTS, Surrogate, modifiers_to_vec, train_surrogate, vec_to_modifiers,
)


def test_modifier_vec_roundtrip():
    v = np.array([0.7, 0.9, 1.2, 0.8, 0.5, 0.3, 0.2, 0.1])
    assert np.allclose(modifiers_to_vec(vec_to_modifiers(v)), v)
    assert len(FEATURES) == 8 and "ros" not in READOUTS


def test_surrogate_trains_and_emulates_smooth_endpoints():
    sur, m = train_surrogate(n_samples=1200, seed=0)
    assert m["r2_overall"] > 0.8
    # graded endpoints are learned well
    for r in ("atp", "gsh", "membrane"):
        assert m["per_readout"][r]["r2"] > 0.85, f"{r} R2 too low: {m['per_readout'][r]['r2']}"


def test_surrogate_tracks_engine_on_extremes():
    """Away from the death threshold, surrogate viability tracks the engine."""
    cell = load_cell("hepatocyte"); toxins = load_all_toxins()
    sur, _ = train_surrogate(n_samples=1500, seed=0)
    from celltwin.experiments.screen import dose_response
    ic = dose_response(toxins["rotenone"], cell, toxins).ic50
    hi = sur.viability(cell, toxins["rotenone"], ic * 5, toxins)   # well above IC50 -> dead
    lo = sur.viability(cell, toxins["rotenone"], ic / 20, toxins)  # well below -> alive
    assert hi < 0.3 and lo > 0.7


def test_surrogate_save_load(tmp_path):
    sur, _ = train_surrogate(n_samples=400, seed=0)
    p = sur.save(tmp_path / "s.joblib")
    loaded = Surrogate.load(p)
    cell = load_cell("hepatocyte"); toxins = load_all_toxins()
    a = sur.predict_toxin(cell, toxins["rotenone"], 50.0, toxins)
    b = loaded.predict_toxin(cell, toxins["rotenone"], 50.0, toxins)
    assert a == b
