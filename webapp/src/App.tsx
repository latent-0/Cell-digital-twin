import { useEffect, useState } from "react";
import "./theme.css";
import { api, cellLabel } from "./api";
import type { DoseResponse, Graph, SimulationResult, Toxin } from "./types";
import { Hero } from "./components/Hero";
import { RelationGraph } from "./components/RelationGraph";
import { DoseResponseChart } from "./components/DoseResponseChart";
import { TimeCourseChart } from "./components/TimeCourseChart";
import { MechanismPanel } from "./components/MechanismPanel";
import { SelectivityChart, type CellIC50 } from "./components/SelectivityChart";
import { CombinationPanel } from "./components/CombinationPanel";
import { BayesPanel, AssimPanel } from "./components/AdvancedPanel";

export default function App() {
  const [cells, setCells] = useState<string[]>([]);
  const [toxins, setToxins] = useState<Toxin[]>([]);
  const [cell, setCell] = useState("hepatocyte");
  const [toxinId, setToxinId] = useState("rotenone");
  const [graph, setGraph] = useState<Graph | null>(null);
  const [dr, setDr] = useState<DoseResponse | null>(null);
  const [sim, setSim] = useState<SimulationResult | null>(null);
  const [sel, setSel] = useState<CellIC50[]>([]);
  const [cyp, setCyp] = useState<number | undefined>(undefined);
  const [fatal, setFatal] = useState<string | null>(null);

  // Initial load: cells + toxins.
  useEffect(() => {
    (async () => {
      try {
        const [cs, tx] = await Promise.all([api.cells(), api.toxins()]);
        setCells(cs); setToxins(tx);
      } catch (e) {
        setFatal("Cannot reach the backend. Start it with:  uvicorn celltwin.api.app:app --app-dir backend  (then reload).\n\n" + String(e));
      }
    })();
  }, []);

  // Graph follows the selected cell (also read cyp from a node? use /cells later).
  useEffect(() => { api.graph(cell).then(setGraph).catch(() => setGraph(null)); }, [cell]);

  // Dose-response + simulation follow cell + toxin.
  useEffect(() => {
    let live = true;
    setDr(null); setSim(null);
    (async () => {
      const d = await api.doseResponse(toxinId, cell);
      if (!live) return;
      setDr(d);
      const maxDose = d.curve.length ? d.curve[d.curve.length - 1].dose : 100;
      const dose = d.ic50 ? d.ic50 * 3 : maxDose;
      const s = await api.simulate(cell, toxinId, dose);
      if (live) setSim(s);
    })().catch(() => {});
    return () => { live = false; };
  }, [cell, toxinId]);

  // Cross-cell selectivity for the current toxin.
  useEffect(() => {
    let live = true;
    Promise.all(cells.map((c) => api.doseResponse(toxinId, c).then((d) => ({ id: c, ic50: d.ic50 }))))
      .then((r) => { if (live) setSel(r); }).catch(() => {});
    return () => { live = false; };
  }, [cells, toxinId]);

  // CYP per cell (defaults known client-side; hepatocyte=1).
  useEffect(() => {
    const map: Record<string, number> = { hepatocyte: 1, cardiomyocyte: 0.1, neuron: 0.05, proximal_tubule: 0.3, cancer_cell: 0.2 };
    setCyp(map[cell]);
  }, [cell]);

  const toxin = toxins.find((t) => t.id === toxinId);

  if (fatal) return (
    <div className="wrap"><div className="panel" style={{ whiteSpace: "pre-wrap", lineHeight: 1.6 }}>
      <h3>Backend not reachable</h3><p className="note" style={{ fontSize: 13 }}>{fatal}</p></div></div>
  );
  if (!toxin) return <div className="wrap"><p className="note">Loading…</p></div>;

  const tcDose = dr ? (dr.ic50 ? dr.ic50 * 3 : (dr.curve.at(-1)?.dose ?? 100)) : 0;

  return (
    <div className="wrap">
      <div className="head">
        <div>
          <div className="eyebrow">Toxicology digital twin · live</div>
          <h1>Cell Digital Twin</h1>
          <div className="sub">A mechanistic + network model of a cell, served live by the <code style={{ fontFamily: "var(--mono)" }}>celltwin</code> API. Pick a cell type and a toxin — every panel is computed on demand by the backend.</div>
        </div>
        <div className="statgrid">
          <div className="stat"><div className="k">toxins</div><div className="v">{toxins.length}</div></div>
          <div className="stat"><div className="k">cell types</div><div className="v">{cells.length}</div></div>
        </div>
      </div>

      <div className="controls">
        <div className="ctrl-row">
          <span className="ctrl-label">Cell</span>
          <div className="chips">
            {cells.map((c) => (
              <button key={c} className="chip" aria-pressed={c === cell} onClick={() => setCell(c)}>{cellLabel(c).replace(" cell", "")}</button>
            ))}
          </div>
        </div>
        <div className="ctrl-row">
          <span className="ctrl-label">Toxin</span>
          <select className="tox" value={toxinId} onChange={(e) => setToxinId(e.target.value)}>
            {toxins.map((t) => <option key={t.id} value={t.id}>{t.name} — {t.class.replace(/_/g, " ")}</option>)}
          </select>
        </div>
      </div>

      <Hero toxin={toxin} cell={cell} sim={sim} ic50={dr?.ic50 ?? null} cyp={cyp} />

      <div className="grid">
        {graph && <RelationGraph graph={graph} toxin={toxin} />}
        {dr ? <DoseResponseChart dr={dr} /> : <Loading title="Dose–response" />}
        {sim ? <TimeCourseChart sim={sim} dose={tcDose} /> : <Loading title="Time course" />}
        {sim ? <MechanismPanel m={sim.mechanism} /> : <Loading title="Mechanism attribution" />}
        <SelectivityChart data={sel} current={cell} />
        <CombinationPanel cell={cell} toxins={toxins} primary={toxin} />
        <BayesPanel toxin={toxinId} cell={cell} />
        <AssimPanel />
      </div>

      <div className="foot">
        Live from the <code>celltwin</code> engine — dose-response, mechanism, tissue selectivity, synergy, NUTS calibration and particle-filter assimilation are all computed on demand. Not a substitute for experimental toxicology.
      </div>
    </div>
  );
}

function Loading({ title }: { title: string }) {
  return <div className="panel"><h3>{title}</h3><p className="note">Computing…</p></div>;
}
