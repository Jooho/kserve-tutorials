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
