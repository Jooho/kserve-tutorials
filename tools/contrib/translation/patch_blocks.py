"""patch_blocks.py <en file> <ko file> <marker>...: update only the blocks of the
Korean file whose English block contains one of the markers (text of the new
English wording). One call to the configured translation CLI (must be codex)
for all blocks of the file; every other block of the Korean file is untouched."""
import json, re
import os, sys
from pathlib import Path
REPO = Path(__file__).resolve().parents[3]
for _line in (REPO / ".tut.env").read_text().splitlines() if (REPO / ".tut.env").exists() else []:
    if "=" in _line and not _line.lstrip().startswith("#"):          # personal settings, as ./tut reads them
        _k, _v = _line.split("=", 1); os.environ.setdefault(_k.strip(), _v.strip().strip('"'))
sys.path.insert(0, str(REPO / "tools"))
from tut import project, translate
from tut.model import REPO_ROOT

en_p, ko_p, markers = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3:]
split = lambda t: re.split(r"(\n\s*\n)", t.strip("\n"))          # keeps the separators
en, ko = split(en_p.read_text()), split(ko_p.read_text())
assert len(en) == len(ko), (len(en), len(ko))
idx = [i for i in range(0, len(en), 2) if any(m in en[i] for m in markers)]
missing = [m for m in markers if not any(m in en[i] for i in idx)]
assert idx and not missing, missing
tr = translate.configured()
assert tr, "set TUT_AI_TRANSLATE (or TUT_AI): ./tut config TUT_AI_TRANSLATE=codex"
keep = project.load(REPO_ROOT).keep_english()
parts = "\n\n".join(f"### BLOCK {n}\n--- English (new wording) ---\n{en[i]}\n--- Korean (translation of the earlier wording) ---\n{ko[i]}" for n, i in enumerate(idx))
prompt = f"""Each block below is one part of a Markdown page about a tutorial: its English text, which was edited, and the Korean translation of the earlier wording.
Update each Korean block so that it says exactly what the new English says. Change only what the English change requires; keep the rest of the Korean wording, its terms and its style. Keep Markdown, `inline code`, link and image targets, table pipes and HTML tags as they are. Keep these names in English: {", ".join(keep)}.
{translate.LANG_STYLE["ko"]}

Output exactly three parts and nothing else:
{translate.BEGIN}
<a JSON array of {len(idx)} strings: the updated Korean blocks, in order>
{translate.END}

{parts}"""
out = json.loads(translate.extract(translate.run(tr, prompt, timeout=900)))
assert isinstance(out, list) and len(out) == len(idx), out
for i, new in zip(idx, out):
    assert new.strip(), "empty block"
    ko[i] = new.strip("\n")
ko_p.write_text("".join(ko) + "\n")
print(f"{ko_p}: {len(idx)} block(s) updated")
