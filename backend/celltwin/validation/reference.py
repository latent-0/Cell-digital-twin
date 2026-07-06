"""Load the literature cytotoxicity reference set."""

from __future__ import annotations

from dataclasses import dataclass

from ..model.registry import REFERENCE_DIR, _load_yaml

CYTOTOX_FILE = REFERENCE_DIR / "cytotoxicity.yaml"


@dataclass(frozen=True)
class CytotoxReference:
    toxin: str
    cell: str
    ic50_uM: float
    confidence: str
    source: str
    note: str = ""


def load_references() -> list[CytotoxReference]:
    data = _load_yaml(CYTOTOX_FILE) or {}
    out: list[CytotoxReference] = []
    for r in data.get("references", []):
        out.append(
            CytotoxReference(
                toxin=r["toxin"],
                cell=r.get("cell", "hepatocyte"),
                ic50_uM=float(r["ic50_uM"]),
                confidence=r.get("confidence", "low"),
                source=r.get("source", ""),
                note=r.get("note", ""),
            )
        )
    return out
