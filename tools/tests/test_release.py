"""Release rules: date-based versions, every matrix entry must pass, `stable`
only moves forward."""
from __future__ import annotations

import datetime as dt
import json
import subprocess

from tut import release


def git(root, *args):
    return subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", *args], cwd=root,
                          check=True, capture_output=True, text=True).stdout.strip()


def test_next_version_is_date_based_and_counts_within_month():
    d = dt.date(2026, 11, 18)
    assert release.next_version(d, tags=[]) == "2026.11.0"
    assert release.next_version(d, tags=["2026.10.4", "2026.11.0", "2026.11.1"]) == "2026.11.2"
    assert release.next_version(dt.date(2026, 12, 1), tags=["2026.11.7"]) == "2026.12.0"


def test_verdict_requires_a_passing_report_for_every_entry(tmp_path):
    expected = [{"tutorial": "a", "kserve_version": "v0.18.0"},
                {"tutorial": "a", "kserve_version": "v0.19.0"},
                {"tutorial": "b", "kserve_version": "v0.18.0"}]
    for name, status in (("a-v0.18.0", "passed"), ("a-v0.19.0", "failed")):
        d = tmp_path / f"report-release-{name}"
        d.mkdir()
        t, v = name.split("-", 1)
        (d / "report.json").write_text(json.dumps(
            {"tutorial": t, "kserve_version": v, "status": status, "failed_at": "x"}))
    ok, problems = release.verdict(release.load_reports(tmp_path), expected)
    assert not ok
    assert any("a @ v0.19.0: failed" in p for p in problems)
    assert any("b @ v0.18.0: no report" in p for p in problems)   # a crashed job is not a pass


def test_stable_only_fast_forwards(tmp_path):
    git(tmp_path, "init", "-q", "-b", "main")
    (tmp_path / "f").write_text("1"); git(tmp_path, "add", "."); git(tmp_path, "commit", "-qm", "1")
    first = git(tmp_path, "rev-parse", "HEAD")
    ok, msg = release.can_fast_forward(first, root=tmp_path)
    assert ok and "does not exist yet" in msg
    git(tmp_path, "update-ref", "refs/remotes/origin/stable", first)
    assert release.can_fast_forward(first, root=tmp_path)[0] is False          # nothing new
    (tmp_path / "f").write_text("2"); git(tmp_path, "commit", "-qam", "2")
    second = git(tmp_path, "rev-parse", "HEAD")
    assert release.can_fast_forward(second, root=tmp_path)[0] is True          # forward
    git(tmp_path, "checkout", "-q", "-b", "side", first)
    (tmp_path / "g").write_text("x"); git(tmp_path, "add", "."); git(tmp_path, "commit", "-qm", "side")
    git(tmp_path, "update-ref", "refs/remotes/origin/stable", second)
    side = git(tmp_path, "rev-parse", "HEAD")
    ok, msg = release.can_fast_forward(side, root=tmp_path)
    assert not ok and "refusing to rewrite" in msg                             # never backwards


def test_notes_list_results_and_changes(tmp_path):
    git(tmp_path, "init", "-q", "-b", "main")
    (tmp_path / "tutorials/a").mkdir(parents=True)
    (tmp_path / "tutorials/a/README.md").write_text("x")
    git(tmp_path, "add", "."); git(tmp_path, "commit", "-qm", "first")
    git(tmp_path, "tag", "2026.11.0")
    (tmp_path / "tutorials/a/README.md").write_text("y")
    git(tmp_path, "commit", "-qam", "change a")
    sha = git(tmp_path, "rev-parse", "HEAD")
    reports = [{"tutorial": "a", "kserve_version": "v0.18.0", "status": "passed", "duration_seconds": 600}]
    text = release.notes("2026.11.1", sha, reports, repo="o/r", root=tmp_path)
    assert "git clone -b 2026.11.1 https://github.com/o/r.git" in text
    assert "| a | v0.18.0 | ✅ | 10 min |" in text
    assert "Changes since 2026.11.0" in text and "`tutorials/a`" in text and "change a" in text
