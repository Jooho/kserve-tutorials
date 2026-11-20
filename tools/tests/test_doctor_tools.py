"""Tutorial tools are owned by environments (envs/*/tools.env), installed into
.tools/<tool>/<version>/ and put on PATH only by the generated setup step."""
from __future__ import annotations

from tut import doctor, generate
from tut.model import REPO_ROOT, load_tutorials

TOOLS_ENV = "KIND=v0.30.0   # comment\nKUBECTL=v1.34.13\nHELM=\nCLOUD_PROVIDER_KIND=v0.12.0\n"


def test_env_tools_are_parsed_and_empty_entries_skipped(tmp_path):
    d = tmp_path / "envs" / "x" / "v1"
    d.mkdir(parents=True)
    (d / "tools.env").write_text(TOOLS_ENV)
    assert doctor.env_tools("x/v1", tmp_path) == {
        "kind": "v0.30.0", "kubectl": "v1.34.13", "cloud-provider-kind": "v0.12.0"}
    assert generate.env_tool_dirs("x/v1", tmp_path) == [
        "$REPO_ROOT/.tools/kind/v0.30.0", "$REPO_ROOT/.tools/kubectl/v1.34.13",
        "$REPO_ROOT/.tools/cloud-provider-kind/v0.12.0"]


def test_setup_block_puts_env_tools_on_path_before_env_setup():
    t = next(t for t in load_tutorials(REPO_ROOT) if t.id == "llmisvc-anatomy")
    block = generate.render_setup(t)
    path_line = next(i for i, l in enumerate(block.splitlines()) if l.startswith("export PATH="))
    setup_line = next(i for i, l in enumerate(block.splitlines()) if l.endswith("/setup.sh\""))
    assert path_line < setup_line
    assert "$REPO_ROOT/.tools/kind/" in block and "~/.bashrc" not in block


def test_doctor_toolkit_only_checks_python_side():
    sections = doctor.run_checks(toolkit_only=True)
    assert [n for n, _ in sections] == ["toolkit (./tut, make setup)"]
    assert {c.name for c in sections[0][1]} == {"python", "python packages", "AI CLI"}


def test_doctor_never_installs_docker():
    src = (REPO_ROOT / "tools" / "install-tools.sh").read_text()
    wanted = [l.split()[2] for l in src.splitlines() if l.startswith("if want ")]
    assert wanted == ["kind", "kubectl", "helm", "cloud-provider-kind"]   # Docker is the user's


def test_python_packages_follow_requirements_txt(tmp_path):
    """A .venv made before a package was added (e.g. pyte) must be reported."""
    from importlib import metadata
    from tut import doctor
    req = tmp_path / "requirements.txt"
    req.write_text(f"pytest=={metadata.version('pytest')}\n"
                   "pyyaml==0.0.1\n"
                   "# a comment\n"
                   "surely-not-installed-pkg==1.0\n")
    missing, other = doctor.python_packages(req)
    assert missing == ["surely-not-installed-pkg"]
    assert len(other) == 1 and other[0].startswith("pyyaml ") and "pinned 0.0.1" in other[0]
