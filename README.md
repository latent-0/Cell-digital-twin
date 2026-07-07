# Cell Digital Twin — Toxicology Screening

A computational **digital twin of a cell** for predicting how **toxins** perturb
cellular biology, propagate through the cell's molecular **relations**, and drive
cytotoxic outcomes.

Introduce a compound (defined by its mechanism of action and potency), run the
simulation forward, and read out **viability**, a **dose-response curve / IC50**,
the **mechanism of death**, and **combination synergy** between toxins.

> Full architecture and roadmap: [`docs/PLAN.md`](docs/PLAN.md).
> Biology & assumptions: [`docs/biology.md`](docs/biology.md).
> Validation & calibration: [`docs/validation.md`](docs/validation.md) —
> model IC50s land **17/17 within 1 log** of literature (Spearman ρ = 0.996).
> Bayesian inference & data assimilation: [`docs/inference.md`](docs/inference.md) —
> NUTS-calibrated **IC50s with credible intervals** + a self-updating particle filter.

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
celltwin simulate rotenone --dose 50       # single exposure + mechanism
celltwin dose-response menadione           # dose-response curve + IC50
celltwin combine bso:150 hydrogen_peroxide:280   # synergy test
celltwin validate-tox                      # model IC50s vs literature
celltwin calibrate --apply                 # re-derive potency calibration
celltwin fit-bayes rotenone                # Bayesian IC50 with credible interval
celltwin assimilate                        # particle-filter data assimilation
```

Example — a mitochondrial toxin's dose-response:

```
$ celltwin dose-response rotenone
Dose-response: rotenone on hepatocyte (24.0 h)
  IC50: 0.033 uM   Hill: 1.37
  ...
```

## Frontends

Two are included:

**1. Live React app (`webapp/`)** — talks to the FastAPI backend; every panel is
computed on demand (dose-response, simulation, tissue selectivity, an interactive
combination/synergy explorer, and on-demand NUTS calibration + particle-filter
assimilation).

```bash
# terminal 1 — backend
uvicorn celltwin.api.app:app --app-dir backend --port 8000
# terminal 2 — frontend (proxies /api -> :8000)
cd webapp && npm install && npm run dev      # open http://localhost:5173
```

**2. Static dashboard (`frontend/index.html`)** — a self-contained snapshot (no
build, no server) with the same panels baked from precomputed real outputs; open
the file directly, works offline.

```bash
python scripts/build_data.py       # recompute frontend/twindata.json from the engine
python scripts/build_frontend.py   # assemble the standalone frontend/index.html
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
data/                biology as YAML (cells, toxins, reference IC50s + calibration)
backend/celltwin/    engine (ODE + coupling), model, experiments, validation,
                     inference (JAX ODE, NUTS calibration, particle filter), api, cli
backend/tests/       unit + behavioral + validation + Bayesian-recovery tests
docs/                PLAN.md, biology.md, validation.md, inference.md
frontend/            React visualization (planned)
```

## Status

Implemented: mechanistic + network engine, 18 toxins × 5 cell types, screening
(dose-response/IC50, mechanism attribution, synergy), literature calibration
(17/17 within 1 log), a **Bayesian layer** (NUTS IC50 credible intervals +
particle-filter data assimilation), a **cell-population layer** (heterogeneity
smooths dose-response into realistic sigmoids), an **ML surrogate** (fast learned
emulator of the ODE endpoints), and **static + live React frontends**. 87 tests.

```bash
celltwin population rotenone      # population (heterogeneity) dose-response
celltwin train-surrogate          # train + score the ML emulator
```

Next: joint posteriors over mechanism parameters, held-out predictive test set —
see [`docs/PLAN.md`](docs/PLAN.md).

*Research/screening tool — not a substitute for experimental toxicology.*
