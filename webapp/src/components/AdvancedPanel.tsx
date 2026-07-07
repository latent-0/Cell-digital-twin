import { useState } from "react";
import type { Assim, BayesFit } from "../types";
import { api } from "../api";
import { areaPath, fmt, lin, log10ticks, path, pct, supTick, useTokens } from "../lib/util";

export function BayesPanel({ toxin, cell }: { toxin: string; cell: string }) {
  const t = useTokens();
  const [fit, setFit] = useState<BayesFit | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const run = async () => {
    setBusy(true); setErr(null);
    try { setFit(await api.fitBayes(toxin, cell)); }
    catch (e) { setErr(String(e)); } finally { setBusy(false); }
  };

  const W = 540, H = 260, l = 46, r = 16, top = 14, b = 40;
  const x0 = l, x1 = W - r, y0 = H - b, y1 = top;
  let svg = null;
  if (fit) {
    const lo = fit.grid[0], hi = fit.grid[fit.grid.length - 1];
    const sx = (v: number) => lin(Math.log10(lo), Math.log10(hi), x0, x1)(Math.log10(v));
    const sy = lin(0, 1, y0, y1);
    svg = (
      <svg viewBox={`0 0 ${W} ${H}`} role="img">
        {[0, .5, 1].map((v) => (<g key={v}><line className="grid-line" x1={x0} x2={x1} y1={sy(v)} y2={sy(v)} />
          <text className="tick" x={x0 - 6} y={sy(v) + 3} textAnchor="end">{pct(v)}</text></g>))}
        {log10ticks(lo, hi).map((v) => (<text key={v} className="tick" x={sx(v)} y={y0 + 15} textAnchor="middle">{supTick(v)}</text>))}
        <line className="axis" x1={x0} x2={x1} y1={y0} y2={y0} />
        <text className="axis-title" x={(x0 + x1) / 2} y={H - 4} textAnchor="middle">dose (µM, log)</text>
        <path d={areaPath(fit.grid.map((d, i) => [sx(d), sy(fit.hi[i])]), fit.grid.map((d, i) => [sx(d), sy(fit.lo[i])]))} fill={t.accent} fillOpacity={0.16} />
        <path d={path(fit.grid.map((d, i) => [sx(d), sy(fit.median[i])]))} fill="none" stroke={t.accent} strokeWidth={2.4} />
        {fit.obs.flatMap((row, ri) => row.map((v, i) => <circle key={ri + "-" + i} cx={sx(fit.obsDoses[i])} cy={sy(v)} r={2.6} fill={t.muted} fillOpacity={0.5} />))}
      </svg>
    );
  }

  return (
    <div className="panel">
      <h3>Bayesian calibration — {toxin}</h3>
      <p className="note">NUTS posterior over potency → IC50 with credible intervals (live, ~10 s).</p>
      {!fit && <button className="run-btn" onClick={run} disabled={busy}>{busy ? "Sampling posterior…" : "Run NUTS calibration"}</button>}
      {err && <p style={{ color: "var(--crit)", fontSize: 12 }}>{err}</p>}
      {svg}
      {fit && (
        <div className="statgrid" style={{ marginTop: 10 }}>
          <div className="stat"><div className="k">IC50 (90% CI)</div><div className="v">{fmt(fit.ic50.median)}</div>
            <div className="k" style={{ textTransform: "none", letterSpacing: 0 }}>{fmt(fit.ic50.lo)} – {fmt(fit.ic50.hi)} µM</div></div>
          <div className="stat"><div className="k">R-hat</div><div className="v">{fmt(fit.rHat, 3)}</div></div>
          <div className="stat"><div className="k">identifiability</div><div className="v">{fmt(fit.shrinkage, 2)}</div>
            <div className="k" style={{ textTransform: "none", letterSpacing: 0 }}>{fit.verdict}</div></div>
        </div>
      )}
    </div>
  );
}

export function AssimPanel() {
  const t = useTokens();
  const [a, setA] = useState<Assim | null>(null);
  const [busy, setBusy] = useState(false);
  const run = async () => { setBusy(true); try { setA(await api.assimilate()); } finally { setBusy(false); } };

  const W = 540, H = 260, l = 44, r = 16, top = 14, b = 40;
  const x0 = l, x1 = W - r, y0 = H - b, y1 = top;
  let svg = null, stat = null;
  if (a) {
    const sx = lin(0, 24, x0, x1), sy = lin(0, 1, y0, y1);
    const w0 = a.hi[0] - a.lo[0], w1 = a.hi[a.hi.length - 1] - a.lo[a.lo.length - 1];
    svg = (
      <svg viewBox={`0 0 ${W} ${H}`} role="img">
        {[0, .5, 1].map((v) => (<g key={v}><line className="grid-line" x1={x0} x2={x1} y1={sy(v)} y2={sy(v)} />
          <text className="tick" x={x0 - 6} y={sy(v) + 3} textAnchor="end">{v.toFixed(1)}</text></g>))}
        {[0, 6, 12, 18, 24].map((v) => (<text key={v} className="tick" x={sx(v)} y={y0 + 15} textAnchor="middle">{v}</text>))}
        <line className="axis" x1={x0} x2={x1} y1={y0} y2={y0} />
        <text className="axis-title" x={(x0 + x1) / 2} y={H - 4} textAnchor="middle">time (h) — evidence accumulates →</text>
        <line x1={x0} x2={x1} y1={sy(a.truth)} y2={sy(a.truth)} stroke={t.crit} strokeWidth={1.3} strokeDasharray="5 4" />
        <path d={areaPath(a.times.map((tt, i) => [sx(tt), sy(a.hi[i])]), a.times.map((tt, i) => [sx(tt), sy(a.lo[i])]))} fill={t.accent} fillOpacity={0.16} />
        <path d={path(a.times.map((tt, i) => [sx(tt), sy(a.mean[i])]))} fill="none" stroke={t.accent} strokeWidth={2.4} />
        {a.times.map((tt, i) => <circle key={i} cx={sx(tt)} cy={sy(a.mean[i])} r={3} fill={t.accent} />)}
      </svg>
    );
    stat = (
      <div className="statgrid" style={{ marginTop: 10 }}>
        <div className="stat"><div className="k">recovered</div><div className="v">{fmt(a.mean[a.mean.length - 1], 2)}</div></div>
        <div className="stat"><div className="k">CI width t=2h</div><div className="v">{fmt(w0, 2)}</div></div>
        <div className="stat"><div className="k">CI width t=24h</div><div className="v">{fmt(w1, 2)}</div></div>
      </div>
    );
  }
  return (
    <div className="panel">
      <h3>Data assimilation (particle filter)</h3>
      <p className="note">Infer an unknown exposure online — the credible band tightens as measurements arrive (live, ~5 s).</p>
      {!a && <button className="run-btn" onClick={run} disabled={busy}>{busy ? "Filtering…" : "Run assimilation"}</button>}
      {svg}{stat}
    </div>
  );
}
