# Contributing

Thanks for picking this up. The kit is deliberately small and standard-library only,
so the fastest way to help is to run it, break it, and send a focused pull request.

## Before you start

- Read [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md). It applies to issues, pull
  requests, and every other project space.
- For a bug or a small fix, open a pull request directly.
- For a change to the workflow stages, the verifier contract, the safety model,
  the CLI, or the state schema, open an issue first so the design can be agreed
  before you spend time on code.
- `main` is protected. Every change lands through a pull request with passing CI.

## Ground rules

- One change per pull request. A bug fix does not need a new feature bolted on.
- Every behaviour change needs a test. The suite in `runtime/tests/` is offline and
  must stay offline: no network, no API keys, no wall-clock sleeps.
- Keep the runtime dependency-free. If a change needs a package, open an issue first.
- Do not commit `.wf/` state, API keys, or generated `eval_runs/` output.
- Never weaken a safety gate or a verifier check just to make a test pass.

## Development setup

```bash
git clone https://github.com/engida32/agent-workflow-kit.git
cd agent-workflow-kit
python3 -m unittest discover -s runtime/tests -v
```

Then check the installed path, which is where packaging bugs hide:

```bash
python3 -m venv /tmp/awk-venv
/tmp/awk-venv/bin/pip install .
/tmp/awk-venv/bin/workflow --version
/tmp/awk-venv/bin/python -c "from workflow.cli import task_skills_dir; print(task_skills_dir())"
```

## What to check before opening a pull request

1. `python3 -m unittest discover -s runtime/tests -v` passes.
2. `python3 -m workflow --help` works from `runtime/` with no third-party packages.
3. If you touched packaging, the clean-venv install above still finds the task skills.
4. If you touched a protocol document, the runtime and the skill still describe the
   same behaviour. Drift between `skill/` and `runtime/` is a bug.
5. No secrets, absolute home paths, or machine-specific names in the diff.

## Commit and branch style

Use conventional commits: `feat:`, `fix:`, `docs:`, `test:`, `chore:`, `ci:`.
Branch from `main` and open a pull request. Direct pushes to `main` are blocked.

```bash
git switch -c fix/short-description
git commit -m "fix: apply the safety deny list to verification commands"
```

Pull requests are squash merged, so the pull request title becomes the commit on
`main`. Write it as a conventional commit, for example
`fix: apply the safety deny list to verification commands`.

## Review and merge

- All six Python CI jobs and the CodeQL analysis must pass.
- The branch must be up to date with `main` before merge.
- Review conversations must be resolved.
- A maintainer reviews the change. With one maintainer, an approving review is
  not a separate merge requirement, so do not wait for a green approval tick.
- Keep the pull request small enough to review. Split unrelated work.

See [`GOVERNANCE.md`](GOVERNANCE.md) for decision making and release policy.

## Reporting issues

Use the issue templates. A bug report needs the version or commit, the surface
(runtime, skill, packaging, docs), a minimal reproduction, and redacted logs. A
feature request starts with the problem and the smallest change that would solve
it. Blank issues are disabled so reports arrive with the details needed to act.

## Reporting security issues

Do not open a public issue for a vulnerability. See [`SECURITY.md`](SECURITY.md)
for the private channel and scope. The relevant surface is command execution,
workspace path containment, secret scrubbing, and untrusted web content.

## License

By contributing you agree that your contribution is licensed under the MIT License
in `LICENSE`.
