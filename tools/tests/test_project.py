"""project.yaml: the engine names no product. A repository for another project
(here a made-up "Kuadrant") gets its own labels, version variable and rules."""
from __future__ import annotations

import pytest

from tut import generate, lint, project, release, runner, translate
from tut.model import load_tutorials
from test_rules import GOOD_README, make_env, make_project, make_tut

KUADRANT = """\
id: kuadrant
name: Kuadrant
title: {en: Kuadrant Tutorials, ko: Kuadrant 튜토리얼}
version_var: KUADRANT_VERSION
upstream: kuadrant/kuadrant-operator
glossary: [Kuadrant, AuthPolicy, RateLimitPolicy]
"""


@pytest.fixture
def other(tmp_path):
    make_project(tmp_path, KUADRANT)
    make_env(tmp_path)
    make_tut(tmp_path, "t")
    generate.sync(tmp_path)
    return tmp_path


def tut(root):
    return next(t for t in load_tutorials(root) if t.id == "t")


def test_labels_and_version_variable_come_from_project_yaml(other):
    readme = (other / "tutorials" / "t" / "README.md").read_text()
    assert "**Tested with Kuadrant:** v0.18.0" in readme
    assert 'export KUADRANT_VERSION="${KUADRANT_VERSION:-v0.18.0}"' in readme
    assert "KSERVE" not in readme and "KServe" not in readme
    script, _ = runner.build_script(tut(other), "v0.19.0", keep=False)
    assert "export KUADRANT_VERSION=v0.19.0" in script


def test_D003_looks_for_the_projects_product_name(other):
    p = other / "tutorials" / "t" / "README.md"
    p.write_text(p.read_text() + "\nInstall Kuadrant v1.2.0 first.\nKServe v0.18.0 is another project.\n")
    d003 = [f for f in lint.Linter(other).run() if f.code == "D003"]
    assert len(d003) == 1 and "$KUADRANT_VERSION" in d003[0].message


def test_P001_missing_or_invalid_project_yaml(tmp_path):
    make_env(tmp_path)
    (tmp_path / "project.yaml").unlink()
    assert [f.code for f in lint.Linter(tmp_path).run()] == ["P001"]
    (tmp_path / "project.yaml").write_text("id: x\nname: X\ntitle: {en: X}\nversion_var: lower\n")
    f = lint.Linter(tmp_path).run()
    assert [x.code for x in f] == ["P001"] and "version_var" in f[0].message
    with pytest.raises(project.ProjectError):
        project.load(tmp_path)


def test_translation_keeps_the_projects_terms(other):
    prompt = translate.build_prompt(GOOD_README, "ko", project.load(other))
    assert "Translate this Kuadrant tutorial" in prompt
    assert "AuthPolicy" in prompt and "kubectl" in prompt and "InferenceService" not in prompt


def test_release_notes_use_the_project_title(other):
    import subprocess
    run = lambda *a: subprocess.run(["git", *a], cwd=other, check=True, capture_output=True)
    run("init", "-q", "-b", "main"); run("add", "."); run("commit", "-qm", "x")
    sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=other, capture_output=True, text=True).stdout.strip()
    text = release.notes("2026.11.0", sha, [], root=other)
    assert text.startswith("## Kuadrant Tutorials 2026.11.0") and "| Tutorial | Kuadrant |" in text


def test_cli_version_flag_and_project_alias():
    from tut import cli
    run = next(a for a in cli.build_parser()._subparsers._group_actions[0].choices["run"]._actions
               if a.dest == "version")
    assert run.option_strings == ["--version", "--kserve-version"]     # this repository: KServe


def test_ui_gets_the_project_for_its_labels(other):
    from test_shared import ui_get
    d = ui_get(other, "/api/tutorials")
    assert d["project"]["name"] == "Kuadrant" and d["project"]["title"]["en"] == "Kuadrant Tutorials"
    assert d["tutorials"][0]["versions"] == {"default": "v0.18.0", "tested": ["v0.18.0"]}
