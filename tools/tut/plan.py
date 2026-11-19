"""Decide what CI should execute.

`./tut affected --base <ref>`  tutorials touched by a change (PR runs)
`./tut matrix --scheduled`      every runnable tutorial x every tested version
`./tut matrix --canary <ver>`   stable/deprecated tutorials against a new KServe version

Blast radius rules (the reason envs are versioned):
  tutorials/<id>/**           -> <id>
  envs/<name>/<ver>/**        -> tutorials whose `env` is <name>/<ver>
  lib/<name>/<ver>/**         -> tutorials that list <name>/<ver> in `uses`
  anything else               -> nothing (lint and unit tests still run)
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from .model import REPO_ROOT, Tutorial, load_tutorials


def changed_files(base: str, root: Path = REPO_ROOT) -> list[str]:
    out = subprocess.run(["git", "diff", "--name-only", f"{base}...HEAD"],
                         cwd=root, capture_output=True, text=True, check=True).stdout
    return [l for l in out.split("\n") if l]


def affected(paths: list[str], tutorials: list[Tutorial]) -> list[Tutorial]:
    by_id = {t.id: t for t in tutorials}
    hit: dict[str, Tutorial] = {}
    for p in paths:
        parts = Path(p).parts
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
    return {"tutorial": t.id, "kserve_version": version, "env": t.env_ref}


def pr_matrix(base: str, root: Path = REPO_ROOT) -> list[dict]:
    ts = [t for t in affected(changed_files(base, root), load_tutorials(root)) if not t.errors]
    return [entry(t, t.kserve_default) for t in ts if t.ci_runnable and t.kserve_default]


def scheduled_matrix(root: Path = REPO_ROOT) -> list[dict]:
    return [entry(t, v) for t in load_tutorials(root) if not t.errors and t.ci_runnable
            for v in t.kserve_tested]


def canary_matrix(version: str, root: Path = REPO_ROOT) -> list[dict]:
    return [entry(t, version) for t in load_tutorials(root)
            if not t.errors and t.ci_runnable and t.status in ("stable", "deprecated")
            and version not in t.kserve_tested]
