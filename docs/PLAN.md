# Cell Digital Twin — Toxicology Screening Platform

**A computational digital twin of a living cell for predicting how toxins
perturb cellular biology, propagate through molecular relationships, and drive
cytotoxic outcomes.**

---

## 1. Vision & Scope

We are building a *digital twin of a cell*: an in-silico model that mirrors the
key biology of a real cell closely enough that we can introduce a **toxin**,
run the simulation forward in time, and read out **what happens to the cell**
(does it survive, how badly is it damaged, and *why*).

The twin is organized around two ideas the user named explicitly:

- **Toxins** — chemical/biological agents with defined molecular targets and
  potencies. We perturb the model with them and observe dose- and time-dependent
  effects.
- **Relations** — the wiring of the cell: which genes regulate which proteins,
  which enzymes catalyze which reactions, which pathways feed which readouts.
  Toxicity is *emergent* from how a perturbation ripples through these relations.

### Primary use case: **Toxicology screening**
Given a compound (defined by its mechanism of action + potency) and a dose,
predict:
- Cell **viability** and dose-response curve (IC50/EC50).
- **Time course** of key damage markers (ATP depletion, ROS accumulation,
  glutathione loss, membrane integrity, apoptosis fraction).
- **Mechanism attribution** — *which pathway(s)* drove the outcome.
- **Combination effects** — synergy/antagonism between two toxins (the
  "relations" between toxins themselves).

### Non-goals (v1)
- Whole-organism / multi-organ PK-PD (single cell only).
- Molecular-dynamics / atomistic simulation.
- Spatial reaction-diffusion within the cell (well-mixed compartments only).
- Perfect quantitative prediction — v1 targets *directionally correct,
  mechanism-aware, literature-anchored* predictions.

---

## 2. Biological Design

### 2.1 Reference cell: human hepatocyte (liver cell)
The liver is the primary site of xenobiotic metabolism and drug-induced
toxicity (DILI), which makes the hepatocyte the standard reference cell for
tox screening. The architecture is **cell-type agnostic** — the hepatocyte is
just the first model we load; new cell types are added as data, not code.

### 2.2 The cell as a graph of relations (the "relations" layer)
We represent the cell as a **typed, signed, directed knowledge graph**.

**Node types (entities):**
| Type | Examples |
|------|----------|
| Gene | *TP53*, *BAX*, *GCLC* |
| mRNA / transcript | transcript of each gene |
| Protein / enzyme | Complex I, GSH synthetase, Caspase-3 |
| Metabolite / species | ATP, ROS, GSH, NADH, Ca²⁺, Cytochrome-c |
| Organelle / compartment | mitochondrion, ER, nucleus, cytosol, membrane |
| Phenotype readout | viability, ATP level, apoptosis fraction, membrane integrity |

**Edge types (relations):** `activates`, `inhibits`, `catalyzes`,
`transcribes`, `translates`, `transports`, `binds`, `forms_complex`,
`produces`, `consumes`, `damages`. Each edge carries a **sign** (+/−) and a
**weight/strength**.

This graph is the substrate for both the fast propagation layer and the
scaffold onto which mechanistic ODE modules attach.

### 2.3 Core pathways modeled in v1
Chosen because they cover the dominant mechanisms of cytotoxicity:

1. **Mitochondrial bioenergetics** — electron transport chain (Complexes I–IV),
   ATP synthesis, membrane potential. *Target of many toxins (rotenone, cyanide,
   oligomycin).*
2. **Oxidative stress axis** — ROS production, glutathione (GSH) buffering,
   NADPH regeneration, lipid peroxidation. *Target of H₂O₂, menadione, paraquat.*
3. **Apoptosis / cell-death decision** — mitochondrial outer membrane
   permeabilization (MOMP), cytochrome-c release, caspase cascade, BAX/BCL-2
   balance. *The integrator that converts damage into a viability outcome.*
4. **Xenobiotic metabolism** — CYP450 bioactivation (turns some pro-toxins into
   reactive metabolites, e.g. APAP → NAPQI) and Phase II conjugation.
5. **Membrane integrity** — plasma-membrane damage → necrotic readout.

### 2.4 Toxin model
A toxin is data, not code:
```yaml
toxin: rotenone
class: mitochondrial_inhibitor
targets:
  - node: complex_I           # which relation/entity it hits
    effect: inhibit
    ic50_uM: 0.005            # potency
    hill: 1.2                 # dose-response steepness
requires_bioactivation: false  # true for e.g. APAP → NAPQI via CYP
```
Supported mechanisms of action (MoA) in v1: mitochondrial ETC inhibition,
oxidative stressor, GSH depleter, membrane disruptor, DNA/genotoxic,
ER-stress inducer, and metabolism-dependent (bioactivated) toxins.

---

## 3. The Hybrid Simulation Engine

The "hybrid" approach = a **fast graph-propagation layer** for breadth +
**mechanistic ODE modules** for quantitative dynamics on the pathways that
matter most. They are coupled.

```
┌─────────────────────────────────────────────────────────────┐
│  TOXIN(S) + DOSE + EXPOSURE TIME                             │
└───────────────┬─────────────────────────────────────────────┘
                │ 1. map toxin targets onto graph nodes
                ▼
┌─────────────────────────────────────────────────────────────┐
│  LAYER A — Relation graph (NetworkX)                         │
│  • signed perturbation propagation across relations          │
│  • identifies which pathways/modules are hit + initial       │
│    perturbation magnitude per node                           │
└───────────────┬─────────────────────────────────────────────┘
                │ 2. set rate-constant modifiers on affected reactions
                ▼
┌─────────────────────────────────────────────────────────────┐
│  LAYER B — Mechanistic ODE modules (SciPy solve_ivp)        │
│  • mitochondria, ROS/GSH, apoptosis, metabolism             │
│  • integrate species concentrations over exposure time       │
└───────────────┬─────────────────────────────────────────────┘
                │ 3. aggregate species + apoptosis state
                ▼
┌─────────────────────────────────────────────────────────────┐
│  READOUTS — viability, ATP, ROS, GSH, apoptosis %,          │
│  IC50, mechanism attribution                                 │
└─────────────────────────────────────────────────────────────┘
```

**Coupling contract:** a toxin's dose → (via Hill equation) a fractional
inhibition/activation of specific reactions → modifies the rate constants of
the ODE system → the ODEs produce time-resolved species trajectories → an
integrator function maps end-state species to a viability score. The graph
layer decides *what to modify*; the ODE layer decides *by how much, over time*.

**Dose-response** is produced by sweeping dose across a log range and
re-simulating; **combination toxins** by applying multiple target modifiers
simultaneously and comparing to a Bliss/Loewe independence baseline to score
synergy vs antagonism.

---

## 4. Technology Stack

**Backend (Python)**
- `FastAPI` + `uvicorn` — REST API.
- `pydantic` — typed schemas for toxins, models, simulation requests.
- `numpy`, `scipy` (`solve_ivp`) — ODE integration.
- `networkx` — the relation graph, propagation, path/mechanism analysis.
- `pyyaml` — human-editable model & toxin definitions.
- `pytest` — tests. (Optional later: `tellurium`/`libRoadRunner` + SBML import,
  `COBRApy` for metabolic flux.)

**Frontend (Web)**
- `React` + `Vite` + `TypeScript`.
- `Cytoscape.js` (or `react-force-graph`) — interactive cell/relation graph;
  nodes light up as a toxin propagates.
- `Recharts` (or Plotly) — dose-response curves and time-course plots.
- Simple state via React Query against the FastAPI backend.

**Model data**: version-controlled YAML/JSON under `data/` so biology can be
edited and reviewed without touching engine code.

---

## 5. Repository Structure

```
Cell-digital-twin/
├── docs/
│   ├── PLAN.md                 # this document
│   ├── biology.md              # pathway & assumption reference + citations
│   └── api.md                  # REST API reference
├── data/
│   ├── cells/hepatocyte.yaml   # graph: nodes, relations, ODE params
│   └── toxins/                 # rotenone.yaml, apap.yaml, h2o2.yaml, ...
├── backend/
│   ├── celltwin/
│   │   ├── model/              # graph loading, entities, relations
│   │   ├── engine/             # graph propagation + ODE modules + coupling
│   │   ├── toxins/             # toxin schema, MoA application
│   │   ├── readouts/           # viability, IC50, mechanism attribution
│   │   ├── experiments/        # dose-response, time-course, combinations
│   │   └── api/                # FastAPI routes
│   └── tests/                  # unit + validation (reference toxins)
├── frontend/
│   └── src/                    # React app: graph view, controls, charts
├── requirements.txt / pyproject.toml
├── .github/workflows/ci.yml
└── README.md
```

---

## 6. Phased Roadmap

### Phase 0 — Scaffolding (foundation)
- Repo structure, `pyproject`/`requirements`, linting, `pytest`, CI workflow.
- Pydantic schemas for cell model, relations, toxins, simulation request/result.
- Load `hepatocyte.yaml` into a NetworkX graph; validate integrity.
- **Deliverable:** `celltwin` package imports, loads a graph, tests pass in CI.

### Phase 1 — Core engine (MVP simulation)
- Mitochondrial + ROS/GSH + apoptosis ODE modules (minimal but coupled).
- Toxin → target-modifier → rate-constant coupling.
- Single-toxin, single-dose, time-course simulation → viability + markers.
- Define 3 reference toxins (rotenone, H₂O₂, an uncoupler) as YAML.
- **Deliverable:** `simulate(toxin, dose, time)` returns trajectories + viability.

### Phase 2 — Screening features
- Dose-response sweep → IC50/EC50 with Hill fit.
- Graph propagation layer + **mechanism attribution** ("mitochondrial failure
  drove death").
- Combination toxins → synergy/antagonism score (Bliss/Loewe).
- **Deliverable:** full screening report for a compound.

### Phase 3 — API + Web frontend
- FastAPI endpoints: list toxins/cells, run simulation, dose-response,
  combination, graph export.
- React UI: pick toxin + dose, animated relation graph, live dose-response and
  time-course charts, mechanism panel.
- **Deliverable:** interactive twin usable in the browser.

### Phase 4 — Validation & extension
- Validate reference toxins against literature IC50s / known mechanisms
  (documented in `docs/biology.md`).
- Add xenobiotic metabolism (bioactivation, e.g. APAP → NAPQI).
- Expand toxin library; add a second cell type to prove extensibility.
- **Deliverable:** validation report + broader toxin/cell coverage.

---

## 7. Validation Strategy

The twin is credible only if it reproduces *known* biology. We validate against
well-characterized reference toxins with published mechanisms and potencies:

| Toxin | Expected mechanism the twin must reproduce |
|-------|--------------------------------------------|
| Rotenone | Complex I inhibition → ATP collapse → death |
| Cyanide | Complex IV inhibition → ATP collapse |
| Oligomycin / FCCP | ATP synthase inhibition / uncoupling |
| H₂O₂, Menadione | ROS surge → GSH depletion → oxidative death |
| Acetaminophen (APAP) | CYP bioactivation → NAPQI → GSH depletion (dose-dependent, metabolism-gated) |

Acceptance for v1: correct **rank-ordering** of potency, correct **mechanism
attribution**, and IC50s within ~1 log of literature values. Each claim in
`docs/biology.md` carries a citation.

---

## 8. Key Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| Biological over-scoping | Fix v1 to 5 pathways + hepatocyte; everything else is data-driven extension. |
| ODE stiffness / instability | Use `solve_ivp` with a stiff solver (BDF/Radau); non-dimensionalize; unit-test steady states. |
| "Made-up" parameters lack credibility | Anchor every parameter to literature; keep them in reviewable YAML with citations. |
| Graph↔ODE coupling complexity | Define one explicit coupling contract (§3); test each layer in isolation first. |
| Frontend scope creep | Backend is fully usable via API/CLI before any UI; UI is a thin visual client. |

---

## 9. Immediate Next Steps (on approval)

1. Scaffold repo (Phase 0): package layout, deps, schemas, CI.
2. Author `hepatocyte.yaml` (nodes, relations, initial ODE params) +
   `rotenone.yaml`.
3. Implement the mitochondrial + apoptosis ODE core and the toxin coupling.
4. Get `simulate(rotenone, dose, time)` producing a viability curve, under test.

Then iterate through Phases 2–4.

---

*This plan is the founding document for the project. It is intentionally
data-driven (biology in YAML, engine in Python) so the model can grow without
rewrites, and validation-first so predictions stay credible.*
