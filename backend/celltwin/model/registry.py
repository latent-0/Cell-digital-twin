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
REFERENCE_DIR = DATA_DIR / "reference"
CALIBRATION_FILE = REFERENCE_DIR / "calibration.yaml"


def _load_yaml(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


@functools.lru_cache(maxsize=1)
def _calibration() -> dict[str, float]:
    """Per-toxin effective-potency scale factors, learned from reference data.

    Kept as a separate overlay so the authored (interpretable) potencies in
    data/toxins/*.yaml stay untouched; calibration to cellular cytotoxicity is a
    transparent, re-derivable layer on top (and later, so is a Bayesian posterior).
    """
    if not CALIBRATION_FILE.exists():
        return {}
    data = _load_yaml(CALIBRATION_FILE) or {}
    return {k: float(v) for k, v in (data.get("potency_scale") or {}).items()}


def clear_caches() -> None:
    load_cell.cache_clear()
    load_toxin.cache_clear()
    _calibration.cache_clear()


@functools.lru_cache(maxsize=None)
def load_cell(cell_id: str) -> CellModel:
    path = CELLS_DIR / f"{cell_id}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Unknown cell model '{cell_id}' (looked in {path})")
    data = _load_yaml(path)

    # A cell may `extends` a base cell to inherit its relation graph (DRY): the
    # child reuses the base's nodes/relations/process_map and overrides its own
    # identity, parameters, and cyp_activity (and any graph field it restates).
    base_id = data.pop("extends", None)
    if base_id:
        base = load_cell(base_id).model_dump()
        for key in ("nodes", "relations", "process_map"):
            data.setdefault(key, base[key])
        merged_params = {**base.get("parameters", {}), **data.get("parameters", {})}
        data["parameters"] = merged_params
        data.setdefault("cyp_activity", base.get("cyp_activity", 1.0))

    return CellModel.model_validate(data)


@functools.lru_cache(maxsize=None)
def load_toxin(toxin_id: str) -> Toxin:
    path = TOXINS_DIR / f"{toxin_id}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Unknown toxin '{toxin_id}' (looked in {path})")
    toxin = Toxin.model_validate(_load_yaml(path))
    scale = _calibration().get(toxin_id)
    if scale and scale != 1.0:
        for tgt in toxin.targets:
            tgt.ic50 *= scale  # calibration overlay: shift effective potency
    return toxin


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
