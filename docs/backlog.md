# Backlog: problems this repository exists to solve

Everything here was hit for real while building the repository (mostly in
the first end-to-end runs of PR #1). Each item says why it matters. Agents:
read this before starting structural work, pick items from here, and update
the status and links when you finish one. Do not delete items; mark them done
with the PR that closed them.

Status: ☐ open · ◐ in progress · ☑ done · ⏸ deferred (see the section's decision)

## A. Platform and environments ("is the cluster really ready?")

| # | Status | Item | Why / evidence |
|---|---|---|---|
| A1 | ☐ | Split environments into **contract + check + provisioners**: `contract.yaml` (what a tutorial needs: KServe version, CRDs, Gateway reachable, webhooks answering), `check.sh` (validates *any* current cluster), `provision/kind.sh` (one way to satisfy it) | Tutorials must work on the reader's own cluster, not only on a kind we create |
| A2 | ☐ | **Bring-your-own-cluster mode**: setup uses the current cluster if `check.sh` passes, provisions kind only when asked | Today setup always creates kind and refuses other clusters |
| A3 | ☐ | **Environment tests on their own**: `./tut env test <env> --version X` (provision → check → teardown); CI runs env jobs first and marks tutorials "blocked by env" instead of failing them | Install failures showed up as tutorial failures (CI-001, CI-002) |
| A4 | ◐ | **Create the kind cluster ourselves** with a pinned kind version and node image (Kubernetes version); keep using KServe's `hack/kserve-install.sh` only for the KServe stack — *kind is now pinned per environment (v0.30.0 → kindest/node v1.34.0); cluster creation still via KServe's script* | kind and `kindest/node` versions came from the CI runner image (v1.37.0 that day), so results could change without any commit |
| A5 | ◐ | **cloud-provider-kind**: pinned release binary instead of `go install …@latest` (slow, unpinned, failed on a proxy.golang.org error); document macOS/Windows needs `sudo` and port mapping; doctor checks it is running — *pinned v0.12.0 release binary done; macOS sudo handling open* | CI-002; the reason we run cloud-provider-kind is real LoadBalancer IPs, like a cloud |
| A6 | ☐ | **Gateway address module**: read the address from Gateway / LLMInferenceService status (same code on kind+cloud-provider-kind, EKS, OpenShift); verify it is reachable; on macOS use cloud-provider-kind's localhost mapping; `port-forward` only as a last resort, announced by doctor | `gateway-url.sh` uses `docker inspect kind-worker` + NodePort: Linux-only |
| A7 | ☐ | **`addons/<name>/vN/`** for optional components (Prometheus/Grafana first, for the monitoring tutorial), versioned and tested like envs | Some tutorials need extra components; installing them ad hoc breaks independence |
| A8 | ☐ | **Report upstream to KServe**: (1) installer applies LLMInferenceServiceConfigs before the webhook answers (CI-001); (2) v0.18.0–v0.19.0 default scheduler image `llm-d-inference-scheduler:v0.7.1` no longer pullable (CI-004) | Our workarounds in `envs/kind-kserve/v1/setup.sh` (formerly `kind-llmisvc/v1`) should become unnecessary |
| A9 | ☑ | Verify the scheduler image workaround (`llm-d-router-endpoint-picker:v0.9.0` under KServe v0.18 config) actually works | Verified: `llmisvc-anatomy` passed 16/16 including a completion through the Gateway ([run](https://github.com/Jooho/kserve-tutorials/actions/runs/44412518216)) |

## B. "Works in CI, fails on my machine"

| # | Status | Item | Why / evidence |
|---|---|---|---|
| B1 | ◐ | **`./tut doctor`**: tools and versions, Docker CPU/memory, architecture, disk, proxy, cloud-provider-kind running; runs in setup, in the UI and in CI — *done: toolkit / host / environment sections, in `make setup` and CI; open: UI panel, proxy check* | Readers' machines differ from the CI runner (4 CPU / 16 GiB, linux/amd64) |
| B2 | ☑ | **Pinned tool versions** (kind, kubectl, helm, cloud-provider-kind) per environment (`envs/*/tools.env`), installed into `.tools/<tool>/<version>/`, used by CI and locally; toolkit separate in `.venv` | Same tools in CI and on laptops |
| B3 | ☐ | **Supported platforms** declared per env (`linux/amd64`, `darwin/arm64`, …) and checked by doctor; find out whether the vLLM CPU image runs on Apple Silicon | CI only covers linux/amd64; GitHub macOS runners cannot run Docker |
| B4 | ☐ | **Lint: no kind-specific commands in tutorials** (`docker inspect`, `kind-worker`, `kind …`) — only in envs/lib | Keeps tutorials portable (A2) |
| B5 | ☐ | **Lint: every `kubectl wait` has `--timeout`; no long `sleep`** | authoring.md § Writing good steps |
| B6 | ☐ | **CI scenario: existing cluster** (provision first, then run the tutorial in bring-your-own mode) | Tests A2 |
| B7 | ☑ | **CI scenario: run twice on the same cluster** (catches `AlreadyExists`, leftover state, partial re-runs from the UI) | Local runs are rarely on a clean cluster |
| B9 | ☑ | **Personal settings without `export`**: `.tut.env` (`make config CLUSTER=tut`), loaded by `./tut`, the UI and every setup step; shell > file > default | A reader with an existing `kind` cluster had to remember `export KIND_CLUSTER_NAME=…` in every terminal |
| B15 | ☑ | **Translations on request only**: `make precommit TRANSLATE=1` drafts every missing/outdated translation with `TUT_AI`; plain `make precommit` lists them (`./tut translation todo`); `./tut sync` never translates (deterministic, offline) | Translating inside sync would make it slow, random and dependent on an AI login, and would chase unfinished English |
| B16 | ☑ | **Sanitise README HTML in `./tut ui`** (done: `ui/sanitize.py` allowlist + Content-Security-Policy, `/files/` sandboxed): the page renders `md.markdown` output as raw HTML, so a `<script>` or `onerror=` in a README runs with the UI's token and can drive the shell WebSocket — just by opening an untrusted branch | Review of tools/ (2026-11-21), `ui/server.py` api_tutorial |
| B17 | ☐ | **`./tut draft` outside-change check**: files already dirty before the run are not compared after it, and any `catalog/collections/*` or the root README passes; compare content hashes and allow only the named collection | Review of tools/ (2026-11-21), `draft.changed_outside` |
| B18 | ☐ | **D012 on continued lines**: rules match line by line, so `kubectl delete x \` + `--ignore-not-found` on the next line is flagged (an error for stable tutorials); join `\`-continued lines first | Review of tools/ (2026-11-21), `lint.py` NOT_IDEMPOTENT |
| B14 | ☑ | **AI translation drafts with the user's own AI CLI**: `TUT_AI=claude|copilot|codex|cmd:…` (formerly `TUT_TRANSLATOR`), `./tut translation draft <id> <lang>` / `--all`, mechanical check before writing, `reviewed=no` until marked | `init` only copied English and looked like a translation; translating by hand does not scale |
| B13 | ☑ | **`./tut list` scales and `./tut` has Tab completion**: one line per tutorial fitted to the terminal (`./tut show <id>` for details, `--collection` in reading order); completion of subcommands, options, ids, tags, collections, versions from the parser itself (`eval "$(./tut completion)"`, automatic in the UI terminal) | With dozens of tutorials the multi-line list was unreadable; ids and tags are hard to remember |
| B12 | ☑ | **CLI that explains itself**: `./tut list` shows title, versions, env/lib, translation state, collections, tags (+ `--tag`, `--status`, `--json`); `./tut translation` shows every translation's state and the next command; `translation draft` starts one (AI); typos in ids get a suggestion; the UI says when a translation is behind the English source | `./tut list` printed one terse line and gave no hint what an id is or what to do next |
| B11 | ☑ | **Notebook-style stepping**: ▶ Next / Shift+Enter runs the selected step and selects the next one on success; click a step to select it; Shift+Enter inside the terminal stays with bash | Readers want to go one step at a time, like Jupyter, rather than run to the end |
| B10 | ☑ | **UI re-running and terminal**: ⏵ Continue / To here start at the first step not passed; passed steps show “↻ Run again · time”; `once` steps ask first; Tab completion (kubectl/helm/kind) and aliases `k`, `kc <ns>` in the UI terminal; next block sent only at a prompt as a short `__tut_run <n>` (no echoed internals, tested through a terminal emulator); full-width document, terminal at the bottom or right, collapsible list, text size A−/A+ (remembered per browser) | Re-running from the top re-ran the 10-minute setup; readers wanted kubectl completion |
| B8 | ☐ | **UI "Report a problem"** button: opens an issue prefilled with doctor output, failing block and output tail | Local failures CI cannot see must come back to the repository |

## C. Content and KServe versions

| # | Status | Item | Why / evidence |
|---|---|---|---|
| C1 | ☐ | **Decide how tutorials handle version-specific content** (separate tutorial versions, per-version blocks, or `versions.tested` ranges + new tutorial) | KServe master removed the scheduler's tokenizer sidecar; `llmisvc-anatomy` explains and verifies three containers |
| C2 | ☐ | Update `llmisvc-anatomy` for the next KServe release once C1 is decided (the canary will flag it) | Same as C1 |
| C3 | ☑ | Korean translation of `llmisvc-anatomy` | AI draft reviewed and marked; kept up to date with the English (PR #24) |
| C5 | ☑ | **Catalog**: tags registry (`catalog/tags.yaml`, G001 with suggestions), collections as owned reading paths resolved per KServe version (archived → replacement), sidebar views Groups / Collections / All with a version filter in each, version × tutorial matrix, tag filter, search; CODEOWNERS generated from `owners` | One flat list could not show paths, versions or tags as tutorials multiply |
| C4 | ☐ | **Migrate the remaining tutorials** (legacy repository + local ones) with docs/migration-guide.md, one PR each, done with local Claude Code | The point of the repository |

## D. Process and publishing

| # | Status | Item | Why / evidence |
|---|---|---|---|
| D1 | ☑ | Get PR #1 green, squash, run the final test | Green on [run 44412518216](https://github.com/Jooho/kserve-tutorials/actions/runs/44412518216) after 4 attempts (CI-001…004); merged |
| D13 | ☐ | Turn on "Require review from Code Owners" and required checks (`check`, `e2e`) for `main` — repository setting | CODEOWNERS only takes effect then; PR #3 was merged before its e2e finished |
| D2 | ☐ | After the first green run: `llmisvc-anatomy` → `stable`, freeze `envs/kind-kserve/v1` and `lib/llmisvc/v1` | T007/L004 |
| D3 | ☐ | **Ready for the kserve organization**: Apache-2.0 LICENSE, DCO sign-off rule + check, no hard-coded `Jooho` URLs (derive from `github.repository`), CODEOWNERS, pinned public images only | Possible move under `kserve/` later |
| D4 | ☐ | Bump GitHub Actions versions (Node 20 deprecation warnings on checkout, setup-python, upload-artifact, deploy-pages) | CI annotations |
| D5 | ☐ | Site generator: Material for MkDocs end of life 2027-05-05 → evaluate Zensical | RFC open question 7 |
| D6 | ☐ | Record verification results (last passed per tutorial × version) and show them on the site and in the UI | RFC open question 3 |
| D7 | ☐ | GPU tutorials: lint-only in CI plus a recorded manual verification, or a self-hosted GPU runner | RFC open question 4 |
| D8 | ☐ | Group CI jobs by env+version if the weekly matrix gets slow | RFC open question 5 |
| D9 | ◐ | Release process: `main` → `stable` fast-forward after the full matrix passes, `YYYY.MM.N` tags, Makefile (docs/release.md) | Readers should only see verified states |
| D10 | ☐ | Protect the `stable` branch (block force push/deletion, only GitHub Actions may push) — repository setting, needs a maintainer | docs/release.md § Repository settings |
| D11 | ☐ | Rename the tutorial status `stable` (e.g. `ready`) so it is not confused with the `stable` branch | Same word, two meanings |
| D12 | ☐ | Optionally start a dry-run release automatically when the weekly run is fully green | Less manual work once the release flow is trusted |

## E. One engine, many projects (KServe, Kuadrant, llm-d, vLLM, ...)

**Decision (2026-11-20): KServe only for now.** E1 is done and stays (it
costs nothing and keeps the engine free of the product name). Everything
else here waits until a second project actually exists; building it earlier
would add structure nobody uses.

Plan when it starts: engine (`tut`) / platform parts (shared kind, ingress,
cert-manager, helpers) / one content repository per project with its
`project.yaml`, dropped into `engine/projects/<id>`. Cross-project tutorials
are out of scope.

Design notes from the discussion, so it does not start from zero:

- The gap is reproducibility, not code layout. "Verified on KServe v0.18.0"
  really means "v0.18.0 plus whatever its installer pulled that day";
  nothing records cert-manager, Gateway API, Envoy, LWS, Kubernetes versions
  (see E7, which applies to KServe today).
- Model: **component** (`platform/components/<name>/`: `install.sh
  --version X`, `check.sh`, tested versions) → **stack / BOM** per project
  (product version → pinned component versions) → **tutorial** picks the
  product version and rarely overrides one component → **resolver** in the
  engine computes the full lock, records it in the report, and uses its hash
  as the cluster marker (same → reuse, different → add or stop).
- An upstream installer (KServe's `hack/`) can stay a component that the
  stack delegates to, as long as the installed versions are read back and
  locked.
- Questions to decide first: who pins dependency versions (tutorial vs stack;
  stack recommended); who maintains the compatibility table (read upstream's
  vs our own); is bring-your-own-cluster near (then A1 contract + check
  first); how much cluster reuse matters locally; how "verified" is shown.

| # | Status | Item | Why / evidence |
|---|---|---|---|
| E1 | ☑ | **`project.yaml`**: product name, title, intro, `version_var`, canary upstream, glossary; `versions:` instead of `kserve:` in tutorial.yaml and env profiles; `--version` (alias `--<id>-version`); `./tut project`; P001 | The engine had "KServe" in 15 files (135 places) |
| E2 | ⏸ | **`ENGINE_ROOT` / `PROJECT_ROOT`**: split the single `REPO_ROOT` (tools/schema vs tutorials/envs/lib/catalog/project.yaml); same directory for now | Needed before the engine can live in its own repository |
| E3 | ⏸ | The env marker (`kube-system/tut-env`, fields `profile`, `kserve_version`) is read by the engine (`ui/server.py` env check, `doctor.py`); let the env profile declare how to read "what is installed" | Env knowledge in the engine; another project's env writes other fields |
| E4 | ⏸ | `.github/scripts/diagnose.sh` dumps KServe resources (InferenceService, LLMInferenceService, namespace `kserve`); move it to the env (`envs/<env>/diagnose.sh`) | Same; found while doing E1 |
| E5 | ⏸ | `mkdocs.yml` `site_name` and the language list (`LANGS = en, ko`) are per project; generate/read them from `project.yaml` | Same |
| E6 | ⏸ | `platform/` for parts every project shares; engine repository; CI clones the engine at a pinned version; UI project switcher | Steps 3–5 of the plan |
| E7 | ☐ | **Record what was installed** (KServe today): after setup, read the versions actually running (KServe, cert-manager, Gateway API, Envoy Gateway, LWS, Kubernetes, kind) and put them in the run report and the UI env status | A green run cannot say which dependency versions it proved; first step towards a lock |
