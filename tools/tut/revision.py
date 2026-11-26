"""`./tut revision start <id> --to <version>`: keep the tutorial as it is for
its current versions, then move it to a new product version (RFC 0002).

1. Copy tutorials/<id>/ as it is on the base branch (not the working tree: the
   copy must be what was verified) to tutorials/<id>/revisions/rN/.
2. Make the copy work from its new place: `frozen: true` in its tutorial.yaml,
   the generated setup step (`cd` into the revision) and header re-rendered,
   relative links that leave the tutorial directory re-pointed.
3. Point the current tutorial at the new version: versions.tested [<version>]
   and versions.default <version>.

`./tut revision keep <id> [<version>...]` does 1 and 2 without a new version:
the revision keeps those tested versions (default: the ones before a gap in
versions.tested, `./tut revision todo`) and the current tutorial drops them. For a
tutorial that skipped versions; the maintainer decides.

After this the author edits the current tutorial for the new version; the
revision and the change go into one commit. `./tut sync` never writes into
revisions/, and lint (R001-R005) keeps a revision unchanged.
"""
from __future__ import annotations

import io
import os
import re
import subprocess
import tarfile
from pathlib import Path

import yaml

from . import generate, markdown, shared
from .model import (REPO_ROOT, REVISION_RE, REVISIONS_DIR, VERSION_RE, Tutorial, load_revisions,
                    load_tutorials, version_key)


class RevisionError(Exception):
    pass


LINK_RE = re.compile(r"(\]\(|(?:src|href)=\")(?![a-z][a-z0-9+.-]*:|#|/)([^)\"\s#]+)")


def next_name(t: Tutorial) -> str:
    nums = [int(REVISION_RE.match(r.revision).group(1)) for r in load_revisions(t)]
    return f"r{max(nums, default=0) + 1}"


def _base_files(t: Tutorial, base: str) -> dict[str, bytes]:
    """{path relative to the tutorial: content} of tutorials/<id>/ on `base`,
    without its revisions/ (they stay where they are)."""
    rel = t.rel
    try:
        data = subprocess.run(["git", "archive", "--format=tar", base, "--", rel],
                              cwd=t.root, capture_output=True, check=True).stdout
    except subprocess.CalledProcessError as e:
        raise RevisionError(f"{rel} is not on {base} ({e.stderr.decode().strip()}); a revision "
                            "keeps what was verified there, so merge the tutorial first")
    out = {}
    with tarfile.open(fileobj=io.BytesIO(data)) as tar:
        for m in tar.getmembers():
            if not m.isfile():
                continue
            sub = Path(m.name).relative_to(rel).as_posix()
            if sub.split("/", 1)[0] == REVISIONS_DIR:
                continue
            out[sub] = tar.extractfile(m).read()
    if "tutorial.yaml" not in out:
        raise RevisionError(f"{rel}/tutorial.yaml is not on {base}")
    return out


def _repoint(text: str, old_dir: Path, new_dir: Path, tut_dir: Path) -> str:
    """Relative links that leave the tutorial directory, re-pointed from the
    file's new place (inside the tutorial they move along with the copy)."""
    def fix(m):
        target = m.group(2)
        resolved = (old_dir / target).resolve()
        if resolved == tut_dir or tut_dir in resolved.parents:
            return m.group(0)
        return m.group(1) + os.path.relpath(resolved, new_dir.resolve()).replace(os.sep, "/")
    return LINK_RE.sub(fix, text)


def _render_frozen(path: Path, r: Tutorial, lang: str) -> None:
    """Regenerate the regions that name the location (setup, header) for the
    revision once; everything else (tut:use text, includes) stays as copied."""
    def render(reg: markdown.Region):
        if reg.kind == "setup":
            return "\n" + generate.render_setup(r) + "\n"
        if reg.kind == "header":
            return "\n" + generate.render_header(r, lang) + "\n"
        return None
    path.write_text(markdown.replace_regions(path.read_text(), render))


def _set_versions(yaml_path: Path, default: str, tested: list[str]) -> None:
    """versions.default and versions.tested of a tutorial.yaml, keeping the
    file's comments and layout."""
    lines = yaml_path.read_text().split("\n")
    inside, seen, out, skip_items = False, set(), [], None
    for line in lines:
        if skip_items is not None:        # the old block list of `tested:` (- v0.18.0 ...)
            if re.match(rf"^{skip_items}\s*- ", line):
                continue
            skip_items = None
        if re.match(r"^versions:\s*(#.*)?$", line):
            inside = True
            out.append(line)
            continue
        if inside and line and not line.startswith((" ", "\t")):
            inside = False
        m = re.match(r"^(\s+)(default|tested):(\s*)([^#]*?)(\s*#.*)?$", line) if inside else None
        if m:
            value = default if m.group(2) == "default" else f"[{', '.join(tested)}]"
            line = f"{m.group(1)}{m.group(2)}:{m.group(3) or ' '}{value}{m.group(5) or ''}"
            seen.add(m.group(2))
            if m.group(2) == "tested" and not m.group(4).strip():
                skip_items = re.escape(m.group(1))
        out.append(line)
    lines = out
    if seen != {"default", "tested"}:
        raise RevisionError(f"{yaml_path}: cannot find versions.default and versions.tested to update")
    yaml_path.write_text("\n".join(lines))


def users_of(t: Tutorial, tutorials: list[Tutorial]) -> list[str]:
    """Tutorials that copy a shared step this tutorial defines (tut:use)."""
    names = {n for n, owners in shared.definitions(tutorials).items() if any(o == t.id for o, _ in owners)}
    out = []
    for u in tutorials:
        if u.id == t.id or not u.readme("en").exists():
            continue
        doc = markdown.parse(u.readme("en").read_text())
        if any(x.kind == "use" and x.name in names for x in shared.regions(doc)):
            out.append(u.id)
    return out


def _copy(t: Tutorial, base: str, tested: list[str] | None = None) -> Path:
    """tutorials/<id>/ on `base` -> revisions/rN/, frozen, working from its new
    place. `tested`: the versions the revision keeps (default: all of base's)."""
    files = _base_files(t, base)
    old = yaml.safe_load(files["tutorial.yaml"]) or {}
    if not (old.get("versions") or {}).get("tested"):
        raise RevisionError(f"{t.id} on {base} lists no tested versions")
    name = next_name(t)
    dst = t.path / REVISIONS_DIR / name
    for sub, data in files.items():
        p = dst / sub
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        mode = subprocess.run(["git", "ls-tree", base, "--", f"{t.rel}/{sub}"], cwd=t.root,
                              capture_output=True, text=True).stdout.split(" ", 1)[0]
        if mode == "100755":
            p.chmod(0o755)
    meta_text = files["tutorial.yaml"].decode()
    if not re.search(r"^frozen:", meta_text, re.M):
        meta_text = meta_text.rstrip("\n") + (
            f"\nfrozen: true                    # revision {name} (docs/rfc/0002-tutorial-revisions.md): never edited\n")
    (dst / "tutorial.yaml").write_text(meta_text)
    if tested is not None:
        _set_versions(dst / "tutorial.yaml", sorted(tested, key=version_key)[-1], tested)
        meta_text = (dst / "tutorial.yaml").read_text()
    r = Tutorial(id=t.id, path=dst, meta=yaml.safe_load(meta_text) or {}, revision=name)
    for p in sorted(dst.rglob("*.md")):
        orig_dir = t.path / p.parent.relative_to(dst)
        p.write_text(_repoint(p.read_text(), orig_dir, p.parent, t.path.resolve()))
    for lang in r.langs:
        if r.readme(lang).exists():
            _render_frozen(r.readme(lang), r, lang)
    return dst


def start(t: Tutorial, version: str, base: str = "origin/main") -> Path:
    if t.revision:
        raise RevisionError(f"{t.key} is a revision; start from the current tutorial {t.id}")
    if not VERSION_RE.match(version):
        raise RevisionError(f"{version!r} is not a version like v0.20.0")
    if version in t.tested_versions:
        raise RevisionError(f"{t.id} is already tested with {version}: nothing to keep apart; to "
                            f"move older versions out, use ./tut revision keep {t.id}")
    dst = _copy(t, base)
    _set_versions(t.path / "tutorial.yaml", version, [version])
    return dst


def keep(t: Tutorial, versions: list[str], base: str = "origin/main") -> Path:
    """Move `versions` of the current tutorial to a new frozen revision without
    moving to a new version: for a tutorial that skipped versions (tested
    [v0.18.0, v0.21.0] while CI runs v0.21 and v0.20). The copy is the one on
    `base`, which was verified with those versions."""
    if t.revision:
        raise RevisionError(f"{t.key} is a revision; keep from the current tutorial {t.id}")
    if not versions:
        raise RevisionError(f"{t.id} skipped no version (./tut revision todo); to move "
                            f"versions anyway, name them: ./tut revision keep {t.id} <version>...")
    unknown = [v for v in versions if v not in t.tested_versions]
    if unknown:
        raise RevisionError(f"{t.id} is not tested with {', '.join(unknown)}")
    base_tested = set(((yaml.safe_load(_base_files(t, base)["tutorial.yaml"]) or {})
                       .get("versions") or {}).get("tested") or [])
    missing = [v for v in versions if v not in base_tested]
    if missing:
        raise RevisionError(f"{', '.join(missing)} is not tested on {base}; a revision keeps what "
                            "was verified there")
    rest = [v for v in t.tested_versions if v not in versions]
    if not rest:
        raise RevisionError(f"that would leave {t.id} with no tested version; move it to a new "
                            f"version instead: ./tut revision start {t.id} --to <version>")
    dst = _copy(t, base, [v for v in t.tested_versions if v in versions])
    default = t.default_version if t.default_version in rest else sorted(rest, key=version_key)[-1]
    _set_versions(t.path / "tutorial.yaml", default, rest)
    return dst


def start_cli(tid: str, version: str, base: str, with_users: bool, root: Path = REPO_ROOT) -> int:
    import sys
    tutorials = load_tutorials(root)
    by_id = {t.id: t for t in tutorials}
    if tid not in by_id:
        sys.exit(f"unknown tutorial {tid!r}")
    todo = [tid] + (users_of(by_id[tid], tutorials) if with_users else [])
    for x in todo:
        try:
            dst = start(by_id[x], version, base)
        except RevisionError as e:
            sys.exit(f"error: {e}")
        print(f"{x}: kept as {dst.relative_to(root)}; tutorial.yaml now tested [{version}]")
    rest = [u for u in users_of(by_id[tid], tutorials) if u not in todo]
    if rest:
        print(f"\n{tid} defines shared steps that {', '.join(rest)} copy (tut:use). If you change "
              f"a definition for {version}, they change too: start them as well "
              f"(./tut revision start {tid} --to {version} --with-users, or one by one).")
    print(f"\nNext: edit the tutorial for {version}, ./tut sync, ./tut run <id>, make precommit;"
          " commit the revision and the change together.")
    return 0


def keep_cli(tid: str, versions: list[str], base: str, root: Path = REPO_ROOT) -> int:
    import sys
    from . import plan
    by_id = {t.id: t for t in load_tutorials(root)}
    if tid not in by_id:
        sys.exit(f"unknown tutorial {tid!r}")
    if not versions:
        versions = next((e["versions"] for e in plan.skipped(root) if e["tutorial"] == tid), [])
    try:
        dst = keep(by_id[tid], versions, base)
    except RevisionError as e:
        sys.exit(f"error: {e}")
    print(f"{tid}: {', '.join(versions)} kept as {dst.relative_to(root)} (frozen); "
          "removed from the current tutorial's versions.tested")
    print("\nNext: ./tut sync, make precommit; commit the revision and the tutorial.yaml change together.")
    return 0
