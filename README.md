# Cell Digital Twin — Toxicology Screening

A computational **digital twin of a cell** for predicting how **toxins** perturb
cellular biology, propagate through the cell's molecular **relations**, and drive
cytotoxic outcomes.

Introduce a compound (defined by its mechanism of action and potency), run the
simulation forward, and read out **viability**, a **dose-response curve / IC50**,
the **mechanism of death**, and **combination synergy** between toxins.

> Full architecture and roadmap: [`docs/PLAN.md`](docs/PLAN.md).
> Biology & validation: [`docs/biology.md`](docs/biology.md).

## How it works (hybrid engine)

```
toxin + dose ──▶ relation graph ──▶ mechanistic ODE core ──▶ readouts
              (what is perturbed)   (by how much, over time)   viability, IC50,
                                                               mechanism, synergy
```

- **Relations layer** — the cell is a typed, signed graph of genes, proteins,
  metabolites, organelles and phenotypes (`data/cells/hepatocyte.yaml`). It maps
  each toxin's targets onto the processes they engage.
- **Mechanistic core** — five coupled ODEs (ATP, ROS, GSH, caspase, membrane)
  integrate the perturbation over the exposure window and yield a viability call.
- **Toxins are data** — adding a compound is editing a YAML file in `data/toxins/`.

## Quick start

```bash
pip install -e ".[dev]"        # install (Python ≥ 3.10)
pytest -q                      # run the test suite

celltwin list                              # available cells & toxins
celltwin simulate rotenone --dose 0.5      # single exposure + mechanism
celltwin dose-response menadione           # dose-response curve + IC50
celltwin combine bso:60 hydrogen_peroxide:8   # synergy test
```

Example — a mitochondrial toxin's dose-response:

```
$ celltwin dose-response rotenone
Dose-response: rotenone on hepatocyte (24.0 h)
  IC50: 0.033 uM   Hill: 1.37
  ...
```

## REST API

```bash
uvicorn celltwin.api.app:app --reload --app-dir backend
```

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET  | `/cells`, `/toxins` | catalog |
| GET  | `/cells/{id}/graph` | relation graph (for visualization) |
| POST | `/simulate` | run one exposure scenario |
| GET  | `/dose-response/{toxin_id}` | curve + IC50 |
| POST | `/combine` | combination synergy score |

## Reference library (18 toxins × 5 cell types)

**Toxins** — Rotenone, Cyanide, Antimycin A, Oligomycin, FCCP (mitochondrial) ·
H₂O₂, menadione, paraquat, tBHP, arsenite (oxidative) · BSO (GSH depletion) ·
Triton X-100 (membrane) · staurosporine (apoptosis) · etoposide, cisplatin
(genotoxic) · doxorubicin, arsenite (multi-mechanism) · acetaminophen, CCl₄
(CYP-bioactivated).

**Cell types** — hepatocyte, cardiomyocyte, neuron, proximal tubule (kidney),
cancer cell — differing in energy dependence, antioxidant reserve, repair,
apoptotic propensity, and CYP metabolism, so the same toxin can be selectively
toxic to some tissues and not others.

## Repository layout

```
data/                biology as YAML (cells, toxins)
backend/celltwin/    engine (ODE + coupling), model, experiments, api, cli
backend/tests/       unit + behavioral validation
docs/                PLAN.md, biology.md
frontend/            React visualization (Phase 3 — planned)
```

## Status

Phases 0–2 implemented (engine, screening, API, CLI, tests). Phase 3 (web
frontend) and Phase 4 (quantitative calibration + more cell types) are next —
see [`docs/PLAN.md`](docs/PLAN.md).

*Research/screening tool — not a substitute for experimental toxicology.*
