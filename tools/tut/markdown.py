"""Parse the parts of a tutorial README that the tooling cares about.

Two constructs make a README executable and verifiable:

1. Fenced code blocks with a role (shell blocks only):

       ```bash run        executed by the runner, in order
       ```bash verify     executed; a failure fails the tutorial
       ```bash cleanup    always executed at the end (even after a failure)
       ```bash skip       shown to readers only (interactive, optional, ...)

   Extra attributes: `retry=N delay=S` on verify blocks.

2. Generated regions, owned by `./tut sync` and never edited by hand:

       <!-- tut:include manifests/foo.yaml -->
       ...
       <!-- /tut -->
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

SHELL_LANGS = {"bash", "sh", "shell"}
ROLES = {"run", "verify", "cleanup", "skip"}

FENCE_RE = re.compile(r"^(?P<indent>\s*)(?P<fence>`{3,}|~{3,})(?P<info>.*)$")
REGION_OPEN_RE = re.compile(r"^\s*<!--\s*tut:(?P<kind>[a-z-]+)(?P<args>[^>]*?)\s*-->\s*$")
REGION_CLOSE_RE = re.compile(r"^\s*<!--\s*/tut\s*-->\s*$")


@dataclass
class Block:
    lang: str
    role: str | None
    attrs: dict[str, str]
    code: str
    line: int                 # 1-based line of the opening fence
    in_region: str | None     # kind of generated region the block sits in
    raw_info: str = ""
    end: int = 0              # 1-based line of the closing fence

    @property
    def is_shell(self) -> bool:
        return self.lang in SHELL_LANGS


@dataclass
class Region:
    kind: str
    args: list[str]
    start: int                # 0-based index of the opening marker line
    end: int                  # 0-based index of the closing marker line
    body: str                 # text between the markers (without them)


@dataclass
class Doc:
    text: str
    blocks: list[Block] = field(default_factory=list)
    regions: list[Region] = field(default_factory=list)
    errors: list[tuple[int, str]] = field(default_factory=list)


def parse_info(info: str) -> tuple[str, str | None, dict[str, str], list[str]]:
    parts = info.strip().split()
    if not parts:
        return "", None, {}, []
    lang, rest = parts[0], parts[1:]
    role, attrs, unknown = None, {}, []
    for p in rest:
        if "=" in p:
            k, v = p.split("=", 1)
            attrs[k] = v
        elif p in ROLES and role is None:
            role = p
        else:
            unknown.append(p)
    return lang, role, attrs, unknown


def parse(text: str) -> Doc:
    doc = Doc(text=text)
    lines = text.split("\n")
    i = 0
    region: tuple[str, list[str], int] | None = None
    while i < len(lines):
        line = lines[i]
        if region is None:
            m = REGION_OPEN_RE.match(line)
            if m:
                region = (m.group("kind"), m.group("args").split(), i)
                i += 1
                continue
        if REGION_CLOSE_RE.match(line):
            if region is None:
                doc.errors.append((i + 1, "closing <!-- /tut --> without an opening marker"))
            else:
                kind, args, start = region
                doc.regions.append(Region(kind, args, start, i, "\n".join(lines[start + 1:i])))
                region = None
            i += 1
            continue
        m = FENCE_RE.match(line)
        if m:
            fence = m.group("fence")
            lang, role, attrs, unknown = parse_info(m.group("info"))
            start = i
            i += 1
            body = []
            while i < len(lines):
                cm = FENCE_RE.match(lines[i])
                if cm and cm.group("fence")[0] == fence[0] and len(cm.group("fence")) >= len(fence) \
                        and not cm.group("info").strip():
                    break
                body.append(lines[i])
                i += 1
            else:
                doc.errors.append((start + 1, "unclosed code fence"))
            indent = len(m.group("indent"))
            code = "\n".join(l[indent:] if l[:indent].isspace() else l for l in body)
            blk = Block(lang, role, attrs, code, start + 1, region[0] if region else None,
                        raw_info=m.group("info").strip(), end=i + 1)
            if unknown:
                doc.errors.append((start + 1, f"unknown fence tokens {unknown!r}"))
            doc.blocks.append(blk)
            i += 1
            continue
        i += 1
    if region is not None:
        doc.errors.append((region[2] + 1, f"<!-- tut:{region[0]} --> is never closed"))
    return doc


def replace_regions(text: str, render) -> str:
    """Return text with every generated region's body replaced by render(region)."""
    doc = parse(text)
    lines = text.split("\n")
    for r in sorted(doc.regions, key=lambda r: r.start, reverse=True):
        new = render(r)
        if new is None:
            continue
        lines[r.start + 1:r.end] = new.split("\n") if new else []
    return "\n".join(lines)


def headings(text: str) -> list[tuple[int, str]]:
    out, in_fence = [], False
    for line in text.split("\n"):
        if FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if not in_fence:
            m = re.match(r"^(#{1,6})\s+(.*)$", line)
            if m:
                out.append((len(m.group(1)), m.group(2).strip()))
    return out
