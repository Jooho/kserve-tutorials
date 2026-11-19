# PoC: shared steps and learning paths

Branch `poc/shared-steps`. A proof of concept, not a finished feature.

## The idea

- Every tutorial is complete on its own: README.md is the source, CI runs it.
- A tutorial can **define** a step that other tutorials need, and another
  tutorial **uses** it with one line. `./tut sync` copies the steps in, so the
  README stays complete (GitHub, CI, standalone runs).
- Opened from a **collection** (learning path) in the UI, a tutorial hides what
  earlier members already did: the `run` blocks of shared steps they define or
  use. Their `verify` blocks still run, to check the state is really there.
  Cleanup is skipped until the end of the path.
- The collection's `vars` (e.g. `NS`) are exported in every member's shell, so
  all tutorials of the path work in the same namespace.

```markdown
<!-- tut:define poc-model -->     in PoC 1: the author writes the steps
```bash run
...
```
```bash verify
...
```
<!-- /tut -->

<!-- tut:use poc-model -->        in PoC 2 and 3: one line, `./tut sync` fills it
<!-- /tut -->
```

```yaml
# catalog/collections/poc-shared-steps.yaml
vars: {NS: poc-path, MODEL: path-model}
members: [poc-shared-1-deploy, poc-shared-2-config, poc-shared-3-scale]
```

## Try it

```bash skip
git switch poc/shared-steps
./tut ui
```

The three PoC tutorials need no cluster: each step writes files under
`${TMPDIR:-/tmp}/tut-poc/$NS`.

1. **Standalone:** open *PoC 3* from **All**. Every step is shown, and Run all
   gives 7/7, like CI (`./tut run poc-shared-3-scale --twice`).
2. **Path, not ready:** open *PoC 3* under **Collections → PoC: shared steps**.
   Two shared `run` steps and cleanup are hidden. Run all: the `poc-model`
   verify fails and offers "Run its hidden steps here" or a link to PoC 1.
3. **Path, in order:** run PoC 1, PoC 2, then PoC 3 from the collection. PoC 3
   only runs the verifies and its own step, in `NS=poc-path` with
   `MODEL=path-model`.

## Writing a tutorial with live preview

Keep `./tut ui` open on your tutorial and edit README.md in your editor. On
save the page redraws within a second:

- It shows the README **as it will be after `./tut sync`**: a new
  `<!-- tut:use name -->` line already shows the copied steps. A chip says
  "preview · file not synced — run make precommit" until you sync.
- A **Problems** panel lists this tutorial's lint findings (for example D014
  `tut:use modle: no tutorial defines it (defined: poc-config, poc-model)`).
- Switch modes with "📚 open in path: …" (standalone → path) and "open
  standalone" (path → standalone).

Note: while the file is not synced, the line numbers on blocks are those of the
preview, not the file.

## What changed

| Part | Change |
|---|---|
| `tools/tut/shared.py` | definitions, copy for `use`, block → step name, which steps an earlier member covers |
| `tools/tut/generate.py` | sync leaves `define` alone and fills `use`; a tutorial without `env` gets no `kubectl` in its setup |
| `tools/tut/lint.py` | D014: one definition per name, `use` an existing name, no markers inside a definition, do not use your own |
| `schema/collection.schema.json`, `catalog.py` | collection `vars` |
| `tools/tut/ui/*` | `?collection=` on a tutorial: hidden blocks, path bar (step n/m, prev/next, vars, show all, open standalone), hint on a failed covered verify; the shell gets the path's vars and restarts when the mode changes |
| `tools/tut/ui/*` (preview) | the page and the run messages use the in-memory synced text; `/api/stamp` (reload on save), `/api/tutorials/<id>/problems` (lint for one tutorial); sidebar `# tags` toggle; learning paths in purple |
| `tools/tests/test_shared.py` | sync, lint, coverage order, live preview, Problems |
| `tools/tests/test_learning_path.py` | server API + real shell: standalone 7/7, path in order in the shared NS, path out of order fails at the covered check |
| `tutorials/poc-shared-*`, `catalog/collections/poc-shared-steps.yaml` | the PoC itself |

Runner and CI are unchanged: they always run the whole README (standalone).

## Findings

1. **A hidden `run` block cannot hand variables to later steps.** In a path
   it does not run, and each tutorial has its own shell. Shared steps must keep
   their state in the cluster (or files), and every block must set the defaults
   it needs (the PoC repeats `POC_HOME=...`), or the value comes from the
   path's `vars`. A lint rule could warn about variables a definition's `run`
   blocks set and later blocks read.
2. **Covered means "an earlier member has it", not "the user ran it".** The
   verify is what makes this safe; a shared step without a verify should be a
   lint error.
3. **The namespace override works with no new code**: the generated setup
   already does `export NS="${NS:-<tutorial>}"`, and the path exports `NS` first.
4. **Mode switch = new shell**, because the vars differ. Opening the same
   tutorial standalone and in a path keeps their shells apart.
5. **Gaps kept on purpose for the PoC:** D003 (hard-coded versions) skips
   `define` bodies; `use` copies the same language's definition and falls back to
   English; per-step "show" expands every hidden block.
