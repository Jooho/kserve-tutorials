# Handbook: how this repository works

The map of the whole repository for the agents (Claude Code, Codex) that do most of the work here, and for people. [AGENTS.md](../AGENTS.md) has the hard rules and says what to read for each task; this handbook explains how the parts fit together, so you can change one without breaking another.

Read it fully before structural work (`tools/`, `schema/`, `envs/`, `lib/`, workflows). For a tutorial-only change, [authoring.md](authoring.md) is enough.

## 1. What we are building

Tutorials whose README **is the test**. Every command a reader runs is a role-tagged block; CI executes the README on a fresh Kind cluster, twice, for every KServe version the tutorial lists; a local UI runs the same blocks step by step. If a tutorial says it works, CI recently proved it.

```text
author (mostly an AI agent)                              reader
  │ ./tut draft / make new                                  ▲
  ▼                                                         │ GitHub, site, ./tut ui
tutorials/<id>/README.md + tutorial.yaml ── ./tut sync ──▶ README with generated regions
  │                                                         │
  ├─ ./tut lint      rules with codes (T/D/G/C/M/L/E/O/P)   │
  ├─ ./tut run       README → one bash script → real Kind   │
  └─ CI              lint + tests + site, then e2e of the affected tutorials
                     weekly: everything × every tested version + canary
                     release: full matrix green → main fast-forwards stable
```

### Decisions already made (do not re-open without the maintainer)

| Decision | Where it is recorded |
|---|---|
| One tutorial = one directory, self-contained; shared things are versioned parts (`envs/`, `lib/`) | RFC §4.1, §4.6, §4.7 |
| README.md (English) is the source; translations follow it, CI runs only English | RFC §4.8, §4.11 |
| Versions are per tutorial (`versions.tested`), not per branch; `stable` = last fully verified `main` | RFC §4.4, §4.15, release.md |
| A change made because of a new KServe version moves the old versions to a frozen revision (`tutorials/<id>/revisions/rN/`, no exceptions); CI runs two versions per tutorial (N = the newest KServe release (upstream), N-1 = the tutorial's newest tested version below N; a tutorial without N runs only that N-1); skipped versions (a gap between tested minors) are reported (`./tut revision todo`, weekly `ci-window` issue) and moved with `./tut revision keep` after the maintainer agrees | RFC 0002, authoring.md section 6 |
| `stable` moves once a month by schedule, skipped when `main` did not change (schedule off until a first dry run, 2026-11-26) | RFC 0002 section 8, release.md |
| No AI in GitHub Actions: every AI step (scouts, drafts, translations, explainers) runs locally | RFC 0002 section 3, AGENTS.md hard rule 13 |
| One env, `kind-kserve/v1`, with options (`env_options`) instead of one env per feature | RFC §6 (6), envs/kind-kserve/v1/README.md |
| The product's install comes from KServe's own `hack/kserve-install.sh`, pinned to the tag | envs/kind-kserve/v1 |
| New tutorials start from tested work through an AI (`./tut draft`), finished by a person | authoring.md § `./tut draft` |
| Shared steps are copied into each README by sync (`tut:define` / `tut:use`); learning paths are collections | authoring.md § Shared steps |
| **KServe only for now.** `project.yaml` keeps the engine free of the name; splitting engine and content, `platform/` components and other projects are deferred until a second project exists | backlog § E |
| AI translation only on request (`make precommit TRANSLATE=1`, `./tut translation draft`), never in `./tut sync` | this file § 6 |
| AI explainers (PoC): teaching pages next to a tutorial, written unattended from a live run, labelled, never executed, outside CI e2e; SVG not GIF | RFC section4.17, docs/explainer.md |
| Markdown under `docs/` has one line per paragraph (editors and GitHub wrap it); tutorial READMEs keep their line breaks, because changing them changes the source hash (translations, explainers) and re-runs e2e | authoring.md, "Writing good steps" |
| Work passes the `tech-lead` agent before it is put to the maintainer; it asks the maintainer only what it cannot settle and keeps their answers in a notebook | AGENTS.md "The tech lead comes before the maintainer", `.claude/agents/tech-lead.md`, `.claude/tech-lead/learned.md` |
| Plans come from the `project-planner` agent as small proposals; the maintainer approves which become GitHub issues (label `plan`); the tech lead runs them one at a time. docs/backlog.md stays the record of problems | AGENTS.md "Plans become issues, issues become work", `.claude/agents/project-planner.md` |
| Before a version is added to `versions.tested`, the `version-scout` agent compares upstream at both versions against what each tutorial uses; it reports and proposes, a run confirms. A bot PR adds the version when the canary passes, a local agent adds the scout report, the maintainer merges | AGENTS.md "A new product version: ask the version scout first", `.claude/agents/version-scout.md`, RFC 0002 section 8 |
| Tutorials for new features of a release are proposed as GitHub issues (label `tutorial-proposal`) by a local `feature-scout` agent; the maintainer approves on the issue | RFC 0002 section 8 |

## 2. Repository map

| Path | What | Who changes it |
|---|---|---|
| `tutorials/<id>/` | one tutorial: `tutorial.yaml`, `README.md`, `README.ko.md`, `manifests/`, `images/` | its owners |
| `tutorials/_template/` | what `make new` copies | rarely |
| `envs/<name>/vN/` | how to build a cluster: `profile.yaml`, `setup.sh`, `teardown.sh`, `tools.env`, `README.md` | frozen once a stable tutorial uses it → `vN+1` |
| `lib/<name>/vN/` | helper scripts tutorials call as `"$TUT_LIB/<name>/vN/x.sh"` (`module.yaml`) | same freeze rule |
| `catalog/` | `tags.yaml`, `groups.yaml`, `collections/<id>.yaml` (learning paths), `maintainers.yaml` | anyone, reviewed by owners |
| `project.yaml` | product name, title, `version_var`, canary upstream, glossary | rarely |
| `schema/` | JSON schemas for tutorial.yaml, profile.yaml, module.yaml, tags, collections, project | with `tools/` |
| `tools/tut/` | the engine (Python), see § 3 | needs tests; rules need approval |
| `tools/tests/` | pytest suite for the engine (no cluster) | with every `tools/` change |
| `tools/local-config.sh` | loads `.tut.env` into `./tut` and every setup step | rarely |
| `tools/install-tools.sh` | downloads an env's pinned CLI tools into `.tools/` | rarely |
| `tut` | the CLI entry point (uses `.venv` when present) | rarely |
| `.github/workflows/` | `ci.yml`, `run-tutorials.yml`, `scheduled.yml`, `release.yml`, `site.yml` (§ 7) | with care |
| `.github/scripts/` | `diagnose.sh` (cluster dump on failure), `report.py` (weekly issues) | with care |
| `.github/CODEOWNERS` | **generated** by `./tut sync` from `owners` | never by hand |
| `docs/` | this handbook, authoring, migration, CI playbook, release, backlog, RFC, prompts (ready-made first messages for agents) | keep in step with the code |
| `.claude/` | for AI agents: `agents/tech-lead.md` (the maintainer's stand-in), `agents/project-planner.md` (proposes small plans, files approved ones as issues), `agents/version-scout.md` (which tutorials a new product version breaks, from the upstream changes), `agents/feature-scout.md` (tutorial proposals for a release's new features), `tech-lead/learned.md` (the notebook of the maintainer's answers), `skills/` (Claude Code wrappers around `./tut`) | maintainer, the tech lead (its notebook) |
| `build/` | generated: drafts, rejected translations, site source (git-ignored) | tools |
| `.venv/`, `.tools/`, `.tut.env` | toolkit, pinned CLI tools, personal settings (git-ignored) | the user's machine |

## 3. Code map (`tools/tut/`)

| Module | Responsibility | Tests |
|---|---|---|
| `cli.py` | argparse front end of every `./tut` command; completion (`complete()` walks the parser) | test_completion, test_local_config |
| `model.py` | load `tutorial.yaml`, env profiles, lib modules; `Tutorial` properties (`default_version`, `tested_versions`, `env_options`, ...); `env_settings()` → `TUT_ENV_*`; revisions (`load_revisions`, `variants`), `resolve(t, version)`, N and N-1 (`latest()`, `ci_minors()`) | test_rules, test_revisions |
| `revision.py` | `./tut revision start` and `keep`: copy a tutorial from the base branch into `revisions/rN/`, re-render its setup and header, re-point links, move the current tutorial to the new version | test_revisions |
| `project.py` | load and validate `project.yaml` (`ProjectError`, lint P001) | test_project |
| `markdown.py` | parse a README: fenced blocks with role and attrs, `<!-- tut:... -->` regions | test_rules |
| `generate.py` | `./tut sync`: fill `tut:header`, `tut:setup`, `tut:include`, `tut:use`, `tut:catalog`; write CODEOWNERS | test_rules, test_shared |
| `shared.py` | shared steps: definitions, `render_use`, which steps a learning path already covers | test_shared, test_learning_path |
| `lint.py` | every rule, with a code; translation state and marking (`translation_state`, `mark_translation`) | test_rules, test_* |
| `runner.py` | `./tut run`: README → one bash script (file, not `bash -c`), cleanup trap, `--twice`, JSON report | test_rules |
| `plan.py` | what CI runs: `affected` (changed paths → tutorials), scheduled and canary matrices, each tutorial limited to its N and N-1 (`model.latest`, `ci_minors`); skipped versions (`skipped`); new revisions in a PR | test_rules, test_revisions |
| `catalog.py` | tags, groups, collections (resolved per version), CODEOWNERS text | test_catalog |
| `aicli.py` | the one reader of `TUT_AI`, `TUT_AI_REVIEW` and their `_ARGS` (older `TUT_TRANSLATOR*` too); translate, draft and explain keep their own command lines | test_translate, test_draft, test_explain |
| `translate.py` | AI translation: presets, prompt, mechanical check of the output, `draft_one` | test_translate |
| `explain.py` | `./tut explain`: AI explainer: live walk (FIFO shell, read-only probes, evidence), checks X001-X005, mark, unattended draft | test_explain |
| `draft.py` | `./tut draft`: copy input, build prompt and parts catalog, run the AI, prune, coverage, report | test_draft |
| `scaffold.py` | `./tut new` from the template | test_scaffold |
| `doctor.py` | `./tut doctor`: toolkit, host (Docker, CPU/memory), environment checks | test_doctor_tools |
| `site.py` | `./tut site`: MkDocs source tree in `build/site-src` | (make site, `mkdocs --strict`) |
| `release.py` | next version, fast-forward check, verdict over reports, release notes | test_release |
| `ui/server.py` | `./tut ui` (aiohttp): tutorial API, live preview, problems, editor, translation, shell tabs, WebSockets | test_shared, test_learning_path, test_ui_session |
| `ui/session.py` | one PTY bash per tutorial; runs blocks one at a time at the prompt; shares `env.sh` with extra shell tabs | test_ui_session |
| `ui/static/` | `index.html`, `app.js`, `app.css`, `shell.html/js` (⧉ terminal tab), vendored xterm.js | browser check (Playwright) |

## 4. How the pieces work

**Sync (`./tut sync`).** Deterministic and offline: same input, same output. CI checks it with lint D002 (regions stale) and O001 (CODEOWNERS stale). Never add anything slow, networked or random to it.

**The setup step.** `tut:setup` is generated from `tutorial.yaml` and `project.yaml`. It exports `$KSERVE_VERSION` (default `versions.default`), `$NS`, `$REPO_ROOT` and `$TUT_LIB`, sources `.tut.env`, and puts the env's pinned tools on `PATH`. Then it calls `envs/<env>/setup.sh` with the tutorial's `env_options` as `TUT_ENV_TYPES/MODE/KEDA`, creates the namespace and `cd`s into the tutorial. A reader who pastes it by hand gets exactly what CI gets.

**The env (`envs/kind-kserve/v1/setup.sh`).** It is idempotent and leaves a marker, ConfigMap `kube-system/tut-env`: profile, KServe version, types, mode and keda.
- A matching cluster is reused.
- When types are missing, only those are added.
- If the mode differs, it stops (`TUT_ENV_RECREATE=1` replaces the cluster).

**The runner (`./tut run`).** It joins `run`/`verify` blocks into one bash script, so variables and `cd` carry over. Block code is pasted **byte for byte** (CI-009). The script runs from a file (CI-008). `verify retry=N delay=S` runs in a retried subshell; `cleanup` runs from an EXIT trap. `--twice` runs every step again in the same shell before cleanup (D012).

**The UI (`./tut ui`).** It uses the same parser, the same block semantics and the same setup as the runner, so passing in the UI means passing in CI. The UI is a convenience; CI is the authority. What it does:
- Live preview shows the README as sync will write it.
- Lists this tutorial's lint findings.
- ✎ Edit for README or tutorial.yaml.
- Creates a translation from a chip.
- ⧉ opens an extra terminal tab with the tutorial shell's variables.
- 🗑 Teardown runs the env's `teardown.sh` in the tutorial shell (pseudo block index -1, never a step state), only when no step is running, after a confirmation that names the cluster and warns when it has no `tut-env` marker; the steps reset once it passed.
- The page theme is Auto / Light / Dark; both terminals (main and ⧉) follow it and share their own text size (`static/term-theme.js`).
- Learning paths open with `?collection=`: covered `run` blocks are hidden, cleanup waits for the end, and the collection `vars` are exported.

**Versions.** A tutorial lists `versions.default` (what readers get) and `versions.tested` (what PR CI, the weekly run and releases run, on N, the newest KServe release, and N-1, the tutorial's newest tested version below it; RFC 0002). Older versions of a changed tutorial live in `revisions/rN/`. An env declares `versions.min/max` it can install (T005). The canary runs stable tutorials on the newest upstream release (`project.yaml upstream`) and opens an issue when it fails. The canary only sees a failure after the release and not for `draft` tutorials; the `version-scout` agent reads the upstream changes between two versions and says beforehand which tutorials they touch (AGENTS.md "A new product version").

## 5. Commands by task

| I want to | Run |
|---|---|
| set up a machine | `make setup && make doctor` |
| remember settings | `./tut config TUT_AI=claude KIND_CLUSTER_NAME=tut` (`.tut.env`) |
| start a tutorial from tested work | `./tut draft <folder> --id <id> --owner <handle> [--collection <c>]` |
| start an empty tutorial | `make new T=<id> TITLE="..." OWNER=<handle>` |
| see the script CI will run | `./tut run <id> --dry-run` |
| run it for real | `./tut run <id> --twice` (`--keep-on-failure` to debug) |
| step through it | `./tut ui` |
| translate | `./tut translation draft <id> ko`, review, `./tut translation mark <id> ko` |
| translate everything missing | `make precommit TRANSLATE=1` |
| explain a tutorial with diagrams (AI) | `./tut explain draft <id>` (walk, write, AI review, one fix round), read it, `./tut explain mark <id>` |
| look at the site as readers will see it | `make site-run` (= `./tut site --serve`): builds it and serves `build/site` on `127.0.0.1:8775` (next free port if taken; `PORT=N` or `TUT_SITE_PORT`) |
| what CI will run for my branch | `./tut affected --base origin/main` |
| before every commit | `make precommit` |
| test the engine | `PYTHONPATH=tools python3 -m pytest -q tools/tests` |
| inspect | `./tut list`, `./tut show <id>`, `./tut translation`, `./tut project` |

## 6. Configuration and variables

Precedence everywhere: **shell > `.tut.env` > default**. Set with `./tut config KEY=VALUE` (no args: show). Keys:

| Key | Meaning |
|---|---|
| `KIND_CLUSTER_NAME` | the kind cluster tutorials create or reuse (default `kind`) |
| `TUT_SKIP_TOOLS` | CLI tools you provide yourself, e.g. `helm` |
| `TUT_ENV_RECREATE` | `1` = replace a cluster built by something else (destructive) |
| `TUT_AI` | your AI CLI for `draft` and translations: `claude`, `copilot`, `codex` or `cmd:<command>` |
| `TUT_AI_ARGS` | extra flags for it, e.g. `--model sonnet` |
| `TUT_AI_REVIEW` | AI CLI that reviews an explainer (`explain review`, end of `explain draft`); several, comma-separated, review independently (`claude,codex`); default: `TUT_AI` |
| `TUT_UI_PORT` | port of `./tut ui`; default 8765, or the next free port when 8765 is taken (a port you set is never swapped) |
| `TUT_SITE_PORT` | port of `make site-run` / `./tut site --serve`; default 8775, or the next free port (a port you set is never swapped) |
| `TUT_AI_REVIEW_ARGS` | extra flags, given to every reviewer |
| `TUT_TRANSLATOR`, `TUT_TRANSLATOR_ARGS` | older names of the two above, still read |

Set by the tooling, not by people:
- **Tutorials read:** `KSERVE_VERSION`, `NS`, `REPO_ROOT`, `TUT_LIB`.
- **The env reads:** `TUT_ENV_TYPES/MODE/KEDA`, `TUT_CACHE`.
- **The runner and UI use:** `TUT_ID`, `TUT_BLOCK`, `TUT_STATE_FILE`, `TUT_UI`, `TUT_UI_DIR`, `TUT_ENV_FROM`, `TUT_CONFIG_LOADED`.

The AI CLI runs on the user's machine with the user's login. No API keys are in the repository or in CI.

## 7. CI

| Workflow | When | What |
|---|---|---|
| `ci.yml` | every PR, push to main | job `check`: `make test`, `make lint BASE=<base>`, `make site`, `./tut affected`; then `e2e / <id> @ <version>` for the affected tutorials only |
| `run-tutorials.yml` | called by the others | one job per matrix entry: `make doctor`, `./tut run --version V --twice --keep-on-failure --report`, diagnostics on failure, teardown, report artifact |
| `scheduled.yml` | weekly + manual | every tutorial and revision × its N and N-1, and the canary; `report.py` files one issue per failure; job `new-version`: a bot PR adding a version the canary passed (secret `TUT_BOT_TOKEN`), and a `new-release` issue for feature-scout; job `skipped-versions`: one `ci-window` issue listing tutorials with a gap in `versions.tested` |
| `release.yml` | `make release`; monthly (1st, 05:23 UTC) once turned on after a first dry run | full in-window matrix at one commit; if green, fast-forward `stable`, tag `YYYY.MM.N`, publish the site; scheduled: skip when nothing changed, issue on failure |
| `site.yml` | push to `stable` | build and publish the site |

What runs in a PR is decided by `plan.affected`:
- a change under `tutorials/<id>/` runs that tutorial on its in-window versions, and a new or touched `revisions/rN/` on its own;
- a change under `envs/<env>/` runs the tutorials using that env;
- a change under `lib/<m>/` runs the tutorials that list it in `uses`;
- any file in `EXECUTION_PATHS` (runner, parser, setup generator, `project.yaml`, tool installer, local config, `run-tutorials.yml`, diagnose) runs **every** tutorial;
- a change under `tutorials/<id>/explainer/` runs none (an explainer is never executed);
- docs and UI changes run none.

The weekly run catches the rest.

## 8. Easy to break (and what protects it)

| Invariant | Protected by |
|---|---|
| Block code reaches bash unchanged (no indenting, heredocs intact) | CI-009, test_rules runner tests |
| The runner is not in its own command line (`pkill -f` in a step) | CI-008, script file |
| `cmd \| grep -q` under `pipefail` fails a true check (SIGPIPE) | CI-007; write `grep ... >/dev/null` |
| Sync is deterministic; generated text never edited by hand | D002, O001 |
| Every step is safe to run twice | D012, `--twice` in CI |
| Tests do not depend on the developer's git config or machine | CI-006, `conftest.py` isolates git |
| The browser never mixes an old `app.js` with a new page | `Cache-Control: no-cache` (test_shared) |
| Env marker format (`profile\|version\|types\|mode\|keda`) | test_env_kserve with fake kind/kubectl |
| Translation keeps code, regions and links | translate check, D011 |
| No script from a README runs in the UI (it holds the token and the shell) | `ui/sanitize.py` allowlist, CSP `script-src 'self'` (no inline script in the pages), `/files/` sandboxed — test_ui_safe_html |

## 9. How agents work here

- **One branch per change, from the latest `main`.** Never stack a branch on another unmerged branch; a PR's base is always `main`.
- **Small PRs, one feature each.** CI e2e runs only what the PR affects; mixing a runner change into a tutorial PR runs every tutorial.
- **Before every commit:** `make precommit`. Before a PR: also `./tut run <id> --dry-run` for tutorials you touched, and the real run when you can (`./tut run <id> --twice`).
- **Prove behaviour-preserving refactors:** save `./tut run --dry-run`, `./tut list`, `./tut site` output before, compare after.
- **Every git or GitHub write needs the maintainer's permission, every time** (branch, commit, push, PR, merge, re-run, settings): say what, why, the exact commands and what it changes, then ask and wait. A tech-lead pass is not permission. Never push to `stable`.
- **Leave knowledge behind:**
  - a CI failure becomes a lesson in authoring.md § Rules learned from CI, and a lint rule when it can be checked;
  - a problem you cannot fix now goes into backlog.md with evidence;
  - a design decision goes into the RFC or the table in § 1.
- **When docs and code disagree, stop and report it.** Then fix the one that is wrong in the same PR.
