"""update_readme.py <tutorial id> [<base ref>]: Korean README from the changed English README,
keeping the reviewed translation of the previous version where the English did
not change. Always the configured translation CLI (must be codex)."""
import subprocess
import os, sys
from pathlib import Path
REPO = Path(__file__).resolve().parents[3]
for _line in (REPO / ".tut.env").read_text().splitlines() if (REPO / ".tut.env").exists() else []:
    if "=" in _line and not _line.lstrip().startswith("#"):          # personal settings, as ./tut reads them
        _k, _v = _line.split("=", 1); os.environ.setdefault(_k.strip(), _v.strip().strip('"'))
sys.path.insert(0, str(REPO / "tools"))
from tut import generate, lint, project, translate
from tut.model import REPO_ROOT, load_tutorials

tid = sys.argv[1]
base_ref = sys.argv[2] if len(sys.argv) > 2 else "origin/main"
t = next(x for x in load_tutorials(REPO_ROOT) if x.id == tid)
tr = translate.configured()
assert tr, "set TUT_AI_TRANSLATE (or TUT_AI): ./tut config TUT_AI_TRANSLATE=codex"
git = lambda p: subprocess.run(["git", "show", f"{base_ref}:{p}"], capture_output=True, text=True, check=True).stdout
old_en, old_ko = git(f"{t.rel}/README.md"), git(f"{t.rel}/README.ko.md")
src = t.readme("en").read_text()
base = translate.build_prompt(src, "ko", project.load(REPO_ROOT))
head, source_part = base.split("=== README.md (English source) ===")
prompt = head + """7. This README is a new version of a README that already has a reviewed Korean
   translation (both follow the new English source below). Where a paragraph,
   heading, table row, list item, alt text or comment of the new English is the
   same as in the previous English, copy its previous Korean translation
   unchanged. Translate only what is new or changed, with the same terms and
   style as the previous translation (for example, it keeps Grafana panel
   names and dashboard section names in English as they appear on screen; do
   the same). Do not improve or rephrase unchanged text.

=== README.md (English source, NEW version: translate this) ===""" + source_part + """

=== README.md (English source, PREVIOUS version) ===
""" + old_en + """

=== README.ko.md (reviewed Korean translation of the PREVIOUS version) ===
""" + old_ko
text = translate.extract(translate.run(tr, prompt, timeout=1800))
problems = translate.check(src, text)
if problems:
    Path(f"build/translations/{tid}.ko.rejected.md").parent.mkdir(parents=True, exist_ok=True)
    Path(f"build/translations/{tid}.ko.rejected.md").write_text(text)
    sys.exit("rejected: " + "; ".join(problems))
print("wrote", lint.write_draft(t, "ko", text, tr.name))
generate.sync(REPO_ROOT)
