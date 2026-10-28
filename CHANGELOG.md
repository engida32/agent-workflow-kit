# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.2] - 2026-10-28

### Added

- Documented a brief-first kickoff path for new projects (`BRIEF.md`).
- Added `skill/templates/brief.md` and `AGENT_PROMPT.md` Prompt 0.

## [0.1.1] - 2026-10-28

### Fixed

- An empty `providers` object, a null provider spec, or a non-object `state.json`
  now reports a clean error and exit code 2 instead of an `IndexError`,
  `AttributeError` or traceback.
- A missing API key during auto-detection reports exit code 2 as documented, not 1.

### Changed

- CI now covers Python 3.10 and 3.11 as well, matching the documented 3.9-3.14 range.
- The example config ships with the wheel under `share/agent-workflow/`.
- Three regression tests cover the malformed config and state paths; the suite is
  now 25 tests.

## [0.1.0] - 2026-10-28

First public release.

### Added

- Installable skill (`skill/`) with six protocols, four task skills, templates and an
  agent prompt for new work, resume, and handover.
- Standard-library Python runtime (`runtime/`) enforcing route, criteria, plan, work,
  independent verify, and failure-cause recovery.
- Resumable state: atomic writes after every stage and turn, pid lock with stale-lock
  takeover, mid-turn resume, context compaction and reset.
- Provider-neutral transcript with per-role fallback chains for Anthropic,
  OpenAI-compatible endpoints, and command-line agents.
- Retry with exponential backoff, jitter and Retry-After; outage pause with exit code
  75; explicit exit codes for passed, paused, needs-human and failure.
- Executable and rubric criteria, a safety deny list for executable criteria, and a
  workspace-contained tool layer with secret scrubbing.
- Ten-task evaluation set (`eval/eval_tasks.json`) covering coding, research, design
  and evaluation profiles.
- Twenty-two offline tests covering resilience, resume, locking, provider wire
  formats, workspace scanning, verifier normalization and CLI error handling.
- Packaging: `pip install .` exposes the `workflow` command and installs the task
  skills; CI runs the suite and the installed-command smoke test on Python 3.9, 3.12,
  3.13 and 3.14.

### Known limits

See `KNOWN_ISSUES.md`. The adapters have not yet been exercised against live
providers, a `failed` run is terminal, and executable verification commands are not
gated by `--approve`.
