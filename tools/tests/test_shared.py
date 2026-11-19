"""PoC: shared steps (tut:define / tut:use) and learning paths."""
from __future__ import annotations

import pytest

from tut import generate, lint, markdown, shared
from tut.model import load_tutorials
from test_rules import GOOD_README, make_env, make_tut

STEP = '```bash run\necho deploy\n```\n\n```bash verify\necho check\n```'


def readme(*regions: str) -> str:
    return GOOD_README.replace("```bash cleanup", "\n".join(regions) + "\n\n```bash cleanup")


@pytest.fixture
def repo(tmp_path):
    make_env(tmp_path)
    make_tut(tmp_path, "a", readme(f"<!-- tut:define model -->\n{STEP}\n<!-- /tut -->"), status="draft")
    make_tut(tmp_path, "b", readme("<!-- tut:use model -->\n<!-- /tut -->"), status="draft")
    return tmp_path


def errors(root, code="D014"):
    generate.sync(root)
    return [f.message for f in lint.Linter(root).run() if f.code == code]


def test_use_copies_the_definition_and_runs_as_normal_blocks(repo):
    changed, errs = generate.sync(repo)
    assert not errs
    b = (repo / "tutorials" / "b" / "README.md").read_text()
    assert "Copied from a (tut:define model)" in b and "echo deploy" in b and "echo check" in b
    doc = markdown.parse(b)
    assert [x.role for x in doc.blocks if x.in_region == "use"] == ["run", "verify"]
    assert set(shared.block_names(doc).values()) == {"model"}
    assert errors(repo) == []
    # the definition is the author's text: sync leaves it alone
    a = (repo / "tutorials" / "a" / "README.md").read_text()
    assert a.count("echo deploy") == 1 and "Copied from" not in a


def test_lint_rules(repo):
    make_tut(repo, "c", readme("<!-- tut:use nope -->\n<!-- /tut -->"), status="draft")
    make_tut(repo, "d", readme(f"<!-- tut:define model -->\n{STEP}\n<!-- /tut -->"), status="draft")
    make_tut(repo, "e", readme("<!-- tut:define nested -->\n<!-- tut:use model -->\n<!-- /tut -->"),
             status="draft")
    make_tut(repo, "f", readme(f"<!-- tut:define own -->\n{STEP}\n<!-- /tut -->\n"
                               "<!-- tut:use own -->\n<!-- /tut -->"), status="draft")
    msgs = " | ".join(errors(repo))
    assert "tut:use nope: no tutorial defines it" in msgs
    assert "tut:define model is defined more than once: a, d" in msgs
    assert "tut:define nested: no tut: markers inside" in msgs
    assert "tut:use own: this tutorial defines it itself" in msgs


def test_covered_only_counts_earlier_members(repo):
    ts = {t.id: t for t in load_tutorials(repo)}
    generate.sync(repo)
    assert shared.covered(["a", "b"], "b", ts) == {"model": "a"}
    assert shared.covered(["b", "a"], "b", ts) == {}          # b comes first: nothing covered
    assert shared.covered(["a", "b"], "a", ts) == {}


def ui_get(root, url):
    import asyncio
    from aiohttp.test_utils import TestClient, TestServer
    from tut.ui.server import UI

    async def main():
        ui = UI(root)
        async with TestClient(TestServer(ui.app())) as c:
            r = await c.get(url, headers={"X-Tut-Token": ui.token})
            assert r.status == 200
            return await r.json()
    return asyncio.run(main())


def test_live_preview_shows_the_synced_text_before_sync(repo):
    """While writing: the page shows what sync will produce, says the file is not
    synced yet, and the run messages use the same block indexes."""
    d = ui_get(repo, "/api/tutorials/b")                        # b has an empty tut:use, not synced
    assert d["preview"] == {"stale": True, "error": None}
    assert any(blk["shared"] == "model" and "echo deploy" in blk["code"] for blk in d["blocks"])
    generate.sync(repo)
    assert ui_get(repo, "/api/tutorials/b")["preview"] == {"stale": False, "error": None}


def test_problems_panel_lists_this_tutorials_findings(repo):
    p = repo / "tutorials" / "b" / "README.md"
    p.write_text(p.read_text().replace("tut:use model", "tut:use modle"))
    d = ui_get(repo, "/api/tutorials/b")
    assert d["preview"]["error"].startswith("tut:use modle: no tutorial defines it")
    probs = ui_get(repo, "/api/tutorials/b/problems")["problems"]
    assert any(x["code"] == "D014" and "modle" in x["message"] for x in probs)
    assert all(x["file"].startswith("tutorials/b/") for x in probs)      # only this tutorial


def ui_call(root, method, url, json=None):
    import asyncio
    from aiohttp.test_utils import TestClient, TestServer
    from tut.ui.server import UI

    async def main():
        ui = UI(root)
        async with TestClient(TestServer(ui.app())) as c:
            r = await c.request(method, url, json=json, headers={"X-Tut-Token": ui.token})
            return r.status, await r.json() if r.content_type == "application/json" else await r.text()
    return asyncio.run(main())


def test_editor_reads_saves_and_never_overwrites_a_newer_file(repo):
    readme = repo / "tutorials" / "b" / "README.md"
    st, src = ui_call(repo, "GET", "/api/tutorials/b/source")
    assert st == 200 and src["file"] == "tutorials/b/README.md" and src["text"] == readme.read_text()
    st, r = ui_call(repo, "PUT", "/api/tutorials/b/source", {"text": src["text"] + "edited", "mtime": src["mtime"]})
    assert st == 200 and readme.read_text().endswith("edited\n")
    # saving with the old mtime (someone changed the file meanwhile) is refused, file untouched
    st, r = ui_call(repo, "PUT", "/api/tutorials/b/source", {"text": "mine", "mtime": src["mtime"]})
    assert st == 409 and r["text"].endswith("edited\n") and readme.read_text().endswith("edited\n")
    # only this tutorial's README files
    assert ui_call(repo, "GET", "/api/tutorials/b/source?lang=../../x")[0] == 400
    assert ui_call(repo, "GET", "/api/tutorials/nope/source")[0] == 404


def test_save_and_sync_fills_the_use_region(repo):
    st, r = ui_call(repo, "POST", "/api/sync")
    assert st == 200 and r["errors"] == [] and "tutorials/b/README.md" in r["changed"]
    assert "Copied from a (tut:define model)" in (repo / "tutorials" / "b" / "README.md").read_text()


def test_page_and_scripts_are_always_revalidated(repo):
    """After `git pull` the browser must not keep an old app.js with a new page."""
    import asyncio
    from aiohttp.test_utils import TestClient, TestServer
    from tut.ui.server import UI

    async def main():
        ui = UI(repo)
        async with TestClient(TestServer(ui.app())) as c:
            h = {"X-Tut-Token": ui.token}
            for path in ("/", "/static/app.js", "/static/app.css", "/static/index.html"):
                r = await c.get(path, headers=h)
                assert r.status == 200 and r.headers.get("Cache-Control") == "no-cache", path
    asyncio.run(main())


ECHO_TRANSLATOR = (
    "import sys; src = sys.stdin.read().split('=== README.md (English source) ===\\n', 1)[1];"
    " print('<<<TUT-TRANSLATION-BEGIN>>>'); print(src); print('<<<TUT-TRANSLATION-END>>>')")


def test_ui_creates_a_translation_with_the_users_ai(repo, monkeypatch, tmp_path):
    from tut import lint
    from tut.model import load_tutorials
    monkeypatch.delenv("TUT_AI", raising=False)
    monkeypatch.delenv("TUT_TRANSLATOR", raising=False)
    st, r = ui_call(repo, "POST", "/api/tutorials/a/translation?lang=ko")
    assert st == 200 and not r["ok"] and "TUT_AI" in r["message"]            # tells how to set it up
    fake = tmp_path / "echo_tr.py"
    fake.write_text(ECHO_TRANSLATOR)
    monkeypatch.setenv("TUT_AI", f"cmd:python3 {fake}")
    generate.sync(repo)
    st, r = ui_call(repo, "POST", "/api/tutorials/a/translation?lang=ko")
    assert st == 200 and r["ok"], r
    t = next(x for x in load_tutorials(repo) if x.id == "a")
    assert (t.path / "README.ko.md").exists() and "ko" in t.langs
    assert lint.translation_state(t, "ko") == "draft"                         # AI draft until reviewed
    assert ui_call(repo, "POST", "/api/tutorials/a/translation?lang=xx")[0] == 400


def test_editor_also_opens_tutorial_yaml_and_nothing_else(repo):
    st, r = ui_call(repo, "GET", "/api/tutorials/a/source?file=tutorial.yaml")
    assert st == 200 and r["file"] == "tutorials/a/tutorial.yaml" and "title" in r["text"]
    st, _ = ui_call(repo, "PUT", "/api/tutorials/a/source?file=tutorial.yaml",
                    {"text": r["text"].replace("title:\n  en: a", "title:\n  en: New title"), "mtime": r["mtime"]})
    assert st == 200
    assert "New title" in (repo / "tutorials" / "a" / "tutorial.yaml").read_text()
    assert ui_call(repo, "GET", "/api/tutorials/a/source?file=../../AGENTS.md")[0] == 400
