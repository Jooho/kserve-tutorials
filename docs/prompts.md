# Prompts for AI agents

Most work in this repository is done by an AI coding agent (Claude Code, Codex) in a clone of the repository. These prompts start the common tasks the same way every time: what to read, in which order, what to report after each step, when to stop and ask. Copy one, replace the `<...>` parts, and paste it as your first message.

Each prompt makes the agent read the repository's own documents (AGENTS.md, docs/handbook.md, ...), so a new session knows the rules even though it has no memory of earlier ones. Improve these prompts here when you find a better wording, so every session benefits.

## Filling in the `<...>` parts

| Placeholder | What to put there | How to find it |
|---|---|---|
| `<id>` of an existing tutorial | its folder name under `tutorials/` (= `id:` in its `tutorial.yaml`) | `./tut list` (first column), or `ls tutorials/` (not `_template`) |
| `<id>` of a new tutorial | a new name: lowercase letters, digits and `-` | `./tut list` to make sure it is not taken |
| `<collection>` | a file name in `catalog/collections/` without `.yaml`, or none | `./tut list --collection <name>` shows its members |
| `<github-handle>` | the owner's GitHub login | `catalog/maintainers.yaml` |
| `<tutorial>` (CI failure) | the id of the failed tutorial | the job name of the failed run |

Example: `./tut list` shows `llmisvc-request-flow`, so prompt 5 becomes "Make the AI explainer for tutorials/llmisvc-request-flow ...". Whether a tutorial already has an explainer: `./tut explain status <id>`.

In Claude Code you can also skip the exact id and say it in your own words ("make the explainer for request-flow"); the agent looks it up with `./tut list`.

| Task | Prompt |
|---|---|
| First session on a machine, or after a long break | [1. Build the context](#1-build-the-context) |
| Move a tutorial from `Jooho/kserve-tutorials-legacy` | [2. Migrate a tutorial](#2-migrate-a-tutorial) |
| A new tutorial from work you tested by hand | [3a. New tutorial from tested work](#3a-new-tutorial-from-tested-work) |
| A new tutorial written from scratch | [3b. New tutorial from scratch](#3b-new-tutorial-from-scratch) |
| A CI run, weekly run or canary failed | [4. Fix a CI failure](#4-fix-a-ci-failure) |
| Teaching page with diagrams for a tutorial (AI explainer) | [5. Make an explainer](#5-make-an-explainer) |

Before the first session: `make setup`, `./tut config TUT_AI=claude` (or `codex`), and for migrations a clone of the legacy repository next to this one (`../kserve-tutorials-legacy`).

## 1. Build the context

Changes nothing; the agent learns the repository and tells you what it understood.

```text
This is your first session in this repository. Do not change any file today:
only learn it and report back.

1. Read these documents completely:
   AGENTS.md, docs/handbook.md, docs/authoring.md, docs/migration-guide.md,
   docs/ci-playbook.md, docs/backlog.md
   (docs/rfc/0001-repository-structure.md: only the sections you need)
2. Check the machine. If something fails, do not fix it; report the cause:
   make setup, make doctor, make precommit,
   ./tut list, ./tut translation, ./tut affected --base origin/main
3. Read the reference tutorial tutorials/llmisvc-anatomy/ and compare its
   README with `./tut run llmisvc-anatomy --dry-run`: understand what the
   generated setup block does and what each verify block proves.
4. Report, briefly:
   - what this repository does, in three lines
   - the rules you must never break, in your own words
   - decisions already made that you must not re-open
   - the open work, top 5 from docs/backlog.md by priority
   - places where the docs and the code disagree, or that you did not understand
   - the results of doctor and precommit
```

## 2. Migrate a tutorial

One legacy tutorial per branch.

```text
Migrate ../kserve-tutorials-legacy/<path, e.g. llmisvc/02-request-flow> into this repository.
id: <e.g. llmisvc-request-flow>, owner: <github-handle>, collection: <e.g. llmisvc-deep-dive, or none>

First read AGENTS.md, docs/handbook.md, docs/migration-guide.md and
docs/authoring.md. Follow docs/migration-guide.md and report briefly after
each step.

Step 1. Inventory (before changing anything)
  - Read the whole legacy tutorial (README, README.ko, scripts, manifests,
    images) and fill in the table of migration-guide §1: KServe version, how
    it installs things, what it needs from earlier tutorials, GPU and
    resources, languages, anything internal (registries, hostnames, tokens).
  - Propose the env_options and lib modules to use, and any shared step
    (tut:use) to reuse. If it needs a new env or lib module, stop here and ask.

Step 2. Draft
  - git fetch origin, then a new branch migrate/<id> from origin/main
  - ./tut draft <legacy folder> --id <id> --owner <github-handle> [--collection <collection>]
  - Read build/draft/<id>/report.md and notes.md. For every input command
    missing from the tutorial, show in a table whether leaving it out was
    intended and why.

Step 3. Finish
  - The tutorial still teaches what the original taught: explanations, order,
    example output.
  - Every "you should see ..." has a verify block that checks it.
  - Every step is safe to run twice (D012); waits use kubectl wait or
    verify retry=N delay=S, never sleep.
  - Images pinned, $KSERVE_VERSION instead of a version, nothing depends on
    another tutorial's state.

Step 4. Verify
  - make precommit (must end with 0 errors)
  - Read ./tut run <id> --dry-run and report anything odd.
  - ./tut run <id> --twice. On failure follow docs/ci-playbook.md: find the
    root cause and fix it. If a rule could have prevented it, add a lesson to
    docs/authoring.md § Rules learned from CI and propose a lint rule.

Step 5. Translation (only if the legacy tutorial has Korean)
  - make precommit TRANSLATE=1 drafts README.ko.md. Bring in the legacy
    Korean wording where it reads better, check the blocks match the English
    one to one, and only then run ./tut translation mark <id> ko.

Final report: files changed, commands that differ from the original and why,
run results (with duration), TODOs left. Commit, but do not open a pull
request until I ask.

Stop and ask me when: a new env or lib module seems needed, it needs a GPU,
a file outside tutorials/<id>/ must change (other than the collection), you
want to change a lint rule, or the same failure persists after two fixes.
```

## 3a. New tutorial from tested work

The usual way to write a new tutorial: test it by hand first, then let the AI turn the folder into a tutorial.

```text
<folder> contains scripts, manifests and notes I tested by hand. Turn them
into a new tutorial.
id: <id>, owner: <github-handle>, collection: <collection, or none>
What the reader must learn: <one or two sentences, e.g. "when and how an
LLMInferenceService scales, and how to observe it">
Level: <beginner | intermediate | advanced>

First read AGENTS.md, docs/handbook.md and docs/authoring.md.
1. git fetch origin, then a new branch tutorial/<id> from origin/main.
2. ./tut draft <folder> --id <id> --owner <github-handle> [--collection <collection>]
3. Review build/draft/<id>/report.md and notes.md: list every place where a
   command I tested was changed or left out, with the reason.
4. Check that "what the reader must learn" is proven by verify blocks; add
   the ones that are missing.
5. make precommit, then ./tut run <id> --twice (on failure: docs/ci-playbook.md).
6. When the English is final: make precommit TRANSLATE=1 for the Korean
   draft; review it before ./tut translation mark <id> ko.
Commit, but do not open a pull request until I ask. Stop and ask before
creating a new env or lib module, or changing anything outside tutorials/<id>/.
```

## 3b. New tutorial from scratch

```text
Write a new tutorial from scratch.
id: <id>, owner: <github-handle>, collection: <collection, or none>
Topic: <topic>
What the reader must learn: <...>
Level: <beginner | intermediate | advanced>

First read AGENTS.md, docs/handbook.md and docs/authoring.md, and look at
tutorials/llmisvc-anatomy/ as the reference.
1. git fetch origin, then a new branch tutorial/<id> from origin/main.
2. make new T=<id> TITLE="<title>" OWNER=<github-handle>
3. Before writing, show me the outline: every step, what it does, and what
   its verify block proves. Wait for my OK.
4. Write it. Then make precommit and ./tut run <id> --twice.
5. Translation as in 3a, step 6.
Commit, but do not open a pull request until I ask.
```

## 4. Fix a CI failure

```text
The e2e for <tutorial> failed in <PR or Actions run link>.
Follow docs/ci-playbook.md. Do not re-run it hoping it passes. First report:
the failing block (README line), the root cause with the log lines that show
it, and where the fix belongs (tutorial, env or lib module).
After fixing: ./tut run <id> --twice, make precommit, and if a rule could
have prevented it, a lesson in docs/authoring.md § Rules learned from CI
plus a proposed lint rule (rule changes need my approval).
Commit on the PR's branch, or on a new branch from origin/main if it is a
failure on main; do not open a pull request until I ask.
```

## 5. Make an explainer

````text
Make the AI explainer for tutorials/<id> (docs/explainer.md). Work unattended
to the end: walk the tutorial on the cluster with ./tut explain start / next /
probe / stop, verify every fact you state, write explainer/index.md (and
index.ko.md if README.ko.md exists) with SVG diagrams and at least one animated
flow, run ./tut explain check, then ./tut explain review (decide every finding:
fix it or reject it with the reason in notes.md; no new walk; review once
more), then report: what you verified, what differs from the README, which
findings you rejected, and where I should look when I review. Do not mark it
reviewed.
````
