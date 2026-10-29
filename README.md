# Agent Workflow Kit

**Long-running agent work that survives interruption, model changes, and its own mistakes.**

[Quick start](#quick-start) · [Ongoing sessions](#use-it-in-an-ongoing-session) · [How it works](#how-it-works) · [Design notes](#design-notes) · [Portfolio](https://engida.devs.et/)

[![CI](https://github.com/engida32/agent-workflow-kit/actions/workflows/ci.yml/badge.svg)](https://github.com/engida32/agent-workflow-kit/actions/workflows/ci.yml)
[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-3776AB.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

Agent Workflow Kit is a small, resumable workflow for tasks that need more than one model turn: coding, research, design, evaluation, or anything else where a single prompt is not enough.

The model works in short sessions instead of one giant conversation. State lives on disk. An independent checker decides when the work is done, not the agent that wrote it. If a provider fails, the run pauses and resumes from the same stage. The same workspace can be continued by a different model.

Built by [Engida Lishan](https://engida.devs.et/).

## Why use it

| Property | What it gives you |
|---|---|
| **Resumable** | Every stage writes its state to `.wf/`, so a crash, rate limit, or provider outage does not erase progress. |
| **Verifiable** | Acceptance criteria run as commands or go to a fresh verifier. The maker does not grade its own work. |
| **Recoverable** | A failure returns to the stage that caused it: work, plan, research, or criteria. |
| **Portable** | The protocol is provider-neutral. Swap models or run the same workspace from another agent. |

It ships in two forms that follow the same protocol:

| Form | Use it when | What it is |
|---|---|---|
| `skill/` | You work interactively in an agent that can read files | A skill with protocols, templates, and task skills. The agent follows the loop by hand. |
| `runtime/` | You want an unattended run, repeatable checks, or automatic resume | A Python program (standard library only) that enforces the loop in code. |

Start with `AGENT_PROMPT.md` if you are using the skill form. Use `workflow` if you want the runtime.

## Use it in an ongoing session

You do not need to restart your project or open a new chat. Install the skill form once, then paste this into the session that is already running:

> Use the agent-workflow skill in this repo on the work already here. Read `skill/SKILL.md` directly, then read `.wf/state.json` if it exists and resume from the saved stage. Do not rebuild completed work. If there is no state, turn the current task into acceptance criteria, show them to me, and wait.

The agent will:

1. Read the saved state and continue from the stage that stopped.
2. Keep completed work, criteria, and progress notes intact.
3. If there is no saved run, turn the current task into criteria and wait for your review before starting.

For the runtime form, the equivalent is:

```bash
workflow resume workspace --config runtime/config.json
```

If the workspace has no state yet, start it with `workflow run` as shown in [Quick start](#quick-start).

## How it works

```
route -> criteria -> (research) -> plan -> work -> verify -> recover
                                          ^                   |
                                          |___________________|
```

| Stage | What happens |
|---|---|
| **Route** | Pick a profile: coding, research, design, or evaluation. |
| **Criteria** | Write 3 to 8 acceptance criteria before any work. Prefer commands that run. A human confirms them. |
| **Research** | Optional. Runs before planning for the `research` profile, or when the verifier finds a knowledge gap. It writes `research.md` and is asked not to build the deliverable. |
| **Plan** | Break the work into 3 to 7 units. Say what and why, not how. The planner reads `research.md` when it exists. |
| **Work** | Work the next unfinished units, using the matching task skill. Append progress notes as you go. |
| **Verify** | Run the executable criteria. Judge the rest with a fresh, skeptical reviewer that sees only the task, criteria, and files. The reviewer tags each failure as implementation work, plan, research, or criteria. |
| **Recover** | Go back to the stage that failed. A work defect returns to work. A wrong approach replans. Missing knowledge runs research and then replans. An ambiguous criterion stops for a human. |

This is prompt chaining with an evaluator-optimizer loop: the path and handoffs are fixed, and one agent makes the decisions inside each bounded stage. Research is a stage, not a separate swarm by default.

## What survives a crash

Everything the next session needs is on disk under `<workspace>/.wf/`:

| File | Purpose |
|---|---|
| `state.json` | task, profile, stage, round, status, limits, feedback |
| `criteria.json` | acceptance criteria |
| `task_list.json` | plan units and done flags |
| `progress.md` | append-only notes: done, in flight, next, failures |
| `verify_N.json` | verification results and evidence for each round |
| `journal.jsonl` | append-only event log |
| `transcript.json` | this work round's provider-neutral conversation |
| `research_transcript.json` | the latest research conversation |

Deliverables, including `research.md`, stay in the workspace root. A lock prevents two runs from using one workspace at the same time. A dead process's lock is taken over.

## Install

You need Python 3.9 or newer for the runtime. It has no third-party dependencies.

### Install the skill form

Copy the skill into your agent's skills directory. For OpenCode:

```bash
mkdir -p ~/.config/opencode/skills/agent-workflow
cp -R skill/. ~/.config/opencode/skills/agent-workflow/
```

Restart the agent after copying so it discovers the new skill. For another agent, use its skills directory, or point the agent at `skill/SKILL.md` by path.

Then give the agent `AGENT_PROMPT.md`. Prompt A starts new work, Prompt B resumes, and Prompt C hands over to a different model. The agent reads one protocol at a time and saves state after every step.

### Install the runtime

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

## Quick start

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

Without installing, run `python -m workflow` from `runtime/` instead. From that directory use `--config config.json` and `-w ../workspace`.

With no config file the runtime auto-detects `ANTHROPIC_API_KEY`, or `OPENAI_API_KEY` plus `WF_OPENAI_MODEL`. A wheel install ships the example config under `<sysconfig data>/share/agent-workflow/config.example.json`.

Exit codes:

| Code | Meaning |
|---|---|
| 0 | every must-pass criterion passed |
| 75 | paused by a service disruption; resume later |
| 3 | needs a human decision |
| 2 | other failure, including malformed config or state |

Useful options:

- `--confirm auto` skips the criteria review. Do not use it when you have not reviewed the criteria.
- `--approve auto|ask|deny` controls shell commands, including executable verification criteria. `ask` prompts once per command; `deny` pauses verification instead of running it. Use `auto` only in a sandbox.
- `--criteria file.json` supplies criteria directly and skips the interactive review.
- `--profile coding|research|design|evaluation` skips profile routing.
- `resume --add-rounds 2 --add-tokens 200000` continues after a limit stopped the run.
- `resume --retry-failed` retries a run that ended in `failed` after you fix the cause.
- Set `"outage_wait_seconds": 3600` in the config's `resilience` block to keep probing during a long outage before pausing.
- Set `"verifier_votes": 3` in the config's `limits` block to control independent rubric ballots. One vote disables majority voting.

> **Review executable criteria before running them.** `--approve auto` executes model-written shell commands. The deny list catches destructive patterns, but it is not a sandbox. An approved command runs with your privileges.

Do not run the skill form and the runtime against the same `.wf/` at the same time. The runtime owns the lock and the stage transitions.

## Starting a new project

A vague idea should become a brief before it becomes autonomous work. The kit does not bundle a briefing skill, but it works with [promptify](https://github.com/engida32/promptify-skill): it turns a raw idea into a short `BRIEF.md` after a bounded set of questions, before any code is written. If promptify is not installed, write the brief by hand.

The handoff is explicit:

1. Invoke promptify, or write `BRIEF.md` by hand from `skill/templates/brief.md`.
2. Keep `BRIEF.md` at the workspace root, not in `.wf/`.
3. Start agent-workflow with that brief as the task source.

The skill form reads `BRIEF.md` before routing. In runtime mode, the runtime does not parse the brief for you, so put its decisions into the task string or the criteria file. There is no automatic promptify-to-workflow handoff.

A brief should record the goal, who it is for, observable success signals, non-goals, constraints, assumptions with falsifiers, and open questions with defaults. Acceptance criteria come from the success signals; the workflow should not re-ask what the brief already answers.

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

Ten tasks across the four profiles. Finished tasks are skipped when you rerun. `--approve auto` executes model-written commands, so run the eval in a container.

## Tests

The test suite is offline and needs no API key:

```bash
python3 -m unittest discover -s runtime/tests -v
```

50 tests cover retries, Retry-After, provider fallback, outage pause and resume, mid-turn resume, locking, provider wire formats, CLI-agent wrapping, workspace scanning, verifier normalization, executable-criteria safety, verification approval gates, criteria re-checks after a human edit, malformed config and state, research before planning, failure-stage routing back to plan or research, state-schema migration, failed-run retries, eval reruns that skip terminal runs, rubric majority voting, verification evidence, corrupt-state rejection, secret and symlink snapshot filtering, malformed criteria, and non-interactive criteria holds.

CI runs the suite and an installed-command smoke test on Python 3.9 through 3.14.

## Design notes

The loop was checked against primary sources from Anthropic and OpenAI. The full notes, including where they disagree, are in [`docs/agentic-loop-research.md`](docs/agentic-loop-research.md).

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

- The provider adapters follow the public message formats but have not been run against live APIs. Expect small fixes on first contact. The state machine and recovery logic are covered by offline tests.
- Resume re-requests the turn that was in flight. A tool that was executing when the process died is run again, so keep tool actions idempotent.
- Locking uses `os.kill`, so the runtime targets Linux and macOS.
- `fetch_url` blocks private addresses at lookup time but does not stop a redirect from a public host to a private one.
- Rubric criteria are only as reliable as the judge. Prefer commands.
- A run that ends in `failed` keeps its state for inspection. Fix the cause, then run `resume --retry-failed`.
- Executable criteria are commands. They follow `--approve`, and the deny list applies, but an approved command still runs with your privileges. Review criteria before a run.
- `--criteria` skips the interactive criteria review, even with `--confirm ask`.

The full list is in [`KNOWN_ISSUES.md`](KNOWN_ISSUES.md).

## Maintainers

Before a release:

1. Run the offline suite and the packaging smoke test in a clean virtual environment.
2. Check that the skill and runtime still agree on stage names and artifacts.
3. Update `CHANGELOG.md` and bump the version in `pyproject.toml` and `runtime/workflow/__init__.py`.
4. Open a pull request and wait for all required CI checks to pass.
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

Bug reports and focused pull requests are welcome. Read [`CONTRIBUTING.md`](CONTRIBUTING.md) first: one change per PR, a test for every behaviour change, offline tests, and no new runtime dependencies. `main` is protected, so every change lands through a pull request with passing CI. Participation is covered by the [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md), and project decisions follow [`GOVERNANCE.md`](GOVERNANCE.md). Security issues go through [`SECURITY.md`](SECURITY.md), not the public tracker.

## Author

Built and maintained by [Engida Lishan](https://engida.devs.et/), a full-stack and AI engineer. More work and case studies are on the [portfolio](https://engida.devs.et/).

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
