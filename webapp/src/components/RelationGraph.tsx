import type { Graph, Toxin } from "../types";
import { lin, path, useTokens } from "../lib/util";
import { hideTip, showTip } from "../lib/tip";

export function RelationGraph({ graph, toxin }: { graph: Graph; toxin: Toxin }) {
  const t = useTokens();
  const W = 560, H = 340, pad = 24;
  const sx = lin(0, 1, pad, W - pad), sy = lin(0, 1, H - pad, pad);
  const engaged = new Set(toxin.targets.map((x) => x.node));
  const typeColor: Record<string, string> = {
    organelle: t.faint, protein: t.s.atp, process: t.accent,
    gene: t.s.casp, metabolite: t.s.gsh, phenotype: t.s.ros,
  };
  const pos: Record<string, [number, number]> = {};
  graph.nodes.forEach((n) => (pos[n.id] = [sx(n.x), sy(n.y)]));

  return (
    <div className="panel span2">
      <h3>Cellular relation network</h3>
      <p className="note">Nodes engaged by {toxin.name} are highlighted; edges are signed regulatory relations.</p>
      <svg viewBox={`0 0 ${W} ${H}`} role="img">
        {graph.edges.map((e, i) => {
          const a = pos[e.source], b = pos[e.target];
          if (!a || !b) return null;
          const hot = engaged.has(e.source) || engaged.has(e.target);
          return <path key={i} className={"gedge" + (hot ? " hot" : "")} d={path([a, b])}
            strokeWidth={hot ? 1.6 : 0.8} strokeOpacity={hot ? 0.8 : 0.4} />;
        })}
        {graph.nodes.map((n) => {
          const [x, y] = pos[n.id]; const on = engaged.has(n.id);
          const label = on || n.type === "phenotype" || n.type === "organelle";
          return (
            <g key={n.id} className="gnode"
              onMouseMove={(ev) => showTip(ev.clientX, ev.clientY,
                `<b>${n.label}</b><div class="row"><span>type</span><span>${n.type}</span></div>` +
                (n.process ? `<div class="row"><span>process</span><span>${n.process}</span></div>` : "") +
                (on ? `<div class="row"><span style="color:var(--accent)">engaged by ${toxin.name}</span></div>` : ""))}
              onMouseLeave={hideTip}>
              {on && <circle cx={x} cy={y} r={13} fill={t.accent} fillOpacity={0.18} />}
              <circle cx={x} cy={y} r={on ? 6.5 : 4.2} fill={typeColor[n.type] ?? t.muted}
                stroke={on ? t.accent : t.panel} strokeWidth={on ? 2 : 1.5} />
              {label && <text x={x} y={y - 9} textAnchor="middle">{n.label.split(" (")[0]}</text>}
            </g>
          );
        })}
      </svg>
      <div className="legend">
        {["protein", "metabolite", "gene", "process", "organelle", "phenotype"].map((k) => (
          <span className="item" key={k}><span className="sw" style={{ background: typeColor[k] }} />{k}</span>
        ))}
      </div>
    </div>
  );
}
