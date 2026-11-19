"""Collections, tags and code owners."""
from __future__ import annotations

import yaml

from tut import catalog, generate, lint
from tut.model import load_tutorials
from test_rules import make_env, make_tut  # noqa: E402  (shared fixtures)

TAGS = {"groups": {"feature": "f", "level": "l"},
        "tags": {"llmisvc": {"group": "feature", "description": "d"},
                 "beginner": {"group": "level", "description": "d"}}}


def setup_catalog(root, members, tags=TAGS, owners=("alice",)):
    d = root / "catalog" / "collections"
    d.mkdir(parents=True, exist_ok=True)
    (root / "catalog" / "tags.yaml").write_text(yaml.safe_dump(tags))
    (root / "catalog" / "maintainers.yaml").write_text(yaml.safe_dump({"maintainers": ["boss"]}))
    (d / "path.yaml").write_text(yaml.safe_dump(
        {"id": "path", "title": {"en": "Path"}, "owners": list(owners), "members": members}))


def errors(root):
    generate.sync(root)
    return {(f.code, f.severity) for f in lint.Linter(root).run()}


def test_unknown_tag_is_rejected_with_a_suggestion(tmp_path):
    make_env(tmp_path)
    make_tut(tmp_path, "a", tags=["llmisvcs", "beginner"])
    setup_catalog(tmp_path, ["a"])
    generate.sync(tmp_path)
    found = [f for f in lint.Linter(tmp_path).run() if f.code == "G001"]
    assert len(found) == 1 and "did you mean 'llmisvc'" in found[0].message


def test_collection_members_must_exist_once(tmp_path):
    make_env(tmp_path)
    make_tut(tmp_path, "a")
    setup_catalog(tmp_path, ["a", "a", "ghost"])
    e = errors(tmp_path)
    assert ("C002", "error") in e and ("C003", "error") in e


def test_archived_member_without_replacement_warns(tmp_path):
    make_env(tmp_path)
    make_tut(tmp_path, "old", status="archived",
             deprecation={"reason": "gone", "last_supported_kserve": "v0.18.0"})
    setup_catalog(tmp_path, ["old"])
    assert ("C004", "warning") in errors(tmp_path)


def test_resolve_by_version_and_replacement(tmp_path):
    make_env(tmp_path)
    make_tut(tmp_path, "a", kserve={"default": "v0.18.0", "tested": ["v0.18.0", "v0.19.0"]})
    make_tut(tmp_path, "b", kserve={"default": "v0.18.0", "tested": ["v0.18.0"]})
    make_tut(tmp_path, "old", status="archived", deprecation={
        "reason": "WVA removed", "last_supported_kserve": "v0.18.0", "replacement": "new"})
    make_tut(tmp_path, "new", kserve={"default": "v0.19.0", "tested": ["v0.19.0"]})
    setup_catalog(tmp_path, ["a", "b", "old", "ghost"])
    by_id = {t.id: t for t in load_tutorials(tmp_path)}
    col = catalog.load_collections(tmp_path)[0]
    states = lambda v: [(r["member"], r["state"], r["shown"]) for r in catalog.resolve(col, by_id, v)]
    assert states("v0.19.0") == [("a", "ok", "a"), ("b", "unavailable", "b"),
                                 ("old", "replaced", "new"), ("ghost", "missing", None)]
    # on v0.18.0 the replacement is not tested, so the archived member stays (marked archived)
    assert states("v0.18.0")[2] == ("old", "archived", "old")
    # "new" is shown by the collection as the replacement of "old": not uncollected
    assert catalog.uncollected(list(by_id.values()), [col]) == []


def test_codeowners_generated_from_owners_and_checked(tmp_path):
    make_env(tmp_path)
    make_tut(tmp_path, "a", owners=["carol"])
    setup_catalog(tmp_path, ["a"])
    generate.sync(tmp_path)
    text = (tmp_path / ".github" / "CODEOWNERS").read_text()
    assert "*  @boss" in text
    assert "/catalog/collections/path.yaml  @alice" in text
    assert "/tutorials/a/  @carol" in text
    assert text.index("*  @boss") < text.index("/tutorials/a/")   # specific paths last
    (tmp_path / "tutorials" / "a" / "tutorial.yaml").write_text(
        (tmp_path / "tutorials" / "a" / "tutorial.yaml").read_text().replace("carol", "dave"))
    assert ("O001", "error") in {(f.code, f.severity) for f in lint.Linter(tmp_path).run()}
