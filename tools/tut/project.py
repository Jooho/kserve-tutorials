"""The project a repository's tutorials are about: project.yaml at the root.

The engine never names the product itself. Labels ("Tested with KServe"), the
shell variable that carries the version (KSERVE_VERSION), the upstream repo of
the weekly canary and the terms translations keep in English come from here.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import yaml

FILE = "project.yaml"

# Kubernetes and tooling words every project keeps in English; a project adds
# its own product terms with `glossary:` in project.yaml.
COMMON_GLOSSARY = [
    "HTTPRoute", "Gateway", "Envoy", "Deployment", "Service", "ServiceAccount", "Secret",
    "ConfigMap", "Pod", "Kind", "kubectl", "Hugging Face", "OwnerReference",
]


class ProjectError(Exception):
    pass


@dataclass(frozen=True)
class Project:
    id: str
    name: str
    title: dict
    version_var: str
    intro: dict = field(default_factory=dict)
    upstream: str | None = None
    latest: str | None = None
    example: str | None = None
    glossary: tuple[str, ...] = ()

    def text(self, key: str, lang: str = "en") -> str:
        v = getattr(self, key) or {}
        return v.get(lang) or v.get("en", "")

    def keep_english(self) -> list[str]:
        out = list(self.glossary)
        out += [w for w in COMMON_GLOSSARY if w not in out]
        return out

    def as_json(self) -> dict:
        return {"id": self.id, "name": self.name, "title": dict(self.title),
                "version_var": self.version_var, "upstream": self.upstream,
                "latest": self.latest}


def path(root: Path) -> Path:
    return Path(root) / FILE


def load(root: Path) -> Project:
    """project.yaml of `root`. Raises ProjectError when missing or invalid."""
    p = path(root)
    try:
        mtime = p.stat().st_mtime_ns
    except FileNotFoundError:
        raise ProjectError(f"{FILE} not found in {root}: every tutorial repository has one "
                           "(name, title, version_var); see docs/authoring.md") from None
    return _load(p, mtime)


@lru_cache(maxsize=16)
def _load(p: Path, _mtime: int) -> Project:
    try:
        meta = yaml.safe_load(p.read_text()) or {}
    except yaml.YAMLError as e:
        raise ProjectError(f"{FILE} is not valid YAML: {e}") from None
    for e in problems(meta):
        raise ProjectError(f"{FILE}: {e}")
    return Project(id=meta["id"], name=meta["name"], title=dict(meta["title"]),
                   version_var=meta["version_var"], intro=dict(meta.get("intro") or {}),
                   upstream=meta.get("upstream"), latest=meta.get("latest") or None, example=meta.get("example"),
                   glossary=tuple(meta.get("glossary") or ()))


def problems(meta: dict) -> list[str]:
    import jsonschema

    from .model import load_schema
    v = jsonschema.Draft202012Validator(load_schema("project.schema.json"))
    return [f"{'/'.join(map(str, e.path)) or '(root)'}: {e.message}"
            for e in sorted(v.iter_errors(meta), key=lambda e: list(e.path))]
