"""`./tut draft`: material, guard rails and report, with a stand-in AI (cmd:)."""
from __future__ import annotations

import shutil
import subprocess
import sys
import textwrap

import pytest

from tut import draft
from tut.model import REPO_ROOT

FAKE_AI = textwrap.dedent('''
    import pathlib, re, sys
    prompt = sys.stdin.read()
    tid = re.search(r"tutorials/([a-z0-9-]+)/: the scaffold", prompt).group(1)
    work = re.search(r"write (build/draft/[a-z0-9-]+)/notes.md", prompt).group(1)
    t = pathlib.Path("tutorials") / tid
    readme = (t / "README.md").read_text()
    step = ("## Deploy\\n\\n![Architecture](images/arch.svg)\\n\\n```bash run\\nkubectl apply -f manifests/model.yaml -n \\"$NS\\"\\n```\\n\\n"
            "```bash verify retry=30 delay=10\\nkubectl wait -n \\"$NS\\" isvc/m --for=condition=Ready --timeout=10s\\n```\\n\\n")
    readme = re.sub(r"## Step 1:.*?(?=## |\\Z)", step, readme, count=1, flags=re.S)
    (t / "README.md").write_text(readme)
    (t / "manifests" / "model.yaml").write_text("kind: ConfigMap\\nmetadata: {name: m}\\n")
    pathlib.Path(work, "notes.md").write_text("Replaced `sleep 60` with kubectl wait.\\n")
    if "--touch-outside" in sys.argv:
        pathlib.Path("AGENTS.md").write_text(pathlib.Path("AGENTS.md").read_text() + "\\nx\\n")
''')


@pytest.fixture
def repo(tmp_path):
    for d in ("envs", "lib", "catalog", "schema", "docs"):
        shutil.copytree(REPO_ROOT / d, tmp_path / d)
    shutil.copytree(REPO_ROOT / "tutorials" / "_template", tmp_path / "tutorials" / "_template")
    shutil.copy(REPO_ROOT / "AGENTS.md", tmp_path / "AGENTS.md")
    (tmp_path / "catalog" / "collections").mkdir(exist_ok=True)
    for p in (tmp_path / "catalog" / "collections").glob("*.yaml"):
        p.unlink()                                   # no members in this tiny repo
    (tmp_path / ".github").mkdir()
    (tmp_path / "fake_ai.py").write_text(FAKE_AI)
    git = lambda *a: subprocess.run(["git", *a], cwd=tmp_path, check=True, capture_output=True)
    git("init", "-q", "-b", "main"); git("add", "."); git("commit", "-qm", "base")
    return tmp_path


@pytest.fixture
def work(tmp_path_factory):
    src = tmp_path_factory.mktemp("my-tested-work")
    (src / "scripts").mkdir()
    (src / "scripts" / "deploy.sh").write_text(textwrap.dedent('''\
        #!/bin/bash
        set -e
        GREEN='\\033[0;32m'
        print_ok() {
            echo -e "${GREEN}ok $1"
        }
        if ! command -v kubectl >/dev/null; then
            exit 1
        fi
        "${SCRIPT_DIR}/deploy.sh" --help
        kubectl apply -f manifests/model.yaml -n ${NAMESPACE}
        sleep 60
        kubectl get isvc -n "$NS" \\
          -o wide
        cat <<EOF | kubectl apply -f -
        kind: ConfigMap
        EOF
        echo done
        '''))
    (src / "notes.txt").write_text("tested on kind")
    (src / "images").mkdir()
    (src / "images" / "arch.svg").write_text("<svg xmlns='http://www.w3.org/2000/svg'/>")
    (src / "images" / "old.png").write_bytes(b"\x89PNG\r\n\x1a\n\0\0")
    (src / "models").mkdir()
    (src / "models" / "model.bst").write_bytes(b"\0\1binary")
    return src


def agent(*extra):
    return draft.Agent("cmd", [f"{sys.executable} fake_ai.py {' '.join(extra)}"], shell=True)


def test_script_commands_skip_decoration_and_join_continuations(work):
    cmds = [c for _, _, c in draft.script_commands(work)]
    assert cmds == ["kubectl apply -f manifests/model.yaml -n ${NAMESPACE}", "sleep 60",
                    'kubectl get isvc -n "$NS" -o wide', "cat <<EOF | kubectl apply -f -"]


def test_draft_end_to_end_with_a_stand_in_ai(repo, work):
    before = sorted(p.name for p in work.rglob("*"))
    r = draft.draft(work, None, "My tested work", agent(), root=repo, log=lambda *_: None)
    t = repo / "tutorials" / r.tid
    assert r.tid == work.name and t.is_dir()
    assert sorted(p.name for p in work.rglob("*")) == before          # original untouched
    assert (r.work / "input" / "scripts" / "deploy.sh").exists()
    assert "kind-llmisvc/v1" in (r.work / "parts.md").read_text()
    assert "./tut _draftcheck" in (r.work / "prompt.md").read_text()
    assert r.outside == [] and r.agent_rc == 0
    assert [c for _, _, c in r.found] == ["kubectl apply -f manifests/model.yaml -n ${NAMESPACE}"]  # $NS in the tutorial
    assert {c for _, _, c in r.missing} == {"sleep 60", 'kubectl get isvc -n "$NS" -o wide',
                                            "cat <<EOF | kubectl apply -f -"}
    report = (r.work / "report.md").read_text()
    assert "in the tutorial (variable names may differ): 1/4" in report and "`sleep 60`" in report
    assert not (repo / "tutorials" / r.tid / "manifests" / "example.yaml").exists()   # template leftover removed
    assert not [f for f in r.problems if f.severity == "error"], r.problems


def test_changes_outside_the_tutorial_are_reported(repo, work):
    r = draft.draft(work, "outside-test", None, agent("--touch-outside"), root=repo, log=lambda *_: None)
    assert r.outside == ["AGENTS.md"]
    assert "Changed outside the allowed folders" in (r.work / "report.md").read_text()


def test_bad_input(repo, tmp_path):
    with pytest.raises(draft.DraftError):
        draft.draft(tmp_path / "nope", None, None, agent(), root=repo)


def test_agent_from_env(monkeypatch):
    monkeypatch.delenv("TUT_TRANSLATOR", raising=False)
    monkeypatch.setenv("TUT_AI", "claude")
    monkeypatch.setenv("TUT_AI_ARGS", "--model sonnet")
    a = draft.agent_from_env()
    assert a.argv[:4] == ["claude", "-p", "--model", "sonnet"] and "Bash(./tut _draftcheck:*)" in " ".join(a.argv)
    monkeypatch.setenv("TUT_AI", "nope")
    with pytest.raises(draft.DraftError):
        draft.agent_from_env()


def test_images_and_binaries_are_copied_in_and_unused_ones_removed(repo, work):
    r = draft.draft(work, "with-images", None, agent(), root=repo, log=lambda *_: None)
    t = repo / "tutorials" / "with-images"
    assert (t / "images" / "arch.svg").exists()                 # linked from README: kept
    assert not (t / "images" / "old.png").exists()              # nothing refers to it: removed
    assert not (t / "models").exists()                          # unused binary: removed, empty dir too
    assert r.assets_kept == ["images/arch.svg"]
    assert sorted(r.assets_removed) == ["images/old.png", "manifests/example.yaml (template)", "models/model.bst"]
    assert "images/arch.svg" in (r.work / "prompt.md").read_text()
    assert not [f for f in r.problems if f.code == "D004"]       # no broken image link
