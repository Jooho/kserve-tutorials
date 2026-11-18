# Backlog: problems this repository exists to solve

Everything here was hit for real while building the repository (mostly in
the first end-to-end runs of PR #1). Each item says why it matters. Agents:
read this before starting structural work, pick items from here, and update
the status and links when you finish one. Do not delete items; mark them done
with the PR that closed them.

Status: ☐ open · ◐ in progress · ☑ done

## A. Platform and environments ("is the cluster really ready?")

| # | Status | Item | Why / evidence |
|---|---|---|---|
| A1 | ☐ | Split environments into **contract + check + provisioners**: `contract.yaml` (what a tutorial needs: KServe version, CRDs, Gateway reachable, webhooks answering), `check.sh` (validates *any* current cluster), `provision/kind.sh` (one way to satisfy it) | Tutorials must work on the reader's own cluster, not only on a kind we create |
| A2 | ☐ | **Bring-your-own-cluster mode**: setup uses the current cluster if `check.sh` passes, provisions kind only when asked | Today setup always creates kind and refuses other clusters |
| A3 | ☐ | **Environment tests on their own**: `./tut env test <env> --kserve-version X` (provision → check → teardown); CI runs env jobs first and marks tutorials "blocked by env" instead of failing them | Install failures showed up as tutorial failures (CI-001, CI-002) |
| A4 | ☐ | **Create the kind cluster ourselves** with a pinned kind version and node image (Kubernetes version); keep using KServe's `hack/kserve-install.sh` only for the KServe stack | kind and `kindest/node` versions came from the CI runner image (v1.37.0 that day), so results could change without any commit |
| A5 | ☐ | **cloud-provider-kind**: pinned release binary instead of `go install …@latest` (slow, unpinned, failed on a proxy.golang.org error); document macOS/Windows needs `sudo` and port mapping; doctor checks it is running | CI-002; the reason we run cloud-provider-kind is real LoadBalancer IPs, like a cloud |
| A6 | ☐ | **Gateway address module**: read the address from Gateway / LLMInferenceService status (same code on kind+cloud-provider-kind, EKS, OpenShift); verify it is reachable; on macOS use cloud-provider-kind's localhost mapping; `port-forward` only as a last resort, announced by doctor | `gateway-url.sh` uses `docker inspect kind-worker` + NodePort: Linux-only |
| A7 | ☐ | **`addons/<name>/vN/`** for optional components (Prometheus/Grafana first, for the monitoring tutorial), versioned and tested like envs | Some tutorials need extra components; installing them ad hoc breaks independence |
| A8 | ☐ | **Report upstream to KServe**: (1) installer applies LLMInferenceServiceConfigs before the webhook answers (CI-001); (2) v0.18.0–v0.19.0 default scheduler image `llm-d-inference-scheduler:v0.7.1` no longer pullable (CI-004) | Our workarounds in `envs/kind-llmisvc/v1/setup.sh` should become unnecessary |
| A9 | ☑ | Verify the scheduler image workaround (`llm-d-router-endpoint-picker:v0.9.0` under KServe v0.18 config) actually works | Verified: `llmisvc-anatomy` passed 16/16 including a completion through the Gateway ([run](https://github.com/Jooho/kserve-tutorials/actions/runs/44412518216)) |

## B. "Works in CI, fails on my machine"

| # | Status | Item | Why / evidence |
|---|---|---|---|
| B1 | ☐ | **`./tut doctor`**: tools and versions, Docker CPU/memory, architecture, disk, proxy, cloud-provider-kind running; runs in setup, in the UI and in CI | Readers' machines differ from the CI runner (4 CPU / 16 GiB, linux/amd64) |
| B2 | ☐ | **Pinned tool versions** (kind, kubectl, helm, cloud-provider-kind) downloaded to `~/.cache/kserve-tutorials/bin`, used by CI and locally | Same tools in CI and on laptops |
| B3 | ☐ | **Supported platforms** declared per env (`linux/amd64`, `darwin/arm64`, …) and checked by doctor; find out whether the vLLM CPU image runs on Apple Silicon | CI only covers linux/amd64; GitHub macOS runners cannot run Docker |
| B4 | ☐ | **Lint: no kind-specific commands in tutorials** (`docker inspect`, `kind-worker`, `kind …`) — only in envs/lib | Keeps tutorials portable (A2) |
| B5 | ☐ | **Lint: every `kubectl wait` has `--timeout`; no long `sleep`** | authoring.md § Writing good steps |
| B6 | ☐ | **CI scenario: existing cluster** (provision first, then run the tutorial in bring-your-own mode) | Tests A2 |
| B7 | ☐ | **CI scenario: run twice on the same cluster** (catches `AlreadyExists`, leftover state, partial re-runs from the UI) | Local runs are rarely on a clean cluster |
| B8 | ☐ | **UI "Report a problem"** button: opens an issue prefilled with doctor output, failing block and output tail | Local failures CI cannot see must come back to the repository |

## C. Content and KServe versions

| # | Status | Item | Why / evidence |
|---|---|---|---|
| C1 | ☐ | **Decide how tutorials handle version-specific content** (separate tutorial versions, per-version blocks, or `kserve.tested` ranges + new tutorial) | KServe master removed the scheduler's tokenizer sidecar; `llmisvc-anatomy` explains and verifies three containers |
| C2 | ☐ | Update `llmisvc-anatomy` for the next KServe release once C1 is decided (the canary will flag it) | Same as C1 |
| C3 | ☐ | Korean translation of `llmisvc-anatomy` | legacy had KO for some tutorials |
| C4 | ☐ | **Migrate the remaining tutorials** (legacy repository + local ones) with docs/migration-guide.md, one PR each, done with local Claude Code | The point of the repository |

## D. Process and publishing

| # | Status | Item | Why / evidence |
|---|---|---|---|
| D1 | ◐ | Get PR #1 green, squash, run the final test | Green on [run 44412518216](https://github.com/Jooho/kserve-tutorials/actions/runs/44412518216) after 4 attempts (CI-001…004); squash + final test pending |
| D2 | ☐ | After the first green run: `llmisvc-anatomy` → `stable`, freeze `envs/kind-llmisvc/v1` and `lib/llmisvc/v1` | T007/L004 |
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
