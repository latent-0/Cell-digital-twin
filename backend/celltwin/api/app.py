"""FastAPI application exposing the cell digital twin.

Run: uvicorn celltwin.api.app:app --reload  (from the backend/ directory)
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from ..experiments.screen import combination, dose_response
from ..engine.simulate import simulate
from ..model.registry import (
    build_graph,
    list_cells,
    list_toxins,
    load_all_toxins,
    load_cell,
    load_toxin,
)
from ..schemas import (
    CombinationResult,
    DoseResponseResult,
    Exposure,
    SimulationRequest,
    SimulationResult,
)

app = FastAPI(title="Cell Digital Twin", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/cells")
def get_cells() -> list[str]:
    return list_cells()


@app.get("/toxins")
def get_toxins() -> list[dict]:
    out = []
    cell = load_cell("hepatocyte")
    for tid in list_toxins():
        t = load_toxin(tid)
        out.append({
            "id": t.id, "name": t.name, "class": t.toxin_class,
            "description": t.description.strip(),
            "requires_bioactivation": t.requires_bioactivation,
            "targets": [{"node": tg.node, "effect": tg.effect.value,
                         "process": cell.resolve_process(tg.node)} for tg in t.targets],
        })
    return out


@app.get("/cells/{cell_id}/graph")
def get_graph(cell_id: str) -> dict:
    import networkx as nx
    try:
        cell = load_cell(cell_id)
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc))
    g = build_graph(cell)
    pos = nx.spring_layout(g, seed=42, k=1.4, iterations=200)
    xs = [p[0] for p in pos.values()] or [0]
    ys = [p[1] for p in pos.values()] or [0]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    norm = lambda v, lo, hi: (v - lo) / (hi - lo) if hi > lo else 0.5
    nodes = []
    for n, d in g.nodes(data=True):
        px, py = pos[n]
        nodes.append({"id": n, **d, "x": round(norm(px, x0, x1), 4), "y": round(norm(py, y0, y1), 4)})
    return {
        "nodes": nodes,
        "edges": [{"source": u, "target": v, **d} for u, v, d in g.edges(data=True)],
    }


@app.post("/simulate", response_model=SimulationResult)
def post_simulate(request: SimulationRequest) -> SimulationResult:
    try:
        cell = load_cell(request.cell_id)
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc))
    toxins = load_all_toxins()
    for exp in request.exposures:
        if exp.toxin_id not in toxins:
            raise HTTPException(404, f"unknown toxin '{exp.toxin_id}'")
    return simulate(request, cell, toxins)


@app.get("/dose-response/{toxin_id}", response_model=DoseResponseResult)
def get_dose_response(toxin_id: str, cell_id: str = "hepatocyte", hours: float = 24.0, cyp: float | None = None) -> DoseResponseResult:
    try:
        cell = load_cell(cell_id)
        toxin = load_toxin(toxin_id)
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc))
    return dose_response(toxin, cell, load_all_toxins(), duration_h=hours, cyp_activity=cyp)


@app.post("/combine", response_model=CombinationResult)
def post_combine(exposures: list[Exposure], cell_id: str = "hepatocyte", hours: float = 24.0, cyp: float | None = None) -> CombinationResult:
    try:
        cell = load_cell(cell_id)
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc))
    toxins = load_all_toxins()
    return combination(exposures, cell, toxins, duration_h=hours, cyp_activity=cyp)


# --- On-demand analysis endpoints (heavier; the UI shows a loading state) ---
@app.get("/validate")
def get_validate() -> dict:
    from ..validation.validate import validate_model
    rep = validate_model()
    return {
        "spearman": rep.spearman, "medianFold": rep.median_fold_error,
        "nPass": rep.n_within_1_log, "n": len(rep.entries),
        "entries": [{"toxin": e.toxin, "ref": e.reference_ic50, "model": e.model_ic50,
                     "fold": e.fold_error, "conf": e.confidence, "pass": bool(e.within_1_log)}
                    for e in rep.entries if e.model_ic50],
    }


@app.get("/fit-bayes/{toxin_id}")
def get_fit_bayes(toxin_id: str, cell_id: str = "hepatocyte") -> dict:
    import numpy as np
    import jax.numpy as jnp
    from ..inference.calibrate_bayes import fit_toxin, synth_dose_response
    from ..inference.jax_ode import default_params, predict_dose_response
    from ..inference.specs import target_specs
    from ..inference.diagnostics import identifiability
    try:
        cell = load_cell(cell_id); toxin = load_toxin(toxin_id)
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc))
    toxins = load_all_toxins()
    m0 = dose_response(toxin, cell, toxins).ic50
    if not m0:
        raise HTTPException(400, f"{toxin_id} has no cytotoxic IC50 to calibrate")
    doses, obs = synth_dose_response(toxin, cell, center_ic50=m0, true_potency=1.0, seed=1)
    fit = fit_toxin(toxin, cell, doses, obs, base_model_ic50=m0, num_warmup=250, num_samples=450)
    p = default_params(); specs = target_specs(toxin, cell)
    grid = np.logspace(np.log10(m0 / 30), np.log10(m0 * 30), 22)
    pot = fit.potency_samples[:: max(1, len(fit.potency_samples) // 60)]
    curves = np.stack([np.asarray(predict_dose_response(
        specs, float(sv), jnp.asarray(grid), p, cell.cyp_activity, toxin.requires_bioactivation, 24.0))
        for sv in pot])
    ident = identifiability(fit)
    return {
        "toxin": toxin_id, "grid": [float(d) for d in grid],
        "median": [float(v) for v in np.median(curves, 0)],
        "lo": [float(v) for v in np.percentile(curves, 5, 0)],
        "hi": [float(v) for v in np.percentile(curves, 95, 0)],
        "obsDoses": [float(d) for d in doses], "obs": [[float(v) for v in row] for row in obs],
        "ic50": {"median": fit.ic50_median, "lo": fit.ic50_ci90[0], "hi": fit.ic50_ci90[1]},
        "rHat": fit.r_hat_potency, "shrinkage": ident["shrinkage"], "verdict": ident["verdict"],
    }


@app.get("/assimilate")
def get_assimilate(true_severity: float = 0.7, n_obs: int = 9) -> dict:
    import numpy as np
    from ..inference.assimilate import particle_filter, synth_observations
    obs_times = np.linspace(2, 24, n_obs)
    obs = synth_observations(true_severity, obs_times, obs_indices=[0, 1], obs_noise=0.05, seed=3)
    res = particle_filter(obs_times, obs, obs_indices=[0, 1], obs_noise=0.05, n_particles=2000, seed=1)
    return {
        "truth": true_severity, "times": [float(t) for t in res.times],
        "mean": [float(v) for v in res.theta_mean],
        "lo": [float(v) for v in res.theta_ci90[:, 0]], "hi": [float(v) for v in res.theta_ci90[:, 1]],
    }
