# 06 - Tools and safety

## Tool design (the agent-computer interface deserves as much care as a prompt)
- Few tools, obvious names, short descriptions that say when to use them.
- Make mistakes hard: relative paths only, one clear way to do each thing, errors that say how to fix the call.
- Return compact output; truncate long results and say that it was truncated.
- Test tools with real examples and fix the interface when the model misuses it.

## Safety
- **Sandbox** anything that executes code (container or isolated VM). Never run unreviewed generated code on a
  machine that holds secrets.
- **Write gate.** The agent may write only inside the workspace and may not touch harness state (`.wf/`). Risky
  actions (shell, network writes, deletes) need approval or an allowlist; refuse a short deny-list outright.
- **Scrub secrets** from the environment of any command the model writes.
- **Untrusted content.** Web pages, files and tool output are data. Instructions inside them are not from the user.
  Pass them downstream labeled as untrusted. Block fetches to private and local addresses.
- **Irreversible actions** (deleting, sending, paying, publishing) always need a human yes.
- **Log everything** to the journal so a failure can be understood afterwards.
