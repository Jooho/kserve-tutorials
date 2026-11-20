// ⧉ An extra terminal for one tutorial, alone in its own browser tab.
"use strict";

const tid = decodeURIComponent(location.pathname.split("/").pop());
const fs = (() => { try { return +localStorage.getItem("tut.fs") || 14; } catch { return 14; } })();
document.title = `shell · ${tid}`;
document.getElementById("who").textContent = `shell · ${tid}`;

const term = new Terminal({
  fontFamily: "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace", fontSize: Math.max(10, fs - 1),
  cursorBlink: true, scrollback: 10000, theme: { background: "#0f1218", foreground: "#dfe3ea" },
});
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
