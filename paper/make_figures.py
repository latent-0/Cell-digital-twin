#!/usr/bin/env python3
"""Generate all paper figures from the real celltwin engine (no illustrative data).

Outputs paper/figures/*.pdf and prints the exact numbers cited in the paper so
the text and figures stay consistent. Run: python paper/make_figures.py
"""
from __future__ import annotations
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import jax.numpy as jnp

from celltwin.model.registry import load_cell, load_all_toxins
from celltwin.experiments.screen import dose_response
from celltwin.experiments.population import CellPopulation
from celltwin.validation.validate import validate_model
from celltwin.inference.calibrate_bayes import fit_toxin, synth_dose_response
from celltwin.inference.jax_ode import default_params, predict_dose_response, integrate_traj, build_modifiers, viability
from celltwin.inference.specs import target_specs
from celltwin.inference.diagnostics import identifiability
from celltwin.inference.assimilate import particle_filter, synth_observations
from celltwin.surrogate import train_surrogate

FIG = Path(__file__).resolve().parent / "figures"
FIG.mkdir(exist_ok=True)
plt.rcParams.update({
    "font.family": "serif", "font.size": 9, "axes.linewidth": 0.6,
    "axes.spines.top": False, "axes.spines.right": False,
    "figure.dpi": 200, "savefig.bbox": "tight", "legend.frameon": False,
})
AC = "#0e7c86"; CRIT = "#cf3b3b"; GOOD = "#178a52"; MUT = "#5a6673"
NUMBERS = {}

cell = load_cell("hepatocyte")
tox = load_all_toxins()


def fig_calibration():
    rep = validate_model()
    e = [x for x in rep.entries if x.model_ic50]
    ref = np.array([x.reference_ic50 for x in e]); mod = np.array([x.model_ic50 for x in e])
    fig, ax = plt.subplots(figsize=(3.3, 3.0))
    lo, hi = min(ref.min(), mod.min()) / 3, max(ref.max(), mod.max()) * 3
    ax.plot([lo, hi], [lo, hi], "--", color=MUT, lw=1, label="$y=x$")
    ax.scatter(ref, mod, s=22, c=GOOD, edgecolor="white", lw=0.5, zorder=3)
    ax.set_xscale("log"); ax.set_yscale("log")
    ax.set_xlabel(r"literature IC$_{50}$ ($\mu$M)"); ax.set_ylabel(r"model IC$_{50}$ ($\mu$M)")
    ax.set_title(f"Calibration: {rep.n_within_1_log}/{len(rep.entries)} within 1 log, "
                 rf"$\rho={rep.spearman:.3f}$", fontsize=8.5)
    ax.legend(loc="upper left")
    fig.savefig(FIG / "fig_calibration.pdf")
    NUMBERS["calibration"] = {"nPass": rep.n_within_1_log, "n": len(rep.entries),
                              "spearman": round(rep.spearman, 3), "medianFold": round(rep.median_fold_error, 3)}


def fig_population():
    fig, ax = plt.subplots(figsize=(3.3, 3.0))
    ic = dose_response(tox["rotenone"], cell, tox).ic50
    doses = np.logspace(np.log10(ic/8), np.log10(ic*8), 22)
    single = [dose_response(tox["rotenone"], cell, tox, doses=[float(d)]).curve[0].viability for d in doses]
    ax.plot(doses, single, color=MUT, lw=1.6, label="single cell")
    for cv, col in [(0.3, AC), (0.6, CRIT)]:
        pop = CellPopulation.for_toxin(cell, tox["rotenone"], tox, n_cells=160, cv=cv, seed=0)
        vs = [pop.response(float(d))["mean_viability"] for d in doses]
        ax.plot(doses, vs, color=col, lw=1.8, label=f"population (CV={cv})")
    ax.set_xscale("log"); ax.set_xlabel(r"rotenone dose ($\mu$M)"); ax.set_ylabel("viability")
    ax.set_title("Population heterogeneity smooths the response", fontsize=8.5)
    ax.legend(loc="lower left")
    fig.savefig(FIG / "fig_population.pdf")


def fig_bayes():
    ic = dose_response(tox["rotenone"], cell, tox).ic50
    doses, obs = synth_dose_response(tox["rotenone"], cell, center_ic50=ic, true_potency=0.7, seed=1)
    fit = fit_toxin(tox["rotenone"], cell, doses, obs, base_model_ic50=ic,
                    num_warmup=400, num_samples=800, seed=0)
    p = default_params(); specs = target_specs(tox["rotenone"], cell)
    grid = np.logspace(np.log10(ic/30), np.log10(ic*30), 24)
    pot = fit.potency_samples[:: max(1, len(fit.potency_samples)//80)]
    curves = np.stack([np.asarray(predict_dose_response(specs, float(s), jnp.asarray(grid), p,
                       cell.cyp_activity, tox["rotenone"].requires_bioactivation, 24.0)) for s in pot])
    med, loq, hiq = np.median(curves, 0), np.percentile(curves, 5, 0), np.percentile(curves, 95, 0)
    ident = identifiability(fit)
    fig, ax = plt.subplots(figsize=(3.3, 3.0))
    ax.fill_between(grid, loq, hiq, color=AC, alpha=0.18, label="90% credible band")
    ax.plot(grid, med, color=AC, lw=1.8, label="posterior median")
    ax.scatter(np.repeat(doses, obs.shape[0]), obs.T.ravel(), s=8, c=MUT, alpha=0.5, label="observations")
    ax.set_xscale("log"); ax.set_xlabel(r"rotenone dose ($\mu$M)"); ax.set_ylabel("viability")
    ax.set_title(rf"NUTS posterior: IC$_{{50}}$={fit.ic50_median:.1f} "
                 rf"[{fit.ic50_ci90[0]:.1f},{fit.ic50_ci90[1]:.1f}] $\mu$M", fontsize=8.5)
    ax.legend(loc="lower left")
    fig.savefig(FIG / "fig_bayes.pdf")
    NUMBERS["bayes"] = {"ic50_median": round(fit.ic50_median, 2), "ci90": [round(fit.ic50_ci90[0], 2), round(fit.ic50_ci90[1], 2)],
                        "rhat": round(fit.r_hat_potency, 3), "shrinkage": round(ident["shrinkage"], 3),
                        "recovered_potency": round(float(np.median(fit.potency_samples)), 3), "true_potency": 0.7}


def fig_assimilation():
    times = np.linspace(2, 24, 9); truth = 0.7
    obs = synth_observations(truth, times, obs_indices=[0, 1], obs_noise=0.05, seed=3)
    res = particle_filter(times, obs, obs_indices=[0, 1], obs_noise=0.05, n_particles=2500, seed=1)
    fig, ax = plt.subplots(figsize=(3.3, 3.0))
    ax.axhline(truth, ls="--", color=CRIT, lw=1, label="true severity")
    ax.fill_between(times, res.theta_ci90[:, 0], res.theta_ci90[:, 1], color=AC, alpha=0.18, label="90% credible band")
    ax.plot(times, res.theta_mean, color=AC, lw=1.8, marker="o", ms=3, label="posterior mean")
    ax.set_xlabel("time (h) -- evidence accumulates"); ax.set_ylabel("inferred ETC inhibition")
    ax.set_ylim(0, 1); ax.set_title("Online data assimilation (particle filter)", fontsize=8.5)
    ax.legend(loc="lower right")
    fig.savefig(FIG / "fig_assimilation.pdf")
    w0 = res.theta_ci90[0, 1] - res.theta_ci90[0, 0]; w1 = res.theta_ci90[-1, 1] - res.theta_ci90[-1, 0]
    NUMBERS["assim"] = {"truth": truth, "recovered": round(float(res.theta_mean[-1]), 3),
                        "ci_w0": round(float(w0), 3), "ci_w1": round(float(w1), 3)}


def fig_selectivity():
    toxins = ["rotenone", "doxorubicin", "cisplatin"]
    cells = ["neuron", "cardiomyocyte", "hepatocyte", "proximal_tubule", "cancer_cell"]
    labels = {"neuron": "neuron", "cardiomyocyte": "cardiomyocyte", "hepatocyte": "hepatocyte",
              "proximal_tubule": "prox. tubule", "cancer_cell": "tumor"}
    data = {t: {c: dose_response(tox[t], load_cell(c), tox).ic50 for c in cells} for t in toxins}
    fig, ax = plt.subplots(figsize=(3.4, 3.0))
    cols = {"rotenone": AC, "doxorubicin": CRIT, "cisplatin": "#4a3aa7"}
    for t in toxins:
        ys = [data[t][c] for c in cells]
        ax.plot(ys, range(len(cells)), "o-", color=cols[t], lw=1.4, ms=5, label=t)
    ax.set_yticks(range(len(cells))); ax.set_yticklabels([labels[c] for c in cells])
    ax.set_xscale("log"); ax.set_xlabel(r"cytotoxic IC$_{50}$ ($\mu$M, lower = more sensitive)")
    ax.set_title("Tissue selectivity across cell types", fontsize=8.5)
    ax.legend(loc="lower right", fontsize=7.5)
    fig.savefig(FIG / "fig_selectivity.pdf")
    NUMBERS["selectivity"] = {t: {c: round(data[t][c], 3) for c in cells} for t in toxins}


def fig_twin():
    # Digital twin: propagate posterior potency uncertainty through the ODE.
    ic = dose_response(tox["rotenone"], cell, tox).ic50
    doses, obs = synth_dose_response(tox["rotenone"], cell, center_ic50=ic, true_potency=1.0, seed=2)
    fit = fit_toxin(tox["rotenone"], cell, doses, obs, base_model_ic50=ic, num_warmup=300, num_samples=500, seed=0)
    p = default_params(); specs = target_specs(tox["rotenone"], cell)
    dose = ic * 1.5
    pot = fit.potency_samples[:: max(1, len(fit.potency_samples)//120)]
    trajs = []
    for s in pot:
        mods = build_modifiers(specs, float(s), float(dose), cell.cyp_activity, tox["rotenone"].requires_bioactivation)
        ts, ys = integrate_traj(p, mods, 24.0)
        trajs.append(np.asarray(ys))
    trajs = np.stack(trajs); ts = np.asarray(ts)
    names = [("ATP", 0, "#2a78d6"), ("ROS", 1, CRIT), ("GSH", 2, GOOD), ("caspase", 3, "#4a3aa7"), ("membrane", 4, "#d9591f")]
    fig, ax = plt.subplots(figsize=(3.4, 3.0))
    for nm, idx, col in names:
        med = np.median(trajs[:, :, idx], 0); lo = np.percentile(trajs[:, :, idx], 5, 0); hi = np.percentile(trajs[:, :, idx], 95, 0)
        ax.fill_between(ts, lo, hi, color=col, alpha=0.15)
        ax.plot(ts, med, color=col, lw=1.5, label=nm)
    ax.set_xlabel("time (h)"); ax.set_ylabel("state (normalized)")
    ax.set_title(rf"Digital twin at {dose:.0f} $\mu$M rotenone (posterior band)", fontsize=8.5)
    ax.legend(loc="center right", fontsize=7)
    fig.savefig(FIG / "fig_twin.pdf")


def surrogate_numbers():
    _, m = train_surrogate(n_samples=3000, seed=0)
    NUMBERS["surrogate"] = {"r2_overall": round(m["r2_overall"], 3),
                            "per": {k: round(v["r2"], 3) for k, v in m["per_readout"].items()}}


if __name__ == "__main__":
    print("Generating figures from the celltwin engine...")
    fig_calibration(); print(" - calibration")
    fig_population(); print(" - population")
    fig_bayes(); print(" - bayes")
    fig_assimilation(); print(" - assimilation")
    fig_selectivity(); print(" - selectivity")
    fig_twin(); print(" - digital twin")
    surrogate_numbers(); print(" - surrogate metrics")
    def _coerce(o):
        if isinstance(o, np.integer): return int(o)
        if isinstance(o, np.floating): return float(o)
        return str(o)
    (Path(__file__).resolve().parent / "numbers.json").write_text(json.dumps(NUMBERS, indent=2, default=_coerce))
    print("\nNumbers cited in the paper:")
    print(json.dumps(NUMBERS, indent=2))
