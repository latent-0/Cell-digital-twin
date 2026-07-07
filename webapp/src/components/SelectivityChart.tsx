import { fmt, lin, log10ticks, supTick, useTokens } from "../lib/util";
import { cellLabel } from "../api";

export interface CellIC50 { id: string; ic50: number | null }

export function SelectivityChart({ data, current }: { data: CellIC50[]; current: string }) {
  const t = useTokens();
  const vals = data.filter((v): v is { id: string; ic50: number } => v.ic50 != null)
    .sort((a, b) => a.ic50 - b.ic50);
  const W = 540, H = 300, l = 120, r = 20, top = 8, b = 34;
  const x0 = l, x1 = W - r, y0 = H - b, y1 = top;
  if (!vals.length)
    return <div className="panel"><h3>Tissue selectivity</h3><p className="note">No cytotoxic IC50 for this compound.</p>
      <div style={{ color: "var(--muted)", fontSize: 13 }}>This compound is a sensitizer (no standalone IC50).</div></div>;
  const lo = Math.min(...vals.map((v) => v.ic50)), hi = Math.max(...vals.map((v) => v.ic50));
  const sx = (v: number) => lin(Math.log10(lo / 2), Math.log10(hi * 2), x0, x1)(Math.log10(v));
  const band = (y0 - y1) / vals.length;

  return (
    <div className="panel">
      <h3>Tissue selectivity</h3>
      <p className="note">Same toxin, five cell types — IC50 spread shows which tissue is most vulnerable.</p>
      <svg viewBox={`0 0 ${W} ${H}`} role="img">
        {log10ticks(lo / 2, hi * 2).map((v) => (
          <text key={v} className="tick" x={sx(v)} y={y0 + 15} textAnchor="middle">{supTick(v)}</text>
        ))}
        <line className="axis" x1={x0} x2={x1} y1={y0} y2={y0} />
        <text className="axis-title" x={(x0 + x1) / 2} y={H - 3} textAnchor="middle">IC50 (µM, log — lower = more sensitive)</text>
        {vals.map((v, i) => {
          const cy = y1 + band * (i + 0.5); const cur = v.id === current;
          return (
            <g key={v.id}>
              <line x1={x0} x2={sx(v.ic50)} y1={cy} y2={cy} stroke={cur ? t.accent : t.faint} strokeWidth={cur ? 3 : 2} strokeLinecap="round" strokeOpacity={cur ? 1 : 0.6} />
              <circle cx={sx(v.ic50)} cy={cy} r={cur ? 5.5 : 4} fill={cur ? t.accent : t.faint} />
              <text className="mono" x={x0 - 8} y={cy + 3.5} textAnchor="end" fontSize={11} fill={cur ? t.ink : t.muted} fontWeight={cur ? 600 : 400}>
                {cellLabel(v.id).replace(" cell", "").replace("Human ", "")}
              </text>
              <text className="mono" x={sx(v.ic50) + 8} y={cy + 3.5} fontSize={10} fill={t.faint}>{fmt(v.ic50)}</text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}
