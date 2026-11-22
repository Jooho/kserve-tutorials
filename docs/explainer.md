# Explainers: the teacher next to a tutorial (PoC)

A tutorial's README is the test: terse steps and the checks that prove them. An
**explainer** is a separate page that teaches what the tutorial is about: the
big picture, how the parts talk to each other, pictures and animated flows. An
AI writes it from a real run of the tutorial; a person reviews it later.

| | README.md | explainer/ |
|---|---|---|
| Purpose | do it and prove it works | understand why it works |
| Written by | a person (or `./tut draft`, finished by a person) | an AI, unattended, from a live run |
| Executed | yes: CI e2e, `./tut run`, the UI | never; changing it runs no tutorial in CI |
| Shown | GitHub, site, UI | its own page: UI chip "How it works" (new tab), link on the site |
| Labelled | - | always "written by an AI", from its marker (the page cannot hide it) |

Code: `tools/tut/explain.py`. Lint: X001-X005. CI blast radius: none
(`plan.affected` skips `tutorials/<id>/explainer/`).

## For people: how to get one

```bash skip
export TUT_AI=claude                     # or codex, copilot (./tut config TUT_AI=claude)
export TUT_AI_REVIEW=codex               # optional: another AI reviews it (default: TUT_AI)
./tut explain draft <id>                 # 15-30 min, needs Docker: the AI walks the tutorial on a cluster,
                                         # writes, gets reviewed, fixes once (build/explain/<id>/review.md)
# read tutorials/<id>/explainer/ (./tut ui -> "How it works"), fix what is wrong
./tut explain mark <id>                  # records that a person reviewed it
```

Or just ask your agent "make an explainer for <id>" (Claude Code: skill
`tutorial-explainer`). Nothing else is needed from you while it runs.

## For the AI: the brief

You write `tutorials/<id>/explainer/` alone, start to end. Nobody answers
questions while you work.

### 1. Walk the tutorial on the cluster

```bash skip
./tut explain start <id>
./tut explain next <id>                       # one run/verify block; repeat to the end
./tut explain probe <id> -- kubectl get pods -n "$NS" -o wide
./tut explain probe <id> -- kubectl describe pod -n "$NS" <name>
./tut explain probe <id> -- kubectl logs -n "$NS" -l <selector> --tail=50
./tut explain stop <id>                       # runs the cleanup blocks
```

- `next` runs exactly what a reader runs, in one shell (variables carry over).
- `probe` runs in that shell, read-only: kubectl `get describe logs explain
  api-resources events top version`, `auth can-i`, `config view`; helm `list
  status get history show`. Anything else is refused. Pipe the output of
  `./tut explain probe` yourself if you need to filter it.
- Probe **after the step where the thing appears**: the state before a step is
  part of the story too (e.g. "the namespace is empty before the apply").
- Everything is recorded in `build/explain/<id>/evidence.md`.

### 2. Accuracy rules

- State a fact about the cluster (kinds and counts of resources, container and
  port names, labels, who calls whom, log lines, metric names, conditions) only
  after you saw it in a step output or a probe.
- Where the README and the cluster disagree, describe the cluster and write the
  difference in `build/explain/<id>/notes.md`. Do not change the README.
- General background (what a Gateway is, what KV cache means) may come from
  your knowledge; keep it short and do not attach numbers or names to it you
  did not observe.
- A part that looks out of place (an init container on a Pod that serves no
  model, an idle sidecar) needs its reason, not only its name: a reader stops
  there. If the cluster does not show the reason, look it up in the product's
  source for that version and say in the text that it comes from the source.
- Values that change per run (IPs, generated suffixes, timings) are examples:
  write "e.g." or use the stable part of the name.

### 3. Shape of `explainer/index.md`

1. First line, exactly: `<!-- tut-explainer source=README.md sha=0 by=<your CLI> reviewed=no -->`
   (`./tut explain mark` fills in the real hash later; lint X001 checks the line).
2. `# <tutorial title>: how it works`
3. **In one picture**: one animated SVG of the main flow, 2-3 sentences.
4. **What you will learn**: 3-6 bullets, each tied to README steps.
5. **The pieces**: a short section per component or idea. Every ```` ```text ````
   diagram of the README becomes an SVG here (same content, drawn properly).
6. **Step by step**: a table, README step -> what happens in the cluster -> what
   to look at; "step N" refers to the walk.
7. **What we saw that the README does not say** (only if there is something).
8. **Check yourself**: 3-5 questions, answers in `<details>`.
9. Last line: `Based on a run of <id> with <product> <version> on <date>.`

Style: a teacher talking to a student. Short sentences. Define a term the first
time it appears. Diagrams carry the structure; text says why. No marketing.
Show commands as plain ```` ```bash ```` blocks (never `run` / `verify` /
`cleanup`: X002), and only ones from the README or your probes.

Languages: `index.md` in English. If the tutorial has `README.ko.md`, also
`index.ko.md` in Korean with the same sections and the same SVGs. Product terms
(project.yaml `glossary`) stay in English.

### 4. SVG rules

- One file per picture, `kebab-case.svg`, under 60 KB, `viewBox` set, width
  720-900 units, transparent background.
- Self-contained: no `<script>`, no `on*=`, no `<foreignObject>`, no external
  `href` or `url()` (X004). They are shown with `<img>`, where scripts never run
  anyway; CSS and SMIL animation do run.
- Colours that work on light and dark pages: put the colours in a `<style>`
  with `@media (prefers-color-scheme: dark)` overrides; text at least 4.5:1
  against both backgrounds.
- Animation: show movement along the real path (a request dot travelling from
  box to box, a highlighted step), 4-8 s loop, and stop it under
  `@media (prefers-reduced-motion: reduce)`. Animate only what helps.
- Labels in English (they are shared by every language); keep text short and
  at least 12 px.
- Link pictures from markdown: `![Alt text that says what it shows](flow.svg)`.

### 5. Finish

`./tut explain check <id>` must report 0 errors. Write
`build/explain/<id>/notes.md`: what you verified, what differs from the README,
what you could not verify. Do not run `./tut explain mark`.

### 6. Review by another AI

The writer does not doubt its own conclusions. A second AI in a fresh context
reads the explainer, the evidence and the README, and lists statements the
evidence does not carry: unsupported, overgeneralized (true for this
environment, written as always), missing reason, contradicted, translation or
SVG mismatch. It only reads; its report is `build/explain/<id>/review.md`.

```bash skip
./tut explain review <id>                  # TUT_AI_REVIEW, else TUT_AI
./tut explain review <id> --print-prompt   # no CLI set: give this to a fresh subagent
```

`draft` does this itself: review, one fix round by the writer (no new walk),
review again. The person reading before `mark` starts from the last review.
A different model shares fewer blind spots, but the fresh context matters
most: in the anatomy pilot the same model (claude) as reviewer found 8 real
issues, codex found 5 and missed the two a person had found.
