"""Validate model cytotoxicity against the literature reference set.

Reports, per toxin, the model's emergent cytotoxic IC50 vs the literature anchor
(fold-error and |log10| error), and, across all toxins, the rank-order (Spearman)
correlation -- the honest v1 acceptance criterion (see docs/PLAN.md §7).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
from scipy.stats import spearmanr

from ..experiments.screen import dose_response
from ..model.registry import load_all_toxins, load_cell
from .reference import CytotoxReference, load_references


@dataclass
class ToxinValidation:
    toxin: str
    cell: str
    reference_ic50: float
    model_ic50: Optional[float]
    confidence: str
    fold_error: Optional[float]   # max(model/ref, ref/model), >=1
    log_error: Optional[float]    # |log10(model/ref)|
    within_1_log: bool


@dataclass
class ValidationReport:
    entries: list[ToxinValidation]
    spearman: Optional[float]
    spearman_p: Optional[float]
    n_within_1_log: int
    n_scored: int
    median_fold_error: Optional[float]


def validate_model(duration_h: float = 24.0) -> ValidationReport:
    toxins = load_all_toxins()
    refs: list[CytotoxReference] = load_references()

    entries: list[ToxinValidation] = []
    ref_vals: list[float] = []
    model_vals: list[float] = []

    for ref in refs:
        if ref.toxin not in toxins:
            continue
        cell = load_cell(ref.cell)
        dr = dose_response(toxins[ref.toxin], cell, toxins, duration_h=duration_h)
        model_ic50 = dr.ic50

        if model_ic50 is None or model_ic50 <= 0:
            entries.append(
                ToxinValidation(
                    toxin=ref.toxin, cell=ref.cell, reference_ic50=ref.ic50_uM,
                    model_ic50=model_ic50, confidence=ref.confidence,
                    fold_error=None, log_error=None, within_1_log=False,
                )
            )
            continue

        log_err = abs(np.log10(model_ic50 / ref.ic50_uM))
        fold = 10 ** log_err
        entries.append(
            ToxinValidation(
                toxin=ref.toxin, cell=ref.cell, reference_ic50=ref.ic50_uM,
                model_ic50=model_ic50, confidence=ref.confidence,
                fold_error=fold, log_error=log_err, within_1_log=log_err <= 1.0,
            )
        )
        ref_vals.append(ref.ic50_uM)
        model_vals.append(model_ic50)

    spearman = spearman_p = None
    if len(ref_vals) >= 3:
        rho, p = spearmanr(np.log10(ref_vals), np.log10(model_vals))
        spearman, spearman_p = float(rho), float(p)

    scored = [e for e in entries if e.fold_error is not None]
    median_fold = float(np.median([e.fold_error for e in scored])) if scored else None

    return ValidationReport(
        entries=entries,
        spearman=spearman,
        spearman_p=spearman_p,
        n_within_1_log=sum(e.within_1_log for e in entries),
        n_scored=len(scored),
        median_fold_error=median_fold,
    )


def format_report(report: ValidationReport) -> str:
    lines = [
        "Cytotoxicity validation (model IC50 vs literature)",
        "",
        f"{'toxin':22s} {'cell':12s} {'ref IC50':>10s} {'model IC50':>12s} {'fold':>7s} {'conf':>7s}  1-log",
        "-" * 82,
    ]
    for e in sorted(report.entries, key=lambda x: (x.fold_error or 1e9)):
        m = f"{e.model_ic50:.3g}" if e.model_ic50 is not None else "NR"
        f = f"{e.fold_error:.2f}x" if e.fold_error is not None else "-"
        ok = "PASS" if e.within_1_log else "----"
        lines.append(
            f"{e.toxin:22s} {e.cell:12s} {e.reference_ic50:>10.3g} {m:>12s} {f:>7s} {e.confidence:>7s}  {ok}"
        )
    lines.append("-" * 82)
    rho = f"{report.spearman:.3f}" if report.spearman is not None else "n/a"
    mfe = f"{report.median_fold_error:.2f}x" if report.median_fold_error is not None else "n/a"
    lines.append(
        f"within 1 log: {report.n_within_1_log}/{len(report.entries)}   "
        f"median fold-error: {mfe}   rank-order (Spearman) rho: {rho}"
    )
    return "\n".join(lines)
