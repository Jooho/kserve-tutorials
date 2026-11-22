"""Which AI CLI the user chose: the one place that reads TUT_AI and friends.

  TUT_AI=claude | copilot | codex | cmd:<command>      (TUT_TRANSLATOR: older name)
  TUT_AI_ARGS="--model sonnet"                         (TUT_TRANSLATOR_ARGS: older name)
  TUT_AI_REVIEW / TUT_AI_REVIEW_ARGS                   the reviewer(s) of an explainer;
                                                       several: TUT_AI_REVIEW=claude,codex

Callers (translate, draft, explain) keep their own command lines per tool: what
the CLI may do differs per job. They share how the choice is read (backlog B19:
two readers of the same variables had drifted apart, see CI-013).
"""
from __future__ import annotations

import os
import shlex
from dataclasses import dataclass, field

TOOLS = ("claude", "copilot", "codex")
OLD_NAME = {"TUT_AI": "TUT_TRANSLATOR"}          # still read


class AICliError(Exception):
    pass


@dataclass
class Choice:
    name: str                                   # claude | copilot | codex | cmd
    command: str = ""                           # for cmd:<command>
    extra: list[str] = field(default_factory=list)   # the *_ARGS flags

    @property
    def shell(self) -> bool:
        return self.name == "cmd"


def read(var: str = "TUT_AI") -> Choice | None:
    """The CLI set in `var` (None: not set). Raises AICliError for an unknown tool."""
    old = OLD_NAME.get(var)
    spec = (os.environ.get(var) or (os.environ.get(old) if old else "") or "").strip()
    if not spec:
        return None
    if spec.startswith("cmd:"):
        return Choice("cmd", command=spec[4:].strip())
    if spec not in TOOLS:
        raise AICliError(f"{var}={spec!r}: use {', '.join(TOOLS[:-1])} or {TOOLS[-1]}, or cmd:<command>")
    args = os.environ.get(f"{var}_ARGS")
    if args is None and old:
        args = os.environ.get(f"{old}_ARGS")
    return Choice(spec, extra=shlex.split(args or ""))


def read_many(var: str) -> list[Choice]:
    """Several CLIs in one variable, comma-separated (TUT_AI_REVIEW=claude,codex):
    each one does the job on its own. cmd:<command> is always a single choice
    (a command may contain commas). The *_ARGS flags go to every one of them."""
    spec = (os.environ.get(var) or "").strip()
    if not spec:
        return []
    if spec.startswith("cmd:") or "," not in spec:
        c = read(var)
        return [c] if c else []
    names = [n.strip() for n in spec.split(",") if n.strip()]
    bad = [n for n in names if n not in TOOLS]
    if bad:
        raise AICliError(f"{var}={spec!r}: unknown {', '.join(bad)}; use {', '.join(TOOLS)} "
                         "(comma-separated), or one cmd:<command>")
    extra = shlex.split(os.environ.get(f"{var}_ARGS") or "")
    return [Choice(n, extra=list(extra)) for n in names]


def with_extra(template: list[str], extra: list[str]) -> list[str]:
    """`template` with the user's flags right before its {prompt} placeholder."""
    i = template.index("{prompt}")
    return template[:i] + list(extra) + template[i:]
