# AGENTS.md — instructions for AI agents

This repository holds KServe tutorials whose READMEs are executed by CI and by
a local UI. It is maintained mostly by AI agents (Claude Code, Codex): you are
expected to know this repository better than the maintainer does. So the
rules and the reasons live in files you must read, not in anyone's memory, and
CI enforces them.

**First time here, or structural work?** Read [docs/handbook.md](docs/handbook.md):
what is built, the decisions already made, the code map, CI, and what is easy
to break. Then the document for your task below.

## Before you start: read the document for your task

| Your task | Read first (fully) |
|---|---|
| Write or edit a tutorial | [docs/authoring.md](docs/authoring.md) |
| Migrate a tutorial from `Jooho/kserve-tutorials-legacy` | [docs/migration-guide.md](docs/migration-guide.md), then docs/authoring.md |
| A CI run, scheduled run or canary failed | [docs/ci-playbook.md](docs/ci-playbook.md) |
| Groups, tags, collections, owners (`catalog/`) | docs/authoring.md § Groups, tags and collections |
| Change `envs/`, `lib/` (shared parts) | docs/authoring.md § Shared parts, then RFC §4.6 |
| Change `tools/`, `schema/`, rules or workflows | [docs/rfc/0001-repository-structure.md](docs/rfc/0001-repository-structure.md) |
| Release, `stable` branch, Makefile or release workflow | [docs/release.md](docs/release.md) |
| Plan or pick up structural work | [docs/handbook.md](docs/handbook.md), then [docs/backlog.md](docs/backlog.md) — known problems with evidence; update an item's status when you finish it |
| Translate a tutorial | docs/authoring.md § Translations |
| Make or update a tutorial's AI explainer (teaching page with diagrams) | [docs/explainer.md](docs/explainer.md) |
| Anything else / you are unsure | [docs/handbook.md](docs/handbook.md) |

If the document and the code disagree, stop and report it; do not guess.

## Commands

`make help` lists the same commands as make targets (`make check` = lint +
tests + site, what CI checks without a cluster; `make precommit` = `./tut sync`
first, then `make check`, then the translations still to do;
`make precommit TRANSLATE=1` also drafts the missing ones with `TUT_AI`).

```bash skip
make setup                  # .venv with the toolkit's Python packages (Python 3.11+)
make doctor                 # Docker / host / environment check
make config CLUSTER=<name>  # personal settings in .tut.env (shell > .tut.env > default)
make tools ENV=<name>/vN    # download an environment's CLI tools ahead of time (optional)
make new T=<id> [TITLE=".."] [OWNER=<handle>]   # new tutorial from tutorials/_template/ (= ./tut new)
./tut draft <folder> [--id <id>] [--collection <c>]   # AI (TUT_AI=claude|copilot|codex) drafts a tutorial from tested scripts/manifests
./tut sync                  # regenerate <!-- tut:... --> regions — after every edit
./tut lint                  # all rules; must end with "0 error(s)"
./tut run <id> --dry-run    # the exact script CI will execute
./tut run <id>              # execute for real (Docker + kubectl + Kind)
./tut ui                    # local web UI: run a tutorial step by step
./tut list [--tag T] [--status S] [--collection C]   # one line per tutorial
./tut show <id>                     # everything about one tutorial
./tut project [--get <key>]         # what project.yaml says (product name, version_var, ...)
eval "$(./tut completion)"          # Tab completion for ./tut in this shell
./tut translation              # state of every translation + next step
./tut translation draft <id> ko   # AI draft via TUT_AI=claude|copilot|codex|cmd:...
./tut translation todo         # only what needs work (make precommit prints it)
./tut affected --base origin/main   # which tutorials CI will execute for this branch
./tut translation mark <id> ko # after reviewing: matches the current README.md
./tut explain draft <id>      # AI explainer: TUT_AI walks the tutorial on a cluster, writes explainer/ (15-30 min)
./tut explain start|next|probe|stop <id>   # the same walk by hand / by you as the agent (docs/explainer.md)
./tut explain check <id>      # explainer checks (X001-X005); ./tut explain mark <id> after a person read it
./tut explain review <id>     # other AIs (TUT_AI_REVIEW=claude,codex; else TUT_AI) check it against the walk's evidence, each on its own
PYTHONPATH=tools python3 -m pytest -q tools/tests   # when changing tools/
```

## Hard rules (never break these)

1. **A tutorial is self-contained.** A tutorial change touches only
   `tutorials/<id>/`. Never read another tutorial's files or rely on state
   another tutorial created.
2. **Reuse through versioned parts.** Shared scripts live in `lib/<name>/vN/`,
   clusters in `envs/<name>/vN/`. Declare what you use in `tutorial.yaml`
   (`env:`, `uses:`). A part with `frozen: true` never changes: create `vN+1`.
3. **README.md is the source.** Everything a reader runs is a role-tagged
   block (`bash run|verify|cleanup|skip`). No separate scripts duplicating steps.
4. **Never edit inside `<!-- tut:... -->` … `<!-- /tut -->`.** Change the
   source and run `./tut sync`.
5. **No hard-coded KServe versions.** Use `$KSERVE_VERSION`.
6. **Every checkable claim gets a `verify` block.**
7. **Do not weaken a rule, skip a test or disable a check to get green.**
   Rule changes go in `tools/tut/lint.py` with tests and need explicit human
   approval.
8. **Do not set `status: stable`** unless CI (or `./tut run <id>`) passed
   with that exact README.
9. **Never push to `Jooho/kserve-tutorials-legacy`** (read only).
10. **Install nothing system-wide.** The toolkit lives in `.venv`; tutorial
    CLI tools are pinned per environment in `envs/<name>/vN/tools.env` and
    installed into `.tools/<tool>/<version>/` by the environment's setup.
    Docker, git and curl are the user's; we only check them (`./tut doctor`).
11. **Tags come from `catalog/tags.yaml`, groups from `catalog/groups.yaml`** (add a new one there, with group and
    description, only if none fits). `.github/CODEOWNERS` is generated from
    `owners` fields by `./tut sync`: never edit it by hand.
12. **Never push to `stable`.** Only the release workflow moves it, and only
    forward to a fully verified commit of `main` (docs/release.md).

## How to work (every task)

1. **New branch from the latest `main`** for each change (`git fetch origin`
   first). Never base a branch on another unmerged branch.
2. **One feature per PR.** A PR's base is always `main`.
3. **Commit only after `make precommit`** passes (0 errors). For a refactor,
   prove it changes nothing: compare `./tut run <id> --dry-run`, `./tut list`
   and the site before and after.
4. **Open a PR, merge, push to `stable` or change repository settings only when
   the maintainer asked for it in the conversation.** Approval for one PR does
   not carry over to the next unless they said so.
   Before you ask, go through the tech lead (next section).
5. **When CI fails, find the root cause** (docs/ci-playbook.md). Never re-run
   hoping it passes more than once; never weaken a check.
6. **Finish with the knowledge in the repository:** backlog item, lesson, or a
   line in docs/handbook.md § Decisions — not only in the chat.

## The tech lead comes before the maintainer

The `tech-lead` agent (`.claude/agents/tech-lead.md`) is the maintainer's
stand-in: it looks at work the way they do, from the seat of the person who
will use it. Its notebook, `.claude/tech-lead/learned.md`, holds what the
maintainer has answered so far.

- **Before you ask the maintainer to approve a plan, a commit, a PR or a
  merge**, give it to the tech lead first. Claude Code: call the `tech-lead`
  subagent. Other agents (Codex, Copilot) have no subagent: read both files and
  do its review yourself as a separate pass before you report, and say in your
  report that the review was your own, not an independent one.
- Answering a question the maintainer asked, and small confirmations, need no
  gate.
- Fix what it sends back and ask it again. What reaches the maintainer is its
  verdict and its questions, not your own summary.
- **Carry its questions to the maintainer word for word.** Do not answer them
  yourself and do not add your own.
- **When the maintainer answers, or corrects or rejects something, call the
  tech lead again with their words** so it writes them into its notebook. Other
  agents: append the entry yourself, in the format under "Learning from the
  answers" in tech-lead.md. Next time that kind of question is answered from
  the notebook.
- The notebook is committed. A change to it travels with the PR that is in
  progress when the maintainer answered; it does not make that PR run more
  tests.
- Git and shared-state actions still need the maintainer's own word, whatever
  the tech lead says.
- A lesson that is a rule for everyone belongs in this file or in docs/, not
  only in the notebook; the tech lead says so when it sees one.

## Plans become issues, issues become work

The `project-planner` agent (`.claude/agents/project-planner.md`) looks at the
whole project, from the UI to what a public repository needs to be safe, and
proposes a short list of small plans. Nothing it proposes is work until the
maintainer says so.

1. **Plan.** Call the planner. Its list goes to the tech lead first (too big?
   already known? evidence?), then to the maintainer with the tech lead's
   verdict.
2. **Approve.** The maintainer says which proposals may become issues. Only
   then is the planner called again to file them (`gh issue create`, label
   `plan`), with the maintainer's approval quoted in the call. The first time,
   the agent creates the label once: `gh label create plan`.
3. **Work, one issue at a time.** Ask the tech lead to run an issue: it checks
   that the issue is still true and writes the brief. Do the work on a new
   branch from the latest `main`, one issue per PR ("Closes #<n>" in the PR
   text).
4. **Check.** The result goes back to the tech lead as any work does, then to
   the maintainer for the PR and the merge.

- docs/backlog.md stays the record of problems with their evidence; an issue is
  the order to work on one of them. When an issue from the backlog is done,
  update the backlog item as before.
- Other agents (Codex, Copilot): read the planner's file and follow it
  yourself; filing issues still needs the maintainer's approval in the
  conversation.

## Translations

When you change a tutorial's README.md, bring its translations along in the same
PR: translate the changed parts yourself or run `./tut translation draft`, review
the result, and only then `./tut translation mark`. Never mark a translation you
did not check against the English text.

## Explainers: offer them, then do them unattended

The maintainer and other users do not know explainers exist; you tell them.
An explainer (`tutorials/<id>/explainer/`, docs/explainer.md) is a teaching
page with diagrams and animated flows, written by an AI from a step-by-step run
of the tutorial on a real cluster. It is labelled AI-written, never executed,
and never triggers CI e2e.

- After you migrate or create a tutorial, or when a tutorial has none or its
  explainer is behind (`./tut explain status <id>`, lint X005), offer it in two
  or three sentences: what it is, that it needs a cluster and 15-30 minutes,
  and that it does not touch the README or CI.
- When the user says yes ("go", "진행해줘"), do the whole thing without asking
  again: `./tut explain start/next/probe/stop`, write the files, `./tut explain
  check`, `./tut explain review`, then decide every finding (fix it, or reject
  it with the reason, in notes.md). Then report what you verified, what differs
  from the README, and what they should look at.
- `./tut explain mark` records that a person read the explainer. Never run it
  on your own judgment. Run it only when the maintainer says they read it
  ("I read it, mark it"), for the languages they name.
- Explainer changes go in their own PR (no tutorial change in it).

## Leave the repository smarter than you found it

When you find a problem you cannot fix in the current task, add it to
docs/backlog.md with the evidence instead of leaving it in a chat.

When you fix a failure that a rule could have prevented:

1. Add a lesson to **docs/authoring.md § Rules learned from CI** (what
   happened, the rule, the evidence link).
2. If the rule can be checked mechanically, add it to `tools/tut/lint.py` with
   a test in `tools/tests/`, and reference the rule code in the lesson.

Before finishing any task: `make precommit` (`./tut sync`, then lint, tests
and site: the checks CI runs without a cluster).
