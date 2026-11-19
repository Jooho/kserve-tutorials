# Authoring tutorials

Read this before writing or changing a tutorial. The design behind these rules
is in [RFC 0001](rfc/0001-repository-structure.md); the mechanical rules are
enforced by `./tut lint` (codes in brackets).

## 1. Shape of a tutorial

```text
tutorials/<id>/
  tutorial.yaml     metadata (schema/tutorial.schema.json)
  README.md         the document AND the test (English, the source)
  README.ko.md      optional translation
  manifests/        real files, shown with tut:include
  images/
```

Start with `make new T=<id> [TITLE="..."] [OWNER=<github-handle>]` (or
`./tut new <id>`): it copies `tutorials/_template/`, fills in id and namespace,
and starts as `status: draft`, English only (translate later with
`./tut translation draft`).

## 2. Blocks

| Fence | Meaning |
|---|---|
| ` ```bash run ` | a step; executed |
| ` ```bash verify ` | a check; executed with `set -Eeo pipefail`, must succeed |
| ` ```bash verify retry=N delay=S ` | a check that becomes true eventually |
| ` ```bash cleanup ` | undo; always executed at the end |
| ` ```bash skip ` | shown only: interactive or optional commands |

Every shell block has exactly one role [D001]. The first runnable block is the
generated `<!-- tut:setup -->` region [D006]. Files are shown with
`<!-- tut:include path -->`, never pasted [D002, D005].

## 3. Writing good steps

- **Write for a fresh machine.** Assume nothing but the environment profile.
  Create everything else in the tutorial's own namespace (`$NS`).
- **Wait, don't sleep.** Use `kubectl wait --for=... --timeout=...` or
  `verify retry=N delay=S`. Never `sleep 60` hoping it is enough.
- **Every wait has an explicit timeout**, sized for a CPU-only CI runner
  (cold image pulls, model download). Put the expected duration in the text.
- **Verify what the reader is meant to learn**, not just that a command ran:
  counts, names, field values, a request that returns a real answer. If the
  prose says "you should see X", a `verify` checks X.
- **Every step is safe to run twice** [D012]. Readers re-run steps after a
  failure, in a new shell, or with "To here"; CI runs every tutorial twice in
  the same cluster (`./tut run --twice`). Use `kubectl apply`,
  `kubectl create … --dry-run=client -o yaml | kubectl apply -f -`,
  `helm upgrade --install`, `kubectl delete … --ignore-not-found`, `>` not
  `>>`. A step that truly cannot repeat is fenced ` ```bash run once `: CI
  runs it once and the UI asks before running it again.
- **No UI aliases in tutorials** [D013]: `k` and `kc` exist only in the UI
  terminal; tutorials always write `kubectl`.
- **Interactive commands** (`watch`, `port-forward` in the foreground,
  editors, `kubectl exec -it`) are `skip`, followed by a non-interactive
  `verify` equivalent when it matters.
- **Pin images** [M001]. No hard-coded KServe versions; use `$KSERVE_VERSION` [D003].
- **Cleanup** deletes what the tutorial created (its namespace at least),
  never the cluster: the cluster belongs to the environment [D007].
- Keep `timeout_minutes` in `tutorial.yaml` realistic: setup + all waits.

## 4. Shared parts

| Need | Use | Declare in tutorial.yaml |
|---|---|---|
| A cluster with KServe | an environment profile `envs/<name>/vN/` | `env:` |
| A helper script used by several tutorials | a script module `lib/<name>/vN/` | `uses:` |

- Check existing parts before creating one.
- Calls look like `"$TUT_LIB/llmisvc/v1/gateway-url.sh"` and must be declared [L002].
- `frozen: true` parts never change [E002, L003]. To change one, copy it to
  `vN+1`, change the copy, move tutorials over one PR at a time.
- A stable tutorial may only use frozen parts [T007, L004].
- **Personal settings** (cluster name, skipped tools) live in `.tut.env`,
  loaded by `tools/local-config.sh` in `./tut` and in every generated setup
  step. Never ask readers to `export` something in prose; add a setting.
- **Tools belong to the environment.** An environment pins the CLI tools it
  needs in `tools.env`; its `setup.sh` installs them into `.tools/` and the
  generated setup block puts them on `PATH` for that shell only. Tutorials
  never install tools or assume system ones. Docker is a user prerequisite,
  checked by `./tut doctor`, never installed.
- **Installation robustness belongs in the environment, not in tutorials.**
  If a tutorial needs a retry or a readiness wait because the platform was not
  really ready, fix the environment profile.

## 5. Groups, tags and collections (catalog/)

- **Group** (`group:` in tutorial.yaml, one per tutorial): what kind of
  tutorial it is — `llmisvc`, `inferencegraph`, ... from `catalog/groups.yaml`
  [G003]. The UI's **Groups** view lists every tutorial once under its group
  and opens it on its own (standalone). Add a group to `catalog/groups.yaml`
  only if none fits.

- **Tags** make tutorials findable (search, filter in the UI, site). Use only
  tags listed in `catalog/tags.yaml` [G001]; lint suggests the closest one for a
  typo. If no tag fits, add one to `catalog/tags.yaml` in the same PR, with a
  group (`feature`, `topic`, `level`) and a one-line description. Prefer
  reusing a tag over adding a near-duplicate. Give every tutorial one `level`.
- **Collections** (`catalog/collections/<id>.yaml`) are learning paths: **two
  or more** tutorials in order [C005: with one member a collection is not shown
  yet]. They list tutorial ids; tutorials never refer to collections and stay
  independent. A tutorial may be in several collections or in none. Opened from
  the **Collections** view, a tutorial runs as a step of the path (shared steps
  already done are hidden, the collection's `vars` are shared).
  - Order is the list order — no order numbers to renumber.
  - Each collection has `owners`; they review every change to it (generated
    `.github/CODEOWNERS`). To add your tutorial to someone's path, edit the
    list in your PR and let them review.
  - Members must exist [C002] and appear once [C003]. When you archive a
    member, give it a `deprecation.replacement` or readers hit a dead end
    [C004]; the UI and site show the replacement in its place automatically.
- **Owners**: `owners` in `tutorial.yaml`, collections, env profiles and lib
  modules are GitHub handles. `./tut sync` writes `.github/CODEOWNERS` from them
  (and `catalog/maintainers.yaml` for everything else) [O001]; never edit it.

## 6. Lifecycle

`draft` → `stable` (CI passed, parts frozen) → `deprecated` (still works,
being replaced) → `archived` (kept, not run). Deprecating or archiving needs a
`deprecation` block [T006] and changes only that tutorial.

## 7. Translations

`README.md` is the source. `<id>` is the tutorial's directory name.

**With an AI CLI** you are logged in to (Claude Code, GitHub Copilot CLI,
Codex CLI, or any command) — no API keys in this repository:

```bash skip
export TUT_TRANSLATOR=claude                # or copilot, codex, cmd:<command>
./tut translation draft <id> ko             # one tutorial
./tut translation draft --all ko            # every missing or outdated translation
#   review the Korean text (git diff), fix what reads badly
./tut translation mark <id> ko              # only after a person or agent reviewed it
```

The AI only returns text; a program checks it before anything is written: code
blocks, commands, generated regions, HTML comments and link targets must be
unchanged (comments inside code may be translated). A rejected draft is kept in
`build/translations/` for inspection and nothing changes. An accepted draft is
marked `by=<tool> reviewed=no`: lint warns, the UI tells readers it is an AI
translation, and `mark` turns it into a reviewed one.

**Rejected or no AI:** start from the rejected output in `build/translations/`,
or copy `README.md` to `README.ko.md`; translate prose and code comments, keep
the code and regions exactly; then `mark` (it also adds `ko` to `langs`).

`./tut translation` shows every translation's state and the next step. A
translation has the same shell blocks in the same order [D011]. When README.md
changes later, lint warns that the translation is behind [D010] and the UI shows
it to readers. Translation lag never blocks English changes or releases.

## 8. Before you open a PR

```bash skip
make precommit               # ./tut sync, then lint + tests + site (CI checks the same)
./tut run <id> --dry-run     # read what CI will execute
./tut run <id>               # or step through it with ./tut ui
```

## 9. Rules learned from CI

Each entry: what happened → the rule → evidence. Add one whenever you fix a
failure a rule could have prevented (see AGENTS.md). Promote it to lint when it
can be checked mechanically.

### CI-001 "Available" is not "ready to use"
- **What happened:** KServe's installer applied `LLMInferenceServiceConfig`s
  right after the controller Deployment was Available; the validating webhook
  was not accepting connections yet (`connection refused`), so setup failed.
- **Rule:** an environment's setup must end with a readiness gate that
  exercises the platform (webhooks answer, CRDs established), not only
  Deployment availability. Retries for platform installs live in the
  environment profile.
- **Evidence:** [PR #1, first e2e run](https://github.com/Jooho/kserve-tutorials/actions/runs/44400612336).

### CI-002 Downloads fail; retry installs
- **What happened:** building `cloud-provider-kind` failed on a
  `proxy.golang.org` stream error.
- **Rule:** anything that downloads during setup is retried (installer
  attempts, pulls). A single network error must not fail a tutorial.
- **Evidence:** [PR #1, second e2e run](https://github.com/Jooho/kserve-tutorials/actions/runs/44401972251).

### CI-003 A failure without evidence cannot be fixed
- **What happened:** the LLMInferenceService never became Ready, but cleanup
  and teardown deleted everything before anyone could look.
- **Rule:** CI runs tutorials with `--keep-on-failure` and dumps diagnostics
  (pods, events, logs) before tearing down. When you add a new kind of
  resource, make sure `.github/scripts/diagnose.sh` would show it.
- **Evidence:** same run as CI-002.

### CI-004 Upstream images disappear
- **What happened:** the LLMInferenceService never became Ready because the
  EPP scheduler image from KServe's own default config,
  `ghcr.io/llm-d/llm-d-inference-scheduler:v0.7.1`, stopped being publicly
  pullable (ghcr.io 403 on the anonymous token). llm-d renamed it to
  `llm-d-router-endpoint-picker`. Every KServe release up to v0.19.0 was
  affected for every user, not only CI.
- **Rule:** a published release can break without any change on our side;
  that is what the weekly run is for. Work around platform breakage in the
  environment profile (documented as a known issue with the upstream fix to
  watch), never in individual tutorials. Diagnostics must show image pull
  errors (they did: `ImagePullBackOff` + the 403 in events).
- **Evidence:** [PR #1, third e2e run](https://github.com/Jooho/kserve-tutorials/actions/runs/44406969077).

### CI-005 Do no work before the first prompt
- **What happened:** a UI shell test timed out on GitHub but never here. The
  UI shell loaded Tab completion before each prompt by running
  `kubectl/helm/kind completion bash`; runners have those tools preinstalled,
  so the first prompt waited for cold Go binaries. This container had none, so
  it never showed up locally.
- **Rule:** interactive conveniences must be lazy (completion now loads on the
  first Tab). Tests that wait on a shell print its output when they time out,
  so a CI-only failure can be diagnosed from the log.
- **Evidence:** [PR #7 check](https://github.com/Jooho/kserve-tutorials/actions/runs/44447042731).

### CI-006 Tests must not depend on the contributor's machine
- **What happened:** `make precommit` failed on a maintainer's laptop and
  passed in CI: (1) four tests that create throwaway git repositories failed
  with `git commit` exit 128, because the personal git config signs commits;
  (2) a UI test failed with `No module named 'pyte'`, because the `.venv` was
  made before `pyte` was added to `tools/requirements.txt`, and `make doctor`
  only checked a hard-coded list of modules.
- **Rule:** tests run with an isolated git config (`tools/tests/conftest.py`:
  no signing, no hooks, no system config). `make doctor` checks every pin in
  `tools/requirements.txt` (missing = problem, other version = warning) and
  `make test` stops with "make setup" before running when a package is missing.
- **Evidence:** reproduced with `GIT_CONFIG_GLOBAL` set to a config with
  `commit.gpgsign = true` (4 failed before the fix, 71 passed after).
