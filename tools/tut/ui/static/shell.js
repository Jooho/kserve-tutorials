// ⧉ An extra terminal for one tutorial, alone in its own browser tab.
"use strict";

const tid = decodeURIComponent(location.pathname.split("/").pop());
TUT_TERM.applyPageTheme();
document.title = `shell · ${tid}`;
document.getElementById("who").textContent = `shell · ${tid}`;

const term = new Terminal({
  fontFamily: "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace", fontSize: TUT_TERM.fontSize(),
  cursorBlink: true, scrollback: 10000, theme: TUT_TERM.theme(),
});
// Theme and terminal text size as in the main page; changes made there (another
// tab, same browser) arrive as "storage" events.
const restyle = () => {
  TUT_TERM.applyPageTheme();
  term.options.theme = TUT_TERM.theme();
  term.options.fontSize = TUT_TERM.fontSize();
  document.getElementById("fs-val").textContent = TUT_TERM.fontSize() + "px";
  try { refit(); } catch {}
};
document.getElementById("fs-val").textContent = TUT_TERM.fontSize() + "px";
document.getElementById("termfs").addEventListener("click", (e) => {
  const d = +(e.target.closest("button")?.dataset.d || 0); if (!d) return;
  TUT_TERM.setFontSize(TUT_TERM.fontSize() + d);
  restyle(); term.focus();
});
addEventListener("storage", (e) => { if (e.key === "tut.theme" || e.key === "tut.termfs") restyle(); });
TUT_TERM.media.addEventListener("change", restyle);
const fit = new FitAddon.FitAddon();
term.loadAddon(fit);
term.open(document.getElementById("term"));

const ws = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws/shell/${encodeURIComponent(tid)}`);
const send = (m) => { if (ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify(m)); };
const refit = () => { try { fit.fit(); } catch {} send({ type: "resize", cols: term.cols, rows: term.rows }); };

ws.onopen = () => { refit(); term.focus(); };
ws.onmessage = (ev) => {
  const m = JSON.parse(ev.data);
  if (m.type === "output") term.write(m.data);
  else if (m.type === "info") {
    document.getElementById("ctx").textContent = m.linked
      ? `variables from the tutorial shell${m.ns ? ` · NS=${m.ns}` : ""}`
      : "the tutorial shell has not started yet — open the tutorial first, then ↻";
  }
};
ws.onclose = () => { document.getElementById("ctx").textContent = "disconnected — reload the page for a new shell"; };
term.onData((data) => send({ type: "input", data }));
new ResizeObserver(refit).observe(document.getElementById("term"));
document.getElementById("reload").onclick = () => { send({ type: "reload" }); term.focus(); };
