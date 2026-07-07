import { useState } from "react";
import type { Combination, Toxin } from "../types";
import { api } from "../api";
import { fmt, pct } from "../lib/util";

export function CombinationPanel({ cell, toxins, primary }: { cell: string; toxins: Toxin[]; primary: Toxin }) {
  const [partner, setPartner] = useState("hydrogen_peroxide");
  const [doseA, setDoseA] = useState(50);
  const [doseB, setDoseB] = useState(280);
  const [res, setRes] = useState<Combination | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const run = async () => {
    setBusy(true); setErr(null);
    try {
      setRes(await api.combine(cell, [
        { toxin_id: primary.id, dose: doseA },
        { toxin_id: partner, dose: doseB },
      ]));
    } catch (e) { setErr(String(e)); } finally { setBusy(false); }
  };

  const verdictColor = res
    ? (res.synergy > 0.05 ? "var(--crit)" : res.synergy < -0.05 ? "var(--good)" : "var(--muted)")
    : "var(--muted)";

  return (
    <div className="panel">
      <h3>Combination · synergy</h3>
      <p className="note">Two toxins together vs. a Bliss-independence baseline (live).</p>
      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        <label style={{ fontSize: 12.5, color: "var(--muted)" }}>
          {primary.name} dose (µM)
          <input className="num-in" type="number" value={doseA} min={0} step="any"
            onChange={(e) => setDoseA(+e.target.value)} />
        </label>
        <label style={{ fontSize: 12.5, color: "var(--muted)" }}>
          partner
          <select className="tox" style={{ minWidth: 0, width: "100%", marginTop: 4 }} value={partner}
            onChange={(e) => setPartner(e.target.value)}>
            {toxins.filter((t) => t.id !== primary.id).map((t) => (
              <option key={t.id} value={t.id}>{t.name}</option>
            ))}
          </select>
        </label>
        <label style={{ fontSize: 12.5, color: "var(--muted)" }}>
          partner dose (µM)
          <input className="num-in" type="number" value={doseB} min={0} step="any"
            onChange={(e) => setDoseB(+e.target.value)} />
        </label>
        <button className="run-btn" onClick={run} disabled={busy}>{busy ? "Running…" : "Test combination"}</button>
      </div>
      {err && <p style={{ color: "var(--crit)", fontSize: 12, marginTop: 8 }}>{err}</p>}
      {res && (
        <div className="statgrid" style={{ marginTop: 12 }}>
          <div className="stat"><div className="k">observed</div><div className="v">{pct(res.observed_viability)}</div></div>
          <div className="stat"><div className="k">expected (Bliss)</div><div className="v">{pct(res.expected_bliss)}</div></div>
          <div className="stat"><div className="k">synergy</div>
            <div className="v" style={{ color: verdictColor }}>{res.synergy > 0 ? "+" : ""}{fmt(res.synergy, 2)}</div>
            <div className="k" style={{ textTransform: "none", letterSpacing: 0 }}>{res.interpretation.split(" (")[0]}</div>
          </div>
        </div>
      )}
    </div>
  );
}
