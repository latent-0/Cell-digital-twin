"""Command-line interface for the cell digital twin.

Examples:
    celltwin list
    celltwin simulate rotenone --dose 1 --hours 24
    celltwin dose-response rotenone
    celltwin combine rotenone:0.05 hydrogen_peroxide:50
"""

from __future__ import annotations

import argparse
import sys

from .experiments.screen import combination, dose_response
from .engine.simulate import simulate
from .model.registry import (
    list_cells,
    list_toxins,
    load_all_toxins,
    load_cell,
    validate_cell,
)
from .schemas import Exposure, SimulationRequest


def _cmd_list(args) -> int:
    print("Cells: ", ", ".join(list_cells()))
    print("Toxins:", ", ".join(list_toxins()))
    return 0


def _cmd_validate(args) -> int:
    cell_ids = list_cells()
    rc = 0
    for cid in cell_ids:
        cell = load_cell(cid)
        problems = validate_cell(cell)
        if problems:
            rc = 1
            print(f"{cell.id}: {len(problems)} problem(s):")
            for p in problems:
                print("  -", p)
        else:
            print(f"{cell.id}: OK ({len(cell.nodes)} nodes, {len(cell.relations)} relations)")
    return rc


def _cmd_simulate(args) -> int:
    cell = load_cell(args.cell)
    toxins = load_all_toxins()
    req = SimulationRequest(
        cell_id=cell.id,
        exposures=[Exposure(toxin_id=args.toxin, dose=args.dose)],
        duration_h=args.hours,
        cyp_activity=args.cyp,
    )
    res = simulate(req, cell, toxins)
    print(f"{args.toxin} @ {args.dose} uM for {args.hours} h on {cell.id}")
    print(f"  final viability: {res.final_viability:.1%}")
    print(f"  {res.mechanism.narrative}")
    return 0


def _cmd_dose_response(args) -> int:
    cell = load_cell(args.cell)
    toxins = load_all_toxins()
    res = dose_response(toxins[args.toxin], cell, toxins, duration_h=args.hours, cyp_activity=args.cyp)
    ic50 = f"{res.ic50:.4g} uM" if res.ic50 is not None else "not reached"
    hill = f"{res.hill:.2f}" if res.hill is not None else "n/a"
    print(f"Dose-response: {args.toxin} on {cell.id} ({args.hours} h)")
    print(f"  IC50: {ic50}   Hill: {hill}")
    for pt in res.curve:
        bar = "#" * int(round(pt.viability * 30))
        print(f"  {pt.dose:>12.4g} uM | {bar:<30} {pt.viability:5.1%}")
    return 0


def _cmd_validate_tox(args) -> int:
    from .validation.validate import format_report, validate_model

    report = validate_model(duration_h=args.hours)
    print(format_report(report))
    return 0


def _cmd_calibrate(args) -> int:
    from .validation.calibrate import apply_calibration, compute_calibration

    results = compute_calibration(duration_h=args.hours)
    print(f"{'toxin':22s} {'model IC50':>12s} {'reference':>10s} {'new scale':>12s}")
    print("-" * 60)
    for r in results:
        print(f"{r.toxin:22s} {r.model_ic50_before:>12.3g} {r.reference_ic50:>10.3g} {r.new_scale:>12.4g}")
    if args.apply:
        apply_calibration(results)
        print(f"\nWrote calibration overlay ({len(results)} toxins).")
    else:
        print("\n(dry run; pass --apply to write the calibration overlay)")
    return 0


def _cmd_fit_bayes(args) -> int:
    from .experiments.screen import dose_response
    from .inference.calibrate_bayes import fit_toxin, synth_dose_response
    from .inference.diagnostics import identifiability

    cell = load_cell(args.cell)
    toxins = load_all_toxins()
    toxin = toxins[args.toxin]
    m0 = dose_response(toxin, cell, toxins).ic50
    if m0 is None:
        print(f"{args.toxin} has no cytotoxic IC50 to calibrate.")
        return 1
    doses, obs = synth_dose_response(toxin, cell, center_ic50=m0, true_potency=args.true_potency, seed=1)
    print(f"Bayesian calibration of {args.toxin} on {cell.id} (NUTS)...")
    fit = fit_toxin(toxin, cell, doses, obs, base_model_ic50=m0,
                    num_warmup=args.warmup, num_samples=args.samples)
    print("  " + fit.summary())
    ident = identifiability(fit)
    print(f"  identifiability: shrinkage={ident['shrinkage']:.2f} -> {ident['verdict']}")
    if args.true_potency != 1.0:
        print(f"  (recovery check: true potency {args.true_potency}, "
              f"recovered {float(__import__('numpy').median(fit.potency_samples)):.3f})")
    return 0


def _cmd_assimilate(args) -> int:
    import numpy as np
    from .inference.assimilate import particle_filter, synth_observations

    obs_times = np.linspace(2.0, args.hours, args.n_obs)
    obs = synth_observations(args.true_severity, obs_times, obs_indices=[0, 1],
                             obs_noise=args.noise, seed=3)
    res = particle_filter(obs_times, obs, obs_indices=[0, 1], obs_noise=args.noise,
                          n_particles=args.particles, seed=1)
    print(f"Data assimilation (particle filter): recovering ETC-inhibition severity")
    print(f"  true severity = {args.true_severity:.2f}")
    print(f"  {'time(h)':>8s} {'post.mean':>10s} {'90% CI width':>14s}")
    for i, t in enumerate(obs_times):
        w = res.theta_ci90[i, 1] - res.theta_ci90[i, 0]
        print(f"  {t:>8.1f} {res.theta_mean[i]:>10.3f} {w:>14.3f}")
    print(f"  final posterior median = {res.final_theta_median:.3f} "
          f"(CI tightens as evidence accumulates)")
    return 0


def _parse_exposure(spec: str) -> Exposure:
    tid, _, dose = spec.partition(":")
    return Exposure(toxin_id=tid, dose=float(dose))


def _cmd_combine(args) -> int:
    cell = load_cell(args.cell)
    toxins = load_all_toxins()
    exposures = [_parse_exposure(s) for s in args.exposures]
    res = combination(exposures, cell, toxins, duration_h=args.hours, cyp_activity=args.cyp)
    combo = ", ".join(f"{e.toxin_id}@{e.dose}" for e in exposures)
    print(f"Combination on {cell.id}: {combo}")
    print(f"  observed viability : {res.observed_viability:.1%}")
    print(f"  expected (Bliss)   : {res.expected_bliss:.1%}")
    print(f"  synergy score      : {res.synergy:+.3f}  -> {res.interpretation}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="celltwin", description=__doc__)
    parser.add_argument("--cell", default="hepatocyte", help="cell model id")
    parser.add_argument("--hours", type=float, default=24.0, help="exposure duration")
    parser.add_argument("--cyp", type=float, default=None, help="relative CYP450 activity (default: cell's own)")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="list available cells and toxins").set_defaults(func=_cmd_list)

    p_val = sub.add_parser("validate", help="validate a cell model")
    p_val.set_defaults(func=_cmd_validate)

    p_sim = sub.add_parser("simulate", help="simulate one toxin at one dose")
    p_sim.add_argument("toxin")
    p_sim.add_argument("--dose", type=float, required=True)
    p_sim.set_defaults(func=_cmd_simulate)

    p_dr = sub.add_parser("dose-response", help="dose-response curve + IC50")
    p_dr.add_argument("toxin")
    p_dr.set_defaults(func=_cmd_dose_response)

    p_cmb = sub.add_parser("combine", help="combination synergy test (toxin:dose ...)")
    p_cmb.add_argument("exposures", nargs="+")
    p_cmb.set_defaults(func=_cmd_combine)

    sub.add_parser("validate-tox", help="validate model IC50s vs literature").set_defaults(func=_cmd_validate_tox)

    p_cal = sub.add_parser("calibrate", help="calibrate potencies to literature IC50s")
    p_cal.add_argument("--apply", action="store_true", help="write the calibration overlay")
    p_cal.set_defaults(func=_cmd_calibrate)

    p_fb = sub.add_parser("fit-bayes", help="Bayesian (NUTS) IC50 with credible intervals")
    p_fb.add_argument("toxin")
    p_fb.add_argument("--true-potency", type=float, default=1.0, help="ground truth for recovery check")
    p_fb.add_argument("--warmup", type=int, default=400)
    p_fb.add_argument("--samples", type=int, default=800)
    p_fb.set_defaults(func=_cmd_fit_bayes)

    p_as = sub.add_parser("assimilate", help="particle-filter data assimilation demo")
    p_as.add_argument("--true-severity", type=float, default=0.7)
    p_as.add_argument("--n-obs", type=int, default=8)
    p_as.add_argument("--particles", type=int, default=1500)
    p_as.add_argument("--noise", type=float, default=0.05)
    p_as.set_defaults(func=_cmd_assimilate)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
