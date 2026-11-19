"""`./tut lint`: the rules. Every rule has a stable code so docs, CI output and
reviews can refer to it. Errors fail CI; warnings are printed only.

Tutorial metadata
  T001 tutorial.yaml missing / invalid against schema/tutorial.schema.json
  T002 `id` must equal the directory name
  T003 `env` must reference an existing envs/<name>/<version>
  T004 kserve.default must be listed in kserve.tested
  T005 every tested KServe version must be supported by the env profile
  T006 deprecated/archived tutorials need a `deprecation` block
  T007 stable tutorials must use a frozen env profile

Documents (README.md and translations)
  D001 shell code blocks need exactly one role: run | verify | cleanup | skip
  D002 generated regions are stale -> run `./tut sync`
  D003 hard-coded KServe version outside generated regions
  D004 broken relative link or image
  D005 tut:include must point inside the tutorial directory
  D006 the tut:setup region must exist and come before any other run/verify block
  D007 non-draft tutorials need at least one `verify` block and one `cleanup` block
  D008 README for a declared language is missing
  D009 malformed markup (unclosed fence / region, unknown fence tokens)
  D010 translation marker missing or translation is stale (stale = warning)
  D011 translation must have the same sequence of shell block roles as README.md
  D012 steps must be safe to run twice (no `kubectl create` without --dry-run,
       `helm install`, `>>`, `kubectl delete` without --ignore-not-found) unless
       the block is marked `once`; warning for drafts
  D013 the UI terminal's aliases (k, kc) must not appear in README blocks

Catalog (catalog/)
  G001 every tag must be listed in catalog/tags.yaml (suggests the closest one)
  G002 catalog/tags.yaml invalid (schema, unknown group)
  C001 collection invalid (schema, id = file name)
  C002 collection member is not a tutorial
  C003 collection lists a tutorial twice
  C004 collection member is archived and has no replacement (warning)
  O001 .github/CODEOWNERS is stale -> run `./tut sync`

Manifests
  M001 container images must be pinned (no `latest`, no missing tag)

Script modules (lib/<name>/v<N>)
  L001 module.yaml invalid, or a script is not executable
  L002 a tutorial calls lib/<module> without listing it in `uses`, or lists a missing module
  L003 a frozen module was modified (compare with --base)
  L004 stable tutorials must only use frozen modules
  L005 module is not used by any tutorial (warning)

Environment profiles
  E001 profile.yaml invalid, or setup.sh / teardown.sh / README.md missing or not executable
  E002 a frozen profile was modified (compare with --base)
  E003 profile is not used by any tutorial (warning)
"""
from __future__ import annotations

import hashlib
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

import jsonschema
import yaml

from . import catalog, generate, markdown
from .model import (LANGS, MODULE_REF_RE, REPO_ROOT, Tutorial, load_envs,
                    load_modules, load_schema, load_tutorials)

TRANSLATION_RE = re.compile(r"<!--\s*tut-translation\s+source=(\S+)\s+sha=([0-9a-f]+)\s*-->")
HARDCODED_VERSION_RE = re.compile(r"kserve[^\n]{0,60}?\bv\d+\.\d+(\.\d+)?\b", re.I)
NOT_IDEMPOTENT = [
    (re.compile(r"\bkubectl\s+create\s+(?!token\b)(?!.*--dry-run)"),
     "`kubectl create` fails with AlreadyExists the second time; use `kubectl apply` "
     "or `kubectl create ... --dry-run=client -o yaml | kubectl apply -f -`"),
    (re.compile(r"\bhelm\s+install\b"), "`helm install` fails the second time; use `helm upgrade --install`"),
    (re.compile(r"(?<![0-9&])>>"), "`>>` appends again on every run; write the whole file with `>`"),
    (re.compile(r"\bkubectl\s+delete\b(?!.*--ignore-not-found)"),
     "`kubectl delete` fails with NotFound the second time; add --ignore-not-found"),
]
UI_ALIAS_RE = re.compile(r"(?:^|[|;&(]\s*|\$\(\s*)(k|kc)\s")
LINK_RE = re.compile(r"!?\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)|(?:src|href)=\"([^\"]+)\"")


@dataclass
class Finding:
    severity: str   # "error" | "warning"
    code: str
    path: Path
    line: int | None
    message: str

    def format(self, root: Path) -> str:
        rel = self.path.relative_to(root) if self.path.is_absolute() else self.path
        loc = f"{rel}:{self.line}" if self.line else f"{rel}"
        if os.environ.get("GITHUB_ACTIONS") == "true":
            ln = f",line={self.line}" if self.line else ""
            return f"::{self.severity} file={rel}{ln},title={self.code}::{self.message}"
        return f"{self.severity.upper():7} {self.code} {loc}: {self.message}"


def source_hash(en_text: str) -> str:
    """Hash of README.md with generated region bodies removed, so `./tut sync`
    alone never makes a translation stale."""
    stripped = markdown.replace_regions(en_text, lambda r: "")
    return hashlib.sha256(stripped.encode()).hexdigest()[:12]


def _logical_lines(code: str):
    """(1-based offset of the first physical line, text) with `\\` continuations
    joined and comment lines dropped."""
    buf, start = [], None
    for n, raw in enumerate(code.split("\n"), 1):
        if raw.lstrip().startswith("#") and not buf:
            continue
        start = start or n
        if raw.rstrip().endswith("\\"):
            buf.append(raw.rstrip()[:-1])
            continue
        buf.append(raw)
        yield start, " ".join(buf)
        buf, start = [], None
    if buf:
        yield start, " ".join(buf)


def _strip_code(text: str) -> list[tuple[int, str]]:
    """Lines outside fenced code blocks, with 1-based line numbers."""
    out, fence = [], None
    for n, line in enumerate(text.split("\n"), 1):
        m = markdown.FENCE_RE.match(line)
        if m:
            f = m.group("fence")
            if fence is None:
                fence = f
            elif f[0] == fence[0] and len(f) >= len(fence) and not m.group("info").strip():
                fence = None
            continue
        if fence is None:
            out.append((n, line))
    return out


def _region_lines(doc: markdown.Doc) -> set[int]:
    s = set()
    for r in doc.regions:
        s.update(range(r.start + 1, r.end + 2))  # 1-based, markers included
    return s


class Linter:
    def __init__(self, root: Path = REPO_ROOT, base: str | None = None):
        self.root = root
        self.base = base
        self.findings: list[Finding] = []
        self.tutorials = load_tutorials(root)
        self.envs = load_envs(root)
        self.modules = load_modules(root)

    def err(self, code, path, msg, line=None):
        self.findings.append(Finding("error", code, path, line, msg))

    def warn(self, code, path, msg, line=None):
        self.findings.append(Finding("warning", code, path, line, msg))

    # ------------------------------------------------------------------ run
    def run(self) -> list[Finding]:
        schema = load_schema("tutorial.schema.json")
        for t in self.tutorials:
            self.lint_meta(t, schema)
            self.lint_docs(t)
            self.lint_manifests(t)
        self.lint_catalog()
        self.lint_envs()
        self.lint_modules()
        if self.base:
            self.lint_frozen("envs", "profile.yaml", "E002")
            self.lint_frozen("lib", "module.yaml", "L003")
        self.lint_generated()
        return self.findings

    # ------------------------------------------------------------- metadata
    def lint_meta(self, t: Tutorial, schema: dict):
        f = t.path / "tutorial.yaml"
        for e in t.errors:
            self.err("T001", f, e)
        if t.errors:
            return
        v = jsonschema.Draft202012Validator(schema)
        for e in sorted(v.iter_errors(t.meta), key=lambda e: list(e.path)):
            where = "/".join(str(p) for p in e.path) or "(root)"
            self.err("T001", f, f"{where}: {e.message}")
        if t.meta.get("id") != t.id:
            self.err("T002", f, f"id {t.meta.get('id')!r} != directory name {t.id!r}")
        env = self.envs.get(t.env_ref) if t.env_ref else None
        if t.env_ref and env is None:
            self.err("T003", f, f"env {t.env_ref!r} does not exist under envs/")
        if t.kserve_default and t.kserve_default not in t.kserve_tested:
            self.err("T004", f, f"kserve.default {t.kserve_default} is not in kserve.tested")
        if env:
            for ver in t.kserve_tested:
                if not env.supports(ver):
                    self.err("T005", f, f"env {env.ref} does not support KServe {ver}")
            if t.status == "stable" and not env.frozen:
                self.err("T007", f, f"stable tutorial uses env {env.ref}, which is not frozen")
        for ref in t.uses:
            mod = self.modules.get(ref)
            if mod is None:
                self.err("L002", f, f"uses {ref!r}, but lib/{ref} does not exist")
            elif t.status == "stable" and not mod.frozen:
                self.err("L004", f, f"stable tutorial uses module {ref}, which is not frozen")
        if t.status in ("deprecated", "archived"):
            dep = t.meta.get("deprecation") or {}
            if not dep.get("reason"):
                self.err("T006", f, f"status {t.status} requires deprecation.reason")
            if t.status == "archived" and not dep.get("last_supported_kserve"):
                self.err("T006", f, "status archived requires deprecation.last_supported_kserve")

    # ------------------------------------------------------------ documents
    def lint_docs(self, t: Tutorial):
        if t.errors:
            return
        en_path = t.readme("en")
        for lang in t.langs:
            if not t.readme(lang).exists():
                self.err("D008", t.readme(lang), f"langs lists {lang!r} but the file is missing")
        for lang in LANGS:
            p = t.readme(lang)
            if p.exists() and lang not in t.langs:
                self.warn("D008", p, f"file exists but {lang!r} is not listed in langs")
        if not en_path.exists():
            return
        en_doc = self.lint_doc(t, en_path, is_source=True)
        for lang in LANGS:
            if lang == "en" or not t.readme(lang).exists():
                continue
            tr_path = t.readme(lang)
            tr_doc = self.lint_doc(t, tr_path, is_source=False)
            self.lint_translation(en_path, en_doc, tr_path, tr_doc)

    def lint_doc(self, t: Tutorial, path: Path, is_source: bool) -> markdown.Doc:
        text = path.read_text()
        doc = markdown.parse(text)
        for line, msg in doc.errors:
            self.err("D009", path, msg, line)
        # D001 roles
        for b in doc.blocks:
            if b.is_shell and b.role is None:
                self.err("D001", path, f"```{b.lang} block has no role "
                         "(add run | verify | cleanup | skip)", b.line)
            if not b.is_shell and b.role:
                self.err("D001", path, f"role {b.role!r} on a non-shell ```{b.lang} block", b.line)
        # D012 safe to run twice, D013 no UI-only aliases
        for b in doc.blocks:
            if not b.is_shell or b.role == "skip":
                continue
            for off, line in _logical_lines(b.code):
                if UI_ALIAS_RE.search(line):
                    self.err("D013", path, "`k`/`kc` are aliases of the UI terminal only; write "
                             "`kubectl` in tutorials (CI has no aliases)", b.line + off)
                if b.attrs.get("once"):
                    continue
                for rx, why in NOT_IDEMPOTENT:
                    if rx.search(line):
                        (self.warn if t.status == "draft" else self.err)(
                            "D012", path, f"not safe to run twice: {why} (or mark the block `once`)",
                            b.line + off)
        # D003 hard-coded versions
        region_lines = _region_lines(doc)
        for n, line in enumerate(text.split("\n"), 1):
            if n in region_lines or "tut-allow-version" in line:
                continue
            if HARDCODED_VERSION_RE.search(line):
                self.err("D003", path, "hard-coded KServe version; use $KSERVE_VERSION or "
                         "tutorial.yaml (or mark the line with <!-- tut-allow-version -->)", n)
        # D004 links
        for n, line in _strip_code(text):
            for m in LINK_RE.finditer(line):
                target = m.group(1) or m.group(2)
                if not target or re.match(r"^[a-z]+:", target) or target.startswith("#"):
                    continue
                p = (path.parent / target.split("#")[0]).resolve()
                if not p.exists():
                    self.err("D004", path, f"broken link: {target}", n)
        # D005 include scope: own directory or a declared module
        allowed = [t.path.resolve()] + [self.modules[u].path.resolve()
                                        for u in t.uses if u in self.modules]
        for r in doc.regions:
            if r.kind == "include" and r.args:
                tgt = (path.parent / r.args[0]).resolve()
                if not any(tgt.is_relative_to(a) for a in allowed):
                    self.err("D005", path, f"tut:include {r.args[0]} is outside the tutorial "
                             "directory and its declared modules", r.start + 1)
        # L002 module calls must be declared
        for b in doc.blocks:
            if not b.is_shell:
                continue
            for ref in sorted(set(MODULE_REF_RE.findall(b.code))):
                if ref not in t.uses:
                    self.err("L002", path, f"calls lib/{ref} but tutorial.yaml does not list "
                             f"it in `uses`", b.line)
        if not is_source:
            return doc
        # D006 setup first
        setups = [r for r in doc.regions if r.kind == "setup"]
        exec_blocks = [b for b in doc.blocks if b.is_shell and b.role in ("run", "verify")]
        if not setups:
            self.err("D006", path, "missing <!-- tut:setup --> region")
        elif exec_blocks and exec_blocks[0].in_region != "setup":
            self.err("D006", path, "a run/verify block appears before the tut:setup region",
                     exec_blocks[0].line)
        # D007 verify + cleanup
        roles = {b.role for b in doc.blocks if b.is_shell}
        for need in ("verify", "cleanup"):
            if need not in roles:
                msg = f"no `{need}` block — CI cannot prove this tutorial works" \
                    if need == "verify" else "no `cleanup` block"
                (self.warn if t.status == "draft" else self.err)("D007", path, msg)
        return doc

    def lint_translation(self, en_path, en_doc, tr_path, tr_doc):
        m = TRANSLATION_RE.search(tr_doc.text)
        expected = source_hash(en_doc.text)
        if not m:
            self.err("D010", tr_path, "missing translation marker; run "
                     f"`./tut translation mark {tr_path.parent.name} "
                     f"{tr_path.name.split('.')[1]}` after translating")
        elif m.group(2) != expected:
            self.warn("D010", tr_path, f"translation is behind {en_path.name} "
                      f"(translated from {m.group(2)}, source is now {expected})")
        seq_en = [b.role for b in en_doc.blocks if b.is_shell]
        seq_tr = [b.role for b in tr_doc.blocks if b.is_shell]
        if seq_en != seq_tr:
            self.err("D011", tr_path, f"shell block roles differ from {en_path.name}: "
                     f"{seq_tr} vs {seq_en}")

    # ------------------------------------------------------------ manifests
    def lint_manifests(self, t: Tutorial):
        for f in sorted(t.path.rglob("*.y*ml")):
            if f.name == "tutorial.yaml" or f.suffix not in (".yaml", ".yml"):
                continue
            try:
                docs = list(yaml.safe_load_all(f.read_text()))
            except yaml.YAMLError as e:
                self.err("M001", f, f"invalid YAML: {e}")
                continue
            for img in _images(docs):
                last = img.rsplit("/", 1)[-1]
                if "@" in img:
                    continue
                if ":" not in last or last.endswith(":latest"):
                    self.err("M001", f, f"image {img!r} is not pinned to a tag or digest")

    # ----------------------------------------------------------------- envs
    def lint_envs(self):
        schema = load_schema("env-profile.schema.json")
        used = {t.env_ref for t in self.tutorials}
        for ref, env in self.envs.items():
            prof = env.path / "profile.yaml"
            v = jsonschema.Draft202012Validator(schema)
            for e in v.iter_errors(env.meta):
                where = "/".join(str(p) for p in e.path) or "(root)"
                self.err("E001", prof, f"{where}: {e.message}")
            if env.meta.get("id") != ref:
                self.err("E001", prof, f"id {env.meta.get('id')!r} != {ref!r}")
            for name in ("setup.sh", "teardown.sh"):
                p = env.path / name
                if not p.exists():
                    self.err("E001", p, "missing")
                elif not os.access(p, os.X_OK):
                    self.err("E001", p, "not executable (chmod +x)")
            if not (env.path / "README.md").exists():
                self.err("E001", env.path / "README.md", "missing")
            if ref not in used:
                self.warn("E003", prof, "not used by any tutorial")

    def lint_catalog(self):
        import difflib
        tags_file = self.root / catalog.CATALOG / "tags.yaml"
        reg = catalog.load_tags(self.root)
        if reg:
            v = jsonschema.Draft202012Validator(load_schema("tags.schema.json"))
            for e in v.iter_errors(reg):
                self.err("G002", tags_file, f"{'/'.join(map(str, e.path)) or '(root)'}: {e.message}")
            groups = set((reg.get("groups") or {}))
            for name, tag in (reg.get("tags") or {}).items():
                if isinstance(tag, dict) and tag.get("group") not in groups:
                    self.err("G002", tags_file, f"tag {name!r}: unknown group {tag.get('group')!r}")
        known = set((reg.get("tags") or {}))
        for t in self.tutorials:
            for tag in t.meta.get("tags", []) or []:
                if tag not in known:
                    near = difflib.get_close_matches(tag, known, n=1)
                    hint = f" — did you mean {near[0]!r}?" if near else ""
                    self.err("G001", t.path / "tutorial.yaml",
                             f"tag {tag!r} is not in catalog/tags.yaml{hint} "
                             "(add it there with a group and description if it is really new)")
        by_id = {t.id: t for t in self.tutorials}
        schema = load_schema("collection.schema.json")
        for c in catalog.load_collections(self.root):
            v = jsonschema.Draft202012Validator(schema)
            for e in v.iter_errors(c.meta):
                self.err("C001", c.path, f"{'/'.join(map(str, e.path)) or '(root)'}: {e.message}")
            if c.meta.get("id") != c.id:
                self.err("C001", c.path, f"id {c.meta.get('id')!r} != file name {c.id!r}")
            seen = set()
            for m in c.members:
                if m in seen:
                    self.err("C003", c.path, f"{m!r} is listed twice")
                seen.add(m)
                t = by_id.get(m)
                if t is None:
                    self.err("C002", c.path, f"member {m!r} is not a tutorial (tutorials/{m}/)")
                elif t.status == "archived" and not (t.meta.get("deprecation") or {}).get("replacement"):
                    self.warn("C004", c.path, f"member {m!r} is archived and has no replacement: "
                              "readers of this collection hit a dead end")

    def lint_modules(self):
        schema = load_schema("module.schema.json")
        used = {u for t in self.tutorials for u in t.uses}
        for ref, mod in self.modules.items():
            f = mod.path / "module.yaml"
            v = jsonschema.Draft202012Validator(schema)
            for e in v.iter_errors(mod.meta):
                where = "/".join(str(p) for p in e.path) or "(root)"
                self.err("L001", f, f"{where}: {e.message}")
            if mod.meta.get("id") != ref:
                self.err("L001", f, f"id {mod.meta.get('id')!r} != {ref!r}")
            for sc in mod.scripts():
                if not os.access(sc, os.X_OK):
                    self.err("L001", sc, "not executable (chmod +x)")
            if ref not in used:
                self.warn("L005", f, "not used by any tutorial")

    def lint_frozen(self, top: str, meta_name: str, code: str):
        """Fail when a directory <top>/<name>/<ver> that was frozen on --base changed."""
        try:
            changed = subprocess.run(
                ["git", "diff", "--name-only", f"{self.base}...HEAD", "--", f"{top}/"],
                cwd=self.root, capture_output=True, text=True, check=True).stdout.split()
        except subprocess.CalledProcessError as e:
            self.warn(code, self.root / top, f"cannot diff against {self.base}: {e.stderr.strip()}")
            return
        seen = set()
        for path in changed:
            parts = Path(path).parts
            if len(parts) < 3:
                continue
            ref = f"{parts[1]}/{parts[2]}"
            if ref in seen:
                continue
            seen.add(ref)
            base_meta = subprocess.run(
                ["git", "show", f"{self.base}:{top}/{ref}/{meta_name}"],
                cwd=self.root, capture_output=True, text=True)
            if base_meta.returncode != 0:
                continue  # new
            if (yaml.safe_load(base_meta.stdout) or {}).get("frozen"):
                nxt = f"v{int(parts[2].lstrip('v')) + 1}" if parts[2].lstrip('v').isdigit() else "<next>"
                self.err(code, self.root / top / ref,
                         f"{top}/{ref} is frozen; create {top}/{parts[1]}/{nxt} instead "
                         "and move tutorials to it one by one")

    # ------------------------------------------------------------ generated
    def lint_generated(self):
        changed, errors = generate.sync(self.root, check=True)
        for e in errors:
            path, _, msg = e.partition(": ")
            self.err("D002", self.root / path, msg)
        for p in changed:
            if p.name == "CODEOWNERS":
                self.err("O001", p, "out of date with the owners fields; run `./tut sync`")
            else:
                self.err("D002", p, "generated regions are out of date; run `./tut sync`")


def _images(node):
    if isinstance(node, dict):
        for k, v in node.items():
            if k == "image" and isinstance(v, str):
                yield v
            else:
                yield from _images(v)
    elif isinstance(node, list):
        for x in node:
            yield from _images(x)


def mark_translation(t: Tutorial, lang: str) -> Path:
    en = t.readme("en").read_text()
    tr_path = t.readme(lang)
    text = tr_path.read_text()
    marker = f"<!-- tut-translation source=README.md sha={source_hash(en)} -->"
    if TRANSLATION_RE.search(text):
        text = TRANSLATION_RE.sub(marker, text, count=1)
    else:
        text = marker + "\n" + text
    tr_path.write_text(text)
    return tr_path
