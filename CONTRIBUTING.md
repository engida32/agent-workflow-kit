# Contributing

Thanks for picking this up. The kit is deliberately small and standard-library only,
so the fastest way to help is to run it, break it, and send a focused pull request.

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
Branch from `main` and open a pull request. Direct pushes to `main` are reserved for
release commits.

```bash
git switch -c fix/short-description
git commit -m "fix: apply the safety deny list to verification commands"
```

## Reporting security issues

Do not open a public issue for a vulnerability. See `SECURITY.md` for the private
channel and scope. The relevant surface is command execution, workspace path
containment, secret scrubbing, and untrusted web content.

## License

By contributing you agree that your contribution is licensed under the MIT License
in `LICENSE`.
