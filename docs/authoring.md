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
  and opens it on its own. Add a group only if none fits.

- **Tags** make tutorials findable (search, filter in the UI, site). Use only
  tags listed in `catalog/tags.yaml` [G001]; lint suggests the closest one for a
  typo. If no tag fits, add one to `catalog/tags.yaml` in the same PR, with a
  group (`feature`, `topic`, `level`) and a one-line description. Prefer
  reusing a tag over adding a near-duplicate. Give every tutorial one `level`.
- **Collections** (`catalog/collections/<id>.yaml`) are learning paths: **two
  or more** tutorials in order [C005 warns with one; the UI shows only real
  paths]. They list tutorial ids; tutorials never refer to collections and stay
  independent. A tutorial may be in several collections or in none. `vars:`
  are shared shell variables for the path (see Shared steps and learning paths).
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

## Shared steps and learning paths

- **Shared step:** wrap steps another tutorial may need in
  `<!-- tut:define name -->` … `<!-- /tut -->`. Another tutorial writes
  `<!-- tut:use name -->` + `<!-- /tut -->` and `./tut sync` copies the steps
  in, so every README stays complete on its own (GitHub, CI) [D014: one
  definition per name, `use` an existing name, no markers inside a definition].
  Keep the state a shared step creates in the cluster or in files: in a
  learning path its `run` blocks may be hidden, so they cannot hand shell
  variables to later steps; every block sets the defaults it needs.
- **Learning path** (a collection opened from the UI's Collections view): a
  shared step an earlier member already has is "covered": its `run` blocks are
  hidden, its `verify` blocks still run (a failing one offers to run the hidden
  steps). Cleanup waits until the end of the path. `vars:` in the collection
  (e.g. `NS`) are exported in every member's shell. CI always runs each
  tutorial standalone.
- **Writing in the UI:** `./tut ui` redraws the page when a file is saved, shows
  the README as it will be after `./tut sync`, and lists this tutorial's lint
  findings. ✎ Edit opens README or tutorial.yaml next to the preview (Ctrl+S,
  Save & sync). The "no KO translation · ＋ create it" chip makes an AI draft
  with `TUT_AI` (claude | copilot | codex).

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

### CI-007 `| grep -q` fails a check that is true
- **What happened:** the first real run of the AI-drafted
  `inferencegraph-ensemble` failed a verify block with exit 141 although the
  image was there: `crictl images | grep -q ensemble-combiner`. The runner uses
  `set -o pipefail`; `grep -q` exits at the first match, the writer gets
  SIGPIPE (141), and the pipeline fails. It depends on output size and timing,
  so it passes by hand and fails in CI. The same pattern in the env's
  `setup.sh` (`kubectl get ... -o yaml | grep -q`, envs/kind-llmisvc/v1) could silently skip the
  scheduler-image workaround.
- **Rule:** after a command that can print more than a few lines, write
  `| grep PATTERN >/dev/null`, not `| grep -q PATTERN`. Proposed lint rule
  (needs approval): warn on `| grep -q` in run/verify blocks and env scripts.
- **Evidence:** [PR #18 e2e](https://github.com/Jooho/kserve-tutorials/pull/18),
  `README.md:444 (step 11/25 · verify) (exit 141)`; reproduced:
  `set -o pipefail; seq 1 200000 | grep -q 1` → 141.

### CI-008 The runner killed itself with a tutorial's `pkill -f`
- **What happened:** the second run of `inferencegraph-ensemble` passed steps
  1–20, then died with exit -15 (SIGTERM) and no failing step. Step 21 ran
  `pkill -f "[p]ort-forward -n ingress-nginx svc/ingress-nginx-controller 8080:80"`.
  The runner passed the whole tutorial as `bash -c <script>`, so the runner's
  own command line contained the port-forward command of the same step, and
  pkill matched it. (The `[p]` trick only keeps pkill from matching itself.)
  In a reader's terminal this cannot happen, so it was a CI-only failure.
- **Rule:** the runner executes the script from a file (`bash <file>`), so no
  step can match the runner by its command line. Tutorials may still prefer
  stopping background processes by PID.
- **Evidence:** [PR #18 e2e](https://github.com/Jooho/kserve-tutorials/pull/18)
  (`exit_code: -15`, `failed_at: null`, during README.md:712); reproduced and
  guarded by `test_runner_survives_pkill_f_of_a_command_in_the_same_tutorial`.

### CI-009 The runner changed a block's code by indenting it
- **What happened:** the third run of `inferencegraph-ensemble` reached step 22
  (the first InferenceGraph request) and failed all 12 retries with
  `IndentationError: unexpected indent`. The runner wrapped `retry=` verify
  blocks (and cleanup blocks) in a loop and indented their code for
  readability; that also indented the lines inside the `python3 -c '...'`
  string. Heredocs would break the same way. The UI and a reader's terminal
  run the code unchanged, so it only failed in CI.
- **Rule:** the runner pastes block code byte for byte, never re-indented.
- **Evidence:** [PR #18 e2e](https://github.com/Jooho/kserve-tutorials/pull/18)
  (README.md:722, step 22/25); reproduced and guarded by
  `test_runner_keeps_block_code_byte_for_byte`.
