"""Load tutorials and environment profiles from the repository.

Everything the tooling knows about a tutorial comes from two places:
  tutorials/<id>/tutorial.yaml   metadata (status, versions, env, ...)
  tutorials/<id>/README*.md      the document, which is also the test

Older versions of a tutorial live in tutorials/<id>/revisions/rN/ (RFC 0002): a
frozen copy with its own tutorial.yaml. `resolve(t, version)` picks the current
tutorial or the revision tested with that version.
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
# AI-written explainer of a tutorial: read by people, never executed (tut.explain)
EXPLAINER_DIR = "explainer"
VERSION_RE = re.compile(r"^v\d+\.\d+\.\d+$")
REVISIONS_DIR = "revisions"
REVISION_RE = re.compile(r"^r([1-9][0-9]*)$")


def readme_name(lang: str) -> str:
    return "README.md" if lang == "en" else f"README.{lang}.md"


def version_key(v: str) -> tuple[int, ...]:
    return tuple(int(x) for x in v.lstrip("v").split("."))


def minor(v: str) -> tuple[int, int]:
    """(major, minor) of vX.Y.Z: a reader on v0.19.2 reads what was tested as v0.19.x."""
    k = version_key(v)
    return (k[0], k[1] if len(k) > 1 else 0)


@dataclass
class EnvProfile:
    ref: str            # "<name>/<version>", e.g. "kind-kserve/v1"
    path: Path
    meta: dict

    @property
    def frozen(self) -> bool:
        return bool(self.meta.get("frozen", False))

    def supports(self, version: str) -> bool:
        ks = self.meta.get("versions", {}) or {}
        lo, hi = ks.get("min"), ks.get("max")
        if lo and version_key(version) < version_key(lo):
            return False
        if hi and version_key(version) > version_key(hi):
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
    revision: str | None = None   # "r1", ... for tutorials/<id>/revisions/rN; None = current

    @property
    def key(self) -> str:
        """Unique name of this variant: "<id>" or "<id>@r1"."""
        return f"{self.id}@{self.revision}" if self.revision else self.id

    @property
    def root(self) -> Path:
        """The repository root (a revision lives two directories deeper)."""
        return self.path.parents[3] if self.revision else self.path.parents[1]

    @property
    def rel(self) -> str:
        """Directory relative to the repository root, e.g. tutorials/a/revisions/r1."""
        return self.path.relative_to(self.root).as_posix()

    @property
    def frozen(self) -> bool:
        return bool(self.meta.get("frozen", False))

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
    def default_version(self) -> str | None:
        """Version of the project's product (project.yaml) readers and PR CI use."""
        return (self.meta.get("versions") or {}).get("default")

    @property
    def tested_versions(self) -> list[str]:
        return list((self.meta.get("versions") or {}).get("tested", []))

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

    def explainer(self, lang: str = "en") -> Path:
        return self.path / EXPLAINER_DIR / ("index.md" if lang == "en" else f"index.{lang}.md")


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


def load_revisions(t: Tutorial) -> list[Tutorial]:
    """tutorials/<id>/revisions/rN/ of a current tutorial, r1 first."""
    if t.revision:
        return []
    d = t.path / REVISIONS_DIR
    if not d.is_dir():
        return []
    out = []
    for p in sorted((p for p in d.iterdir() if p.is_dir() and REVISION_RE.match(p.name)),
                    key=lambda p: int(REVISION_RE.match(p.name).group(1))):
        r = Tutorial(id=t.id, path=p, meta={}, revision=p.name)
        f = p / "tutorial.yaml"
        if not f.exists():
            r.errors.append("missing tutorial.yaml")
        else:
            try:
                r.meta = yaml.safe_load(f.read_text()) or {}
            except yaml.YAMLError as e:
                r.errors.append(f"tutorial.yaml is not valid YAML: {e}")
        out.append(r)
    return out


def variants(t: Tutorial) -> list[Tutorial]:
    """The current tutorial and its revisions."""
    return [t, *load_revisions(t)]


def resolve(t: Tutorial, version: str | None) -> Tutorial | None:
    """The variant a reader on `version` uses (RFC 0002 section 6): the current
    tutorial if it was tested with that version, else the revision that was;
    an exact tag first, then the same minor. None: not available."""
    if not version:
        return t
    vs = [v for v in variants(t) if not v.errors]
    for v in vs:
        if version in v.tested_versions:
            return v
    if not VERSION_RE.match(version):
        return None
    for v in vs:
        if any(minor(x) == minor(version) for x in v.tested_versions if VERSION_RE.match(x)):
            return v
    return None


def pinned_version(root: Path = REPO_ROOT) -> str | None:
    """`version` in project.yaml: the newest product version the tutorials
    move to. Always pinned by the maintainer, never read from the network."""
    from . import project
    try:
        return project.load(root).version
    except project.ProjectError:
        return None


def pinned_minor(tutorials: list[Tutorial], root: Path | None = None) -> tuple[int, int] | None:
    """N (RFC 0002): the minor of the pinned version."""
    root = root or (tutorials[0].root if tutorials else REPO_ROOT)
    v = pinned_version(root)
    return minor(v) if v and VERSION_RE.match(v) else None


def ci_minors(t: Tutorial, n: tuple[int, int] | None) -> set[tuple[int, int]]:
    """The minors CI runs for tutorial `t` (its current version and revisions
    together): N if one of them tests N, and N-1 = the newest tested minor
    below N. A tutorial without N runs only that N-1 (it has not moved yet)."""
    ms = sorted({minor(v) for x in variants(t) if not x.errors for v in x.tested_versions
                 if VERSION_RE.match(str(v))})
    if not ms:
        return set()
    if n is None:                          # no project.yaml (lint P001 reports it)
        n = ms[-1]
    below = [m for m in ms if m < n]
    if n in ms:
        return {n, below[-1]} if below else {n}
    return {below[-1]} if below else set()


def runs_in_ci(version: str, minors: set[tuple[int, int]]) -> bool:
    return VERSION_RE.match(version) is not None and minor(version) in minors


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


# CLI tools an environment pins in envs/<env>/tools.env (KEY=version  # comment).
TOOL_KEYS = {"KIND": "kind", "KUBECTL": "kubectl", "HELM": "helm",
             "CLOUD_PROVIDER_KIND": "cloud-provider-kind"}


def env_tools(env_ref: str, root: Path = REPO_ROOT) -> dict[str, str]:
    """{tool: version} from envs/<env>/tools.env, in file order; empty entries skipped.
    The one reader of that file (doctor, the generated setup step, the UI)."""
    out: dict[str, str] = {}
    f = root / "envs" / env_ref / "tools.env"
    if not f.exists():
        return out
    for line in f.read_text().splitlines():
        line = line.split("#", 1)[0]
        if "=" not in line:
            continue
        k, v = (x.strip() for x in line.split("=", 1))
        if k in TOOL_KEYS and v:
            out[TOOL_KEYS[k]] = v.split()[0]
    return out
