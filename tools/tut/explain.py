"""`./tut explain`: an AI-written explainer of a tutorial (PoC).

A tutorial's README is the test: terse steps and checks. An explainer is the
teacher next to it: what the tutorial is for, how the parts fit, pictures and
animated flows (SVG). It lives in tutorials/<id>/explainer/ and is read, never
executed: the runner, CI e2e (`plan.affected`) and the README ignore it.

Accuracy comes from a real run, not from memory. An AI agent drives a live
tutorial shell one block at a time and looks at the cluster between steps:

  ./tut explain start <id>            fresh shell for the tutorial (no cluster work yet)
  ./tut explain next <id>             run the next run/verify block, print its output
  ./tut explain probe <id> -- CMD     read-only look at the cluster (kubectl get/describe/
                                      logs/..., helm list/get/status), in the same shell
  ./tut explain status <id>           where the walk is
  ./tut explain stop <id>             run the cleanup blocks, end the shell
  ./tut explain check <id>            mechanical checks of the explainer (lint X001-X005)
  ./tut explain mark <id> [lang]      a person reviewed it: reviewed=yes
  ./tut explain review <id>           another AI (TUT_AI_REVIEW, else TUT_AI) checks the text
                                      against the evidence: build/explain/<id>/review.md
  ./tut explain draft <id>            all of the above by the AI CLI in TUT_AI, unattended

Every block output and every probe is appended to build/explain/<id>/evidence.md,
so a reviewer can see what each statement of the explainer rests on. Nothing in
here runs from `./tut sync` or CI: explainers are made on request only.

The explainer starts with a marker the UI and the site turn into an "AI-written"
banner (the page cannot hide it):

  <!-- tut-explainer source=README.md sha=<README hash> by=<tool> reviewed=no -->
"""
from __future__ import annotations

import json
import os
import re
import shlex
import signal
import subprocess
import time
import uuid
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

from . import markdown
from .model import EXPLAINER_DIR, LANGS, REPO_ROOT, Tutorial

MARKER_RE = re.compile(
    r"<!--\s*tut-explainer\s+source=(\S+)\s+sha=([0-9a-f]+)\s+by=(\S+)\s+reviewed=(yes|no)\s*-->")
EXEC_ROLES = {"run", "verify", "cleanup"}
MAX_SHOWN = 160                    # lines of a block output printed / kept in the evidence

# Probes may only look. kubectl verbs that read, and the read-only helm commands.
KUBECTL_READ = {"get", "describe", "logs", "explain", "api-resources", "api-versions",
                "top", "version", "cluster-info", "events"}
HELM_READ = {"list", "ls", "status", "get", "history", "show"}
NO_WAIT_FLAGS = {"-w", "--watch", "--watch-only", "--follow"}
UNSAFE = re.compile(r"[;&|<>`\n]|\$\(")


class ExplainError(Exception):
    pass


# --------------------------------------------------------------- the explainer
def state(t: Tutorial, lang: str = "en") -> str | None:
    """None (no explainer) | "draft" (AI, not reviewed) | "behind" (README changed
    since) | "ok" (reviewed, current) | "unmarked" (no marker)."""
    from .lint import source_hash
    p = t.explainer(lang)
    if not p.exists():
        return None
    m = MARKER_RE.search(p.read_text())
    if not m:
        return "unmarked"
    if m.group(4) == "no":
        return "draft"                 # the hash is recorded by `mark`
    return "ok" if m.group(2) == source_hash(t.readme("en").read_text()) else "behind"


def marker(t: Tutorial, lang: str = "en") -> dict | None:
    p = t.explainer(lang)
    m = MARKER_RE.search(p.read_text()) if p.exists() else None
    return None if not m else {"by": m.group(3), "reviewed": m.group(4) == "yes"}


def check(t: Tutorial) -> list[tuple[str, str, Path, str]]:
    """(severity, code, path, message) for tutorials/<id>/explainer/. Lint runs it."""
    from .lint import source_hash
    d = t.path / EXPLAINER_DIR
    out: list[tuple[str, str, Path, str]] = []
    if not d.is_dir():
        return out
    pages = [t.explainer(l) for l in LANGS if t.explainer(l).exists()]
    if not t.explainer("en").exists():
        out.append(("error", "X001", d, "explainer/index.md (English) is missing"))
    src = source_hash(t.readme("en").read_text()) if t.readme("en").exists() else ""
    for p in pages:
        text = p.read_text()
        m = MARKER_RE.search(text.split("\n", 1)[0])
        if not m:
            out.append(("error", "X001", p, "first line must be the AI marker "
                        "<!-- tut-explainer source=README.md sha=... by=... reviewed=no -->"))
        elif m.group(4) == "no":
            out.append(("warning", "X005", p, f"AI explainer (by {m.group(3)}) not reviewed yet: "
                        f"read it, then ./tut explain mark {t.id}"))
        elif m.group(2) != src:
            out.append(("warning", "X005", p, "README.md changed since this explainer was made "
                        f"(run ./tut explain draft {t.id} again)"))
        doc = markdown.parse(text)
        for b in doc.blocks:
            if b.role in EXEC_ROLES:
                out.append(("error", "X002", p, f"```{b.lang} {b.role}: an explainer is never "
                            "executed; show commands as plain ```bash", ))
        for target in _links(text):
            if not (p.parent / target.split("#")[0]).resolve().exists():
                out.append(("error", "X003", p, f"broken link or image: {target}"))
    for svg in sorted(d.rglob("*.svg")):
        out += [("error", "X004", svg, msg) for msg in svg_problems(svg)]
    return out


_LINK_RE = re.compile(r"!?\[[^\]]*\]\(([^)\s]+)[^)]*\)|(?:src|href)=\"([^\"]+)\"")


def _links(text: str) -> list[str]:
    out = []
    for m in _LINK_RE.finditer(text):
        target = m.group(1) or m.group(2)
        if target and not re.match(r"^[a-z][a-z0-9+.-]*:|^#|^/", target):
            out.append(target)
    return out


def svg_problems(path: Path) -> list[str]:
    """An explainer SVG is a picture: no script, no event handlers, nothing loaded
    from elsewhere. CSS and SMIL animation are fine (they run in <img> too)."""
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError as e:
        return [f"not well-formed XML: {e}"]
    probs = []
    if not root.tag.endswith("svg"):
        probs.append("root element is not <svg>")
    for el in root.iter():
        tag = el.tag.rsplit("}", 1)[-1]
        if tag in ("script", "foreignObject", "iframe", "object", "embed"):
            probs.append(f"<{tag}> is not allowed")
        for k, v in el.attrib.items():
            name = k.rsplit("}", 1)[-1]
            if name.lower().startswith("on"):
                probs.append(f"event handler {name}= on <{tag}>")
            if name == "href" and not v.startswith("#"):
                probs.append(f"<{tag} href={v!r}>: only #fragment references")
        if tag == "style" and el.text and re.search(r"@import|url\(\s*['\"]?(?!#)", el.text):
            probs.append("<style> loads something from outside (@import / url())")
    return sorted(set(probs))


def mark(t: Tutorial, lang: str = "en") -> Path:
    from .lint import source_hash
    p = t.explainer(lang)
    if not p.exists():
        raise ExplainError(f"{p} does not exist")
    errors = [f for f in check(t) if f[0] == "error"]
    if errors:
        raise ExplainError("fix these first:\n" + "\n".join(f"  {c} {pp}: {m}" for _, c, pp, m in errors))
    text = p.read_text()
    m = MARKER_RE.search(text)
    new = (f"<!-- tut-explainer source=README.md sha={source_hash(t.readme('en').read_text())} "
           f"by={m.group(3) if m else 'person'} reviewed=yes -->")
    p.write_text(MARKER_RE.sub(new, text, count=1) if m else new + "\n" + text)
    return p


# --------------------------------------------------------------- the live walk
@dataclass
class Step:
    n: int
    role: str
    line: int
    code: str
    attrs: dict


def steps(t: Tutorial) -> list[Step]:
    doc = markdown.parse(t.readme("en").read_text())
    blocks = [b for b in doc.blocks if b.is_shell and b.role in ("run", "verify")]
    return [Step(i + 1, b.role, b.line, b.code, b.attrs) for i, b in enumerate(blocks)]


def cleanups(t: Tutorial) -> list[str]:
    doc = markdown.parse(t.readme("en").read_text())
    return [b.code for b in doc.blocks if b.is_shell and b.role == "cleanup"]


def workdir(t: Tutorial, root: Path = REPO_ROOT) -> Path:
    return root / "build" / "explain" / t.id


class Session:
    """A bash process that reads commands from a FIFO, so separate `./tut explain`
    calls share one shell: variables, functions and `cd` carry over between
    blocks exactly as in the runner and the UI."""

    def __init__(self, t: Tutorial, root: Path = REPO_ROOT):
        self.t, self.root, self.d = t, root, workdir(t, root)
        self.fifo, self.log, self.statef = self.d / "in", self.d / "shell.log", self.d / "state.json"
        self.evidence = self.d / "evidence.md"

    # state ------------------------------------------------------------
    def load(self) -> dict:
        return json.loads(self.statef.read_text()) if self.statef.exists() else {}

    def save(self, st: dict) -> None:
        self.statef.write_text(json.dumps(st, indent=2))

    @property
    def alive(self) -> bool:
        pid = self.load().get("pid")
        if not pid:
            return False
        try:
            os.kill(pid, 0)
            return True
        except ProcessLookupError:
            return False

    # lifecycle --------------------------------------------------------
    def start(self, version: str | None = None) -> None:
        if self.alive:
            raise ExplainError(f"a walk of {self.t.id} is running; ./tut explain stop {self.t.id} first")
        if self.d.exists():
            for p in self.d.iterdir():
                if p.is_file() or p.is_fifo():
                    p.unlink()
        self.d.mkdir(parents=True, exist_ok=True)
        os.mkfifo(self.fifo)
        env = dict(os.environ, TUT_ID=self.t.id)
        if version:
            from . import project
            env[project.load(self.root).version_var] = version
        with open(self.log, "ab") as log:
            # fd 3 keeps the FIFO open for writing too, so bash never sees EOF
            # between two `./tut explain` calls.
            p = subprocess.Popen(
                ["bash", "--noprofile", "--norc", "-c",
                 'exec 3<>"$1"; exec bash --noprofile --norc <&3', "_", str(self.fifo)],
                cwd=self.root, env=env, stdin=subprocess.DEVNULL, stdout=log,
                stderr=subprocess.STDOUT, start_new_session=True)
        self.save({"pid": p.pid, "cursor": 0, "total": len(steps(self.t)),
                   "started": time.strftime("%Y-%m-%d %H:%M:%S"), "version": version})
        self.evidence.write_text(
            f"# Evidence: {self.t.id}\n\nA live walk of tutorials/{self.t.id}/README.md, "
            f"started {self.load()['started']}. Every run/verify block and every read-only "
            "probe, with what it printed.\n")

    def stop(self, run_cleanup: bool = True) -> str:
        out = ""
        if self.alive and run_cleanup:
            for i, code in enumerate(cleanups(self.t), 1):
                rc, text = self.run(code, f"cleanup{i}", timeout=900)
                self.record(f"## Cleanup {i}", code, rc, text)
                out += text
        st = self.load()
        if st.get("pid"):
            try:
                os.killpg(st["pid"], signal.SIGTERM)
            except ProcessLookupError:
                pass
            st["pid"] = None
            self.save(st)
        return out

    # running ------------------------------------------------------------
    def run(self, code: str, tag: str, timeout: float) -> tuple[int, str]:
        if not self.alive:
            raise ExplainError(f"no walk running for {self.t.id}: ./tut explain start {self.t.id}")
        f = self.d / f"{tag}.sh"
        f.write_text(code + "\n")
        tok = "__TUT_" + uuid.uuid4().hex
        offset = self.log.stat().st_size
        # stdin from /dev/null: a block that reads stdin (kubectl run -i) must not
        # eat the next commands from the FIFO. Failures are recorded, the shell lives on.
        cmd = (f"printf '\\n{tok} BEGIN\\n'\n"
               "__tut_err=0; trap '__tut_err=$?' ERR; set -E -o pipefail\n"
               f"source {shlex.quote(str(f))} </dev/null\n"
               "__tut_last=$?; trap - ERR; set +E\n"
               f"printf '\\n{tok} END %s\\n' \"$(( __tut_err ? __tut_err : __tut_last ))\"\n")
        with open(self.fifo, "w") as w:
            w.write(cmd)
        deadline = time.time() + timeout
        end_re = re.compile(rf"^{tok} END (\d+)$", re.M)
        while time.time() < deadline:
            with open(self.log, "rb") as r:
                r.seek(offset)
                chunk = r.read().decode(errors="replace")
            m = end_re.search(chunk)
            if m:
                begin = chunk.find(f"{tok} BEGIN\n")
                body = chunk[begin + len(tok) + 7:m.start()] if begin >= 0 else chunk[:m.start()]
                return int(m.group(1)), _strip_ansi(body).strip("\n")
            if not self.alive:
                raise ExplainError("the tutorial shell exited (a block ran `exit`?); start again")
            time.sleep(0.5)
        raise ExplainError(f"{tag}: no result after {int(timeout)} s; the shell is still busy "
                           f"(./tut explain stop {self.t.id} ends it)")

    def record(self, title: str, code: str, rc: int, out: str, lang: str = "bash") -> None:
        with open(self.evidence, "a") as e:
            e.write(f"\n{title} (exit {rc})\n\n```{lang}\n{code.rstrip()}\n```\n\n"
                    f"```text\n{_shorten(out)}\n```\n")

    def next(self) -> tuple[Step, int, str]:
        st = self.load()
        all_steps = steps(self.t)
        if st.get("cursor", 0) >= len(all_steps):
            raise ExplainError(f"all {len(all_steps)} steps ran; probe more, or ./tut explain stop {self.t.id}")
        s = all_steps[st["cursor"]]
        tries = int(s.attrs.get("retry", "1")) if s.role == "verify" else 1
        delay = int(s.attrs.get("delay", "10"))
        timeout = int(self.t.meta.get("timeout_minutes", 45)) * 60
        for i in range(tries):
            rc, out = self.run(s.code, f"step{s.n:02d}", timeout)
            if rc == 0 or i == tries - 1:
                break
            time.sleep(delay)
        self.record(f"## Step {s.n}/{len(all_steps)} - {s.role} - README.md:{s.line}", s.code, rc, out)
        st["cursor"] += 1
        self.save(st)
        return s, rc, out

    def probe(self, argv: list[str]) -> tuple[int, str]:
        line = probe_command(argv)
        st = self.load()
        rc, out = self.run(f"( timeout 120 {line} )", f"probe{int(time.time() * 1000)}", timeout=150)
        self.record(f"### Probe after step {st.get('cursor', 0)}: `{' '.join(argv)}`", line, rc, out)
        return rc, out


def probe_command(argv: list[str]) -> str:
    """The shell line for a read-only probe, or ExplainError. `$NS` and other shell
    variables of the tutorial expand; nothing else of the shell does."""
    if not argv:
        raise ExplainError("probe needs a command, e.g. -- kubectl get pods -n \"$NS\"")
    tool, rest = argv[0], argv[1:]
    words = _positional(rest)
    verb = words[0] if words else ""
    if tool == "kubectl":
        ok = verb in KUBECTL_READ or rest[:2] == ["auth", "can-i"] or \
            (verb == "config" and len(words) > 1 and words[1] in ("view", "current-context", "get-contexts"))
        if verb == "logs" and "-f" in rest:
            ok = False
    elif tool == "helm":
        ok = verb in HELM_READ
    else:
        ok = False
    if not ok:
        raise ExplainError(f"not a read-only probe: {' '.join(argv)!r} (allowed: kubectl "
                           f"{'/'.join(sorted(KUBECTL_READ))}, auth can-i, config view; "
                           f"helm {'/'.join(sorted(HELM_READ))})")
    if NO_WAIT_FLAGS & set(rest):
        raise ExplainError("probes must return: no --watch / --follow")
    for a in argv:
        if UNSAFE.search(a):
            raise ExplainError(f"shell syntax is not allowed in a probe argument: {a!r} "
                               "(pipe the output of ./tut explain probe yourself)")
    return " ".join('"' + a.replace("\\", "\\\\").replace('"', '\\"') + '"' for a in argv)


# Flags that take the next argument as their value (kubectl / helm). Their value
# is skipped so `kubectl -n get delete ns x` reads as verb "delete", not "get".
VALUE_FLAGS = {"-n", "--namespace", "--context", "--cluster", "--user", "--kubeconfig",
               "-s", "--server", "--token", "--as", "--as-group", "--request-timeout",
               "-l", "--selector", "-o", "--output", "-c", "--container", "--field-selector",
               "--kube-context", "--tail", "--since", "--sort-by", "-L", "--label-columns"}


def _positional(args: list[str]) -> list[str]:
    out, skip = [], False
    for a in args:
        if skip:
            skip = False
        elif a.startswith("-"):
            skip = "=" not in a and a in VALUE_FLAGS
        else:
            out.append(a)
    return out


def _strip_ansi(s: str) -> str:
    return re.sub(r"\x1b\[[0-9;?]*[A-Za-z]", "", s)


def _shorten(out: str, keep: int = MAX_SHOWN) -> str:
    lines = out.split("\n")
    if len(lines) <= keep:
        return out
    half = keep // 2
    return "\n".join(lines[:half] + [f"... ({len(lines) - keep} lines cut) ..."] + lines[-half:])


# --------------------------------------------------------------- unattended (TUT_AI)
AGENT_TOOLS = {
    "claude": ["claude", "-p", "{prompt}", "--permission-mode", "acceptEdits",
               "--allowedTools", "Read,Write,Edit,Glob,Grep,Bash(./tut explain:*)",
               "--output-format", "text"],
    "codex": ["codex", "exec", "--skip-git-repo-check", "--sandbox", "workspace-write", "{prompt}"],
    "copilot": ["copilot", "-p", "{prompt}", "--allow-tool", "write",
                "--allow-tool", "shell(./tut explain)", "-s", "--no-color"],
}


def build_prompt(t: Tutorial, root: Path = REPO_ROOT) -> str:
    guide = (root / "docs" / "explainer.md")
    langs = [l for l in LANGS if t.readme(l).exists()]
    return f"""You are writing the explainer of the tutorial `{t.id}` in this repository.
Work alone from start to end; nobody will answer questions. Read docs/explainer.md
first: it is the brief (what an explainer is, its shape, SVG rules).{'' if guide.exists() else ' (missing!)'}

Material: tutorials/{t.id}/README.md (the tutorial and its test), tutorial.yaml,
manifests/, and the files it includes. Then walk it on the cluster:

  ./tut explain start {t.id}
  ./tut explain next {t.id}                 (repeat until every step ran)
  ./tut explain probe {t.id} -- kubectl ... (read-only, as often as you need)
  ./tut explain stop {t.id}                 (when you know enough; runs cleanup)

Rules for accuracy:
- Before you state a fact about what exists or happens in the cluster (resource
  kinds and counts, container names, ports, labels, which component calls which,
  log lines, metric names), see it in a step output or a probe. The walk is
  recorded in build/explain/{t.id}/evidence.md.
- Where the README text and what you observed differ, say so in your notes
  (build/explain/{t.id}/notes.md); describe what you observed.
- Values that change every run (IPs, generated names, timings) are examples only.

Write only these files:
- tutorials/{t.id}/explainer/index.md (English){''.join(f', index.{l}.md' for l in langs if l != 'en')}
- tutorials/{t.id}/explainer/*.svg (diagrams; at least one animated flow)
- build/explain/{t.id}/notes.md (what you checked, what differs from the README, open doubts)

Finish with ./tut explain check {t.id} and fix every error it reports. Do not
mark the explainer reviewed; a person does that.
"""


def _argv(template: list[str] | None, agent, prompt: str) -> list[str]:
    """A command line for `agent`: this module's template (its permissions) with
    the user's *_ARGS flags (e.g. --model) before the prompt; without a template,
    the agent's own command line (it already has them)."""
    if template is None:
        return [prompt if a == "{prompt}" else a for a in agent.argv]
    i = template.index("{prompt}")
    return template[:i] + list(getattr(agent, "extra", [])) + [prompt] + template[i + 1:]


def _run_agent(agent, template: list[str] | None, prompt: str, root: Path, logf, timeout: int,
               capture: bool = False) -> tuple[int, str]:
    """Run an AI CLI once. cmd:<command> agents get the prompt on stdin."""
    out = subprocess.PIPE if capture else logf
    if agent.shell:
        p = subprocess.run(agent.argv[0], shell=True, input=prompt, cwd=root, text=True,
                           stdout=out, stderr=logf, timeout=timeout)
    else:
        argv = _argv(template, agent, prompt)
        p = subprocess.run(argv, cwd=root, stdin=subprocess.DEVNULL, text=True,
                           stdout=out, stderr=logf, timeout=timeout)
    return p.returncode, (p.stdout or "") if capture else ""


def draft(t: Tutorial, agent, root: Path = REPO_ROOT, timeout: int = 7200, log=print,
          reviewer=None, reviewers=None) -> int:
    """Run the AI CLI (TUT_AI) with build_prompt; it drives start/next/probe/stop
    itself. Afterwards: the shell is always stopped. With reviewers (TUT_AI_REVIEW,
    one or several, else TUT_AI): each reviews on its own, the writer decides every
    finding in one fix round, then they review again."""
    reviewers = list(reviewers or ([reviewer] if reviewer else []))
    d = workdir(t, root)
    d.mkdir(parents=True, exist_ok=True)
    prompt = build_prompt(t, root)
    (d / "prompt.md").write_text(prompt)
    log(f"-> {t.id}: {agent.name} walks the tutorial on the cluster and writes the explainer "
        "(15-30 minutes) ...")
    try:
        with open(d / "agent.log", "w") as logf:
            rc, _ = _run_agent(agent, AGENT_TOOLS.get(agent.name), prompt, root, logf, timeout)
    finally:
        s = Session(t, root)
        if s.alive:
            log("the agent left the tutorial shell running: cleaning up")
            s.stop()
    if rc or not reviewers or not t.explainer("en").exists():
        return rc
    n = review_all(t, reviewers, root, log=log)
    if n:
        log(f"-> {agent.name} decides the {n} finding(s): fix or reject, with the reason (no cluster) ...")
        with open(d / "agent.log", "a") as logf:
            rc, _ = _run_agent(agent, AGENT_TOOLS.get(agent.name), build_fix_prompt(t, root),
                               root, logf, timeout)
        (d / "review.md").rename(d / "review-1.md")
        n = review_all(t, reviewers, root, log=log)
    return rc


# ------------------------------------------------------------- review (TUT_AI_REVIEW)
# The reviewer only reads; its report is what it prints.
REVIEW_TOOLS = {
    "claude": ["claude", "-p", "{prompt}", "--allowedTools", "Read,Glob,Grep",
               "--output-format", "text"],
    "codex": ["codex", "exec", "--skip-git-repo-check", "--sandbox", "read-only", "{prompt}"],
    "copilot": ["copilot", "-p", "{prompt}", "-s", "--no-color"],
}
FINDINGS_RE = re.compile(r"^FINDINGS:\s*(\d+)\s*$", re.M)
KINDS = ("unsupported", "overgeneralized", "missing-reason", "contradicted", "mismatch")


def build_review_prompt(t: Tutorial, root: Path = REPO_ROOT) -> str:
    e = t.explainer("en").parent.relative_to(root)
    w = workdir(t, root).relative_to(root)
    return f"""You review an explainer another AI wrote for the tutorial `{t.id}`. Be
skeptical: your job is to find statements the evidence does not carry. You
cannot run anything and you change no file; you only read and report.

Read:
- {e}/index.md and any {e}/index.<lang>.md, and the text inside {e}/*.svg
- {w}/evidence.md: every step output and probe of the live run (the only
  evidence about the cluster)
- {w}/notes.md if it exists, tutorials/{t.id}/README.md, docs/explainer.md (the rules)

Check the statements about this cluster and this product (what exists, counts,
names, ports, labels, who calls whom, why something is there). Report one that
is not fine as one of:
- unsupported: a fact about this run that nothing in evidence.md shows
- overgeneralized: the evidence shows it for this run, environment or
  configuration; the text says it is always so. Look hard at every place where
  the text says the README is wrong or differs: could the difference come from
  this environment or a setting rather than from the README?
- missing-reason: a part a reader would not expect (a container on a Pod
  that does not seem to need it, an idle sidecar, an extra route) is named
  without saying why it is there
- contradicted: evidence.md shows something else
- mismatch: a translation or an SVG states a fact the English text contradicts
Not findings: general Kubernetes or product background, and what an API field
means by its definition (what an init container or failureMode: FailOpen
does); explanations of mechanism that follow from observed configuration;
statements labelled as coming from the product source; answers in "Check
yourself" that follow from the text. Report a statement once even if every
language repeats it (name the English file). Fewer, real findings are worth
more than many weak ones.

Output, and nothing else:
- one line per finding:
  - [<kind>] <file>: "<the statement, short>" -- <why>; evidence: <evidence.md line or "none">
- then the last line exactly: FINDINGS: <number of findings>
"""


def build_fix_prompt(t: Tutorial, root: Path = REPO_ROOT) -> str:
    w = workdir(t, root).relative_to(root)
    return f"""One or more reviewers checked the explainer of `{t.id}` against the
evidence of the run, each on its own. Their findings are in {w}/review.md (two
reviewers may report the same thing in different words). The cluster walk is
over; do not start it again.

Decide every finding; a reviewer can be wrong.
- Accept it when {w}/evidence.md does not carry the statement: correct it if
  the evidence supports a correct one, narrow it ("in this run", "with this
  configuration"), add the missing reason only if the evidence or a labelled
  source gives it, or remove it. Apply the same change to every language and
  SVG.
- Reject it when the text is right as written: the evidence shows it (name the
  line), or it is general background or follows from a definition. Do not hedge
  a correct sentence only because someone asked; the page must still teach.

Write the decisions in {w}/notes.md under a heading "## Review round", one line
per finding: "A: <finding> -> <what you changed>" or "R: <finding> -> <why it
stays>". The person who reads the explainer afterwards starts from that list.
Then ./tut explain check {t.id} must report 0 errors. Do not mark the explainer
reviewed.
"""


def review(t: Tutorial, agent, root: Path = REPO_ROOT, timeout: int = 1800, log=print,
           name: str = "review") -> int | None:
    """Let a reviewer AI compare the explainer with evidence.md. Writes
    build/explain/<id>/<name>.md; returns the number of findings (None: unknown)."""
    d = workdir(t, root)
    if not t.explainer("en").exists():
        raise ExplainError(f"{t.id} has no explainer to review")
    if not (d / "evidence.md").exists():
        raise ExplainError(f"no evidence for {t.id}: walk it first (./tut explain start {t.id})")
    log(f"-> {agent.name} reviews the explainer of {t.id} against the evidence ...")
    with open(d / f"{name}.log", "w") as logf:
        rc, out = _run_agent(agent, REVIEW_TOOLS.get(agent.name), build_review_prompt(t, root),
                             root, logf, timeout, capture=True)
    m = FINDINGS_RE.findall(out)
    n = int(m[-1]) if m else None
    (d / f"{name}.md").write_text(f"# Review of the {t.id} explainer by {agent.name}\n\n{out.strip()}\n")
    if rc:
        raise ExplainError(f"reviewer {agent.name} failed (exit {rc}); see {d / (name + '.log')}")
    log(f"   {agent.name}: {'?' if n is None else n} finding(s): {(d / (name + '.md')).relative_to(root)}")
    return n


def review_all(t: Tutorial, agents: list, root: Path = REPO_ROOT, timeout: int = 1800,
               log=print) -> int | None:
    """Every reviewer checks the explainer on its own, at the same time, without
    seeing the others. One reviewer: review.md as before. Several: one
    review-<name>.md each and review.md with all of them. Returns the findings in
    total (None: no reviewer gave a count). A reviewer that fails is reported and
    left out; if all fail, that is an error."""
    if len(agents) == 1:
        return review(t, agents[0], root, timeout, log)
    from concurrent.futures import ThreadPoolExecutor
    d = workdir(t, root)
    labels, seen = [], {}
    for a in agents:                       # claude, claude-2 when the same tool is listed twice
        seen[a.name] = seen.get(a.name, 0) + 1
        labels.append(a.name if seen[a.name] == 1 else f"{a.name}-{seen[a.name]}")

    def one(pair):
        label, a = pair
        try:
            return label, review(t, a, root, timeout, log, name=f"review-{label}"), None
        except ExplainError as e:
            return label, None, str(e)

    with ThreadPoolExecutor(max_workers=len(agents)) as pool:
        results = list(pool.map(one, zip(labels, agents)))
    failed = [(label, err) for label, _, err in results if err]
    for label, err in failed:
        log(f"   {label}: {err}")
    if len(failed) == len(agents):
        raise ExplainError("every reviewer failed: " + "; ".join(err for _, err in failed))
    parts = [f"# Reviews of the {t.id} explainer: {', '.join(labels)} (each on its own)\n"]
    for label, n, err in results:
        f = d / f"review-{label}.md"
        body = f.read_text().split("\n", 2)[-1].strip() if f.exists() else ""
        parts.append(f"## {label}\n\n{body or ('(failed: ' + str(err) + ')')}\n")
    (d / "review.md").write_text("\n".join(parts))
    counts = [n for _, n, err in results if n is not None and not err]
    total = sum(counts) if counts else None
    log(f"   {'?' if total is None else total} finding(s) in total: {(d / 'review.md').relative_to(root)}")
    return total
