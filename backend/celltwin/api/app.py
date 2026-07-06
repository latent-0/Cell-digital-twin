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
    for tid in list_toxins():
        t = load_toxin(tid)
        out.append({"id": t.id, "name": t.name, "class": t.toxin_class})
    return out


@app.get("/cells/{cell_id}/graph")
def get_graph(cell_id: str) -> dict:
    try:
        cell = load_cell(cell_id)
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc))
    g = build_graph(cell)
    return {
        "nodes": [{"id": n, **d} for n, d in g.nodes(data=True)],
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
def get_dose_response(toxin_id: str, cell_id: str = "hepatocyte", hours: float = 24.0, cyp: float = 1.0) -> DoseResponseResult:
    try:
        cell = load_cell(cell_id)
        toxin = load_toxin(toxin_id)
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc))
    return dose_response(toxin, cell, load_all_toxins(), duration_h=hours, cyp_activity=cyp)


@app.post("/combine", response_model=CombinationResult)
def post_combine(exposures: list[Exposure], cell_id: str = "hepatocyte", hours: float = 24.0, cyp: float = 1.0) -> CombinationResult:
    try:
        cell = load_cell(cell_id)
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc))
    toxins = load_all_toxins()
    return combination(exposures, cell, toxins, duration_h=hours, cyp_activity=cyp)
