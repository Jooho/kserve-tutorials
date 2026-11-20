"""`./tut new`: a new tutorial from the real template passes lint as a draft."""
import shutil

import pytest
import yaml

from tut import generate, lint, scaffold
from tut.model import REPO_ROOT


@pytest.fixture
def repo(tmp_path):
    for d in ("envs", "lib", "catalog", "schema"):
        shutil.copytree(REPO_ROOT / d, tmp_path / d)
    shutil.copy(REPO_ROOT / "project.yaml", tmp_path / "project.yaml")
    shutil.copytree(REPO_ROOT / "tutorials" / "_template", tmp_path / "tutorials" / "_template")
    (tmp_path / ".github").mkdir()
    return tmp_path


def test_new_tutorial_from_template_lints_clean(repo):
    d = scaffold.new_tutorial("my-new-one", title='Say "hi"', owner="@someone", root=repo)
    meta = yaml.safe_load((d / "tutorial.yaml").read_text())
    assert (meta["id"], meta["namespace"], meta["langs"]) == ("my-new-one", "my-new-one", ["en"])
    assert meta["title"]["en"] == 'Say "hi"' and meta["owners"] == ["someone"]
    assert meta["status"] == "draft"
    assert not (d / "README.ko.md").exists()                  # no fake translation
    assert (d / "README.md").read_text().startswith('# Say "hi"\n')
    assert "# Start a tutorial with" not in (d / "tutorial.yaml").read_text()
    generate.sync(repo)
    errors = [f for f in lint.Linter(repo).run() if f.severity == "error"
              and "my-new-one" in str(f.path)]
    assert errors == []


def test_new_tutorial_rejects_bad_or_existing_ids(repo):
    for bad in ("My_Tutorial", "-x", "_template", ""):
        with pytest.raises(scaffold.ScaffoldError):
            scaffold.new_tutorial(bad, root=repo)
    scaffold.new_tutorial("dup", root=repo)
    with pytest.raises(scaffold.ScaffoldError, match="already exists"):
        scaffold.new_tutorial("dup", root=repo)
