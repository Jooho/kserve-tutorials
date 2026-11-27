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
- Superseded on 2026-11-23 by "Nothing with git without asking, explained first" (below).

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
- Reopened on 2026-11-23 by "v0.18 as it is, for now": their later answer to Q2 can be read as "migrate 04 as 0.18-only". Until they say which, agents do not migrate 04.

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

### 2026-11-21 Existing tutorials to 0.21 first, then the migration goes on - superseded by 2026-11-23 "v0.18 as it is, for now"
- Asked / situation: the version-scout's first report (blind test, v0.18.0 to v0.21.0): v0.21.0 removes the scheduler's tokenizer sidecar and init container so llmisvc-anatomy's verify fails, the default scorers change, the legacy WVA tutorial stops working at v0.21.0 because the VariantAutoscaling CR is gone, master rejects WVA.
- They said: "The version-scout is good. Before the migration continues, it would be good to update the existing ones to 0.21 tomorrow."
- So: the agent is accepted as it reported (per-tutorial findings with upstream evidence, target and master kept apart). Order, superseding the migration order in "Outdated source" and "Migration plan" above: first the existing tutorials are brought to v0.21.0, then the migration continues. "Tomorrow" is the time: nothing of it starts today, and today only the version-scout goes up as a PR. Their words say "update the existing ones to 0.21"; that they are willing to change an existing tutorial for a newer version is their word, so no document may state the opposite as a rule while backlog C1 is open.
  - The working agent's reading, not their words: new tutorials are then written for v0.21.0 from the start.
  - Not decided, to be asked tomorrow before any work: whether v0.18.0 stays in `versions.tested` of an updated tutorial (this is C1 in practice), and whether the WVA tutorial is still migrated for v0.18 now that it does not work at v0.21.0.
- Applies to: tomorrow's order of work; backlog C1/C2; the remaining migration PRs; 04-autoscaling.

### 2026-11-23 v0.18 as it is, for now (v0.21 questions)
- Asked / situation: two questions before any v0.21 work. Q1: when an existing tutorial moves to 0.21, is 0.18 dropped, or kept with a new 0.21 tutorial? Q2: is the WVA autoscaling tutorial still migrated on 0.18 as it is, or left until a 0.21-style version exists? The day before, without being asked, they had said about autoscaling: "the autoscaling part has to change, since WVA is not used any more.. I will rebuild that one myself before it is migrated." A follow-up question by the working agent ("existing tutorials stay off 0.21 and autoscaling goes in as 0.18, or do you still rebuild it?") got no answer.
- They said: "For now I will do it as it is, on 0.18." (one sentence for both questions) Later: "Good, now let's do the migration."
- So:
  - Decided: no v0.21 move now. Existing and migrated tutorials stay on v0.18.0, written as they are. "For now" means it is postponed; it is not a decision about later.
  - Not decided: Q1 (drop 0.18 or keep it next to 0.21). Nothing is moved now, so it is not asked again until 0.21 work starts.
  - Not decided: autoscaling (04). "As it is, on 0.18" answers Q2's option (b) word for word. It is also the newer statement. "I will rebuild it myself" was said earlier, and WVA belongs to the new versions' change, not to 0.18. Reading it as "do not migrate 04" would let the older statement beat the newer one; reading it as "migrate 04 as 0.18" would ignore that they said they would rebuild it. Neither reading is theirs. Agents do not migrate 04 until they choose. The other four are unaffected either way, so nothing is blocked now; ask once, with a recommendation, before 04 would come next.
  - "Now let's do the migration" is the order for the llmisvc migrations (monitoring, tracing, traffic-control, aigateway-route).
  - Lesson about my own questions: one short answer to two questions, and Q2 named exactly the words they then used. A follow-up question they skip is not an answer; do not fill the gap with the older statement.
- Applies to: KServe version choices for tutorials, the 04-autoscaling migration, how a one-line answer to several questions is read.

### 2026-11-24 llmisvc is the llmisvc controller, not the KServe controller
- Asked / situation: nothing was asked. They read the llmisvc-anatomy explainer, which (like llmisvc-request-flow) called the component that reconciles LLMInferenceService "the KServe controller".
- They said: "llmisvc is not the kserve controller, it is the llmisvc controller; the kserve controller is for predictive models."
- So: name components by what actually runs, not by the product's umbrella name. On the cluster LLMInferenceService is reconciled by `llmisvc-controller-manager` (namespace kserve); `kserve-controller-manager` handles the predictive InferenceService. In the same check the request-path picture was found to draw InferencePool -> EPP -> vLLM Pod as if the request passed through the EPP; really Envoy asks the EPP over ExtProc and sends the request to the Pod itself. Both were fixed by the working agent, and two lines were added to docs/explainer.md section 2 (Accuracy rules) - that is where the rule for everyone lives. When reviewing an explainer or tutorial text: check every named component and every arrow against the cluster (Deployment name, who calls whom), not against how the product is usually described; a picture's arrows are claims like sentences.
- Applies to: llmisvc explainers and tutorials, any text or diagram that names a controller or draws a request path; reviews of explainers (`./tut explain review` findings).

### 2026-11-24 A tutorial teaches; commands alone are not a tutorial (llmisvc-monitoring)
- Asked / situation: nothing was asked. They read the llmisvc-monitoring migration (staged, not committed), which I had passed at the gate while it lacked what follows.
- They said: "The monitoring tutorial is good, but something is missing: what each step is trying to show, what value you should expect and why that value is expected, and so on. For example, when the prefix is used, there is no explanation of which value goes up and why it goes up. And was there no image in this one?" Then: "Keep in mind it is a tutorial. It is not copy the command, run it, done. What matters is what we want to teach with this tutorial and what the reader can learn from it."
- So: a tutorial is judged first by what it teaches, then by whether it runs. Correct commands, passing verifies and a faithful conversion of the legacy text are not enough; I passed this one on exactly those, which was my miss. From now on, at every tutorial or migration gate, before lint and dry-run, I check:
  - The top says what the reader will learn (concepts, not commands), and "What we learned" at the end answers the same list.
  - Every step says what to look at in its output, the value the reader should see, and why it is that value (the mechanism). A command whose output is printed with no word on what matters in it is a must-fix.
  - Where a number moves (counter, gauge, hit rate), the text says which one, by about how much, and why; a contrast case (here varied vs shared prefix) is explained, not only checked.
  - Values come from a real run, "in our run" where they vary by machine; reasons from source rather than the run say so.
  - The command prints what the text talks about (not the first 20 lines of something else).
  - Pictures: is there one where the reader would want to see the state, does it show what the text says, and is it legible at the page width. "Was there no image?" means they look for pictures in a tutorial about something visual (a dashboard).
  - A migration first decides what the tutorial teaches; the legacy text is the starting material, not the bar.
- Applies to: every tutorial and migration gate; already-migrated tutorials (llmisvc-anatomy, llmisvc-request-flow, inferencegraph-ensemble) were passed on the old bar and may have the same gap. Rule for everyone: belongs in docs/authoring.md section 3 and docs/migration-guide.md (lines proposed in the report of this date).

### 2026-11-24 "Do all of it" (student agent, monitoring plan, doc wording, three merged tutorials)
- Asked / situation: the working agent put four things to them at once: (1) a new `student` agent (fresh context, reads only README, pictures and run output, lists a learner's questions; no teacher agent, the author answers with run evidence); (2) the monitoring rewrite plan with my three must-fixes; (3) my wording for docs/authoring.md section 3 and docs/migration-guide.md; (4) my question on the three merged tutorials, (a) check them after the remaining migrations with a backlog item now [recommended] or (b) now.
- They said: "Do all of it." (whole answer, translated from Korean)
- So: (1)-(3) approved as proposed. (4): they picked neither (a) nor (b), so (a) is my stated default, applied by the agent (backlog C7); this is not their own choice and a later word outranks it. Approving the student agent is a deliberate growth of the agent system, asked for this time (see "Open: agents by framework"); it does not license further agents. The extra authoring line "Ask the student before you ask for review" was added by the agent, not shown to them in that form: check at the gate that it matches what they approved. Open, from llm-d-router v0.9.0 source (read, not observed): the EPP prefix-cache-scorer uses its own index of token-ID blocks of at least 64 tokens recorded in PreRequest, not vLLM metrics; with ~25-token prompts the EPP may score 0 while vLLM hits about 60%. To be measured (inference_extension_prefix_indexer_*) before the README states it.
- Applies to: the monitoring PR, the student agent, backlog C7, one-line answers to a bundle (again: the recommendation is what gets taken).

### 2026-11-24 Explain what misleads, moderate detail, the student at most twice (llmisvc-monitoring rework)
- Asked / situation: nothing was asked; instructions while the monitoring tutorial was being reworked after "A tutorial teaches".
- They said: each step must say what to look at, the expected value and why ("Keep in mind it is a tutorial: it is not copy the command, run it, done..."); "things that are confusing should get an explanation" - e.g. "Avg Cache Hit Rate" sits under "InferencePool Status" but is computed from vLLM counters; the detail moderate, less than an explainer; after a change run the student agent and update, and "the student agent gets questions only up to two times". Also "do all of it" and "you may go ahead" (use the cluster).
- So: (1) a name or place that suggests the wrong source or meaning (a panel title, a section, a metric name) is explained in the tutorial itself, where the reader meets it, and in the tool's own help where there is one (Grafana panel description); at a gate I look for such names and treat an unexplained one as a must-fix. (2) Tutorial depth sits between commands-only and the explainer: mechanism and expected value per step, not the full component walk. (3) Student agent: at most two rounds per change (ask, update, ask, update, stop); a third round is not asked for, later questions go to the explainer or a follow-up. Written for everyone in docs/authoring.md section 3 and .claude/agents/student.md. "Go ahead" covered the cluster for this work; it says nothing about git.
- Applies to: every tutorial and migration gate; how many student rounds an agent may run; dashboards and other UIs shipped with a tutorial.

### 2026-11-23 Nothing with git without asking, explained first (revokes "Up to the PR")
- Asked / situation: an agent made a GPG-signed commit without asking, relying on "Up to the PR". Recorded late (2026-11-24); words relayed by the working agent.
- They said: "Why do you keep doing gpg; don't do anything git-related without my permission." and "Why are you committing? When you want to do something git-related with me, you should explain first and ask for permission."
- So: every git write (branch, worktree, add, commit, push, PR) needs their permission for that action, asked after explaining what, why, the exact commands and the effect; then stop and wait. My pass at the gate never allows a git step. "Up to the PR" (2026-11-21) no longer counts. Read-only git (status, diff, log) is fine.
- Applies to: mode "Gate" (passing ends with a git question to them, not a go), mode "Run an issue", every report's "For the maintainer". A rule for everyone: AGENTS.md "How to work" step 4 and "The tech lead comes before the maintainer", and docs/handbook.md section 9, still say the opposite and must be changed (with their approval).

### 2026-11-25 Call the tech lead only when needed; git always asks the maintainer
- Asked / situation: the maintainer said "merge what can be merged" and the working agent sent the merges to me first; separately, whether AGENTS.md and the handbook should still say "a tech-lead pass allows the PR".
- They said: "The tech lead is used too often. It should be called only when needed, not every time. I said merge, why ask the tech lead?" and "Anything git always needs my permission." (translated from Korean)
- So: I am called before the agent shows the maintainer work it produced (a plan, a new tutorial or rework, a rule change), not for their direct orders (merge #N, re-run a job, answer a question). My pass is never permission for git or GitHub; every such step is explained (what, why, commands, impact) and asked, each time.
- Applies to: every mode; AGENTS.md "How to work" step 4 and "The tech lead comes before the maintainer", docs/handbook.md section 9 (changed in the same PR).

### 2026-11-25 Backlog C1 direction: per-tutorial revisions, old versions always go to a revision (relayed)
- Asked / situation: the working agent discussed C1 with them (per-version blocks in the README, repo-wide release branches per KServe version, per-tutorial revisions) and brought me the agreed design for a gate. Their words reached me only through the agent's summary.
- They said (as relayed, not quoted): per-version branches inside a README rejected (hard to read, verify splits); release branches set aside, they prefer per-tutorial revisions; fixed rule: when a tutorial changes because of a new KServe version, the old versions always go to a frozen revision (tutorials/<id>/revisions/rN/), no attempt to keep one README true for both. Readers on old KServe must still read and run the old tutorial. It must be automatable; that matters most to them.
- So: C1's direction is taken (revisions). It fits the recorded Decision "versions are per tutorial, not per branch" (handbook, RFC 4.4); release branches would have re-opened it. Do not offer release branches or per-version README blocks again unless they raise it. Details of the design (window, bot PR, PR CI on all versions, how frozen a revision is) are not decided by this.
- Applies to: backlog C1/C2, any version bump of a tutorial, version-scout proposals, docs/ci-playbook.md section 5.

### 2026-11-25 Revisions: CI runs only the N, N-1 window, decided now
- Asked / situation: Q2 of the revisions-design gate: decide "PR CI over every tested version" and "the N, N-1 support window" now, or after the pilot when CI time is measured [recommended: after].
- They said: "2- \"N, N-1 window\" 만 돌리자." ("2: let's run only the N, N-1 window.")
- So: decided now, not after the pilot; my recommendation was not taken. CI runs only versions inside the N, N-1 window, not every tested version. My reading, not their words: "CI" covers PR, weekly and release alike (one matrix rule, principle 5), so release's "full matrix = every tested version" (docs/release.md:13) becomes "every tested version in the window"; a version outside the window stays in `versions.tested` (it was verified) and is shown with "last verified" (D6), so lint (a) is unchanged. Not said: what N is (newest release upstream, or newest version any tutorial tests). State the reading in the design doc; a correction outranks it.
- Applies to: plan.py matrices, release verdict, docs/release.md, RFC 4.4/4.15, the revisions design doc.

### 2026-11-25 Frozen revisions have no exceptions
- Asked / situation: Q3: may a frozen revision get typo or broken-link fixes? (a) no, frozen like envs/lib, revisit if a fix is ever needed [recommended]; (b) allow them with a lint exception.
- They said: "3 -a"
- So: a revision is frozen like envs/lib: lint (b) has no exception, and sync does not touch revisions/. If a fix is ever needed, it goes back to them.
- Applies to: lint (b), sync, `revision start`, the design doc.

### 2026-11-25 New versions into tested: a bot PR, the maintainer merges
- Asked / situation: Q1 of the revisions-design gate: should a bot add a new KServe version to `versions.tested`? (a) canary passes -> bot opens the PR with the version-scout result attached, the maintainer merges; needs a PAT or GitHub App token (repository setting) [recommended]; (b) no bot, an agent runs the scout and opens the PR. They first asked what "canary" means.
- They said: "오 그렇군. a로 진행하는게 좋겠군 maintainer가 merge해야지." ("Oh, I see. Better to go with (a); the maintainer has to merge.")
- So: (a). Automation may go up to opening the PR; the merge stays theirs. The scout result travels with the PR, so the handbook Decision "scout before tested" holds (it is satisfied, not re-opened). The token (PAT or App) and the workflow permissions are a repository setting: theirs to set up, per action. Lesson about my questions: a term I used without explaining ("canary") cost them a round; explain project terms in the question itself.
- Applies to: scheduled.yml, the bot workflow, handbook Decisions (scout row), how questions are worded.
- Corrected on 2026-11-25 by "No AI in GitHub Actions" (below): the workflow opens the bot PR without the scout result; a local agent runs version-scout and adds it to the PR before the maintainer merges.

### 2026-11-25 Keep stable; release automatically once a month, skip when nothing changed
- Asked / situation: question 4 (relayed by the working agent): keep the `stable` branch or not, and how releases start (backlog D9, D12).
- They said: "4번은 b로 하고 gitaction으로 1달에 한번 stable branch로 옮기는거 어때? main이 망가질수도 있으니.." then "주단위는 너무 자주인거 같아.. 그렇게 자주 update될거 같지 않은데" then "좋다 변경이 없으면 tag생성없이 한다면 문제 없겠네 4번은 이렇게 정하자" ("4: (b), and how about a GitHub Action moving it to stable once a month? main may break.." / "weekly seems too often.. I do not think it will be updated that often" / "good, if there is no tag when nothing changed, no problem; let's decide 4 this way").
- So: `stable` stays, because main can break; readers only see a commit where the whole window passed together. release.yml runs by itself once a month (cron), not weekly. No new commit on main since the last release: skip (no verify, no tag). Verify fails: nothing moves, an issue is opened. The `YYYY.MM.N` tag, the GitHub Release and a manual `make release` stay. This replaces D12 (auto release after a green weekly run) and changes D9. The monthly publish to `stable` without asking each time is their own standing approval for that workflow only; it does not loosen "every git write by an agent needs permission".
- Applies to: release.yml, docs/release.md, backlog D9/D10/D12, handbook Decisions (stable row), RFC 4.15.

### 2026-11-25 Tutorial proposals for new features are issues
- Asked / situation: question 3 (relayed): how features from a new KServe release become tutorials.
- They said: "이슈로 두는게 좋을거 같은데" ("I think keeping them as issues would be good").
- So: one GitHub issue per candidate feature (label `tutorial-proposal`, from a template); they approve or reject on the issue; an approved issue becomes one tutorial PR (status draft), built by a local agent on Kind. The template, label and who files them are the working agent's reading, not their words. Filing each issue is a GitHub write: it still needs their permission (AGENTS.md How to work, step 4), the same as the planner's `plan` issues. Not answered yet: the adoption criteria.
- Applies to: new-release work, the issue template, the project-planner/version-scout split.

### 2026-11-25 No AI in GitHub Actions
- Asked / situation: the same discussion; where the AI steps run.
- They said: "ai는 모두 로컬에서 돌려야해 api key가 없거든" ("AI must all run locally; there is no API key").
- So: no workflow calls an AI CLI or API (none does today: no TUT_AI, claude or codex in .github/). Every AI step (version-scout, drafting, explainers, reviews, any feature-scouting) runs on a local machine. Workflows only prepare the work: a bot PR (new version in tested) or an issue ("new release vX"); a local agent then adds the AI part. A PAT or App token for PRs is not an AI key and stays allowed. Their reason is the missing key, so this may change if a key ever exists; until they say so, it is a rule.
- Applies to: every workflow, the Q1 bot PR, release-time feature scouting, any proposal that puts an agent in CI. A rule for everyone: belongs in AGENTS.md and the handbook Decisions.

### 2026-11-25 feature-scout is its own agent (relayed 2026-11-26)
- Asked / situation: how to build the scouting of new features of a KServe release: (1-a) extend version-scout, (1-b) a new agent `feature-scout`.
- They said: "1-b가 좋을거 같아" ("1-b seems good").
- So: a separate `feature-scout` agent, not a second job for version-scout; it is created in its own later PR, not in the RFC PR. Like every agent here it runs locally ("No AI in GitHub Actions"). One more agent was asked for this time; it does not license others (see "Open: agents by framework").
- Applies to: RFC 0002 section 8 and rollout, backlog C8, the version-scout file (it stays about breakage).

### 2026-11-25 Adoption criteria for tutorial proposals stay as proposed (relayed 2026-11-26)
- Asked / situation: question 2: the criteria for turning a new feature into a tutorial proposal: user-facing (not an internal refactor), runs on CPU kind (GPU waits for D7), API reasonably stable (alpha or feature gate flagged, lower priority), a mechanism to teach, no overlap with an existing tutorial.
- They said: "2번은 그대로 둔다" ("leave 2 as it is").
- So: the criteria are accepted as written; they go into the `tutorial-proposal` template and feature-scout as they are. The issue fields and the label name are still the working agent's design, not their words.
- Applies to: feature-scout, the issue template, reviews of proposals.

### 2026-11-25 Image mirroring on hold (relayed 2026-11-26)
- Asked / situation: a proposal to mirror the vLLM CPU image to quay after the public.ecr.aws 429s (backlog A10).
- They said: "image관련된것은 일단 안해도 돼" ("image-related things do not need doing for now").
- So: no image mirror, cache or registry work now; "for now" is a postponement, not a rejection. Adding new 429 evidence to A10 is fine; changing A10's status or plan is theirs. When a 429 hits CI again: one re-run per failure stays the rule (AGENTS.md How to work, step 5), record it in A10, do not start image work.
- Applies to: backlog A10, e2e ImagePullBackOff failures, proposals touching images or envs for pull speed.

### 2026-11-26 RFC 0002: the whole implementation, in one commit (relayed)
- Asked / situation: I had passed the RFC 0002 docs-only change; the implementation was planned as later PRs (rollout steps, feature-scout "in its own later PR").
- They said: "문서만 하지말고 전체적인 구현까지 모두다 해야지" and "1개의 commit으로 끝내자" ("do not do only the docs, do the whole implementation" / "let's finish it as one commit").
- So: for a design they decided, they want the design and its implementation to land together, not a docs PR followed by implementation PRs; this supersedes, for RFC 0002, "feature-scout is created in its own later PR" and the RFC's staged rollout. It does not make every change one commit: the pilot (C2) still needs a cluster run and was left out, which fits "try a new idea on one case" as a separate step. A bigger single change means the commit request must list each rule it adds (AGENTS.md hard rules, lint codes) and each thing that will act on its own after merge (scheduled workflows), because they approve it in one look.
- Applies to: PR boundaries for designs the maintainer decided; how a large commit request is written.

### 2026-11-26 RFC 0002 window: global N, skipped versions reported, dry run later (relayed)
- Asked / situation: three questions from the gate on the RFC 0002 implementation: (1) a tutorial that has not moved to N runs nowhere under one global N; (2) what runs for a tutorial whose `tested` has no N-1, and what happens to one that skipped versions (tested v0.18 and v0.21); (3) a release dry run before the first scheduled release.
- They said: "1.너가 찾은 문제는 맞아. 그런데 나는 0.19,0.20으로 차례로 올리면서 테스트를 할거라 이것은 자연스레 해결이 될거야. 그래도 강제로 revision을 만드는 부분이 있으면 좋을수 있겠다. 버젼을 건너뛸때도 필요하니깐 / 2. tested에 안들어있으면 N만 돌리면 되는거야. N-1은 tested version에 있는것을 의미하는거지. 만약에 이렇게 버젼이 건너뛴 tutorial이 있다면 나에게 알려줘.그리고 내가 허락하면 revision을 만들고 해당 tested에서 빼는거지. ... 어디서 new-version을 가져오는거야? upstream/kserve? / 3. 나중에 좀 하자 다 끝나서 나면 dry run을 하든지뭘하든지 해야지 지금은 너무 dev stage다" ("1: the problem you found is right, but I will move up 0.19, 0.20 one after the other while testing, so it resolves itself; still, a way to force a revision could be good, it is needed when skipping versions too / 2: if it is not in tested, run only N; N-1 means the one that is in tested. If a tutorial skipped versions like this, tell me; when I allow it, make the revision and take those versions out of tested. ... where does new-version come from? upstream kserve? / 3: later; when everything is done, do a dry run or whatever; now it is too dev stage").
- So:
  - One N for the whole repository stays; a lagging tutorial is not a defect to engineer around, they move tutorials one minor at a time. A command that makes a revision on demand is wanted (also for a version jump).
  - N-1 runs for a tutorial only if its `tested` lists it; else only N.
  - "Skipped" means a gap in a tutorial's tested minors (v0.18 then v0.21). That case is reported to them; the revision and the removal from `tested` happen only with their word, per tutorial. Old versions that are contiguous with the window are not "skipped": they stay in `tested` as "last verified" (2026-11-25 window entry); do not report them as needing a revision.
  - "Where does new-version come from" is a question, answer it with the facts: scheduled.yml asks `repos/kserve/kserve/releases/latest` (v0.21.0 on 2026-11-26), so the canary jumps to the newest release, not to the next minor.
  - Dry run: deferred by them, "too dev stage". My reading, not their words: a first real scheduled publish before that dry run is the same thing they deferred, so it is asked, not assumed.
- Applies to: plan.py window and `skipped()`, `./tut revision keep/start/todo`, the `ci-window` issue, release.yml schedule, RFC 0002 sections 3 and 8, backlog C8.

### 2026-11-26 N is the newest KServe release; N-1 is the newest version the tutorial tests below it (corrects the entry above)
- Asked / situation: in my recheck I wrote that for tested [0.17, 0.18, 0.20] the versions before the gap (0.17, 0.18) are caught for a revision. The working agent then asked them (AskUserQuestion) whether N is per tutorial or one for the repository, with X tested [0.18, 0.19] while another tutorial tests 0.21.
- They said: "[0.17, 0.18, 0.20] 이경우 0.18,0.20 이여야지" and "기본적으로 kserve 의 최신 버전이 N 이야. 각 tutorial에 해당 N이 없다면 N-1만 돌리면 된느거야" ("in the case [0.17, 0.18, 0.20] it should be 0.18, 0.20" / "basically N is the latest KServe version. If a tutorial does not have that N, just run N-1").
- So: N = the newest upstream KServe release, not the newest version any tutorial lists. N-1 is per tutorial: the newest minor it tests below N, not "the minor before N". CI runs N and that N-1 when the tutorial tests N, otherwise only that N-1. A tutorial never "runs nowhere", so "lagging" is gone. The working agent and I both read "N-1 = previous minor" and "N = newest tested in the repository"; both readings were wrong. This supersedes those parts of "RFC 0002 window: global N, skipped versions reported" (above) and of the 2026-11-25 window entry. Still from the entry above: skipped versions are reported and moved only with their word. My reading, not their words: a gap is still reported even though its N-1 runs. The dry-run question is not answered.
- Applies to: model.py latest/ci_minors, plan.py matrices and skipped(), release notes, RFC 0002 sections 3 and 8, every doc that defines the window. Lesson for me: when I write an example as if it were settled, they correct the example. Check examples against their words first.

### 2026-11-26 Monthly release schedule stays off until a first dry run (relayed)
- Asked / situation: dry run deferred ("too dev stage"), but merging RFC 0002 before Dec 1 would let release.yml publish for real on Dec 1 05:23 UTC: it would create `stable`, tag the first release and deploy the site, on a path never run. (a) commit the cron turned off until a first dry run passes [recommended]; (b) leave it on, a failure only opens an issue.
- They said: "a로 하자" ("let's go with a").
- So: the schedule is committed commented out; it is turned on by a one-line change after a first `make release` dry run passed, and that change goes to them like any other. Their monthly standing approval (2026-11-25) applies only once it is on. Fact for later, not their words: the first tag is `2026.12.0`, not `.1` (release.py counts N from 0); I had it wrong in the question.
- Applies to: release.yml, docs/release.md, backlog C8/D12, any later request to turn the schedule on.

### 2026-11-26 The repository pins its own newest version (N), not upstream (relayed)
- Asked / situation: nothing was asked; v0.21.0 is upstream's newest release, all four tutorials test v0.18.0.
- They said: "이 tutorial에서 사용하는 최신버젼을 우리가 지정하게 만들자 0.21이 현재 가장 최신의 것이지만 0.20으로 테스트를 진행하고 싶거든." then "kserve-tutorial repo에서 사용할 kserve의 최신버젼말이야." ("let us make it so we set the newest version these tutorials use; 0.21 is the newest now, but I want to test with 0.20" / "I mean the newest KServe version this kserve-tutorials repo uses"). The working agent proposed project.yaml `latest: v0.20.0` and `./tut latest`, used for CI N, the canary and the new-release issue, saying the canary/new-release part was its own call; they said "진행해" ("go ahead").
- So: N is chosen by the maintainer (project.yaml `latest`); upstream's newest release is only the fallback when no pin is set. This narrows "N is the newest KServe release" (2026-11-26, above): that stays true only without a pin. The canary and the new-release issue following the pin is the agent's proposal they did not object to, not their own words; a later word outranks it. One repository-wide pin, consistent with "one N for the whole repository".
- Applies to: model.latest, `./tut latest`, ci.yml/scheduled.yml/release.yml, RFC 0002 section 8, version-scout/feature-scout default targets, any doc that defines N.

### 2026-11-26 Pin v0.20 even though it skips v0.19
- Asked / situation: with `latest: v0.20.0` the canary and bot PR make the four tutorials' tested [v0.18.0, v0.20.0], a gap at v0.19 that the `ci-window` issue reports; earlier they had said they would move "0.19, 0.20 in order". (a) keep v0.20.0 and accept the gap report [recommended]; (b) pin v0.19.0 first, then v0.20.0.
- They said: "a로 하자" ("let's go with a").
- So: the pin stays at the version they name, even when it jumps a minor; the gap report that follows is expected, not a defect to prevent. "One minor at a time" (2026-11-26 window entry) was a plan, not a rule. What happens to the gap (revision, removal from tested) is still their word per tutorial.
- Applies to: project.yaml `latest`, canary/bot PR results, `ci-window` issue, `./tut revision keep`.
