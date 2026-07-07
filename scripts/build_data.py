#!/usr/bin/env python3
"""Precompute real model outputs for the static frontend (frontend/twindata.json).

Runs the actual celltwin engine, screening, validation, Bayesian calibration and
data assimilation, and serializes everything the dashboard needs. No mock data.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

import networkx as nx
import numpy as np

from celltwin.engine.simulate import simulate
from celltwin.experiments.screen import dose_response
from celltwin.model.registry import build_graph, list_cells, list_toxins, load_all_toxins, load_cell
from celltwin.schemas import Exposure, SimulationRequest

R = lambda x, n=4: round(float(x), n)


def graph_data():
    cell = load_cell("hepatocyte")
    g = build_graph(cell)
    pos = nx.spring_layout(g, seed=42, k=1.4, iterations=200)
    xs = [p[0] for p in pos.values()]
    ys = [p[1] for p in pos.values()]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)

    def nx_(v, lo, hi):
        return (v - lo) / (hi - lo) if hi > lo else 0.5

    nodes = []
    for n in cell.nodes:
        px, py = pos[n.id]
        nodes.append({
            "id": n.id, "label": n.label, "type": n.type.value,
            "process": n.process, "compartment": n.compartment,
            "x": R(nx_(px, x0, x1), 4), "y": R(nx_(py, y0, y1), 4),
        })
    edges = [{"source": r.source, "target": r.target, "type": r.type.value, "sign": r.sign}
             for r in cell.relations]
    return {"nodes": nodes, "edges": edges}


def per_pair(cell, toxin, toxins):
    dr = dose_response(toxin, cell, toxins, n_doses=22)
    ic50 = dr.ic50
    curve = [[R(p.dose, 6), R(p.viability, 4)] for p in dr.curve]

    tc_dose = (ic50 * 3.0) if ic50 else max(t.ic50 for t in toxin.targets) * 50
    res = simulate(
        SimulationRequest(exposures=[Exposure(toxin_id=toxin.id, dose=tc_dose)],
                          duration_h=24, n_points=40),
        cell, toxins,
    )
    tc = {
        "t": [R(p.t, 3) for p in res.trajectory],
        "atp": [R(p.atp) for p in res.trajectory],
        "ros": [R(p.ros) for p in res.trajectory],
        "gsh": [R(p.gsh) for p in res.trajectory],
        "casp": [R(p.caspase) for p in res.trajectory],
        "mem": [R(p.membrane) for p in res.trajectory],
        "via": [R(p.viability) for p in res.trajectory],
    }
    m = res.mechanism
    return {
        "dr": curve,
        "ic50": R(ic50, 5) if ic50 else None,
        "hill": R(dr.hill, 3) if dr.hill else None,
        "tcDose": R(tc_dose, 5),
        "tc": tc,
        "mech": {
            "dominant": m.dominant,
            "apoptotic": R(m.apoptotic, 3), "necrotic": R(m.necrotic, 3),
            "energy": R(m.energy_failure, 3), "oxidative": R(m.oxidative_stress, 3),
            "narrative": m.narrative,
        },
    }


def results_data():
    toxins = load_all_toxins()
    out = {}
    for cid in list_cells():
        cell = load_cell(cid)
        out[cid] = {}
        for tid in list_toxins():
            out[cid][tid] = per_pair(cell, toxins[tid], toxins)
    return out


def validation_data():
    from celltwin.validation.validate import validate_model
    rep = validate_model()
    entries = [{
        "toxin": e.toxin, "ref": R(e.reference_ic50, 5),
        "model": R(e.model_ic50, 5) if e.model_ic50 else None,
        "fold": R(e.fold_error, 3) if e.fold_error else None,
        "conf": e.confidence, "pass": bool(e.within_1_log),
    } for e in rep.entries]
    return {"entries": entries, "spearman": R(rep.spearman, 4),
            "medianFold": R(rep.median_fold_error, 3), "nPass": int(rep.n_within_1_log),
            "n": len(rep.entries)}


def bayes_data():
    import jax.numpy as jnp
    from celltwin.inference.calibrate_bayes import fit_toxin, synth_dose_response
    from celltwin.inference.jax_ode import default_params, predict_dose_response
    from celltwin.inference.specs import target_specs
    from celltwin.inference.diagnostics import identifiability

    cell = load_cell("hepatocyte")
    toxins = load_all_toxins()
    rot = toxins["rotenone"]
    m0 = dose_response(rot, cell, toxins).ic50
    doses, obs = synth_dose_response(rot, cell, center_ic50=m0, true_potency=1.0, seed=1)
    fit = fit_toxin(rot, cell, doses, obs, base_model_ic50=m0, num_warmup=400, num_samples=800, seed=0)

    # Posterior predictive dose-response band.
    p = default_params(); specs = target_specs(rot, cell)
    grid = np.logspace(np.log10(m0 / 30), np.log10(m0 * 30), 24)
    pot = fit.potency_samples[:: max(1, len(fit.potency_samples) // 80)]
    curves = np.stack([
        np.asarray(predict_dose_response(specs, float(s), jnp.asarray(grid), p,
                                         cell.cyp_activity, rot.requires_bioactivation, 24.0))
        for s in pot
    ])
    ident = identifiability(fit)
    return {
        "toxin": "rotenone",
        "obsDoses": [R(d, 5) for d in doses],
        "obs": [[R(v, 4) for v in row] for row in obs],
        "grid": [R(d, 5) for d in grid],
        "median": [R(v, 4) for v in np.median(curves, 0)],
        "lo": [R(v, 4) for v in np.percentile(curves, 5, 0)],
        "hi": [R(v, 4) for v in np.percentile(curves, 95, 0)],
        "ic50": {"median": R(fit.ic50_median, 4), "lo": R(fit.ic50_ci90[0], 4), "hi": R(fit.ic50_ci90[1], 4)},
        "rHat": R(fit.r_hat_potency, 4),
        "shrinkage": R(ident["shrinkage"], 3), "verdict": ident["verdict"],
    }


def assim_data():
    from celltwin.inference.assimilate import particle_filter, synth_observations
    obs_times = np.linspace(2, 24, 9)
    truth = 0.7
    obs = synth_observations(truth, obs_times, obs_indices=[0, 1], obs_noise=0.05, seed=3)
    res = particle_filter(obs_times, obs, obs_indices=[0, 1], obs_noise=0.05, n_particles=2500, seed=1)
    return {
        "truth": truth,
        "times": [R(t, 2) for t in res.times],
        "mean": [R(v, 4) for v in res.theta_mean],
        "lo": [R(v, 4) for v in res.theta_ci90[:, 0]],
        "hi": [R(v, 4) for v in res.theta_ci90[:, 1]],
        "obsAtp": [R(o[0], 4) for o in obs],
        "obsRos": [R(o[1], 4) for o in obs],
        "stateAtp": [R(s[0], 4) for s in res.state_mean],
        "stateRos": [R(s[1], 4) for s in res.state_mean],
    }


def main():
    print("Computing graph, results (5x18), validation, Bayesian fit, assimilation...")
    data = {
        "cells": [{"id": c.id, "name": c.name, "cyp": R(c.cyp_activity, 3)}
                  for c in (load_cell(cid) for cid in list_cells())],
        "toxins": [],
        "graph": graph_data(),
        "results": results_data(),
        "validation": validation_data(),
        "bayes": bayes_data(),
        "assim": assim_data(),
    }
    toxins = load_all_toxins()
    cell0 = load_cell("hepatocyte")
    for tid in list_toxins():
        t = toxins[tid]
        data["toxins"].append({
            "id": t.id, "name": t.name, "cls": t.toxin_class, "desc": t.description.strip(),
            "bioact": t.requires_bioactivation,
            "targets": [{"node": tg.node, "effect": tg.effect.value,
                         "process": cell0.resolve_process(tg.node)} for tg in t.targets],
        })

    out = Path(__file__).resolve().parents[1] / "frontend" / "twindata.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(data, separators=(",", ":")))
    kb = out.stat().st_size / 1024
    print(f"Wrote {out} ({kb:.0f} KB)")


if __name__ == "__main__":
    main()
