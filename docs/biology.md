# Biology Reference & Modeling Assumptions

This document records what the digital twin models, the assumptions behind the
ODE core, and the reference toxins used for validation. Parameters in
`backend/celltwin/engine/params.py` are literature-informed placeholders; the
Phase 4 goal is to calibrate them against published data.

## State variables

| Symbol | Meaning | Baseline | Notes |
|--------|---------|----------|-------|
| ATP  | Energy charge (normalized) | 1.0 | Produced by ETC × ATP synthase, consumed at a basal rate. |
| ROS  | Reactive oxygen species | 0.05 | Basal + ETC-leak + toxin input; scavenged by GSH. |
| GSH  | Glutathione buffer | 1.0 | Synthesized by GCLC; consumed scavenging ROS and by reactive metabolites. |
| CASP | Caspase / apoptosis commitment | 0.0 | Triggered by high ROS, low ATP, direct pro-apoptotic agents, or DNA damage; has commitment feedback. |
| MEM  | Plasma-membrane integrity | 1.0 | Damaged by lipid peroxidation, disruptors, and catastrophic ATP loss. |

### Coupling processes (how a toxin enters the ODEs)

A toxin's target node maps (via `process_map`) to one of these engine processes:
`etc` (ETC complexes → ATP), `atp_synthesis` (ATP synthase / uncoupling),
`ros_production` (oxidative stressors), `gsh_synthesis` / `gsh_pool` (antioxidant
capacity), `membrane` (disruptors), `apoptosis` (direct pro-apoptotic agents),
and `dna` (genotoxic agents, acting through p53 → BAX). CYP-dependent toxins are
additionally gated by the cell's `cyp_activity`.

**Viability** = `MEM × (1 − CASP)` — a cell survives only if it neither
executes apoptosis nor loses membrane integrity.

## Modeled pathways (why these)

1. **Mitochondrial bioenergetics** — ETC Complexes I/III/IV feed the proton
   gradient that drives ATP synthase. Target of rotenone, cyanide, FCCP.
2. **Oxidative stress / glutathione** — ROS generation vs GSH-dependent
   scavenging and NADPH-backed resynthesis. Target of H₂O₂, menadione, BSO.
3. **Apoptosis decision** — energy crisis and oxidative stress converge on the
   BAX/BCL-2 → cytochrome-c → caspase axis. The integrator that turns damage
   into a life/death call.
4. **Xenobiotic metabolism** — CYP450 bioactivation converts some pro-toxins to
   reactive metabolites (APAP → NAPQI) that drain GSH. Gated by `cyp_activity`.
5. **Membrane integrity** — lytic/necrotic death from detergents or severe
   lipid peroxidation.

## Reference toxins (validation targets)

| Toxin | Mechanism the twin must reproduce | Expected dominant death mode |
|-------|-----------------------------------|------------------------------|
| Rotenone | Complex I inhibition → ATP collapse | energy failure |
| Cyanide | Complex IV inhibition → ATP collapse | energy failure / apoptosis |
| FCCP | Uncoupling → ATP loss without ETC block | energy failure |
| H₂O₂ | ROS surge → GSH depletion → oxidative death | oxidative stress → apoptosis |
| Menadione | Redox cycling → sustained ROS | oxidative stress → apoptosis |
| Acetaminophen | CYP → NAPQI → GSH depletion (dose-thresholded, CYP-gated) | oxidative stress |
| BSO | GCLC inhibition → low GSH (sensitizer, weak alone) | — (potentiator) |
| Triton X-100 | Membrane solubilization | necrosis |
| Antimycin A | Complex III inhibition | energy failure |
| Oligomycin | ATP synthase inhibition | energy failure |
| Paraquat / tBHP | Redox cycling / peroxide → ROS | oxidative stress → apoptosis |
| Arsenite | Thiol binding (GSH↓) + ROS (dual) | oxidative stress → apoptosis |
| CCl₄ | CYP → trichloromethyl radical → lipid peroxidation (CYP-gated) | membrane / oxidative |
| Staurosporine | Direct intrinsic-apoptosis inducer | apoptosis |
| Etoposide | Topoisomerase II poison → DNA breaks → p53 | apoptosis (genotoxic) |
| Cisplatin | DNA crosslinks (+ mild GSH↓); nephrotoxic | apoptosis (genotoxic) |
| Doxorubicin | Redox cycling (ROS) + DNA intercalation (dual); cardiotoxic | apoptosis |

## Cell types

All cell types share the reference relation graph (v1 abstraction: same core
machinery, different physiology) and differ by parameter overrides and CYP
capacity. Defined via a YAML `extends` mechanism to stay DRY.

| Cell | Distinguishing physiology | Characteristic vulnerability (reproduced) |
|------|---------------------------|-------------------------------------------|
| Hepatocyte | High CYP metabolism | Bioactivated toxins (APAP, CCl₄) |
| Cardiomyocyte | Energy-dependent, poor repair, low CYP | Doxorubicin > hepatocyte (cardiotoxicity) |
| Neuron | Very high energy demand, low antioxidant reserve | Rotenone / oxidative (most vulnerable) |
| Proximal tubule | Transport-driven, concentrates toxins | Cisplatin (nephrotoxicity) |
| Cancer cell | Glycolytic, antioxidant-rich, apoptosis-resistant | Broadly resistant (therapeutic-window contrast) |

### Qualitative validation status (v0.1)

Current model reproduces, and the test suite asserts:

- Unperturbed cell rests at homeostasis; control viability ≈ 100%.
- Dose-response is monotonic; IC50s rank rotenone ≪ H₂O₂ (correct order).
- Rotenone/FCCP death is attributed to **energy failure**; Triton to **necrosis**.
- **APAP is CYP-gated**: toxic at `cyp_activity=1`, protected at `cyp_activity=0`
  — the metabolism-dependent hallmark of paracetamol hepatotoxicity.
- **BSO synergizes with H₂O₂**: GSH-synthesis blockade sensitizes the cell to an
  oxidant (a well-established experimental result).
- **Tissue selectivity**: doxorubicin is more potent on cardiomyocytes than
  hepatocytes; rotenone hits neurons hardest; cisplatin is proximal-tubule
  selective; cancer cells resist apoptosis inducers (staurosporine) — each
  asserted in `backend/tests/test_cells.py`.
- **CCl₄ and APAP are CYP-gated**: both are lethal to high-CYP hepatocytes and
  spared in low-CYP cell types or when `cyp_activity=0`.

### Phase 4 quantitative targets (not yet met)

- IC50s within ~1 log of published cell-based values.
- Time-to-death kinetics consistent with reported assays.
- Each numeric parameter annotated with a citation.

## Known simplifications (v0.1)

- Single well-mixed cell; no spatial/organelle compartment diffusion.
- ATP, ROS, GSH are normalized (dimensionless), not absolute concentrations.
- CYP bioactivation is a single scalar gate, not a full Phase I/II kinetic model.
- The relation graph is used for coupling/attribution/visualization; it does not
  yet run an independent Boolean/propagation dynamic (planned).
