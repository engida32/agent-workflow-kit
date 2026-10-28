# 02 - State, checkpoints and resuming

Principle: long work is many short sessions, not one giant one. Every session starts blind, so the disk must hold
the truth. If a fresh context cannot reconstruct the project from disk, you have a long prompt, not a workflow.

## Files (all under `<workspace>/.wf/`; deliverables stay in the workspace root)

| File | Holds |
|---|---|
| `state.json` | task, profile, stage, round, status, counters, limits |
| `criteria.json` | acceptance criteria (see `templates/criteria.json`) |
| `task_list.json` | plan units with done flags (advisory) |
| `progress.md` | append-only notes: done, in flight, next, failures and what was learned |
| `verify_N.json` | per-round verification results |
| `journal.jsonl` | append-only event log (stage changes, tools, errors, retries) |
| `transcript.json` | the current work round's conversation in a provider-neutral format |
| `research_transcript.json` | the latest research round's conversation |

Workspace deliverables, including `research.md`, stay at the workspace root, not in `.wf/`.

Write atomically (write a temp file, then rename). Append to the journal and progress notes; never rewrite history.

## Startup ritual (every session, every round)

1. Read `state.json`, `criteria.json`, `task_list.json`, the tail of `progress.md`, and list the workspace files.
2. Read `research.md` if it exists, then the latest `verify_N.json` feedback.
3. Run a quick sanity check that the workspace still works (tests pass, files open) before building more.
4. Pick the next unfinished unit. Work on one unit.
5. Before stopping or when context is getting long, write a progress note: done, in flight, next.

## Resuming

1. Read the files above. Trust the disk over memory of an earlier chat.
2. Resume at `state.stage`. If the stage transcript (`transcript.json` or `research_transcript.json`) ends in an
   assistant turn with tool calls whose results are missing, run those calls first, then continue. Make tool actions
   idempotent so a repeat is harmless.
3. If the stage was `verify`, run the verification again; it has no side effects.
4. If status is `paused`, the reason says why (outage, interrupt). If `needs_human`, answer the question or edit
   `criteria.json` first, then continue.
5. Never redo finished stages. Never silently change criteria mid-run; record any change in `progress.md`.

## Adopting work in progress

Use when there is no `.wf/` yet but the task is already underway (a half-built project, a plan from an earlier chat).

1. **Inventory**: list what exists (files, tests, notes). Run what can be run. Record the observed facts, not hopes.
2. **Reconstruct the goal**: write the task in one paragraph and confirm it with the user if there is any doubt.
3. **Draft criteria** from the goal plus what must already work; get the user's yes.
4. **Build `task_list.json`** from what remains. Mark a unit done only with evidence (a passing check, a file that
   exists and is correct). When unsure, leave it not-done.
5. Write `state.json` with stage `work` (or `verify` if the work looks complete) and a first `progress.md` entry
   that says "adopted at <time>; here is what was found".
6. Continue with the normal loop.

## Context hygiene

Long contexts degrade. Clear old tool outputs once used, keep notes on disk instead of in context, and prefer a
fresh session built from the startup ritual over dragging a huge transcript. When you feel pressure to wrap up
early, do not declare victory: write the handoff notes and let the next session continue.
