from __future__ import annotations

import argparse
import json
import subprocess
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


def _rows(a):
    from . import catalog
    from .model import version_key
    ts = [t for t in load_tutorials(REPO_ROOT) if not t.errors]
    cols = catalog.load_collections(REPO_ROOT)
    if a.status:
        ts = [t for t in ts if t.status == a.status]
    if a.tag:
        ts = [t for t in ts if a.tag in (t.meta.get("tags") or [])]
    if getattr(a, "collection", None):
        col = next((c for c in cols if c.id == a.collection), None)
        if col is None:
            sys.exit(f"unknown collection {a.collection!r}; collections: "
                     f"{', '.join(c.id for c in cols) or '(none)'}")
        order = {m: i for i, m in enumerate(col.members)}
        ts = sorted((t for t in ts if t.id in order), key=lambda t: order[t.id])
    elif a.sort == "status":
        rank = {"stable": 0, "deprecated": 1, "draft": 2, "archived": 3}
        ts.sort(key=lambda t: (rank.get(t.status, 9), t.id))
    elif a.sort == "kserve":
        ts.sort(key=lambda t: (max((version_key(v) for v in t.kserve_tested), default=(0,)), t.id),
                reverse=True)
    else:
        ts.sort(key=lambda t: t.id)
    return ts, cols


def _show(t, cols):
    """The detailed view of one tutorial (./tut show, ./tut list --long)."""
    kv = ", ".join(f"{v} (default)" if v == t.kserve_default else v for v in t.kserve_tested)
    parts = [f"env {t.env_ref}"] if t.env_ref else []
    parts += [f"lib {u}" for u in t.uses]
    langs = ["en (source)"] + [f"{l} {lint.TRANSLATION_STATES[lint.translation_state(t, l)]}"
                               for l in LANG_NAME if l != "en"]
    inc = [f"{c.id} (#{c.members.index(t.id) + 1})" for c in cols if t.id in c.members]
    req = t.meta.get("requires") or {}
    print(f"{t.id}  {STATUS_ICON.get(t.status, '')} {t.status}")
    print(f"  {t.title()}")
    if t.summary():
        print(f"  {t.summary()}")
    print(f"  KServe       {kv}")
    if parts:
        print(f"  uses         {'  ·  '.join(parts)}")
    if req:
        print(f"  needs        {'GPU, ' if req.get('gpu') else ''}{req.get('cpu', '?')} CPU, "
              f"{req.get('memory', '?')} memory, ~{t.meta.get('timeout_minutes', 45)} min")
    print(f"  languages    {'  ·  '.join(langs)}")
    if inc:
        print(f"  collections  {', '.join(inc)}")
    if t.meta.get("tags"):
        print(f"  tags         {' '.join('#' + x for x in t.meta['tags'])}")
    if t.meta.get("owners"):
        print(f"  owners       {', '.join('@' + o for o in t.meta['owners'])}")
    dep = t.meta.get("deprecation") or {}
    if dep:
        print(f"  deprecation  {dep.get('reason', '')}"
              + (f" → {dep['replacement']}" if dep.get("replacement") else ""))
    print(f"  files        tutorials/{t.id}/README.md")


def _fit(text: str, width: int) -> str:
    return text if len(text) <= width else text[:max(1, width - 1)] + "…"


def cmd_list(a):
    import shutil
    ts, cols = _rows(a)
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
    if a.long:
        for t in ts:
            _show(t, cols)
            print()
        return
    # one line per tutorial; columns shrink to the terminal width (tags last)
    lang_mark = {"current": "✓", "draft": "~", "behind": "!", "unmarked": "?", "missing": "-"}
    rows = []
    for t in ts:
        from .model import version_key
        vs = sorted(t.kserve_tested, key=version_key)
        kv = (vs[-1] + ("*" if vs[-1] == t.kserve_default else "") + (f" +{len(vs) - 1}" if len(vs) > 1 else "")
              ) if vs else "-"
        tr = " ".join(f"{l}{lang_mark[lint.translation_state(t, l)]}" for l in LANG_NAME if l != "en")
        inc = ",".join(f"{c.id}#{c.members.index(t.id) + 1}" for c in cols if t.id in c.members)
        rows.append([t.id, t.status, kv, tr, inc or "-",
                     " ".join(t.meta.get("tags") or [])])
    head = ["ID", "STATUS", "KSERVE", "TRANSL.", "COLLECTION", "TAGS"]
    width = shutil.get_terminal_size((120, 20)).columns
    w = [min(max(len(r[i]) for r in rows + [head]), cap)
         for i, cap in enumerate((34, 10, 14, 7, 22, 999))]
    w[-1] = width - sum(w[:-1]) - 2 * (len(w) - 1)
    if w[-1] < 12:                       # no useful room for tags: drop the column
        head, rows, w = head[:-1], [r[:-1] for r in rows], w[:-1]
    line = lambda r: "  ".join(_fit(c, w[i]).ljust(w[i]) for i, c in enumerate(r)).rstrip()
    print(line(head))
    for r in rows:
        print(line(r))
    print(f"\n{len(ts)} tutorial(s)")
    print("KSERVE: newest tested, * = default, +n = more versions · TRANSL.: ✓ ok ~ AI draft ! behind ? unmarked - none")
    print("Details: ./tut show <id> · filter: --tag --status --collection · step through: ./tut ui")


def cmd_completion(a):
    path = REPO_ROOT / "tools" / "tut-completion.bash"
    if a.print_script:
        sys.stdout.write(path.read_text())
    else:
        print(f'source "{path}"')
        if sys.stdout.isatty():
            print("# Tab completion for ./tut. Enable it in this shell with:\n"
                  '#   eval "$(./tut completion)"\n'
                  "# zsh: run `autoload -U +X bashcompinit && bashcompinit` first.\n"
                  "# To keep it, add the source line above to your ~/.bashrc yourself.",
                  file=sys.stderr)


def cmd_show(a):
    from . import catalog
    _show(_tutorial(a.id), catalog.load_collections(REPO_ROOT))


def cmd_new(a):
    from . import scaffold
    try:
        d = scaffold.new_tutorial(a.new_id, title=a.title, owner=a.owner)
    except scaffold.ScaffoldError as e:
        sys.exit(str(e))
    generate.sync(REPO_ROOT)
    rel = d.relative_to(REPO_ROOT)
    todo = [] if a.title else ["title and summary"]
    todo += [] if a.owner else ["owners (your GitHub handle)"]
    print(f"created {rel}/ from the template (status: draft)\n\nNext:\n"
          f"  1. edit {rel}/tutorial.yaml: {', '.join(todo + ['tags', 'kserve', 'requires'])}\n"
          f"  2. write {rel}/README.md (guide: docs/authoring.md); replace manifests/example.yaml\n"
          f"  3. once the English is done, translate: ./tut translation draft {a.new_id} ko\n"
          f"  4. make precommit, then ./tut ui (or ./tut run {a.new_id})")


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
                icon = {"current": "✅", "draft": "🤖", "behind": "⚠️ ", "unmarked": "❌", "missing": "· "}[st]
                print(f"  {icon} {t.id:32} {l}  {lint.TRANSLATION_STATES[st]}")
                if st == "missing":
                    todo.append(f"start:   ./tut translation draft {t.id} {l}   (AI)  or  init (by hand)")
                elif st == "draft":
                    todo.append(f"review tutorials/{t.id}/README.{l}.md, then: ./tut translation mark {t.id} {l}")
                elif st in ("behind", "unmarked"):
                    todo.append(f"update tutorials/{t.id}/README.{l}.md, then: "
                                f"./tut translation mark {t.id} {l}")
        if todo:
            print("\nNext steps:\n  " + "\n  ".join(todo))
        return
    if a.tcmd == "draft":
        return _translation_draft(a, langs)
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


def _translation_draft(a, langs):
    from . import translate
    lang = a.lang if a.lang else a.id if a.all else None
    if a.all:
        lang, a.id = a.id, None
    if lang not in langs:
        sys.exit(f"unknown language {lang!r}; supported: {', '.join(langs)}")
    try:
        tr = translate.configured()
    except translate.TranslationError as e:
        sys.exit(str(e))
    if tr is None:
        sys.exit("No AI translator configured. Pick the CLI you are logged in to, e.g.\n"
                 "  export TUT_TRANSLATOR=claude      # or copilot, codex, cmd:<command>\n"
                 "  ./tut config TUT_TRANSLATOR=claude   # to remember it in .tut.env")
    if not tr.available:
        sys.exit(f"TUT_TRANSLATOR={tr.name}, but `{tr.argv[0]}` is not on PATH")
    if a.all:
        targets = [t for t in load_tutorials(REPO_ROOT) if not t.errors
                   and lint.translation_state(t, lang) in ("missing", "behind", "unmarked")]
    else:
        targets = [_tutorial(a.id)]
        st = lint.translation_state(targets[0], lang)
        if st == "current" and not a.force:
            sys.exit(f"{a.id} {lang} is up to date and reviewed; use --force to re-translate it")
    if not targets:
        print(f"Nothing to translate into {lang}.")
        return 0
    failed = 0
    for t in targets:
        src = t.readme("en").read_text()
        print(f"→ {t.id} → {lang} with {tr.name} …", flush=True)
        try:
            text = translate.extract(translate.run(tr, translate.build_prompt(src, lang)))
        except (translate.TranslationError, subprocess.TimeoutExpired) as e:
            print(f"  ✗ {e}")
            failed += 1
            continue
        problems = translate.check(src, text)
        if problems:
            rej = REPO_ROOT / "build" / "translations" / f"{t.id}.{lang}.rejected.md"
            rej.parent.mkdir(parents=True, exist_ok=True)
            rej.write_text(text)
            print("  ✗ rejected, nothing written: " + "; ".join(problems)
                  + f"\n    (the AI output is in {rej.relative_to(REPO_ROOT)})")
            failed += 1
            continue
        path = lint.write_draft(t, lang, text, tr.name)
        generate.sync(REPO_ROOT)
        print(f"  ✓ wrote {path.relative_to(REPO_ROOT)} (AI draft, not reviewed)\n"
              f"    review it, then: ./tut translation mark {t.id} {lang}")
    return 1 if failed else 0


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
               "TUT_ENV_RECREATE": "1 = replace a cluster built by something else (destructive)",
               "TUT_TRANSLATOR": "AI CLI for `translation draft`: claude | copilot | codex | cmd:<command>",
               "TUT_TRANSLATOR_ARGS": "extra flags for that CLI, e.g. \"--model sonnet\""}


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


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="tut", description="KServe tutorials toolkit")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("list", help="one line per tutorial (details: ./tut show <id>)")
    s.add_argument("--status", choices=["draft", "stable", "deprecated", "archived"])
    s.add_argument("--tag", help="only tutorials with this tag (see catalog/tags.yaml)")
    s.add_argument("--collection", help="only this collection, in reading order")
    s.add_argument("--sort", choices=["id", "status", "kserve"], default="id")
    s.add_argument("--long", "-l", action="store_true", help="the detailed view for every tutorial")
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_list)

    s = sub.add_parser("completion", help="Tab completion for ./tut: eval \"$(./tut completion)\"")
    s.add_argument("--print-script", action="store_true", help="print the bash script itself")
    s.set_defaults(fn=cmd_completion)

    s = sub.add_parser("show", help="everything about one tutorial")
    s.add_argument("id", help="tutorial id (directory name under tutorials/)")
    s.set_defaults(fn=cmd_show)

    s = sub.add_parser("new", help="start a tutorial from tutorials/_template/",
                       description="Copy tutorials/_template/ to tutorials/<id>/ (English only), fill "
                                   "in id and namespace (and the title / owner if given), then ./tut sync.")
    s.add_argument("new_id", metavar="id", help="new tutorial id, e.g. llmisvc-autoscaling")
    s.add_argument("--title", help='English title, e.g. "Autoscaling an LLMInferenceService"')
    s.add_argument("--owner", help="your GitHub handle (goes to owners and CODEOWNERS)")
    s.set_defaults(fn=cmd_new)

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
    d = tsub.add_parser("draft", help="translate with your AI CLI (TUT_TRANSLATOR=claude|copilot|codex|cmd:...)",
                        description="Translate README.md with the AI CLI set in TUT_TRANSLATOR. The result "
                                    "is checked (code, commands, regions, links unchanged) and written as an "
                                    "AI draft; review it, then `translation mark`.")
    d.add_argument("id", help="tutorial id (or, with --all, the language)")
    d.add_argument("lang", nargs="?", help="language code, e.g. ko")
    d.add_argument("--all", action="store_true",
                   help="every tutorial whose translation is missing or behind: ./tut translation draft --all ko")
    d.add_argument("--force", action="store_true", help="re-translate a reviewed, up-to-date translation")
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

    return p


# --------------------------------------------------------------- completion
def _values(dest: str) -> list[str]:
    """Dynamic values for an argument, by its argparse dest."""
    from . import catalog
    from .model import version_key
    if dest == "id":
        return [t.id for t in load_tutorials(REPO_ROOT)]
    if dest == "lang":
        return [l for l in LANG_NAME if l != "en"]
    if dest == "tag":
        return sorted(catalog.load_tags(REPO_ROOT).get("tags") or {})
    if dest == "collection":
        return [c.id for c in catalog.load_collections(REPO_ROOT)]
    if dest == "kserve_version":
        return sorted({v for t in load_tutorials(REPO_ROOT) for v in t.kserve_tested},
                      key=version_key, reverse=True)
    if dest == "set":
        return [f"{k}=" for k in CONFIG_KEYS]
    return []


def complete(words: list[str]) -> list[str]:
    """Candidates for the word after `words` (the words already typed after
    `tut`). Walks the real argparse parser, so it never drifts from the CLI."""
    def subparsers(p):
        return next((a for a in p._actions if isinstance(a, argparse._SubParsersAction)), None)

    p, rest = build_parser(), list(words)
    while (spa := subparsers(p)) is not None:
        positional = [w for w in rest if not w.startswith("-")]
        if not positional:
            return sorted(c for c in spa.choices if not c.startswith("_"))
        if positional[0] not in spa.choices:
            return []
        rest = rest[rest.index(positional[0]) + 1:]
        p = spa.choices[positional[0]]
    opts = {o: a for a in p._actions for o in a.option_strings}
    if rest and rest[-1] in opts and opts[rest[-1]].nargs != 0:      # value of an option
        act = opts[rest[-1]]
        return [str(c) for c in act.choices] if act.choices else _values(act.dest)
    given, skip = 0, False
    for w in rest:
        if skip:
            skip = False
        elif w in opts and opts[w].nargs != 0:
            skip = True
        elif not w.startswith("-"):
            given += 1
    positionals = [a for a in p._actions if not a.option_strings]
    out = []
    if given < len(positionals):
        out += _values(positionals[given].dest)
    elif positionals and positionals[-1].nargs == "*":
        out += _values(positionals[-1].dest)
    return out + sorted(o for o in opts if o.startswith("--"))


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["__complete"]:          # used by tools/tut-completion.bash
        print("\n".join(complete(argv[1:])))
        return 0
    a = build_parser().parse_args(argv)
    return a.fn(a) or 0
