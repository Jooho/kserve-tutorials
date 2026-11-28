"""update_explainer.py <tutorial id> [<base ref>]: Korean explainer page from the
changed English one, keeping the reviewed translation of the previous version
(on <base ref>, default origin/main) where the English did not change. Refuses
output whose code, image targets, headings or marker line differ from the
English page. Uses the configured translation CLI."""
import re, subprocess
import os, sys
from pathlib import Path
REPO = Path(__file__).resolve().parents[3]
for _line in (REPO / ".tut.env").read_text().splitlines() if (REPO / ".tut.env").exists() else []:
    if "=" in _line and not _line.lstrip().startswith("#"):          # personal settings, as ./tut reads them
        _k, _v = _line.split("=", 1); os.environ.setdefault(_k.strip(), _v.strip().strip('"'))
sys.path.insert(0, str(REPO / "tools"))
tid = sys.argv[1]
base_ref = sys.argv[2] if len(sys.argv) > 2 else "origin/main"
from tut import translate, project  # noqa

src = (REPO / "tutorials" / tid / "explainer" / "index.md").read_text()
_git = lambda p: subprocess.run(["git", "-C", str(REPO), "show", f"{base_ref}:{p}"], capture_output=True, text=True, check=True).stdout
old_en = _git(f"tutorials/{tid}/explainer/index.md")
old_ko = _git(f"tutorials/{tid}/explainer/index.ko.md")
keep = project.load(REPO).keep_english() if hasattr(project, "load") else list(project.COMMON_GLOSSARY)
prompt = f"""Translate this AI-written teaching page about a tutorial from English to Korean.

A program checks your output; if any rule is broken the translation is discarded.
1. Translate prose, headings, list and table text, image alt text, and the text inside <details>/<summary>.
2. Keep every fenced code block (```...```) exactly as it is, including text blocks.
3. Keep the first line (the HTML comment) exactly. Keep the last line ("Based on a run of ...") exactly, in English.
4. Keep image and link targets (the part in parentheses) and HTML tags unchanged; keep `inline code` unchanged.
5. Keep these names in English: {", ".join(keep)}.
6. Do not add, remove or reorder sections, bullets, table rows or questions.
Use a natural technical Korean style for engineers.
{translate.LANG_STYLE["ko"]}

Output exactly three parts and nothing else:
{translate.BEGIN}
<the translated Markdown>
{translate.END}

7. This page is a new version of a page that already has a reviewed Korean
   translation (both follow the new English source below). Where a paragraph,
   heading, table row, list item, alt text or question of the new English is
   the same as in the previous English, copy its previous Korean translation
   unchanged. Translate only what is new or changed, with the same terms and
   style as the previous translation. Do not improve or rephrase unchanged text.

=== index.md (English source, NEW version: translate this) ===
{src}

=== index.md (English source, PREVIOUS version) ===
{old_en}

=== index.ko.md (reviewed Korean translation of the PREVIOUS version) ===
{old_ko}"""

tr = translate.configured()          # the same CLI and model as ./tut translation draft
assert tr, "set TUT_AI_TRANSLATE (or TUT_AI): ./tut config TUT_AI_TRANSLATE=codex"
print(f"{tid}: translating with {' '.join(a for a in tr.argv if a != '{prompt}')}", flush=True)
text = translate.run(tr, prompt, timeout=2400)
ko = translate.extract(text)

def fences(t): return re.findall(r"```.*?```", t, re.S)
def targets(t): return re.findall(r"\]\(([^)]+)\)", t)
def heads(t): return [l.split()[0] for l in t.splitlines() if l.startswith("#")]
probs = []
if fences(ko) != fences(src): probs.append("code blocks changed")
if targets(ko) != targets(src): probs.append("image/link targets changed")
if heads(ko) != heads(src): probs.append("heading structure changed")
if ko.splitlines()[0] != src.splitlines()[0]: probs.append("marker line changed")
if ko.strip().splitlines()[-1] != src.strip().splitlines()[-1]: probs.append("last line changed")
dst = REPO / "tutorials" / tid / "explainer" / "index.ko.md"
if probs:
    rej = REPO / "build" / "translations" / f"{tid}.explainer.ko.rejected.md"
    rej.parent.mkdir(parents=True, exist_ok=True); rej.write_text(ko)
    print(f"{tid}: REJECTED ({'; '.join(probs)}), kept in {rej}"); sys.exit(1)
lines = ko.splitlines()
lines[0] = "<!-- tut-explainer source=README.md sha=0 by=codex reviewed=no -->"   # a new text: a person has not read it yet
dst.write_text("\n".join(lines) + "\n")
print(f"{tid}: wrote {dst}")
