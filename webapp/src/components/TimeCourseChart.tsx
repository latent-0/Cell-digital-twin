import { useRef } from "react";
import type { SimulationResult } from "../types";
import { fmt, lin, path, useTokens } from "../lib/util";
import { hideTip, showTip } from "../lib/tip";

export function TimeCourseChart({ sim, dose }: { sim: SimulationResult; dose: number }) {
  const t = useTokens();
  const ref = useRef<SVGSVGElement>(null);
  const W = 540, H = 300, l = 40, r = 16, top = 14, b = 40;
  const x0 = l, x1 = W - r, y0 = H - b, y1 = top;
  const tr = sim.trajectory;
  const tmax = tr[tr.length - 1].t;
  const sx = lin(0, tmax, x0, x1), sy = lin(0, 1.05, y0, y1);
  const series: [keyof typeof tr[0], string, string][] = [
    ["atp", "ATP", t.s.atp], ["ros", "ROS", t.s.ros], ["gsh", "GSH", t.s.gsh],
    ["caspase", "caspase", t.s.casp], ["membrane", "membrane", t.s.mem],
  ];
  const varKey: Record<string, "atp" | "ros" | "gsh" | "casp" | "mem" | "via"> = {
    atp: "atp", ros: "ros", gsh: "gsh", caspase: "casp", membrane: "mem", viability: "via",
  };

  const move = (ev: React.MouseEvent) => {
    const rect = ref.current!.getBoundingClientRect();
    const px = ((ev.clientX - rect.left) / rect.width) * W;
    let bi = 0, bd = 1e9;
    tr.forEach((p, i) => { const d = Math.abs(sx(p.t) - px); if (d < bd) { bd = d; bi = i; } });
    const p = tr[bi];
    const rows = [...series, ["viability", "viability", t.s.via] as const]
      .map(([k, lab, col]) => `<div class="row"><span style="color:${col}">${lab}</span><span>${(p[k] as number).toFixed(2)}</span></div>`).join("");
    showTip(ev.clientX, ev.clientY, `<b>t = ${p.t} h</b>${rows}`);
  };

  return (
    <div className="panel">
      <h3>Time course</h3>
      <p className="note">Trajectories at {fmt(dose)} µM over 24 h.</p>
      <svg viewBox={`0 0 ${W} ${H}`} ref={ref} role="img">
        {[0, .5, 1].map((v) => (
          <g key={v}>
            <line className="grid-line" x1={x0} x2={x1} y1={sy(v)} y2={sy(v)} />
            <text className="tick" x={x0 - 6} y={sy(v) + 3} textAnchor="end">{v.toFixed(1)}</text>
          </g>
        ))}
        {[0, 6, 12, 18, 24].map((v) => (
          <text key={v} className="tick" x={sx(v)} y={y0 + 15} textAnchor="middle">{v}</text>
        ))}
        <line className="axis" x1={x0} x2={x1} y1={y0} y2={y0} />
        <text className="axis-title" x={(x0 + x1) / 2} y={H - 4} textAnchor="middle">time (h)</text>
        {series.map(([k, , col]) => (
          <path key={k as string} d={path(tr.map((p) => [sx(p.t), sy(p[k] as number)]))} fill="none" stroke={col} strokeWidth={1.8} strokeOpacity={0.9} />
        ))}
        <path d={path(tr.map((p) => [sx(p.t), sy(p.viability)]))} fill="none" stroke={t.s.via} strokeWidth={3} />
        <rect x={x0} y={y1} width={x1 - x0} height={y0 - y1} fill="transparent" onMouseMove={move} onMouseLeave={hideTip} />
      </svg>
      <div className="legend">
        {[...series.map(([k, lab]) => [k, lab] as const), ["viability", "viability"] as const].map(([k, lab]) => (
          <span className="item" key={k as string}><span className="ln" style={{ background: `var(--s-${varKey[k as string]})`, height: k === "viability" ? 3 : 2.5 }} />{lab}</span>
        ))}
      </div>
    </div>
  );
}
