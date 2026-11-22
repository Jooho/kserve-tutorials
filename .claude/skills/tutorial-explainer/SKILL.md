---
name: tutorial-explainer
description: Make or update the AI explainer of a tutorial in this repository - a teaching page with SVG diagrams and animated flows, written from a step-by-step run of the tutorial on a real cluster (./tut explain). Use when the user asks for an explainer, "how it works" page, diagrams or a visual explanation of a tutorial, or says yes after you offered one.
---

# Tutorial explainer

Thin wrapper: the work is defined in `docs/explainer.md` (read it fully first)
and done with `./tut explain`, so any agent (Claude Code, Codex, Copilot) does
the same thing.

1. Read `docs/explainer.md`, then `tutorials/<id>/README.md`, `tutorial.yaml`
   and the files it includes.
2. Walk the tutorial, unattended, without asking the user anything:
   `./tut explain start <id>`, then `./tut explain next <id>` until every step
   ran, with `./tut explain probe <id> -- kubectl ...` (read-only) wherever you
   need to see something before you write it. Then `./tut explain stop <id>`.
3. Write `tutorials/<id>/explainer/index.md` (+ `index.ko.md` if the tutorial
   has `README.ko.md`) and the SVGs, following the brief's shape and SVG rules.
4. `./tut explain check <id>` until 0 errors.
5. Review by other AIs in a fresh context: `./tut explain review <id>`
   (TUT_AI_REVIEW, one or several like `claude,codex`, else TUT_AI). If neither
   is set, give the output of `./tut explain review <id> --print-prompt` to a
   fresh subagent and save its answer as `build/explain/<id>/review.md`. Decide
   every finding (no new walk): fix it, or reject it with the reason; one line
   each in notes.md under "## Review round" (`A: ...` / `R: ...`). Review once
   more. Then `make precommit`.
6. Report to the user in their language: what you verified, what differs from
   the README (from `build/explain/<id>/notes.md`), which findings you
   rejected, where to look when reviewing, and that `./tut explain mark <id>`
   records their review. Do not mark it on your own judgment; run `mark` only
   when the user says they read it.

If the user does not know what an explainer is, say it in two sentences first:
a teaching page with diagrams next to the tutorial, written by an AI from a
real run, labelled as AI-written, never executed and not part of CI.
