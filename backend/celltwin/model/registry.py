"""Load cell models and toxins from the version-controlled YAML data files."""

from __future__ import annotations

import functools
from pathlib import Path

import networkx as nx
import yaml

from ..schemas import CellModel, Toxin

# repo_root/data
DATA_DIR = Path(__file__).resolve().parents[3] / "data"
CELLS_DIR = DATA_DIR / "cells"
TOXINS_DIR = DATA_DIR / "toxins"


def _load_yaml(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


@functools.lru_cache(maxsize=None)
def load_cell(cell_id: str) -> CellModel:
    path = CELLS_DIR / f"{cell_id}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Unknown cell model '{cell_id}' (looked in {path})")
    return CellModel.model_validate(_load_yaml(path))


@functools.lru_cache(maxsize=None)
def load_toxin(toxin_id: str) -> Toxin:
    path = TOXINS_DIR / f"{toxin_id}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Unknown toxin '{toxin_id}' (looked in {path})")
    return Toxin.model_validate(_load_yaml(path))


def list_cells() -> list[str]:
    return sorted(p.stem for p in CELLS_DIR.glob("*.yaml"))


def list_toxins() -> list[str]:
    return sorted(p.stem for p in TOXINS_DIR.glob("*.yaml"))


def load_all_toxins() -> dict[str, Toxin]:
    return {tid: load_toxin(tid) for tid in list_toxins()}


def build_graph(cell: CellModel) -> nx.DiGraph:
    """Build a NetworkX directed graph of the cell's relations."""
    g = nx.DiGraph()
    for node in cell.nodes:
        g.add_node(node.id, **node.model_dump())
    for rel in cell.relations:
        g.add_edge(rel.source, rel.target, **rel.model_dump())
    return g


def validate_cell(cell: CellModel) -> list[str]:
    """Return a list of integrity problems (empty means the model is sound)."""
    problems: list[str] = []
    ids = {n.id for n in cell.nodes}
    for rel in cell.relations:
        if rel.source not in ids:
            problems.append(f"relation references unknown source node '{rel.source}'")
        if rel.target not in ids:
            problems.append(f"relation references unknown target node '{rel.target}'")
        if rel.sign not in (-1, 1):
            problems.append(f"relation {rel.source}->{rel.target} has invalid sign {rel.sign}")
    for node_id in cell.process_map:
        if node_id not in ids:
            problems.append(f"process_map references unknown node '{node_id}'")
    return problems
