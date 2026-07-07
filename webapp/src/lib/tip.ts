// Imperative floating tooltip shared by all charts (one node appended to body).
let el: HTMLDivElement | null = null;
function node(): HTMLDivElement {
  if (!el) { el = document.createElement("div"); el.className = "tip"; document.body.appendChild(el); }
  return el;
}
export function showTip(x: number, y: number, html: string) {
  const t = node();
  t.innerHTML = html;
  t.style.opacity = "1";
  const w = t.offsetWidth;
  t.style.left = Math.min(x + 14, window.innerWidth - w - 8) + "px";
  t.style.top = y + 14 + "px";
}
export function hideTip() { if (el) el.style.opacity = "0"; }
