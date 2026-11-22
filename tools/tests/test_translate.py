"""AI translation drafts: any CLI via TUT_TRANSLATOR, output checked before writing."""
from __future__ import annotations

import re
import sys

import pytest

from tut import lint, translate
from tut.model import load_tutorials
from test_rules import GOOD_README, make_env, make_tut  # noqa: E402

FAKE = r'''
import sys
prompt = sys.stdin.read()
src = prompt.split("=== README.md (English source) ===\n", 1)[1]
mode = sys.argv[1]
if mode == "nomarkers":
    print(src); sys.exit(0)
out = src.replace("# T", "# 티").replace("kubectl get cm x", "kubectl get cm y" if mode == "breaks" else "kubectl get cm x")
print("<<<TUT-TRANSLATION-BEGIN>>>\n" + out + "\n<<<TUT-TRANSLATION-END>>>")
'''


@pytest.fixture
def fake(tmp_path, monkeypatch):
    script = tmp_path / "fake.py"
    script.write_text(FAKE)
    def use(mode):
        monkeypatch.setenv("TUT_TRANSLATOR", f"cmd:{sys.executable} {script} {mode}")
        return translate.configured()
    return use


def test_presets_and_unknown_translator(monkeypatch):
    monkeypatch.setenv("TUT_TRANSLATOR", "claude")
    monkeypatch.setenv("TUT_TRANSLATOR_ARGS", "--model sonnet")
    tr = translate.configured()
    assert tr.argv[:4] == ["claude", "-p", "--model", "sonnet"] and "{prompt}" in tr.argv
    monkeypatch.setenv("TUT_TRANSLATOR", "gemini")
    with pytest.raises(translate.TranslationError):
        translate.configured()


def test_good_translation_passes_the_check(fake):
    out = translate.run(fake("good"), translate.build_prompt(GOOD_README, "ko"))
    text = translate.extract(out)
    assert "# 티" in text and translate.check(GOOD_README, text) == []


def test_changed_command_is_rejected(fake):
    text = translate.extract(translate.run(fake("breaks"), translate.build_prompt(GOOD_README, "ko")))
    assert any("code changed" in p for p in translate.check(GOOD_README, text))


def test_output_without_markers_is_an_error(fake):
    out = translate.run(fake("nomarkers"), translate.build_prompt(GOOD_README, "ko"))
    with pytest.raises(translate.TranslationError):
        translate.extract(out)


def test_comments_in_code_may_be_translated():
    src = GOOD_README.replace('kubectl get cm x -n "$NS"', 'kubectl get cm x -n "$NS"  # check it')
    tr = src.replace("# check it", "# 확인")
    assert translate.check(src, tr) == []


def test_draft_state_then_mark(repo):
    d = make_tut(repo, "t")
    t = next(x for x in load_tutorials(repo) if x.id == "t")
    lint.write_draft(t, "ko", GOOD_README.replace("# T", "# 티"), "claude")
    t = next(x for x in load_tutorials(repo) if x.id == "t")
    assert lint.translation_state(t, "ko") == "draft"
    assert "by=claude reviewed=no" in (d / "README.ko.md").read_text()
    lint.mark_translation(t, "ko")
    assert lint.translation_state(t, "ko") == "current"


@pytest.fixture
def repo(tmp_path):
    make_env(tmp_path)
    return tmp_path


def test_precommit_translate_drafts_every_missing_translation(tmp_path, monkeypatch, capsys):
    """make precommit TRANSLATE=1 = `./tut translation draft --all` (every language),
    and `./tut translation todo` prints what is left; nothing when all is current."""
    from tut import cli, generate
    repo = tmp_path / "repo"
    make_env(repo)
    make_tut(repo, "a", status="draft")
    generate.sync(repo)
    monkeypatch.setattr(cli, "REPO_ROOT", repo)
    script = tmp_path / "fake.py"
    script.write_text(FAKE)
    monkeypatch.delenv("TUT_TRANSLATOR", raising=False)
    monkeypatch.setenv("TUT_AI", f"cmd:{sys.executable} {script} good")

    cli.main(["translation", "todo"])
    out = capsys.readouterr().out
    assert "TRANSLATE=1" in out
    assert re.search(r"^\s+ko\s+not translated\s+a$", out, re.M), out

    assert cli.main(["translation", "draft", "--all"]) == 0          # no language: every language
    t = next(x for x in load_tutorials(repo) if x.id == "a")
    assert (t.path / "README.ko.md").exists() and lint.translation_state(t, "ko") == "draft"

    capsys.readouterr()
    cli.main(["translation", "todo"])
    out = capsys.readouterr().out
    assert "waiting for a review" in out and "./tut translation mark a ko" in out
    lint.mark_translation(t, "ko")
    capsys.readouterr()
    cli.main(["translation", "todo"])
    assert capsys.readouterr().out == ""
