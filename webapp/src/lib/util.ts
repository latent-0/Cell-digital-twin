import { useEffect, useState } from "react";

// Linear scale factory.
export const lin = (d0: number, d1: number, r0: number, r1: number) =>
  (v: number) => r0 + (r1 - r0) * ((v - d0) / (d1 - d0 || 1));

export const path = (pts: [number, number][]) =>
  "M" + pts.map((p) => p[0].toFixed(1) + "," + p[1].toFixed(1)).join("L");

export const areaPath = (top: [number, number][], bottom: [number, number][]) =>
  path(top) + "L" + path([...bottom].reverse()).slice(1) + "Z";

export function log10ticks(lo: number, hi: number): number[] {
  const t: number[] = [];
  for (let e = Math.floor(Math.log10(lo)); e <= Math.ceil(Math.log10(hi)); e++) t.push(Math.pow(10, e));
  return t.filter((v) => v >= lo * 0.5 && v <= hi * 2);
}
const SUP = "⁰¹²³⁴⁵⁶⁷⁸⁹";
export const supTick = (v: number) => {
  const e = Math.round(Math.log10(v));
  return "10" + String(e).replace(/-/g, "⁻").replace(/[0-9]/g, (d) => SUP[+d]);
};

export function fmt(x: number | null | undefined, d = 3): string {
  if (x == null || Number.isNaN(x)) return "—";
  const a = Math.abs(x);
  if (a !== 0 && (a < 1e-2 || a >= 1e5)) return x.toExponential(1);
  return (+x.toFixed(d)).toString();
}
export const pct = (x: number | null | undefined) => (x == null ? "—" : (100 * x).toFixed(0) + "%");

export function fate(v: number): ["good" | "warn" | "crit", string] {
  if (v >= 0.7) return ["good", "viable"];
  if (v >= 0.3) return ["warn", "stressed"];
  return ["crit", "non-viable"];
}

// Read theme tokens from CSS custom properties; re-read when the theme changes.
export function useTokens() {
  const read = () => {
    const cs = getComputedStyle(document.documentElement);
    const C = (n: string) => cs.getPropertyValue(n).trim();
    return {
      ink: C("--ink"), muted: C("--muted"), faint: C("--faint"),
      border: C("--border"), grid: C("--grid"), panel: C("--panel"),
      accent: C("--accent"), good: C("--good"), warn: C("--warn"), crit: C("--crit"),
      s: {
        atp: C("--s-atp"), ros: C("--s-ros"), gsh: C("--s-gsh"),
        casp: C("--s-casp"), mem: C("--s-mem"), via: C("--s-via"),
      },
    };
  };
  const [tok, setTok] = useState(read);
  useEffect(() => {
    const update = () => setTok(read());
    const mq = matchMedia("(prefers-color-scheme: dark)");
    mq.addEventListener("change", update);
    const mo = new MutationObserver(update);
    mo.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
    return () => { mq.removeEventListener("change", update); mo.disconnect(); };
  }, []);
  return tok;
}
export type Tokens = ReturnType<typeof useTokens>;
