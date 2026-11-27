"""Decide what CI should execute.

`./tut affected --base <ref>`  tutorials touched by a change (PR runs)
`./tut matrix --scheduled`      every runnable tutorial and revision x every tested version
`./tut matrix --canary <ver>`   stable/deprecated tutorials against a new version of the product

Only two minors run per tutorial (RFC 0002): N = the product's newest minor
(`./tut latest`: project.yaml `latest`, else the upstream's latest release; CI
sets TUT_LATEST_VERSION from it; offline without a pin, the newest any tutorial tests) if the tutorial tests it, and N-1 = the newest
minor it tests below N. A matrix entry names the tutorial and the
version; `./tut run <id> --version V` picks the revision tested with V.

Blast radius rules (the reason envs are versioned):
  tutorials/<id>/explainer/** -> nothing (an AI explainer is read, never executed)
  tutorials/<id>/revisions/rN/** -> <id> on rN's versions (a new revision proves itself)
  tutorials/<id>/**           -> <id>
  envs/<name>/<ver>/**        -> tutorials whose `env` is <name>/<ver>
  lib/<name>/<ver>/**         -> tutorials that list <name>/<ver> in `uses`
  how tutorials are executed  -> every tutorial (runner, markdown parser, generated
    (EXECUTION_PATHS)            setup step, tool installer, local config, CI job)
  anything else               -> nothing (lint and unit tests still run)
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from .model import (EXPLAINER_DIR, REPO_ROOT, REVISIONS_DIR, VERSION_RE, Tutorial, ci_minors,
                    latest, load_tutorials, minor, runs_in_ci, variants, version_key)


def changed_files(base: str, root: Path = REPO_ROOT) -> list[str]:
    out = subprocess.run(["git", "diff", "--name-only", f"{base}...HEAD"],
                         cwd=root, capture_output=True, text=True, check=True).stdout
    return [l for l in out.split("\n") if l]


# Files that change how *every* tutorial runs; a change here runs them all.
EXECUTION_PATHS = (
    "tools/tut/runner.py", "tools/tut/markdown.py", "tools/tut/generate.py",
    "tools/tut/project.py", "project.yaml",
    "tools/install-tools.sh", "tools/local-config.sh",
    ".github/workflows/run-tutorials.yml", ".github/scripts/diagnose.sh",
)


def affected(paths: list[str], tutorials: list[Tutorial]) -> list[Tutorial]:
    by_id = {t.id: t for t in tutorials}
    hit: dict[str, Tutorial] = {}
    if any(p in EXECUTION_PATHS for p in paths):
        return list(tutorials)
    for p in paths:
        parts = Path(p).parts
        if len(parts) >= 3 and parts[0] == "tutorials" and parts[2] == EXPLAINER_DIR:
            continue
        if len(parts) >= 2 and parts[0] == "tutorials" and parts[1] in by_id:
            hit[parts[1]] = by_id[parts[1]]
        elif len(parts) >= 3 and parts[0] == "envs":
            ref = f"{parts[1]}/{parts[2]}"
            for t in tutorials:
                if t.env_ref == ref:
                    hit[t.id] = t
        elif len(parts) >= 3 and parts[0] == "lib":
            ref = f"{parts[1]}/{parts[2]}"
            for t in tutorials:
                if ref in t.uses:
                    hit[t.id] = t
    return [t for t in tutorials if t.id in hit]


def entry(t: Tutorial, version: str) -> dict:
    """One CI job. `env` is the variant's (a revision may use an older env)."""
    return {"tutorial": t.id, "version": version, "env": t.env_ref, "revision": t.revision or ""}


def _runs(v: Tutorial, minors) -> list[dict]:
    """CI jobs of one variant: its tested versions in the tutorial's CI minors."""
    return [entry(v, x) for x in v.tested_versions if runs_in_ci(x, minors)] \
        if not v.errors and v.ci_runnable else []


def changed_revisions(paths: list[str], tid: str) -> set[str]:
    """rN directories of tutorial `tid` that a change touches."""
    out = set()
    for p in paths:
        parts = Path(p).parts
        if len(parts) >= 4 and parts[:3] == ("tutorials", tid, REVISIONS_DIR):
            out.add(parts[3])
    return out


def pr_matrix(base: str, root: Path = REPO_ROOT) -> list[dict]:
    """The affected current tutorials on their CI versions, and the revisions
    the change adds or touches (a frozen one cannot change: lint)."""
    paths = changed_files(base, root)
    tutorials = load_tutorials(root)
    n = latest(tutorials)
    out = []
    for t in affected(paths, tutorials):
        ms = ci_minors(t, n)
        out += _runs(t, ms)
        revs = changed_revisions(paths, t.id)
        out += [e for r in variants(t)[1:] if r.revision in revs for e in _runs(r, ms)]
    return out


def scheduled_matrix(root: Path = REPO_ROOT) -> list[dict]:
    """Every tutorial and revision CI can run, on its CI versions."""
    tutorials = load_tutorials(root)
    n = latest(tutorials)
    return [e for t in tutorials for v in variants(t) for e in _runs(v, ci_minors(t, n))]


def out_of_window(root: Path = REPO_ROOT) -> list[dict]:
    """Tested versions CI no longer runs (shown as "last verified")."""
    tutorials = load_tutorials(root)
    n = latest(tutorials)
    return [entry(v, x) for t in tutorials for v in variants(t) if not v.errors
            for x in v.tested_versions if not runs_in_ci(x, ci_minors(t, n))]


def skipped(root: Path = REPO_ROOT) -> list[dict]:
    """Current tutorials that skipped versions (RFC 0002 section 8): a gap
    between the minors of versions.tested (v0.18.0 and v0.20.0, nothing for
    v0.19). `versions` are the ones older than the newest gap; with the
    maintainer's permission `./tut revision keep <id>` moves them to a frozen
    revision. CI still runs N and the newest one below it (v0.20, v0.18)
    until then. A tutorial that has not moved to N yet is not a skip."""
    out = []
    for t in load_tutorials(root):
        if t.errors:
            continue
        vs = sorted((v for v in t.tested_versions if VERSION_RE.match(v)), key=version_key)
        ms = sorted({minor(v) for v in vs})
        gaps = [b for a, b in zip(ms, ms[1:]) if b[0] != a[0] or b[1] - a[1] > 1]
        if gaps:
            out.append({"tutorial": t.id, "versions": [v for v in vs if minor(v) < gaps[-1]]})
    return out


def canary_matrix(version: str, root: Path = REPO_ROOT) -> list[dict]:
    return [entry(t, version) for t in load_tutorials(root)
            if not t.errors and t.ci_runnable and t.status in ("stable", "deprecated")
            and all(version not in v.tested_versions for v in variants(t))]
