# Agent Workflow Kit

A general-purpose, resumable agent workflow for any task type (coding, research, design, evaluation). It ships in two
forms that follow the same protocol:

1. **`skill/`** - an installable skill (SKILL.md, protocols, templates, task skills). Give it to any agent that can
   read files; the agent follows the protocol by hand.
2. **`runtime/`** - a small Python program (standard library only) that enforces the protocol in code: checkpoints,
   retries, model fallback, independent verification, budgets.

Start with `AGENT_PROMPT.md`.

## Install

The runtime has no third-party dependencies (Python 3.9+).

```bash
# from a checkout
python3 -m venv .venv && . .venv/bin/activate
pip install .

# or straight from GitHub
pip install "git+https://github.com/engida32/agent-workflow-kit.git"

workflow --version
```

The skill form needs no install. Copy the `skill/` directory into your agent's skills
folder, for example:

```bash
cp -R skill ~/.config/opencode/skills/agent-workflow
```

Then hand the agent `AGENT_PROMPT.md` and point it at the copied `SKILL.md`.

## What it does

route -> criteria (you confirm) -> plan -> work -> independent verify -> fix by failure cause -> done

- **Survives disruption.** Transient errors (429, 5xx, 529 overloaded, network, timeouts) are retried with backoff and
  jitter, honoring Retry-After. Persistent failures fall back to the next model in the chain. If everything is down the
  run saves state, sets status `paused` (exit code 75) and stops. `resume` continues from the exact stage, and from
  the exact turn inside the work stage.
- **Resumes after crashes.** State is written atomically after every stage and every model turn, so even `kill -9`
  costs at most one turn. A lock prevents two runs on one workspace; a dead process's lock is taken over.
- **Works with different models and agents.** The saved conversation is provider-neutral, each round is rebuilt from
  disk, and roles (router, planner, executor, verifier) each have their own fallback chain. Built in: Anthropic API,
  any OpenAI-compatible endpoint (OpenAI, Gemini compat, OpenRouter, Ollama, vLLM...), and any command-line agent
  (as a text role, or as a "native agent" executor that does its own tool use).
- **Adopts work in progress.** `protocols/02-state-and-resume.md` explains how to take over a half-finished task.

## How Anthropic's guidance is applied

Sources: Anthropic's "Building effective agents" (anthropic.com/engineering/building-effective-agents) and
Anthropic's engineering posts on harnesses for long-running agents ("Effective harnesses for long-running agents",
"Harness design for long-running application development"; I could only read secondary summaries of the latter two).

| Guidance | Where |
|---|---|
| Simplest solution first; workflows for known steps, an agent only when needed | `protocols/01-patterns.md`, one loop with skills |
| Prompt chaining, routing, evaluator-optimizer | route/criteria/plan chain, profile routing, work -> verify -> fix |
| Invest in the agent-computer interface | `runtime/workflow/tools.py`: few clear tools, relative paths only, truncated output |
| Persistent progress file, task list, startup ritual, one unit per session | `.wf/progress.md`, `task_list.json`, `step_work` rebuilds context from disk |
| Completion is a property of the artifact, not the transcript | verifier gate; the agent's own "done" is ignored |
| Separate generator and evaluator (agents praise their own work) | independent skeptical verifier, different model preferred |
| Planner says what and why, not how | planner prompt |
| Context management: clear stale tool results, reset when needed | `compact()` and `reset_transcript()` |
| Sandboxing, untrusted content, human approval for risk | `protocols/06-tools-and-safety.md`, write gate, scrubbed env |
| Measure changes with evals | `eval/eval_tasks.json`, `workflow eval` (resumable) |

## Quick start (runtime)

```
cp runtime/config.example.json runtime/config.json      # edit models, keys come from env vars
export ANTHROPIC_API_KEY=...                            # and/or OPENAI_API_KEY=...
workflow run "Write slugify.py ..." -w workspace --config runtime/config.json
# interrupted, rate limited, or provider down?
workflow resume workspace --config runtime/config.json
workflow status workspace
```

Without an install, run `python -m workflow` from `runtime/` instead. These commands
assume the repo root; from `runtime/`, use `--config config.json` and `-w ../workspace`.
A wheel install ships the example config at
`<sysconfig data>/share/agent-workflow/config.example.json`.
With no config file, it auto-detects `ANTHROPIC_API_KEY` (or `OPENAI_API_KEY` plus `WF_OPENAI_MODEL`).
Exit codes: 0 passed, 75 paused (resume later), 3 needs a human, 2 other failure.

Useful options: `--confirm auto` (skip the criteria review), `--approve auto|ask|deny` (shell commands; use `auto`
only in a sandbox), `--criteria file.json`, `--profile coding|research|design|evaluation`,
`resume --add-rounds 2 --add-tokens 200000` to continue after a limit stopped it.
For long outages set `"outage_wait_seconds": 3600` in `resilience` and the run keeps probing before it pauses.

## Eval

```
workflow eval eval/eval_tasks.json --out eval_runs --config runtime/config.json --confirm auto --approve auto
```
10 tasks across the four profiles. Run before and after every change; finished tasks are skipped on re-run.
`--approve auto` executes model-written commands, so run this inside a container.

## Tests (offline, no API key)

```
python -m unittest discover -s runtime/tests -v
```
25 tests cover backoff, Retry-After, fallback, outage pause, resume without re-planning, mid-turn resume, a crash
between a model turn and its tool run, locking, provider wire formats, CLI-agent wrapping, workspace scanning,
verifier verdict normalization, the executable-criteria deny list and malformed config or state handling.

## Honest limits

- Not yet run against live APIs; the provider adapters follow the public message formats but expect small fixes on
  first contact. The state machine and recovery logic are covered by the offline tests above.
- Resume re-requests the turn that was in flight; a tool that was executing when the process died is re-run, so keep
  tool actions idempotent.
- Locking uses `os.kill`, so it is meant for Linux and macOS.
- `fetch_url` blocks private addresses at lookup time but does not stop a redirect from a public host to a private one.
- Rubric (judged) criteria are only as reliable as the judge; prefer executable criteria.

The full list, including terminal `failed` runs, ungated verification commands, and
`fetch_url` redirect handling, is in [`KNOWN_ISSUES.md`](KNOWN_ISSUES.md).

## Contributing

Bug reports and focused pull requests are welcome. Read
[`CONTRIBUTING.md`](CONTRIBUTING.md) first: one change per PR, a test for every
behaviour change, and no new runtime dependencies. Security issues go through
[`SECURITY.md`](SECURITY.md), not the public tracker.

## License

MIT. See [`LICENSE`](LICENSE).

## Layout

```
AGENT_PROMPT.md          prompts to hand to your agent
skill/                   the installable skill (SKILL.md, protocols/, templates/, task-skills/)
runtime/                 python runtime (workflow/, tests/, config.example.json)
eval/eval_tasks.json     10-task eval set
pyproject.toml           packaging and the `workflow` entry point
.github/workflows/ci.yml test + install smoke test on Python 3.9-3.14
KNOWN_ISSUES.md          intentional limits and unverified behaviour
```
