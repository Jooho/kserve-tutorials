from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import doctor, generate, lint, plan, release, runner, site
from .model import REPO_ROOT, load_tutorials


def _tutorial(tid: str):
    import difflib
    ts = load_tutorials(REPO_ROOT, include_template=False)
    for t in ts:
        if t.id == tid:
            return t
    near = difflib.get_close_matches(tid, [t.id for t in ts], n=1)
    hint = f"did you mean {near[0]!r}? " if near else ""
    sys.exit(f"unknown tutorial {tid!r}: {hint}A tutorial id is its directory name under "
             f"tutorials/; `./tut list` shows them.")


STATUS_ICON = {"draft": "🚧", "stable": "✅", "deprecated": "⚠️ ", "archived": "🗄️ "}
LANG_NAME = {"en": "English", "ko": "Korean"}


def cmd_list(a):
    from . import catalog
    ts = [t for t in load_tutorials(REPO_ROOT) if not t.errors]
    if a.status:
        ts = [t for t in ts if t.status == a.status]
    if a.tag:
        ts = [t for t in ts if a.tag in (t.meta.get("tags") or [])]
    cols = catalog.load_collections(REPO_ROOT)
    if a.json:
        print(json.dumps([{
            "id": t.id, "title": t.title(), "status": t.status, "kserve": t.meta.get("kserve"),
            "env": t.env_ref, "uses": t.uses, "tags": t.meta.get("tags", []),
            "translations": {l: lint.translation_state(t, l) for l in LANG_NAME if l != "en"},
            "collections": [c.id for c in cols if t.id in c.members],
        } for t in ts], indent=2, ensure_ascii=False))
        return
    if not ts:
        print("No tutorials match.")
        return
    for t in ts:
        kv = ", ".join(f"{v} (default)" if v == t.kserve_default else v for v in t.kserve_tested)
        parts = [f"env {t.env_ref}"] if t.env_ref else []
        parts += [f"lib {u}" for u in t.uses]
        langs = ["en (source)"] + [
            f"{l} {lint.translation_state(t, l).replace('current', 'up to date').replace('missing', 'not translated')}"
            for l in LANG_NAME if l != "en"]
        inc = [f"{c.id} (#{c.members.index(t.id) + 1})" for c in cols if t.id in c.members]
        print(f"{t.id}  {STATUS_ICON.get(t.status, '')} {t.status}")
        print(f"  {t.title()}")
        print(f"  KServe       {kv}")
        if parts:
            print(f"  uses         {'  ·  '.join(parts)}")
        print(f"  languages    {'  ·  '.join(langs)}")
        if inc:
            print(f"  collections  {', '.join(inc)}")
        if t.meta.get("tags"):
            print(f"  tags         {' '.join('#' + x for x in t.meta['tags'])}")
        print()
    print(f"{len(ts)} tutorial(s).  Run one: ./tut run <id>   ·   step through it: ./tut ui   ·   "
          "translations: ./tut translation")


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
                      keep_on_failure=a.keep_on_failure, twice=a.twice)


def cmd_affected(a):
    m = plan.pr_matrix(a.base)
    print(json.dumps(m) if a.json else "\n".join(f"{e['tutorial']} @ {e['kserve_version']}" for e in m))


def cmd_matrix(a):
    m = plan.canary_matrix(a.canary) if a.canary else plan.scheduled_matrix()
    print(json.dumps(m) if a.json else "\n".join(f"{e['tutorial']} @ {e['kserve_version']}" for e in m))


def cmd_translation(a):
    langs = [l for l in LANG_NAME if l != "en"]
    if a.tcmd in (None, "status"):
        print("Translations (English README.md is the source)\n")
        todo = []
        for t in load_tutorials(REPO_ROOT):
            if t.errors:
                continue
            for l in langs:
                st = lint.translation_state(t, l)
                icon = {"current": "✅", "behind": "⚠️ ", "unmarked": "❌", "missing": "· "}[st]
                print(f"  {icon} {t.id:32} {l}  {lint.TRANSLATION_STATES[st]}")
                if st == "missing":
                    todo.append(f"start:   ./tut translation init {t.id} {l}")
                elif st in ("behind", "unmarked"):
                    todo.append(f"update tutorials/{t.id}/README.{l}.md, then: "
                                f"./tut translation mark {t.id} {l}")
        if todo:
            print("\nNext steps:\n  " + "\n  ".join(todo))
        return
    if a.lang not in langs:
        sys.exit(f"unknown language {a.lang!r}; supported: {', '.join(langs)}")
    t = _tutorial(a.id)
    if a.tcmd == "init":
        try:
            p = lint.init_translation(t, a.lang)
        except (FileExistsError, ValueError) as e:
            sys.exit(str(e))
        print(f"created {p.relative_to(REPO_ROOT)} (a copy of README.md) and added {a.lang!r} to langs.\n"
              f"Translate the prose and code comments; keep the code blocks as they are.\n"
              f"Then: ./tut translation mark {t.id} {a.lang}")
        return
    if not t.readme(a.lang).exists():
        sys.exit(f"tutorials/{t.id}/README.{a.lang}.md does not exist yet. Start it with:\n"
                 f"  ./tut translation init {t.id} {a.lang}")
    p = lint.mark_translation(t, a.lang)
    print(f"marked {p.relative_to(REPO_ROOT)} as a translation of the current README.md")


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

    s = sub.add_parser("list", help="list tutorials: versions, env, languages, collections, tags")
    s.add_argument("--status", choices=["draft", "stable", "deprecated", "archived"])
    s.add_argument("--tag", help="only tutorials with this tag (see catalog/tags.yaml)")
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_list)

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
    s.add_argument("--twice", action="store_true",
                   help="run every step twice (same shell and cluster) to prove the steps are safe to repeat")
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

    s = sub.add_parser("translation", help="translation status (no arguments), init, mark",
                       description="Without a subcommand: show every translation's state and the next "
                                   "step. <id> is a tutorial id (directory under tutorials/, see ./tut "
                                   "list); <lang> is a language code such as ko.")
    tsub = s.add_subparsers(dest="tcmd")
    tsub.add_parser("status", help="state of every translation (default)")
    for name, help_ in (("init", "start a translation: copy README.md and add the language to langs"),
                        ("mark", "after translating: record that it matches the current README.md")):
        m = tsub.add_parser(name, help=help_)
        m.add_argument("id", help="tutorial id, e.g. llmisvc-anatomy")
        m.add_argument("lang", help="language code, e.g. ko")
    s.set_defaults(fn=cmd_translation)

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
