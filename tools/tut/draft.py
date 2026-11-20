"""`./tut draft <folder>`: turn a folder of tested work (scripts, manifests,
notes, a README) into a tutorial in this repository's format, with the AI CLI
the author already uses (TUT_AI=claude|copilot|codex|cmd:...).

A program cannot do this alone (scripts call each other, setup must be told
apart from the lesson, prose and verify steps have to be written), so an AI
agent does the work. This module gives it the material and checks the result:

  1. scaffold tutorials/<id>/ from the template; copy the input folder to
     build/draft/<id>/input/ (the original is only read, never changed)
  2. build/draft/<id>/parts.md: the envs, helper scripts and shared steps the
     tutorial can reuse, with how to use each and who uses it
  3. run the AI agent with the rules (AGENTS.md, docs/authoring.md), an example
     tutorial and the parts. It may write only tutorials/<id>/ and
     build/draft/<id>/, and may run only `./tut _draftcheck <id>` (sync + lint +
     dry run; nothing touches a cluster)
  4. check: files changed outside those two places, lint findings, and which
     commands of the input scripts are not in the tutorial (the AI may change
     some on purpose, e.g. `sleep` -> `kubectl wait`; its notes say why)
  5. report: build/draft/<id>/report.md; the author finishes in `./tut ui`
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from . import generate, lint, markdown, project, scaffold, shared
from .model import REPO_ROOT, MODULE_REF_RE, load_envs, load_modules, load_tutorials

SKIP_DIRS = {".git", "__pycache__", "node_modules", ".venv", ".tools"}
MAX_FILE = 5 * 1024 * 1024        # bigger files are not copied (models, images are still listed)

# Agent mode: the AI edits files and runs one check command. Writes are limited
# by instruction and by the check after the run (anything outside is reported).
AGENTS = {
    "claude": ["claude", "-p", "{prompt}", "--permission-mode", "acceptEdits",
               "--allowedTools", "Read,Write,Edit,Glob,Grep,Bash(./tut _draftcheck:*)",
               "--output-format", "text"],
    "codex": ["codex", "exec", "--skip-git-repo-check", "--sandbox", "workspace-write", "{prompt}"],
    "copilot": ["copilot", "-p", "{prompt}", "--allow-tool", "write",
                "--allow-tool", "shell(./tut _draftcheck)", "-s", "--no-color"],
}


class DraftError(Exception):
    pass


@dataclass
class Agent:
    name: str
    argv: list[str]
    shell: bool = False

    @property
    def available(self) -> bool:
        return self.shell or shutil.which(self.argv[0]) is not None


def agent_from_env() -> Agent | None:
    """TUT_AI (or the older TUT_TRANSLATOR) picks the CLI; TUT_AI_ARGS adds flags."""
    import shlex
    spec = (os.environ.get("TUT_AI") or os.environ.get("TUT_TRANSLATOR") or "").strip()
    if not spec:
        return None
    if spec.startswith("cmd:"):
        return Agent("cmd", [spec[4:].strip()], shell=True)
    if spec not in AGENTS:
        raise DraftError(f"TUT_AI={spec!r}: use claude, copilot, codex or cmd:<command>")
    extra = shlex.split(os.environ.get("TUT_AI_ARGS", os.environ.get("TUT_TRANSLATOR_ARGS", "")))
    argv = list(AGENTS[spec])
    i = argv.index("{prompt}")
    return Agent(spec, argv[:i] + extra + argv[i:])


def slug(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return s or "tutorial"


# ------------------------------------------------------------------ material
def copy_input(src: Path, dst: Path) -> tuple[list[str], list[str]]:
    """Copy the folder (read only); return (copied, skipped as too big)."""
    copied, skipped = [], []
    for p in sorted(src.rglob("*")):
        rel = p.relative_to(src)
        if any(part in SKIP_DIRS for part in rel.parts) or not p.is_file():
            continue
        if p.stat().st_size > MAX_FILE:
            skipped.append(str(rel))
            continue
        (dst / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, dst / rel)
        copied.append(str(rel))
    return copied, skipped


IMAGE_EXT = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"}


def is_asset(p: Path) -> bool:
    """Files the AI cannot write itself (it only writes text): images and binaries."""
    if p.suffix.lower() in IMAGE_EXT:
        return True
    try:
        return b"\0" in p.read_bytes()[:8192]
    except OSError:
        return False


def copy_assets(inp: Path, tdir: Path) -> list[str]:
    """Copy images and binary files into the tutorial at the same relative path
    (images/x.svg -> tutorials/<id>/images/x.svg), so existing links keep working
    and the UI, the site and GitHub show them."""
    out = []
    for p in sorted(inp.rglob("*")):
        if p.is_file() and is_asset(p):
            rel = p.relative_to(inp)
            (tdir / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, tdir / rel)
            out.append(str(rel))
    return out


def prune_assets(tdir: Path, assets: list[str]) -> list[str]:
    """Remove copied assets nothing in the tutorial refers to; return them."""
    texts = "\n".join(p.read_text(errors="replace") for p in tdir.rglob("*")
                      if p.is_file() and not is_asset(p))
    removed = []
    for rel in assets:
        p = tdir / rel
        if p.exists() and rel not in texts and Path(rel).name not in texts:
            p.unlink()
            removed.append(rel)
    for d in sorted({(tdir / r).parent for r in removed}, key=lambda d: -len(d.parts)):
        while d != tdir and d.is_dir() and not any(d.iterdir()):
            d.rmdir(); d = d.parent
    return removed


def parts_catalog(root: Path = REPO_ROOT) -> str:
    """Everything a new tutorial can reuse, and who already uses it."""
    tutorials = [t for t in load_tutorials(root) if not t.errors]
    name = project.load(root).name
    out = ["# Reusable parts", "",
           "Use these instead of writing the same thing again. Declare envs and helper",
           "modules in tutorial.yaml (`env:`, `uses:`); use shared steps with one line.", ""]
    out += ["## Environments (`env:` in tutorial.yaml)", "",
            f"An env creates the cluster and installs {name}; the generated setup step runs it.",
            "Pick what to install with env_options. If no env and no option fits, do NOT create",
            "one: write the setup as steps and add a TODO to the notes.", ""]
    for ref, env in sorted(load_envs(root).items()):
        users = [t.id for t in tutorials if t.env_ref == ref]
        tools = (env.path / "tools.env").read_text().strip() if (env.path / "tools.env").exists() else ""
        options = env.meta.get("options") or {}
        out += [f"### `{ref}`", "", f"- what: {env.meta.get('description', '').strip()}",
                f"- {name} versions: {env.meta.get('versions', {})}", f"- frozen: {env.meta.get('frozen', False)}",
                f"- use: `env: {ref}`" + (" plus `env_options:` (see options)" if options else ""),
                f"- used by: {', '.join(users) or '-'}",
                f"- details: envs/{ref}/README.md, envs/{ref}/setup.sh"]
        if options:
            out += ["- options (`env_options` in tutorial.yaml; anything else fails lint T008):"]
            out += [f"  - `{k}`: {v.get('description', '')}; allowed {v.get('allowed')}, default {v.get('default')}"
                    for k, v in options.items()]
            used = [f"{t.id}: {t.env_options}" for t in tutorials if t.env_ref == ref and t.env_options]
            if used:
                out += ["  - examples: " + "; ".join(used)]
        if tools:
            out += ["- tools:", "", "```", tools, "```"]
        out.append("")
    out += ["## Helper scripts (`uses:` in tutorial.yaml, called from steps)", ""]
    for ref, mod in sorted(load_modules(root).items()):
        users = sorted({t.id for t in tutorials for b in markdown.parse(t.readme("en").read_text()).blocks
                        if ref in MODULE_REF_RE.findall(b.code)}) if tutorials else []
        out += [f"### `{ref}` — {mod.meta.get('description', '')}", "",
                f"- use: `uses: [{ref}]` in tutorial.yaml", f"- used by: {', '.join(users) or '-'}", ""]
        for name, desc in (mod.meta.get("scripts") or {}).items():
            out.append(f"- `\"$TUT_LIB/{ref}/{name}\"` — {desc} (source: lib/{ref}/{name})")
        out.append("")
    out += ["## Shared steps (`<!-- tut:use name -->` + `<!-- /tut -->`, then ./tut sync)", ""]
    defs = shared.definitions(tutorials)
    if not defs:
        out.append("(none yet)")
    for name, where in sorted(defs.items()):
        users = [t.id for t in tutorials if name in shared.names_in(t) and t.id != where[0][0]]
        out.append(f"- `{name}` — defined in {where[0][0]}; used by {', '.join(users) or '-'}")
    return "\n".join(out) + "\n"


def build_prompt(tid: str, inp: Path, work: Path, files: list[str], skipped: list[str],
                 root: Path = REPO_ROOT, assets: list[str] | None = None) -> str:
    rel = lambda p: p.relative_to(root)
    proj = project.load(root)
    example = (f"- tutorials/{proj.example}/: a finished tutorial to imitate (README.md, tutorial.yaml, manifests/)\n"
               if proj.example else "")
    big = f"\nToo big to copy (mention them if they matter): {', '.join(skipped)}" if skipped else ""
    if assets:
        big += ("\nImages and binary files are ALREADY copied into tutorials/" + tid + "/ at the same "
                "relative path (you cannot write binary files): " + ", ".join(assets) +
                ". Link images with relative paths, e.g. ![Architecture](images/architecture.svg); "
                "refer to the other files by those paths. Copies nothing refers to are removed afterwards.")
    return f"""You turn a folder of TESTED work into a {proj.name} tutorial in this repository's format.
Work in the repository at {root}.

Read first (fully):
- AGENTS.md and docs/authoring.md: the rules; lint enforces them
- {rel(work)}/parts.md: envs, helper scripts and shared steps you can reuse
{example}- tutorials/{tid}/: the scaffold to fill in (from tutorials/_template/)

The input (a copy; the author's original is not touched): {rel(inp)}/
Files: {", ".join(files)}{big}

Goal: tutorials/{tid}/ becomes a tutorial a reader can follow and CI can run:
- README.md is the source: every command the reader runs is a ```bash run|verify|cleanup|skip block.
  Keep the commands the author tested. Change one only to meet a rule (safe to run twice,
  ${proj.version_var} instead of a hard-coded version, kubectl wait instead of sleep, no colors/echo
  decoration) and list every such change in the notes.
- Inline the steps of helper scripts; leave out decoration (color codes, banners, print functions).
- Cluster creation and {proj.name} installation belong to an env (`env:`). If an env in parts.md fits,
  use it and drop those steps. If none fits, keep them as steps and say so in the notes.
- Use helper scripts and shared steps from parts.md where they do exactly what is needed.
- Kubernetes YAML goes to tutorials/{tid}/manifests/ and is shown with <!-- tut:include manifests/x.yaml -->.
  Other files the steps need (code, data) go under tutorials/{tid}/ too.
- Add verify blocks that prove each claim (retry=N delay=S where things take time) and a cleanup.
- Fill tutorial.yaml: title, summary, tags (from catalog/tags.yaml), versions, requires,
  owners (keep the scaffold's), status: draft, langs: [en].
- Prose: short, explain what each step does and why, in English.

Rules for this run:
- Write ONLY under tutorials/{tid}/ and {rel(work)}/. Do not change anything else.
- The only command you may run is: ./tut _draftcheck {tid}
  (runs ./tut sync, lint for this tutorial and a dry run; nothing touches a cluster).
  Run it after your edits and fix what it reports until it says "0 error(s)".
- When done, write {rel(work)}/notes.md: what you built, every input command you changed or left
  out and why, which env/helpers/shared steps you used, and TODOs for the author (things you
  could not verify, a missing env, ...).
"""


# ------------------------------------------------------------------ checks
_SKIP_LINE = re.compile(r"^(#|set -|\{|\}|fi$|done$|else$|then$|esac$|;;|do$|[A-Za-z_]+\(\)\s*\{?$|function )")
# Script plumbing, not a step a reader runs: control flow, exits, prompts, tool checks.
_PLUMBING = re.compile(r"^(if|elif|while|until|for|case)\b|^(exit|return|read|wait|shift|local|export -f|break|continue)\b"
                       r"|^command -v\b|^(true|false|:)$")


def script_commands(inp: Path) -> list[tuple[str, int, str]]:
    """(file, line, command) for the commands in the input shell scripts."""
    out = []
    scripts = {p.name for p in inp.rglob("*.sh")}
    call = re.compile(r'"?(?:[^\s"]*/)?([\w.-]+\.sh)"?(?:\s.*)?')   # "${DIR}/x.sh" args, ./scripts/x.sh

    def calls_script(c: str) -> bool:
        m = call.fullmatch(c)
        return bool(m) and m.group(1) in scripts
    for p in sorted(inp.rglob("*.sh")):
        lines = p.read_text(errors="replace").split("\n")
        heredoc, buf, start = None, "", 0
        for n, raw in enumerate(lines, 1):
            line = raw.strip()
            if heredoc:
                if line == heredoc:
                    heredoc = None
                continue
            if buf:
                buf += " " + line.rstrip("\\").strip()
            else:
                buf, start = line.rstrip("\\").strip(), n
            if raw.rstrip().endswith("\\"):
                continue
            cmd, buf = buf, ""
            m = re.search(r"<<-?\s*['\"]?(\w+)['\"]?", cmd)
            if m:
                heredoc = m.group(1)
            if not cmd or _SKIP_LINE.match(cmd) or _PLUMBING.match(cmd) \
                    or re.match(r"^(echo|printf|print_\w+)\b", cmd) or re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", cmd) \
                    or calls_script(cmd):                    # a call to another input script: it gets inlined
                continue
            out.append((str(p.relative_to(inp)), start, cmd))
    return out


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.replace("\\\n", " ")).strip()


def _loose(s: str) -> str:
    """Compare commands without caring how variables are named or quoted:
    `${NAMESPACE}`, `$NS` and `"$NS"` all become `$`."""
    s = re.sub(r'"?\$\{?[A-Za-z_][A-Za-z0-9_]*(:-[^}]*)?\}?"?', "$", s)
    # files moved into the tutorial (k8s/x.yaml -> manifests/x.yaml): compare by name
    s = re.sub(r"(?<![\w:/])(?:\.?/)?(?:[\w.-]+/)+([\w.-]+/?)", r"\1", s)
    return _norm(s.replace("'", "").replace('"', ""))


def coverage(inp: Path, tdir: Path) -> tuple[list, list]:
    """(found, missing) input commands in the tutorial's files; a command counts
    as found when it is there with only its variable names changed."""
    texts = "\n".join(p.read_text(errors="replace") for p in tdir.rglob("*")
                      if p.is_file() and not is_asset(p))
    corpus, loose = _norm(texts), _loose(texts)
    found, missing = [], []
    for f, n, cmd in script_commands(inp):
        (found if _norm(cmd) in corpus or _loose(cmd) in loose else missing).append((f, n, cmd))
    return found, missing


# Files `./tut sync` itself rewrites when a tutorial is added (owners, catalog).
SYNC_OUTPUTS = {".github/CODEOWNERS", "README.md", "README.ko.md"}


def changed_outside(before: set[str], tid: str, root: Path = REPO_ROOT) -> list[str]:
    allowed = (f"tutorials/{tid}/", "build/")
    now = git_dirty(root)
    return sorted(p for p in now - before if not p.startswith(allowed) and p not in SYNC_OUTPUTS
                  and not p.startswith("catalog/collections/"))        # --collection, written by us


def git_dirty(root: Path = REPO_ROOT) -> set[str]:
    r = subprocess.run(["git", "status", "--porcelain", "--untracked-files=all"], cwd=root,
                       capture_output=True, text=True)
    return {line[3:].split(" -> ")[-1] for line in r.stdout.splitlines() if line}


def add_to_collection(col: str, tid: str, owner: str | None, root: Path = REPO_ROOT) -> Path:
    """Append the tutorial to catalog/collections/<col>.yaml (created if missing).
    Done by the program: the AI may not write outside the tutorial."""
    if not scaffold.ID_RE.match(col):
        raise DraftError(f"invalid collection id {col!r}")
    p = root / "catalog" / "collections" / f"{col}.yaml"
    if p.exists():
        text = p.read_text()
        if re.search(rf"^\s*-\s*{re.escape(tid)}\s*$", text, re.M):
            return p
        p.write_text(text.rstrip("\n") + f"\n  - {tid}\n")
    else:
        p.parent.mkdir(parents=True, exist_ok=True)
        title = col.replace("-", " ").title()
        p.write_text(f"# A collection is an ordered reading path; tutorials stay independent.\n"
                     f"id: {col}\ntitle:\n  en: \"{title}\"\ndescription:\n  en: \"TODO: one sentence.\"\n"
                     f"owners: [{owner or 'your-github-handle'}]\nmembers:\n  - {tid}\n")
    return p


# ------------------------------------------------------------------ the run
@dataclass
class Result:
    tid: str
    work: Path
    outside: list[str] = field(default_factory=list)
    problems: list = field(default_factory=list)
    found: list = field(default_factory=list)
    missing: list = field(default_factory=list)
    agent_rc: int = 0
    assets_kept: list = field(default_factory=list)
    assets_removed: list = field(default_factory=list)
    collection: str | None = None


def draft(src: Path, tid: str | None, title: str | None, agent: Agent,
          root: Path = REPO_ROOT, timeout: int = 3600, log=print, owner: str | None = None,
          collection: str | None = None) -> Result:
    src = src.expanduser().resolve()
    if not src.is_dir():
        raise DraftError(f"{src} is not a folder")
    tid = tid or slug(src.name)
    before = git_dirty(root)
    tdir = scaffold.new_tutorial(tid, title=title, owner=owner, root=root)   # raises on a bad / existing id
    work = root / "build" / "draft" / tid
    if work.exists():
        shutil.rmtree(work)
    inp = work / "input"
    inp.mkdir(parents=True)
    files, skipped = copy_input(src, inp)
    assets = copy_assets(inp, tdir)
    (work / "parts.md").write_text(parts_catalog(root))
    prompt = build_prompt(tid, inp, work, files, skipped, root, assets)
    (work / "prompt.md").write_text(prompt)
    log(f"→ {tid}: {len(files)} input file(s) copied to {inp.relative_to(root)}; "
        f"running {agent.name} (this can take several minutes) …")
    with open(work / "agent.log", "w") as logf:
        if agent.shell:
            p = subprocess.run(agent.argv[0], shell=True, input=prompt, cwd=root, text=True,
                               stdout=logf, stderr=subprocess.STDOUT, timeout=timeout)
        else:
            argv = [prompt if a == "{prompt}" else a for a in agent.argv]
            p = subprocess.run(argv, cwd=root, stdin=subprocess.DEVNULL, text=True,
                               stdout=logf, stderr=subprocess.STDOUT, timeout=timeout)
    res = Result(tid, work, agent_rc=p.returncode)
    if collection:
        res.collection = str(add_to_collection(collection, tid, owner, root).relative_to(root))
    res.assets_removed = prune_assets(tdir, assets)
    example = tdir / "manifests" / "example.yaml"      # template leftover the AI cannot delete
    if example.exists() and "example.yaml" not in (tdir / "README.md").read_text():
        example.unlink()
        res.assets_removed.append("manifests/example.yaml (template)")
    res.assets_kept = [a for a in assets if a not in res.assets_removed]
    generate.sync(root)
    res.outside = changed_outside(before, tid, root)
    res.problems = [f for f in lint.Linter(root).run() if f.path.resolve().is_relative_to(tdir.resolve())]
    res.found, res.missing = coverage(inp, tdir)
    (work / "report.md").write_text(render_report(res, src, root))
    return res


def render_report(r: Result, src: Path, root: Path = REPO_ROOT) -> str:
    errs = [f for f in r.problems if f.severity == "error"]
    total = len(r.found) + len(r.missing)
    out = [f"# Draft report: {r.tid}", "",
           f"- input: `{src}` (copied to `{(r.work / 'input').relative_to(root)}`, original unchanged)",
           f"- AI exit code: {r.agent_rc} (log: `{(r.work / 'agent.log').relative_to(root)}`)",
           f"- AI notes: `{(r.work / 'notes.md').relative_to(root)}`"
           + ("" if (r.work / "notes.md").exists() else " — **missing**"),
           f"- lint: {len(errs)} error(s), {len(r.problems) - len(errs)} warning(s)",
           f"- input script commands in the tutorial (variable names may differ): {len(r.found)}/{total}"
           " (control flow, prompts, echo and tool checks are not counted)",
           f"- images / binary files copied in: {len(r.assets_kept)} used"
           + (f", {len(r.assets_removed)} unused removed ({', '.join(r.assets_removed)})" if r.assets_removed else ""),
           f"- files changed outside tutorials/{r.tid}/ and build/: {len(r.outside)}"]
    out += ([f"- added to the collection `{r.collection}`"] if r.collection else []) + [""]
    if r.outside:
        out += ["## ✗ Changed outside the allowed folders (review, then restore with git)", ""]
        out += [f"- `{p}`" for p in r.outside] + [""]
    if r.problems:
        out += ["## Lint", ""] + [f"- {f.severity} {f.code} line {f.line or '-'}: {f.message}" for f in r.problems] + [""]
    if r.missing:
        out += ["## Input commands not in the tutorial",
                "", "Changed or left out on purpose? The AI notes should say why; otherwise add them.", ""]
        out += [f"- `{f}:{n}` `{c[:140]}`" for f, n, c in r.missing] + [""]
    out += ["## Next", "", f"1. Read the AI notes and this report.",
            f"2. `./tut ui` → open **{r.tid}** → ✎ Edit: fix what is listed, Save & sync.",
            f"3. Run all in the UI, then `./tut run {r.tid} --twice`.", ""]
    return "\n".join(out)


def draftcheck(tid: str, root: Path = REPO_ROOT) -> int:
    """What the AI may run: sync, lint for this tutorial, dry run. No cluster."""
    from . import runner
    changed, errors = generate.sync(root)
    for e in errors:
        print("sync error:", e)
    t = next((x for x in load_tutorials(root) if x.id == tid), None)
    if t is None:
        print(f"no tutorial {tid}"); return 1
    findings = [f for f in lint.Linter(root).run() if f.path.resolve().is_relative_to(t.path.resolve())]
    for f in findings:
        print(f.format(root))
    n_err = sum(f.severity == "error" for f in findings) + len(errors)
    if not t.errors:
        try:
            script, steps = runner.build_script(t, None, keep=False)
            print(f"dry run: {len(steps)} step(s) would run")
        except Exception as e:                       # noqa: BLE001 - report, do not crash the agent
            print(f"dry run failed: {e}"); n_err += 1
    print(f"{n_err} error(s), {len(findings) - sum(f.severity == 'error' for f in findings)} warning(s)")
    return 1 if n_err else 0
