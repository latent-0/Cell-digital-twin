# Validation & Calibration Report

This document records how the digital twin is validated against experimental
data and the outcome of calibration. It is generated from
`data/reference/cytotoxicity.yaml` and reproducible with:

```bash
celltwin validate-tox     # score model IC50s vs literature
celltwin calibrate --apply  # re-derive the potency overlay
```

## Method

1. **Reference set** — representative *cellular* cytotoxic IC50 values from the
   literature for each toxin, each tagged with a confidence level and source
   (`data/reference/cytotoxicity.yaml`). These are order-of-magnitude anchors:
   published IC50s are highly assay-, cell-line-, timepoint- and readout-
   dependent and routinely vary 1–2 logs across studies.

2. **Calibration** — a toxin's *effective potency* is distinct from its
   biochemical binding constant (e.g. rotenone binds Complex I at nM but kills
   glycolytic cells only at µM). Because the emergent cytotoxic IC50 scales
   linearly with a toxin's potency constant, calibration is a one-shot
   multiplicative solve per toxin, written to `data/reference/calibration.yaml`
   as an overlay that leaves the authored potencies untouched.

3. **Scoring** — per toxin: fold-error and |log₁₀| error of model vs reference;
   across toxins: the Spearman rank-order correlation of log-IC50 (the honest
   primary acceptance criterion for v1 — getting the *ordering* right).

## Result (calibrated model, 24 h, hepatocyte context)

| Metric | Value |
|--------|-------|
| Toxins within 1 log of literature | **17 / 17** |
| Median fold-error | **1.00×** |
| Rank-order correlation (Spearman ρ) | **0.996** |

Post-calibration the absolute IC50s match by construction (the calibration
target); the meaningful result is that a **single scalar per toxin** suffices —
the *shape* of every dose-response and the *cross-toxin ordering* are emergent
model properties, not fitted. Notably, **before** calibration the rank-order
correlation was already ρ ≈ 0.88, i.e. the mechanistic model orders toxin
potencies well on its own.

## What calibration does and does not establish

**Does:** put every toxin on a realistic cellular potency scale; confirm the
mechanistic engine reproduces relative potencies; give the forthcoming Bayesian
layer concrete anchors to place priors around.

**Does not:** validate absolute predictions on *held-out* compounds (the anchors
are training targets, not a test set); capture assay/cell-line variance; replace
experimental toxicology.

## Roadmap to stronger validation

- **Held-out test set** — calibrate on a subset, predict the rest, report blind
  fold-error. This is the real predictive-accuracy measure.
- **Time-course validation** — compare simulated ATP/ROS/GSH trajectories, not
  just endpoint IC50, against kinetic assay data.
- **Bayesian calibration (next)** — replace the point-estimate potency overlay
  with posterior distributions (NumPyro/HMC), yielding IC50 predictions with
  credible intervals and enabling data assimilation. Prior-predictive checks,
  prior-sensitivity analysis, and parameter-identifiability reporting will be
  built in (see the discussion in the project notes).

## Other validated behaviors (see `backend/tests/`)

- Homeostatic steady state; monotonic dose-response.
- Mechanism attribution (energy failure / oxidative / necrosis / apoptosis).
- CYP-gating of APAP and CCl₄ (toxic only with metabolic bioactivation).
- Tissue selectivity (doxorubicin→cardiomyocyte, rotenone→neuron,
  cisplatin→proximal tubule, apoptosis-resistance→cancer cell).
- BSO × H₂O₂ synergy (GSH-depletion sensitizes to oxidants).
