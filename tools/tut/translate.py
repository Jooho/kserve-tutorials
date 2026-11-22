"""`./tut translation draft`: translate a tutorial README with an AI CLI the
user is already logged in to — no API keys in this repository.

Choose the tool with TUT_AI (shell, or `./tut config TUT_AI=…`; the older name
TUT_TRANSLATOR is still read):

  claude          Claude Code      claude -p <prompt>
  copilot         GitHub Copilot   copilot -p <prompt> -s
  codex           OpenAI Codex     codex exec --sandbox read-only … <prompt>
  cmd:<command>   anything else    <command> (prompt on stdin, translation on stdout)

TUT_AI_ARGS adds flags (e.g. "--model sonnet").

The model only returns text. Its output is checked by a program before it is
written: every code block, command, generated region, HTML comment and link
target must be unchanged (comments inside code may be translated). A draft that
fails is not written. A draft that passes is marked "AI draft, not reviewed";
a person (or agent) reviews it and runs `./tut translation mark`.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from . import aicli, markdown, project

BEGIN, END = "<<<TUT-TRANSLATION-BEGIN>>>", "<<<TUT-TRANSLATION-END>>>"
LANG_NAMES = {"ko": "Korean (한국어)"}

PRESETS = {
    "claude": ["claude", "-p", "{prompt}", "--output-format", "text"],
    "copilot": ["copilot", "-p", "{prompt}", "-s", "--no-color"],
    "codex": ["codex", "exec", "--skip-git-repo-check", "--ephemeral", "--sandbox", "read-only",
              "-o", "{outfile}", "{prompt}"],
}



class TranslationError(Exception):
    pass


@dataclass
class Translator:
    name: str          # claude | copilot | codex | cmd
    argv: list[str]    # with {prompt} / {outfile} placeholders, or a shell command
    shell: bool = False

    @property
    def available(self) -> bool:
        return self.shell or shutil.which(self.argv[0]) is not None


def configured() -> Translator | None:
    try:
        c = aicli.read("TUT_AI")
    except aicli.AICliError as e:
        raise TranslationError(str(e)) from None
    if c is None:
        return None
    if c.shell:
        return Translator("cmd", [c.command], shell=True)
    return Translator(c.name, aicli.with_extra(PRESETS[c.name], c.extra))


def build_prompt(source: str, lang: str, proj: "project.Project | None" = None) -> str:
    """`proj` names the product and its terms (project.yaml); without it only the
    common Kubernetes terms are kept in English."""
    name = LANG_NAMES.get(lang, lang)
    product = f"{proj.name} " if proj else ""
    keep = proj.keep_english() if proj else list(project.COMMON_GLOSSARY)
    return f"""Translate this {product}tutorial README from English to {name}.

A program checks your output; if any rule is broken the translation is discarded.
1. Translate prose, headings, list and table text, link text and image alt text.
2. Inside fenced code blocks translate ONLY comment text (after `#`); keep every
   command, flag, path, YAML key and value, and the fence lines exactly.
3. Keep every HTML comment line exactly (`<!-- ... -->`), and keep everything
   between a `<!-- tut:... -->` line and the next `<!-- /tut -->` line unchanged.
4. Keep link and image targets (the part in parentheses) unchanged.
5. Keep these names in English: {", ".join(keep)}.
6. Do not add, remove or reorder sections, steps, code blocks or notes.
Use a natural technical {name} style for engineers.

Output exactly three parts and nothing else:
{BEGIN}
<the translated Markdown>
{END}

=== README.md (English source) ===
{source}"""


def run(tr: Translator, prompt: str, timeout: int = 900) -> str:
    with tempfile.TemporaryDirectory(prefix="tut-translate-") as tmp:
        outfile = Path(tmp) / "last-message.txt"
        if tr.shell:
            p = subprocess.run(tr.argv[0], shell=True, input=prompt, capture_output=True,
                               text=True, timeout=timeout)
        else:
            argv = [outfile.as_posix() if a == "{outfile}" else prompt if a == "{prompt}" else a
                    for a in tr.argv]
            p = subprocess.run(argv, capture_output=True, text=True, timeout=timeout,
                               stdin=subprocess.DEVNULL, cwd=tmp)
        out = outfile.read_text() if outfile.exists() else p.stdout
        if p.returncode != 0 and BEGIN not in out:
            raise TranslationError(f"{tr.name} exited {p.returncode}: {(p.stderr or p.stdout)[-800:]}")
        return out


def extract(output: str) -> str:
    if BEGIN not in output or END not in output:
        raise TranslationError("the AI did not return the translation between the markers")
    body = output.split(BEGIN, 1)[1].rsplit(END, 1)[0]
    body = body.strip("\n")
    m = re.fullmatch(r"```(?:markdown|md)?\n(.*)\n```", body, re.S)   # tolerate a wrapping fence
    return (m.group(1) if m else body) + "\n"


# ---------------------------------------------------------------- checking
_TRAILING_COMMENT = re.compile(r"\s+#\s.*$")


def _code_skeleton(code: str) -> list[str]:
    """Code lines with comments removed (comments may be translated)."""
    out = []
    for line in code.split("\n"):
        if line.strip().startswith("#") or not line.strip():
            continue
        out.append(_TRAILING_COMMENT.sub("", line).rstrip())
    return out


def _structure(text: str) -> dict:
    doc = markdown.parse(text)
    lines = text.split("\n")
    region_lines = set()
    for r in doc.regions:
        region_lines.update(range(r.start, r.end + 1))
    return {
        "blocks": [(b.lang, b.role, tuple(sorted(b.attrs.items())), _code_skeleton(b.code))
                   for b in doc.blocks if b.in_region is None],
        "regions": [(r.kind, tuple(r.args)) for r in doc.regions],
        "comments": [l.strip() for i, l in enumerate(lines)
                     if l.strip().startswith("<!--") and i not in region_lines],
        "targets": sorted(m.group(1) for m in re.finditer(r"\]\(([^)\s]+)", text)),
        "headings": [lvl for lvl, _ in markdown.headings(text)],
    }


def check(source: str, translated: str) -> list[str]:
    """Problems that make a translation unusable (empty list = OK)."""
    a, b = _structure(source), _structure(translated)
    problems = []
    if len(a["blocks"]) != len(b["blocks"]):
        problems.append(f"code blocks: {len(b['blocks'])} instead of {len(a['blocks'])}")
    for n, (x, y) in enumerate(zip(a["blocks"], b["blocks"]), 1):
        if x[:3] != y[:3]:
            problems.append(f"code block {n}: fence changed ({y[0]} {y[1]} vs {x[0]} {x[1]})")
        elif x[3] != y[3]:
            problems.append(f"code block {n}: code changed (only comments may be translated)")
    for key, what in (("regions", "generated regions"), ("comments", "HTML comments"),
                      ("targets", "link targets"), ("headings", "heading structure")):
        if a[key] != b[key]:
            problems.append(f"{what} changed")
    return problems


@dataclass
class DraftResult:
    ok: bool
    message: str
    path: Path | None = None        # the draft written, or the rejected output


def draft_one(t, lang: str, tr: Translator, root: Path | None = None) -> DraftResult:
    """Translate one tutorial's README.md, check it, write it as an AI draft.
    A rejected output is kept in build/translations/ and nothing is written."""
    import subprocess
    from . import generate, lint
    from .model import REPO_ROOT
    root = root or REPO_ROOT
    src = t.readme("en").read_text()
    try:
        text = extract(run(tr, build_prompt(src, lang, project.load(root))))
    except (TranslationError, subprocess.TimeoutExpired) as e:
        return DraftResult(False, str(e))
    problems = check(src, text)
    if problems:
        rej = root / "build" / "translations" / f"{t.id}.{lang}.rejected.md"
        rej.parent.mkdir(parents=True, exist_ok=True)
        rej.write_text(text)
        return DraftResult(False, "rejected, nothing written: " + "; ".join(problems), rej)
    path = lint.write_draft(t, lang, text, tr.name)
    generate.sync(root)
    return DraftResult(True, f"wrote {path.relative_to(root)} (AI draft, not reviewed)", path)
