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
- Narrowed on 2026-11-21 by "Up to the PR" (Q6 answered): for work the maintainer ordered and the tech lead passed, commit, push and opening the PR need no further word. Merge, deleting or force-pushing a branch, repository settings and cluster-wide state stay per action, as does everything nobody ordered.

### 2026-11-21 A planner proposes, issues need the maintainer, the tech lead runs them
- Asked / situation: the tech-lead agent had just been built from the analysis of the whole project; nothing was asked.
- They said: "On that basis, can you also make a project-planner agent? I want it to think of the plans this project needs in order to go well, from the UI to helping the project proceed safely as open source. I am not asking for anything too complex or too big. And in the end it creates issues, with my permission. Later the tech-lead checks them one by one and gives out the actual work. And the tech-lead checks and then proceeds."
- So: plans come from a separate planner and cover the whole project (UI through open-source safety); the planner and its plans stay small and simple; an issue is created only with the maintainer's permission; the tech lead takes approved issues one at a time, checks each before work is handed out, and checks the result. Not settled by this: whether "checks and then proceeds" means the tech lead may go on to the next step (PR, next issue) without asking each time. Until they say, "Approvals are per action" (above) stands. Settled on 2026-11-21 by "Up to the PR" (below).
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

### 2026-11-21 Still open: what "the tech lead checks and proceeds" allows (Q6) - answered, superseded by 2026-11-21 "Up to the PR"
- Asked / situation: Q6 offered options (a)/(b)/(c) without a recommendation.
- They said: nothing that selects an option ("let's do it that way" has nothing to point at here).
- So: not decided. The working agent keeps (a) as an assumption - PR and merge need the maintainer's word each time - and has told the maintainer so and asked them to say if they want (b) or (c). "Approvals are per action" stands. Do not record (a) as their decision, and do not ask again unless work is blocked on it.
- Applies to: mode "Run an issue"; anything the tech lead might wave through after a check.

### 2026-11-21 How they answer a list: always mark a recommendation
- Asked / situation: six questions with options in one message.
- They said: one short sentence accepting everything.
- So: the maintainer answers a list as a whole and takes what is recommended. Every question must carry a marked recommendation and the assumption used if they say nothing; a question without one comes back unanswered (Q6). Put the one question that really needs their own choice first and alone, and keep the list short: one "ok" covers only what a recommendation points at. After such an answer the agent states its reading per question before acting (as was done here; see "A question is a question").
- Applies to: section "For the maintainer" of every report.

### 2026-11-21 Up to the PR (Q6 answered)
- Asked / situation: Q6, asked a second time because the first answer selected nothing: what does "the tech lead checks and proceeds" allow? (a) PR and merge each need the maintainer's word; (b) when the tech lead passes it, open the PR, only the merge needs their word; (c) approved issues are handled through to the merge.
- They said: "Up to the PR, you may open it." (their whole answer, translated from Korean)
- So: option (b). Once the tech lead has passed work the maintainer ordered, the agent commits, pushes and opens the PR without asking again and gives the maintainer the link with the verdict. "Up to" is the limit: the merge is theirs, each time. Their words name only the PR; the rest is the working agent's reading, told to them, and a later correction outranks it:
  - "ordered" means an approved issue or an instruction of theirs in the conversation (the question was about issues; the instruction case is the reading);
  - commit and push are included because a PR cannot be opened without them;
  - deleting or force-pushing a branch, repository settings and cluster-wide state were not mentioned, so they stay per action;
  - a plan, and anything nobody ordered, still goes to the maintainer before anything is done;
  - an instruction that says otherwise for one piece of work ("do not open a pull request until I ask", as the prompts in docs/prompts.md do) wins for that work.
- Applies to: mode "Gate" (what passing allows), mode "Run an issue", AGENTS.md "How to work" step 4. A rule for everyone, so it is written in AGENTS.md and docs/handbook.md section 9, not only here.

### 2026-11-21 Their own tutorials answer design questions: read them before asking
- Asked / situation: before migrating the five remaining legacy llmisvc tutorials, the agent asked "How should tutorials that change the shared Gateway configuration (05-0, 06) be handled?" and offered an env option, or change in the tutorial and revert in cleanup.
- They said: "You could tell by analysing the tutorials I made."
- So: a correction. The legacy tutorials are the maintainer's design, not only text to convert: how a tutorial changes shared state, what it installs, what it restores is already decided there (05-0 sets the rate-limit backend with `helm upgrade --reuse-values` and its Cleanup sets it back to null; 06 patches the GatewayClass and its Cleanup removes the patch). Read the source material first; ask only what it leaves open, and say what you read. A question the material answers costs them a turn and should be stopped at the gate.
- Applies to: every migration; any question about "how should X behave" when a legacy tutorial, an existing tutorial or a document already shows X.

### 2026-11-21 "The same cluster": asked for a structure, answered with a place
- Asked / situation: "Where should Prometheus and Grafana be installed?", offered as a choice between a new addons/monitoring/v1 structure and each tutorial installing it.
- They said: "The same cluster."
- So: they answered where, not which structure. Read as: no new structure was asked for; use what exists (install in the tutorial, as the legacy one does and docs/migration-guide.md says for add-ons; shared steps for reuse). This is my reading, one data point: it does not close backlog A7 (addons/), which only they can close or keep. When a question frames a structure choice, first ask whether the plain thing already in the repository is enough, and put that first.
- Applies to: proposals of new directories, mechanisms or abstractions; how questions are framed for them.
- Weakened on 2026-11-21 by "The question hid the choice": they had not seen that the question was about sharing as an addon, so "the same cluster" says nothing for or against addons/. The practical outcome (shared step, A7 open) stands as an assumption only.

### 2026-11-21 A question back is a request for the facts, not a yes
- Asked / situation: "Should 04-autoscaling run in CI?"
- They said: "Would doing that be a problem?"
- So: not a decision (see "A question is a question"). They do not see why it would not run in CI, so the default is that a tutorial runs in CI like the others; the one who wants an exception owes the concrete problem with evidence (a run, numbers), not a worry. Answer the question with what was measured, then let them decide.
- Applies to: any proposal to exclude or limit something in CI; questions asked without the reason attached.
- For 04-autoscaling itself this is moot since 2026-11-21 "Outdated source: I will rebuild it myself"; the rule stays.

### 2026-11-21 Outdated source: "I will rebuild it myself" (04-autoscaling) - superseded by 2026-11-21 "WVA autoscaling: migrate it as it is for 0.18"; the migration order by "Existing tutorials to 0.21 first"
- Asked / situation: Q1 from the migration-plan gate: 04-autoscaling, (a) migrate the WVA version last and try it in CI on a draft PR [recommended], or (b) postpone until the next KServe release and rewrite for direct KEDA.
- They said: "Right, the autoscaling part has to change, since WVA is not used any more.. I will rebuild that one myself before it is migrated."
- So: neither option. When the legacy source itself is outdated, the content is theirs to redo; agents do not migrate it as it is and do not rewrite it for them. 04 is out of the current migration: no WVA version, no CI experiment, and the collection order is monitoring, tracing, traffic-control, aigateway-route. It comes back only when they say the new source is ready. Both options I offered assumed the agent would do the work; the missing third option was "this is yours". When the source is the problem, say what is outdated and why, and ask who redoes it before offering ways to migrate it. One data point about one tutorial: not "agents never rewrite content".
- Applies to: migrations whose legacy tutorial no longer matches the product; any question where every option has the agent doing the work.

### 2026-11-21 The question hid the choice (Prometheus/Grafana, backlog A7)
- Asked / situation: Q2: backlog A7, (a) keep it open with the note "deferred, monitoring solved by a shared step" [recommended], or (b) close it. Earlier the same matter had been asked as "Where should Prometheus and Grafana be installed?".
- They said: "Ah, so that was the question: whether to share it as an addon." Nothing on (a) or (b).
- So: two things, kept apart.
  - Their words: the earlier question did not tell them what was being decided. "Where to install" was the vague form; "share it as an addon or not" was the decision. Name the decision in the question itself, in the words they would use, with what each side does to the repository; a question that needs a second round to be understood is a defect of the question.
  - Not decided: A7. The working agent uses my stated default (a): A7 stays open with a "deferred" note. This is an assumption, told to the maintainer, not their decision; the note in docs/backlog.md must not say they decided it. Do not ask again unless work is blocked on it. Whether to share as an addon is still theirs if it comes up.
- Applies to: wording of every question in "For the maintainer"; backlog A7; the monitoring migration.

### 2026-11-21 Migration plan for the llmisvc tutorials: not objected to, not approved in words - start and order superseded by 2026-11-21 "Answers to questions are not start" and "Existing tutorials to 0.21 first"
- Asked / situation: the working agent told them the revised plan (shared step for monitoring from 05-0 steps 0-3; change-and-restore for the shared Gateway; one PR each in the order monitoring, tracing, traffic-control, aigateway-route; done = standalone twice + once as a collection path).
- They said: nothing about it; their answer was only about autoscaling and the addon question.
- So: the agent's reading, told to them before acting: the migration is work they ordered, the plan passed the gate, so it starts with 03-monitoring and under "Up to the PR" opens the PR after I pass the work. Silence is not their decision on any single point; a later correction outranks this. The merge is theirs.
- Applies to: the four migration PRs.

### 2026-11-21 Say the core first when explaining to them
- Asked / situation: nothing was asked. It came right after they saw, only on the second round, that "Where should Prometheus and Grafana be installed?" had really been the decision "share it as an addon or not".
- They said: "One more thing: when the tech lead explains something to me, I want it to say the core of it more."
- So: every explanation and every question to them opens with the core in one or two sentences they can act on: what is being decided (in their words), what I think, and what it does to the repository. Reasons come after, in a few lines with evidence; then what would change my mind. Not a list of options without a view, not background first, not the detail in place of the point. Test before sending: if they read only the first two sentences, do they know what is decided and what I recommend?
- Applies to: sections "Verdict" and "For the maintainer" of every report; every answer to a direct question of theirs.

### 2026-11-21 Asked for my own view: addon or shared step (backlog A7)
- Asked / situation: "'Share it as an addon or not': what does the tech lead think?"
- They said: (the question itself; they want the tech lead's opinion, not options)
- So: when they ask what I think, I give one position with reasons and the condition that would reverse it. My answer here: no addons/ now, shared step defined in llmisvc-monitoring; revisit when a third real user appears or CI time measurably hurts. This is my view, not their decision; A7 stays theirs.
- Applies to: direct questions to the tech lead; backlog A7 until they decide.

### 2026-11-21 Answers to questions are not "start" (the monitoring migration)
- Asked / situation: the maintainer answered the working agent's questions about the llmisvc migration; the agent took the answers as the order to begin and started migrating llmisvc-monitoring.
- They said: "The migration is for tomorrow."
- So: a correction; the agent stopped the run. Answering questions settles the questions, it does not set the time. Before starting ordered work after a round of answers, say "I start now with X" and wait for it, or ask when. This also corrects "Migration plan for the llmisvc tutorials: not objected to" above: the reading "it starts with 03-monitoring" was wrong about when.
- Applies to: every start of work after a question round; what the gate tells an agent it may do next.

### 2026-11-21 WVA autoscaling: migrate it as it is for 0.18, and an agent that finds what a new version breaks
- Asked / situation: nothing was asked; it followed the correction above.
- They said: "Let's test it. We are on 0.18 now. Install it based on WVA and proceed as it is. And I want to know how these get excluded when I upgrade to 0.21, and for an agent to find out how they will be excluded - no, I think another agent is needed: one that goes through the PRs, finds this kind of information, and finds the tutorials that will not run in a new version or need to be deleted or updated."
- So: two things.
  - 04-autoscaling: the WVA tutorial is migrated as it is for v0.18. This reverses "Outdated source: I will rebuild it myself" (marked superseded). A tutorial that is true for the version it is tested with may be migrated even when a later version drops the feature; what happens to it at the upgrade is a separate question.
  - A new agent (version-scout): it goes through upstream PRs and changes and names the tutorials that will not run, or need deleting or updating, in a new version. What they asked for is finding and telling how a tutorial gets excluded; they did not ask it to decide or to change tutorials.
- Applies to: migrations of tutorials whose feature is leaving the product; version upgrades; the size of the version-scout agent.
- Made unclear on 2026-11-21 by "Existing tutorials to 0.21 first" (below): whether the WVA tutorial is still migrated as it is for v0.18 must be asked, not assumed.

### 2026-11-21 Existing tutorials to 0.21 first, then the migration goes on
- Asked / situation: the version-scout's first report (blind test, v0.18.0 to v0.21.0): v0.21.0 removes the scheduler's tokenizer sidecar and init container so llmisvc-anatomy's verify fails, the default scorers change, the legacy WVA tutorial stops working at v0.21.0 because the VariantAutoscaling CR is gone, master rejects WVA.
- They said: "The version-scout is good. Before the migration continues, it would be good to update the existing ones to 0.21 tomorrow."
- So: the agent is accepted as it reported (per-tutorial findings with upstream evidence, target and master kept apart). Order, superseding the migration order in "Outdated source" and "Migration plan" above: first the existing tutorials are brought to v0.21.0, then the migration continues. "Tomorrow" is the time: nothing of it starts today, and today only the version-scout goes up as a PR. Their words say "update the existing ones to 0.21"; that they are willing to change an existing tutorial for a newer version is their word, so no document may state the opposite as a rule while backlog C1 is open.
  - The working agent's reading, not their words: new tutorials are then written for v0.21.0 from the start.
  - Not decided, to be asked tomorrow before any work: whether v0.18.0 stays in `versions.tested` of an updated tutorial (this is C1 in practice), and whether the WVA tutorial is still migrated for v0.18 now that it does not work at v0.21.0.
- Applies to: tomorrow's order of work; backlog C1/C2; the remaining migration PRs; 04-autoscaling.
