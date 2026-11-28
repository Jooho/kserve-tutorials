# CI playbook: when a tutorial run fails

Read this when a PR check or a release run fails. Goal: find the root cause, fix it in the right place, and leave a lesson behind.

## 1. Locate the failure

The job log names the exact block:

```text
✗ FAILED in tutorials/<id>/README.md:<line> (step <n>/<total> · <role>)
```

CI runs every tutorial twice in the same shell and cluster (`--twice`); a failure labelled `pass 2/2` means the step works on a clean cluster but not when repeated: make it idempotent (docs/authoring.md, D012) or mark it `once`.

`<total>` counts `run` + `verify` blocks; `cleanup` and `skip` are not numbered (cleanup runs last, after the numbered steps). The JSON report (`report.json` artifact) has the same `failed_at`.

## 2. Decide whose problem it is

| Failed in | Whose | Fix in |
|---|---|---|
| block 1 (`tut:setup`), lines prefixed `[env <name>/vN]` | the environment | `envs/<name>/vN/` (new version if frozen) |
| a block calling `$TUT_LIB/<module>/...` and the script itself errors | the module | `lib/<module>/` (new version if frozen) |
| any other block | the tutorial | `tutorials/<id>/` |
| only on the new KServe version (a PR that moves the pin) | KServe changed | `./tut revision start <id> --to <version>`, then update the tutorial as `status: draft`; or leave the version out of its `tested` |

## 3. Read the diagnostics

On failure CI keeps the resources and runs `.github/scripts/diagnose.sh` (step "Diagnostics (on failure)"): nodes, all pods, warning events, LLMInferenceServices, `describe` and logs for the tutorial's namespace and `kserve`. Typical causes:

| Symptom in diagnostics | Likely cause |
|---|---|
| Pod `Pending`, event `Insufficient cpu/memory` | requests too high for the runner |
| `ImagePullBackOff` / slow pulls | image tag, registry, image size vs timeout |
| `CrashLoopBackOff`, logs end abruptly / `Illegal instruction` | CPU features or memory limit (OOMKilled in `describe`) |
| init container still running | model or tokenizer download (network, size) |
| `connection refused` to a webhook | platform not ready (see authoring.md CI-001) |

## 4. Fix, prove, record

1. Reproduce if you can: `./tut run <id> --keep-on-failure`, or `./tut ui`.
2. Fix the root cause in the right place (step 2). "Flaky" is not a root cause; a job gets one re-run at most.
3. Never skip, delete or weaken a `verify` block to get green.
4. Push; CI re-runs only what your change affects (`./tut affected --base origin/main` shows it; docs/handbook.md § 7 has the rules).
5. Add a lesson to docs/authoring.md § Rules learned from CI, and a lint rule if it can be checked mechanically.

## 5. A new KServe version

There is no scheduled run and no canary: the maintainer starts the move (AGENTS.md "A new product version"). The PR that pins the new version (`./tut kserve-version <ver>`, `./tut tested add <ver> --all`) runs every tutorial on N and N-1. A failure on N-1 is a regression of what worked: treat it like any PR failure. A failure on N means KServe changed: keep the old versions as a frozen revision first (`./tut revision start <id> --to <version>`, docs/authoring.md "A new product version changes a tutorial"), fix the current tutorial, set `status: draft`, push to the same PR; a person reviews before `stable`. If a KServe feature was removed, propose either an update or `status: archived` with a `deprecation` block, and explain the choice. `./tut revision todo` lists tutorials that skipped versions (a gap in `versions.tested`): put it to the maintainer; with their word, `./tut revision keep <id>`.
