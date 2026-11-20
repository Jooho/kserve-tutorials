"""`./tut site`: assemble the MkDocs source tree in build/site-src.

The repository layout is mirrored (tutorials/<id>/, envs/<name>/<ver>/) so the
relative links that work on GitHub also work on the site. README.md becomes
index.md and README.ko.md becomes index.ko.md (mkdocs-static-i18n suffix mode).
"""
from __future__ import annotations

import re
import shutil
from pathlib import Path

from . import generate, markdown, project
from .model import REPO_ROOT, load_envs, load_tutorials, version_key

LANG_FILES = {"README.md": "index.md", "README.ko.md": "index.ko.md"}



ROLE_TITLES = {"verify": "✔ verify", "cleanup": "🧹 cleanup", "skip": "optional"}


def _site_fence_info(line: str) -> str:
    """`bash verify retry=3` is fine on GitHub but Python-Markdown only accepts
    a bare language. Keep the language and show the role as the block title."""
    m = markdown.FENCE_RE.match(line)
    if not m or not m.group("info").strip():
        return line
    lang, role, _attrs, _ = markdown.parse_info(m.group("info"))
    if not role:
        return line
    title = ROLE_TITLES.get(role)
    info = f'{lang} title="{title}"' if title else lang
    return f"{m.group('indent')}{m.group('fence')}{info}"


def _copy_tree(src: Path, dst: Path):
    for p in src.rglob("*"):
        if p.is_dir():
            continue
        rel = p.relative_to(src)
        target = dst / LANG_FILES.get(str(rel), str(rel))
        target.parent.mkdir(parents=True, exist_ok=True)
        if p.suffix == ".md":
            text = "\n".join(_site_fence_info(l) for l in p.read_text().split("\n"))
            # The README's "🌐 English / 한국어" line links README*.md for GitHub; the
            # site renames them to index pages and has its own language switcher.
            text = re.sub(r"^>[ \t]*\n> 🌐 .*\n", "", text, flags=re.M)
            target.write_text(text)
        else:
            shutil.copy2(p, target)


def build_source(out: Path, root: Path = REPO_ROOT) -> Path:
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    tutorials = [t for t in load_tutorials(root) if not t.errors]
    for t in tutorials:
        _copy_tree(t.path, out / "tutorials" / t.id)
    for env in load_envs(root).values():
        _copy_tree(env.path, out / "envs" / env.ref)
    proj = project.load(root)
    for lang, name in (("en", "index.md"), ("ko", "index.ko.md")):
        intro = f"# {proj.text('title', lang)}\n\n{proj.text('intro', lang)}\n".replace("\n\n\n", "\n")
        body = intro + "\n" + generate.render_catalog(tutorials, lang, root) + "\n"
        (out / name).write_text(body)
    # Per-version pages: "what can I run on <product> vX?"
    versions = sorted({v for t in tutorials for v in t.tested_versions}, key=version_key, reverse=True)
    lines = [f"# By {proj.name} version", ""]
    for v in versions:
        lines += [f"## {v}", ""]
        for t in tutorials:
            if v in t.tested_versions and t.status != "archived":
                lines.append(f"- [{t.title()}](tutorials/{t.id}/index.md) — {t.summary()}")
        lines.append("")
    (out / "versions.md").write_text("\n".join(lines))
    _link_dir_indexes(out)
    return out


_DIR_LINK = re.compile(r"(\]\()(?![a-z][a-z0-9+.-]*:|#|/)([^)\s#]*/)(#[^)\s]*)?(\))")


def _link_dir_indexes(out: Path) -> None:
    """READMEs link folders (`../other/`), which GitHub opens as their README.
    MkDocs cannot check a folder link, so point it at the folder's index.md
    page, so `mkdocs build --strict` checks it: a link to a folder that no
    longer exists fails the build. Only a folder that exists without an index
    page (e.g. manifests/) keeps its plain link."""
    for md in out.rglob("*.md"):
        def fix(m):
            d = md.parent / m.group(2)
            if d.is_dir() and not (d / "index.md").is_file():
                return m.group(0)
            return f"{m.group(1)}{m.group(2)}index.md{m.group(3) or ''}{m.group(4)}"
        text = md.read_text()
        new = _DIR_LINK.sub(fix, text)
        if new != text:
            md.write_text(new)
