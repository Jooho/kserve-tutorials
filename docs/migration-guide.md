# Migration guide: moving an existing tutorial into this repository

One tutorial per pull request. `tutorials/llmisvc-anatomy` is the reference
result: it was migrated from `llmisvc/01-anatomy` in the old repository
([`Jooho/kserve-tutorials-legacy`](https://github.com/Jooho/kserve-tutorials-legacy)) with
these exact steps, so compare against it when in doubt.

## 0. Before you start

- Read [RFC 0001](rfc/0001-repository-structure.md) §4.6–4.8 (profiles,
  independence, executable documents).
- Make sure `./tut lint` passes on `main`.
- Pick the tutorial's id: lowercase, hyphenated, descriptive, without numbers
  (`llmisvc-request-flow`, not `02-request-flow`). Order is expressed with
  `series.order`.

## 1. Inventory the old tutorial

Write down, before changing anything:

| Question | Where it goes |
|---|---|
| Which KServe version does it install / assume? | `kserve.default`, `kserve.tested` |
| How is the cluster created and KServe installed? | Choose or create an env profile (step 2) |
| What does it need from a previous tutorial? | Must be re-created inside this tutorial (step 4) |
| Which KServe features does it exercise? | `features` |
| GPU? CPU / memory? | `requires` |
| Which languages exist? | `langs` |
| Which files does the text show inline? | Must become `tut:include` (step 5) |
| Anything internal (registries, hostnames, tokens)? | Remove before committing |

## 2. Choose the environment profile

- If an existing profile builds the cluster the tutorial needs, use it.
- If the tutorial only needs a small add-on (Prometheus, a CRD, a Helm chart),
  install it **inside the tutorial** and remove it in its cleanup.
- Only create a new profile (`envs/<name>/v1/`) when the cluster itself is
  different (e.g. another ingress/gateway, another KServe install type). Copy
  `envs/kind-llmisvc/v1/` as a starting point; keep `setup.sh` idempotent and
  pinned to `$KSERVE_VERSION`.
- Never edit a frozen profile; create the next version instead.

## 3. Create the directory

```bash skip
cp -r tutorials/_template tutorials/<id>
rm tutorials/<id>/manifests/example.yaml
```

Fill in `tutorial.yaml`. Start with `status: draft`.

## 4. Rewrite the README

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
| "You should see X" with no check | Keep the sentence and add a `verify` block that checks X. |
| `sleep 60` while waiting | `kubectl wait ...` or `verify retry=N delay=S`. |
| Inline copy of a YAML/py/sh file | `<!-- tut:include manifests/<file> -->` + `<!-- /tut -->`. |
| The same helper logic in several tutorials (URL lookup, waiting, request + check) | A script in a module under `lib/<name>/vN/`, listed in `uses`, called as `"$TUT_LIB/<name>/vN/<script>"`. Check existing modules first. |
| Links to tutorials that do not exist yet | Remove the link (plain text), or lint fails (D004). |
| Separate `scripts/1.prepare.sh`, `2.deploy.sh` that the README tells you to run | Prefer inlining the commands as `run` blocks so the README stays the source. Keep a script only if it is long and self-explanatory, and show it with `tut:include`. |

Every shell block gets a role: `run`, `verify`, `cleanup` or `skip`.

A good `verify` checks what the reader is supposed to have learned, not only
that a command ran: resource counts, container names, a field value, a request
that returns a valid response.

## 5. Move files

- Manifests → `manifests/`, images → `images/`, helper code → a directory of
  your choice inside the tutorial.
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

1. Copy the old KO text into `README.ko.md` and restructure it so its shell
   blocks match `README.md` one to one (same order, same roles, same code;
   only comments and prose differ).
2. Use the same `tut:` regions as the English file.
3. `./tut translation mark <id> ko`
4. `./tut lint` (D011 checks the structure).

## 8. Open the pull request

- One tutorial per PR. CI runs lint, then executes only this tutorial.
- When CI is green, change `status: draft` → `stable` (if its profile is
  frozen) in the same PR or a follow-up.

## Checklist

- [ ] `tutorial.yaml` complete; `status: draft`
- [ ] No dependency on another tutorial's state
- [ ] Every shell block has a role; interactive commands are `skip`
- [ ] At least one meaningful `verify` and a `cleanup`
- [ ] No inline copies of files; `tut:include` instead
- [ ] No hard-coded KServe versions; images pinned
- [ ] No internal hostnames, registries, tokens
- [ ] `./tut sync && ./tut lint` clean
- [ ] `./tut run <id>` passes locally (or CI is green)
- [ ] Translation marked, if any
