# What the tech lead has learned from the maintainer

The notebook of the `tech-lead` agent (`.claude/agents/tech-lead.md`). The agent reads it at every start and appends to it when the maintainer answers a question or corrects something. Newest entries count most. People may edit it too: delete what is wrong, mark what is outdated.

Entry format: what was asked or what happened, what the maintainer said, the rule taken from it, where it applies.

## Entries

### 2026-11-21 The tech lead comes before the maintainer
- Asked / situation: the tech-lead agent had just been written as a reviewer that is called on request.
- They said: "I always want the tech-lead to verify things before I am asked for permission. When my permission or opinion is needed, the tech-lead asks me, and it learns from my answers."
- So: every request for the maintainer's approval or decision passes the tech lead first; the maintainer sees its verdict and only the questions it could not settle; every answer is written here.
- Applies to: all work in this repository, by any agent.
- Narrowed on 2026-11-21 by "Six questions, one answer" (Q5): the gate is for plans, commits, PRs and merges; answers to the maintainer's questions and small confirmations go straight to them.

### 2026-11-21 A hardening nobody hit is not a must-fix
- Asked / situation: proposed to change the tutorial's port-forward port (8080) and to record that its failure is silent.
- They said: "Why?" to the port change, then "only this" (the fix tied to the real failure) and "that note is not needed".
- So: fix what failed or what a user will hit; do not attach nearby improvements. If you cannot say why in one sentence, leave it out.
- Applies to: review findings, PR scope, backlog entries.

### 2026-11-21 Blind test of this agent: what it missed and what it overdid
- Asked / situation: the agent reviewed the inferencegraph-ensemble tutorial on a snapshot from before the maintainer's later corrections.
- They said: (no answer; comparison with what the maintainer had caught on their own)
- So: it found the UI port 8080 clash, as the maintainer did. It missed that the README pictures were written differently from the sibling tutorial (markup and size), which the maintainer saw by looking at the page: compare siblings line for line and look at the rendered result. It listed the silent port-forward as a must-fix, which the maintainer had turned down: see the entry above. Its report was several times longer than the maintainer would read.
- Applies to: every review; report length.

### 2026-11-21 Related leftovers go into one PR
- Asked / situation: a small explainer wording fix was about to become its own PR next to an open one.
- They said: "Put all the remaining things into one PR." Earlier: "these two are related, better to merge them into one."
- So: small, related leftovers travel together; splitting is for things that are reviewed or reverted separately.
- Applies to: PR boundaries.

### 2026-11-21 "Standard" is the default deployment mode
- Asked / situation: a fix set KServe's default deployment mode only when KServe standard was requested.
- They said: "Standard has to be the default."
- So: in this environment Knative is the exception (only when serverless is asked for); a fix must state and enforce the rule, not the one case that failed.
- Applies to: envs/kind-kserve, any tutorial that relies on a cluster-wide default.

### 2026-11-21 The "reviewed by a person" mark
- Asked / situation: "why do I have to run mark myself?"
- They said: they will read the explainers later.
- So: reading is theirs; the command is not. An agent runs `./tut explain mark` only when the maintainer says they read it, for the languages they name, never on its own judgment.
- Applies to: explainers, translations (`translation mark`).

### 2026-11-21 Line breaks in documents
- Asked / situation: why are documents wrapped by hand; is that good for AI; one sentence per line was proposed.
- They said: one sentence per line "is hard for a person, it gets too long downwards"; "change only what is under docs/".
- So: under docs/ one line per paragraph; tutorial READMEs keep their line breaks (changing them costs e2e runs and translations). When AI convenience and human reading disagree, human reading wins.
- Applies to: writing and reviewing documents.

### 2026-11-21 Other agents use AGENTS.md as before
- Asked / situation: whether Codex and Copilot should get the Claude skill mechanism (shared skill folder).
- They said: "Is there a problem with reading it directly? Is the CLAUDE.md way better?" then "let's use it as before."
- So: AGENTS.md is the source for every agent; do not add structure for one tool unless it removes a real difference in results.
- Applies to: agent tooling, .claude/, skills.

### 2026-11-21 A question is a question
- Asked / situation: the agent started testing and changing things when the maintainer asked how something works; later it started a different task than the one meant.
- They said: "Don't fix it, I want to talk first." "I am asking." "What are you doing? I meant the UI port."
- So: answer first. Start work only on an instruction. When a short "ok" could cover several proposals, say which one you take it for before acting.
- Applies to: every conversation with the maintainer; what the tech lead tells agents to do next.

### 2026-11-21 Approvals are per action
- Asked / situation: merges and pushes after "ok" or "go".
- They said: "Nothing with git without my permission." "Merge when CI passes" was given per PR, several times.
- So: commit, push, PR, merge and branch deletion each need the maintainer's word for that case; an approval does not carry to the next PR.
- Applies to: what the tech lead may wave through (never these) and what it must ask.

### 2026-11-21 A planner proposes, issues need the maintainer, the tech lead runs them
- Asked / situation: the tech-lead agent had just been built from the analysis of the whole project; nothing was asked.
- They said: "On that basis, can you also make a project-planner agent? I want it to think of the plans this project needs in order to go well, from the UI to helping the project proceed safely as open source. I am not asking for anything too complex or too big. And in the end it creates issues, with my permission. Later the tech-lead checks them one by one and gives out the actual work. And the tech-lead checks and then proceeds."
- So: plans come from a separate planner and cover the whole project (UI through open-source safety); the planner and its plans stay small and simple; an issue is created only with the maintainer's permission; the tech lead takes approved issues one at a time, checks each before work is handed out, and checks the result. Not settled by this: whether "checks and then proceeds" means the tech lead may go on to the next step (PR, next issue) without asking each time. Until they say, "Approvals are per action" (above) stands.
- Applies to: the project-planner agent, mode "Run an issue", any proposal of new process or agents (keep it small).

### 2026-11-21 Open: agents by framework
- Asked / situation: after asking for the planner.
- They said: "Would it be better to build the agents with a framework instead?"
- So: no decision yet; this is a question to be answered, not an order to change anything (see "A question is a question"). It shows they watch the size of the agent system themselves: do not grow it without being asked.
- Applies to: agent tooling, .claude/.

### 2026-11-21 Six questions, one answer: the recommendations were taken
- Asked / situation: six questions from the gate on the tech-lead/planner work, put word for word, each with options; Q1-Q5 had a recommendation, Q6 had none.
- They said: "Good, let's do it that way." (one sentence for all six; they named no option themselves)
- So: this is read as "take the recommended option" for Q1-Q5. The reading is the working agent's, told to the maintainer before acting; it is not the maintainer's own wording, so a later correction of any single point outranks it.
  - Q1: the agent creates the `plan` label once (`gh label create plan`) when the first issue is filed.
  - Q2: new branch from the latest main; tech-lead, planner, AGENTS.md and handbook changes in one PR.
  - Q3: the notebook is committed to the public repository; later notebook changes travel with the PR in progress. So nothing private or secret goes into it.
  - Q4: Codex/Copilot stay as they are: they do the review themselves and say it was their own (no tech-lead call).
  - Q5: the gate covers plans, commits, PRs and merges only; answers to questions and small confirmations go straight through.
- Applies to: the PR that adds the agents; issue filing; what must be gated; what may be written in this notebook.

### 2026-11-21 Still open: what "the tech lead checks and proceeds" allows (Q6)
- Asked / situation: Q6 offered options (a)/(b)/(c) without a recommendation.
- They said: nothing that selects an option ("let's do it that way" has nothing to point at here).
- So: not decided. The working agent keeps (a) as an assumption - PR and merge need the maintainer's word each time - and has told the maintainer so and asked them to say if they want (b) or (c). "Approvals are per action" stands. Do not record (a) as their decision, and do not ask again unless work is blocked on it.
- Applies to: mode "Run an issue"; anything the tech lead might wave through after a check.

### 2026-11-21 How they answer a list: always mark a recommendation
- Asked / situation: six questions with options in one message.
- They said: one short sentence accepting everything.
- So: the maintainer answers a list as a whole and takes what is recommended. Every question must carry a marked recommendation and the assumption used if they say nothing; a question without one comes back unanswered (Q6). Put the one question that really needs their own choice first and alone, and keep the list short: one "ok" covers only what a recommendation points at. After such an answer the agent states its reading per question before acting (as was done here; see "A question is a question").
- Applies to: section "For the maintainer" of every report.
