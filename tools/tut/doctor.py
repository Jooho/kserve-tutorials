"""`./tut doctor`: is this machine ready to run the tutorials?

Checks what most often makes "it works in CI" fail locally: Python, OS and
architecture, Docker running and the CPU/memory it may use, the pinned tool
versions (tools/versions.env), an existing kind cluster, free disk.
Runs in `make setup`, in CI and before a tutorial, so it is tested all the time.
"""
from __future__ import annotations

import json
import os
import platform
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from .model import REPO_ROOT, env_tools, load_tutorials

OK, WARN, FAIL = "ok", "warn", "fail"
ICON = {OK: "✅", WARN: "⚠️ ", FAIL: "❌"}
GIB = 1024 ** 3


@dataclass
class Check:
    name: str
    status: str
    detail: str
    fix: str = ""          # may span several lines


def cluster_name() -> tuple[str, str]:
    """(name, where it came from) — shell > .tut.env > default."""
    name = os.environ.get("KIND_CLUSTER_NAME")
    if name is None:
        return "kind", "default"
    loaded = (os.environ.get("TUT_CONFIG_LOADED") or "").split()
    return name, ".tut.env" if "KIND_CLUSTER_NAME" in loaded else "shell"


def python_packages(req: Path = REPO_ROOT / "tools" / "requirements.txt") -> tuple[list[str], list[str]]:
    """(missing, other version) for the pins in tools/requirements.txt, so a
    .venv made before a package was added or bumped is noticed."""
    from importlib import metadata
    missing, other = [], []
    for line in req.read_text().splitlines():
        m = re.match(r"^\s*([A-Za-z0-9_.-]+)\s*==\s*(\S+)", line)
        if not m:
            continue
        name, want = m.groups()
        try:
            have = metadata.version(name)
        except metadata.PackageNotFoundError:
            missing.append(name)
            continue
        if have != want:
            other.append(f"{name} {have} (pinned {want})")
    return missing, other


def _run(cmd: list[str], timeout: float = 15) -> tuple[int, str]:
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return p.returncode, (p.stdout + p.stderr).strip()
    except (OSError, subprocess.TimeoutExpired) as e:
        return 127, str(e)


def requirements(root: Path, tutorial: str | None) -> tuple[int, float, str]:
    """CPU and memory (GiB) the selected tutorial (or the most demanding one) needs."""
    cpu, mem, who = 0, 0.0, ""
    for t in load_tutorials(root):
        if t.errors or (tutorial and t.id != tutorial):
            continue
        req = t.meta.get("requires") or {}
        c = int(req.get("cpu", 0))
        m = str(req.get("memory", "0Gi"))
        g = float(m[:-2]) if m.endswith("Gi") else float(m[:-2]) / 1024
        if (c, g) > (cpu, mem):
            cpu, mem, who = c, g, t.id
    return cpu, mem, who


def toolkit_checks() -> list[Check]:
    """What ./tut itself needs (make setup)."""
    v = sys.version_info
    checks = [Check("python", OK if v >= (3, 11) else FAIL, platform.python_version(),
                    "" if v >= (3, 11) else "install Python 3.11+")]
    from . import translate
    try:
        tr = translate.configured()
        checks_tr = (Check("AI CLI", OK, "not set (optional: TUT_AI=claude|copilot|codex, for draft and translation)")
                     if tr is None else
                     Check("AI CLI", OK if tr.available else WARN,
                           f"{tr.name}" + ("" if tr.available else f": `{tr.argv[0]}` not on PATH"),
                           "" if tr.available else f"install or log in to the {tr.name} CLI"))
    except translate.TranslationError as e:
        checks_tr = Check("AI CLI", WARN, str(e))
    missing, other = python_packages()
    venv = sys.prefix != sys.base_prefix
    detail = "; ".join(x for x in (f"missing: {', '.join(missing)}" if missing else "",
                                   f"other version: {', '.join(other)}" if other else "") if x)
    checks.append(Check("python packages", FAIL if missing else WARN if other else OK,
                        detail or ("as pinned, in .venv" if venv else "as pinned (no venv)"),
                        "make setup   (installs the versions pinned in tools/requirements.txt)"
                        if missing or other else ""))
    checks.append(checks_tr)
    return checks


def host_checks(root: Path, tutorial: str | None) -> list[Check]:
    """Can this machine run kind? We check, we do not install (Docker is yours)."""
    checks: list[Check] = []
    osname, arch = platform.system(), platform.machine().lower()
    arch = {"x86_64": "amd64", "aarch64": "arm64"}.get(arch, arch)
    if osname == "Linux" and arch == "amd64":
        checks.append(Check("platform", OK, f"linux/{arch} (same as CI)"))
    elif osname in ("Linux", "Darwin") and arch in ("amd64", "arm64"):
        extra = (" — cloud-provider-kind needs sudo; LoadBalancer IPs are reached via localhost"
                 if osname == "Darwin" else "")
        checks.append(Check("platform", WARN, f"{osname.lower()}/{arch}: not covered by CI{extra}",
                            "report problems with the issue template (docs/backlog.md B3)"))
    else:
        checks.append(Check("platform", FAIL, f"{osname}/{arch}", "use Linux, macOS or WSL2"))

    from .ui.session import pick_bash
    rc, out = _run([pick_bash(), "-c", "echo $BASH_VERSION"])
    major = int(out.split(".")[0]) if rc == 0 and out[:1].isdigit() else 0
    checks.append(Check("bash (UI terminal)", OK if major >= 4 else WARN,
                        f"{pick_bash()} {out if rc == 0 else '?'}",
                        "" if major >= 4 else "bash 3.2 (macOS default) works, but Tab completion is "
                        "limited: brew install bash"))

    for tool in ("git", "curl"):
        checks.append(Check(tool, OK if shutil.which(tool) else FAIL,
                            "found" if shutil.which(tool) else "not found",
                            "" if shutil.which(tool) else f"install {tool}"))

    if not shutil.which("docker"):
        checks.append(Check("docker", FAIL, "not installed",
                            "install Docker (Docker Desktop, colima, Docker Engine); we do not install it"))
    else:
        rc, out = _run(["docker", "info", "--format", "{{json .}}"])
        if rc != 0:
            checks.append(Check("docker", FAIL, "installed but not running", "start Docker"))
        else:
            info = json.loads(out)
            ncpu, memg = info.get("NCPU", 0), info.get("MemTotal", 0) / GIB
            need_cpu, need_mem, who = requirements(root, tutorial)
            low = ncpu < need_cpu or memg + 0.5 < need_mem
            checks.append(Check(
                "docker", WARN if low else OK,
                f"{info.get('ServerVersion', '?')}, {ncpu} CPU, {memg:.1f} GiB"
                + (f"; {who} asks for {need_cpu} CPU, {need_mem:g} GiB" if who else ""),
                "give Docker more CPU / memory" if low else ""))

    free = shutil.disk_usage(Path.home()).free / GIB
    checks.append(Check("disk", OK if free >= 20 else WARN, f"{free:.0f} GiB free",
                        "" if free >= 20 else "images and models need ~20 GiB"))
    return checks


def env_checks(root: Path, env_ref: str) -> list[Check]:
    """The env's pinned CLI tools (installed by its setup step) and its cluster."""
    checks: list[Check] = []
    tools = env_tools(env_ref, root)
    for name, version in tools.items():
        path = root / ".tools" / name / version / name
        checks.append(Check(f"{name} {version}", OK,
                            "downloaded (.tools/)" if path.exists()
                            else "not downloaded yet: the setup step installs it"))
    kind = root / ".tools" / "kind" / tools.get("kind", "-") / "kind"
    kind_cmd = str(kind) if kind.exists() else shutil.which("kind")
    cluster, source = cluster_name()
    checks.append(Check("cluster name", OK, f"'{cluster}' ({source}; change with "
                        "`make config CLUSTER=<name>`)"))
    if kind_cmd and shutil.which("docker"):
        _, out = _run([kind_cmd, "get", "clusters"])
        if cluster not in out.split():
            checks.append(Check("kind cluster", OK, f"no '{cluster}' cluster yet (setup creates it)"))
        else:
            kubectl = root / ".tools" / "kubectl" / tools.get("kubectl", "-") / "kubectl"
            kcmd = str(kubectl) if kubectl.exists() else (shutil.which("kubectl") or "kubectl")
            rc, marker = _run([kcmd, "--context", f"kind-{cluster}", "-n", "kube-system", "get",
                               "configmap", "tut-env", "-o",
                               "jsonpath={.data.profile}@{.data.kserve_version}"])
            if rc == 0 and marker:
                checks.append(Check("kind cluster", OK, f"'{cluster}' exists, built as {marker}"))
            else:
                checks.append(Check(
                    "kind cluster", WARN,
                    f"a kind cluster named '{cluster}' already exists and was not created by "
                    "these tutorials (it may hold your own work). The tutorial will not touch it "
                    "and will stop at the setup step.",
                    "keep it and let the tutorials use another cluster (remembered in .tut.env):\n"
                    "    make config CLUSTER=tut\n"
                    "or, if you no longer need it, delete it:\n"
                    f"    kind delete cluster --name {cluster}"))
    return checks


def run_checks(root: Path = REPO_ROOT, tutorial: str | None = None,
               toolkit_only: bool = False) -> list[tuple[str, list[Check]]]:
    sections = [("toolkit (./tut, make setup)", toolkit_checks())]
    if toolkit_only:
        return sections
    sections.append(("host: can it run kind? (you install Docker, git, curl)",
                     host_checks(root, tutorial)))
    envs = sorted({t.env_ref for t in load_tutorials(root)
                   if t.env_ref and not t.errors and (not tutorial or t.id == tutorial)})
    for e in envs:
        sections.append((f"environment {e} (tools are installed by its setup step)",
                         env_checks(root, e)))
    return sections


def report(sections: list[tuple[str, list[Check]]], as_json: bool = False) -> int:
    checks = [c for _, cs in sections for c in cs]
    if as_json:
        print(json.dumps([{"section": n, **c.__dict__} for n, cs in sections for c in cs], indent=2))
    else:
        for name, cs in sections:
            print(f"\n{name}")
            for c in cs:
                print(f"  {ICON[c.status]} {c.name:30} {c.detail}")
                if c.fix and c.status != OK:
                    first, *rest = c.fix.splitlines()
                    print(f"      → {first}")
                    for line in rest:
                        print(f"        {line}")
        n_fail = sum(c.status == FAIL for c in checks)
        n_warn = sum(c.status == WARN for c in checks)
        print(f"\n{n_fail} problem(s), {n_warn} warning(s)")
    return 1 if any(c.status == FAIL for c in checks) else 0
