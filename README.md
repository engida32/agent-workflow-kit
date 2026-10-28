# Agent Workflow Kit

A small, resumable workflow for long tasks: coding, research, design, evaluation, or anything else that needs more
than one model turn.

The kit makes the model work in short sessions instead of one giant conversation. State lives on disk. An independent
checker decides when the work is done, not the agent that wrote it. If a provider fails, the run pauses and resumes
from the same stage. The same workspace can be continued by a different model.

It ships in two forms that follow the same protocol:

| Form | Use it when | What it is |
|---|---|---|
| `skill/` | You work interactively in an agent that can read files | A skill with protocols, templates, and task skills. The agent follows the loop by hand. |
| `runtime/` | You want an unattended run, repeatable checks, or automatic resume | A Python program (standard library only) that enforces the loop in code. |

Start with `AGENT_PROMPT.md` if you are using the skill form. Use `workflow` if you want the runtime.

## The loop

```
route -> criteria -> (research) -> plan -> work -> verify -> recover
                                          ^                   |
                                          |___________________|
```

1. **Route.** Pick a profile: coding, research, design, or evaluation.
2. **Criteria.** Write 3 to 8 acceptance criteria before any work. Prefer commands that run. A human confirms them.
3. **Research (optional).** Runs before planning for the `research` profile, or when the verifier finds a knowledge
   gap. It writes `research.md` and is asked not to build the deliverable.
4. **Plan.** Break the work into 3 to 7 units. Say what and why, not how. The planner reads `research.md` when it
   exists.
5. **Work.** Work the next unfinished units, using the matching task skill. Append progress notes as you go.
6. **Verify.** Run the executable criteria. Judge the rest with a fresh, skeptical reviewer that sees only the
   task, criteria and files. The reviewer tags each failure as implementation work, plan, research, or criteria.
7. **Recover.** Go back to the stage that failed. A work defect returns to work. A wrong approach replans. Missing
   knowledge runs research and then replans. An ambiguous criterion stops for a human.

This is prompt chaining with an evaluator-optimizer loop: the path and handoffs are fixed, and one agent makes the
decisions inside each bounded stage. Research is a stage, not a separate swarm by default.

## What survives a crash

Everything the next session needs is on disk under `<workspace>/.wf/`:

| File | Purpose |
|---|---|
| `state.json` | task, profile, stage, round, status, limits, feedback |
| `criteria.json` | acceptance criteria |
| `task_list.json` | plan units and done flags |
| `progress.md` | append-only notes: done, in flight, next, failures |
| `verify_N.json` | verification result for each round |
| `journal.jsonl` | append-only event log |
| `transcript.json` | this work round's provider-neutral conversation |
| `research_transcript.json` | the latest research conversation |

Deliverables, including `research.md`, stay in the workspace root. A lock prevents two runs from using one workspace
at the same time. A dead process's lock is taken over.

## Install

You need Python 3.9 or newer for the runtime. It has no third-party dependencies.

```bash
git clone https://github.com/engida32/agent-workflow-kit.git
cd agent-workflow-kit
python3 -m venv .venv
. .venv/bin/activate
pip install .
workflow --version
```

You can also install straight from GitHub:

```bash
pip install "git+https://github.com/engida32/agent-workflow-kit.git"
```

### Install the skill form

Copy the skill into your agent's skills directory. For OpenCode:

```bash
mkdir -p ~/.config/opencode/skills/agent-workflow
cp -R skill/. ~/.config/opencode/skills/agent-workflow/
```

Restart the agent after copying so it discovers the new skill. For another agent, use its skills directory, or point
the agent at `skill/SKILL.md` by path.

Then give the agent `AGENT_PROMPT.md`. Prompt A starts new work, Prompt B resumes, and Prompt C hands over to a
different model. The agent reads one protocol at a time and saves state after every step.

## Start a new project

A vague idea should become a brief before it becomes autonomous work. The kit does not bundle a briefing skill, but it
works with [promptify](https://github.com/engida32/promptify-skill): it turns a raw idea into a short `BRIEF.md` after a
bounded set of questions, before any code is written. If promptify is not installed, write the brief by hand.

The handoff is explicit:

1. Invoke promptify, or write `BRIEF.md` by hand from `skill/templates/brief.md`.
2. Keep `BRIEF.md` at the workspace root, not in `.wf/`.
3. Start agent-workflow with that brief as the task source.

The skill form reads `BRIEF.md` before routing. In runtime mode, the runtime does not parse the brief for you, so put
its decisions into the task string or the criteria file. There is no automatic promptify-to-workflow handoff.

A brief should record the goal, who it is for, observable success signals, non-goals, constraints, assumptions with
falsifiers, and open questions with defaults. Acceptance criteria come from the success signals; the workflow should
not re-ask what the brief already answers.

## Quick start with the runtime

```bash
cp runtime/config.example.json runtime/config.json
# edit models and provider names; API keys come from environment variables
export ANTHROPIC_API_KEY=...
workflow run "Write slugify.py with tests" -w workspace --config runtime/config.json
```

If the run is interrupted, rate limited, or the provider goes down:

```bash
workflow resume workspace --config runtime/config.json
workflow status workspace
```

Without installing, run `python -m workflow` from `runtime/` instead. From that directory use `--config config.json`
and `-w ../workspace`.

With no config file the runtime auto-detects `ANTHROPIC_API_KEY`, or `OPENAI_API_KEY` plus `WF_OPENAI_MODEL`.
A wheel install ships the example config under `<sysconfig data>/share/agent-workflow/config.example.json`.

Exit codes:

| Code | Meaning |
|---|---|
| 0 | every must-pass criterion passed |
| 75 | paused by a service disruption; resume later |
| 3 | needs a human decision |
| 2 | other failure, including malformed config or state |

Useful options:

- `--confirm auto` skips the criteria review. Do not use it when you have not reviewed the criteria.
- `--approve auto|ask|deny` controls shell commands, including executable verification criteria. `ask` prompts once per
  command; `deny` pauses verification instead of running it. Use `auto` only in a sandbox.
- `--criteria file.json` supplies criteria directly and skips the interactive review.
- `--profile coding|research|design|evaluation` skips profile routing.
- `resume --add-rounds 2 --add-tokens 200000` continues after a limit stopped the run.
- `resume --retry-failed` retries a run that ended in `failed` after you fix the cause.
- Set `"outage_wait_seconds": 3600` in the config's `resilience` block to keep probing during a long outage before
  pausing.
- Set `"verifier_votes": 3` in the config's `limits` block to control independent rubric ballots. One vote disables
  majority voting.

Do not run the skill form and the runtime against the same `.wf/` at the same time. The runtime owns the lock and the
stage transitions.

## Profiles and task skills

| Profile | Task skill | Notes |
|---|---|---|
| `coding` | `skill/task-skills/coding.md` | Plan, small files, tests, root-cause fixes. |
| `research` | `skill/task-skills/research.md` | Runs the research stage before planning and writes `research.md`. |
| `design` | `skill/task-skills/design.md` | Audience, constraints, an artifact file, rejected alternatives. |
| `evaluation` | `skill/task-skills/evaluation.md` | Rubric first, evidence, a review with prioritized fixes. |

Any profile can be sent back to research by the verifier when the failure is missing knowledge.

## Eval

```bash
workflow eval eval/eval_tasks.json --out eval_runs --config runtime/config.json --confirm auto --approve auto
```

Ten tasks across the four profiles. Finished tasks are skipped when you rerun. `--approve auto` executes
model-written commands, so run the eval in a container.

## Tests

The test suite is offline and needs no API key:

```bash
python3 -m unittest discover -s runtime/tests -v
```

40 tests cover retries, Retry-After, provider fallback, outage pause and resume, mid-turn resume, locking, provider
wire formats, CLI-agent wrapping, workspace scanning, verifier normalization, executable-criteria safety, verification
approval gates, criteria re-checks after a human edit, malformed config and state, research before planning,
failure-stage routing back to plan or research, state-schema migration, failed-run retries, eval reruns that skip terminal runs,
rubric majority voting, and verification evidence.

CI runs the suite and an installed-command smoke test on Python 3.9 through 3.14.

## How the guidance was applied

The loop was checked against primary sources from Anthropic and OpenAI. The full notes, including where they disagree,
are in [`docs/agentic-loop-research.md`](docs/agentic-loop-research.md).

Sources:

- Anthropic, [Building effective agents](https://www.anthropic.com/research/building-effective-agents), December 2024.
- Anthropic, [Effective harnesses for long-running agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents), November 2025.
- Anthropic, [Harness design for long-running application development](https://www.anthropic.com/engineering/harness-design-long-running-apps), March 2026.
- OpenAI, [A practical guide to building agents](https://cdn.openai.com/business-guides-and-resources/a-practical-guide-to-building-agents.pdf), April 2025.

| Guidance | Where it shows up |
|---|---|
| Find the simplest solution first; add complexity only when results prove it is needed | one loop, optional research, no agent swarm by default |
| Workflow steps where the path is known, an agent where it is not | route, criteria, plan and verify are bounded stages; work is an agent loop |
| Gain ground truth from the environment at each step | executable criteria; tool results; no completion claim without a check |
| Write the plan and pause at checkpoints | criteria confirmation, plan file, `needs_human` on ambiguity |
| Work in short sessions and leave artifacts | `.wf/` state, progress notes, transcripts, a unit-level plan |
| Do not mark work done without testing | per-unit plan, independent verifier, executable checks |
| Separate the maker from the checker; agents praise their own work | fresh skeptical verifier, different model preferred |
| Stop conditions and budgets | max rounds, turns, tokens and wall time; no-progress stop |
| Layer guardrails and escalate high-risk actions | write gate, deny list, secret scrubbing, approval modes, human stop |
| Start with one agent and add tools incrementally | four profiles, four task skills, a small fixed tool set |

## Honest limits

- The provider adapters follow the public message formats but have not been run against live APIs. Expect small fixes
  on first contact. The state machine and recovery logic are covered by offline tests.
- Resume re-requests the turn that was in flight. A tool that was executing when the process died is run again, so
  keep tool actions idempotent.
- Locking uses `os.kill`, so the runtime targets Linux and macOS.
- `fetch_url` blocks private addresses at lookup time but does not stop a redirect from a public host to a private one.
- Rubric criteria are only as reliable as the judge. Prefer commands.
- A run that ends in `failed` keeps its state for inspection. Fix the cause, then run `resume --retry-failed`.
- Executable criteria are commands. They follow `--approve`, and the deny list applies, but an approved command still
  runs with your privileges. Review criteria before a run.
- `--criteria` skips the interactive criteria review, even with `--confirm ask`.

The full list is in [`KNOWN_ISSUES.md`](KNOWN_ISSUES.md).

## Maintainers

Before a release:

1. Run the offline suite and the packaging smoke test in a clean virtual environment.
2. Check that the skill and runtime still agree on stage names and artifacts.
3. Update `CHANGELOG.md` and bump the version in `pyproject.toml` and `runtime/workflow/__init__.py`.
4. Open a pull request and wait for all six CI jobs to pass.
5. Tag and publish only after maintainer approval.

Repository discoverability is a GitHub setting, not a file in the repo. Set topics once with:

```bash
gh repo edit engida32/agent-workflow-kit \
  --description "Resumable, provider-neutral agent workflow with independent verification" \
  --add-topic agentic-workflow --add-topic ai-agents --add-topic llm \
  --add-topic agent-orchestration --add-topic workflow --add-topic python \
  --add-topic resumable --add-topic verification --add-topic anthropic \
  --add-topic openai --add-topic developer-tools --add-topic prompt-engineering
```

## Contributing

Bug reports and focused pull requests are welcome. Read [`CONTRIBUTING.md`](CONTRIBUTING.md) first: one change per
PR, a test for every behaviour change, offline tests, and no new runtime dependencies. `main` is protected, so every
change lands through a pull request with passing CI. Participation is covered by the
[`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md), and project decisions follow [`GOVERNANCE.md`](GOVERNANCE.md). Security
issues go through [`SECURITY.md`](SECURITY.md), not the public tracker.

## License

MIT. See [`LICENSE`](LICENSE).

## Layout

```
AGENT_PROMPT.md          prompts to hand to your agent
skill/                   installable skill (SKILL.md, protocols/, templates/, task-skills/)
runtime/                 Python runtime (workflow/, tests/, config.example.json)
eval/eval_tasks.json     10-task eval set
docs/                    research notes and design decisions
pyproject.toml           packaging and the `workflow` entry point
.github/                 issue and PR templates, CodeQL, Dependabot, CODEOWNERS
CODE_OF_CONDUCT.md       community expectations and enforcement
GOVERNANCE.md            maintainer, review, merge and release policy
KNOWN_ISSUES.md          intentional limits and unverified behaviour
```
