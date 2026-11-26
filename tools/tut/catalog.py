"""The catalog: tags, collections and code owners — one implementation used by
lint, the local UI and the site.

  catalog/tags.yaml               every tag a tutorial may use
  catalog/groups.yaml             what kind of tutorial it is (one per tutorial, for browsing)
  catalog/collections/<id>.yaml   ordered reading paths over independent tutorials
  catalog/maintainers.yaml        default code owners

A collection never changes its tutorials. Which member a reader sees for a
KServe version is computed here (`resolve`): a member that is not tested on that
version is "unavailable"; an archived member, or one unavailable on that
version, is replaced by its `deprecation.replacement` when that one fits.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from .model import REPO_ROOT, Tutorial, load_envs, load_modules, load_tutorials, resolve as resolve_version

CATALOG = "catalog"


@dataclass
class Collection:
    id: str
    path: Path
    meta: dict

    @property
    def members(self) -> list[str]:
        return list(self.meta.get("members") or [])

    @property
    def vars(self) -> dict[str, str]:
        """Shared shell variables for the learning path (UI only)."""
        return {str(k): str(v) for k, v in (self.meta.get("vars") or {}).items()}

    @property
    def owners(self) -> list[str]:
        return list(self.meta.get("owners") or [])

    def text(self, key: str, lang: str = "en") -> str:
        v = self.meta.get(key, "")
        return (v.get(lang) or v.get("en", "")) if isinstance(v, dict) else v


def _yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return yaml.safe_load(path.read_text()) or {}
    except yaml.YAMLError:
        return {"_invalid": True}


def load_tags(root: Path = REPO_ROOT) -> dict:
    return _yaml(root / CATALOG / "tags.yaml")


def load_groups(root: Path = REPO_ROOT) -> dict:
    """{id: {title, description}} in file order (catalog/groups.yaml)."""
    return dict(_yaml(root / CATALOG / "groups.yaml").get("groups") or {})


def load_maintainers(root: Path = REPO_ROOT) -> list[str]:
    return list(_yaml(root / CATALOG / "maintainers.yaml").get("maintainers") or [])


def load_collections(root: Path = REPO_ROOT) -> list[Collection]:
    d = root / CATALOG / "collections"
    if not d.is_dir():
        return []
    return [Collection(p.stem, p, _yaml(p)) for p in sorted(d.glob("*.yaml"))]


def _available(t: Tutorial, version: str | None) -> bool:
    """Not archived, and the tutorial or one of its revisions was tested with
    `version` (RFC 0002 section 6)."""
    return t.status != "archived" and (version is None or resolve_version(t, version) is not None)


def _replacement(t: Tutorial, by_id: dict[str, Tutorial], version: str | None) -> Tutorial | None:
    """Follow deprecation.replacement until a tutorial available on `version`."""
    seen, cur = {t.id}, t
    for _ in range(5):
        nxt = by_id.get(((cur.meta.get("deprecation") or {}).get("replacement")) or "")
        if nxt is None or nxt.id in seen:
            return None
        if _available(nxt, version):
            return nxt
        seen.add(nxt.id)
        cur = nxt
    return None


def resolve(col: Collection, by_id: dict[str, Tutorial], version: str | None = None) -> list[dict]:
    """What a reader sees for each member, in order.

    state: ok | unavailable (not tested on `version`) | archived (no replacement)
           | replaced (show `shown` instead of `member`) | missing (no such tutorial)
    """
    out = []
    for n, mid in enumerate(col.members, 1):
        t = by_id.get(mid)
        if t is None:
            out.append({"n": n, "member": mid, "shown": None, "state": "missing"})
            continue
        if _available(t, version):
            v = resolve_version(t, version)
            out.append({"n": n, "member": mid, "shown": mid, "state": "ok",
                        "revision": (v.revision if v else None) or None})
            continue
        r = _replacement(t, by_id, version)
        if r:
            out.append({"n": n, "member": mid, "shown": r.id, "state": "replaced"})
        else:
            out.append({"n": n, "member": mid, "shown": mid,
                        "state": "archived" if t.status == "archived" else "unavailable"})
    return out


def uncollected(tutorials: list[Tutorial], collections: list[Collection]) -> list[Tutorial]:
    """Tutorials no collection shows — neither as a member nor as the
    replacement of an archived/deprecated member."""
    used = {m for c in collections for m in c.members}
    by_id = {t.id: t for t in tutorials}
    for m in list(used):
        cur, hops = by_id.get(m), 0
        while cur is not None and hops < 5:
            nxt = (cur.meta.get("deprecation") or {}).get("replacement")
            if not nxt or nxt in used:
                break
            used.add(nxt)
            cur, hops = by_id.get(nxt), hops + 1
    return [t for t in tutorials if t.id not in used]


# ------------------------------------------------------------------ owners
CODEOWNERS_PATH = Path(".github") / "CODEOWNERS"


def _handles(owners: list[str]) -> str:
    return " ".join("@" + o.lstrip("@") for o in owners)


def codeowners(root: Path = REPO_ROOT) -> str:
    """Generated .github/CODEOWNERS. Later lines win, so specific paths come last."""
    lines = ["# Generated by `./tut sync` from catalog/maintainers.yaml and the `owners`",
             "# fields of tutorials, collections, envs and libs. Do not edit by hand.", ""]
    maint = load_maintainers(root)
    if maint:
        lines += [f"*  {_handles(maint)}", ""]
    for env in load_envs(root).values():
        if env.meta.get("owners"):
            lines.append(f"/envs/{env.ref}/  {_handles(env.meta['owners'])}")
    for mod in load_modules(root).values():
        if mod.meta.get("owners"):
            lines.append(f"/lib/{mod.ref}/  {_handles(mod.meta['owners'])}")
    for c in load_collections(root):
        if c.owners:
            lines.append(f"/{CATALOG}/collections/{c.path.name}  {_handles(c.owners)}")
    for t in load_tutorials(root):
        if t.meta.get("owners"):
            lines.append(f"/tutorials/{t.id}/  {_handles(t.meta['owners'])}")
    return "\n".join(lines).rstrip() + "\n"
