# Bayesian Inference Layer

This layer turns the mechanistic model into an **uncertainty-quantified, self-
updating digital twin**. It has two capabilities:

1. **Bayesian calibration (NumPyro / HMC)** — infer toxin potencies with full
   posteriors, yielding **IC50 predictions with credible intervals**.
2. **Data assimilation (particle filter)** — update the twin online from a stream
   of noisy measurements, jointly inferring latent cell state and the unknown
   exposure, with the posterior tightening as evidence accumulates.

## Why this is the meaningful step

The point-calibration layer (`docs/validation.md`) gives single-number IC50s.
Real decisions need *uncertainty*, and a real "twin" must *track its physical
counterpart*. This layer provides both, and it does so over the **actual
mechanistic model**, not a surrogate.

## Differentiable forward model

`celltwin/inference/jax_ode.py` reimplements the five-state ODE core in JAX using
a fixed-step RK4 integrator (`lax.scan`). Two reasons:

- **Gradients for HMC** — NUTS needs derivatives through the ODE. A fixed-step
  scan gives stable reverse-mode gradients (an adaptive solver's adjoint is
  fragile here).
- **Fidelity** — it matches the SciPy (LSODA) engine to <0.02 in viability across
  all toxins (asserted in `backend/tests/test_jax_ode.py`), so HMC calibrates the
  real model.

## Bayesian calibration

```bash
celltwin fit-bayes rotenone                     # IC50 + 90% credible interval
celltwin fit-bayes rotenone --true-potency 0.7  # parameter-recovery check
```

We infer a per-toxin **potency multiplier** (log-normal prior centered on the
point-calibrated value) and the assay noise. Output includes the IC50 posterior
median + 90% CI, `R-hat`, and an **identifiability** verdict.

A **hierarchical** (partial-pooling) variant, `fit_toxins_hierarchical`, draws
each toxin's log-potency from a shared population `Normal(mu, tau)`, so data from
one toxin informs the others — turning the toxin panel into a shared-information
asset.

### On prior dependence (the honest part)

Priors here encode real biology (potencies are known to order-of-magnitude), so
they are a feature, not a bug. The workflow makes their influence explicit
(`celltwin/inference/diagnostics.py`):

- **Prior predictive check** — sample from the prior, confirm the implied
  dose-responses are biologically plausible before touching data.
- **Prior sensitivity** — refit under widening priors (`potency_log_sd` sweep);
  report how far the posterior moves.
- **Identifiability** — prior-vs-posterior variance *shrinkage* on log-potency.
  ~1 ⇒ data-constrained; ~0 ⇒ prior-dominated. We **report** this rather than
  hide it: a prior-dominated parameter is disclosed, not disguised. (In the
  recovery example rotenone's potency shows shrinkage ≈ 0.94 — well constrained.)

## Data assimilation (the "twin" part)

```bash
celltwin assimilate --true-severity 0.7
```

A particle filter (`celltwin/inference/assimilate.py`, gradient-free, runs on the
NumPy engine) ingests a noisy time-course of measured observables (e.g. ATP and
ROS) and infers the unknown exposure severity + latent state online. As data
arrive the credible interval contracts:

```
 time(h)  post.mean   90% CI width
     2.0      0.554          0.137
     ...
    24.0      0.709          0.056     <- tightens toward the true 0.70
```

This is the mechanism by which the digital twin would stay synchronized with a
real cell line or patient sample as monitoring data stream in.

## Validation of the pipeline

Both capabilities are validated by **parameter recovery** on model-generated
synthetic data (`backend/tests/test_bayes.py`): NUTS recovers a known injected
potency within its credible interval; the particle filter recovers a known
severity and demonstrably tightens over time.

## Limitations & next steps

- Calibration currently infers toxin potencies; the shared rate constants are
  fixed. The JAX model already supports differentiating w.r.t. them, so a joint
  posterior over mechanism parameters is a natural extension (watch for
  identifiability/"sloppiness").
- Synthetic recovery is a *method* check, not a claim of predictive accuracy on
  real assays — that needs real time-course data and a held-out test set.
