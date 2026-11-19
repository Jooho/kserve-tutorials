"""Load tutorials and environment profiles from the repository.

Everything the tooling knows about a tutorial comes from two places:
  tutorials/<id>/tutorial.yaml   metadata (status, versions, env, ...)
  tutorials/<id>/README*.md      the document, which is also the test
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_DIR = REPO_ROOT / "schema"
TEMPLATE_ID = "_template"
LANGS = ("en", "ko")
VERSION_RE = re.compile(r"^v\d+\.\d+\.\d+$")


def readme_name(lang: str) -> str:
    return "README.md" if lang == "en" else f"README.{lang}.md"


def version_key(v: str) -> tuple[int, ...]:
    return tuple(int(x) for x in v.lstrip("v").split("."))


@dataclass
class EnvProfile:
    ref: str            # "<name>/<version>", e.g. "kind-kserve/v1"
    path: Path
    meta: dict

    @property
    def frozen(self) -> bool:
        return bool(self.meta.get("frozen", False))

    def supports(self, kserve_version: str) -> bool:
        ks = self.meta.get("kserve", {}) or {}
        lo, hi = ks.get("min"), ks.get("max")
        if lo and version_key(kserve_version) < version_key(lo):
            return False
        if hi and version_key(kserve_version) > version_key(hi):
            return False
        return True


@dataclass
class Module:
    """A versioned library of scripts shared by tutorials: lib/<name>/v<N>/."""
    ref: str            # "<name>/<version>", e.g. "llmisvc/v1"
    path: Path
    meta: dict

    @property
    def frozen(self) -> bool:
        return bool(self.meta.get("frozen", False))

    def scripts(self) -> list[Path]:
        return sorted(p for p in self.path.iterdir() if p.is_file() and p.suffix == ".sh")


MODULE_REF_RE = re.compile(r"(?:\$\{?TUT_LIB\}?|\blib)/([a-z0-9-]+/v[0-9]+)/")


@dataclass
class Tutorial:
    id: str
    path: Path
    meta: dict
    errors: list[str] = field(default_factory=list)  # load-time problems

    @property
    def status(self) -> str:
        return self.meta.get("status", "draft")

    @property
    def env_ref(self) -> str | None:
        return self.meta.get("env")

    @property
    def env_options(self) -> dict:
        return dict(self.meta.get("env_options") or {})

    @property
    def uses(self) -> list[str]:
        return list(self.meta.get("uses", []))

    @property
    def langs(self) -> list[str]:
        return list(self.meta.get("langs", ["en"]))

    @property
    def kserve_default(self) -> str | None:
        return (self.meta.get("kserve") or {}).get("default")

    @property
    def kserve_tested(self) -> list[str]:
        return list((self.meta.get("kserve") or {}).get("tested", []))

    @property
    def namespace(self) -> str:
        return self.meta.get("namespace", self.id)

    @property
    def needs_gpu(self) -> bool:
        return bool((self.meta.get("requires") or {}).get("gpu", False))

    @property
    def ci_runnable(self) -> bool:
        """Can CI execute this tutorial end to end?"""
        return self.status != "archived" and not self.needs_gpu

    def title(self, lang: str = "en") -> str:
        t = self.meta.get("title", self.id)
        return t.get(lang) or t.get("en") if isinstance(t, dict) else t

    def summary(self, lang: str = "en") -> str:
        s = self.meta.get("summary", "")
        return (s.get(lang) or s.get("en", "")) if isinstance(s, dict) else s

    def readme(self, lang: str = "en") -> Path:
        return self.path / readme_name(lang)


def load_schema(name: str) -> dict:
    return json.loads((SCHEMA_DIR / name).read_text())


def load_tutorials(root: Path = REPO_ROOT, include_template: bool = False) -> list[Tutorial]:
    out = []
    tdir = root / "tutorials"
    if not tdir.is_dir():
        return out
    for d in sorted(p for p in tdir.iterdir() if p.is_dir()):
        if d.name == TEMPLATE_ID and not include_template:
            continue
        meta_file = d / "tutorial.yaml"
        t = Tutorial(id=d.name, path=d, meta={})
        if not meta_file.exists():
            t.errors.append("missing tutorial.yaml")
        else:
            try:
                t.meta = yaml.safe_load(meta_file.read_text()) or {}
            except yaml.YAMLError as e:
                t.errors.append(f"tutorial.yaml is not valid YAML: {e}")
        out.append(t)
    return out


def load_envs(root: Path = REPO_ROOT) -> dict[str, EnvProfile]:
    out: dict[str, EnvProfile] = {}
    edir = root / "envs"
    if not edir.is_dir():
        return out
    for prof in sorted(edir.glob("*/*/profile.yaml")):
        ref = f"{prof.parent.parent.name}/{prof.parent.name}"
        try:
            meta = yaml.safe_load(prof.read_text()) or {}
        except yaml.YAMLError:
            meta = {"_invalid": True}
        out[ref] = EnvProfile(ref=ref, path=prof.parent, meta=meta)
    return out


def load_modules(root: Path = REPO_ROOT) -> dict[str, Module]:
    out: dict[str, Module] = {}
    ldir = root / "lib"
    if not ldir.is_dir():
        return out
    for m in sorted(ldir.glob("*/*/module.yaml")):
        ref = f"{m.parent.parent.name}/{m.parent.name}"
        try:
            meta = yaml.safe_load(m.read_text()) or {}
        except yaml.YAMLError:
            meta = {"_invalid": True}
        out[ref] = Module(ref=ref, path=m.parent, meta=meta)
    return out


def env_settings(t: "Tutorial", env: "EnvProfile | None") -> list[tuple[str, str]]:
    """[(TUT_ENV_<NAME>, value)] for the setup step: the tutorial's env_options
    over the env's declared defaults, in the order the env declares them."""
    if env is None:
        return []
    out = []
    for name, spec in (env.meta.get("options") or {}).items():
        v = t.env_options.get(name, spec.get("default"))
        if isinstance(v, list):
            v = ",".join(str(x) for x in v)
        elif isinstance(v, bool):
            v = "true" if v else "false"
        out.append((f"TUT_ENV_{name.upper()}", str(v)))
    return out
