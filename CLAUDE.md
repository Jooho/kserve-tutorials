# Instructions for coding agents

This repository holds KServe tutorials whose READMEs are executed by CI. The
design is in `docs/rfc/0001-repository-structure.md`; read it before structural
changes. These rules are not optional: CI enforces them.

## Commands

```bash skip
./tut sync                  # regenerate <!-- tut:... --> regions — run after every edit
./tut lint                  # all rules; must end with "0 error(s)"
./tut lint --base origin/main
./tut run <id> --dry-run    # the exact script CI will execute
./tut run <id>              # execute for real (Docker + kubectl + Kind)
./tut list
./tut ui                    # local web UI: run tutorials step by step in a real shell
./tut translation mark <id> ko
PYTHONPATH=tools python3 -m pytest -q tools/tests   # when changing tools/
```

Requires Python 3.11+, `pip install -r tools/requirements.txt`.

## Hard rules

1. **A tutorial is self-contained.** Only touch `tutorials/<id>/` for a
   tutorial change. Never reference files of another tutorial and never rely
   on state another tutorial created.
2. **Reuse scripts through modules.** A script two tutorials need goes into
   `lib/<name>/vN/`, is listed in each tutorial's `uses`, and is called as
   `"$TUT_LIB/<name>/vN/<script>"`. Never call an undeclared module. A frozen
   module never changes: create `vN+1`.
3. **Frozen env profiles never change.** If `envs/<name>/vN/profile.yaml` has
   `frozen: true`, create `vN+1` instead and move tutorials one by one.
4. **README.md is the source.** Everything a reader runs is a role-tagged
   block (`bash run|verify|cleanup|skip`). Do not create separate scripts that
   duplicate README steps.
5. **Never edit inside `<!-- tut:... -->` … `<!-- /tut -->`.** Change the source
   (`tutorial.yaml`, the included file) and run `./tut sync`.
6. **No hard-coded KServe versions** in prose or commands. Use
   `$KSERVE_VERSION`; versions live in `tutorial.yaml`.
7. **Add a `verify` for every claim** the text makes that can be checked.
8. **Pin images.** No `latest`.
9. **Translations follow `README.md`**: same shell blocks in the same order;
   run `./tut translation mark` only after the translation is actually
   updated.
10. **Do not weaken a rule to make lint pass.** Rule changes go in
   `tools/tut/lint.py` with tests in `tools/tests/` and need explicit approval.
11. **Do not set `status: stable`** unless `./tut run <id>` or CI has passed
    with that exact README.

## Migrating a tutorial from the old repository

The old tutorials live in `Jooho/kserve-tutorials-legacy` (read only; never
push there).

Follow `docs/migration-guide.md` step by step, one tutorial per branch / PR.
`tutorials/llmisvc-anatomy` is the reference result. Report anything that does
not fit the rules instead of working around it.

## When a canary / scheduled run fails

The issue names the tutorial, KServe version and the failing README line.
Fix only that tutorial. If the cause is a KServe change that removed a feature,
propose either an update or `status: archived` with a `deprecation` block, and
explain the choice in the PR.
