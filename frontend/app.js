/* Cell Digital Twin dashboard. Renders real model outputs from window.TWIN_DATA.
   Vanilla JS + SVG so it is self-contained (no build step, no CDN). */
(function () {
  "use strict";
  const D = window.TWIN_DATA;
  const state = { cell: "hepatocyte", toxin: "rotenone" };

  // ---- helpers -------------------------------------------------------------
  const SVGNS = "http://www.w3.org/2000/svg";
  const h = (tag, attrs, ...kids) => {
    const e = document.createElement(tag);
    for (const k in (attrs || {})) {
      if (k === "class") e.className = attrs[k];
      else if (k.startsWith("on")) e.addEventListener(k.slice(2), attrs[k]);
      else if (attrs[k] != null) e.setAttribute(k, attrs[k]);
    }
    for (const c of kids.flat()) if (c != null) e.append(c.nodeType ? c : document.createTextNode(c));
    return e;
  };
  const s = (tag, attrs, ...kids) => {
    const e = document.createElementNS(SVGNS, tag);
    for (const k in (attrs || {})) if (attrs[k] != null) e.setAttribute(k, attrs[k]);
    for (const c of kids.flat()) if (c != null) e.append(c.nodeType ? c : document.createTextNode(c));
    return e;
  };
  const css = () => getComputedStyle(document.documentElement);
  const C = (n) => css().getPropertyValue(n).trim();
  const fmt = (x, d = 3) => {
    if (x == null) return "—";
    const a = Math.abs(x);
    if (a !== 0 && (a < 1e-2 || a >= 1e5)) return x.toExponential(1);
    return (+x.toFixed(d)).toString();
  };
  const pct = (x) => (x == null ? "—" : (100 * x).toFixed(0) + "%");
  const lin = (d0, d1, r0, r1) => (v) => r0 + (r1 - r0) * ((v - d0) / (d1 - d0 || 1));

  // ---- tooltip -------------------------------------------------------------
  let tipEl;
  const tip = () => (tipEl || (tipEl = document.body.appendChild(h("div", { class: "tip" }))));
  const showTip = (x, y, html) => {
    const t = tip(); t.innerHTML = html; t.style.opacity = "1";
    const w = t.offsetWidth, vw = window.innerWidth;
    t.style.left = Math.min(x + 14, vw - w - 8) + "px";
    t.style.top = (y + 14) + "px";
  };
  const hideTip = () => { if (tipEl) tipEl.style.opacity = "0"; };

  // ---- generic line-chart frame -------------------------------------------
  function frame(W, H, pad) {
    const g = s("svg", { viewBox: `0 0 ${W} ${H}`, role: "img" });
    return { g, W, H, pad, x0: pad.l, x1: W - pad.r, y0: H - pad.b, y1: pad.t };
  }
  function yAxis(fr, sy, ticks, label, fmtT = (v) => v) {
    for (const tk of ticks) {
      const y = sy(tk);
      fr.g.append(s("line", { class: "grid-line", x1: fr.x0, x2: fr.x1, y1: y, y2: y }));
      fr.g.append(s("text", { class: "tick", x: fr.x0 - 6, y: y + 3, "text-anchor": "end" }, fmtT(tk)));
    }
    if (label) fr.g.append(s("text", { class: "axis-title", x: fr.x0 - 34, y: (fr.y0 + fr.y1) / 2,
      transform: `rotate(-90 ${fr.x0 - 34} ${(fr.y0 + fr.y1) / 2})`, "text-anchor": "middle" }, label));
  }
  function xTicks(fr, sx, ticks, label, fmtT = (v) => v) {
    for (const tk of ticks) {
      const x = sx(tk);
      fr.g.append(s("text", { class: "tick", x, y: fr.y0 + 15, "text-anchor": "middle" }, fmtT(tk)));
    }
    fr.g.append(s("line", { class: "axis", x1: fr.x0, x2: fr.x1, y1: fr.y0, y2: fr.y0 }));
    if (label) fr.g.append(s("text", { class: "axis-title", x: (fr.x0 + fr.x1) / 2, y: fr.H - 4, "text-anchor": "middle" }, label));
  }
  const path = (pts) => "M" + pts.map((p) => p[0].toFixed(1) + "," + p[1].toFixed(1)).join("L");
  const log10ticks = (lo, hi) => {
    const t = []; for (let e = Math.floor(Math.log10(lo)); e <= Math.ceil(Math.log10(hi)); e++) t.push(Math.pow(10, e));
    return t.filter((v) => v >= lo * 0.5 && v <= hi * 2);
  };
  const supTicks = (v) => { const e = Math.round(Math.log10(v)); return "10" + supers(e); };
  const supers = (n) => String(n).replace(/-/g, "⁻").replace(/[0-9]/g, (d) => "⁰¹²³⁴⁵⁶⁷⁸⁹"[+d]);

  // ---- relation graph ------------------------------------------------------
  function graphPanel() {
    const W = 560, H = 340, pad = 22;
    const fr = frame(W, H, { l: 0, r: 0, t: 0, b: 0 });
    const sx = lin(0, 1, pad, W - pad), sy = lin(0, 1, H - pad, pad);
    const tox = D.toxins.find((t) => t.id === state.toxin);
    const engaged = new Set(tox.targets.map((t) => t.node));
    const typeColor = {
      organelle: C("--faint"), protein: C("--s-atp"), process: C("--accent"),
      gene: C("--s-casp"), metabolite: C("--s-gsh"), phenotype: C("--s-ros"),
    };
    const pos = {}; D.graph.nodes.forEach((n) => (pos[n.id] = [sx(n.x), sy(n.y)]));
    // edges
    for (const e of D.graph.edges) {
      const a = pos[e.source], b = pos[e.target]; if (!a || !b) continue;
      const hot = engaged.has(e.source) || engaged.has(e.target);
      fr.g.append(s("path", { class: "gedge" + (hot ? " hot" : ""), d: path([a, b]),
        "stroke-width": hot ? 1.6 : 0.8, "stroke-opacity": hot ? 0.8 : 0.4 }));
    }
    // nodes
    for (const n of D.graph.nodes) {
      const [x, y] = pos[n.id]; const on = engaged.has(n.id);
      const grp = s("g", { class: "gnode" });
      if (on) grp.append(s("circle", { cx: x, cy: y, r: 13, fill: C("--accent"), "fill-opacity": 0.18, stroke: "none" }));
      grp.append(s("circle", { cx: x, cy: y, r: on ? 6.5 : 4.2, fill: typeColor[n.type] || C("--muted"),
        "stroke-width": on ? 2 : 1.5, stroke: on ? C("--accent") : C("--panel") }));
      if (on || ["phenotype", "organelle"].includes(n.type))
        grp.append(s("text", { x, y: y - 9, "text-anchor": "middle" }, n.label.split(" (")[0]));
      grp.addEventListener("mousemove", (ev) => showTip(ev.clientX, ev.clientY,
        `<b>${n.label}</b><div class="row"><span>type</span><span>${n.type}</span></div>` +
        (n.process ? `<div class="row"><span>process</span><span>${n.process}</span></div>` : "") +
        (on ? `<div class="row"><span style="color:var(--accent)">engaged by ${tox.name}</span></div>` : "")));
      grp.addEventListener("mouseleave", hideTip);
      fr.g.append(grp);
    }
    const types = ["protein", "metabolite", "gene", "process", "organelle", "phenotype"];
    const leg = h("div", { class: "legend" },
      types.map((t) => h("span", { class: "item" },
        h("span", { class: "sw", style: `background:${typeColor[t]}` }), t)));
    return panel("Cellular relation network", `Nodes engaged by ${tox.name} are highlighted; edges are signed regulatory relations.`, fr.g, leg, "span2");
  }

  // ---- dose-response -------------------------------------------------------
  function dosePanel() {
    const r = D.results[state.cell][state.toxin];
    const pts = r.dr.filter((p) => p[0] > 0);
    const W = 540, H = 300, fr = frame(W, H, { l: 46, r: 16, t: 14, b: 40 });
    const xs = pts.map((p) => p[0]);
    const lo = Math.min(...xs), hi = Math.max(...xs);
    const sx = (v) => lin(Math.log10(lo), Math.log10(hi), fr.x0, fr.x1)(Math.log10(v));
    const sy = lin(0, 1, fr.y0, fr.y1);
    yAxis(fr, sy, [0, .25, .5, .75, 1], "viability", (v) => pct(v));
    xTicks(fr, sx, log10ticks(lo, hi), "dose (µM, log)", supTicks);
    // 50% guide
    fr.g.append(s("line", { class: "grid-line", x1: fr.x0, x2: fr.x1, y1: sy(.5), y2: sy(.5), "stroke-dasharray": "3 3" }));
    const line = pts.map((p) => [sx(p[0]), sy(p[1])]);
    fr.g.append(s("path", { d: path(line), fill: "none", stroke: C("--accent"), "stroke-width": 2.5, "stroke-linejoin": "round" }));
    if (r.ic50) {
      const x = sx(r.ic50);
      fr.g.append(s("line", { x1: x, x2: x, y1: fr.y0, y2: fr.y1, stroke: C("--crit"), "stroke-width": 1.2, "stroke-dasharray": "4 3" }));
      fr.g.append(s("circle", { cx: x, cy: sy(.5), r: 4, fill: C("--crit") }));
      fr.g.append(s("text", { class: "mono", x: x + 6, y: fr.y1 + 12, fill: C("--crit"), "font-size": 11 }, `IC50 ${fmt(r.ic50)} µM`));
    }
    crosshair(fr, sx, sy, pts, (p) => `<div class="row"><b>${fmt(p[0])} µM</b></div><div class="row"><span>viability</span><span>${pct(p[1])}</span></div>`);
    return panel("Dose–response", r.ic50 ? `Cytotoxic IC50 ${fmt(r.ic50)} µM · Hill ${fmt(r.hill, 2)}` : "Sensitizer — no direct cytotoxic IC50.", fr.g);
  }

  // ---- time course ---------------------------------------------------------
  function timePanel() {
    const r = D.results[state.cell][state.toxin];
    const W = 540, H = 300, fr = frame(W, H, { l: 40, r: 16, t: 14, b: 40 });
    const T = r.tc.t, tmax = T[T.length - 1];
    const sx = lin(0, tmax, fr.x0, fr.x1), sy = lin(0, 1.05, fr.y0, fr.y1);
    yAxis(fr, sy, [0, .5, 1], "level (norm.)", (v) => v.toFixed(1));
    xTicks(fr, sx, [0, 6, 12, 18, 24], "time (h)");
    const series = [
      ["atp", "ATP", C("--s-atp")], ["ros", "ROS", C("--s-ros")], ["gsh", "GSH", C("--s-gsh")],
      ["casp", "caspase", C("--s-casp")], ["mem", "membrane", C("--s-mem")],
    ];
    for (const [k, , col] of series)
      fr.g.append(s("path", { d: path(T.map((t, i) => [sx(t), sy(r.tc[k][i])])), fill: "none", stroke: col, "stroke-width": 1.8, "stroke-opacity": .9 }));
    fr.g.append(s("path", { d: path(T.map((t, i) => [sx(t), sy(r.tc.via[i])])), fill: "none", stroke: C("--s-via"), "stroke-width": 3, "stroke-dasharray": "1 0" }));
    // hover
    const idxAt = crosshairMulti(fr, sx, T);
    const overlay = s("rect", { x: fr.x0, y: fr.y1, width: fr.x1 - fr.x0, height: fr.y0 - fr.y1, fill: "transparent" });
    overlay.addEventListener("mousemove", (ev) => {
      const i = idxAt(ev); if (i == null) return;
      const rows = series.concat([["via", "viability", C("--s-via")]]).map(([k, lab, col]) =>
        `<div class="row"><span style="color:${col}">${lab}</span><span>${r.tc[k][i].toFixed(2)}</span></div>`).join("");
      showTip(ev.clientX, ev.clientY, `<b>t = ${T[i]} h</b>${rows}`);
    });
    overlay.addEventListener("mouseleave", hideTip);
    fr.g.append(overlay);
    const leg = h("div", { class: "legend" },
      series.concat([["via", "viability"]]).map(([k, lab]) =>
        h("span", { class: "item" }, h("span", { class: "ln", style: `background:var(--s-${k}); height:${k === "via" ? 3 : 2.5}px` }), lab)));
    return panel("Time course", `Trajectories at ${fmt(r.tcDose)} µM over 24 h.`, fr.g, leg);
  }

  // ---- mechanism bars ------------------------------------------------------
  function mechPanel() {
    const m = D.results[state.cell][state.toxin].mech;
    const rows = [["energy", "energy failure", m.energy], ["oxidative", "oxidative stress", m.oxidative],
      ["apoptotic", "apoptosis", m.apoptotic], ["necrotic", "necrosis", m.necrotic]];
    const wrap = h("div", { style: "display:flex;flex-direction:column;gap:11px;margin-top:4px" });
    for (const [key, lab, v] of rows) {
      const dom = (m.dominant.indexOf(lab.split(" ")[0]) === 0);
      wrap.append(h("div", {},
        h("div", { style: "display:flex;justify-content:space-between;font-size:12.5px;margin-bottom:4px" },
          h("span", { style: dom ? "font-weight:600" : "color:var(--muted)" }, lab),
          h("span", { class: "mono", style: "color:var(--muted)" }, pct(v))),
        h("div", { style: "height:9px;border-radius:5px;background:var(--panel-2);overflow:hidden" },
          h("div", { style: `height:100%;width:${Math.max(2, v * 100)}%;border-radius:5px;background:${dom ? C("--accent") : C("--faint")}` }))));
    }
    wrap.append(h("p", { style: "font-size:12.5px;color:var(--muted);margin:8px 0 2px;line-height:1.5" }, m.narrative));
    return panel("Mechanism attribution", "Why the cell lives or dies — death-mode and driver magnitudes.", wrap);
  }

  // ---- cross-cell selectivity ---------------------------------------------
  function selectivityPanel() {
    const vals = D.cells.map((c) => ({ id: c.id, name: c.name, ic50: (D.results[c.id][state.toxin] || {}).ic50 }))
      .filter((v) => v.ic50);
    const W = 540, H = 300, fr = frame(W, H, { l: 120, r: 20, t: 8, b: 34 });
    if (!vals.length) return panel("Tissue selectivity", "No cytotoxic IC50 for this compound.", h("div", { style: "color:var(--muted);font-size:13px" }, "This compound is a sensitizer (no standalone IC50)."));
    const lo = Math.min(...vals.map((v) => v.ic50)), hi = Math.max(...vals.map((v) => v.ic50));
    const sx = (v) => lin(Math.log10(lo / 2), Math.log10(hi * 2), fr.x0, fr.x1)(Math.log10(v));
    const band = (fr.y0 - fr.y1) / vals.length;
    xTicks(fr, sx, log10ticks(lo / 2, hi * 2), "IC50 (µM, log — lower = more sensitive)", supTicks);
    vals.sort((a, b) => a.ic50 - b.ic50);
    vals.forEach((v, i) => {
      const cy = fr.y1 + band * (i + .5), cur = v.id === state.cell;
      fr.g.append(s("line", { x1: fr.x0, x2: sx(v.ic50), y1: cy, y2: cy, stroke: cur ? C("--accent") : C("--faint"), "stroke-width": cur ? 3 : 2, "stroke-linecap": "round", "stroke-opacity": cur ? 1 : .6 }));
      fr.g.append(s("circle", { cx: sx(v.ic50), cy, r: cur ? 5.5 : 4, fill: cur ? C("--accent") : C("--faint") }));
      fr.g.append(s("text", { class: "mono", x: fr.x0 - 8, y: cy + 3.5, "text-anchor": "end", "font-size": 11,
        fill: cur ? C("--ink") : C("--muted"), "font-weight": cur ? 600 : 400 }, v.name.split(" (")[0].split(" cell")[0]));
      fr.g.append(s("text", { class: "mono", x: sx(v.ic50) + 8, y: cy + 3.5, "font-size": 10, fill: C("--faint") }, fmt(v.ic50)));
    });
    return panel("Tissue selectivity", `Same toxin, five cell types — IC50 spread shows which tissue is most vulnerable.`, fr.g);
  }

  // ---- validation scatter (global) ----------------------------------------
  function validationPanel() {
    const e = D.validation.entries.filter((x) => x.model);
    const W = 540, H = 300, fr = frame(W, H, { l: 46, r: 16, t: 14, b: 40 });
    const all = e.flatMap((x) => [x.ref, x.model]);
    const lo = Math.min(...all), hi = Math.max(...all);
    const sc = (v) => lin(Math.log10(lo / 3), Math.log10(hi * 3), 0, 1)(Math.log10(v));
    const sx = (v) => lin(0, 1, fr.x0, fr.x1)(sc(v)), sy = (v) => lin(0, 1, fr.y0, fr.y1)(sc(v));
    const tk = log10ticks(lo / 3, hi * 3);
    yAxis(fr, sy, tk, "model IC50 (µM)", supTicks);
    xTicks(fr, sx, tk, "literature IC50 (µM)", supTicks);
    fr.g.append(s("line", { x1: fr.x0, y1: fr.y0, x2: fr.x1, y2: fr.y1, stroke: C("--muted"), "stroke-width": 1, "stroke-dasharray": "5 4", "stroke-opacity": .6 }));
    for (const x of e) {
      const cx = sx(x.ref), cy = sy(x.model);
      const dot = s("circle", { cx, cy, r: 5, fill: x.pass ? C("--good") : C("--warn"), "fill-opacity": .85, stroke: C("--panel"), "stroke-width": 1 });
      dot.addEventListener("mousemove", (ev) => showTip(ev.clientX, ev.clientY,
        `<b>${x.toxin}</b><div class="row"><span>literature</span><span>${fmt(x.ref)} µM</span></div><div class="row"><span>model</span><span>${fmt(x.model)} µM</span></div><div class="row"><span>fold error</span><span>${fmt(x.fold, 2)}×</span></div>`));
      dot.addEventListener("mouseleave", hideTip);
      fr.g.append(dot);
    }
    const leg = h("div", { class: "legend" },
      h("span", { class: "item" }, h("span", { class: "sw", style: `background:${C("--good")}` }), "within 1 log"),
      h("span", { class: "item" }, h("span", { class: "ln", style: `background:${C("--muted")}` }), "y = x (perfect)"));
    return panel("Validation vs literature", `${D.validation.nPass}/${D.validation.n} within 1 log · Spearman ρ = ${fmt(D.validation.spearman, 3)} · median fold ${fmt(D.validation.medianFold, 2)}×`, fr.g, leg, "span2");
  }

  // ---- Bayesian panel (global) --------------------------------------------
  function bayesPanel() {
    const b = D.bayes;
    const W = 540, H = 300, fr = frame(W, H, { l: 46, r: 16, t: 14, b: 40 });
    const lo = b.grid[0], hi = b.grid[b.grid.length - 1];
    const sx = (v) => lin(Math.log10(lo), Math.log10(hi), fr.x0, fr.x1)(Math.log10(v));
    const sy = lin(0, 1, fr.y0, fr.y1);
    yAxis(fr, sy, [0, .5, 1], "viability", pct);
    xTicks(fr, sx, log10ticks(lo, hi), "dose (µM, log)", supTicks);
    // credible band
    const up = b.grid.map((d, i) => [sx(d), sy(b.hi[i])]);
    const dn = b.grid.map((d, i) => [sx(d), sy(b.lo[i])]).reverse();
    fr.g.append(s("path", { d: path(up) + "L" + path(dn).slice(1), fill: C("--accent"), "fill-opacity": .16, stroke: "none" }));
    fr.g.append(s("path", { d: path(b.grid.map((d, i) => [sx(d), sy(b.median[i])])), fill: "none", stroke: C("--accent"), "stroke-width": 2.4 }));
    // observed points
    const flat = b.obs.flatMap((row) => row.map((v, i) => [b.obsDoses[i], v]));
    for (const [d, v] of flat) fr.g.append(s("circle", { cx: sx(d), cy: sy(v), r: 2.6, fill: C("--muted"), "fill-opacity": .55 }));
    const leg = h("div", { class: "legend" },
      h("span", { class: "item" }, h("span", { class: "ln", style: `background:${C("--accent")}` }), "posterior median"),
      h("span", { class: "item" }, h("span", { class: "sw", style: `background:${C("--accent")};opacity:.25` }), "90% credible band"),
      h("span", { class: "item" }, h("span", { class: "sw", style: `background:${C("--muted")};border-radius:50%` }), "observations"));
    const stat = h("div", { class: "statgrid", style: "margin-top:10px" },
      h("div", { class: "stat" }, h("div", { class: "k" }, "IC50 (90% CI)"), h("div", { class: "v" }, `${fmt(b.ic50.median)}`),
        h("div", { class: "k", style: "text-transform:none;letter-spacing:0" }, `${fmt(b.ic50.lo)} – ${fmt(b.ic50.hi)} µM`)),
      h("div", { class: "stat" }, h("div", { class: "k" }, "R-hat"), h("div", { class: "v" }, fmt(b.rHat, 3))),
      h("div", { class: "stat" }, h("div", { class: "k" }, "identifiability"), h("div", { class: "v" }, fmt(b.shrinkage, 2)),
        h("div", { class: "k", style: "text-transform:none;letter-spacing:0" }, b.verdict)));
    return panel(`Bayesian calibration — ${b.toxin}`, "NUTS posterior over potency → IC50 with credible intervals.", fr.g, h("div", {}, leg, stat));
  }

  // ---- assimilation panel (global) ----------------------------------------
  function assimPanel() {
    const a = D.assim;
    const W = 540, H = 300, fr = frame(W, H, { l: 44, r: 16, t: 14, b: 40 });
    const sx = lin(0, 24, fr.x0, fr.x1), sy = lin(0, 1, fr.y0, fr.y1);
    yAxis(fr, sy, [0, .5, 1], "ETC inhibition", (v) => v.toFixed(1));
    xTicks(fr, sx, [0, 6, 12, 18, 24], "time (h) — evidence accumulates →");
    fr.g.append(s("line", { x1: fr.x0, x2: fr.x1, y1: sy(a.truth), y2: sy(a.truth), stroke: C("--crit"), "stroke-width": 1.3, "stroke-dasharray": "5 4" }));
    fr.g.append(s("text", { class: "mono", x: fr.x1 - 4, y: sy(a.truth) - 5, "text-anchor": "end", "font-size": 10, fill: C("--crit") }, `truth ${a.truth}`));
    const up = a.times.map((t, i) => [sx(t), sy(a.hi[i])]);
    const dn = a.times.map((t, i) => [sx(t), sy(a.lo[i])]).reverse();
    fr.g.append(s("path", { d: path(up) + "L" + path(dn).slice(1), fill: C("--accent"), "fill-opacity": .16, stroke: "none" }));
    fr.g.append(s("path", { d: path(a.times.map((t, i) => [sx(t), sy(a.mean[i])])), fill: "none", stroke: C("--accent"), "stroke-width": 2.4 }));
    a.times.forEach((t, i) => fr.g.append(s("circle", { cx: sx(t), cy: sy(a.mean[i]), r: 3, fill: C("--accent") })));
    const w0 = a.hi[0] - a.lo[0], w1 = a.hi[a.hi.length - 1] - a.lo[a.lo.length - 1];
    const stat = h("div", { class: "statgrid", style: "margin-top:10px" },
      h("div", { class: "stat" }, h("div", { class: "k" }, "recovered"), h("div", { class: "v" }, fmt(a.mean[a.mean.length - 1], 2))),
      h("div", { class: "stat" }, h("div", { class: "k" }, "CI width t=2h"), h("div", { class: "v" }, fmt(w0, 2))),
      h("div", { class: "stat" }, h("div", { class: "k" }, "CI width t=24h"), h("div", { class: "v" }, fmt(w1, 2))));
    return panel("Data assimilation (particle filter)", "Inferring an unknown exposure online — the credible band tightens as measurements arrive.", fr.g, stat);
  }

  // ---- crosshair helpers ---------------------------------------------------
  function crosshair(fr, sx, sy, pts, tipFn) {
    const marker = s("circle", { r: 4, fill: C("--accent"), opacity: 0 });
    const vline = s("line", { y1: fr.y1, y2: fr.y0, stroke: C("--faint"), "stroke-width": 1, opacity: 0 });
    fr.g.append(vline); fr.g.append(marker);
    const ov = s("rect", { x: fr.x0, y: fr.y1, width: fr.x1 - fr.x0, height: fr.y0 - fr.y1, fill: "transparent" });
    ov.addEventListener("mousemove", (ev) => {
      const rect = fr.g.getBoundingClientRect();
      const px = fr.x0 + (ev.clientX - rect.left) / rect.width * fr.W - fr.x0;
      let best = 0, bd = 1e9;
      pts.forEach((p, i) => { const d = Math.abs(sx(p[0]) - px); if (d < bd) { bd = d; best = i; } });
      const p = pts[best];
      marker.setAttribute("cx", sx(p[0])); marker.setAttribute("cy", sy(p[1])); marker.setAttribute("opacity", 1);
      vline.setAttribute("x1", sx(p[0])); vline.setAttribute("x2", sx(p[0])); vline.setAttribute("opacity", .5);
      showTip(ev.clientX, ev.clientY, tipFn(p));
    });
    ov.addEventListener("mouseleave", () => { hideTip(); marker.setAttribute("opacity", 0); vline.setAttribute("opacity", 0); });
    fr.g.append(ov);
  }
  function crosshairMulti(fr, sx, T) {
    return (ev) => {
      const rect = fr.g.getBoundingClientRect();
      const px = (ev.clientX - rect.left) / rect.width * fr.W;
      let best = null, bd = 1e9;
      T.forEach((t, i) => { const d = Math.abs(sx(t) - px); if (d < bd) { bd = d; best = i; } });
      return best;
    };
  }

  // ---- panel wrapper -------------------------------------------------------
  function panel(title, note, ...body) {
    const cls = body[body.length - 1] === "span2" ? "panel span2" : "panel";
    if (body[body.length - 1] === "span2") body = body.slice(0, -1);
    return h("div", { class: cls }, h("h3", {}, title), note ? h("p", { class: "note" }, note) : null, ...body);
  }

  // ---- fate classification -------------------------------------------------
  function fate(v) {
    if (v >= 0.7) return ["good", "viable"];
    if (v >= 0.3) return ["warn", "stressed"];
    return ["crit", "non-viable"];
  }

  // ---- render --------------------------------------------------------------
  function render() {
    const root = document.getElementById("app");
    root.innerHTML = "";
    const tox = D.toxins.find((t) => t.id === state.toxin);
    const r = D.results[state.cell][state.toxin];
    const finalV = r.tc.via[r.tc.via.length - 1];
    const [fc, flabel] = fate(finalV);
    const cell = D.cells.find((c) => c.id === state.cell);

    const header = h("div", { class: "head" },
      h("div", {}, h("div", { class: "eyebrow" }, "Toxicology digital twin"),
        h("h1", {}, "Cell Digital Twin"),
        h("div", { class: "sub" }, "A mechanistic + network model of a cell. Pick a cell type and a toxin to see how the compound propagates through the cell's relations, what happens over 24 h, and why it lives or dies — all from the real ", h("code", { style: "font-family:var(--mono)" }, "celltwin"), " engine.")),
      h("div", { class: "statgrid" },
        h("div", { class: "stat" }, h("div", { class: "k" }, "toxins"), h("div", { class: "v" }, D.toxins.length)),
        h("div", { class: "stat" }, h("div", { class: "k" }, "cell types"), h("div", { class: "v" }, D.cells.length)),
        h("div", { class: "stat" }, h("div", { class: "k" }, "validated"), h("div", { class: "v" }, `${D.validation.nPass}/${D.validation.n}`))));

    const cellChips = h("div", { class: "chips" }, D.cells.map((c) =>
      h("button", { class: "chip", "aria-pressed": c.id === state.cell, onclick: () => { state.cell = c.id; render(); } }, c.name.split(" (")[0])));
    const toxSel = h("select", { class: "tox", onchange: (e) => { state.toxin = e.target.value; render(); } },
      D.toxins.map((t) => h("option", { value: t.id }, `${t.name} — ${t.cls.replace(/_/g, " ")}`)));
    toxSel.value = state.toxin;
    const controls = h("div", { class: "controls" },
      h("div", { class: "ctrl-row" }, h("span", { class: "ctrl-label" }, "Cell"), cellChips),
      h("div", { class: "ctrl-row" }, h("span", { class: "ctrl-label" }, "Toxin"), toxSel,
        tox.bioact ? h("span", { class: "pill" }, h("span", { class: "dot", style: `background:${C("--warn")}` }), "CYP-bioactivated") : null));

    const hero = h("div", { class: "hero" },
      h("div", { class: "gauge" },
        h("div", { class: "num", style: `color:var(--${fc})` }, pct(finalV)),
        h("div", { class: "cap" }, "24 h viability")),
      h("div", { class: "hero-info" },
        h("div", { class: "hero-title" }, `${tox.name} on ${cell.name}`),
        h("div", { class: "hero-desc" }, tox.desc),
        h("div", { class: "hero-meta" },
          h("span", { class: "pill" }, "outcome ", h("b", { class: `fate ${fc}` }, flabel)),
          h("span", { class: "pill" }, "dominant ", h("b", {}, r.mech.dominant)),
          h("span", { class: "pill" }, "IC50 ", h("b", {}, r.ic50 ? fmt(r.ic50) + " µM" : "n/a")),
          h("span", { class: "pill" }, "CYP ", h("b", {}, cell.cyp)))));

    const grid = h("div", { class: "grid" },
      graphPanel(), dosePanel(), timePanel(), mechPanel(), selectivityPanel(),
      validationPanel(), bayesPanel(), assimPanel());

    const foot = h("div", { class: "foot" },
      "Generated from the ", h("code", {}, "celltwin"), " engine — dose-response, mechanism, calibration (17/17 within 1 log), NUTS posteriors and particle-filter assimilation are all real model outputs. Not a substitute for experimental toxicology.");

    root.append(header, controls, hero, grid, foot);
  }

  render();
  // re-render on theme change so chart colors follow the tokens
  matchMedia("(prefers-color-scheme: dark)").addEventListener("change", render);
  new MutationObserver(render).observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
})();
