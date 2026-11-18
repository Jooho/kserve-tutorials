# Contributing

## How this repository works

- Each tutorial lives in `tutorials/<id>/` and owns everything it needs.
- Its `README.md` is both the document and the test: CI executes the shell
  blocks in order.
- Shared cluster setup lives in versioned environment profiles under `envs/`.
- `./tut lint` enforces the rules; `./tut run` executes a tutorial.

Full design: [RFC 0001](docs/rfc/0001-repository-structure.md).

## Setup

```bash skip
python3 -m pip install -r tools/requirements.txt
./tut lint
```

## Writing a tutorial

```bash skip
cp -r tutorials/_template tutorials/<id>
# edit tutorial.yaml and README.md
./tut sync && ./tut lint
./tut run <id> --dry-run     # what CI will execute
./tut run <id>               # execute it (Docker, kubectl, Kind)
```

### Shell block roles

| Fence | Meaning |
|---|---|
| ` ```bash run ` | executed |
| ` ```bash verify ` | executed and must succeed; add `retry=N delay=S` for eventual conditions |
| ` ```bash cleanup ` | always executed at the end, also after a failure |
| ` ```bash skip ` | shown only (interactive or optional commands) |

### Generated regions

Never edit between `<!-- tut:... -->` and `<!-- /tut -->`; run `./tut sync`.

| Region | Generated from |
|---|---|
| `<!-- tut:header -->` | `tutorial.yaml` |
| `<!-- tut:setup -->` | `tutorial.yaml` (KServe version, namespace, env) |
| `<!-- tut:include path -->` | the file at `path` inside the tutorial |

### Rules

The list with codes is in [`tools/tut/lint.py`](tools/tut/lint.py) and RFC
§4.9. The most important ones:

- No dependency on another tutorial's files or cluster state.
- No hard-coded KServe versions; use `$KSERVE_VERSION`.
- At least one `verify` and one `cleanup` block.
- Pinned container images.
- Frozen env profiles are never modified; create the next version.

### Shared scripts (modules)

Scripts used by more than one tutorial live in `lib/<name>/v<N>/` with a
`module.yaml`. List the module in `tutorial.yaml` (`uses: [llmisvc/v1]`) and
call `"$TUT_LIB/llmisvc/v1/<script>"`. Lint fails on undeclared calls. Once a
module is `frozen: true` it never changes: copy it to `v<N+1>`, change the
copy, and move tutorials over one PR at a time.

### Trying it in the UI

`./tut ui` runs your tutorial step by step in a real shell, exactly as CI
will (same parser, same verify semantics).

### Lifecycle

`draft` → `stable` → `deprecated` → `archived`. Archiving a tutorial is a
one-file change to its `tutorial.yaml` (with a `deprecation` block) and does
not affect any other tutorial.

### Translations

English `README.md` is the source. After translating, run
`./tut translation mark <id> <lang>`; lint warns when the source changes later
and fails if the translation's shell blocks differ from the source.

## Migrating an existing tutorial

See [docs/migration-guide.md](docs/migration-guide.md).
