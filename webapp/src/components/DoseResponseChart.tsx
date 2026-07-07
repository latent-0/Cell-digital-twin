import { useRef } from "react";
import type { DoseResponse } from "../types";
import { fmt, lin, log10ticks, path, pct, supTick, useTokens } from "../lib/util";
import { hideTip, showTip } from "../lib/tip";

export function DoseResponseChart({ dr }: { dr: DoseResponse }) {
  const t = useTokens();
  const ref = useRef<SVGSVGElement>(null);
  const W = 540, H = 300, l = 46, r = 16, top = 14, b = 40;
  const x0 = l, x1 = W - r, y0 = H - b, y1 = top;
  const pts = dr.curve.filter((p) => p.dose > 0);
  const xs = pts.map((p) => p.dose);
  const lo = Math.min(...xs), hi = Math.max(...xs);
  const sx = (v: number) => lin(Math.log10(lo), Math.log10(hi), x0, x1)(Math.log10(v));
  const sy = lin(0, 1, y0, y1);
  const line = pts.map((p) => [sx(p.dose), sy(p.viability)] as [number, number]);

  const move = (ev: React.MouseEvent) => {
    const rect = ref.current!.getBoundingClientRect();
    const px = ((ev.clientX - rect.left) / rect.width) * W;
    let best = pts[0], bd = 1e9;
    for (const p of pts) { const d = Math.abs(sx(p.dose) - px); if (d < bd) { bd = d; best = p; } }
    showTip(ev.clientX, ev.clientY,
      `<div class="row"><b>${fmt(best.dose)} µM</b></div><div class="row"><span>viability</span><span>${pct(best.viability)}</span></div>`);
  };

  return (
    <div className="panel">
      <h3>Dose–response</h3>
      <p className="note">{dr.ic50 ? `Cytotoxic IC50 ${fmt(dr.ic50)} µM · Hill ${fmt(dr.hill, 2)}` : "Sensitizer — no direct cytotoxic IC50."}</p>
      <svg viewBox={`0 0 ${W} ${H}`} ref={ref} role="img">
        {[0, .25, .5, .75, 1].map((v) => (
          <g key={v}>
            <line className="grid-line" x1={x0} x2={x1} y1={sy(v)} y2={sy(v)} />
            <text className="tick" x={x0 - 6} y={sy(v) + 3} textAnchor="end">{pct(v)}</text>
          </g>
        ))}
        {log10ticks(lo, hi).map((v) => (
          <text key={v} className="tick" x={sx(v)} y={y0 + 15} textAnchor="middle">{supTick(v)}</text>
        ))}
        <line className="axis" x1={x0} x2={x1} y1={y0} y2={y0} />
        <text className="axis-title" x={(x0 + x1) / 2} y={H - 4} textAnchor="middle">dose (µM, log)</text>
        <line className="grid-line" x1={x0} x2={x1} y1={sy(.5)} y2={sy(.5)} strokeDasharray="3 3" />
        <path d={path(line)} fill="none" stroke={t.accent} strokeWidth={2.5} strokeLinejoin="round" />
        {dr.ic50 && (
          <g>
            <line x1={sx(dr.ic50)} x2={sx(dr.ic50)} y1={y0} y2={y1} stroke={t.crit} strokeWidth={1.2} strokeDasharray="4 3" />
            <circle cx={sx(dr.ic50)} cy={sy(.5)} r={4} fill={t.crit} />
            <text className="mono" x={sx(dr.ic50) + 6} y={y1 + 12} fill={t.crit} fontSize={11}>IC50 {fmt(dr.ic50)} µM</text>
          </g>
        )}
        <rect x={x0} y={y1} width={x1 - x0} height={y0 - y1} fill="transparent" onMouseMove={move} onMouseLeave={hideTip} />
      </svg>
    </div>
  );
}
