"""Personal settings in .tut.env: shell > .tut.env > default, the same for ./tut,
the UI and someone pasting the README's setup block."""
from __future__ import annotations

import subprocess

from tut import doctor, generate
from tut.model import REPO_ROOT, load_tutorials

LOADER = REPO_ROOT / "tools" / "local-config.sh"


def load(tmp_path, content, pre=""):
    (tmp_path / "tools").mkdir()
    (tmp_path / "tools" / "local-config.sh").write_text(LOADER.read_text())
    (tmp_path / ".tut.env").write_text(content)
    script = f'set -u; {pre} source "{tmp_path}/tools/local-config.sh"; ' \
             'echo "${KIND_CLUSTER_NAME:-unset}|${KSERVE_VERSION:-unset}|$TUT_CONFIG_LOADED"'
    return subprocess.run(["bash", "-c", script], capture_output=True, text=True, check=True,
                          env={"PATH": "/usr/bin:/bin"}).stdout.strip()


def test_file_values_load_and_trim(tmp_path):
    assert load(tmp_path, "# c\nKIND_CLUSTER_NAME = tut  \nbad key=x\n") == "tut|unset| KIND_CLUSTER_NAME"


def test_shell_wins_over_file(tmp_path):
    out = load(tmp_path, "KIND_CLUSTER_NAME=tut\nKSERVE_VERSION=v9\n", pre="export KSERVE_VERSION=v0.18.0;")
    assert out == "tut|v0.18.0| KIND_CLUSTER_NAME"


def test_setup_block_loads_local_config_before_env_setup():
    t = next(t for t in load_tutorials(REPO_ROOT) if t.id == "llmisvc-anatomy")
    lines = generate.render_setup(t).splitlines()
    cfg = next(i for i, l in enumerate(lines) if "tools/local-config.sh" in l)
    setup = next(i for i, l in enumerate(lines) if l.endswith('/setup.sh"'))
    assert cfg < setup


def test_cluster_name_source(monkeypatch):
    monkeypatch.delenv("KIND_CLUSTER_NAME", raising=False)
    assert doctor.cluster_name() == ("kind", "default")
    monkeypatch.setenv("KIND_CLUSTER_NAME", "tut")
    monkeypatch.setenv("TUT_CONFIG_LOADED", " KIND_CLUSTER_NAME")
    assert doctor.cluster_name() == ("tut", ".tut.env")
    monkeypatch.setenv("TUT_CONFIG_LOADED", "")
    assert doctor.cluster_name() == ("tut", "shell")


def test_multiline_fix_is_printed_as_commands(capsys):
    c = doctor.Check("kind cluster", doctor.WARN, "exists", "keep it:\n    make config CLUSTER=tut")
    doctor.report([("env", [c])])
    out = capsys.readouterr().out
    assert "      → keep it:\n            make config CLUSTER=tut" in out
