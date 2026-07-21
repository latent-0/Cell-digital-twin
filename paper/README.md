# Paper

`celltwin_ieee.tex` — a complete IEEE-format manuscript on the cell digital twin,
grounded entirely in this repository's real model and results.

## Reproduce the figures and numbers

Every figure in `figures/` and every quantitative claim in the paper is generated
from the engine — nothing is illustrative:

```bash
pip install -e ".[dev]" matplotlib      # from repo root
python paper/make_figures.py            # writes figures/*.pdf and numbers.json
```

`numbers.json` holds the exact values cited in the text (calibration, Bayesian
IC50 + CI, assimilation, tissue-selectivity IC50s, surrogate R²), so the prose and
figures stay consistent whenever the model changes.

## Build the PDF

No local LaTeX needed — upload `celltwin_ieee.tex` + the `figures/` folder to
Overleaf, or locally:

```bash
cd paper && pdflatex celltwin_ieee && pdflatex celltwin_ieee
```

## What the paper claims (and doesn't)

It presents the twin as a **well-posed, uncertainty-quantified, open** QST model,
validated for internal consistency and correct potency ordering against literature
anchors. It is explicit that the theorems are classical (the contribution is
instantiation + validation), and that **blind prediction on a held-out set of real
assay data** — the strongest external test — is stated as future work, not claimed.
