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
| Change `envs/`, `lib/` (shared parts) | docs/authoring.md § Shared parts, then RFC §4.6 |
| Change `tools/`, `schema/`, rules or workflows | [docs/rfc/0001-repository-structure.md](docs/rfc/0001-repository-structure.md) |

If the document and the code disagree, stop and report it; do not guess.

## Commands

```bash skip
pip install -r tools/requirements.txt        # Python 3.11+
./tut sync                  # regenerate <!-- tut:... --> regions — after every edit
./tut lint                  # all rules; must end with "0 error(s)"
./tut run <id> --dry-run    # the exact script CI will execute
./tut run <id>              # execute for real (Docker + kubectl + Kind)
./tut ui                    # local web UI: run a tutorial step by step
./tut list
./tut translation mark <id> ko
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

## Leave the repository smarter than you found it

When you fix a failure that a rule could have prevented:

1. Add a lesson to **docs/authoring.md § Rules learned from CI** (what
   happened, the rule, the evidence link).
2. If the rule can be checked mechanically, add it to `tools/tut/lint.py` with
   a test in `tools/tests/`, and reference the rule code in the lesson.

Before finishing any task: `./tut sync && ./tut lint` and, if you changed
`tools/`, the tests.
