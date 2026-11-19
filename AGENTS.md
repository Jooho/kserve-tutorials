# AGENTS.md — instructions for AI agents

This repository holds KServe tutorials whose READMEs are executed by CI and by
a local UI. It is maintained mostly by AI agents, so the rules live in files
you must read, not in anyone's memory. CI enforces them.

## Before you start: read the document for your task

| Your task | Read first (fully) |
|---|---|
| Write or edit a tutorial | [docs/authoring.md](docs/authoring.md) |
| Migrate a tutorial from `Jooho/kserve-tutorials-legacy` | [docs/migration-guide.md](docs/migration-guide.md), then docs/authoring.md |
| A CI run, scheduled run or canary failed | [docs/ci-playbook.md](docs/ci-playbook.md) |
| Tags, collections, owners (`catalog/`) | docs/authoring.md § Tags and collections |
| Change `envs/`, `lib/` (shared parts) | docs/authoring.md § Shared parts, then RFC §4.6 |
| Change `tools/`, `schema/`, rules or workflows | [docs/rfc/0001-repository-structure.md](docs/rfc/0001-repository-structure.md) |
| Release, `stable` branch, Makefile or release workflow | [docs/release.md](docs/release.md) |
| Plan or pick up structural work | [docs/backlog.md](docs/backlog.md) — known problems with evidence; update an item's status when you finish it |

If the document and the code disagree, stop and report it; do not guess.

## Commands

`make help` lists the same commands as make targets (`make check` = lint +
tests + site, what CI checks without a cluster).

```bash skip
make setup                  # .venv with the toolkit's Python packages (Python 3.11+)
make doctor                 # Docker / host / environment check
make config CLUSTER=<name>  # personal settings in .tut.env (shell > .tut.env > default)
make tools ENV=<name>/vN    # download an environment's CLI tools ahead of time (optional)
./tut sync                  # regenerate <!-- tut:... --> regions — after every edit
./tut lint                  # all rules; must end with "0 error(s)"
./tut run <id> --dry-run    # the exact script CI will execute
./tut run <id>              # execute for real (Docker + kubectl + Kind)
./tut ui                    # local web UI: run a tutorial step by step
./tut list [--tag T] [--status S] [--collection C]   # one line per tutorial
./tut show <id>                     # everything about one tutorial
./tut translation              # state of every translation + next step
./tut translation init <id> ko # start one (copies README.md, adds ko to langs)
./tut translation mark <id> ko # after translating: matches the current README.md
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
11. **Tags come from `catalog/tags.yaml`** (add a new one there, with group and
    description, only if none fits). `.github/CODEOWNERS` is generated from
    `owners` fields by `./tut sync`: never edit it by hand.
12. **Never push to `stable`.** Only the release workflow moves it, and only
    forward to a fully verified commit of `main` (docs/release.md).

## Leave the repository smarter than you found it

When you find a problem you cannot fix in the current task, add it to
docs/backlog.md with the evidence instead of leaving it in a chat.

When you fix a failure that a rule could have prevented:

1. Add a lesson to **docs/authoring.md § Rules learned from CI** (what
   happened, the rule, the evidence link).
2. If the rule can be checked mechanically, add it to `tools/tut/lint.py` with
   a test in `tools/tests/`, and reference the rule code in the lesson.

Before finishing any task: `./tut sync && ./tut lint` and, if you changed
`tools/`, the tests.
