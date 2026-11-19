"""`./tut new <id>`: start a tutorial from tutorials/_template/."""
from __future__ import annotations

import re
import shutil
from pathlib import Path

from .model import REPO_ROOT, TEMPLATE_ID

ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")      # same as schema/tutorial.schema.json


class ScaffoldError(Exception):
    pass


def new_tutorial(tid: str, title: str | None = None, owner: str | None = None,
                 root: Path = REPO_ROOT) -> Path:
    """Copy the template to tutorials/<tid>/ and fill in id, namespace and,
    when given, the English title and the owner. Edits text, not a YAML
    round-trip, so the template's comments stay as guidance."""
    if not ID_RE.match(tid):
        raise ScaffoldError(f"invalid id {tid!r}: lowercase letters, digits and '-', "
                            "starting with a letter or digit (e.g. llmisvc-autoscaling)")
    src, dst = root / "tutorials" / TEMPLATE_ID, root / "tutorials" / tid
    if dst.exists():
        raise ScaffoldError(f"tutorials/{tid}/ already exists")
    if not src.is_dir():
        raise ScaffoldError(f"template not found: tutorials/{TEMPLATE_ID}/")
    # English only: a copied README.ko.md would be the template's text, not a
    # translation of this tutorial. Translate once the English is written.
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("README.*.md"))

    meta = dst / "tutorial.yaml"
    text = meta.read_text()
    text = re.sub(r"^langs:[ \t]*\[[^\]]*\]", "langs: [en]", text, count=1, flags=re.M)
    text = re.sub(r"^# Start a tutorial with .*\n", "", text, count=1, flags=re.M)
    text = re.sub(r"^id:[ \t]*\S+", f"id: {tid}", text, count=1, flags=re.M)
    text = re.sub(r"^namespace:[ \t]*\S+", f"namespace: {tid}", text, count=1, flags=re.M)
    if title:
        text = re.sub(r'^(title:\s*\n[ \t]+en:[ \t]*).*$', lambda m: m.group(1) + _quote(title),
                      text, count=1, flags=re.M)
        readme = dst / "README.md"
        readme.write_text(re.sub(r"^# .*$", f"# {title}", readme.read_text(), count=1, flags=re.M))
    if owner:
        text = re.sub(r"^owners:.*$", f"owners: [{owner.lstrip('@')}]", text, count=1, flags=re.M)
    meta.write_text(text)
    return dst


def _quote(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'
