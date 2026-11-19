"""`./tut ui`: a local web UI that runs tutorials in a real shell on this machine.

Security: the server listens on 127.0.0.1 only and every request must carry the
random token printed at start-up (it is stored in a cookie after the first
visit). Anyone with the token can run commands as you, so do not share it.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import time
import secrets
import shutil
import webbrowser
from pathlib import Path

import markdown as md
from aiohttp import WSMsgType, web

from .. import lint as tlint
from .. import markdown as tmd
from ..model import REPO_ROOT, load_tutorials, version_key
from .session import ShellSession

STATIC = Path(__file__).parent / "static"
SCRIPT_REF_RE = re.compile(r"(?:\$\{?TUT_LIB\}?|\blib)/([a-z0-9-]+/v[0-9]+)/([A-Za-z0-9_.-]+)")
SERVE_DIRS = ("tutorials", "envs", "lib")


class UI:
    def __init__(self, root: Path = REPO_ROOT):
        self.root = root
        self.token = secrets.token_urlsafe(18)
        self.sessions: dict[str, ShellSession] = {}
        self.clients: dict[str, set[web.WebSocketResponse]] = {}
        self.block_states: dict[str, dict[int, dict]] = {}

    # ------------------------------------------------------------- helpers
    def tutorials(self):
        return {t.id: t for t in load_tutorials(self.root) if not t.errors}

    def tutorial_or_404(self, tid: str):
        t = self.tutorials().get(tid)
        if not t:
            raise web.HTTPNotFound(text=f"unknown tutorial {tid}")
        return t

    def broadcast(self, tid: str, msg: dict):
        if msg.get("type") == "block":
            msg = {**msg, "ts": time.time()}
            self.block_states.setdefault(tid, {})[msg["idx"]] = msg
        data = json.dumps(msg)
        for ws in list(self.clients.get(tid, ())):
            if not ws.closed:
                asyncio.ensure_future(ws.send_str(data))

    def doc_blocks(self, tid: str, lang: str):
        t = self.tutorial_or_404(tid)
        path = t.readme(lang) if t.readme(lang).exists() else t.readme("en")
        text = path.read_text()
        return t, path, text, tmd.parse(text)

    # ----------------------------------------------------------- middleware
    @web.middleware
    async def auth(self, request: web.Request, handler):
        tok = request.query.get("token") or request.cookies.get("tut_token") \
            or request.headers.get("X-Tut-Token")
        if not secrets.compare_digest(tok or "", self.token):
            raise web.HTTPForbidden(text="missing or wrong token — use the URL printed by ./tut ui")
        resp = await handler(request)
        if request.query.get("token") and isinstance(resp, web.StreamResponse) and not resp.prepared:
            resp.set_cookie("tut_token", self.token, httponly=True, samesite="Strict")
        return resp

    # --------------------------------------------------------------- routes
    async def index(self, request):
        resp = web.FileResponse(STATIC / "index.html")
        if request.query.get("token"):
            resp.set_cookie("tut_token", self.token, httponly=True, samesite="Strict")
        return resp

    async def api_tutorials(self, request):
        out = []
        for t in self.tutorials().values():
            out.append({
                "id": t.id, "title": {l: t.title(l) for l in ("en", "ko")},
                "summary": {l: t.summary(l) for l in ("en", "ko")},
                "status": t.status, "env": t.env_ref, "uses": t.uses,
                "kserve": {"default": t.kserve_default, "tested": t.kserve_tested},
                "tags": t.meta.get("tags", []) or [], "gpu": t.needs_gpu, "langs": t.langs,
                "replacement": (t.meta.get("deprecation") or {}).get("replacement"),
            })
        versions = sorted({v for t in out for v in t["kserve"]["tested"]}, key=version_key,
                          reverse=True)
        return web.json_response({"tutorials": out, "versions": versions})

    async def api_catalog(self, request):
        """Collections resolved for a KServe version, uncollected tutorials, tags."""
        from .. import catalog
        version = request.query.get("version") or None
        tutorials = list(self.tutorials().values())
        by_id = {t.id: t for t in tutorials}
        cols = [{"id": c.id, "title": {l: c.text("title", l) for l in ("en", "ko")},
                 "description": {l: c.text("description", l) for l in ("en", "ko")},
                 "owners": c.owners, "items": catalog.resolve(c, by_id, version)}
                for c in catalog.load_collections(self.root)]
        reg = catalog.load_tags(self.root)
        return web.json_response({
            "version": version, "collections": cols,
            "other": [t.id for t in catalog.uncollected(tutorials, catalog.load_collections(self.root))],
            "tags": reg.get("tags") or {}, "groups": reg.get("groups") or {},
        })

    async def api_tutorial(self, request):
        tid = request.match_info["tid"]
        lang = request.query.get("lang", "en")
        t, path, text, doc = self.doc_blocks(tid, lang)
        lines = text.split("\n")
        blocks = []
        # Replace each fenced block with a placeholder the front end hydrates.
        for i, b in reversed(list(enumerate(doc.blocks))):
            lines[b.line - 1:b.end] = ["", f'<div class="tut-block" data-idx="{i}"></div>', ""]
        for i, b in enumerate(doc.blocks):
            scripts = []
            if b.is_shell:
                for ref, name in sorted(set(SCRIPT_REF_RE.findall(b.code))):
                    p = self.root / "lib" / ref / name
                    scripts.append({"path": f"lib/{ref}/{name}",
                                    "content": p.read_text() if p.is_file() else None})
            blocks.append({"idx": i, "lang": b.lang, "role": b.role, "attrs": b.attrs,
                           "code": b.code, "line": b.line, "region": b.in_region,
                           "scripts": scripts})
        body = "\n".join(lines)
        body = re.sub(r"<details>", '<details markdown="1">', body)
        html = md.markdown(body, extensions=["tables", "md_in_html", "sane_lists"])
        base = f"/files/tutorials/{tid}/"
        html = re.sub(r'(src|href)="(?!https?:|#|/|mailto:)([^"]+)"',
                      lambda m: f'{m.group(1)}="{base}{m.group(2)}"', html)
        return web.json_response({
            "id": tid, "lang": lang if t.readme(lang).exists() else "en",
            "translation": None if lang == "en" else tlint.translation_state(t, lang),
            "file": str(path.relative_to(self.root)), "html": html, "blocks": blocks,
            "states": self.block_states.get(tid, {}),
            "session": {"alive": tid in self.sessions and self.sessions[tid].alive,
                        "kserve_version": self.sessions[tid].kserve_version
                        if tid in self.sessions else None},
        })

    async def api_env(self, request):
        t = self.tutorial_or_404(request.match_info["tid"])
        cluster = os.environ.get("KIND_CLUSTER_NAME", "kind")
        res = {"env": t.env_ref, "kind": bool(shutil.which("kind")),
               "kubectl": bool(shutil.which("kubectl")), "docker": bool(shutil.which("docker")),
               "cluster": None, "built_as": None}
        if res["kind"]:
            out = await _cmd("kind", "get", "clusters")
            res["cluster"] = cluster if cluster in out.split() else None
        if res["cluster"] and res["kubectl"]:
            res["built_as"] = (await _cmd(
                "kubectl", "--context", f"kind-{cluster}", "-n", "kube-system", "get",
                "configmap", "tut-env", "-o",
                "jsonpath={.data.profile}@{.data.kserve_version}")).strip() or None
        return web.json_response(res)

    async def files(self, request):
        rel = Path(request.match_info["path"])
        if not rel.parts or rel.parts[0] not in SERVE_DIRS or ".." in rel.parts:
            raise web.HTTPForbidden()
        p = (self.root / rel).resolve()
        if not p.is_file() or not p.is_relative_to(self.root.resolve()):
            raise web.HTTPNotFound()
        return web.FileResponse(p)

    async def ws(self, request):
        tid = request.match_info["tid"]
        self.tutorial_or_404(tid)
        ws = web.WebSocketResponse(heartbeat=30)
        await ws.prepare(request)
        self.clients.setdefault(tid, set()).add(ws)
        sess = self.sessions.get(tid)
        if sess and sess.alive:
            await ws.send_str(json.dumps({"type": "output", "data": "".join(sess.scrollback)}))
            await ws.send_str(json.dumps({"type": "session", "state": "started",
                                          "kserve_version": sess.kserve_version}))
        try:
            async for msg in ws:
                if msg.type != WSMsgType.TEXT:
                    continue
                m = json.loads(msg.data)
                sess = self.sessions.get(tid)
                kind = m.get("type")
                if kind == "start" or (kind == "restart"):
                    version = m.get("kserve_version") or None
                    if sess:
                        sess.stop()
                    self.block_states[tid] = {}
                    sess = self.start_session(tid, version)
                    if m.get("cols"):
                        sess.resize(m["cols"], m["rows"])
                    continue
                if not sess or not sess.alive:
                    await ws.send_str(json.dumps({"type": "session", "state": "stopped"}))
                    continue
                if kind == "input":
                    sess.write(m["data"])
                elif kind == "resize":
                    sess.resize(int(m["cols"]), int(m["rows"]))
                elif kind == "run":
                    _, path, _, doc = self.doc_blocks(tid, m.get("lang", "en"))
                    blocks = [{"idx": i, "role": doc.blocks[i].role, "code": doc.blocks[i].code,
                               "attrs": doc.blocks[i].attrs,
                               "label": f"{doc.blocks[i].role} · {path.name}:{doc.blocks[i].line}"}
                              for i in m["blocks"]
                              if 0 <= i < len(doc.blocks) and doc.blocks[i].is_shell
                              and doc.blocks[i].role in ("run", "verify", "cleanup", "skip")]
                    sess.run_queue(blocks, stop_on_fail=m.get("stop_on_fail", True))
                elif kind == "interrupt":
                    sess.interrupt()
        finally:
            self.clients.get(tid, set()).discard(ws)
        return ws

    def start_session(self, tid: str, version: str | None) -> ShellSession:
        sess = ShellSession(
            tid, self.root, version,
            on_output=lambda data: self.broadcast(tid, {"type": "output", "data": data}),
            on_event=lambda ev: self.broadcast(tid, ev))
        self.sessions[tid] = sess
        sess.start()
        return sess

    async def on_shutdown(self, app):
        for s in self.sessions.values():
            s.stop()

    def app(self) -> web.Application:
        app = web.Application(middlewares=[self.auth])
        app.add_routes([
            web.get("/", self.index),
            web.get("/api/tutorials", self.api_tutorials),
            web.get("/api/catalog", self.api_catalog),
            web.get("/api/tutorials/{tid}", self.api_tutorial),
            web.get("/api/tutorials/{tid}/env", self.api_env),
            web.get("/ws/{tid}", self.ws),
            web.get("/files/{path:.+}", self.files),
            web.static("/static", STATIC),
        ])
        app.on_shutdown.append(self.on_shutdown)
        return app


async def _cmd(*args: str, timeout: float = 10) -> str:
    try:
        p = await asyncio.create_subprocess_exec(*args, stdout=asyncio.subprocess.PIPE,
                                                 stderr=asyncio.subprocess.DEVNULL)
        out, _ = await asyncio.wait_for(p.communicate(), timeout)
        return out.decode()
    except (asyncio.TimeoutError, OSError):
        return ""


def serve(port: int = 8080, open_browser: bool = True, root: Path = REPO_ROOT):
    ui = UI(root)
    url = f"http://127.0.0.1:{port}/?token={ui.token}"
    print(f"KServe tutorials UI: {url}\n(commands run on this machine as you; Ctrl+C to stop)",
          flush=True)
    if open_browser:
        webbrowser.open(url)
    web.run_app(ui.app(), host="127.0.0.1", port=port, print=None)
