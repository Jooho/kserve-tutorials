from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import generate, lint, plan, runner, site
from .model import REPO_ROOT, load_tutorials


def _tutorial(tid: str):
    for t in load_tutorials(REPO_ROOT, include_template=False):
        if t.id == tid:
            return t
    sys.exit(f"unknown tutorial {tid!r} (see ./tut list)")


def cmd_list(a):
    for t in load_tutorials(REPO_ROOT):
        print(f"{t.id:32} {t.status:11} kserve={','.join(t.kserve_tested):24} env={t.env_ref}")


def cmd_sync(a):
    changed, errors = generate.sync(REPO_ROOT, check=a.check)
    for e in errors:
        print(f"ERROR   {e}", file=sys.stderr)
    for p in changed:
        print(("would update " if a.check else "updated ") + str(p.relative_to(REPO_ROOT)))
    return 1 if errors or (a.check and changed) else 0


def cmd_lint(a):
    findings = lint.Linter(REPO_ROOT, base=a.base).run()
    for f in findings:
        print(f.format(REPO_ROOT))
    n_err = sum(f.severity == "error" for f in findings)
    n_warn = len(findings) - n_err
    print(f"\n{n_err} error(s), {n_warn} warning(s)")
    return 1 if n_err else 0


def cmd_run(a):
    return runner.run(_tutorial(a.id), kserve_version=a.kserve_version, keep=a.keep,
                      dry_run=a.dry_run, teardown_env=a.teardown_env,
                      report=Path(a.report) if a.report else None)


def cmd_affected(a):
    m = plan.pr_matrix(a.base)
    print(json.dumps(m) if a.json else "\n".join(f"{e['tutorial']} @ {e['kserve_version']}" for e in m))


def cmd_matrix(a):
    m = plan.canary_matrix(a.canary) if a.canary else plan.scheduled_matrix()
    print(json.dumps(m) if a.json else "\n".join(f"{e['tutorial']} @ {e['kserve_version']}" for e in m))


def cmd_translation(a):
    t = _tutorial(a.id)
    if not t.readme(a.lang).exists():
        sys.exit(f"{t.readme(a.lang)} does not exist")
    p = lint.mark_translation(t, a.lang)
    print(f"marked {p.relative_to(REPO_ROOT)} as translated from the current README.md")


def cmd_site(a):
    out = site.build_source(Path(a.out).resolve())
    print(f"site source written to {out}")


def main(argv=None):
    p = argparse.ArgumentParser(prog="tut", description="KServe tutorials toolkit")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list", help="list tutorials").set_defaults(fn=cmd_list)

    s = sub.add_parser("sync", help="regenerate <!-- tut:... --> regions")
    s.add_argument("--check", action="store_true", help="fail instead of writing")
    s.set_defaults(fn=cmd_sync)

    s = sub.add_parser("lint", help="check every rule (see tools/tut/lint.py)")
    s.add_argument("--base", help="git ref to compare with (enables frozen-env check)")
    s.set_defaults(fn=cmd_lint)

    s = sub.add_parser("run", help="execute a tutorial README end to end")
    s.add_argument("id")
    s.add_argument("--kserve-version", help="override kserve.default")
    s.add_argument("--keep", action="store_true", help="skip cleanup blocks")
    s.add_argument("--dry-run", action="store_true", help="print the generated script")
    s.add_argument("--teardown-env", action="store_true", help="run the env teardown.sh at the end")
    s.add_argument("--report", help="write a JSON result file")
    s.set_defaults(fn=cmd_run)

    s = sub.add_parser("affected", help="tutorials affected by changes since --base")
    s.add_argument("--base", required=True)
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_affected)

    s = sub.add_parser("matrix", help="CI matrix for scheduled or canary runs")
    g = s.add_mutually_exclusive_group(required=True)
    g.add_argument("--scheduled", action="store_true")
    g.add_argument("--canary", metavar="VERSION")
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_matrix)

    s = sub.add_parser("translation", help="translation helpers")
    tsub = s.add_subparsers(dest="tcmd", required=True)
    m = tsub.add_parser("mark", help="record that a translation matches the current README.md")
    m.add_argument("id")
    m.add_argument("lang")
    m.set_defaults(fn=cmd_translation)

    s = sub.add_parser("site", help="assemble the MkDocs source tree")
    s.add_argument("--out", default=str(REPO_ROOT / "build" / "site-src"))
    s.set_defaults(fn=cmd_site)

    a = p.parse_args(argv)
    return a.fn(a) or 0
