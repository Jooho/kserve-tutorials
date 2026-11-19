# RFC 0001: Repository structure for versioned, independently verifiable tutorials

| | |
|---|---|
| Status | Draft — open for review |
| Author | @Jooho |
| Created | 2026-11-18 |

## 1. Summary

Each tutorial becomes a self-contained unit that declares **which KServe
versions it supports** and **which environment profile it needs**. Its
`README.md` is both the document people read and the test CI runs. Shared setup
lives in **versioned, frozen environment profiles**, so a change to shared setup
can only reach the tutorials that opt into the new version. A small set of
numbered rules, enforced by `./tut lint` and by actually running every
tutorial, keeps documents, code and versions from drifting apart.

## 2. Motivation

The first repository (now [`Jooho/kserve-tutorials-legacy`](https://github.com/Jooho/kserve-tutorials-legacy)) showed the problems this design
targets. Each one was found by reading the files, not by any check:

| Problem | Example |
|---|---|
| Copies drift | The YAML shown inline in `llmisvc/01-anatomy/README.md` is missing `VLLM_ADDITIONAL_ARGS`, which the real `llmisvc-cpu.yaml` has. |
| Indexes drift | The root README lists one tutorial; the `llmisvc` series is missing. |
| Versions are scattered | KServe v0.17.0 in one tutorial, v0.18.0 in another, each written in scripts and in both EN and KO text. |
| Setup is not pinned | `00-setup` clones kserve **master** and then installs v0.18.0; the ensemble script fetches the installer from `refs/heads/master`. |
| Hidden coupling | `01-anatomy` says "leave everything as is for 02"; later tutorials depend on state the reader may not have. |
| Dead references | `00-setup` talks about demos 00–05 and `03` links to `04-autoscaling`; neither exists. |
| Translations drift silently | Some tutorials have KO, some do not; nothing says whether a KO file matches its EN source. |
| Two structures | `scripts/` + `docs/` in one tutorial, numbered READMEs with inline bash in the other. |

More tutorials exist locally and will be added, and the repository is meant
for external readers. Without structure, every new tutorial multiplies these
problems.

## 3. Goals and non-goals

**Goals**

1. **Isolation.** A KServe change (for example, WVA being dropped) touches exactly
   the tutorials that use it, and each one can be kept, updated or archived on
   its own.
2. **Version mapping.** For any KServe version, we can say which tutorials work
   with it, because CI ran them.
3. **Docs as source.** What a reader runs is exactly what CI runs. No second copy.
4. **Rules first, AI second.** Correctness comes from deterministic checks; AI
   proposes changes that must pass the same checks.
5. **Easy to use.** A newcomer finds a tutorial for their KServe version, clones
   the repository and copies commands. Nothing else to install beyond the
   environment's prerequisites.
6. **Cheap to maintain.** No custom UI to build; a generated static site.

**Non-goals**

- Supporting every KServe version for every tutorial. A tutorial supports what
  it declares and CI proves.
- Running GPU tutorials in CI (see §6.4).
- A WYSIWYG editor or authoring UI.

## 4. Design

### 4.1 Units

| Unit | Where | Owns |
|---|---|---|
| **Tutorial** | `tutorials/<id>/` | Its README(s), manifests, scripts, images and `tutorial.yaml`. Nothing outside the directory. |
| **Environment profile** | `envs/<name>/v<N>/` | How to build a cluster for a range of KServe versions: `profile.yaml`, `setup.sh`, `teardown.sh`, `README.md`. |
| **Script module** | `lib/<name>/v<N>/` | Scripts shared by tutorials (`module.yaml` + `*.sh`). Versioned and frozen like profiles (§4.6). |
| **Tooling** | `tools/tut/`, `./tut` | The rules, the runner, the site generator. |

### 4.2 Layout

```text
.
├── tut                         # CLI entry point: ./tut lint | sync | run | ...
├── tutorials/
│   ├── _template/              # copy this to start a tutorial
│   └── <id>/
│       ├── tutorial.yaml
│       ├── README.md           # source of truth (English)
│       ├── README.ko.md        # translation (optional)
│       ├── manifests/          # real files, included into the README
│       └── images/
├── lib/<name>/v<N>/            # shared scripts, versioned
│   ├── module.yaml
│   └── *.sh
├── envs/<name>/v<N>/
│   ├── profile.yaml
│   ├── setup.sh                # idempotent
│   ├── teardown.sh
│   └── README.md
├── schema/                     # JSON schemas for tutorial.yaml and profile.yaml
├── tools/tut/                  # rules, runner, planner, site builder
├── tools/tests/                # tests for the rules themselves
├── docs/rfc/                   # design records like this one
└── .github/workflows/          # ci.yml, scheduled.yml, site.yml
```

### 4.3 `tutorial.yaml`

```yaml
id: llmisvc-anatomy                 # == directory name
title: {en: "...", ko: "..."}
summary: {en: "...", ko: "..."}
status: stable                      # draft | stable | deprecated | archived
series: {name: llmisvc-deep-dive, order: 1}   # navigation only
env: kind-llmisvc/v1                # a frozen profile (required for stable)
uses: [llmisvc/v1]                  # script modules, pinned
namespace: llmisvc-anatomy          # default: id
kserve:
  default: v0.18.0                  # what readers and PR CI use
  tested: [v0.18.0]                 # what the weekly CI runs
features: [llmisvc, gateway-api-inference-extension, epp-scheduler]
requires: {gpu: false, cpu: 4, memory: 16Gi}
langs: [en]
timeout_minutes: 60
owners: [Jooho]
deprecation:                        # deprecated / archived only
  reason: "..."
  last_supported_kserve: v0.17.1
  replacement: other-tutorial
```

`features` is what makes "which tutorials does this KServe change affect?" a
search instead of an investigation.

### 4.4 Versioning model: per tutorial, not per branch

A tutorial lists the KServe versions it supports. There are **no release
branches**.

Release branches (one per KServe version) were rejected because they tie
every tutorial to the same branch: a fix to one tutorial has to be
back-ported across branches, and a tutorial that only makes sense on one
version still has to exist, or be deleted, on every branch. Per-tutorial
declarations let each tutorial move at its own pace, and the catalog page
"By KServe version" is generated from them.

Readers use `kserve.default` unless they set `KSERVE_VERSION` themselves; the
generated setup block does `export KSERVE_VERSION="${KSERVE_VERSION:-<default>}"`.

### 4.5 Lifecycle

```text
draft ──► stable ──► deprecated ──► archived
```

| Status | Meaning | CI | Rules |
|---|---|---|---|
| `draft` | Being written | Runs on PR | D007 is a warning, any env allowed |
| `stable` | Recommended | PR + weekly + canary | Must use a frozen env (T007), must verify (D007) |
| `deprecated` | Still works, being replaced | PR + weekly + canary | Needs `deprecation.reason` |
| `archived` | Kept for reference, frozen | Not executed | Needs `deprecation.reason` and `last_supported_kserve` |

**Example: WVA is removed from KServe.** The canary run (§4.10) fails for the
WVA tutorial only and opens an issue for it. The owner either:

- **archives** it: `status: archived`, `deprecation.last_supported_kserve: v0.17.1`.
  The page shows a banner, the catalog stops listing it under newer versions,
  CI stops running it. One file changes.
- **rewrites** it for the replacement feature: a normal PR to that directory,
  which runs only that tutorial.

No other tutorial is touched in either case.

### 4.6 Environment profiles, script modules and blast radius

Shared setup and shared scripts are necessary (most tutorials need the same
cluster and the same helpers) and dangerous (one edit changes all of them).
Both are versioned the same way.

Shared setup is necessary (most tutorials need the same cluster) and dangerous
(one edit changes all of them). Profiles resolve this the way package managers
do:

- A profile is identified by `<name>/v<N>` and is **frozen** once a stable
  tutorial depends on it. `./tut lint --base` fails (E002) if a frozen profile
  is modified.
- To change setup, create `v<N+1>`, then move tutorials to it one PR at a time.
  Each PR runs only the tutorial being moved.
- A profile receives the KServe version as an input and checks out KServe
  **at that tag**. It never uses master.
- A profile pins the CLI tools it needs (`tools.env`: kind, kubectl, helm,
  cloud-provider-kind). They are installed into `<repo>/.tools/<tool>/<version>/`
  — side by side, so two profiles can pin different versions — and put on
  `PATH` only by the tutorial's setup step. The toolkit itself (`make setup`)
  is a separate `.venv`. Docker is a user prerequisite that `./tut doctor`
  checks and nobody installs.
- `setup.sh` is idempotent and records what built the cluster (a `tut-env`
  ConfigMap). It reuses a matching cluster and refuses to modify a cluster
  built by a different profile or version.

What a change can reach:

| Change | Tutorials executed in the PR |
|---|---|
| `tutorials/<id>/**` | `<id>` |
| `envs/<name>/v<N>/**` | Tutorials whose `env` is `<name>/v<N>` (only allowed while not frozen) |
| `lib/<name>/v<N>/**` | Tutorials that list `<name>/v<N>` in `uses` (only allowed while not frozen) |
| anything else | None; lint and unit tests still run, the weekly run covers the rest |

**Script modules** (`lib/<name>/v<N>/`) apply the same rule to reusable
scripts. A tutorial declares the modules it calls (`uses: [llmisvc/v1]`) and
calls them as `"$TUT_LIB/llmisvc/v1/gateway-url.sh"`. A script exists once, so
it is reused instead of copied; it is pinned, so improving it means a new
module version that tutorials adopt one at a time. Lint enforces that every
call is declared (L002) and that frozen modules do not change (L003). Readers
still see what a script does: the README can include it with `tut:include`,
and the local UI shows it under the block that calls it.

This mapping is tested in `tools/tests/test_rules.py`.

### 4.7 Independence rules

1. **No hidden state between tutorials.** Every tutorial starts from its
   environment profile and creates everything else it needs in its own
   namespace. If tutorial B builds on what tutorial A created, B re-creates it
   (by copying A's manifest into B; see rule 3).
2. **Series are navigation only.** `series` orders tutorials on the site; it
   never implies shared state.
3. **Share through modules, not through other tutorials.** A tutorial never
   reads another tutorial's files. Scripts worth sharing move into a
   versioned module under `lib/`; manifests that two tutorials need are copied
   (they are content that may diverge). `tut:include` can reference the
   tutorial's own files and its declared modules (D005).
4. **Own namespace.** Defaults to the tutorial id, so tutorials can run on the
   same cluster without colliding.
5. **Cleanup leaves the environment as it found it.** The cluster belongs to
   the profile; the namespace belongs to the tutorial.

### 4.8 Executable documents

The English `README.md` is the source. Two constructs make it executable and
verifiable while staying plain Markdown on GitHub.

**Shell block roles**

| Fence | Executed | Purpose |
|---|---|---|
| ` ```bash run ` | yes | A step the reader performs |
| ` ```bash verify ` | yes, must succeed | An assertion: `kubectl wait`, `test`, a request that must return a valid answer |
| ` ```bash verify retry=N delay=S ` | yes, retried | Something that becomes true eventually |
| ` ```bash cleanup ` | always at the end, also after failures | Undo what the tutorial created |
| ` ```bash skip ` | no | Interactive (`watch`), optional or illustrative commands |

Non-shell blocks (`yaml`, `text`, ...) are never executed. Every shell block
must have exactly one role (D001), so nothing is executed by accident and
nothing is silently left untested.

**Runner semantics** (`./tut run <id>`): all `run`/`verify` blocks are joined in
document order into a single `bash -Eeuo pipefail` script, so variables and
`cd` carry over exactly as in a reader's terminal. On failure it reports the
README line of the failing block (`tutorials/<id>/README.md:240 (verify 9/16)`),
runs the cleanup blocks, and writes a JSON report for CI.

**Generated regions** are owned by `./tut sync` and never edited by hand:

| Region | Content |
|---|---|
| `<!-- tut:header -->` | Status, tested KServe versions, env link, GPU, language links, deprecation banner |
| `<!-- tut:setup -->` | The first runnable block: KServe version, namespace, env `setup.sh` |
| `<!-- tut:include <path> -->` | A file from the tutorial directory, as a code block |
| `<!-- tut:catalog -->` | The catalog (root README) |

Lint fails when a region is stale (D002), so a manifest and the copy shown in
the document can no longer disagree.

### 4.9 Rules

Errors fail CI; warnings are printed. The authoritative list is the docstring
of `tools/tut/lint.py`.

| Code | Rule |
|---|---|
| T001 | `tutorial.yaml` exists and matches `schema/tutorial.schema.json` |
| T002 | `id` equals the directory name |
| T003 | `env` references an existing profile |
| T004 | `kserve.default` is in `kserve.tested` |
| T005 | Every tested version is supported by the profile (`kserve.min`/`max`) |
| T006 | `deprecated`/`archived` have a `deprecation` block |
| T007 | `stable` tutorials use a frozen profile |
| D001 | Every shell block has exactly one role |
| D002 | Generated regions are up to date |
| D003 | No hard-coded KServe version outside generated regions (escape: `<!-- tut-allow-version -->`) |
| D004 | Relative links and images resolve |
| D005 | `tut:include` stays inside the tutorial directory |
| D006 | `tut:setup` exists and precedes every other run/verify block |
| D007 | Non-draft tutorials have at least one `verify` and one `cleanup` block |
| D008 | Every language in `langs` has a README |
| D009 | Markup is well formed (fences, regions, fence tokens) |
| D010 | Translations carry a source marker; a stale marker is a warning |
| D011 | Translations have the same sequence of shell block roles as the source |
| M001 | Container images are pinned (no `latest`, no missing tag) |
| L001 | Modules are valid and their scripts executable |
| L002 | Every `lib/<module>` call is declared in `uses`, and declared modules exist |
| L003 | Frozen modules are not modified |
| L004 | `stable` tutorials use frozen modules |
| L005 | Unused module (warning) |
| E001 | Profiles are valid and have executable `setup.sh`/`teardown.sh` and a README |
| E002 | Frozen profiles are not modified |
| E003 | Unused profile (warning) |

The rules have their own tests (`tools/tests/`), so changing a rule is a
reviewed, tested change too.

### 4.10 CI

| Workflow | Trigger | Does |
|---|---|---|
| `ci.yml` | pull request, push to main | lint (`--base`), rule tests, site build; then **executes only affected tutorials** with their `kserve.default` |
| `scheduled.yml` | weekly + manual | **Full matrix:** every runnable tutorial × every `kserve.tested` version. **Canary:** the latest KServe release against every stable/deprecated tutorial that does not list it yet. Failures open or update one issue per tutorial. |
| `release.yml` | manual (`make release`) | Full matrix at one commit of `main`; if everything passes, fast-forwards `stable`, tags `YYYY.MM.N`, publishes the site |
| `site.yml` | push to `stable`, called by `release.yml` | Builds and publishes the site to GitHub Pages |

The canary answers "when do I need to update?" before readers notice: when
KServe ships a release, each tutorial either passes (add the version to
`tested`) or gets an issue.

### 4.11 Translations

- English is the source; other languages are translations of it.
- A translation starts with `<!-- tut-translation source=README.md sha=<hash> -->`,
  written by `./tut translation mark <id> <lang>` after translating.
- The hash ignores generated regions, so `./tut sync` alone never makes a
  translation stale.
- Stale translation → warning (D010). The block structure must match → error
  (D011), because a translation that skips or adds a step is wrong, not just
  old.
- CI only executes the English README. Code blocks in translations are
  expected to be identical except for comments.

### 4.12 Publishing

The site is MkDocs Material, generated, not written: `./tut site` mirrors
`tutorials/` and `envs/` (so relative links work), turns `README.md` /
`README.ko.md` into `index.md` / `index.ko.md` for the language switcher, and
generates the catalog and the "By KServe version" page from `tutorial.yaml`.
GitHub remains a first-class way to read every tutorial.

### 4.13 Local runner UI

Copying commands from a page into a terminal is the main friction for
readers and for authors testing their own tutorials. `./tut ui` starts a
local web application (127.0.0.1 only, protected by a token printed at
start-up) that:

- lists tutorials, filtered by the KServe version selected at the top;
- renders the README with a card per block: ▶ Run, ⏭ Run to here,
  ▶ Run all, ■ Stop, 🧹 Cleanup; the state of each block (running, passed,
  failed, stopped) is shown on the card and in the terminal;
- runs blocks in one real bash per tutorial on the user's machine, so they
  reach the user's Docker / Kind / kubectl, and variables and `cd` carry over;
- shows that shell in an embedded terminal (xterm.js, vendored so it works
  offline), where the user can also type;
- shows the environment status (no cluster / built by which profile and
  version) before the setup step runs;
- expands module scripts under the block that calls them.

It uses the same parser as lint and CI, and the same block semantics as the
runner (verify blocks run with `set -Eeo pipefail` and honour
`retry`/`delay`), so passing in the UI and passing in CI mean the same thing.
The UI is a convenience for the reader; CI remains the authority.

Why not Runme: it runs Markdown cells well, but has no notion of a check that
must pass, no per-tutorial KServe version or environment, and its browser mode
is a full VS Code (code-server). Those are the parts this project needs, so
the UI is built on the existing `tut` parser instead.

### 4.14 Release channel

Two branches: `main` for development and `stable` for readers. A release
promotes a commit of `main` to `stable` (fast-forward only) after the full
matrix — every runnable tutorial × every tested KServe version — passes at
that commit, and tags it `YYYY.MM.N`. The site is published from `stable`.
Because `stable` is always an earlier commit of `main`, there are no
back-ports, unlike the per-KServe-version branches rejected in §4.4.
Details: docs/release.md.

### 4.15 AI-assisted maintenance

AI works on top of the rules, never instead of them:

- `AGENTS.md` (imported by `CLAUDE.md`) is the entry point for every coding
  agent: commands, hard rules, and which document to read for which task
  (`docs/authoring.md`, `docs/ci-playbook.md`, `docs/migration-guide.md`).
- Knowledge accumulates in the repository, not in a session: whoever fixes a
  failure adds a lesson to `docs/authoring.md § Rules learned from CI`, and
  promotes it to a lint rule with a test when it can be checked mechanically.
- A canary issue is a precise task: tutorial, KServe version, failing block and
  log. An agent can propose a fix PR; that PR passes lint and executes the
  tutorial like any other.
- Translations can be drafted by an agent; D011 and the marker keep them honest.

## 5. Alternatives considered

| Alternative | Why not (for now) |
|---|---|
| One branch per KServe version | Couples all tutorials; back-ports for every fix (§4.4). |
| Shared, unversioned setup (`00-setup`) | Any edit changes every tutorial at once; the reason for §4.6. |
| Scripts as the source, docs describe them | Two sources again; readers run something other than what CI runs. |
| [Runme](https://runme.dev) / mdsh to execute Markdown | Runs cells well, but lacks verify semantics, version/env awareness and a light browser UI (§4.13). |
| Copying shared scripts into each tutorial | Independence without reuse: every fix has to be repeated. Versioned modules give both (§4.6). |
| Jupyter / Quarto | Good for Python-first content; most steps here are `kubectl` and YAML, and notebooks diff poorly in review. |
| A hosted web UI | Commands must run where the user's cluster is; the UI is local (§4.13). The static site stays for reading. |

## 6. Open questions

1. **License.** Suggest Apache-2.0 for code (matches KServe) and CC BY 4.0 for
   prose. Needs a decision before the repository is promoted.
2. ~~**Repository.**~~ **Decided:** the old repository was renamed to
   `Jooho/kserve-tutorials-legacy` and this repository starts fresh under the
   original name, which also suits a later move under the `kserve`
   organization (GitHub keeps redirects on transfer).
3. **Recording verification.** The weekly run knows when each tutorial last
   passed per version. Publish as a JSON file on the site, or open a bot PR
   that updates a `verified` field? The JSON approach avoids commit noise.
4. **GPU tutorials.** Not runnable on hosted runners. Options: `requires.gpu`
   tutorials are lint-only plus a manual `verified` record, or a self-hosted
   GPU runner later.
5. **CI cost.** Each tutorial builds its own cluster (isolation over speed).
   If the weekly matrix gets slow, group tutorials that share a profile and
   version into one job; the namespace rule (§4.7) makes this safe.
6. **Profile granularity.** Add-ons used by a few tutorials (Prometheus,
   KEDA, ...) — separate profiles (`kind-llmisvc-monitoring/v1`) or installed by
   the tutorial itself? Proposal: by the tutorial, until three tutorials need
   the same add-on.

7. **Site generator lifetime.** Material for MkDocs announces end of life on
   2027-05-05, with Zensical as its successor (reads `mkdocs.yml`). The site is
   generated by `./tut site`, so switching only touches `mkdocs.yml` and
   `site.yml`. Revisit before 2027-05.

## 7. Rollout

1. **Skeleton** (this change): tooling, rules + tests, CI, site, template,
   `kind-llmisvc/v1`, and `llmisvc-anatomy` migrated as the reference.
2. **First green run** on GitHub Actions; adjust timeouts and the profile if
   needed (a profile is not frozen until a stable tutorial passes on it).
3. **Migration** of the remaining tutorials, one PR each, following
   `docs/migration-guide.md` (done locally with Claude Code).
4. **Publish**: license, Pages, a pointer from `kserve-tutorials-legacy` to this repository.
5. **Canary** enabled; first KServe release handled through the issue flow.
