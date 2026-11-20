"""Usage: report.py <reports-dir> [--dry-run]

Turn run reports into a summary table and one issue per failing tutorial/version.

Issues are deduplicated by title, so a tutorial that keeps failing gets
comments on one issue instead of a new issue every week.
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

DRY_RUN = "--dry-run" in sys.argv
args = [a for a in sys.argv[1:] if a != "--dry-run"]
ROOT = Path(__file__).resolve().parents[2]
# The product's name from project.yaml (this job has no toolkit .venv, so no PyYAML).
_m = re.search(r"^name:\s*([^#\n]+?)\s*(?:#.*)?$", (ROOT / "project.yaml").read_text(), re.M)
NAME = _m.group(1).strip("\"'") if _m else "the product"

reports = []
for f in sorted(Path(args[0]).glob("report-*/report.json")):
    r = json.loads(f.read_text())
    r["kind"] = f.parent.name.split("-")[1]          # scheduled | canary
    reports.append(r)

lines = [f"| Run | Tutorial | {NAME} | Result | Failed at |", "|---|---|---|---|---|"]
for r in reports:
    icon = "✅" if r["status"] == "passed" else "❌"
    lines.append(f"| {r['kind']} | {r['tutorial']} | {r['version']} | {icon} | {r['failed_at'] or ''} |")
summary = os.environ.get("GITHUB_STEP_SUMMARY")
if summary:
    Path(summary).write_text("\n".join(lines) + "\n")
print("\n".join(lines))


def gh(*args):
    if DRY_RUN:
        print("would run: gh", " ".join(args)[:160])
        return "[]"
    return subprocess.run(["gh", *args], check=True, capture_output=True, text=True).stdout


for name, color in (("tutorial-ci", "d73a4a"), ("canary", "fbca04")):
    gh("label", "create", name, "--color", color, "--force")

for r in reports:
    if r["status"] == "passed":
        continue
    title = f"[{r['kind']}] {r['tutorial']} fails on {NAME} {r['version']}"
    body = (f"**Tutorial:** `tutorials/{r['tutorial']}`\n"
            f"**{NAME}:** {r['version']}\n"
            f"**Environment:** `{r['env']}`\n"
            f"**Failed at:** `{r['failed_at']}`\n"
            f"**Run:** {os.environ.get('RUN_URL', '')}\n\n"
            + ("A canary failure means the tutorial has not been verified on this version yet: "
               "update it, or record that it does not support this version.\n"
               if r["kind"] == "canary" else
               "This version is listed in `versions.tested`, so readers are affected.\n"))
    existing = json.loads(gh("issue", "list", "--state", "open", "--label", "tutorial-ci",
                             "--search", f'in:title "{title}"', "--json", "number,title"))
    match = next((i for i in existing if i["title"] == title), None)
    if match:
        gh("issue", "comment", str(match["number"]), "--body", body)
    else:
        labels = ["tutorial-ci"] + (["canary"] if r["kind"] == "canary" else [])
        gh("issue", "create", "--title", title, "--body", body, *sum((["--label", l] for l in labels), []))
