import type { Mechanism } from "../types";
import { pct, useTokens } from "../lib/util";

export function MechanismPanel({ m }: { m: Mechanism }) {
  const t = useTokens();
  const rows: [string, number][] = [
    ["energy failure", m.energy_failure], ["oxidative stress", m.oxidative_stress],
    ["apoptosis", m.apoptotic], ["necrosis", m.necrotic],
  ];
  return (
    <div className="panel">
      <h3>Mechanism attribution</h3>
      <p className="note">Why the cell lives or dies — death-mode and driver magnitudes.</p>
      <div style={{ display: "flex", flexDirection: "column", gap: 11, marginTop: 4 }}>
        {rows.map(([lab, v]) => {
          const dom = m.dominant.indexOf(lab.split(" ")[0]) === 0;
          return (
            <div key={lab}>
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12.5, marginBottom: 4 }}>
                <span style={{ fontWeight: dom ? 600 : 400, color: dom ? "var(--ink)" : "var(--muted)" }}>{lab}</span>
                <span className="mono" style={{ color: "var(--muted)" }}>{pct(v)}</span>
              </div>
              <div style={{ height: 9, borderRadius: 5, background: "var(--panel-2)", overflow: "hidden" }}>
                <div style={{ height: "100%", width: `${Math.max(2, v * 100)}%`, borderRadius: 5, background: dom ? t.accent : t.faint }} />
              </div>
            </div>
          );
        })}
        <p style={{ fontSize: 12.5, color: "var(--muted)", margin: "8px 0 2px", lineHeight: 1.5 }}>{m.narrative}</p>
      </div>
    </div>
  );
}
