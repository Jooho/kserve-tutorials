# RFC 0002: Tutorial revisions, the CI version window, and new KServe versions

| | |
|---|---|
| Status | Decided 2026-11-25 (section 3); implemented except the pilot (section 9, step 4) and "last verified" dates (backlog D6) |
| Author | @Jooho |
| Created | 2026-11-26 |
| Closes | backlog C1, C8 |

## 1. Summary

When a new KServe version changes an API, a tutorial has to change, and the changed tutorial no longer runs on the older versions. Readers on those versions must still be able to read and run the tutorial as it was. So the old content stays in the tutorial's own directory as a frozen **revision** (`tutorials/<id>/revisions/rN/`), and the current tutorial moves to the new version. The UI, the site and `./tut run --version` pick the revision that was tested with the reader's version.

CI runs two versions per tutorial (N, the newest KServe version this repository moves to, and N-1, its newest tested version below N). New KServe releases reach `versions.tested` through a bot PR that a person merges; tutorial ideas for new features become GitHub issues. `stable` moves once a month (the schedule is off until a first dry run). No AI runs in GitHub Actions.

## 2. Motivation

- Today a tutorial has one README for every version in `versions.tested`. When KServe v0.20 removes something v0.18 needs, the only choices are to keep the README on the old version or to break it for old readers (backlog C1; KServe master already removed the scheduler's tokenizer sidecar that `llmisvc-anatomy` explains).
- A reader on an older KServe should not have to find an old git commit to read the tutorial that matches their cluster.
- CI cost grows with tutorials x versions; one LLM tutorial is about 10 minutes.

## 3. Decisions (the maintainer's, 2026-11-25)

| Question | Decision |
|---|---|
| How does one tutorial carry content that differs per version? | Per-tutorial revisions. Not per-version blocks inside a README, not release branches per KServe version (RFC 0001 section 4.4 stays: no release branches) |
| Keep one README true for old and new versions when possible? | No. A change made because of a new KServe version always moves the old versions to a revision |
| May a frozen revision be fixed (typo, broken link)? | No exceptions, like frozen envs and lib parts. Revisit if a fix is ever needed |
| Which versions does CI run? | Two per tutorial: N = the newest KServe release (upstream), or the version the maintainer pins as `latest` in project.yaml (2026-11-26: v0.20.0 while v0.21.0 is out). N-1 = the newest version in that tutorial's `tested` (its revisions included) below N: tested [v0.17, v0.18, v0.20] with N = v0.20 runs v0.18 and v0.20. A tutorial without N runs only that N-1 (2026-11-26) |
| A tutorial that skipped versions (tested v0.18 and v0.21, nothing for v0.19/v0.20)? | Tell the maintainer; with their permission the old versions go to a revision and leave the current `tested` (`./tut revision keep`). Until then CI runs it on N and the version before the gap. The maintainer moves tutorials one version at a time (2026-11-26) |
| Who adds a new KServe version to `versions.tested`? | A bot PR when the canary passes; a local agent adds the version-scout report; the maintainer merges |
| AI in GitHub Actions? | Never (there is no API key). Every AI step runs locally |
| Tutorials for new features of a release? | A new `feature-scout` agent (local) files one GitHub issue per candidate, label `tutorial-proposal`; the maintainer approves on the issue |
| The `stable` branch? | Kept. The release workflow runs once a month (off until a first dry run, 2026-11-26), skips when `main` has no new commit, opens an issue when verification fails |

Interpretations written down here (correct them if they are wrong): "the CI window" of a tutorial is its N and N-1 as defined in the table (corrected by the maintainer on 2026-11-26: N-1 is the tutorial's own previous tested version, not the previous KServe minor); the window applies to PR CI, the weekly run and releases; a reader's version matches an entry by minor (v0.19.2 reads the content tested as v0.19.x).

Sections 4-9 are the design proposed by the agent from these decisions, not the maintainer's words: the layout, `revision start` copying from the base branch, shared steps and generated regions, minor matching, the lint rules, the label name `tutorial-proposal` and its issue fields, the "new release vX" issue, and the explainer exception in section 4. Details may change in their implementation PR.

## 4. Layout

```text
tutorials/<id>/
  tutorial.yaml          versions.tested [v0.20.0], default v0.20.0
  README.md, README.ko.md, explainer/, manifests/, ...      current content
  revisions/
    r1/                  frozen copy of the tutorial as it was before the v0.20 change
      tutorial.yaml      versions.tested [v0.18.0, v0.19.0], default v0.19.0, env/uses as they were, frozen: true
      README.md, README.ko.md, explainer/, manifests/, ...
```

- A revision is inside `tutorials/<id>/`, so hard rule 1 (self-contained) holds.
- `r1`, `r2`, ... in order; a revision never changes after it is created.
- The copy includes translations and the explainer as they were. This is the one case where explainer files change in the same PR as a tutorial; AGENTS.md ("Explainer changes go in their own PR") names the exception.

## 5. A version-driven change

```bash skip
./tut revision start <id>   # copy the tutorial as it is on the base branch to revisions/rN,
                            # set the current tested/default to the new version
# edit the tutorial for the new version, ./tut run <id>, make precommit
# one commit: the new revision and the change together
```

- Freeze first, then edit: no CI round trip to find out that the old version broke.
- `revision start` copies from the base branch (`origin/main`), not from the working tree, so the revision is exactly what was verified.
- A change that is not about a version (typo, more explanation) gets no revision; PR CI runs the tutorial on every in-window version in `tested`.

### Shared steps

A `tut:define` in one tutorial is copied into others by `./tut sync` (`llmisvc-anatomy` defines `llmisvc-demo-model`; `llmisvc-request-flow` and `llmisvc-monitoring` use it).

- `./tut sync` never writes into `revisions/`. A revision holds the expanded text as it was, so its `tut:use` regions need no definition.
- When a definition changes because of a version, every tutorial that uses it changes too, so each of them needs `revision start` in the same PR. `./tut revision start <id>` names the users of the tutorial's definitions; `--with-users` starts them as well.

### Generated regions

`tut:setup`, `tut:header` and `tut:catalog` are regenerated by sync. Revisions are skipped by sync, so their generated regions stay as they were and the frozen check does not fire when `generate.py` or the catalog changes. The current README's `tut:header` gets one generated line per revision ("KServe v0.18-v0.19: revisions/r1/"), so a reader on GitHub can find it.

## 6. Version resolution

The same rule everywhere: `./tut run <id> --version v`, `./tut ui`, the static site, `catalog.resolve` (collections), `./tut matrix`, `./tut affected` and the release verdict.

```text
1. the current tutorial's tested has v (by minor)  -> current
2. a revision's tested has v (by minor)            -> that revision
3. neither                                         -> "not available for KServe v"
```

`archived` (RFC 0001 section 4.5) stays what it is: a whole tutorial that is no longer recommended, with a `deprecation.replacement`. A revision is an older form of a tutorial that is still current.

## 7. Lint

| Rule | Checks |
|---|---|
| R001 | a revision's `tutorial.yaml` is valid, `frozen: true`, same id, default in tested; `frozen` only in revisions |
| R002 | a frozen revision did not change (compared with `--base`, like E002 and L003) |
| R003 | a revision references only frozen env and lib parts |
| R004 | a version removed from `versions.tested` (compared with `--base`) must be in a revision of that tutorial |
| R005 | one version is tested by one variant of a tutorial |

## 8. CI, releases and new versions

### Window

- PR CI: a changed tutorial runs on each in-window version in its `tested`, and a new or touched revision on its own versions.
- Weekly: every current tutorial and revision, on its in-window versions.
- Release: the same set. Out-of-window versions stay in `tested`; they are not run and are shown as "last verified <date>, <commit>" once results are recorded (backlog D6); `./tut matrix --out-of-window` lists them.
- N is `./tut latest`: `latest` in project.yaml when the maintainer pins it, else the newest release of the upstream (`project.yaml upstream`, `gh api repos/<upstream>/releases/latest`). CI sets `TUT_LATEST_VERSION` from it; the weekly canary and the `new-release` issue use the same version. A tested version above the pin still counts as N, so it keeps running. Offline without a pin (tests) N is the newest version any tutorial tests. N-1 is per tutorial: the newest minor in its `tested` (revisions included) below N. A tutorial that does not test N yet runs only that one. Older versions stay in `tested` ("last verified"). A current tutorial that skipped versions (a gap between its tested minors, like v0.18.0 and v0.20.0) is listed by `./tut revision todo` (also printed by `make precommit`), and the weekly run keeps one issue (label `ci-window`) with that list, closed when it is empty. The maintainer decides, then a local agent runs `./tut revision keep <id>`: the copy from the base branch becomes `revisions/rN/` with the versions before the gap, and the current tutorial drops them.

### A new KServe release

```text
weekly scheduled run (no AI)
  canary pass -> bot PR: add the version to tested  -> local agent adds the version-scout report -> maintainer merges
  canary fail -> issue per tutorial                 -> local agent: fix, with `revision start` when the change is version-driven
  first sight of the version -> issue "new release vX"  -> local agent runs feature-scout -> tutorial-proposal issues
```

The version is N (`./tut latest`): a pinned `latest` holds the canary at that version until the maintainer moves the pin.

- The bot PR needs a token that triggers CI (a PAT or a GitHub App; a PR opened with `GITHUB_TOKEN` does not run workflows). The maintainer sets it up as a repository secret.
- The handbook decision "version-scout before a version is added to tested" holds: the report is on the PR before it is merged.
- The canary runs stable and deprecated tutorials only; drafts get new versions from their author.
- Filing issues and commenting are GitHub writes: a local agent asks the maintainer each time (AGENTS.md "How to work" step 4).

### Tutorial proposals

One issue per candidate feature, label `tutorial-proposal`:

| Field | Content |
|---|---|
| Feature | name, upstream PRs and issues, release note line |
| User problem | what a user cannot do without it |
| Upstream evidence | upstream e2e tests and sample YAML (already tested manifests) |
| Needs | CRDs, feature gates, extra components, images and sizes |
| Runs on kind + CPU? | yes / no, and why |
| Existing tutorials | new tutorial, or a change to which one (and whether it needs a revision) |
| What you will learn | 3-5 points |
| Verify points | facts a run can check |
| env / lib | parts to use, parts that are missing |
| Estimate | run time, group, collection, level tag |
| Score | the criteria below |

Criteria: a feature users use (not an internal refactor); runs on CPU kind (GPU-only waits for backlog D7); API reasonably stable (alpha or behind a feature gate: flagged, lower priority); has a mechanism to teach, not only commands; does not overlap an existing tutorial. An approved issue becomes one tutorial PR, built by a local agent on kind (`./tut draft` needs tested scripts), with `status: draft`.

### Monthly release

`release.yml` gets a monthly schedule next to `workflow_dispatch`, turned off until a first dry run has passed (maintainer, 2026-11-26). A scheduled run publishes (not a dry run), skips when `main` has no commit since the last tag (no verification, no tag), and opens an issue when verification fails; nothing moves then. Tags `YYYY.MM.N` and GitHub Releases stay; `make release` by hand still works.

## 9. Rollout

Done in one change (the maintainer asked for one commit), except where noted.

1. This document; handbook decisions, backlog, AGENTS.md, ci-playbook section 5.
2. Schema (`revisions/`, `frozen`) and the lint rules of section 7, with tests.
3. `./tut revision start`, `keep` and `todo`, version resolution (section 6) in run, catalog, matrix, affected and release; sync skips `revisions/`; header link; the window in `plan.py` and docs/release.md; the explainer exception in AGENTS.md.
4. Pilot: move `llmisvc-anatomy` to the next KServe version with its first revision (backlog C2). Not done yet: it needs a version-scout report and a run on a cluster.
5. Bot PR workflow (`scheduled.yml` job `new-version`); it opens PRs once the repository secret `TUT_BOT_TOKEN` exists (until then it prints a notice).
6. UI and site: a "my KServe version" selector; the sidebar lists what is available for it, revisions labelled; content, run and explainer follow it; the matrix shows current or rN per cell.

Also: the monthly release schedule (`release.yml`), the `feature-scout` agent (`.claude/agents/feature-scout.md`) and the issue template (`.github/ISSUE_TEMPLATE/tutorial-proposal.yml`). "Last verified <date>, <commit>" for out-of-window versions needs recorded results (backlog D6); until then release notes mark them "not run".

## 10. Alternatives considered

| Alternative | Why not |
|---|---|
| Per-version blocks in one README | Hard to read for learners; verify blocks split by version |
| Release branches per KServe version | Rejected again (RFC 0001 section 4.4): ties all tutorials to one branch; the maintainer prefers per-tutorial revisions |
| Old content only in git tags | Readers would have to find the tag; the site and the UI would show only the newest content |
| Keep one README true for both versions when possible | Needs a judgement on every change; the fixed rule (always a revision) needs none |
