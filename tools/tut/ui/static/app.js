// KServe tutorials — local runner UI.
"use strict";

const $ = (s) => document.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const store = {
  get(k, d) { try { return localStorage.getItem(k) ?? d; } catch { return d; } },
  set(k, v) { try { localStorage.setItem(k, v); } catch {} },
};

const S = {
  tutorials: [], versions: [], current: null, doc: null, ws: null,
  states: {}, lang: store.get("tut.lang", "en"), version: store.get("tut.version", ""),
  sessionVersion: null,
};

// ------------------------------------------------------------- terminal
const term = new Terminal({
  fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Consolas, monospace', fontSize: 13,
  cursorBlink: true, scrollback: 5000, convertEol: false,
  theme: { background: "#0f1218", foreground: "#dfe3ea" },
});
const fit = new FitAddon.FitAddon();
term.loadAddon(fit);
term.open($("#term"));
const refit = () => {
  try { fit.fit(); } catch {}
  send({ type: "resize", cols: term.cols, rows: term.rows });
};
new ResizeObserver(refit).observe($("#term"));
term.onData((data) => send({ type: "input", data }));

function send(msg) {
  if (S.ws && S.ws.readyState === WebSocket.OPEN) S.ws.send(JSON.stringify(msg));
}

// ------------------------------------------------------------- sidebar
async function loadList() {
  const r = await fetch("/api/tutorials").then((r) => r.json());
  S.tutorials = r.tutorials; S.versions = r.versions;
  const sel = $("#version");
  sel.innerHTML = `<option value="">Tutorial default</option>` +
    S.versions.map((v) => `<option value="${v}">${v}</option>`).join("");
  sel.value = S.versions.includes(S.version) ? S.version : "";
  if (!S.versions.includes(S.version)) S.version = "";
  await loadCatalog();
  const want = location.hash.slice(1) || store.get("tut.current", "");
  if (S.tutorials.some((t) => t.id === want)) openTutorial(want);
}

// ------------------------------------------------------------- catalog views
// Collections are resolved on the server for the selected KServe version
// (tools/tut/catalog.py); this code only displays them.
Object.assign(S, { view: store.get("tut.view", "collections"), sort: store.get("tut.sort", "title"),
                   tagFilter: new Set(), catalog: null, collapsed: new Set(JSON.parse(store.get("tut.collapsed", "[]"))) });

async function loadCatalog() {
  S.catalog = await fetch(`/api/catalog?version=${encodeURIComponent(S.version)}`).then((r) => r.json());
  const groups = S.catalog.groups;
  const byGroup = {};
  for (const [name, t] of Object.entries(S.catalog.tags)) (byGroup[t.group] ||= []).push(name);
  $("#addtag").innerHTML = `<option value="">＋ tag</option>` + Object.entries(byGroup).map(([g, names]) =>
    `<optgroup label="${esc(groups[g] || g)}">${names.sort().map((n) =>
      `<option value="${n}">${n}</option>`).join("")}</optgroup>`).join("");
  renderList();
}

const byId = (id) => S.tutorials.find((t) => t.id === id);
const vkey = (v) => v.replace(/^v/, "").split(".").map(Number);
const vcmp = (a, b) => { const x = vkey(a), y = vkey(b); for (let i = 0; i < 3; i++) if (x[i] !== y[i]) return x[i] - y[i]; return 0; };

function matches(t) {
  const q = $("#search").value.toLowerCase().trim();
  const hay = [t.id, t.title.en, t.title.ko, t.summary.en, t.summary.ko, ...t.tags].join(" ").toLowerCase();
  if (q && !q.split(/\s+/).every((w) => hay.includes(w))) return false;
  for (const tag of S.tagFilter) if (!t.tags.includes(tag)) return false;
  return true;
}

function item(t, { n = null, note = "", dim = false, extra = "" } = {}) {
  const title = esc(t.title[S.lang] || t.title.en);
  const tags = t.tags.map((x) => `<span class="tag ${S.tagFilter.has(x) ? "on" : ""}" data-tag="${x}"
    title="${esc(S.catalog?.tags[x]?.description || "")}">#${x}</span>`).join("");
  return `<li data-id="${t.id}" class="${t.id === S.current ? "on" : ""} ${dim ? "untested" : ""} ${extra}">
    <div class="t">${n ? `<span class="num">${n}</span>` : ""}${title}</div>
    <div class="meta"><span>${statusLabel(t.status)}</span><span>${t.kserve.tested.join(", ")}</span>
      ${t.gpu ? "<span>GPU</span>" : ""}${note ? `<span class="note">${note}</span>` : ""}</div>
    ${tags ? `<div class="tags">${tags}</div>` : ""}</li>`;
}

function renderList() {
  document.querySelectorAll("#views button").forEach((b) => b.classList.toggle("on", b.dataset.view === S.view));
  $("#sort").hidden = S.view !== "all";
  $("#sort").value = S.sort;
  $("#tagchips").innerHTML = [...S.tagFilter].map((x) =>
    `<span class="tag on" data-untag="${x}" title="Remove filter">#${x} ✕</span>`).join("");
  const v = S.version, html = [];
  if (!S.catalog) return;
  if (S.view === "collections") {
    const group = (id, title, desc, rows) => {
      const shown = rows.filter((r) => r.html);
      if (!shown.length) return;
      const closed = S.collapsed.has(id);
      html.push(`<li class="group" data-group="${id}" title="${esc(desc)}">${closed ? "▸" : "▾"} ${esc(title)}
        <span class="count">${shown.length}</span></li>`);
      if (!closed) shown.forEach((r) => html.push(r.html));
    };
    for (const c of S.catalog.collections) {
      group(c.id, c.title[S.lang] || c.title.en, c.description[S.lang] || c.description.en,
        c.items.filter((r) => r.state !== "missing").map((r) => {
          const t = byId(r.shown); if (!t || !matches(t)) return {};
          const note = { unavailable: `not on ${v}`, replaced: `replaces ${r.member}`, archived: "archived" }[r.state] || "";
          return { html: item(t, { n: r.n, note, dim: r.state === "unavailable" || r.state === "archived" }) };
        }));
    }
    group("_other", S.lang === "ko" ? "기타" : "Other tutorials", "Not in any collection",
      S.catalog.other.map(byId).filter((t) => t && matches(t)).map((t) =>
        ({ html: item(t, { dim: v && !t.kserve.tested.includes(v), note: v && !t.kserve.tested.includes(v) ? `not on ${v}` : "" }) })));
  } else if (S.view === "all") {
    const order = { stable: 0, deprecated: 1, draft: 2, archived: 3 };
    const ts = S.tutorials.filter(matches).sort((a, b) =>
      S.sort === "status" ? (order[a.status] - order[b.status]) || a.title.en.localeCompare(b.title.en)
      : S.sort === "kserve" ? vcmp(b.kserve.tested.slice().sort(vcmp).at(-1) || "v0.0.0", a.kserve.tested.slice().sort(vcmp).at(-1) || "v0.0.0")
      : (a.title[S.lang] || a.title.en).localeCompare(b.title[S.lang] || b.title.en));
    ts.forEach((t) => html.push(item(t, { dim: v && !t.kserve.tested.includes(v), note: v && !t.kserve.tested.includes(v) ? `not on ${v}` : "" })));
  } else {
    html.push(`<li class="group" data-matrix="1">▦ ${S.lang === "ko" ? "버전 매트릭스 보기" : "Open the version matrix"}</li>`);
    for (const ver of S.versions) {
      if (v && ver !== v) continue;
      const ts = S.tutorials.filter((t) => t.status !== "archived" && t.kserve.tested.includes(ver) && matches(t));
      if (!ts.length) continue;
      html.push(`<li class="group" data-group="v:${ver}">KServe ${ver}<span class="count">${ts.length}</span></li>`);
      ts.forEach((t) => html.push(item(t)));
    }
  }
  $("#list").innerHTML = html.join("") || `<li class="muted">No tutorials match.</li>`;
}

function renderMatrix() {
  const vs = S.versions;
  const rows = S.tutorials.filter(matches).map((t) => `<tr data-id="${t.id}" class="${t.status === "archived" ? "archived" : ""}">
    <td>${esc(t.title[S.lang] || t.title.en)} <span class="muted">${statusLabel(t.status)}</span></td>
    ${vs.map((ver) => t.kserve.tested.includes(ver)
      ? `<td class="yes ${ver === t.kserve.default ? "default" : ""}" title="${ver === t.kserve.default ? "default version" : "tested"}">✓</td>`
      : "<td></td>").join("")}</tr>`).join("");
  $("#matrix").innerHTML = `<h2>${S.lang === "ko" ? "KServe 버전별 튜토리얼" : "Tutorials by KServe version"}</h2>
    <p class="muted">✓ = run and verified in CI on that version; outlined = the tutorial's default version.</p>
    <table><thead><tr><th>Tutorial</th>${vs.map((v) => `<th>${v}</th>`).join("")}</tr></thead><tbody>${rows}</tbody></table>`;
  $("#matrix").hidden = false; $("#doc-wrap").hidden = true; $("#empty").hidden = true;
}
$("#matrix").addEventListener("click", (e) => { const tr = e.target.closest("tr[data-id]"); if (tr) openTutorial(tr.dataset.id); });

const statusLabel = (s) => ({ draft: "🚧 draft", stable: "✅ stable", deprecated: "⚠️ deprecated", archived: "🗄️ archived" }[s] || s);

$("#list").addEventListener("click", (e) => {
  const tag = e.target.closest("[data-tag]");
  if (tag) { e.stopPropagation(); S.tagFilter.add(tag.dataset.tag); renderList(); return; }
  if (e.target.closest("[data-matrix]")) { renderMatrix(); return; }
  const g = e.target.closest("li.group[data-group]");
  if (g && S.view === "collections") {
    const id = g.dataset.group;
    S.collapsed.has(id) ? S.collapsed.delete(id) : S.collapsed.add(id);
    store.set("tut.collapsed", JSON.stringify([...S.collapsed])); renderList(); return;
  }
  const li = e.target.closest("li[data-id]");
  if (li) openTutorial(li.dataset.id);
});
$("#tagchips").addEventListener("click", (e) => {
  const t = e.target.closest("[data-untag]"); if (t) { S.tagFilter.delete(t.dataset.untag); renderList(); }
});
$("#addtag").addEventListener("change", (e) => { if (e.target.value) S.tagFilter.add(e.target.value); e.target.value = ""; renderList(); });
$("#sort").addEventListener("change", (e) => { S.sort = e.target.value; store.set("tut.sort", S.sort); renderList(); });
$("#views").addEventListener("click", (e) => {
  const b = e.target.closest("button[data-view]"); if (!b) return;
  S.view = b.dataset.view; store.set("tut.view", S.view); renderList();
});
$("#search").addEventListener("input", () => { renderList(); if (!$("#matrix").hidden) renderMatrix(); });
$("#version").addEventListener("change", (e) => {
  S.version = e.target.value; store.set("tut.version", S.version);
  loadCatalog();
  if (S.current) {
    renderChips();
    const want = sessionVersionFor(currentMeta());
    if (want !== S.sessionVersion &&
        confirm(`Start a new shell with KServe ${want}? Variables in the current shell are lost.`)) {
      startShell();
    }
  }
});
$("#lang").addEventListener("click", (e) => {
  const b = e.target.closest("button"); if (!b) return;
  S.lang = b.dataset.lang; store.set("tut.lang", S.lang);
  document.querySelectorAll("#lang button").forEach((x) => x.classList.toggle("on", x === b));
  renderList();
  if (S.current) loadDoc();
});
document.querySelectorAll("#lang button").forEach((x) => x.classList.toggle("on", x.dataset.lang === S.lang));

const currentMeta = () => S.tutorials.find((t) => t.id === S.current);
function sessionVersionFor(t) {
  return S.version && t.kserve.tested.includes(S.version) ? S.version : t.kserve.default;
}

// ------------------------------------------------------------- document
async function openTutorial(id) {
  S.current = id; store.set("tut.current", id); history.replaceState(null, "", "#" + id);
  renderList();
  $("#empty").hidden = true; $("#matrix").hidden = true; $("#doc-wrap").hidden = false;
  await loadDoc();
  connect();
  loadEnv();
}

async function loadDoc() {
  const d = await fetch(`/api/tutorials/${S.current}?lang=${S.lang}`).then((r) => r.json());
  S.doc = d; S.states = {}; S.times = {};
  for (const [k, v] of Object.entries(d.states || {})) { S.states[k] = v.state; S.times[k] = v.ts; }
  const t = currentMeta();
  $("#doc-title").textContent = t.title[S.lang] || t.title.en;
  renderChips();
  $("#doc").innerHTML = d.html;
  for (const el of document.querySelectorAll(".tut-block")) {
    const b = d.blocks[+el.dataset.idx];
    el.replaceWith(renderBlock(b));
  }
  updateProgress();
  select(firstPending(), false);
}

function renderChips() {
  const t = currentMeta(); if (!t) return;
  const v = sessionVersionFor(t);
  const untested = S.version && !t.kserve.tested.includes(S.version);
  $("#chips").innerHTML = [
    `<span class="chip">${statusLabel(t.status)}</span>`,
    `<span class="chip">KServe ${v}</span>`,
    untested ? `<span class="chip warn">not tested on ${S.version} — using ${v}</span>` : "",
    t.env ? `<span class="chip">env ${t.env}</span>` : "",
    ...t.uses.map((u) => `<span class="chip">lib ${u}</span>`),
    S.doc && S.doc.lang !== S.lang ? `<span class="chip warn">no ${S.lang.toUpperCase()} translation</span>` : "",
  ].join("");
}

const RUNNABLE = new Set(["run", "verify"]);

function renderBlock(b) {
  if (!b.role) {
    const pre = document.createElement("pre");
    pre.className = "static"; pre.innerHTML = `<code>${esc(b.code)}</code>`;
    return pre;
  }
  const role = b.region === "setup" ? "setup" : b.role;
  const el = document.createElement("div");
  el.className = `block role-${role}`; el.dataset.idx = b.idx;
  const attrs = Object.entries(b.attrs).map(([k, v]) => `${k}=${v}`).join(" ");
  const label = { setup: "setup", run: "run", verify: "verify", cleanup: "cleanup", skip: "optional" }[role];
  el.innerHTML = `
    <div class="block-head">
      <span class="badge">${label}</span>
      <span class="loc mono">${esc(S.doc.file)}:${b.line}</span>
      ${attrs ? `<span class="attrs mono">${esc(attrs)}</span>` : ""}
      <span class="head-actions">
        <span class="state"></span>
        ${RUNNABLE.has(b.role) ? `<button class="btn" data-act="to-here" title="Run the steps that have not passed yet, up to this one">⏭ To here</button>` : ""}
        <button class="btn" data-act="run" title="Run this block in the terminal">▶ Run</button>
      </span>
    </div>
    <pre><code>${esc(b.code)}</code></pre>
    ${b.scripts.map((s) => `<details class="scripts"><summary>uses <span class="mono">${esc(s.path)}</span></summary>
      <pre><code>${esc(s.content ?? "(file not found)")}</code></pre></details>`).join("")}`;
  el.addEventListener("click", (e) => {
    const act = e.target.closest("button")?.dataset.act;
    if (!act && !e.target.closest("pre, summary, a")) { select(b.idx); return; }   // Jupyter-style select
    if (act === "run") {
      if (b.attrs.once && S.states[b.idx] === "passed" &&
          !confirm("This step is marked `once`: it is not meant to run twice. Run it again anyway?")) return;
      run([b.idx], false);
    }
    if (act === "to-here") run(pendingSteps(b.idx));
  });
  paint(el, S.states[b.idx]);
  return el;
}

// Steps from the first one that has not passed in this shell, up to `last`
// (a new shell starts with nothing passed, so this then means "from the top").
function pendingSteps(last = Infinity) {
  const steps = S.doc.blocks.filter((x) => RUNNABLE.has(x.role) && x.idx <= last);
  const first = steps.findIndex((x) => S.states[x.idx] !== "passed");
  if (first === -1) return Number.isFinite(last) ? [last] : [];
  return steps.slice(first).map((x) => x.idx);
}

function ago(ts) {
  if (!ts) return "";
  const s = Math.max(0, Math.round(Date.now() / 1000 - ts));
  return s < 60 ? "just now" : s < 3600 ? `${Math.round(s / 60)} min ago` : `${Math.round(s / 3600)} h ago`;
}

function paint(el, state) {
  const idx = +el.dataset.idx;
  el.classList.remove("st-running", "st-failed", "st-passed", "st-stopped");
  if (state) el.classList.add("st-" + state);
  const s = el.querySelector(".state");
  s.className = "state " + (state || "");
  const when = ["passed", "failed", "stopped"].includes(state) && S.times?.[idx] ? ` · ${ago(S.times[idx])}` : "";
  s.innerHTML = ({ running: `<span class="spinner"></span> running`, queued: "queued", passed: "✓ passed",
                   failed: "✗ failed", stopped: "■ stopped" }[state] || "") + when;
  const btn = el.querySelector('button[data-act="run"]');
  if (btn) btn.textContent = ["passed", "failed", "stopped"].includes(state) ? "↻ Run again" : "▶ Run";
}
setInterval(() => document.querySelectorAll(".block").forEach((el) => {
  const st = S.states[+el.dataset.idx];
  if (["passed", "failed", "stopped"].includes(st)) paint(el, st);
}), 30000);

// ---------------------------------------------------------- Next (Jupyter-style)
// One step is selected. Next / Shift+Enter runs it; when it passes, the
// selection moves to the following run/verify step. Clicking a step selects it.
function firstPending() {
  const p = pendingSteps();
  return p.length ? p[0] : null;
}
function select(idx, scroll = true) {
  S.selected = idx;
  document.querySelectorAll(".block.selected").forEach((el) => el.classList.remove("selected"));
  const el = idx == null ? null : document.querySelector(`.block[data-idx="${idx}"]`);
  if (el) {
    el.classList.add("selected");
    if (scroll) el.scrollIntoView({ block: "center", behavior: "smooth" });
  }
}
function nextAfter(idx) {
  const n = S.doc.blocks.find((x) => RUNNABLE.has(x.role) && x.idx > idx);
  return n ? n.idx : null;
}
function runSelected() {
  if (!S.doc) return;
  if (S.selected == null) select(firstPending());
  const b = S.doc.blocks[S.selected];
  if (!b) { alert("Every step has passed in this shell. Use ⏩ Run all to start over."); return; }
  if (b.attrs.once && S.states[b.idx] === "passed" &&
      !confirm("This step is marked `once`: it is not meant to run twice. Run it again anyway?")) return;
  S.advanceFrom = b.idx;
  run([b.idx], false, false);
}
$("#next").onclick = runSelected;
addEventListener("keydown", (e) => {
  if (!(e.key === "Enter" && e.shiftKey)) return;
  if (e.target.closest?.(".xterm, input, select, textarea")) return;   // typing in the terminal or a field
  e.preventDefault();
  runSelected();
});

function setState(idx, state, ts) {
  S.states[idx] = state;
  if (ts) (S.times ||= {})[idx] = ts;
  if (state === "passed" && S.advanceFrom === idx) { S.advanceFrom = null; select(nextAfter(idx)); }
  const el = document.querySelector(`.block[data-idx="${idx}"]`);
  if (el) {
    paint(el, state);
    if (state === "running" || state === "failed") el.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }
  updateProgress();
}

function updateProgress() {
  if (!S.doc) return;
  const steps = S.doc.blocks.filter((b) => RUNNABLE.has(b.role));
  const ok = steps.filter((b) => S.states[b.idx] === "passed").length;
  const bad = steps.filter((b) => S.states[b.idx] === "failed").length;
  $("#progress").textContent = `${ok}/${steps.length} passed${bad ? ` · ${bad} failed` : ""}`;
}

function run(idxs, stopOnFail = true, focusTerminal = true) {
  if (!idxs.length) return;
  send({ type: "run", blocks: idxs, lang: S.doc.lang, stop_on_fail: stopOnFail });
  if (focusTerminal) term.focus();
  else if (document.activeElement?.closest?.(".xterm")) document.activeElement.blur();   // keep Shift+Enter for Next
}

$("#continue").onclick = () => {
  const todo = pendingSteps();
  if (!todo.length) { alert("Every step has passed in this shell. Use ▶ Run all to start over."); return; }
  run(todo);
};
$("#run-all").onclick = () => run(S.doc.blocks.filter((b) => RUNNABLE.has(b.role)).map((b) => b.idx));
$("#cleanup").onclick = () => run(S.doc.blocks.filter((b) => b.role === "cleanup").map((b) => b.idx), false);
$("#stop").onclick = () => send({ type: "interrupt" });
$("#restart").onclick = () => { if (confirm("Start a new shell? Variables in the current shell are lost.")) startShell(); };

// ------------------------------------------------------------- environment
async function loadEnv() {
  const t = currentMeta();
  const e = await fetch(`/api/tutorials/${S.current}/env`).then((r) => r.json());
  const want = `${t.env}@${sessionVersionFor(t)}`;
  const bar = $("#envbar");
  let cls = "warn", msg;
  if (!e.docker || !e.kubectl) msg = `Missing tools: ${["docker", "kubectl"].filter((x) => !e[x]).join(", ")}. Install them before running.`;
  else if (!e.cluster) msg = `No Kind cluster yet. The <b>setup</b> step creates <span class="mono">${esc(t.env)}</span> with KServe ${sessionVersionFor(t)} (takes several minutes).`;
  else if (e.built_as === want) { cls = "ok"; msg = `Kind cluster ready: <span class="mono">${esc(e.built_as)}</span>. The setup step will reuse it.`; }
  else msg = `A Kind cluster exists but was built as <span class="mono">${esc(e.built_as || "unknown")}</span>, not <span class="mono">${esc(want)}</span>. Setup will stop; delete it with <span class="mono">envs/${esc(t.env)}/teardown.sh</span> or set TUT_ENV_RECREATE=1.`;
  bar.className = "envbar " + cls; bar.innerHTML = msg;
}

// ------------------------------------------------------------- websocket
function connect() {
  if (S.ws) { S.ws.onclose = null; S.ws.close(); }
  term.reset();
  const ws = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws/${S.current}`);
  S.ws = ws;
  let started = false;
  ws.onopen = () => setTimeout(() => { if (!started) startShell(); }, 150);
  ws.onmessage = (ev) => {
    const m = JSON.parse(ev.data);
    if (m.type === "output") term.write(m.data);
    else if (m.type === "block") setState(m.idx, m.state === "idle" ? null : m.state, m.ts);
    else if (m.type === "session") {
      if (m.state === "started") {
        started = true; S.sessionVersion = m.kserve_version;
        $("#term-title").textContent = `Terminal — ${S.current} · KServe ${m.kserve_version || "default"}`;
        refit();
      } else if (m.state === "exited" || m.state === "stopped") {
        $("#term-title").textContent = "Terminal — shell exited (↻ New shell)";
      }
    } else if (m.type === "queue" && m.state === "cancelled") {
      for (const [k, v] of Object.entries(S.states)) if (v === "queued") setState(k, null);
    }
  };
  ws.onclose = () => { $("#term-title").textContent = "Terminal — disconnected (reload the page)"; };
}

function startShell() {
  const t = currentMeta();
  S.states = {};
  document.querySelectorAll(".block").forEach((el) => paint(el, null));
  updateProgress();
  select(firstPending(), false);
  term.reset();
  send({ type: "start", kserve_version: sessionVersionFor(t), cols: term.cols, rows: term.rows });
  loadEnv();
}

// ------------------------------------------------------------- layout & text size
// Remembered per browser (localStorage); the page works without it.
const VIEW = {
  fs: +store.get("tut.fs", 14), pos: store.get("tut.termpos", "bottom"),
  sidebar: store.get("tut.sidebar", "shown"),
  termH: store.get("tut.termH", ""), termW: store.get("tut.termW", ""),
};
function applyView() {
  const main = $(".main");
  document.documentElement.style.setProperty("--fs", VIEW.fs + "px");
  $("#fs-val").textContent = VIEW.fs + "px";
  term.options.fontSize = Math.max(10, VIEW.fs - 1);
  document.body.classList.toggle("term-right", VIEW.pos === "right");
  document.body.classList.toggle("sidebar-hidden", VIEW.sidebar === "hidden");
  document.querySelectorAll("#termpos button").forEach((b) => b.classList.toggle("on", b.dataset.pos === VIEW.pos));
  if (VIEW.termH) main.style.setProperty("--term-h", VIEW.termH);
  if (VIEW.termW) main.style.setProperty("--term-w", VIEW.termW);
  requestAnimationFrame(refit);
}
$("#fontsize").addEventListener("click", (e) => {
  const d = +(e.target.closest("button")?.dataset.d || 0); if (!d) return;
  VIEW.fs = Math.min(24, Math.max(11, VIEW.fs + d)); store.set("tut.fs", VIEW.fs); applyView();
});
$("#termpos").addEventListener("click", (e) => {
  const pos = e.target.closest("button")?.dataset.pos; if (!pos) return;
  VIEW.pos = pos; store.set("tut.termpos", pos); applyView();
});
$("#toggle-sidebar").onclick = () => {
  VIEW.sidebar = VIEW.sidebar === "hidden" ? "shown" : "hidden"; store.set("tut.sidebar", VIEW.sidebar); applyView();
};
(() => {   // splitter: drag to resize the terminal (height at the bottom, width on the right)
  const main = $(".main"); let drag = false;
  $("#splitter").addEventListener("mousedown", () => { drag = true; document.body.style.userSelect = "none"; });
  addEventListener("mouseup", () => {
    if (!drag) return;
    drag = false; document.body.style.userSelect = "";
    store.set("tut.termH", VIEW.termH); store.set("tut.termW", VIEW.termW);
  });
  addEventListener("mousemove", (e) => {
    if (!drag) return;
    const r = main.getBoundingClientRect();
    if (VIEW.pos === "right") {
      VIEW.termW = Math.min(Math.max(r.right - e.clientX, 260), r.width - 320) + "px";
      main.style.setProperty("--term-w", VIEW.termW);
    } else {
      VIEW.termH = Math.min(Math.max(r.bottom - e.clientY, 120), r.height - 160) + "px";
      main.style.setProperty("--term-h", VIEW.termH);
    }
  });
})();
applyView();

loadList();
