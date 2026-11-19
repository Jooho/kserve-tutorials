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

Start from `tutorials/_template/`. New tutorials start as `status: draft`.

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
- **Installation robustness belongs in the environment, not in tutorials.**
  If a tutorial needs a retry or a readiness wait because the platform was not
  really ready, fix the environment profile.

## 5. Lifecycle

`draft` → `stable` (CI passed, parts frozen) → `deprecated` (still works,
being replaced) → `archived` (kept, not run). Deprecating or archiving needs a
`deprecation` block [T006] and changes only that tutorial.

## 6. Translations

`README.md` is the source. A translation has the same shell blocks in the same
order [D011]; after translating run `./tut translation mark <id> <lang>` [D010].

## 7. Before you open a PR

```bash skip
./tut sync && ./tut lint
./tut run <id> --dry-run     # read what CI will execute
./tut run <id>               # or step through it with ./tut ui
```

## 8. Rules learned from CI

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
