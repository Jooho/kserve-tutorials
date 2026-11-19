"""`./tut sync`: (re)generate every <!-- tut:... --> region from its source of truth.

Region kinds
  tut:header             status / tested versions / env line, from tutorial.yaml
  tut:setup              the first runnable block: versions, namespace, env setup
  tut:include <path>     a file from the tutorial directory, shown as a code block
  tut:catalog            the tutorial catalog (root README only)
"""
from __future__ import annotations

from pathlib import Path

from . import markdown, shared
from .model import (LANGS, REPO_ROOT, Tutorial, env_settings, load_envs, load_modules, load_tutorials,
                    readme_name, version_key)

EXT_LANG = {".yaml": "yaml", ".yml": "yaml", ".json": "json", ".py": "python",
            ".sh": "bash", ".toml": "toml", ".txt": "text", ".go": "go",
            "Dockerfile": "dockerfile"}

GEN_NOTE = {
    "en": "Generated from tutorial.yaml by `./tut sync` — do not edit by hand.",
    "ko": "tutorial.yaml에서 `./tut sync`로 생성됨 — 직접 수정하지 마세요.",
}

STATUS_TEXT = {
    "en": {"draft": "🚧 draft", "stable": "✅ stable", "deprecated": "⚠️ deprecated",
           "archived": "🗄️ archived"},
    "ko": {"draft": "🚧 작성 중", "stable": "✅ 안정", "deprecated": "⚠️ 지원 중단 예정",
           "archived": "🗄️ 보관됨"},
}


class SyncError(Exception):
    pass


def _lang_for(path: Path) -> str:
    return EXT_LANG.get(path.name) or EXT_LANG.get(path.suffix, "text")


def render_include(readme_dir: Path, args: list[str]) -> str:
    if not args:
        raise SyncError("tut:include needs a path")
    target = (readme_dir / args[0]).resolve()
    if not target.is_file():
        raise SyncError(f"tut:include: {args[0]} does not exist")
    lang = _lang_for(target)
    info = f"{lang} skip" if lang in markdown.SHELL_LANGS else lang
    body = target.read_text().rstrip("\n")
    fence = "```"
    while fence in body:
        fence += "`"
    return f"{fence}{info}\n{body}\n{fence}"


def env_tool_dirs(env_ref: str, root: Path = REPO_ROOT) -> list[str]:
    """`$REPO_ROOT/.tools/<tool>/<version>` for every tool in envs/<env>/tools.env."""
    f = root / "envs" / env_ref / "tools.env"
    if not f.exists():
        return []
    names = {"KIND": "kind", "KUBECTL": "kubectl", "HELM": "helm",
             "CLOUD_PROVIDER_KIND": "cloud-provider-kind"}
    out = []
    for line in f.read_text().splitlines():
        line = line.split("#", 1)[0].strip()
        if "=" in line:
            k, v = (x.strip() for x in line.split("=", 1))
            if k in names and v:
                out.append(f"$REPO_ROOT/.tools/{names[k]}/{v}")
    return out


def render_setup(t: Tutorial) -> str:
    env = t.env_ref
    lines = [
        "```bash run",
        f"# {GEN_NOTE['en']}",
        f'export KSERVE_VERSION="${{KSERVE_VERSION:-{t.kserve_default}}}"',
        f'export NS="${{NS:-{t.namespace}}}"',
        'export REPO_ROOT="$(git rev-parse --show-toplevel)"',
        'source "$REPO_ROOT/tools/local-config.sh"   # your settings in .tut.env, if any',
        'export TUT_LIB="$REPO_ROOT/lib"',
    ]
    if env:
        dirs = env_tool_dirs(env)
        if dirs:
            lines.append("# pinned CLI tools of the environment, for this shell only")
            lines.append(f'export PATH="{":".join(dirs)}:$PATH"')
        settings = env_settings(t, load_envs(t.path.parent.parent).get(env))
        prefix = " ".join(f"{k}={v}" for k, v in settings)
        if settings:
            lines.append("# what this tutorial needs from the environment (env_options in tutorial.yaml)")
        lines.append(f'{prefix + " " if prefix else ""}"$REPO_ROOT/envs/{env}/setup.sh"')
    if env:   # no env = no cluster (e.g. a tutorial that only runs local commands)
        lines.append('kubectl create namespace "$NS" --dry-run=client -o yaml | kubectl apply -f -')
    lines += [f'cd "$REPO_ROOT/tutorials/{t.id}"', "```"]
    return "\n".join(lines)


def render_header(t: Tutorial, lang: str) -> str:
    st = STATUS_TEXT[lang].get(t.status, t.status)
    tested = ", ".join(t.kserve_tested) or "—"
    env = t.env_ref or "—"
    env_link = f"[`{env}`](../../envs/{env}/)" if t.env_ref else env
    if lang == "ko":
        gpu = "필요" if t.needs_gpu else "불필요"
        line = (f"> **상태:** {st} · **검증된 KServe:** {tested} · "
                f"**환경:** {env_link} · **GPU:** {gpu}")
    else:
        gpu = "required" if t.needs_gpu else "not required"
        line = (f"> **Status:** {st} · **Tested with KServe:** {tested} · "
                f"**Environment:** {env_link} · **GPU:** {gpu}")
    out = [f"<!-- {GEN_NOTE[lang]} -->", line]
    others = [l for l in t.langs if l != lang]
    if others:
        names = {"en": "English", "ko": "한국어"}
        links = " · ".join(f"[{names[o]}]({readme_name(o)})" for o in others)
        out += [">", f"> 🌐 {links}"]
    dep = t.meta.get("deprecation")
    if t.status in ("deprecated", "archived") and dep:
        reason = dep.get("reason", "")
        last = dep.get("last_supported_kserve")
        repl = dep.get("replacement")
        label = "주의" if lang == "ko" else "Note"
        msg = f"> **{label}:** {reason}"
        if last:
            msg += (f" 마지막 지원 KServe: {last}." if lang == "ko"
                    else f" Last supported KServe: {last}.")
        if repl:
            msg += (f" 대체 튜토리얼: [{repl}](../{repl}/)." if lang == "ko"
                    else f" Replacement: [{repl}](../{repl}/).")
        out += [">", msg]
    return "\n".join(out)


def render_catalog(tutorials: list[Tutorial], lang: str = "en", root: Path = REPO_ROOT) -> str:
    from . import catalog
    visible = [t for t in tutorials if not t.errors]
    by_id = {t.id: t for t in visible}
    hdr = ("| Tutorial | Status | Tested KServe | Tags | Environment | GPU |",
           "|---|---|---|---|---|---|")
    rows = []
    for t in visible:
        st = STATUS_TEXT[lang].get(t.status, t.status)
        tags = " ".join(f"`{x}`" for x in t.meta.get("tags", []) or [])
        rows.append(f"| [{t.title(lang)}](tutorials/{t.id}/) | {st} | "
                    f"{', '.join(t.kserve_tested)} | {tags} | `{t.env_ref or '—'}` | "
                    f"{'yes' if t.needs_gpu else 'no'} |")
    cols = []
    for c in catalog.load_collections(root):
        cols += ["", f"- **{c.text('title', lang)}** — {c.text('description', lang)}".rstrip(" —")]
        for r in catalog.resolve(c, by_id):
            if r["state"] == "missing":
                continue
            t = by_id[r["shown"]]
            note = {"archived": " 🗄️", "replaced": f" (replaces `{r['member']}`)"}.get(r["state"], "")
            cols.append(f"  {r['n']}. [{t.title(lang)}](tutorials/{t.id}/){note}")
    by_version: dict[str, list[Tutorial]] = {}
    for t in visible:
        if t.status == "archived":
            continue
        for v in t.kserve_tested:
            by_version.setdefault(v, []).append(t)
    out = ["<!-- " + GEN_NOTE[lang].replace("tutorial.yaml", "tutorials/*/tutorial.yaml") + " -->",
           *hdr, *rows]
    if cols:
        out += ["", "**Collections** (reading paths)", *cols]
    out += ["", "**By KServe version**", ""]
    for v in sorted(by_version, key=version_key, reverse=True):
        links = ", ".join(f"[{t.id}](tutorials/{t.id}/)" for t in by_version[v])
        out.append(f"- **{v}**: {links}")
    return "\n".join(out)


def sync_file(path: Path, t: Tutorial | None, lang: str, tutorials: list[Tutorial],
              root: Path = REPO_ROOT) -> str:
    text = path.read_text()

    def render(r: markdown.Region):
        if r.kind == "include":
            return render_include(path.parent, r.args)
        if r.kind == "setup":
            if t is None:
                raise SyncError("tut:setup only works inside a tutorial")
            return render_setup(t)
        if r.kind == "header":
            if t is None:
                raise SyncError("tut:header only works inside a tutorial")
            return render_header(t, lang)
        if r.kind == "catalog":
            return render_catalog(tutorials, lang, root)
        if r.kind == "define":
            return None                       # written by the author: left as it is
        if r.kind == "use":
            if t is None or len(r.args) != 1:
                raise SyncError("tut:use takes one name and only works inside a tutorial")
            try:
                return shared.render_use(r.args[0], lang, tutorials)
            except ValueError as e:
                raise SyncError(str(e))
        raise SyncError(f"unknown region tut:{r.kind}")

    def padded(r: markdown.Region):
        # Blank lines around the body: MkDocs (Python-Markdown) would otherwise
        # swallow a code fence that directly follows an HTML comment.
        body = render(r)
        return None if body is None else "\n" + body + "\n"

    return markdown.replace_regions(text, padded)


def targets(root: Path = REPO_ROOT):
    """Yield (path, tutorial, lang) for every markdown file that may hold regions."""
    tutorials = load_tutorials(root, include_template=True)
    for t in tutorials:
        for lang in LANGS:
            p = t.readme(lang)
            if p.exists():
                yield p, t, lang
    for mod in load_modules(root).values():
        for lang in LANGS:
            p = mod.path / readme_name(lang)
            if p.exists():
                yield p, None, lang
    for env in load_envs(root).values():
        for lang in LANGS:
            p = env.path / readme_name(lang)
            if p.exists():
                yield p, None, lang
    for lang in LANGS:
        p = root / readme_name(lang)
        if p.exists():
            yield p, None, lang


def sync(root: Path = REPO_ROOT, check: bool = False) -> tuple[list[Path], list[str]]:
    """Regenerate regions. Returns (files that changed / would change, errors)."""
    changed, errors = [], []
    tutorials = load_tutorials(root)
    for path, t, lang in targets(root):
        try:
            new = sync_file(path, t, lang, tutorials, root)
        except SyncError as e:
            errors.append(f"{path.relative_to(root)}: {e}")
            continue
        if new != path.read_text():
            changed.append(path)
            if not check:
                path.write_text(new)
    from . import catalog
    owners_path = root / catalog.CODEOWNERS_PATH
    owners = catalog.codeowners(root)
    if not owners_path.exists() or owners_path.read_text() != owners:
        changed.append(owners_path)
        if not check:
            owners_path.parent.mkdir(parents=True, exist_ok=True)
            owners_path.write_text(owners)
    return changed, errors
