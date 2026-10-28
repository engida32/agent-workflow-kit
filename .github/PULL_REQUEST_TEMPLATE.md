# Pull request

## Summary

<!-- What changed, and why? Link the issue if there is one. -->

Fixes #

## Type of change

- [ ] Bug fix
- [ ] New feature
- [ ] Documentation
- [ ] Tests or CI
- [ ] Packaging or release
- [ ] Breaking change

## How it was tested

<!-- Commands, manual checks, or eval tasks you ran. -->

```text
python3 -m unittest discover -s runtime/tests -v
```

## Checklist

- [ ] One focused change, not several unrelated changes.
- [ ] A test covers every behaviour change.
- [ ] The offline suite passes.
- [ ] The runtime and the skill still describe the same behaviour.
- [ ] Documentation is updated when behaviour or setup changes.
- [ ] No secrets, API keys, absolute home paths, or generated `.wf/` state.
- [ ] Safety gates and verifier checks were not weakened to make a test pass.

## Breaking change notes

<!-- If this changes the state schema, CLI, config, or protocol, describe the
migration and what existing workspaces need. Otherwise write "None". -->
