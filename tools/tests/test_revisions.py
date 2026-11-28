"""Tutorial revisions, version resolution and the CI window (docs/rfc/0002-tutorial-revisions.md)."""
from __future__ import annotations

import asyncio
import json
import subprocess

import pytest
import yaml

from test_rules import GOOD_README, make_env, make_tut, meta, pin
from tut import catalog, generate, lint, model, plan, revision, runner, site


def git(root, *a):
    return subprocess.run(["git", *a], cwd=root, check=True, capture_output=True, text=True).stdout


def commit_all(root, msg="c"):
    git(root, "add", "-A")
    git(root, "commit", "-qm", msg)


@pytest.fixture
def repo(tmp_path):
    make_env(tmp_path)
    git(tmp_path, "init", "-q", "-b", "main")
    return tmp_path


def make_revision(root, tid, rev, tested, **kw):
    d = root / "tutorials" / tid / "revisions" / rev
    (d / "manifests").mkdir(parents=True)
    (d / "manifests" / "cm.yaml").write_text("kind: ConfigMap\nmetadata: {name: x}\n")
    m = meta(tid, versions={"default": tested[-1], "tested": tested}, frozen=True)
    m.update(kw)
    (d / "tutorial.yaml").write_text(yaml.safe_dump(m))
    (d / "README.md").write_text(GOOD_README)
    return d


def errors(root, base=None):
    generate.sync(root)
    return sorted({(f.code, f.path.relative_to(root).as_posix()) for f in lint.Linter(root, base=base).run()
                   if f.severity == "error"})


# ------------------------------------------------------------- resolution
def test_resolve_picks_current_then_revision_by_tag_then_minor(repo):
    make_tut(repo, "t", versions={"default": "v0.20.0", "tested": ["v0.20.0"]})
    make_revision(repo, "t", "v0.19", ["v0.18.0", "v0.19.0"])
    t = model.load_tutorials(repo)[0]
    assert model.resolve(t, None).revision is None
    assert model.resolve(t, "v0.20.0").revision is None
    assert model.resolve(t, "v0.19.0").revision == "v0.19"
    assert model.resolve(t, "v0.19.2").revision == "v0.19"          # same minor
    assert model.resolve(t, "v0.20.1").revision is None
    assert model.resolve(t, "v0.17.0") is None
    r = model.resolve(t, "v0.18.0")
    assert r.key == "t@v0.19" and r.rel == "tutorials/t/revisions/v0.19" and r.root == repo


def test_ci_runs_N_and_the_newest_tested_minor_below_it(repo):
    make_tut(repo, "a", versions={"default": "v0.20.0", "tested": ["v0.20.0"]})
    make_revision(repo, "a", "v0.18", ["v0.17.0", "v0.18.0"])          # a jumped 0.18 -> 0.20
    make_tut(repo, "b", versions={"default": "v0.19.1", "tested": ["v0.18.0", "v0.19.1"]})
    pin(repo, "v0.20.0")
    ts = model.load_tutorials(repo)
    assert model.pinned_version(repo) == "v0.20.0" and model.pinned_minor(ts) == (0, 20)
    m = plan.full_matrix(repo)
    # a: N=0.20 and N-1 = its newest tested minor below N (0.18, in v0.18); b has no N: only 0.19
    assert {(e["tutorial"], e["version"], e["revision"]) for e in m} == {
        ("a", "v0.20.0", ""), ("a", "v0.18.0", "v0.18"), ("b", "v0.19.1", "")}
    assert sorted((e["tutorial"], e["version"]) for e in plan.out_of_window(repo)) == [
        ("a", "v0.17.0"), ("b", "v0.18.0")]
    # the pin moves to 0.21 and nobody tests it yet: everyone runs only its newest version
    pin(repo, "v0.21.0")
    assert {(e["tutorial"], e["version"]) for e in plan.full_matrix(repo)} == {
        ("a", "v0.20.0"), ("b", "v0.19.1")}


def test_N_is_only_the_pinned_version(repo, monkeypatch):
    make_tut(repo, "a", versions={"default": "v0.20.0", "tested": ["v0.18.0", "v0.20.0"]})
    pin(repo, "v0.20.0")
    assert {e["version"] for e in plan.full_matrix(repo)} == {"v0.18.0", "v0.20.0"}
    # nothing else moves N: not an environment variable, not what a tutorial tests
    monkeypatch.setenv("TUT_LATEST_VERSION", "v0.21.0")
    assert model.pinned_minor(model.load_tutorials(repo)) == (0, 20)
    pin(repo, "v0.19.0")
    assert model.pinned_minor(model.load_tutorials(repo)) == (0, 19)
    # T009: a tested version above the pin would never run
    assert ("T009", "tutorials/a/tutorial.yaml") in errors(repo)
    pin(repo, "v0.20.0")
    assert errors(repo) == []


def test_product_version_command_checks_the_release_and_sets_the_pin(repo, monkeypatch, capsys):
    from tut import cli
    make_tut(repo, "a")
    monkeypatch.setattr(cli, "REPO_ROOT", repo)
    calls = []

    def fake_gh(cmd, **kw):
        calls.append(cmd)
        tag = cmd[2].rsplit("/", 1)[-1]
        ok = tag == "v0.21.0"
        return subprocess.CompletedProcess(cmd, 0 if ok else 1, tag + "\n" if ok else "", "" if ok else "Not Found")
    monkeypatch.setattr(cli.subprocess, "run", fake_gh)
    assert cli.main(["kserve-version"]) == 0 and capsys.readouterr().out.strip() == "v0.18.0"
    with pytest.raises(SystemExit, match="has no release v0.99.0"):
        cli.main(["kserve-version", "v0.99.0"])
    assert model.pinned_version(repo) == "v0.18.0"                  # nothing changed
    assert cli.main(["kserve-version", "v0.21.0"]) == 0
    assert calls[-1][:3] == ["gh", "api", "repos/kserve/kserve/releases/tags/v0.21.0"]
    assert model.pinned_version(repo) == "v0.21.0"
    assert "# the newest KServe version" in (repo / "project.yaml").read_text()   # the comment stays


def test_pr_matrix_runs_a_new_revision_and_not_an_old_one(repo):
    pin(repo, "v0.19.0")
    make_tut(repo, "a", versions={"default": "v0.19.0", "tested": ["v0.19.0"]})
    commit_all(repo)
    base = git(repo, "rev-parse", "HEAD").strip()
    make_revision(repo, "a", "v0.18", ["v0.18.0"])
    (repo / "tutorials" / "a" / "tutorial.yaml").write_text(yaml.safe_dump(
        meta("a", versions={"default": "v0.19.0", "tested": ["v0.19.0"]})))
    commit_all(repo, "rev")
    assert {(e["version"], e["revision"]) for e in plan.pr_matrix(base, repo)} == {("v0.19.0", ""), ("v0.18.0", "v0.18")}
    base2 = git(repo, "rev-parse", "HEAD").strip()
    (repo / "tutorials" / "a" / "README.md").write_text(GOOD_README + "\nMore text.\n")
    commit_all(repo, "edit")
    assert {(e["version"], e["revision"]) for e in plan.pr_matrix(base2, repo)} == {("v0.19.0", "")}


# ------------------------------------------------------------- revision start
def test_revision_start_keeps_the_base_state_and_moves_the_tutorial(repo):
    d = make_tut(repo, "a")
    pin(repo, "v0.19.0")
    (d / "README.md").write_text(GOOD_README.replace("# T\n", "# T\n\nSee [env](../../envs/kind-x/v1/) "
                                                     "and [cm](manifests/cm.yaml).\n"))
    (d / "tutorial.yaml").write_text(
        (d / "tutorial.yaml").read_text().replace("  default: v0.18.0", "  default: v0.18.0   # readers"))
    generate.sync(repo)
    commit_all(repo)
    (d / "README.md").write_text((d / "README.md").read_text() + "\nUncommitted edit.\n")
    t = model.load_tutorials(repo)[0]
    dst = revision.start(t, "v0.19.0", base="HEAD")
    assert dst == d / "revisions" / "v0.18"
    r = model.load_revisions(model.load_tutorials(repo)[0])[0]
    assert r.frozen and r.tested_versions == ["v0.18.0"] and r.default_version == "v0.18.0"
    text = r.readme("en").read_text()
    assert "Uncommitted edit" not in text                       # the base branch, not the working tree
    assert 'cd "$REPO_ROOT/tutorials/a/revisions/v0.18"' in text   # setup runs inside the revision
    assert "](../../../../envs/kind-x/v1/)" in text and "](manifests/cm.yaml)" in text
    assert "Older revision (v0.18)" in text
    cur = (d / "tutorial.yaml").read_text()
    assert "default: v0.19.0   # readers" in cur and yaml.safe_load(cur)["versions"]["tested"] == ["v0.19.0"]
    # sync never writes into revisions/; the current header links the revision
    before = text
    generate.sync(repo)
    assert r.readme("en").read_text() == before
    assert "[v0.18](revisions/v0.18/README.md)" in (d / "README.md").read_text()
    script, _ = runner.build_script(model.resolve(model.load_tutorials(repo)[0], "v0.18.0"), "v0.18.0", False)
    assert "tutorials/a/revisions/v0.18/README.md:" in script
    assert errors(repo) == []
    with pytest.raises(revision.RevisionError, match="already kept as v0.18"):     # not a second copy
        revision.start(model.load_tutorials(repo)[0], "v0.19.0", base="HEAD")


def test_revision_start_after_the_new_version_was_added_to_tested(repo):
    """The flow for a new product version: pin it, add it to tested, CI fails,
    then keep the old version as a revision (AGENTS.md "A new product version")."""
    d = make_tut(repo, "a")                                       # tested [v0.18.0]
    generate.sync(repo)
    commit_all(repo)
    pin(repo, "v0.20.0")
    (d / "tutorial.yaml").write_text((d / "tutorial.yaml").read_text().replace("- v0.18.0", "- v0.18.0\n  - v0.20.0"))
    t = model.load_tutorials(repo)[0]
    assert t.tested_versions == ["v0.18.0", "v0.20.0"]
    assert {e["version"] for e in plan.full_matrix(repo)} == {"v0.18.0", "v0.20.0"}     # N and N-1
    revision.start(t, "v0.20.0", base="HEAD")                     # v0.20.0 is new on this branch
    t = model.load_tutorials(repo)[0]
    assert t.tested_versions == ["v0.20.0"] and t.default_version == "v0.20.0"
    assert model.load_revisions(t)[0].tested_versions == ["v0.18.0"]
    assert {(e["version"], e["revision"]) for e in plan.full_matrix(repo)} == {("v0.20.0", ""), ("v0.18.0", "v0.18")}
    assert errors(repo, base="HEAD") == []
    with pytest.raises(revision.RevisionError, match="already tested with v0.18.0 on HEAD"):
        revision.start(model.load_tutorials(repo)[0], "v0.18.0", base="HEAD")


def test_skipped_lists_a_gap_in_tested_and_keep_moves_the_versions_before_it(repo):
    pin(repo, "v0.21.0")
    d = make_tut(repo, "a", versions={"default": "v0.21.0", "tested": ["v0.17.0", "v0.18.0", "v0.21.0"]})
    make_tut(repo, "b", versions={"default": "v0.20.0", "tested": ["v0.20.0"]})
    make_tut(repo, "c", versions={"default": "v0.18.0", "tested": ["v0.18.0"]})
    make_tut(repo, "d", versions={"default": "v0.21.0", "tested": ["v0.18.0", "v0.19.0", "v0.20.0", "v0.21.0"]})
    generate.sync(repo)
    commit_all(repo)
    # N=0.21. a: 0.21 and 0.18 (its tested minor below N) until the maintainer says keep;
    # b, c have no N: only their newest; d: 0.21 and 0.20
    assert {(e["tutorial"], e["version"]) for e in plan.full_matrix(repo)} == {
        ("a", "v0.21.0"), ("a", "v0.18.0"), ("b", "v0.20.0"), ("c", "v0.18.0"),
        ("d", "v0.20.0"), ("d", "v0.21.0")}
    # only a gap is a skip; d's old versions join up, c has not moved yet
    assert plan.skipped(repo) == [{"tutorial": "a", "versions": ["v0.17.0", "v0.18.0"]}]
    assert revision.keep_cli("a", [], "HEAD", root=repo) == 0
    t = model.load_tutorials(repo)[0]
    assert t.tested_versions == ["v0.21.0"] and t.default_version == "v0.21.0"
    r = model.load_revisions(t)[0]
    assert r.revision == "v0.18" and r.frozen and r.tested_versions == ["v0.17.0", "v0.18.0"]
    assert r.default_version == "v0.18.0"
    assert 'cd "$REPO_ROOT/tutorials/a/revisions/v0.18"' in r.readme("en").read_text()
    assert model.resolve(t, "v0.18.0").revision == "v0.18"
    assert plan.skipped(repo) == []
    assert ("a", "v0.18.0") in {(e["tutorial"], e["version"]) for e in plan.full_matrix(repo)}
    assert errors(repo, base="HEAD") == []                      # R004: the revision keeps them
    c = model.load_tutorials(repo)[2]
    with pytest.raises(revision.RevisionError, match="skipped no version"):
        revision.keep(model.load_tutorials(repo)[3], [], base="HEAD")
    with pytest.raises(revision.RevisionError, match="no tested version"):
        revision.keep(c, ["v0.18.0"], base="HEAD")
    with pytest.raises(revision.RevisionError, match="not tested with"):
        revision.keep(model.load_tutorials(repo)[1], ["v0.19.0"], base="HEAD")


def test_revision_start_names_the_users_of_shared_steps(repo):
    owner = GOOD_README.replace("```bash run\nkubectl apply", "<!-- tut:define cm -->\n\n```bash run\nkubectl apply") \
        .replace('-n "$NS"\n```\n\n<!-- tut:include', '-n "$NS"\n```\n\n<!-- /tut -->\n\n<!-- tut:include', 1)
    make_tut(repo, "a", owner)
    make_tut(repo, "b", GOOD_README + "\n<!-- tut:use cm -->\n<!-- /tut -->\n")
    generate.sync(repo)
    assert revision.users_of(model.load_tutorials(repo)[0], model.load_tutorials(repo)) == ["b"]


# ------------------------------------------------------------------- lint
def test_R001_R003_R005_revision_metadata(repo):
    make_tut(repo, "a", versions={"default": "v0.19.0", "tested": ["v0.19.0"]})
    make_revision(repo, "a", "v0.18", ["v0.18.0"], frozen=False)
    make_revision(repo, "a", "v0.19", ["v0.19.0"], env="kind-x/v2")
    found = errors(repo)
    assert ("R001", "tutorials/a/revisions/v0.18/tutorial.yaml") in found
    assert ("R003", "tutorials/a/revisions/v0.19/tutorial.yaml") in found
    assert ("R005", "tutorials/a/revisions/v0.19/tutorial.yaml") in found
    make_tut(repo, "c", frozen=True)
    assert ("R001", "tutorials/c/tutorial.yaml") in errors(repo)
    # the directory name says which version the revision is for
    pin(repo, "v0.20.0")
    make_tut(repo, "d", versions={"default": "v0.20.0", "tested": ["v0.20.0"]})
    make_revision(repo, "d", "v0.17", ["v0.17.0", "v0.18.0"])
    assert ("R001", "tutorials/d/revisions/v0.17/tutorial.yaml") in errors(repo)


def test_R002_R004_frozen_revision_and_removed_versions(repo):
    pin(repo, "v0.19.0")
    make_tut(repo, "a", versions={"default": "v0.18.0", "tested": ["v0.18.0"]})
    commit_all(repo)
    base = git(repo, "rev-parse", "HEAD").strip()
    (repo / "tutorials" / "a" / "tutorial.yaml").write_text(yaml.safe_dump(
        meta("a", versions={"default": "v0.19.0", "tested": ["v0.19.0"]})))
    commit_all(repo, "drop v0.18")
    assert ("R004", "tutorials/a/tutorial.yaml") in errors(repo, base)
    make_revision(repo, "a", "v0.18", ["v0.18.0"])
    commit_all(repo, "keep it")
    assert errors(repo, base) == []
    base2 = git(repo, "rev-parse", "HEAD").strip()
    (repo / "tutorials" / "a" / "revisions" / "v0.18" / "README.md").write_text(GOOD_README + "\nfix\n")
    commit_all(repo, "touch the revision")
    assert ("R002", "tutorials/a/revisions/v0.18") in errors(repo, base2)


# ------------------------------------------------------- catalog, site, CLI
def test_catalog_site_and_release_see_revisions(repo, tmp_path):
    make_tut(repo, "a", versions={"default": "v0.19.0", "tested": ["v0.19.0"]})
    make_revision(repo, "a", "v0.18", ["v0.18.0"])
    (repo / "catalog" / "collections").mkdir(parents=True)
    (repo / "catalog" / "collections" / "p.yaml").write_text(yaml.safe_dump(
        {"id": "p", "title": {"en": "P"}, "description": {"en": "d"}, "owners": ["x"], "members": ["a"]}))
    col = catalog.load_collections(repo)[0]
    by_id = {t.id: t for t in model.load_tutorials(repo)}
    item = catalog.resolve(col, by_id, "v0.18.0")[0]
    assert item["state"] == "ok" and item["revision"] == "v0.18"
    assert catalog.resolve(col, by_id, "v0.17.0")[0]["state"] == "unavailable"
    generate.sync(repo)
    rev_readme = repo / "tutorials" / "a" / "revisions" / "v0.18" / "README.md"
    rev_readme.write_text(rev_readme.read_text() + "\nCurrent tutorial: [a](../../README.md)\n")
    out = site.build_source(tmp_path / "site", repo)
    assert (out / "tutorials" / "a" / "revisions" / "v0.18" / "index.md").exists()
    # README links between the tutorial and its revision follow the renaming (mkdocs --strict)
    cur, old = (out / "tutorials" / "a" / "index.md").read_text(), (out / "tutorials" / "a" / "revisions" / "v0.18" / "index.md").read_text()
    assert "](revisions/v0.18/index.md)" in cur and "README.md)" not in cur
    assert "](../../index.md)" in old and "README.md)" not in old
    assert "tutorials/a/revisions/v0.18/index.md) (v0.18, an older revision)" in (out / "versions.md").read_text()
    assert "a (v0.18)](tutorials/a/revisions/v0.18/)" in (repo / "README.md").read_text() \
        if (repo / "README.md").exists() else True


def test_tested_add_appends_to_the_list(repo, monkeypatch):
    from tut import cli
    d = make_tut(repo, "a")
    (d / "tutorial.yaml").write_text("id: a\nversions:\n  default: v0.18.0\n  tested: [v0.18.0]   # weekly\n")
    monkeypatch.setattr(cli, "REPO_ROOT", repo)
    monkeypatch.setattr(cli, "_tutorial", lambda tid: model.load_tutorials(repo)[0])
    cli.cmd_tested(type("A", (), {"version": "v0.19.0", "ids": ["a"], "all": False}))
    assert "  tested: [v0.18.0, v0.19.0]   # weekly" in (d / "tutorial.yaml").read_text()


def test_ui_serves_the_revision_for_rev(repo):
    from aiohttp.test_utils import TestClient, TestServer
    from tut.ui.server import UI
    make_tut(repo, "a", versions={"default": "v0.19.0", "tested": ["v0.19.0"]})
    d = make_revision(repo, "a", "v0.18", ["v0.18.0"])
    (d / "README.md").write_text(GOOD_README.replace("# T\n", "# T\n\nOLD TEXT\n"))
    generate.sync(repo)

    async def main():
        ui = UI(repo)
        async with TestClient(TestServer(ui.app())) as c:
            h = {"X-Tut-Token": ui.token}
            lst = await (await c.get("/api/tutorials", headers=h)).json()
            assert lst["versions"] == ["v0.19.0", "v0.18.0"]
            assert lst["tutorials"][0]["revisions"][0]["rev"] == "v0.18"
            cur = await (await c.get("/api/tutorials/a?lang=en", headers=h)).json()
            old = await (await c.get("/api/tutorials/a?lang=en&rev=v0.18", headers=h)).json()
            assert cur["revision"] is None and "OLD TEXT" not in cur["html"]
            assert old["revision"] == "v0.18" and "OLD TEXT" in old["html"]
            assert (await c.get("/api/tutorials/a?rev=r9", headers=h)).status == 404
    asyncio.run(main())
