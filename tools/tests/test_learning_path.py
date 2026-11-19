"""What the UI shows and runs for a tutorial, standalone vs in a learning path,
checked through the real server API and a real shell (no browser).

Uses the fixture in tools/tests/fixtures/shared-steps/ (three tiny tutorials that
share steps, and a learning path over them), copied into a temporary
repository; the steps only write files under $TMPDIR.
"""
from __future__ import annotations

import asyncio
import shutil
import subprocess
from pathlib import Path

import pytest
from aiohttp.test_utils import TestClient, TestServer

from tut.model import REPO_ROOT
from tut.ui.server import UI
from tut.ui.session import ShellSession

PATH = "poc-shared-steps"
MEMBERS = ["poc-shared-1-deploy", "poc-shared-2-config", "poc-shared-3-scale"]
VARS = {"NS": "poc-path", "MODEL": "path-model"}


FIXTURE = Path(__file__).parent / "fixtures" / "shared-steps"


@pytest.fixture(scope="module")
def root(tmp_path_factory) -> Path:
    """A repository with the real schema, envs and catalog plus the fixture."""
    r = tmp_path_factory.mktemp("repo")
    for d in ("schema", "envs", "lib", "catalog"):
        shutil.copytree(REPO_ROOT / d, r / d)
    for p in (r / "catalog" / "collections").glob("*.yaml"):
        p.unlink()
    (r / "tools").mkdir()
    shutil.copy(REPO_ROOT / "tools" / "local-config.sh", r / "tools" / "local-config.sh")
    shutil.copytree(FIXTURE / "tutorials", r / "tutorials")
    shutil.copytree(FIXTURE / "catalog" / "collections", r / "catalog" / "collections", dirs_exist_ok=True)
    groups = r / "catalog" / "groups.yaml"
    groups.write_text(groups.read_text().rstrip() + "\n  poc:\n    title: {en: PoC}\n")
    (r / ".github").mkdir()
    # Module-scoped, so conftest's per-test isolated git config is not active yet:
    # give git an identity explicitly (CI runners have none).
    git = lambda *a: subprocess.run(["git", "-c", "user.name=tut-tests", "-c", "user.email=tut-tests@example.invalid",
                                     "-c", "commit.gpgsign=false", *a], cwd=r, check=True, capture_output=True)
    git("init", "-q", "-b", "main"); git("add", "."); git("commit", "-qm", "fixture")
    from tut import generate
    generate.sync(r)
    return r


def api(root: Path, tid: str, collection: str | None = None) -> dict:
    async def main():
        ui = UI(root)
        async with TestClient(TestServer(ui.app())) as c:
            q = f"?collection={collection}" if collection else ""
            r = await c.get(f"/api/tutorials/{tid}{q}", headers={"X-Tut-Token": ui.token})
            assert r.status == 200
            return await r.json()
    return asyncio.run(main())


def visible_steps(doc: dict) -> list[dict]:
    """The run/verify blocks the UI runs (same rule as app.js `steps()`)."""
    return [b for b in doc["blocks"] if b["role"] in ("run", "verify")
            and not (b["covered_by"] and b["role"] == "run") and not b["group_skip"]]


def run_in_shell(root: Path, doc: dict, env: dict | None) -> dict[int, str]:
    blocks = [{"idx": b["idx"], "role": b["role"], "code": b["code"], "attrs": b["attrs"]}
              for b in visible_steps(doc)]
    events = []

    async def main():
        s = ShellSession(doc["id"], root, "v0.18.0", lambda _: None, events.append,
                         collection=PATH if env else None, extra_env=env)
        s.start()
        s.run_queue(blocks, stop_on_fail=True)
        try:
            await asyncio.wait_for(s.queue_task, 30)
        finally:
            s.stop()
    asyncio.run(main())
    return {e["idx"]: e["state"] for e in events if e["type"] == "block"}


@pytest.fixture(autouse=True)
def tmp_state(tmp_path, monkeypatch):
    monkeypatch.setenv("TMPDIR", str(tmp_path))      # where the PoC steps write


def test_standalone_shows_and_runs_everything(root, tmp_path):
    d = api(root, "poc-shared-3-scale")
    assert d["group"] is None
    assert not any(b["covered_by"] or b["group_skip"] for b in d["blocks"])
    assert {b["shared"] for b in d["blocks"]} >= {"poc-model", "poc-config"}   # marked, not hidden
    states = run_in_shell(root, d, env=None)
    assert len(states) == 7 and set(states.values()) == {"passed"}


def test_path_hides_covered_runs_and_cleanup_and_shares_vars(root):
    d = api(root, "poc-shared-3-scale", PATH)
    g = d["group"]
    assert (g["n"], g["total"], g["prev"], g["next"], g["vars"]) == (3, 3, "poc-shared-2-config", None, VARS)
    covered = {(b["shared"], b["role"]): b["covered_by"] for b in d["blocks"] if b["covered_by"]}
    assert covered == {("poc-model", "run"): "poc-shared-1-deploy", ("poc-model", "verify"): "poc-shared-1-deploy",
                       ("poc-config", "run"): "poc-shared-2-config", ("poc-config", "verify"): "poc-shared-2-config"}
    assert [b["role"] for b in visible_steps(d)] == ["run", "verify", "verify", "run", "verify"]  # setup, 2 checks, own step
    assert all(b["group_skip"] for b in d["blocks"] if b["role"] == "cleanup")
    first = api(root, "poc-shared-1-deploy", PATH)
    assert first["group"]["n"] == 1 and not any(b["covered_by"] for b in first["blocks"])


def test_unknown_or_unrelated_collection_means_standalone(root):
    assert api(root, "poc-shared-3-scale", "no-such-path")["group"] is None
    assert api(root, "poc-shared-3-scale", "llmisvc-deep-dive")["group"] is None   # not in it


def test_path_out_of_order_fails_at_the_covered_check(root, tmp_path):
    d = api(root, "poc-shared-3-scale", PATH)
    states = run_in_shell(root, d, env=VARS)
    first_verify = next(b["idx"] for b in visible_steps(d) if b["covered_by"])
    assert states[first_verify] == "failed"      # the UI then offers "run its hidden steps here"


def test_path_in_order_runs_in_the_shared_namespace(root, tmp_path):
    for tid in MEMBERS:                          # each member in its own shell, like the UI
        states = run_in_shell(root, api(root, tid, PATH), env=VARS)
        assert states and set(states.values()) == {"passed"}, (tid, states)
    shared = tmp_path / "tut-poc" / "poc-path"
    assert (shared / "model").read_text().strip() == "path-model"
    assert (shared / "replicas").read_text().strip() == "3"
    assert not (tmp_path / "tut-poc" / "poc-shared-3-scale").exists()   # nothing in its own NS
