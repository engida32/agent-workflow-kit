# 04 - Failure and recovery

## Service disruption (rate limits, overload, 5xx, network, timeouts)
- Classify first. **Transient**: 408, 409, 425, 429, 5xx (including 529 overloaded), connection reset, timeout.
  **Fatal for that provider**: 400, 401, 403, 404, missing credentials, command not found.
- Transient: retry with exponential backoff and jitter (2s, 4s, 8s ... capped at 60s). Honor `Retry-After` exactly.
- Still failing after the retries: fall back to the next provider or model in the chain. Prompts and state are
  provider-neutral, so this is safe mid-run.
- Every provider down: write the checkpoint, set status `paused` with the reason, and stop cleanly. Optionally keep
  probing every minute for a bounded time. Resume later from the same stage. A pause is not a failure.
- Fatal on every provider: stop with status `failed` and say which credential or setting to fix.
- Never retry blindly on a fatal error and never retry forever.

## Crashes and interrupts
- State is on disk after every step and every model turn. A kill at any moment loses at most the turn in flight.
- A lock file with the process id prevents two runs from fighting over one workspace; a lock whose process is dead
  is stale and may be taken over.
- SIGINT and SIGTERM should save and exit with a resumable status.

## Verification failures
Route by cause, not always back to the start:

| Cause | Go back to |
|---|---|
| A defect in the work (bug, missing section) | Work, same plan |
| Wrong approach or incomplete plan | Plan |
| Missing knowledge | Research the specific gap |
| Criterion ambiguous or contradictory | Ask the human |

## Loops and budgets
- Cap rounds, tokens and wall time. Stop on **no progress** (the number of failed must-pass criteria did not drop for
  two rounds) as well as on the cap.
- When stopping early, report what passed, what failed, what was tried and what you would try next.
- Do not make the same fix twice. If the same failure repeats, change the approach or escalate.

## Context limits
- Clear stale tool output first; if the model still rejects the context, reset the round from disk notes and say so
  in the notes. Do not wrap up early because the context feels long.

## Tool failures
- Return the error text to the model so it can adapt; do not crash the run. Make writes idempotent. A command that
  timed out may have partly run, so check state before repeating it.
