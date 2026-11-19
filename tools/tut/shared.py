"""Shared steps (PoC): write a step once, reuse it in other tutorials.

A tutorial marks steps that other tutorials may need:

    <!-- tut:define deploy-model -->
    ```bash run
    ...
    ```
    ```bash verify
    ...
    ```
    <!-- /tut -->

Another tutorial asks for them with one line; `./tut sync` copies the steps
into its README, so every README stays complete on its own (GitHub, CI):

    <!-- tut:use deploy-model -->
    <!-- /tut -->

Standalone (search, CI): every step is shown and run.
In a learning path (a collection opened in the UI): a shared step that an
earlier member already defined or used is "covered": its `run` blocks are
hidden and only its `verify` blocks run, to check that the state is there.

Rules (lint D014): one definition per name; `use` needs an existing name; no
markers inside a definition; a tutorial does not use what it defines.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from . import markdown
from .model import Tutorial

KINDS = ("define", "use")
NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


@dataclass
class Shared:
    kind: str           # define | use
    name: str
    region: markdown.Region


def regions(doc: markdown.Doc) -> list[Shared]:
    return [Shared(r.kind, r.args[0] if r.args else "", r)
            for r in doc.regions if r.kind in KINDS]


def _readme(t: Tutorial, lang: str) -> Path:
    return t.readme(lang) if t.readme(lang).exists() else t.readme("en")


def definitions(tutorials: list[Tutorial], lang: str = "en") -> dict[str, list[tuple[str, str]]]:
    """{name: [(tutorial id, body), ...]} — more than one entry is a lint error."""
    out: dict[str, list[tuple[str, str]]] = {}
    for t in tutorials:
        p = _readme(t, lang)
        if not p.exists():
            continue
        for s in regions(markdown.parse(p.read_text())):
            if s.kind == "define" and s.name:
                out.setdefault(s.name, []).append((t.id, s.region.body))
    return out


def render_use(name: str, lang: str, tutorials: list[Tutorial]) -> str:
    defs = definitions(tutorials, lang).get(name) or definitions(tutorials, "en").get(name)
    if not defs:
        raise ValueError(f"tut:use {name}: no tutorial defines it (<!-- tut:define {name} -->)")
    tid, body = defs[0]
    note = f"<!-- Copied from {tid} (tut:define {name}) by `./tut sync` — do not edit by hand. -->"
    return note + "\n\n" + body.strip("\n")


def block_names(doc: markdown.Doc) -> dict[int, str]:
    """{block index: shared step name} for blocks inside define/use regions."""
    out = {}
    for s in regions(doc):
        for i, b in enumerate(doc.blocks):
            if s.region.start < b.line - 1 < s.region.end:
                out[i] = s.name
    return out


def names_in(t: Tutorial, lang: str = "en") -> list[str]:
    p = _readme(t, lang)
    return [s.name for s in regions(markdown.parse(p.read_text()))] if p.exists() else []


def covered(members: list[str], tid: str, tutorials: dict[str, Tutorial],
            lang: str = "en") -> dict[str, str]:
    """{shared step name: id of the earlier member that has it} for `tid` in a
    learning path. Only members before `tid` count; order = collection order."""
    seen: dict[str, str] = {}
    for m in members:
        if m == tid:
            break
        if m in tutorials:
            for name in names_in(tutorials[m], lang):
                seen.setdefault(name, m)
    return seen
