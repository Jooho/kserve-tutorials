"""Shared test setup.

Tests create throwaway git repositories. They must not depend on the
contributor's own git settings (commit signing, hooks, default branch,
templates, ...), which made tests fail locally but pass in CI.
"""
import pytest


@pytest.fixture(autouse=True)
def isolated_git(tmp_path_factory, monkeypatch):
    cfg = tmp_path_factory.mktemp("gitconfig") / "config"
    cfg.write_text("[user]\n\tname = tut-tests\n\temail = tut-tests@example.invalid\n"
                   "[init]\n\tdefaultBranch = main\n"
                   "[commit]\n\tgpgsign = false\n[tag]\n\tgpgsign = false\n")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(cfg))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    for var in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_AUTHOR_NAME",
                "GIT_AUTHOR_EMAIL", "GIT_COMMITTER_NAME", "GIT_COMMITTER_EMAIL"):
        monkeypatch.delenv(var, raising=False)
