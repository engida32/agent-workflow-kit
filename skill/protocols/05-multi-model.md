# 05 - Working across different models and agents

Design for portability from the start.

- **Neutral state.** Checkpoints use a provider-neutral message format (user text, assistant text + tool calls,
  tool results). Convert at the edge, not in the core. Any model can pick up a saved round.
- **Fresh context per round.** Each round is rebuilt from files, so switching models between rounds loses nothing.
- **Roles, not models.** Configure a chain of models per role (router, planner, executor, verifier). Cheap and fast for
  routing, strongest for execution, a different family for verification when possible.
- **Only common features.** Plain tool calling with JSON Schema inputs and text output. Do not depend on a vendor's
  built-in tools, special reasoning modes or response formats.
- **Defensive parsing.** Ask for JSON only, extract the first valid JSON value, retry once with a reminder, then fail
  clearly. Never trust that a smaller model followed the format.
- **Weaker or local models.** Use smaller units, more explicit criteria, more executable checks and fewer judged ones.
  Keep tool sets small and names obvious.
- **Wrapping an existing agent.** Any CLI that accepts a prompt on stdin and prints text can fill a role. If it does
  its own tool use inside the workspace, mark it a native agent and let it run the work step while this workflow still
  owns routing, criteria, verification, state and recovery.
- **Same rules for every executor.** The completion gate is the verifier, whatever model or agent did the work.
