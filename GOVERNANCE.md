# Governance

This is a small project with a single maintainer. The goal is to keep decisions
predictable and contributions easy to review.

## Maintainer

`@engida32` is the current maintainer. The maintainer merges pull requests,
publishes releases, handles security reports, and enforces the code of conduct.

## Decisions

- Small fixes and documentation changes are decided in the pull request.
- Changes to the workflow stages, the verifier contract, the safety model, or the
  state schema start as an issue so the design can be discussed before code.
- When there is disagreement, the maintainer decides and records the reason in the
  pull request or in `docs/`.

## Review and merge policy

- `main` is protected. Every change lands through a pull request.
- Required CI checks must pass and the branch must be up to date before merge.
- Conversations on the pull request must be resolved.
- Direct pushes, force pushes, and deletion of `main` are blocked.
- The project uses squash merges, so each pull request becomes one commit on
  `main`. Write the pull request title as a conventional commit.
- A maintainer reviews every pull request. Because the project currently has one
  maintainer, an approving review is not a separate merge requirement.

## Releases

Releases are cut from `main` after the test suite and packaging check pass. The
version follows semantic versioning. The changelog and release notes describe
user-visible changes. Tags and releases are created by the maintainer.

## Becoming a maintainer

There is no formal path yet. Sustained, high-quality contributions and helpful
reviews are the signal. The current maintainer can invite a contributor to help
with triage or review when that trust exists.

## Security

Do not report vulnerabilities in public issues. Use the private channel in
`SECURITY.md`.
