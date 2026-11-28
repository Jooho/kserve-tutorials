# Authoring tutorials

Read this before writing or changing a tutorial. The design behind these rules is in [RFC 0001](rfc/0001-repository-structure.md); the mechanical rules are enforced by `./tut lint` (codes in brackets).

## 1. Shape of a tutorial

```text
tutorials/<id>/
  tutorial.yaml     metadata (schema/tutorial.schema.json)
  README.md         the document AND the test (English, the source)
  README.ko.md      optional translation
  manifests/        real files, shown with tut:include
  images/
```

Start with `make new T=<id> [TITLE="..."] [OWNER=<github-handle>]` (or `./tut new <id>`): it copies `tutorials/_template/`, fills in id and namespace, and starts as `status: draft`, English only (translate later with `./tut translation draft`).

### The project: `project.yaml`

The toolkit (`tools/`, `schema/`) names no product. What it shows or writes about the product comes from `project.yaml` at the repository root [P001]:

| Field | Used for |
|---|---|
| `name` | labels: "Tested with KServe v0.18.0", the UI's version picker, release notes, D003 |
| `title`, `intro` | the site's home page, the UI's title, release names |
| `version_var` | the shell variable a tutorial reads its version from (`$KSERVE_VERSION`); the setup step exports it, `./tut run --version` sets it |
| `upstream` | the GitHub repo whose releases `./tut kserve-version <ver>` checks a version against |
| `version` | the newest KServe version the tutorials move to, always pinned here (required): N in CI. Show or set it with `./tut kserve-version [<ver>]` (the command is `<id>-version`); nothing follows the upstream's newest release by itself. A tested version above it is an error [T009] |
| `example` | the finished tutorial `./tut draft` shows the AI |
| `glossary` | product terms translations keep in English |

So a tutorial's versions live under `versions:` in `tutorial.yaml` (not under the product's name), an env declares the versions it can install under `versions: {min, max}`, and `./tut project --get <key>` prints a value for scripts. `./tut run --kserve-version` still works: `--<project id>-version` is an alias of `--version`.

## 2. Blocks

| Fence | Meaning |
|---|---|
| ` ```bash run ` | a step; executed |
| ` ```bash verify ` | a check; executed with `set -Eeo pipefail`, must succeed |
| ` ```bash verify retry=N delay=S ` | a check that becomes true eventually |
| ` ```bash cleanup ` | undo; always executed at the end |
| ` ```bash skip ` | shown only: interactive or optional commands |

Every shell block has exactly one role [D001]. The first runnable block is the generated `<!-- tut:setup -->` region [D006]. Files are shown with `<!-- tut:include path -->`, never pasted [D002, D005].

## 3. Writing good steps

- **Write for a fresh machine.** Assume nothing but the environment profile. Create everything else in the tutorial's own namespace (`$NS`).
- **Wait, don't sleep.** Use `kubectl wait --for=... --timeout=...` or `verify retry=N delay=S`. Never `sleep 60` hoping it is enough.
- **Every wait has an explicit timeout**, sized for a CPU-only CI runner (cold image pulls, model download). Put the expected duration in the text.
- **Decide what the tutorial teaches, and say it at the top.** Under the Key question, list in a few bullets, under a line "What you will learn:", what the reader will understand at the end: concepts, not commands [D016, a warning for now]. Every step serves one of them, and "What we learned" at the end answers the same list. A tutorial is not a list of commands to copy and run; a step that teaches nothing on the list is cut or says why it is there.
- **Every step says what to look at, the value to expect, and why.** Name the field, metric or output line that matters; give the value the reader should see, taken from a real run ("in our run" for values that vary by machine); explain the mechanism that produces it (which counter rises, by about how much, and why). When a reason comes from source code or documentation rather than from the run, say so. Make the command print what the text talks about, and check stable values with a `verify`.
- **Ask the student before you ask for review.** Give the README to the `student` agent (`.claude/agents/student.md`; other AIs: read it and do the same in a fresh context). It reads only what a reader sees and lists the questions a learner would ask ("what is the difference between these two panels?"). Answer each in the README, or write in the PR why not. At most two rounds per change: ask, update, ask once more, update, then stop; later questions go to the explainer or a follow-up.
- **Change every copy of a claim together.** A tutorial says most things more than once: README.md, every README translation, the explainer and every explainer translation, and their pictures. Before you fix a claim, a section or a picture, look for it in all of them; fix every one that has it in the same change, and say per file what you changed.
- **Verify what the reader is meant to learn**, not just that a command ran: counts, names, field values, a request that returns a real answer. If the prose says "you should see X", a `verify` checks X.
- **Every step is safe to run twice** [D012]. Readers re-run steps after a failure, in a new shell, or with "To here"; CI runs every tutorial twice in the same cluster (`./tut run --twice`). Use `kubectl apply`, `kubectl create … --dry-run=client -o yaml | kubectl apply -f -`, `helm upgrade --install`, `kubectl delete … --ignore-not-found`, `>` not `>>`. A step that truly cannot repeat is fenced ` ```bash run once `: CI runs it once and the UI asks before running it again.
- **No UI aliases in tutorials** [D013]: `k` and `kc` exist only in the UI terminal; tutorials always write `kubectl`.
- **Interactive commands** (`watch`, `port-forward` in the foreground, editors, `kubectl exec -it`) are `skip`, followed by a non-interactive `verify` equivalent when it matters.
- **Pin images** [M001]. No hard-coded KServe versions; use `$KSERVE_VERSION` [D003].
- **Cleanup** deletes what the tutorial created (its namespace at least), never the cluster: the cluster belongs to the environment [D007].
- Keep `timeout_minutes` in `tutorial.yaml` realistic: setup + all waits.

Images in a README: `<a href="images/x.svg" target="_blank"><img src="images/x.svg" width="720" alt="what it shows"></a>`, not `![..](images/x.svg)`. Every picture then has the same width on GitHub and in the UI, and a click opens it at full size [D015]. Say once, next to the first picture, that a click opens it full size.

Screenshots of a web UI (Grafana, a dashboard) come from a real run, show the state the text talks about at that point, and are cropped to the panels the text names (PNG, about 1000 px wide). Take them with Playwright in a container, never with a browser installed on the host [hard rule 10]. What worked (llmisvc-monitoring, 2026-11-24):

- Image `mcr.microsoft.com/playwright/python:v1.56.0-noble` with `pip install playwright==1.56.0`. The older v1.49 Chromium could not load Grafana 13's plugins.
- Run it with `--network host` (the Kind node IP is reachable), `--user "$(id -u):$(id -g)" -e HOME=/tmp`, and mount the output folder with `:Z` on SELinux hosts (Fedora), or the container cannot read the script.
- Give the browser a locale: `new_context(locale="en-US")` and `-e LANG=en_US.UTF-8`. Without it the locale is `en-US@posix` and Grafana fails with "Datasource ... was not found" on every panel.
- Log in through the API in the same browser context (`ctx.request.post(base + "/login", data={"user": "admin", "password": pw})`), then open the dashboard; HTTP basic credentials alone end on the login page.
- Wait for the panels (network idle, then about 15 s, scroll once through the page), screenshot the full page, crop with `magick -crop` and reduce with `magick -colors 192 PNG8:`.

Line breaks: in `docs/` write one line per paragraph and do not wrap by hand; a phrase then stays on one line, so `grep` and exact-match edits find it, and nothing has to be re-wrapped after a change. In a tutorial README keep the existing line breaks: reflowing changes nothing a reader sees but changes the source hash, so translations and the explainer go behind and CI runs the tutorial again.

## 4. Shared parts

| Need | Use | Declare in tutorial.yaml |
|---|---|---|
| A cluster with KServe | an environment profile `envs/<name>/vN/` | `env:` |
| A helper script used by several tutorials | a script module `lib/<name>/vN/` | `uses:` |

- Check existing parts before creating one.
- Calls look like `"$TUT_LIB/llmisvc/v1/gateway-url.sh"` and must be declared [L002].
- `frozen: true` parts never change [E002, L003]. To change one, copy it to `vN+1`, change the copy, move tutorials over one PR at a time.
- A stable tutorial may only use frozen parts [T007, L004].
- **Personal settings** (cluster name, skipped tools) live in `.tut.env`, loaded by `tools/local-config.sh` in `./tut` and in every generated setup step. Never ask readers to `export` something in prose; add a setting.
- **Tools belong to the environment.** An environment pins the CLI tools it needs in `tools.env`; its `setup.sh` installs them into `.tools/` and the generated setup block puts them on `PATH` for that shell only. Tutorials never install tools or assume system ones. Docker is a user prerequisite, checked by `./tut doctor`, never installed.
- **Installation robustness belongs in the environment, not in tutorials.** If a tutorial needs a retry or a readiness wait because the platform was not really ready, fix the environment profile.

## 5. Groups, tags and collections (catalog/)

- **Group** (`group:` in tutorial.yaml, one per tutorial): what kind of tutorial it is — `llmisvc`, `inferencegraph`, ... from `catalog/groups.yaml` [G003]. The UI's **Groups** view lists every tutorial once under its group and opens it on its own. Add a group only if none fits.

- **Tags** make tutorials findable (search, filter in the UI, site). Use only tags listed in `catalog/tags.yaml` [G001]; lint suggests the closest one for a typo. If no tag fits, add one to `catalog/tags.yaml` in the same PR, with a group (`feature`, `topic`, `level`) and a one-line description. Prefer reusing a tag over adding a near-duplicate. Give every tutorial one `level`.
- **Collections** (`catalog/collections/<id>.yaml`) are learning paths: **two or more** tutorials in order [C005 warns with one; the UI shows only real paths]. They list tutorial ids; tutorials never refer to collections and stay independent. A tutorial may be in several collections or in none. `vars:` are shared shell variables for the path (see Shared steps and learning paths).
  - Order is the list order — no order numbers to renumber.
  - Each collection has `owners`; they review every change to it (generated `.github/CODEOWNERS`). To add your tutorial to someone's path, edit the list in your PR and let them review.
  - Members must exist [C002] and appear once [C003]. When you archive a member, give it a `deprecation.replacement` or readers hit a dead end [C004]; the UI and site show the replacement in its place automatically.
- **Owners**: `owners` in `tutorial.yaml`, collections, env profiles and lib modules are GitHub handles. `./tut sync` writes `.github/CODEOWNERS` from them (and `catalog/maintainers.yaml` for everything else) [O001]; never edit it.

## 6. Lifecycle

`draft` → `stable` (CI passed, parts frozen) → `deprecated` (still works, being replaced) → `archived` (kept, not run). Deprecating or archiving needs a `deprecation` block [T006] and changes only that tutorial.

### A new product version changes a tutorial: keep the old one as a revision

When a tutorial has to change because of a new version (an API, a default, a component), readers on the older versions keep the tutorial as it was: a frozen copy in `tutorials/<id>/revisions/vX.Y/` (docs/rfc/0002-tutorial-revisions.md). Always, without trying to keep one README true for both.

```bash skip
./tut kserve-version v0.20.0             # pin the new version (checks the upstream has that release)
./tut tested add v0.20.0 --all           # then ./tut sync; CI of the PR runs every tutorial on v0.20.0 and on v0.18.0
# for each tutorial that fails or is no longer true on v0.20.0:
./tut revision start <id> --to v0.20.0   # copies tutorials/<id>/ from origin/main to revisions/vX.Y (frozen),
                                         # sets versions.tested/default of the current tutorial to v0.20.0
# edit the tutorial for v0.20.0, ./tut sync, ./tut run <id>, make precommit
./tut revision list                      # every tutorial and revision with its tested versions
./tut revision todo                      # tutorials that skipped versions (a gap in versions.tested)
./tut revision keep <id> [v0.18.0 ...]   # skipped versions: move them to a revision without a new version
```

- The maintainer starts the move (AGENTS.md "A new product version"); `revision start` also works after the new version was added to `tested` on the branch. A tutorial edited for the new version is `status: draft` until a person reviewed it.
- The revision's directory is named after the newest minor it keeps: `revisions/v0.18/` is the tutorial for v0.18 [R001].
- The current tutorial shows its own version only. Do not compare with older versions ("removed", "no longer", "in older versions") and do not keep a ghost of what is gone in text, tables, checks or pictures: delete it. Readers of the older version have the revision. Something that looks odd in the current version gets its reason in present terms.
- Freeze first, then edit; the revision and the change go into one commit. The copy is taken from the base branch, so it is what was verified.
- The copy runs from its new place: its setup step `cd`s into the revision and links that leave the tutorial are re-pointed. `./tut sync` never writes into `revisions/`; the current README's header links each revision.
- A revision is never edited [R002], uses only frozen env and lib parts [R003], and one version belongs to one variant [R005]. A version removed from `versions.tested` must be in a revision [R004].
- If the tutorial defines shared steps (`tut:define`) that other tutorials copy, and you change a definition for the new version, those tutorials change too: `--with-users` starts them as well.
- `./tut run <id> --version v0.19.0`, `./tut ui` ("My KServe" version) and the site pick the revision tested with that version, by tag, then by minor (v0.19.2 uses what was tested as v0.19.x).
- The copy includes translations and the explainer as they were: copying them is the one exception to "explainer changes go in their own PR".
- A change that is not about a version (a typo, more explanation) needs no revision.
- CI runs two versions of a tutorial: N (`version` in project.yaml, `./tut kserve-version`) if the tutorial tests it, and N-1, the newest version it tests below N (revisions included). Older versions stay in `tested` as "last verified". A tutorial that skipped versions (tested v0.18.0 and v0.20.0, nothing for v0.19) is listed by `./tut revision todo` (`make precommit` prints it). Ask the maintainer, then `./tut revision keep <id>` moves the versions before the gap to a frozen revision.

## 7. Translations

`README.md` is the source. `<id>` is the tutorial's directory name.

**With an AI CLI** you are logged in to (Claude Code, GitHub Copilot CLI, Codex CLI, or any command) — no API keys in this repository:

```bash skip
export TUT_AI=claude                        # or copilot, codex, cmd:<command>; or ./tut config TUT_AI=claude
export TUT_AI_TRANSLATE=codex               # optional: another CLI only for translations
./tut translation draft <id> ko             # one tutorial
./tut translation draft --all [ko]          # every missing or outdated translation
make precommit TRANSLATE=1                  # the same, as part of the pre-commit checks
#   review the Korean text (git diff), fix what reads badly
./tut translation mark <id> ko              # only after a person or agent reviewed it
```

The AI only returns text; a program checks it before anything is written: code blocks, commands, generated regions, HTML comments and link targets must be unchanged (comments inside code may be translated). A rejected draft is kept in `build/translations/` for inspection and nothing changes. An accepted draft is marked `by=<tool> reviewed=no`: lint warns, the UI tells readers it is an AI translation, and `mark` turns it into a reviewed one.

**Rejected or no AI:** start from the rejected output in `build/translations/`, or copy `README.md` to `README.ko.md`; translate prose and code comments, keep the code and regions exactly; then `mark` (it also adds `ko` to `langs`).

`./tut translation` shows every translation's state and the next step. A translation has the same shell blocks in the same order [D011]. When README.md changes later, lint warns that the translation is behind [D010] and the UI shows it to readers. Translation lag never blocks English changes or releases.

Nothing translates on its own: `./tut sync` stays deterministic and offline, and plain `make precommit` only lists what is missing (`./tut translation todo`). Translate when the English is done, so the AI does not chase a moving text.

### Updating a translation after the English changed

`./tut translation draft` translates the whole README again. That takes 5 to 10 minutes per file and the AI rewords sentences a person already reviewed (it once turned the Grafana panel name "Scheduler Attempts", which stays English because the screen shows it in English, into Korean). When a translation exists and only parts of the English changed, update instead of redoing. The helpers are in `tools/contrib/translation/` (not part of `./tut` yet, backlog B23); they use the same AI CLI as `./tut translation draft` (`TUT_AI_TRANSLATE`, else `TUT_AI`):

```bash skip
# 1. Finish the English first: README, explainer, the review rounds. Translate once, at the end.
# 2. A tutorial whose English changed in many places: the AI gets the previous English, the reviewed
#    previous translation (from the base branch) and the new English; it keeps the translation of
#    every unchanged paragraph and translates only what changed. The usual checks run on the result.
.venv/bin/python tools/contrib/translation/update_readme.py <id>            # README.ko.md
.venv/bin/python tools/contrib/translation/update_explainer.py <id>         # explainer/index.ko.md
# 3. A few sentences changed after that (a review finding, a typo): send only those blocks.
#    A block is the text between two blank lines; name each changed block by a piece of its new English.
.venv/bin/python tools/contrib/translation/patch_blocks.py tutorials/<id>/explainer/index.md \
    tutorials/<id>/explainer/index.ko.md "a few words of the new sentence" "another changed block"
# 4. Compare what changed with the English (git diff of the .ko.md file), then ./tut translation mark <id> ko.
```

- Step 2 still makes the AI write the whole file (5 to 10 minutes); step 3 took about a minute for eight blocks in three files. Use step 3 whenever you can name the changed blocks.
- Step 3 needs the English and the translation to have the same number of blocks in the same order; the helper refuses otherwise. A translation made by the tools has that shape.
- Unchanged text must stay byte for byte: check with `git diff` that only the blocks you expected moved.
- An explainer's translation is never marked by an agent (`./tut explain mark` is the reader's).

## 8. New tutorial from tested work: `./tut draft`

Start from the scripts, manifests and notes you tested by hand:

```bash skip
export TUT_AI=claude          # or copilot, codex, cmd:<command>; or ./tut config TUT_AI=claude
./tut draft ~/work/my-test --id my-test --owner <github-handle> [--collection <path>]
```

The folder is copied (the original is only read); images and binary files are copied into `tutorials/<id>/` at the same paths. Your AI CLI gets these rules, an example tutorial and the reusable parts (envs with their options, helper scripts, shared steps). It may write only `tutorials/<id>/` and `build/draft/<id>/` and run only `./tut _draftcheck <id>` (sync, lint, dry run; never a cluster). It lists every change to a tested command and the TODOs in `build/draft/<id>/notes.md`; the program checks the result and writes `build/draft/<id>/report.md` (lint, files changed elsewhere, input commands not in the tutorial). Finish in `./tut ui` (✎ Edit), then `./tut run <id> --twice`. Example of the material and the output: `docs/draft-example/`.

## 9. Shared steps and learning paths

- **Shared step:** wrap steps another tutorial may need in `<!-- tut:define name -->` … `<!-- /tut -->`. Another tutorial writes `<!-- tut:use name -->` + `<!-- /tut -->` and `./tut sync` copies the steps in, so every README stays complete on its own (GitHub, CI) [D014: one definition per name, `use` an existing name, no markers inside a definition]. Keep the state a shared step creates in the cluster or in files: in a learning path its `run` blocks may be hidden, so they cannot hand shell variables to later steps; every block sets the defaults it needs.
- **Learning path** (a collection opened from the UI's Collections view): a shared step an earlier member already has is "covered": its `run` blocks are hidden, its `verify` blocks still run (a failing one offers to run the hidden steps). Cleanup waits until the end of the path. `vars:` in the collection (e.g. `NS`) are exported in every member's shell. CI always runs each tutorial standalone.
- **Writing in the UI:** `./tut ui` redraws the page when a file is saved, shows the README as it will be after `./tut sync`, and lists this tutorial's lint findings. ✎ Edit opens README or tutorial.yaml next to the preview (Ctrl+S, Save & sync). The "no KO translation · ＋ create it" chip makes an AI draft with `TUT_AI` (claude | copilot | codex).

### Explainer (optional, AI)

A tutorial can have a teaching page next to it, `explainer/`, written by an AI from a live run (diagrams, animated flows, labelled AI-written, never executed, outside CI e2e). Do not write one by hand inside the README; see [explainer.md](explainer.md) and `./tut explain draft <id>`.

## 10. Before you open a PR

```bash skip
make precommit               # ./tut sync, then lint + tests + site (CI checks the same)
./tut run <id> --dry-run     # read what CI will execute
./tut run <id>               # or step through it with ./tut ui
```

## 11. Rules learned from CI

Each entry: what happened → the rule → evidence. Add one whenever you fix a failure a rule could have prevented (see AGENTS.md). Promote it to lint when it can be checked mechanically.

### CI-001 "Available" is not "ready to use"
- **What happened:** KServe's installer applied `LLMInferenceServiceConfig`s right after the controller Deployment was Available; the validating webhook was not accepting connections yet (`connection refused`), so setup failed.
- **Rule:** an environment's setup must end with a readiness gate that exercises the platform (webhooks answer, CRDs established), not only Deployment availability. Retries for platform installs live in the environment profile.
- **Evidence:** [PR #1, first e2e run](https://github.com/Jooho/kserve-tutorials/actions/runs/44400612336).

### CI-002 Downloads fail; retry installs
- **What happened:** building `cloud-provider-kind` failed on a `proxy.golang.org` stream error.
- **Rule:** anything that downloads during setup is retried (installer attempts, pulls). A single network error must not fail a tutorial.
- **Evidence:** [PR #1, second e2e run](https://github.com/Jooho/kserve-tutorials/actions/runs/44401972251).

### CI-003 A failure without evidence cannot be fixed
- **What happened:** the LLMInferenceService never became Ready, but cleanup and teardown deleted everything before anyone could look.
- **Rule:** CI runs tutorials with `--keep-on-failure` and dumps diagnostics (pods, events, logs) before tearing down. When you add a new kind of resource, make sure `.github/scripts/diagnose.sh` would show it.
- **Evidence:** same run as CI-002.

### CI-004 Upstream images disappear
- **What happened:** the LLMInferenceService never became Ready because the EPP scheduler image from KServe's own default config, `ghcr.io/llm-d/llm-d-inference-scheduler:v0.7.1`, stopped being publicly pullable (ghcr.io 403 on the anonymous token). llm-d renamed it to `llm-d-router-endpoint-picker`. Every KServe release up to v0.19.0 was affected for every user, not only CI.
- **Rule:** a published release can break without any change on our side (there is no scheduled run any more: the next PR or release run shows it). Work around platform breakage in the environment profile (documented as a known issue with the upstream fix to watch), never in individual tutorials. Diagnostics must show image pull errors (they did: `ImagePullBackOff` + the 403 in events).
- **Evidence:** [PR #1, third e2e run](https://github.com/Jooho/kserve-tutorials/actions/runs/44406969077).

### CI-005 Do no work before the first prompt
- **What happened:** a UI shell test timed out on GitHub but never here. The UI shell loaded Tab completion before each prompt by running `kubectl/helm/kind completion bash`; runners have those tools preinstalled, so the first prompt waited for cold Go binaries. This container had none, so it never showed up locally.
- **Rule:** interactive conveniences must be lazy (completion now loads on the first Tab). Tests that wait on a shell print its output when they time out, so a CI-only failure can be diagnosed from the log.
- **Evidence:** [PR #7 check](https://github.com/Jooho/kserve-tutorials/actions/runs/44447042731).

### CI-006 Tests must not depend on the contributor's machine
- **What happened:** `make precommit` failed on a maintainer's laptop and passed in CI: (1) four tests that create throwaway git repositories failed with `git commit` exit 128, because the personal git config signs commits; (2) a UI test failed with `No module named 'pyte'`, because the `.venv` was made before `pyte` was added to `tools/requirements.txt`, and `make doctor` only checked a hard-coded list of modules.
- **Rule:** tests run with an isolated git config (`tools/tests/conftest.py`: no signing, no hooks, no system config). `make doctor` checks every pin in `tools/requirements.txt` (missing = problem, other version = warning) and `make test` stops with "make setup" before running when a package is missing.
- **Evidence:** reproduced with `GIT_CONFIG_GLOBAL` set to a config with `commit.gpgsign = true` (4 failed before the fix, 71 passed after).

### CI-007 `| grep -q` fails a check that is true
- **What happened:** the first real run of the AI-drafted `inferencegraph-ensemble` failed a verify block with exit 141 although the image was there: `crictl images | grep -q ensemble-combiner`. The runner uses `set -o pipefail`; `grep -q` exits at the first match, the writer gets SIGPIPE (141), and the pipeline fails. It depends on output size and timing, so it passes by hand and fails in CI. The same pattern in the env's `setup.sh` (`kubectl get ... -o yaml | grep -q`, envs/kind-llmisvc/v1) could silently skip the scheduler-image workaround.
- **Rule:** after a command that can print more than a few lines, write `| grep PATTERN >/dev/null`, not `| grep -q PATTERN`. The same goes for anything that stops reading early: `grep -m1`, `head`. To show the matching line, use `| grep PATTERN | tail -n 1` (tail reads everything; no match still fails through grep). Checked by `./tut lint` (warning): D017 in README blocks, E004 in env scripts, L006 in lib scripts; a short `echo`/`printf` writer is allowed.
- **Evidence:** [PR #18 e2e](https://github.com/Jooho/kserve-tutorials/pull/18), `README.md:444 (step 11/25 · verify) (exit 141)`; reproduced: `set -o pipefail; seq 1 200000 | grep -q 1` → 141. Again in [PR #55 e2e](https://github.com/Jooho/kserve-tutorials/actions/runs/45730357476/job/139610900602?pr=55): `kubectl logs ... | grep -m1 'auto-created default producer...'` printed the line and failed with 141 (llmisvc-request-flow README.md:454).

### CI-008 The runner killed itself with a tutorial's `pkill -f`
- **What happened:** the second run of `inferencegraph-ensemble` passed steps 1–20, then died with exit -15 (SIGTERM) and no failing step. Step 21 ran `pkill -f "[p]ort-forward -n ingress-nginx svc/ingress-nginx-controller 8080:80"`. The runner passed the whole tutorial as `bash -c <script>`, so the runner's own command line contained the port-forward command of the same step, and pkill matched it. (The `[p]` trick only keeps pkill from matching itself.) In a reader's terminal this cannot happen, so it was a CI-only failure.
- **Rule:** the runner executes the script from a file (`bash <file>`), so no step can match the runner by its command line. Tutorials may still prefer stopping background processes by PID.
- **Evidence:** [PR #18 e2e](https://github.com/Jooho/kserve-tutorials/pull/18) (`exit_code: -15`, `failed_at: null`, during README.md:712); reproduced and guarded by `test_runner_survives_pkill_f_of_a_command_in_the_same_tutorial`.

### CI-009 The runner changed a block's code by indenting it
- **What happened:** the third run of `inferencegraph-ensemble` reached step 22 (the first InferenceGraph request) and failed all 12 retries with `IndentationError: unexpected indent`. The runner wrapped `retry=` verify blocks (and cleanup blocks) in a loop and indented their code for readability; that also indented the lines inside the `python3 -c '...'` string. Heredocs would break the same way. The UI and a reader's terminal run the code unchanged, so it only failed in CI.
- **Rule:** the runner pastes block code byte for byte, never re-indented.
- **Evidence:** [PR #18 e2e](https://github.com/Jooho/kserve-tutorials/pull/18) (README.md:722, step 22/25); reproduced and guarded by `test_runner_keeps_block_code_byte_for_byte`.

### CI-010 The cluster name decided whether the Gateway got an address
- **What happened:** with `KIND_CLUSTER_NAME=tut` (what `make doctor` suggests when a foreign `kind` cluster exists), `llmisvc-request-flow` failed at `kubectl wait --for=condition=Programmed gateway`: `AddressNotAssigned`, the Envoy LoadBalancer Service had no IP and cloud-provider-kind was not running. KServe's installer (`hack/setup/common.sh` `detect_platform`) treats a cluster as kind only when the node hostname contains "kind"; `tut-control-plane` does not, so it logged `Platform kubernetes does not require external LB setup. Skipping.` CI uses the default name `kind`, so only local runs hit it.
- **Rule:** an environment tells the upstream installer what it built instead of letting it guess: `envs/kind-kserve/v1/setup.sh` exports `PLATFORM=kind`. Test env scripts with a non-default cluster name.
- **Evidence:** local `./tut run llmisvc-request-flow --twice` on cluster `tut` (step 5/22, pass 1); passed on a cluster named `tut-kind`. Guarded by `test_installer_is_told_the_platform_is_kind_whatever_the_cluster_name`.

### CI-011 `kubectl logs -l ... --tail=N | grep` missed a line that was there
- **What happened:** the first `--twice` run of `llmisvc-request-flow` passed pass 1 and failed pass 2 at the verify that finds a request id in the EPP scheduler log (`kubectl logs -l ... --tail=500 | grep "$REQUEST_ID"`). The EPP image the env installs (`llm-d-router-endpoint-picker`, CI-004) also prints its OpenTelemetry spans to the log, several hundred lines per request, a few seconds later; by the time of the check the request was about 1000 lines from the end. The first fix, `--since=5m` alone, failed at once: with `-l`, `kubectl logs` keeps only the last 10 lines unless `--tail` is given.
- **Rule:** to find a recent event in a log, search a time window, not a line count: `kubectl logs ... --since=5m --tail=-1 | grep ...`. Never rely on the default tail of `kubectl logs -l`.
- **Evidence:** local runs on 2026-11-20 (pass 2, step 12/22: the request id was at line 1792 of 2793; `--since=5m` with `-l` returned 10 lines, `--since=5m --tail=-1` returned 3259 lines with 12 matches); the fixed tutorial then passed `--twice` from a fresh cluster in 572 s.

### CI-012 A cloud-provider-kind from the previous cluster did not serve the new one
- **What happened:** `./tut run llmisvc-anatomy --teardown-env` followed by `./tut run llmisvc-request-flow` failed at the Gateway `Programmed` check (`AddressNotAssigned`) although the cluster was named `kind` (not CI-010). Teardown deleted cluster `kind` and setup recreated it two seconds later. The cloud-provider-kind process started for the old cluster was still running, so KServe's installer logged `cloud-provider-kind is already running` and went on; that process never served the new cluster with the same name. Restarting it gave the Gateway an address within a second. CI never sees it: every job starts on a fresh runner.
- **Rule:** an environment owns the host processes its clusters need. The `kind-kserve/v1` setup starts cloud-provider-kind itself (pinned binary, log in `$TUT_CACHE/cloud-provider-kind.log`), restarts it whenever it creates a cluster, starts it when a reused cluster has none (after a reboot), and only reports ready once the Gateway is `Programmed`, so the failure shows up in the setup step with the log instead of in a tutorial step.
- **Evidence:** reproduced locally on 2026-11-20 (teardown, then setup 2 s later: Gateway `Programmed=False` after 4 min; a fresh cluster long after the previous one was deleted worked). With the fix the same sequence ended with the Gateway at `172.18.0.5`, `Programmed=True`. Guarded by `test_new_cluster_restarts_cloud_provider_kind` and `test_reuse_keeps_a_running_cloud_provider_kind_and_starts_a_missing_one`.

### CI-013 An exported TUT_AI made the translation tests call the real AI CLI
- **What happened:** the translation tests set `TUT_TRANSLATOR` to a fake command, but `TUT_AI` wins over it. With `TUT_AI` exported in the shell (as docs/getting-started.md tells you to), `make precommit` ran the real CLI or failed: with `TUT_AI=cmd:false`, 3 tests failed and one passed for the wrong reason. CI never sees it: no `TUT_AI` there. Same family as CI-006.
- **Rule:** tests run without the contributor's AI settings. `conftest.py` removes `TUT_AI*`, `TUT_AI_REVIEW*` and `TUT_TRANSLATOR*` before every test; a test that needs one sets it itself. `pytest.raises` wraps only the call that should raise, so a failure before it cannot pass the test.
- **Evidence:** found by a review of the test suite on 2026-11-21; `TUT_AI=cmd:false pytest tools/tests/test_translate.py` failed 3 tests before the fix and passes after it.

### CI-014 A reused cluster kept KServe's default deployment mode at Knative
- **What happened:** running `inferencegraph-ensemble` on the cluster the llmisvc tutorials had used, the InferenceGraph never got its router: `ServerlessModeRejected: It is not possible to use Knative deployment mode when Knative Services are not available`. The InferenceServices worked because their manifests say `deploymentMode: RawDeployment`; the InferenceGraph has no annotation and took the default from the shared `inferenceservice-config`, which said `Knative`. The llmisvc install had created that ConfigMap with `Knative` (this profile installs no Knative), and KServe standard added later with `--raw` did not touch it (`createSharedResources: false`). CI never sees it: every job starts with a fresh cluster.
- **Rule:** the environment owns the cluster-wide defaults its options imply. `kind-kserve/v1` sets `deploy.defaultDeploymentMode` to `Standard` unless KServe runs in serverless mode, after every install and on every reuse (which also repairs clusters set up before the fix), and restarts the KServe controller when it changes the value and the controller exists (an llmisvc-only cluster has none: the first CI run of the fix failed on exactly that, because the fake kubectl in the tests answered every command with success; it now fails for a controller that was never installed).
- **Evidence:** reproduced on 2026-11-22 (llmisvc cluster, then `TUT_ENV_TYPES=kserve TUT_ENV_MODE=standard`): `defaultDeploymentMode` stayed `Knative`; the next setup with the fix changed it to `Standard`, and a second run changed nothing. Guarded by `test_kserve_added_to_an_llmisvc_cluster_gets_the_standard_default`, `test_reused_cluster_with_the_wrong_default_is_repaired_once`, `test_an_llmisvc_only_cluster_gets_standard_too`, `test_serverless_keeps_knative`.

### CI-015 Adding KServe to an llmisvc cluster deleted every LLMInferenceServiceConfig
- **What happened:** on the cluster the llmisvc tutorials and `inferencegraph-ensemble` had shared, a new LLMInferenceService never started: `LLMInferenceServiceConfig "kserve-config-llm-scheduler" not found`. KServe's installer keeps the ClusterServingRuntimes (type kserve) and the LLMInferenceServiceConfigs (type llmisvc) in one Helm release, `kserve-runtime-configs`, and upgrades it with `--set kserve.servingruntime.enabled=$INSTALL_RUNTIMES --set kserve.llmisvcConfigs.enabled=$INSTALL_LLMISVC_CONFIGS`, which default to the types of the current call (`hack/kserve-install.sh`, `hack/setup/infra/manage.kserve-helm.sh` at v0.18.0). Adding kserve upgraded the release with `llmisvcConfigs.enabled=false` and Helm removed the configs; adding llmisvc to a kserve cluster removes the runtimes the same way. The env marker still said `types: kserve,llmisvc`. CI never sees it: every job starts with a fresh cluster.
- **Rule:** the environment tells the installer about every type on the cluster, not only the one it adds: `kind-kserve/v1` exports `INSTALL_RUNTIMES` and `INSTALL_LLMISVC_CONFIGS` from all types (what the cluster has plus what is added). On reuse it checks that each type it has still has its configs (`kserve-config-llm-scheduler`, at least one ClusterServingRuntime) and otherwise reinstalls that type with `FORCE_UPGRADE=true`, since the installer skips a part it thinks is installed; that also repairs clusters set up before the fix. The fake installer in the tests now upgrades one shared release the way the real one does, so the bug shows there.
- **Evidence:** seen on 2026-11-22: `helm get values -n kserve kserve-runtime-configs` gave `llmisvcConfigs.enabled: true, servingruntime.enabled: false` at revision 1 (llmisvc install) and the opposite at revision 2 (KServe standard added), and `kubectl get llminferenceserviceconfig -A` found none. Guarded by `test_adding_a_type_keeps_the_configs_of_the_other` (both orders) and `test_a_cluster_that_lost_its_llmisvc_configs_is_repaired_once`, which fail on the setup before the fix. The repair on that cluster (2026-11-23) brought back 8 LLMInferenceServiceConfigs and kept 12 ClusterServingRuntimes; its first installer attempt failed once with `no matches for kind "ClusterStorageContainer"` right after the CRD chart upgrade and the existing retry passed, and the reinstall set `defaultDeploymentMode` back to Knative, which the CI-014 step corrected. A second setup only reused the cluster. On the repaired cluster a new LLMInferenceService came up: `./tut run llmisvc-anatomy` passed (16 steps), and so did `./tut run inferencegraph-ensemble` (25 steps) on the KServe side.
