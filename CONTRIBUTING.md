# Contributing

Thanks for helping. Most of the work here is done by AI coding agents (Claude
Code, Codex) that follow [AGENTS.md](AGENTS.md); people steer them, review the
result and decide. Both follow the same documents, and CI enforces the rules
either way.

## Set up once

You need Docker (running, about 4 CPU / 16 GiB for it), git, curl and Python
3.11+. Nothing is installed system-wide.

```bash skip
make setup                     # .venv with the toolkit
make doctor                    # is this machine ready? (Docker, resources, tools)
./tut config TUT_AI=claude     # your AI CLI (claude | codex | copilot | cmd:...), kept in .tut.env
```

If you already use a kind cluster called `kind`, add `KIND_CLUSTER_NAME=tut`
to the same `./tut config` command.

## Working with an AI agent

Start the agent in the repository root. Claude Code reads `CLAUDE.md`, which
imports `AGENTS.md`; Codex reads `AGENTS.md`. Then ask for the task in your own
words, for example:

- "Turn ~/work/llmisvc-autoscaling (my tested scripts) into a tutorial in the
  llmisvc-deep-dive collection." The agent runs `./tut draft`, which uses your
  `TUT_AI`, then finishes the result and checks it.
- "Migrate `llmisvc/02-request-flow` from the legacy repository." The agent
  follows docs/migration-guide.md.
- "The weekly run failed on inferencegraph-ensemble; find out why." The agent
  follows docs/ci-playbook.md.

What to expect from the agent, and what to check in its PR:

| The agent should | You check |
|---|---|
| work on a new branch from `main`, one feature per PR | the PR touches only what the task needs |
| run `make precommit` before committing | CI `check` is green |
| run the tutorial (`./tut run <id> --twice`) or let CI's e2e do it | CI `e2e / <id> @ <version>` is green |
| say what it changed in a tested command, and why | the tutorial still teaches what you meant |
| leave a lesson or backlog item for problems it found | `docs/` changed with the code |
| not merge, push to `stable` or change settings unless you asked | — |

## Working by hand

```bash skip
make new T=<id> TITLE="..." OWNER=<github-handle>   # from the template
#   write tutorials/<id>/README.md and tutorial.yaml (docs/authoring.md)
make precommit                                    # sync, lint, tests, site
./tut ui                                          # run it step by step in the browser
./tut run <id> --twice                            # what CI runs
```

Or start from what you already tested: `./tut draft <folder> --id <id>
--owner <you>` (docs/authoring.md § `./tut draft`).

## Translations

English `README.md` is the source. When it is ready, translations are drafted
by your AI and reviewed by a person or an agent before they are marked:

```bash skip
make precommit TRANSLATE=1             # drafts every missing / outdated translation with TUT_AI
#   review tutorials/<id>/README.ko.md
./tut translation mark <id> ko         # only after the review
```

`make precommit` without `TRANSLATE=1` never translates; it only lists what is
missing.

## Where things are explained

| Topic | Document |
|---|---|
| How the repository fits together, decisions, code map | [docs/handbook.md](docs/handbook.md) |
| Writing or changing a tutorial | [docs/authoring.md](docs/authoring.md) |
| Moving a tutorial from the legacy repository | [docs/migration-guide.md](docs/migration-guide.md) |
| A CI run failed | [docs/ci-playbook.md](docs/ci-playbook.md) |
| Releasing (`main` → `stable`) | [docs/release.md](docs/release.md) |
| Known problems and next work | [docs/backlog.md](docs/backlog.md) |
| Why it is built this way | [RFC 0001](docs/rfc/0001-repository-structure.md) |

`make help` lists every command.
