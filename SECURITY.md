# Security policy

## Reporting a vulnerability

Open a private security advisory on GitHub
(https://github.com/engida32/agent-workflow-kit/security/advisories/new) rather than a
public issue. Include a minimal reproduction and the affected version.

## Scope

The interesting surfaces are:

- command execution during `run_command` and executable verification criteria,
- workspace path containment (`safe_path`) and the write gate,
- secret scrubbing of the environment passed to commands,
- untrusted web content handling in `fetch_url`,
- the workspace lock and state files.

## Not in scope

- Prompt injection that changes only the model's wording, without crossing a tool or
  path boundary.
- The security of third-party model providers.
- Running untrusted code with `--approve auto` outside a sandbox. That flag is a
  documented foot-gun, not a vulnerability.

## Supported versions

The latest release on `main` is supported. This is a 0.x project; fixes land on
`main` and in a patch release.
