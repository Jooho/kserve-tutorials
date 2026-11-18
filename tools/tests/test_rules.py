"""Tests for the rules themselves. Each test builds a tiny repository in tmp_path."""
from __future__ import annotations

import json
import subprocess
import textwrap
from pathlib import Path

import pytest
import yaml

from tut import generate, lint, markdown, plan, runner
from tut.model import load_tutorials

GOOD_README = """\
# T

<!-- tut:header -->
<!-- /tut -->

<!-- tut:setup -->
<!-- /tut -->

```bash run
kubectl apply -f manifests/cm.yaml -n "$NS"
```

<!-- tut:include manifests/cm.yaml -->
<!-- /tut -->

```bash verify
kubectl get cm x -n "$NS"
```

```bash cleanup
kubectl delete ns "$NS"
```
"""


def meta(tid, **kw):
    m = {"id": tid, "title": {"en": tid}, "summary": {"en": "s"}, "status": "stable",
         "env": "kind-x/v1", "kserve": {"default": "v0.18.0", "tested": ["v0.18.0"]},
         "langs": ["en"]}
    m.update(kw)
    return m


def make_env(root: Path, ref="kind-x/v1", frozen=True, kmin="v0.17.0"):
    d = root / "envs" / ref
    d.mkdir(parents=True)
    (d / "profile.yaml").write_text(yaml.safe_dump(
        {"id": ref, "description": "d", "frozen": frozen, "kserve": {"min": kmin}, "requires": []}))
    for s in ("setup.sh", "teardown.sh"):
        (d / s).write_text("#!/bin/sh\n")
        (d / s).chmod(0o755)
    (d / "README.md").write_text("# env\n")


def make_tut(root: Path, tid, readme=GOOD_README, **kw):
    d = root / "tutorials" / tid
    (d / "manifests").mkdir(parents=True)
    (d / "manifests" / "cm.yaml").write_text("kind: ConfigMap\nmetadata: {name: x}\n")
    (d / "tutorial.yaml").write_text(yaml.safe_dump(meta(tid, **kw)))
    (d / "README.md").write_text(readme)
    return d


def codes(root, base=None):
    generate.sync(root)
    return sorted({f.code for f in lint.Linter(root, base=base).run() if f.severity == "error"})


@pytest.fixture
def repo(tmp_path):
    make_env(tmp_path)
    return tmp_path


# ------------------------------------------------------------------ parsing
def test_parse_roles_and_regions():
    doc = markdown.parse(GOOD_README)
    assert [b.role for b in doc.blocks] == ["run", "verify", "cleanup"]
    assert [r.kind for r in doc.regions] == ["header", "setup", "include"]


def test_good_tutorial_is_clean(repo):
    make_tut(repo, "good")
    assert codes(repo) == []


# -------------------------------------------------------------------- rules
def test_D001_shell_block_without_role(repo):
    make_tut(repo, "t", GOOD_README.replace("```bash verify", "```bash"))
    assert "D001" in codes(repo)


def test_D002_stale_generated_region(repo):
    d = make_tut(repo, "t")
    generate.sync(repo)
    (d / "manifests" / "cm.yaml").write_text("kind: ConfigMap\nmetadata: {name: changed}\n")
    found = {f.code for f in lint.Linter(repo).run()}
    assert "D002" in found


def test_D003_hardcoded_version(repo):
    make_tut(repo, "t", GOOD_README + "\nInstall KServe v0.18.0 first.\n")
    assert "D003" in codes(repo)


def test_D003_escape_hatch(repo):
    make_tut(repo, "t", GOOD_README + "\nSince KServe v0.15 this works. <!-- tut-allow-version -->\n")
    assert "D003" not in codes(repo)


def test_D004_broken_link(repo):
    make_tut(repo, "t", GOOD_README + "\nSee [next](../does-not-exist/).\n")
    assert "D004" in codes(repo)


def test_D005_include_outside_tutorial(repo):
    make_tut(repo, "other")
    make_tut(repo, "t", GOOD_README.replace(
        "<!-- tut:include manifests/cm.yaml -->", "<!-- tut:include ../other/manifests/cm.yaml -->"))
    assert "D005" in codes(repo)


def test_D006_run_before_setup(repo):
    make_tut(repo, "t", "```bash run\necho hi\n```\n\n" + GOOD_README)
    assert "D006" in codes(repo)


def test_D007_stable_needs_verify_but_draft_only_warns(repo):
    no_verify = GOOD_README.replace("```bash verify", "```bash run")
    make_tut(repo, "s", no_verify)
    make_tut(repo, "d", no_verify, status="draft")
    generate.sync(repo)
    errs = [(f.code, f.path.parent.name) for f in lint.Linter(repo).run() if f.severity == "error"]
    assert ("D007", "s") in errs and ("D007", "d") not in errs


def test_M001_unpinned_image(repo):
    d = make_tut(repo, "t")
    (d / "manifests" / "pod.yaml").write_text("spec:\n  containers:\n  - image: nginx\n")
    assert "M001" in codes(repo)


def test_T004_default_not_tested(repo):
    make_tut(repo, "t", kserve={"default": "v0.19.0", "tested": ["v0.18.0"]})
    assert "T004" in codes(repo)


def test_T005_version_outside_env_range(repo):
    make_tut(repo, "t", kserve={"default": "v0.16.0", "tested": ["v0.16.0"]})
    assert "T005" in codes(repo)


def test_T006_archived_needs_deprecation(repo):
    make_tut(repo, "t", status="archived")
    assert "T006" in codes(repo)


def test_T007_stable_needs_frozen_env(tmp_path):
    make_env(tmp_path, "kind-x/v1", frozen=False)
    make_tut(tmp_path, "t")
    assert "T007" in codes(tmp_path)


# -------------------------------------------------------------- translation
def test_translation_marker_staleness_and_structure(repo):
    d = make_tut(repo, "t", langs=["en", "ko"])
    (d / "README.ko.md").write_text(GOOD_README)
    assert "D010" in codes(repo)                       # marker missing -> error
    t = next(t for t in load_tutorials(repo) if t.id == "t")
    lint.mark_translation(t, "ko")
    assert codes(repo) == []
    (d / "README.md").write_text(GOOD_README + "\nNew paragraph.\n")
    warnings = {f.code for f in lint.Linter(repo).run() if f.severity == "warning"}
    assert "D010" in warnings                          # stale -> warning only
    (d / "README.ko.md").write_text((d / "README.ko.md").read_text()
                                    .replace("```bash verify", "```bash run"))
    assert "D011" in codes(repo)                       # structure drift -> error


def test_sync_alone_never_stales_translation(repo):
    d = make_tut(repo, "t", langs=["en", "ko"])
    (d / "README.ko.md").write_text(GOOD_README)
    generate.sync(repo)
    lint.mark_translation(next(t for t in load_tutorials(repo) if t.id == "t"), "ko")
    (d / "manifests" / "cm.yaml").write_text("kind: ConfigMap\nmetadata: {name: y}\n")
    generate.sync(repo)
    assert not [f for f in lint.Linter(repo).run() if f.code == "D010"]


# ----------------------------------------------------------- blast radius
def test_affected_env_change_hits_only_its_users(repo):
    make_env(repo, "kind-x/v2")
    make_tut(repo, "a")
    make_tut(repo, "b", env="kind-x/v2")
    make_tut(repo, "c")
    ts = load_tutorials(repo)
    assert [t.id for t in plan.affected(["envs/kind-x/v2/setup.sh"], ts)] == ["b"]
    assert [t.id for t in plan.affected(["tutorials/c/README.md"], ts)] == ["c"]
    assert plan.affected(["tools/tut/lint.py", "README.md"], ts) == []


def test_E002_frozen_env_cannot_change(repo):
    make_tut(repo, "t")
    git = lambda *a: subprocess.run(["git", *a], cwd=repo, check=True, capture_output=True)
    git("init", "-q", "-b", "main")
    git("-c", "user.email=t@t", "-c", "user.name=t", "add", ".")
    git("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "base")
    (repo / "envs/kind-x/v1/setup.sh").write_text("#!/bin/sh\necho changed\n")
    git("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qam", "edit")
    assert "E002" in codes(repo, base="HEAD~1")


# ------------------------------------------------------------------ runner
RUNNABLE = """\
```bash run
X=1
```

```bash verify retry=3 delay=0
test -f "$MARK" || { touch "$MARK"; false; }
```

```bash run
echo "x is $X"
```

```bash verify
test "$X" = "2"
```

```bash cleanup
echo cleaned > "$OUT"
```
"""


def test_runner_reports_failing_block_and_always_cleans_up(tmp_path, monkeypatch):
    d = make_tut(tmp_path, "t", RUNNABLE)
    monkeypatch.setattr(runner, "REPO_ROOT", tmp_path)
    t = next(t for t in load_tutorials(tmp_path) if t.id == "t")
    monkeypatch.setenv("MARK", str(tmp_path / "mark"))
    monkeypatch.setenv("OUT", str(tmp_path / "out"))
    report = tmp_path / "r.json"
    rc = runner.run(t, report=report)
    res = json.loads(report.read_text())
    assert rc != 0 and res["status"] == "failed"
    assert res["failed_at"].startswith("tutorials/t/README.md:13 (verify 4/4)")
    assert (tmp_path / "out").read_text().strip() == "cleaned"   # cleanup ran after failure
    assert (tmp_path / "mark").exists()                         # retry block retried and passed


# -------------------------------------------------------------------- site
def test_site_strips_roles_from_fences():
    from tut import site
    assert site._site_fence_info("```bash run") == "```bash"
    assert site._site_fence_info("```bash verify retry=3 delay=5") == '```bash title="✔ verify"'
    assert site._site_fence_info("```yaml") == "```yaml"


def test_generated_regions_are_padded_and_idempotent(repo):
    d = make_tut(repo, "t")
    generate.sync(repo)
    once = (d / "README.md").read_text()
    assert "<!-- tut:setup -->\n\n```bash run" in once
    generate.sync(repo)
    assert (d / "README.md").read_text() == once


# ----------------------------------------------------------------- modules
def make_module(root: Path, ref="helpers/v1", frozen=True):
    d = root / "lib" / ref
    d.mkdir(parents=True)
    (d / "module.yaml").write_text(yaml.safe_dump({"id": ref, "description": "d", "frozen": frozen}))
    (d / "hello.sh").write_text("#!/bin/sh\necho hello\n")
    (d / "hello.sh").chmod(0o755)
    return d


CALLS_MODULE = GOOD_README.replace(
    'kubectl get cm x -n "$NS"', '"$TUT_LIB/helpers/v1/hello.sh"\nkubectl get cm x -n "$NS"')


def test_L002_module_call_must_be_declared(repo):
    make_module(repo)
    make_tut(repo, "t", CALLS_MODULE)
    assert "L002" in codes(repo)
    make_tut(repo, "u", CALLS_MODULE, uses=["helpers/v1"])
    errs = [(f.code, f.path.parent.name) for f in lint.Linter(repo).run() if f.severity == "error"]
    assert ("L002", "u") not in errs


def test_L002_missing_module(repo):
    make_tut(repo, "t", uses=["nope/v1"])
    assert "L002" in codes(repo)


def test_L004_stable_needs_frozen_module(repo):
    make_module(repo, frozen=False)
    make_tut(repo, "t", CALLS_MODULE, uses=["helpers/v1"])
    assert "L004" in codes(repo)


def test_D005_include_from_declared_module_is_allowed(repo):
    make_module(repo)
    inc = GOOD_README + "\n<!-- tut:include ../../lib/helpers/v1/hello.sh -->\n<!-- /tut -->\n"
    make_tut(repo, "ok", inc, uses=["helpers/v1"])
    make_tut(repo, "bad", inc)
    generate.sync(repo)
    errs = [(f.code, f.path.parent.name) for f in lint.Linter(repo).run() if f.severity == "error"]
    assert ("D005", "bad") in errs and ("D005", "ok") not in errs


def test_affected_module_change_hits_only_its_users(repo):
    make_module(repo, "helpers/v1")
    make_module(repo, "helpers/v2")
    make_tut(repo, "a", uses=["helpers/v1"])
    make_tut(repo, "b", uses=["helpers/v2"])
    make_tut(repo, "c")
    ts = load_tutorials(repo)
    assert [t.id for t in plan.affected(["lib/helpers/v2/hello.sh"], ts)] == ["b"]


def test_L003_frozen_module_cannot_change(repo):
    make_module(repo)
    make_tut(repo, "t", CALLS_MODULE, uses=["helpers/v1"])
    git = lambda *a: subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", *a],
                                    cwd=repo, check=True, capture_output=True)
    git("init", "-q", "-b", "main"); git("add", "."); git("commit", "-qm", "base")
    (repo / "lib/helpers/v1/hello.sh").write_text("#!/bin/sh\necho changed\n")
    git("commit", "-qam", "edit")
    assert "L003" in codes(repo, base="HEAD~1")


def test_runner_keep_on_failure_skips_cleanup_only_on_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "REPO_ROOT", tmp_path)
    monkeypatch.setenv("OUT", str(tmp_path / "out"))
    ok = "```bash run\ntrue\n```\n\n```bash cleanup\necho cleaned > \"$OUT\"\n```\n"
    make_tut(tmp_path, "ok", ok)
    make_tut(tmp_path, "bad", ok.replace("true", "false"))
    ts = {t.id: t for t in load_tutorials(tmp_path)}
    assert runner.run(ts["bad"], keep_on_failure=True) != 0
    assert not (tmp_path / "out").exists()            # failed: resources kept for diagnostics
    assert runner.run(ts["ok"], keep_on_failure=True) == 0
    assert (tmp_path / "out").exists()                # passed: cleaned up as usual
