# Known issues and limits

This file records behaviour that is intentional, unverified, or not yet worth
fixing. It exists so nobody discovers these the hard way in production.

## Not yet exercised against live providers

The provider adapters follow the public Anthropic and OpenAI-compatible message
formats, but this release has only been exercised by the offline test suite. Expect
small fixes on first contact with a real endpoint. If a wire-format bug bites, the
failure is usually a `Fatal` with the provider's error text; fix the adapter and add
a test with a recorded payload.

## A `failed` run is terminal

`resume` revives `paused` and `needs_human` runs. It does not revive `failed` runs,
including failures caused by a model returning invalid JSON twice. The state file is
kept for inspection. To retry, either fix the cause and start a new run in a fresh
workspace, or back up `.wf/` and delete `.wf/state.json`.

## Criteria are executable content

Executable criteria run shell commands. They follow `--approve`: `auto` runs them,
`ask` prompts once per command, and `deny` pauses verification. The safety deny list
still applies (destructive filesystem, partition, shutdown, fork-bomb and
pipe-to-shell patterns), but it is not a sandbox. An approved command runs with your
privileges. Review `.wf/criteria.json` before a run, especially when a model drafted
it.

## Supplied criteria skip confirmation

When you pass `--criteria file.json`, the criteria are accepted without the usual
human review prompt, even with `--confirm ask`. The file is your approval. If you
want the review step, omit `--criteria` and let the runtime draft criteria.

## In-flight work is replayed on resume

A tool that was executing when the process died is run again on resume, and the
assistant turn that requested it is re-requested from the model. Keep tool actions
idempotent. A command that timed out may have left partial effects.

## Rubric criteria are only as reliable as the judge

Judged criteria depend on the verifier model. A weak or agreeable judge can pass
work that a human would reject. Prefer executable criteria, use a different model for
the verifier role where possible, and treat a poor judge as a configuration bug.

## The workspace file list and verifier snapshot skip heavy directories

`.git`, `.wf`, virtualenvs, `node_modules` and cache directories are excluded from
`list_files` and from the verifier snapshot. If a deliverable legitimately lives in
one of those directories, move it or name it explicitly in the criteria.

## `fetch_url` redirects are not re-checked

Private, loopback and link-local addresses are blocked at DNS lookup. A redirect from
a public host to a private address is not re-validated, and DNS rebinding between the
check and the fetch is theoretically possible. Treat fetched pages as untrusted data.

## Locking is POSIX-only

The workspace lock uses `os.kill` to test whether the owning pid is alive. It targets
Linux and macOS. Windows is not supported. A rare race can report a lock as held
after taking over a stale one; retry once.

## Task skills after `pip install --user`

Installed task skills are looked up in the interpreter data directory, the user base,
and `WF_TASK_SKILLS_DIR`. A `--user` install into an unusual prefix may not be found.
Set `WF_TASK_SKILLS_DIR` to the directory containing `coding.md`, `design.md`,
`evaluation.md` and `research.md` if `load_skill` reports no skills.
