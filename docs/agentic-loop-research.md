# Designing the loop: research notes and decisions

This note records the research behind the kit's loop, the gaps found when the
loop was compared with that research, and the changes made in response. It is
written for maintainers. The short version belongs in the README.

The loop under review was:

```
research -> plan -> execute -> test/verify -> find improvement -> research -> plan
```

The kit already had most of that shape. The question was whether the stages,
the handoffs, and the recovery rules matched what Anthropic and OpenAI
actually recommend, and where the documentation promised more than the code
did.

## Sources

I read the primary pages on 2026-10-28. Dates below are the publication dates
shown on those pages.

| Source | Date | Used for |
|---|---|---|
| Anthropic, [Building effective agents](https://www.anthropic.com/research/building-effective-agents) | 2024-12-19, page updated 2026-10-09 | Workflow vs agent, pattern choice, evaluator-optimizer, ground truth, ACI |
| Anthropic, [Effective harnesses for long-running agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents) | 2025-11-26 | Sessions, progress files, feature lists, startup ritual, testing gap |
| Anthropic, [Harness design for long-running application development](https://www.anthropic.com/engineering/harness-design-long-running-apps) | 2026-03-24 | Generator/evaluator split, criteria, sprint contract, context resets |
| OpenAI, [A practical guide to building agents](https://cdn.openai.com/business-guides-and-resources/a-practical-guide-to-building-agents.pdf) | 2025-04-07 | Single-agent first, run exit conditions, layered guardrails, human escalation |

The two Anthropic long-running-agent posts are primary sources. The earlier version of
this repository's README said that only secondary summaries of them had been
read. That was true when the README was written, and it is no longer true.

## What the sources agree on

Five points recur across all four sources.

1. **Start with the least structure that can work.** Anthropic says to find the
   simplest solution and add complexity only when it is needed. OpenAI says to
   maximize a single agent first, add tools gradually, and move to multiple
   agents only when a single one falls short.

2. **Ground the loop in what actually happened.** Anthropic calls this ground
   truth from the environment at each step: tool results, code execution, a
   running app. A model's belief that it finished is not evidence.

3. **Completion needs an independent check.** Anthropic's long-running-agent work found
   that agents praise their own output, including mediocre output. Separating
   the maker from the evaluator was a strong improvement. The evaluator itself
   still needs calibration and hard thresholds.

4. **Long work is many short sessions.** Progress must survive a lost context.
   Anthropic's long-running-agent method uses a progress file, a structured feature
   list, and a startup ritual that reads both before touching code. OpenAI
   frames a run as a loop with explicit exit conditions, including a maximum
   number of turns.

5. **Autonomy needs limits and layered protection.** Both vendors recommend
   stopping conditions, sandboxing or approval for risky actions, and human
   escalation for irreversible or high-impact work. OpenAI adds a tool-risk
   rating: read-only versus write, reversible versus not, permissions, and
   financial impact.

## Where they differ

The differences matter more than the agreements, because they decide what the
kit should not build.

**Workflow first or agent first.** Anthropic presents workflows, with
predefined code paths, as the cheaper and more predictable option, and reserves
autonomy for open-ended work. OpenAI's guide starts from an agent loop and
describes orchestration patterns around it. For this kit the Anthropic framing
wins: the top-level loop is a workflow. Only the work stage is an agent loop.
That keeps routing, planning, verification, and recovery inspectable.

**One agent or several.** OpenAI recommends a single agent until there is
evidence for more. Anthropic's application-development setup uses a planner, a generator,
and an evaluator, but the authors say to remove components one at a
time and retest as models improve. The kit keeps three model roles (planner,
executor, verifier) but one executor. It does not add parallel workers or a
voting layer by default.

**Context resets or compaction.** Anthropic's later setup dropped automatic
context resets after newer models stopped showing "context anxiety". The kit
keeps compaction and a reset fallback for a provider that rejects a large
context. It does not reset on a schedule.

**How much the evaluator is worth.** Anthropic notes that an evaluator pays off
when the task is beyond what the model can do reliably alone, and that every
component encodes an assumption that can go stale. The kit treats the
verifier as the authority for completion, but keeps the option to use cheaper
executable checks for most criteria.

## The loop the kit should express

```
route -> criteria -> [research] -> plan -> work -> verify -> recover
                                              |         |
                                              +---------+  by failure cause
```

- **Route** picks a profile and the simplest pattern. One profile per run.
- **Criteria** are written before work, shown to a human, and treated as fixed.
  Prefer a command that exits zero. This is the programmatic gate Anthropic
  describes, and it plays the role of the sprint contract in that post:
  it says what done looks like and how it will be checked.
- **Research** is optional. It runs when the profile is `research`, or when the
  verifier says a failure came from missing knowledge. It writes `research.md`
  and does not build the deliverable.
- **Plan** produces a small list of units, each with a what and a why. It reads
  the research notes and the previous round's feedback.
- **Work** is the one agent loop. It loads the task skill, uses tools, works one
  unit at a time, and records progress notes.
- **Verify** runs executable criteria and judges rubric criteria with a fresh,
  skeptical verifier. The verifier returns a failure stage for each failed item.
- **Recover** goes back to the stage that failed. A work defect returns to
  work, a wrong approach deletes the plan and returns to plan, missing knowledge
  deletes the plan and returns to research, and an ambiguous criterion asks the
  human. Unknown causes fall back to work.

The loop stops on success, on a round, token, or wall-clock cap, or when the
number of failed must-pass criteria has not improved for two rounds.

## What the audit found

The protocol documents already described this loop. The runtime did not fully
implement it.

| Finding | Effect |
|---|---|
| Recover always advanced to work | A verifier that asked for plan or research was ignored. The run retried the same work with the same plan. |
| Plan ran only when `task_list.json` was missing | Even if the stage had been routed to plan, the planner would have been skipped. |
| No research stage existed | The research profile routed straight to plan. The `STAGE_HINTS` research entry was unreachable. |
| Research notes were not read from the workspace root | The first implementation read `research.md` through the `.wf` store, so the planner never saw the file the research agent wrote. |
| The README cited secondary summaries | The long-running-agent claims were weaker than they looked. |
| Setup and promptify were hard to find | The README explained features before it explained how to start, and it did not connect the promptify kickoff to `BRIEF.md`. |

The first three were documentation-versus-code drift, not missing features.
That is the more damaging kind: the docs told an agent to recover by cause, and
the runtime quietly did something else.

## Decisions

**Keep the workflow skeleton.** Routing, criteria, plan, work, verify, recover.
No orchestrator-workers by default, no parallel sectioning, no majority voting.
The eval set and the failure log do not justify the extra cost yet. A user who
needs parallel research can run separate workspaces.

**Add research as a real stage, not a prompt hint.** A stage needs a saved
artifact (`research.md`), a saved transcript, its own system prompt, and a
routing rule back into plan. A stage that cannot be reached and cannot be
re-entered is only a label.

**Replan after research.** Filling a knowledge gap can invalidate the plan. On
a research failure the runtime now deletes `task_list.json` as well as the
research transcript, so the planner runs again with the new notes and the
verifier's feedback. The same rule applies to a plan failure: delete the plan
and let the planner rebuild it.

**Keep the research artifact in the workspace root.** `.wf/` is state and is
excluded from the verifier snapshot and the file list the agent sees.
Deliverables, including `research.md`, live beside the work.

**Normalize unknown failure stages.** The verifier prompt allows implement,
plan, research, and criteria. A model can still return something else. Unknown
values now fall back to implement instead of routing to a stage that does not
exist.

**Keep executable failures at work.** An executable criterion has no model
opinion about why it failed. The runtime assigns those failures to work. The
verifier's failure-stage routing applies to rubric criteria, where a model can
distinguish a bug from a bad plan or a missing fact.

**Keep the human gate at criteria.** The runtime still pauses for review when
`--confirm ask` is used without a tty, and it still runs headless evaluation
with `--confirm auto`. Supplying `--criteria` skips the gate; that exception is
documented in `KNOWN_ISSUES.md` rather than hidden.

**Do not auto-invoke promptify.** The brief is a front door, not a stage. The
runtime takes a task string or a `BRIEF.md` that already exists. Automatically
calling another skill from inside the loop would add a second approval gate and
make the state machine depend on a skill registry.

**No new dependencies.** The loop changes are standard library only.

## What changed

The follow-up implementation PR adds:

- a `research` stage with `research_system_prompt`, `research_prompt`,
  `step_research`, and `research_transcript.json`;
- research before plan for the research profile;
- failure-stage recovery for plan, research, and criteria;
- research notes in the planner and work prompts, read from the workspace root;
- a shared `run_tool_loop` so research and work use the same resume, compaction,
  and turn-cap behavior;
- three routing tests: plan failure replans with feedback, research failure
  researches and replans, and the research profile runs research before plan;
- skill documentation for the optional stage and the real recovery table;
- a README organized around setup, the loop, and the sources.

It does not add a new provider, a sandbox, automatic multi-agent work, or live
API tests. The known limits in `KNOWN_ISSUES.md` still apply.

## What to measure next

The loop is now reachable end to end in offline tests, but offline tests do not
show that the extra stage improves outcomes. The next measurements should be:

1. Run the eval set with and without research routing on a task that needs
   external facts. Compare pass rate, rounds, and tokens.
2. Check whether the planner uses `research.md` or merely repeats it. A planner
   that ignores the notes is a cost with no benefit.
3. Calibrate rubric verdicts against a few human-scored examples. Anthropic's
   post is explicit that an uncalibrated evaluator can talk itself into
   approving weak work.
4. Re-test the stage routing after a model upgrade. The post's warning
   applies here too: every stage encodes an assumption about what the model
   cannot do alone.

## References

- Anthropic, "Building effective agents", 2024-12-19, updated 2026-10-09.
  https://www.anthropic.com/research/building-effective-agents
- Anthropic, "Effective harnesses for long-running agents", 2025-11-26.
  https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents
- Anthropic, "Harness design for long-running application development",
  2026-03-24.
  https://www.anthropic.com/engineering/harness-design-long-running-apps
- OpenAI, "A practical guide to building agents", 2025-04-07.
  https://cdn.openai.com/business-guides-and-resources/a-practical-guide-to-building-agents.pdf
