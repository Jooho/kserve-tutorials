"""Release process: promote a verified `main` commit to the `stable` branch.

    main ──(every runnable tutorial × every tested version passes)──▶ stable + tag

Releases are named by date: YYYY.MM.N (N starts at 0 each month). `stable`
only ever moves forward to a commit of `main` (fast-forward), so there are no
back-ports and no merge commits. The GitHub workflow .github/workflows/release.yml
drives these functions; they are also usable locally (`./tut release ...`).
"""
from __future__ import annotations

import datetime as dt
import json
import re
import subprocess
from pathlib import Path

from . import project
from .model import REPO_ROOT, load_tutorials

TAG_RE = re.compile(r"^(\d{4})\.(\d{2})\.(\d+)$")
STABLE_BRANCH = "stable"


def _git(*args: str, root: Path = REPO_ROOT, check: bool = True) -> str:
    return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True,
                          check=check).stdout.strip()


def release_tags(root: Path = REPO_ROOT) -> list[str]:
    tags = [t for t in _git("tag", "--list", root=root).split("\n") if TAG_RE.match(t)]
    return sorted(tags, key=lambda t: tuple(int(x) for x in TAG_RE.match(t).groups()))


def next_version(today: dt.date | None = None, tags: list[str] | None = None,
                 root: Path = REPO_ROOT) -> str:
    today = today or dt.date.today()
    tags = release_tags(root) if tags is None else tags
    prefix = f"{today.year:04d}.{today.month:02d}."
    used = [int(TAG_RE.match(t).group(3)) for t in tags if t.startswith(prefix)]
    return f"{prefix}{max(used) + 1 if used else 0}"


def load_reports(reports_dir: Path) -> list[dict]:
    """Reports written by `tut run --report`, one per matrix entry
    (artifact layout: <dir>/report-<label>-<tutorial>-<version>/report.json)."""
    return [json.loads(p.read_text()) for p in sorted(Path(reports_dir).rglob("report.json"))]


def verdict(reports: list[dict], expected: list[dict]) -> tuple[bool, list[str]]:
    """Every expected {tutorial, version} must have a passing report."""
    problems = []
    got = {(r["tutorial"], r["version"]): r for r in reports}
    for e in expected:
        key = (e["tutorial"], e["version"])
        r = got.get(key)
        if r is None:
            problems.append(f"{key[0]} @ {key[1]}: no report (job did not run or crashed)")
        elif r["status"] != "passed":
            problems.append(f"{key[0]} @ {key[1]}: {r['status']} at {r.get('failed_at')}")
    return not problems, problems


def can_fast_forward(sha: str, root: Path = REPO_ROOT, remote: str = "origin") -> tuple[bool, str]:
    """`stable` may only move forward: the current tip must be an ancestor of sha."""
    tip = _git("rev-parse", "--verify", "-q", f"{remote}/{STABLE_BRANCH}", root=root, check=False)
    if not tip:
        return True, f"{STABLE_BRANCH} does not exist yet; it will be created at {sha[:7]}"
    if tip == sha:
        return False, f"{STABLE_BRANCH} is already at {sha[:7]}; nothing to release"
    ok = subprocess.run(["git", "merge-base", "--is-ancestor", tip, sha], cwd=root).returncode == 0
    if not ok:
        return False, (f"{STABLE_BRANCH} ({tip[:7]}) is not an ancestor of {sha[:7]}; "
                       "refusing to rewrite it")
    return True, f"{STABLE_BRANCH} fast-forwards {tip[:7]} → {sha[:7]}"


def notes(version: str, sha: str, reports: list[dict], repo: str = "<owner>/<repo>",
          root: Path = REPO_ROOT) -> str:
    tags = [t for t in release_tags(root) if t != version]
    prev = tags[-1] if tags else None
    proj = project.load(root)
    out = [f"## {proj.text('title')} {version}", "",
           f"Commit `{sha[:7]}` of `main`, promoted to `{STABLE_BRANCH}` after every runnable "
           f"tutorial and revision passed on every {proj.name} version CI runs for it (N and N-1).", "",
           "```bash", f"git clone -b {version} https://github.com/{repo}.git", "```", ""]
    out += ["### Verification", "", f"| Tutorial | {proj.name} | Result | Duration |", "|---|---|---|---|"]
    for r in sorted(reports, key=lambda r: (r["tutorial"], r["version"])):
        icon = "✅" if r["status"] == "passed" else "❌"
        out.append(f"| {r['tutorial']} | {r['version']} | {icon} | "
                   f"{round(r.get('duration_seconds', 0) / 60)} min |")
    if not reports:
        out.append("| — | — | no CI-runnable tutorials | — |")
    out += ["", "### Tutorials in this release", "",
            f"| Tutorial | Status | Tested {proj.name} | Environment |", "|---|---|---|---|"]
    from .model import ci_minors, pinned_minor, runs_in_ci, variants
    tutorials = load_tutorials(root)
    n = pinned_minor(tutorials, root)
    for t in tutorials:
        ms = ci_minors(t, n)
        for v in variants(t):
            if v.errors:
                continue
            note = "" if v.ci_runnable else " (not run in CI)"
            tested = ", ".join(x if runs_in_ci(x, ms) else f"{x} (last verified earlier, not run)"
                               for x in v.tested_versions)
            out.append(f"| {v.key} | {v.status}{note} | {tested} | `{v.env_ref}` |")
    if prev:
        changed = _git("diff", "--name-only", f"{prev}..{sha}", root=root).split("\n")
        parts = sorted({"/".join(Path(p).parts[:2]) if p.startswith("tutorials/") else
                        "/".join(Path(p).parts[:3]) for p in changed
                        if p.startswith(("tutorials/", "envs/", "lib/"))})
        log = _git("log", "--no-merges", "--format=- %s (%h)", f"{prev}..{sha}", root=root)
        out += ["", f"### Changes since {prev}", ""]
        out += [f"- `{p}`" for p in parts] or ["- no tutorial, environment or module changes"]
        out += ["", "<details><summary>Commits</summary>", "", log or "(none)", "", "</details>"]
    else:
        out += ["", "### Changes", "", "First release."]
    return "\n".join(out) + "\n"
