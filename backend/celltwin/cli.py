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

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
