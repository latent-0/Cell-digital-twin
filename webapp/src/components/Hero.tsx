import type { SimulationResult, Toxin } from "../types";
import { cellLabel } from "../api";
import { fate, fmt, pct } from "../lib/util";

export function Hero({ toxin, cell, sim, ic50, cyp }: {
  toxin: Toxin; cell: string; sim: SimulationResult | null; ic50: number | null; cyp?: number;
}) {
  const v = sim ? sim.final_viability : null;
  const [fc, flabel] = v == null ? ["warn" as const, "…"] : fate(v);
  return (
    <div className="hero">
      <div className="gauge">
        <div className="num" style={{ color: `var(--${fc})` }}>{pct(v)}</div>
        <div className="cap">24 h viability</div>
      </div>
      <div className="hero-info">
        <div className="hero-title">{toxin.name} on {cellLabel(cell)}</div>
        <div className="hero-desc">{toxin.description}</div>
        <div className="hero-meta">
          <span className="pill">outcome <b className={`fate ${fc}`}>{flabel}</b></span>
          <span className="pill">dominant <b>{sim?.mechanism.dominant ?? "…"}</b></span>
          <span className="pill">IC50 <b>{ic50 ? fmt(ic50) + " µM" : "n/a"}</b></span>
          {cyp != null && <span className="pill">CYP <b>{cyp}</b></span>}
          {toxin.requires_bioactivation && <span className="pill"><span className="dot" style={{ background: "var(--warn)" }} />CYP-bioactivated</span>}
        </div>
      </div>
    </div>
  );
}
