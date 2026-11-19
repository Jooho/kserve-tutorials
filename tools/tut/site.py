"""`./tut site`: assemble the MkDocs source tree in build/site-src.

The repository layout is mirrored (tutorials/<id>/, envs/<name>/<ver>/) so the
relative links that work on GitHub also work on the site. README.md becomes
index.md and README.ko.md becomes index.ko.md (mkdocs-static-i18n suffix mode).
"""
from __future__ import annotations

import shutil
from pathlib import Path

from . import generate, markdown
from .model import REPO_ROOT, load_envs, load_tutorials, version_key

LANG_FILES = {"README.md": "index.md", "README.ko.md": "index.ko.md"}

INTRO = {
    "en": ("# KServe Tutorials\n\nHands-on tutorials for [KServe](https://kserve.github.io/website/). "
           "Every tutorial is executed in CI against the KServe versions listed for it.\n"),
    "ko": ("# KServe 튜토리얼\n\n[KServe](https://kserve.github.io/website/) 실습 튜토리얼 모음입니다. "
           "모든 튜토리얼은 표시된 KServe 버전으로 CI에서 실제 실행되어 검증됩니다.\n"),
}


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
            target.write_text("\n".join(_site_fence_info(l) for l in p.read_text().split("\n")))
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
    for lang, name in (("en", "index.md"), ("ko", "index.ko.md")):
        body = INTRO[lang] + "\n" + generate.render_catalog(tutorials, lang, root) + "\n"
        (out / name).write_text(body)
    # Per-version pages: "what can I run on KServe vX?"
    versions = sorted({v for t in tutorials for v in t.kserve_tested}, key=version_key, reverse=True)
    lines = ["# By KServe version", ""]
    for v in versions:
        lines += [f"## {v}", ""]
        for t in tutorials:
            if v in t.kserve_tested and t.status != "archived":
                lines.append(f"- [{t.title()}](tutorials/{t.id}/index.md) — {t.summary()}")
        lines.append("")
    (out / "versions.md").write_text("\n".join(lines))
    return out
