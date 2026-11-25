# Migration guide: moving an existing tutorial into this repository

One tutorial per pull request. `tutorials/llmisvc-anatomy` is the reference result: it was migrated from `llmisvc/01-anatomy` in the old repository ([`Jooho/kserve-tutorials-legacy`](https://github.com/Jooho/kserve-tutorials-legacy)) with these exact steps, so compare against it when in doubt.

## 0. Before you start

- Read [docs/authoring.md](authoring.md) — the rules, including the ones learned from CI.
- Make sure `./tut lint` passes on `main`.
- Pick the tutorial's id: lowercase, hyphenated, descriptive, without numbers (`llmisvc-request-flow`, not `02-request-flow`). Order is expressed by the collection's member list (`catalog/collections/`).

## The usual way: `./tut draft`, then steps 1–8 as the checklist

Point `./tut draft` at the old tutorial's folder (in a clone of the legacy repository). Your AI CLI (`TUT_AI`) writes `tutorials/<id>/` in this format, using the rules below, the reference tutorial and the reusable parts:

```bash skip
./tut draft ../kserve-tutorials-legacy/llmisvc/02-request-flow \
  --id llmisvc-request-flow --owner <github-handle> --collection llmisvc-deep-dive
```

Then read `build/draft/<id>/report.md` (lint, files changed elsewhere, old commands missing from the new README) and `notes.md` (what the AI changed and why). Use the steps below to check and finish the result. Doing it by hand is the same steps, in order.

## 1. Inventory the old tutorial

Write down, before changing anything:

| Question | Where it goes |
|---|---|
| Which KServe version does it install / assume? | `versions.default`, `versions.tested` |
| How is the cluster created and KServe installed? | Choose or create an env profile (step 2) |
| What does it need from a previous tutorial? | Must be re-created inside this tutorial (step 4) |
| Which KServe features does it exercise? Level? | `tags` (from `catalog/tags.yaml`) |
| GPU? CPU / memory? | `requires` |
| Which languages exist? | `langs` |
| Which files does the text show inline? | Must become `tut:include` (step 5) |
| Anything internal (registries, hostnames, tokens)? | Remove before committing |

Before you ask the maintainer a design question about the old tutorial (where something should be installed, whether a part is shared), read that tutorial's step and its Cleanup section: they usually answer it already.

## 2. Choose the environment profile

- If an existing profile builds the cluster the tutorial needs, use it.
- If the tutorial only needs a small add-on (Prometheus, a CRD, a Helm chart), install it **inside the tutorial** and remove it in its cleanup.
- Use `env: kind-kserve/v1` and pick the KServe parts in `env_options` (`types: [kserve|localmodel|llmisvc]`, `mode: standard|serverless`, `keda`); see `envs/kind-kserve/v1/README.md`. Only create a new profile (`envs/<name>/v1/`) when the cluster itself must differ in a way an option cannot express; keep `setup.sh` idempotent and pinned to `$KSERVE_VERSION`.
- Never edit a frozen profile; create the next version instead.

## 3. Create the directory

```bash skip
make new T=<id> TITLE="<English title>" OWNER=<github-handle>   # = ./tut new <id> ...
rm tutorials/<id>/manifests/example.yaml     # the template's example (./tut draft removes it for you)
```

Fill in `tutorial.yaml` (it starts as `status: draft`, English only). Pick `tags` from `catalog/tags.yaml` (one `level` tag at least) and set `owners`. If the old tutorial was part of a series, add it to the matching `catalog/collections/<id>.yaml` in reading order (the planned members are listed there as comments).

## 4. Rewrite the README

Decide what the tutorial teaches before converting a single command: write the "What you will learn" list for the top of the README (docs/authoring.md section 3). The old text is the starting material, not the bar: it often has the commands without saying what to look at or why. A migration that only converts commands is not done.

Map the old patterns to the new ones:

| Old pattern | New pattern |
|---|---|
| "Complete 00-setup first" | Delete. The generated `tut:setup` block does it. |
| `REPO_ROOT=...; cd ...; NS=kserve-demo` | Delete. `tut:setup` exports `NS`, `REPO_ROOT`, `KSERVE_VERSION` and `cd`s into the tutorial. |
| `git clone kserve` (master) / `curl .../master/...install.sh` | Belongs in an env profile, pinned to `$KSERVE_VERSION`. |
| Hard-coded `v0.18.0` in text or commands | `$KSERVE_VERSION` in commands; the header shows the tested versions. Historical mentions: add `<!-- tut-allow-version -->` to the line. |
| `kserve-demo` in URLs / names | `$NS` |
| "Leave everything for the next demo" | Delete. Add a `cleanup` block. The next tutorial creates what it needs. |
| Uses resources created by a previous tutorial | Copy that manifest into this tutorial's `manifests/` and apply it here. |
| `watch ...`, `kubectl port-forward ... &`, editors, anything interactive | `bash skip`, followed by a non-interactive `verify` equivalent where it matters. |
| A command whose output is shown with no word on what matters in it | Say what to look at, the value from your run, and why it is that value (docs/authoring.md section 3). |
| "You should see X" with no check | Keep the sentence and add a `verify` block that checks X. |
| `sleep 60` while waiting | `kubectl wait ...` or `verify retry=N delay=S`. |
| Inline copy of a YAML/py/sh file | `<!-- tut:include manifests/<file> -->` + `<!-- /tut -->`. |
| The same helper logic in several tutorials (URL lookup, waiting, request + check) | A script in a module under `lib/<name>/vN/`, listed in `uses`, called as `"$TUT_LIB/<name>/vN/<script>"`. Check existing modules first. |
| Links to tutorials that do not exist yet | Remove the link (plain text), or lint fails (D004). |
| Separate `scripts/1.prepare.sh`, `2.deploy.sh` that the README tells you to run | Prefer inlining the commands as `run` blocks so the README stays the source. Keep a script only if it is long and self-explanatory, and show it with `tut:include`. |

Every shell block gets a role: `run`, `verify`, `cleanup` or `skip`.

A good `verify` checks what the reader is supposed to have learned, not only that a command ran: resource counts, container names, a field value, a request that returns a valid response.

## 5. Move files

- Manifests → `manifests/`, images → `images/`, helper code → a directory of your choice inside the tutorial.
- Pin every container image (M001).
- Then run:

```bash skip
./tut sync
./tut lint
./tut run <id> --dry-run | less    # read the script CI will execute
./tut ui                            # step through it in the browser
```

## 6. Run it

```bash skip
./tut run <id>                      # needs the env prerequisites (Docker, kubectl, ...)
./tut run <id> --keep               # keep resources to debug a failure
```

On failure the runner prints the README line of the failing block.

## 7. Translation (if the old tutorial had one)

1. `./tut translation draft <id> ko` (or `make precommit TRANSLATE=1`) — an AI draft with the same blocks and `tut:` regions as `README.md` (without an AI CLI: copy `README.md` to `README.ko.md`).
2. Bring in the old KO wording where it is better (and translate code comments); keep the shell blocks one to one with `README.md` (same order, roles, code).
3. `./tut translation mark <id> ko` (also adds `ko` to `langs`)
4. `./tut lint` (D011 checks the structure).

## 8. Open the pull request

- One tutorial per PR. CI runs lint, then executes only this tutorial.
- When CI is green, change `status: draft` → `stable` in the same PR or a follow-up. Stable needs frozen parts: the env and every `uses` module must have `frozen: true` [T007, L004] (backlog D2: freezing `kind-kserve/v1` and `llmisvc/v1` is still open).

## Checklist

- [ ] `tutorial.yaml` complete; `status: draft`
- [ ] No dependency on another tutorial's state
- [ ] Every shell block has a role; interactive commands are `skip`
- [ ] At least one meaningful `verify` and a `cleanup`
- [ ] No inline copies of files; `tut:include` instead
- [ ] No hard-coded KServe versions; images pinned
- [ ] No internal hostnames, registries, tokens
- [ ] `make precommit` clean (sync, lint, tests, site)
- [ ] `./tut run <id>` passes locally (or CI is green)
- [ ] Translation marked, if any
