from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import doctor, generate, lint, plan, release, runner, site
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
                      report=Path(a.report) if a.report else None,
                      keep_on_failure=a.keep_on_failure)


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


def cmd_release(a):
    if a.rcmd == "next-version":
        print(release.next_version())
    elif a.rcmd == "check":
        expected = json.loads(Path(a.expected).read_text())
        ok, problems = release.verdict(release.load_reports(Path(a.reports)), expected)
        for p in problems:
            print(f"✗ {p}", file=sys.stderr)
        print(f"{len(expected) - len(problems)}/{len(expected)} passed")
        return 0 if ok else 1
    elif a.rcmd == "can-ff":
        ok, msg = release.can_fast_forward(a.sha)
        print(msg)
        return 0 if ok else 1
    elif a.rcmd == "notes":
        reports = release.load_reports(Path(a.reports)) if a.reports else []
        sys.stdout.write(release.notes(a.version, a.sha, reports, repo=a.repo))


CONFIG_FILE = REPO_ROOT / ".tut.env"
CONFIG_KEYS = {"KIND_CLUSTER_NAME": "name of the kind cluster tutorials create/use (default: kind)",
               "TUT_SKIP_TOOLS": "tools you provide yourself, e.g. \"helm\" (default: none)",
               "TUT_ENV_RECREATE": "1 = replace a cluster built by something else (destructive)"}


def cmd_config(a):
    import os
    import re
    lines = CONFIG_FILE.read_text().splitlines() if CONFIG_FILE.exists() else []
    changes = []
    for kv in a.set:
        k, eq, v = kv.partition("=")
        k, v = k.strip(), v.strip()
        if not re.fullmatch(r"[A-Z_][A-Z0-9_]*", k) or not eq:
            sys.exit(f"expected KEY=VALUE, got {kv!r}")
        lines = [l for l in lines if l.split("=", 1)[0].strip() != k]
        if v:
            lines.append(f"{k}={v}")
        changes.append(f"set {k}={v}" if v else f"removed {k}")
    if a.set:   # save first, then report
        body = [l for l in lines if not l.startswith("# personal")]
        CONFIG_FILE.write_text("# personal settings, not in git; see `./tut config`\n"
                               + "".join(l + "\n" for l in body))
        for c in changes:
            print(f"{c} in .tut.env")
    print("\nsettings (shell > .tut.env > default):")
    loaded = set((os.environ.get("TUT_CONFIG_LOADED") or "").split())
    for k, help_ in CONFIG_KEYS.items():
        val = os.environ.get(k)
        src = ".tut.env" if k in loaded else ("shell" if val is not None else "default")
        print(f"  {k:18} {val if val is not None else '-':10} ({src})  {help_}")


def cmd_doctor(a):
    return doctor.report(doctor.run_checks(tutorial=a.tutorial, toolkit_only=a.toolkit),
                         as_json=a.json)


def cmd_ui(a):
    try:
        from .ui.server import serve
    except ImportError as e:
        sys.exit(f"{e}. Install the UI dependencies: pip install -r tools/requirements.txt")
    serve(port=a.port, open_browser=not a.no_browser)


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
    s.add_argument("--keep-on-failure", action="store_true",
                   help="skip cleanup blocks only when a step failed (for debugging / CI diagnostics)")
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

    s = sub.add_parser("release", help="release helpers (see docs/release.md)")
    rsub = s.add_subparsers(dest="rcmd", required=True)
    rsub.add_parser("next-version", help="next YYYY.MM.N tag")
    r = rsub.add_parser("check", help="fail unless every expected matrix entry has a passing report")
    r.add_argument("--reports", required=True)
    r.add_argument("--expected", required=True, help="JSON file from `tut matrix --scheduled --json`")
    r = rsub.add_parser("can-ff", help="can `stable` fast-forward to this commit?")
    r.add_argument("sha")
    r = rsub.add_parser("notes", help="release notes (markdown)")
    r.add_argument("version")
    r.add_argument("sha")
    r.add_argument("--reports")
    r.add_argument("--repo", default="<owner>/<repo>")
    s.set_defaults(fn=cmd_release)

    s = sub.add_parser("config", help="show or set personal settings in .tut.env")
    s.add_argument("set", nargs="*", metavar="KEY=VALUE", help="KEY= removes a setting")
    s.set_defaults(fn=cmd_config)

    s = sub.add_parser("doctor", help="is this machine ready to run the tutorials?")
    s.add_argument("--tutorial", help="check the resources this tutorial asks for")
    s.add_argument("--toolkit", action="store_true", help="only what ./tut itself needs")
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_doctor)

    s = sub.add_parser("ui", help="local web UI: read and run tutorials in a real shell")
    s.add_argument("--port", type=int, default=8080)
    s.add_argument("--no-browser", action="store_true", help="do not open a browser")
    s.set_defaults(fn=cmd_ui)

    a = p.parse_args(argv)
    return a.fn(a) or 0
