"""`./tut run <id>`: execute a tutorial README exactly as a reader would.

All `run` and `verify` blocks are concatenated, in document order, into one bash
script, so variables and `cd` carry over between blocks just like in a reader's
terminal. `cleanup` blocks run at the end through an EXIT trap, also after a
failure. `skip` blocks are never executed.

verify blocks may carry `retry=N delay=S`; they then run in a subshell, which is
retried until it succeeds (variables set inside a retried block do not persist).
"""
from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
import time
from pathlib import Path

from . import markdown
from .model import REPO_ROOT, Tutorial


def build_script(t: Tutorial, kserve_version: str | None, keep: bool,
                 keep_on_failure: bool = False, passes: int = 1) -> tuple[str, list[markdown.Block]]:
    doc = markdown.parse(t.readme("en").read_text())
    blocks = [b for b in doc.blocks if b.is_shell and b.role in ("run", "verify", "cleanup")]
    readme = f"tutorials/{t.id}/README.md"
    out = [
        "#!/usr/bin/env bash",
        "set -Eeuo pipefail",
        f"cd {shlex.quote(str(REPO_ROOT))}",
        f"export TUT_ID={shlex.quote(t.id)}",
    ]
    if kserve_version:
        out.append(f"export KSERVE_VERSION={shlex.quote(kserve_version)}")
    out += [
        "TUT_BLOCK=''",
        "__tut_failed=0",
        "__tut_report() { echo \"$1\" > \"${TUT_STATE_FILE:-/dev/null}\"; }",
        "__tut_on_err() { local rc=$?; __tut_failed=1; echo \"✗ FAILED in ${TUT_BLOCK} (exit ${rc})\" >&2; "
        "__tut_report \"$TUT_BLOCK\"; }",
        "trap __tut_on_err ERR",
    ]
    cleanups = [b for b in blocks if b.role == "cleanup"]
    if cleanups and not keep:
        out.append("__tut_cleanup() {")
        out.append("  set +e")
        if keep_on_failure:
            out.append("  if [ \"$__tut_failed\" = 1 ]; then echo 'keeping resources for debugging "
                       "(--keep-on-failure); cleanup skipped'; return; fi")
        out.append("  trap - ERR")
        out.append("  echo '::group::cleanup'")
        for b in cleanups:
            out.append(f"  # --- {readme}:{b.line} (cleanup)")
            out.append("  (")
            out.append(_indent(b.code, 4))
            out.append("  )")
        out.append("  echo '::endgroup::'")
        out.append("}")
        out.append("trap __tut_cleanup EXIT")
    steps = [b for b in blocks if b.role in ("run", "verify")]
    # passes=2 (--twice): every step again in the same shell and cluster, before
    # cleanup — a step that only works on a clean cluster fails here (D012).
    plan = [(p, n, b) for p in range(1, passes + 1) for n, b in enumerate(steps, 1)
            if not (p > 1 and b.attrs.get("once"))]
    for p, n, b in plan:
        tag = f"pass {p}/{passes} · " if passes > 1 else ""
        label = f"{readme}:{b.line} ({tag}step {n}/{len(steps)} · {b.role})"
        out.append("")
        out.append(f"TUT_BLOCK={shlex.quote(label)}")
        out.append(f"echo {shlex.quote('::group::' + label)}")
        retry = int(b.attrs.get("retry", "1"))
        if b.role == "verify" and retry > 1:
            delay = int(b.attrs.get("delay", "10"))
            out += [
                "for __tut_try in $(seq 1 %d); do" % retry,
                "  set +e; trap - ERR",
                "  (",
                "    set -Eeuo pipefail; trap - ERR",
                _indent(b.code, 4),
                "  )",
                "  __tut_rc=$?",
                "  set -e; trap __tut_on_err ERR",
                "  [ $__tut_rc -eq 0 ] && break",
                "  if [ $__tut_try -eq %d ]; then false; fi" % retry,
                f"  echo \"retry $__tut_try/{retry} failed, sleeping {delay}s\" >&2; sleep {delay}",
                "done",
            ]
        else:
            out.append(b.code)
        out.append("echo '::endgroup::'")
    out.append("")
    out.append("TUT_BLOCK=''")
    out.append("echo '✓ all steps passed'")
    return "\n".join(out) + "\n", steps


def _indent(code: str, n: int) -> str:
    pad = " " * n
    return "\n".join(pad + l if l.strip() else l for l in code.split("\n"))


def run(t: Tutorial, kserve_version: str | None = None, keep: bool = False,
        dry_run: bool = False, teardown_env: bool = False,
        report: Path | None = None, keep_on_failure: bool = False, twice: bool = False) -> int:
    script, steps = build_script(t, kserve_version, keep, keep_on_failure, 2 if twice else 1)
    if dry_run:
        sys.stdout.write(script)
        return 0
    version = kserve_version or t.kserve_default
    state_file = Path(os.environ.get("RUNNER_TEMP", "/tmp")) / f"tut-{t.id}-{os.getpid()}.state"
    env = dict(os.environ, TUT_STATE_FILE=str(state_file))
    timeout = int(t.meta.get("timeout_minutes", 45)) * 60
    started = time.time()
    print(f"▶ {t.id} with KServe {version} ({len(steps)} steps, timeout {timeout // 60}m)", flush=True)
    # Run the script from a file, not `bash -c <script>`: with -c the whole tutorial
    # is in the shell's command line, so a step like `pkill -f "[p]ort-forward ..."`
    # matched the runner itself and killed it (CI-008). A reader's terminal never
    # has the script in its command line either.
    script_file = state_file.with_suffix(".sh")
    script_file.write_text(script)
    try:
        rc = subprocess.run(["bash", str(script_file)], env=env, timeout=timeout).returncode
        failed_at = state_file.read_text().strip() if rc and state_file.exists() else None
    except subprocess.TimeoutExpired:
        rc, failed_at = 124, f"timeout after {timeout // 60} minutes"
    finally:
        if teardown_env and t.env_ref:
            subprocess.run([str(REPO_ROOT / "envs" / t.env_ref / "teardown.sh")])
        state_file.unlink(missing_ok=True)
        script_file.unlink(missing_ok=True)
    result = {
        "tutorial": t.id,
        "kserve_version": version,
        "env": t.env_ref,
        "status": "passed" if rc == 0 else "failed",
        "failed_at": failed_at,
        "exit_code": rc,
        "duration_seconds": round(time.time() - started),
    }
    if report:
        report.write_text(json.dumps(result, indent=2) + "\n")
    print(("✓ " if rc == 0 else "✗ ") + json.dumps(result), flush=True)
    return rc
