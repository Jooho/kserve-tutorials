# Example: what `./tut draft` produced for `inferencegraph-ensemble`

A snapshot of `build/draft/inferencegraph-ensemble/` from the first real draft
(2026-11-19), kept to show the material the AI gets and what comes back:

| File | Written by | What |
|---|---|---|
| `prompt.md` | the program | the instructions the AI CLI received |
| `parts.md` | the program | the reusable parts it was offered (envs, helper scripts, shared steps) |
| `notes.md` | the AI | what it built, every tested command it changed or left out, TODOs |
| `report.md` | the program | lint, files changed elsewhere, input commands missing from the tutorial |

It is a snapshot, not a reference for today's names: it predates
`envs/kind-kserve/v1` (it shows the old `kind-llmisvc/v1`) and `project.yaml`.
For the current wording run `./tut draft` yourself; the finished tutorial is
`tutorials/inferencegraph-ensemble/`.
