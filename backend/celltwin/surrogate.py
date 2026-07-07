"""ML surrogate — a fast learned emulator of the mechanistic ODE endpoints.

The mechanistic engine is ground truth, but every readout costs an integration.
A surrogate learns the mapping

    process-modifier vector  ->  endpoint readouts

from the simulator's own outputs, so screening becomes near-instant. This is the
hybrid design: the mechanistic core generates data, an MLP learns to emulate it.

Feature vector = the 8 coupling-process modifiers (engine.coupling.Modifiers);
targets = the 6 endpoint readouts. Any toxin@dose is encoded by running the
normal coupling (build_modifiers) and reading off its modifier vector.

(Adapted from the parallel `blc5xp` implementation into this engine.)
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from .engine.coupling import Modifiers, build_modifiers
from .engine.simulate import run_modifiers
from .schemas import CellModel, Exposure, Toxin

FEATURES = ("etc_activity", "atp_synth_mod", "ros_input", "gsh_synth_mod",
            "gsh_extra", "mem_input", "apop_input", "dna_input")
# Only bounded [0,1] endpoints are emulated (ROS is unbounded and would dominate
# the multi-output loss); ROS can be recovered from the engine when needed.
READOUTS = ("viability", "atp", "gsh", "caspase", "membrane")
_MULT = {"etc_activity", "atp_synth_mod", "gsh_synth_mod"}  # neutral = 1; others neutral = 0


def modifiers_to_vec(m: Modifiers) -> np.ndarray:
    return np.array([getattr(m, f) for f in FEATURES], dtype=float)


def vec_to_modifiers(v: np.ndarray) -> Modifiers:
    return Modifiers(**{f: float(v[i]) for i, f in enumerate(FEATURES)})


def _sample(rng: np.random.Generator, sparsity: float) -> np.ndarray:
    hi = {"ros_input": 3.0, "gsh_extra": 3.0, "mem_input": 2.0, "apop_input": 2.0, "dna_input": 2.0}
    v = np.empty(len(FEATURES))
    for i, f in enumerate(FEATURES):
        neutral = 1.0 if f in _MULT else 0.0
        if rng.random() < sparsity:
            v[i] = neutral
        else:
            v[i] = rng.uniform(0.0, 1.0) if f in _MULT else rng.uniform(0.0, hi[f])
    return v


def generate_dataset(n_samples: int, *, sparsity: float = 0.5, duration_h: float = 24.0,
                     seed: int = 0) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    X = np.zeros((n_samples, len(FEATURES)))
    Y = np.zeros((n_samples, len(READOUTS)))
    for i in range(n_samples):
        v = _sample(rng, sparsity)
        out = run_modifiers(vec_to_modifiers(v), duration_h=duration_h)
        X[i] = v
        Y[i] = [out[r] for r in READOUTS]
    return X, Y


class Surrogate:
    """A fitted MLP emulator of the mechanistic model's endpoint readouts."""

    def __init__(self, pipeline, features=FEATURES, readouts=READOUTS):
        self.pipeline = pipeline
        self.features = tuple(features)
        self.readouts = tuple(readouts)

    def predict_vec(self, v: np.ndarray) -> dict[str, float]:
        pred = self.pipeline.predict(np.atleast_2d(v))[0]
        return {r: float(np.clip(x, 0.0, 1.0)) for r, x in zip(self.readouts, pred)}

    def predict_modifiers(self, m: Modifiers) -> dict[str, float]:
        return self.predict_vec(modifiers_to_vec(m))

    def predict_toxin(self, cell: CellModel, toxin: Toxin, dose: float,
                      toxins: dict[str, Toxin], cyp_activity: float | None = None) -> dict[str, float]:
        cyp = cyp_activity if cyp_activity is not None else cell.cyp_activity
        m = build_modifiers(cell, [Exposure(toxin_id=toxin.id, dose=dose)], toxins, cyp)
        return self.predict_modifiers(m)

    def viability(self, cell: CellModel, toxin: Toxin, dose: float,
                  toxins: dict[str, Toxin], cyp_activity: float | None = None) -> float:
        return self.predict_toxin(cell, toxin, dose, toxins, cyp_activity)["viability"]

    def save(self, path: str | Path) -> Path:
        import joblib
        joblib.dump({"pipeline": self.pipeline, "features": self.features, "readouts": self.readouts}, path)
        return Path(path)

    @classmethod
    def load(cls, path: str | Path) -> "Surrogate":
        import joblib
        d = joblib.load(path)
        return cls(d["pipeline"], d["features"], d["readouts"])


def train_surrogate(*, n_samples: int = 3000, hidden_layer_sizes=(64, 64),
                    test_fraction: float = 0.2, duration_h: float = 24.0,
                    seed: int = 0) -> tuple[Surrogate, dict]:
    """Generate data from the simulator, fit an MLP, return (surrogate, metrics)."""
    from sklearn.metrics import mean_absolute_error, r2_score
    from sklearn.model_selection import train_test_split
    from sklearn.neural_network import MLPRegressor
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler

    X, Y = generate_dataset(n_samples, duration_h=duration_h, seed=seed)
    X_tr, X_te, Y_tr, Y_te = train_test_split(X, Y, test_size=test_fraction, random_state=seed)
    pipe = Pipeline([
        ("scale", StandardScaler()),
        ("mlp", MLPRegressor(hidden_layer_sizes=hidden_layer_sizes, activation="relu",
                             max_iter=2000, early_stopping=True, random_state=seed)),
    ])
    pipe.fit(X_tr, Y_tr)
    pred = np.clip(pipe.predict(X_te), 0.0, 1.0)
    metrics = {
        "n_samples": n_samples, "n_test": len(X_te),
        "r2_overall": float(r2_score(Y_te, pred)),
        "mae_overall": float(mean_absolute_error(Y_te, pred)),
        "per_readout": {r: {"r2": float(r2_score(Y_te[:, j], pred[:, j])),
                            "mae": float(mean_absolute_error(Y_te[:, j], pred[:, j]))}
                        for j, r in enumerate(READOUTS)},
    }
    return Surrogate(pipe), metrics
