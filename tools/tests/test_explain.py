"""AI explainers (tut/explain.py): never executed, never in CI e2e, checked by
lint X001-X005, and a live walk that keeps one shell across separate calls."""
from __future__ import annotations

import textwrap

import pytest

from tut import explain, generate, lint, plan
from tut.model import load_tutorials

from test_rules import GOOD_README, make_env, make_tut

SVG_OK = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10">'
          '<style>@keyframes f { to { opacity: 0 } } rect { animation: f 1s infinite }</style>'
          '<rect width="5" height="5"/><use href="#r"/></svg>')


@pytest.fixture
def repo(tmp_path):
    make_env(tmp_path)
    return tmp_path


def tut(repo, tid="t"):
    d = make_tut(repo, tid)
    generate.sync(repo)
    return d, next(t for t in load_tutorials(repo) if t.id == tid)


def write_explainer(d, t, body="# How it works\n\n![flow](flow.svg)\n", svg=SVG_OK, reviewed="no"):
    e = d / "explainer"
    e.mkdir(exist_ok=True)
    sha = lint.source_hash(t.readme().read_text())
    (e / "index.md").write_text(
        f"<!-- tut-explainer source=README.md sha={sha} by=claude reviewed={reviewed} -->\n{body}")
    (e / "flow.svg").write_text(svg)


def found(repo):
    return {(f.code, f.severity) for f in lint.Linter(repo).run() if f.code.startswith("X")}


# ------------------------------------------------------------- CI e2e
def test_explainer_changes_run_no_tutorial(repo):
    make_tut(repo, "a")
    ts = load_tutorials(repo)
    assert plan.affected(["tutorials/a/explainer/index.md", "tutorials/a/explainer/flow.svg"], ts) == []
    assert [t.id for t in plan.affected(["tutorials/a/README.md"], ts)] == ["a"]


# ---------------------------------------------------------------- lint
def test_good_explainer_only_warns_until_reviewed(repo):
    d, t = tut(repo)
    write_explainer(d, t)
    assert found(repo) == {("X005", "warning")}
    explain.mark(t)
    assert found(repo) == set()
    assert explain.state(t) == "ok"


def test_X001_marker_must_be_the_first_line(repo):
    d, t = tut(repo)
    write_explainer(d, t)
    p = d / "explainer" / "index.md"
    p.write_text("# no marker\n" + p.read_text())
    assert ("X001", "error") in found(repo)


def test_X002_explainer_is_never_executed(repo):
    d, t = tut(repo)
    write_explainer(d, t, body="# x\n\n```bash run\nkubectl delete ns x\n```\n")
    assert ("X002", "error") in found(repo)


def test_X003_broken_image(repo):
    d, t = tut(repo)
    write_explainer(d, t, body="# x\n\n![missing](nope.svg)\n")
    assert ("X003", "error") in found(repo)


@pytest.mark.parametrize("svg", [
    '<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>',
    '<svg xmlns="http://www.w3.org/2000/svg"><rect onclick="x()"/></svg>',
    '<svg xmlns="http://www.w3.org/2000/svg"><image href="https://evil/x.png"/></svg>',
    '<svg xmlns="http://www.w3.org/2000/svg"><style>@import url(https://x/y.css);</style></svg>',
    '<svg xmlns="http://www.w3.org/2000/svg"><foreignObject/></svg>',
    '<svg',
])
def test_X004_svg_is_a_picture_only(repo, svg):
    d, t = tut(repo)
    write_explainer(d, t, svg=svg)
    assert ("X004", "error") in found(repo)


def test_X005_readme_changed_since(repo):
    d, t = tut(repo)
    write_explainer(d, t)
    explain.mark(t)
    (d / "README.md").write_text(GOOD_README + "\nMore text.\n")
    assert ("X005", "warning") in found(repo)
    assert explain.state(t) == "behind"


def test_mark_refuses_an_explainer_with_errors(repo):
    d, t = tut(repo)
    write_explainer(d, t, body="# x\n\n```bash verify\ntrue\n```\n")
    with pytest.raises(explain.ExplainError):
        explain.mark(t)


# --------------------------------------------------------------- probes
@pytest.mark.parametrize("argv", [
    ["kubectl", "get", "pods", "-n", "$NS"],
    ["kubectl", "describe", "pod", "-n", "${NS}", "x"],
    ["kubectl", "logs", "-n", "x", "-l", "app=y", "--tail=50"],
    ["kubectl", "-n", "x", "get", "inferencepool", "-o", "yaml"],
    ["kubectl", "auth", "can-i", "get", "pods"],
    ["helm", "list", "-A"],
])
def test_read_only_probes_are_allowed(argv):
    # every word double-quoted: $NS still expands in the tutorial shell, nothing else is parsed
    assert explain.probe_command(argv) == " ".join(f'"{a}"' for a in argv)


@pytest.mark.parametrize("argv", [
    ["kubectl", "delete", "ns", "x"],
    ["kubectl", "-n", "get", "delete", "ns", "x"],          # a flag value is not the verb
    ["kubectl", "--namespace=x", "delete", "ns", "y"],
    ["kubectl", "apply", "-f", "x.yaml"],
    ["kubectl", "exec", "pod", "--", "sh"],
    ["kubectl", "port-forward", "svc/x", "8080"],
    ["kubectl", "logs", "-f", "pod"],
    ["kubectl", "get", "pods", "--watch"],
    ["kubectl", "get", "pods", "-n", "$(rm -rf /)"],
    ["kubectl", "get", "pods;", "rm", "x"],
    ["helm", "uninstall", "x"],
    ["bash", "-c", "kubectl get pods"],
    [],
])
def test_anything_else_is_refused(argv):
    with pytest.raises(explain.ExplainError):
        explain.probe_command(argv)


# ------------------------------------------------------------ live walk
WALK = textwrap.dedent("""\
    # W

    ```bash run
    export A=1
    cd /tmp
    f() { echo "f says $A"; }
    ```

    ```bash verify
    test "$A" = 1
    ```

    ```bash run
    read -r line || echo "stdin is empty"
    false
    echo "after a failure, pwd=$(pwd)"
    f
    ```

    ```bash cleanup
    echo bye
    ```
    """)


def test_walk_keeps_one_shell_and_records_evidence(tmp_path):
    from tut.model import Tutorial
    d = tmp_path / "tutorials" / "w"
    d.mkdir(parents=True)
    (d / "README.md").write_text(WALK)
    t = Tutorial(id="w", path=d, meta={"timeout_minutes": 1})
    s = explain.Session(t, root=tmp_path)
    s.start()
    try:
        s1, rc1, _ = s.next()
        s2, rc2, _ = s.next()
        s3, rc3, out3 = s.next()
        assert (s1.role, rc1, s2.role, rc2) == ("run", 0, "verify", 0)
        # a failing command is reported, the shell lives on; stdin never eats the FIFO
        assert rc3 == 1 and "stdin is empty" in out3
        assert "pwd=/tmp" in out3 and "f says 1" in out3
        with pytest.raises(explain.ExplainError):
            s.next()                                    # all steps ran
    finally:
        out = s.stop()
    assert "bye" in out and not s.alive
    ev = s.evidence.read_text()
    assert "Step 1/3" in ev and "Step 3/3" in ev and "Cleanup 1" in ev


# ------------------------------------------------------------------ UI
def ui_fetch(root, url):
    import asyncio
    from aiohttp.test_utils import TestClient, TestServer
    from tut.ui.server import UI

    async def main():
        ui = UI(root)
        async with TestClient(TestServer(ui.app())) as c:
            r = await c.get(url, headers={"X-Tut-Token": ui.token})
            return r.status, r.headers.get("Content-Security-Policy", ""), await r.text()
    return asyncio.run(main())


def test_ui_shows_the_explainer_in_its_own_page_with_the_ai_banner(repo):
    d, t = tut(repo)
    write_explainer(d, t, body="# How it works\n\n![flow](flow.svg)\n\n<script>alert(1)</script>\n")
    status, csp, html = ui_fetch(repo, "/explain/t")
    assert status == 200 and "script-src 'self'" in csp
    assert "Written by an AI (claude)" in html and "Not reviewed by a person yet" in html
    assert 'src="/files/tutorials/t/explainer/flow.svg"' in html
    assert "alert(1)" not in html                    # cleaned like a README
    import json
    status, _, body = ui_fetch(repo, "/api/tutorials/t")
    assert json.loads(body)["explainer"] == {"en": "draft"}


def test_ui_has_no_explainer_page_when_there_is_none(repo):
    tut(repo)
    status, _, _ = ui_fetch(repo, "/explain/t")
    assert status == 404


# --------------------------------------------------------------- review
def test_review_agent_is_tut_ai_review_else_tut_ai(monkeypatch):
    from tut import draft
    monkeypatch.delenv("TUT_TRANSLATOR", raising=False)
    monkeypatch.setenv("TUT_AI", "claude")
    monkeypatch.delenv("TUT_AI_REVIEW", raising=False)
    a, var = draft.review_agent_from_env()
    assert (a.name, var) == ("claude", "TUT_AI")
    monkeypatch.setenv("TUT_AI_REVIEW", "codex")
    monkeypatch.setenv("TUT_AI_REVIEW_ARGS", "--model o3")
    a, var = draft.review_agent_from_env()
    assert (a.name, var, a.extra) == ("codex", "TUT_AI_REVIEW", ["--model", "o3"])
    # the reviewer only reads: read-only sandbox, and the user's flags are kept
    argv = explain._argv(explain.REVIEW_TOOLS["codex"], a, "P")
    assert argv[-3:] == ["--model", "o3", "P"] and "read-only" in argv


def test_review_writes_the_report_and_counts_findings(repo):
    from tut.draft import Agent
    d, t = tut(repo)
    write_explainer(d, t)
    w = explain.workdir(t, repo)
    w.mkdir(parents=True)
    (w / "evidence.md").write_text("# evidence\n")
    report = '- [unsupported] index.md: "x" -- not seen; evidence: none\nFINDINGS: 1'
    agent = Agent("cmd", [f"cat >/dev/null; printf '%s\\n' '{report}'"], shell=True)
    assert explain.review(t, agent, root=repo, log=lambda *_: None) == 1
    assert "[unsupported]" in (w / "review.md").read_text()


def test_review_needs_the_evidence_of_a_walk(repo):
    from tut.draft import Agent
    d, t = tut(repo)
    write_explainer(d, t)
    with pytest.raises(explain.ExplainError):
        explain.review(t, Agent("cmd", ["true"], shell=True), root=repo, log=lambda *_: None)


def test_pictures_open_at_full_size_on_the_page(repo):
    """zoom.js: a click on a picture opens it in a dialog instead of replacing the
    page (README pictures are links to themselves and lose target= when cleaned).
    Both pages load the script, and it is ours (the CSP allows only 'self')."""
    d, t = tut(repo)
    write_explainer(d, t)
    _, _, page = ui_fetch(repo, "/explain/t")
    _, _, index = ui_fetch(repo, "/")
    assert '<script src="/static/zoom.js"></script>' in page
    assert '<script src="/static/zoom.js"></script>' in index
    status, _, js = ui_fetch(repo, "/static/zoom.js")
    assert status == 200 and "showModal" in js and "#doc img, .explainer-doc img" in js


# ------------------------------------------------- several reviewers, each on its own
def test_tut_ai_review_takes_several_tools(monkeypatch):
    from tut import draft
    monkeypatch.setenv("TUT_AI", "claude")
    monkeypatch.setenv("TUT_AI_REVIEW", "claude, codex")
    monkeypatch.setenv("TUT_AI_REVIEW_ARGS", "--verbose")
    agents, var = draft.review_agents_from_env()
    assert ([a.name for a in agents], var) == (["claude", "codex"], "TUT_AI_REVIEW")
    assert all(a.extra == ["--verbose"] for a in agents)          # the flags go to every reviewer
    monkeypatch.setenv("TUT_AI_REVIEW", "claude,gemini")
    with pytest.raises(draft.DraftError, match="gemini"):
        draft.review_agents_from_env()
    monkeypatch.setenv("TUT_AI_REVIEW", "cmd:my-reviewer --a,b")  # a command may contain commas
    agents, _ = draft.review_agents_from_env()
    assert [(a.name, a.argv) for a in agents] == [("cmd", ["my-reviewer --a,b"])]
    monkeypatch.delenv("TUT_AI_REVIEW")
    agents, var = draft.review_agents_from_env()                   # falls back to the writer's CLI
    assert ([a.name for a in agents], var) == (["claude"], "TUT_AI")


def _reviewed_repo(repo):
    d, t = tut(repo)
    write_explainer(d, t)
    w = explain.workdir(t, repo)
    w.mkdir(parents=True)
    (w / "evidence.md").write_text("# evidence\n")
    return t, w


def _fake_reviewer(report: str):
    from tut.draft import Agent
    return Agent("cmd", [f"cat >/dev/null; printf '%s\\n' '{report}'"], shell=True)


def test_several_reviewers_each_write_a_report_and_one_combined(repo):
    t, w = _reviewed_repo(repo)
    a = _fake_reviewer('- [unsupported] index.md: "x" -- not seen; evidence: none\nFINDINGS: 1')
    b = _fake_reviewer('- [contradicted] index.md: "y" -- says 3, is 4; evidence: 12\n'
                       '- [mismatch] flow.svg: "z" -- differs; evidence: none\nFINDINGS: 2')
    assert explain.review_all(t, [a, b], root=repo, log=lambda *_: None) == 3
    assert "[unsupported]" in (w / "review-cmd.md").read_text()
    assert "[mismatch]" in (w / "review-cmd-2.md").read_text()      # same tool twice: -2
    combined = (w / "review.md").read_text()
    assert "## cmd\n" in combined and "## cmd-2\n" in combined
    assert "[unsupported]" in combined and "[contradicted]" in combined


def test_a_failing_reviewer_is_left_out_but_all_failing_is_an_error(repo):
    from tut.draft import Agent
    t, w = _reviewed_repo(repo)
    good = _fake_reviewer("FINDINGS: 0")
    broken = Agent("cmd", ["cat >/dev/null; exit 3"], shell=True)
    logged = []
    assert explain.review_all(t, [good, broken], root=repo, log=logged.append) == 0
    assert any("failed (exit 3)" in line for line in logged)
    assert "(failed:" in (w / "review.md").read_text()
    with pytest.raises(explain.ExplainError, match="every reviewer failed"):
        explain.review_all(t, [broken, broken], root=repo, log=lambda *_: None)


def test_one_reviewer_keeps_the_single_report(repo):
    t, w = _reviewed_repo(repo)
    assert explain.review_all(t, [_fake_reviewer("FINDINGS: 0")], root=repo, log=lambda *_: None) == 0
    assert (w / "review.md").exists() and not list(w.glob("review-*.md"))


def test_the_writer_must_decide_every_finding(repo):
    t, _ = _reviewed_repo(repo)
    p = explain.build_fix_prompt(t, repo)
    assert "A reviewer can be wrong" in p.replace("a reviewer can be wrong", "A reviewer can be wrong")
    assert '"A: <finding>' in p and '"R: <finding>' in p and "## Review round" in p
