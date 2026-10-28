# 03 - Verification

Agents tend to praise their own work. Separate the maker from the checker and make completion depend on evidence.

## Criteria
- Written before the work starts, confirmed by the user, then treated as fixed. Changes are logged.
- 3-8 items. Each is `exec` (a command that exits 0 when satisfied) or `rubric` (judged from the files).
- Mark `must: true` only for items whose failure means the task is not done; the rest are nice-to-have.
- Prefer `exec`: tests, linters, schema checks, `grep` for required sections, file existence and size. Use rubric
  items only for what a command cannot check (clarity, correctness of reasoning, fit to audience).
- Make rubric items observable: "names at least three alternatives with a trade-off each" beats "is thorough".

## Independent evaluation
- The reviewer sees only the criteria and the deliverables, never the author's reasoning or self-assessment.
- Prefer a different model or at least a fresh session for the reviewer.
- Tell the reviewer to be skeptical and to pass an item only when the evidence is in the files.
- For subjective items, run the judgment two or three times and take the majority.
- The reviewer returns, per item: passed, a one-line reason, and a failure stage
  (implement, plan, research, or criteria).
- For interactive things (a web page, an app), verify by using them (run them, click through) and not by reading code.

## Calibrate
Keep a few examples of good and bad outputs with the verdicts you agree with. When the reviewer disagrees with you,
fix the reviewer prompt with those examples, not the criteria.

## Done means
Every must-pass criterion passed in the most recent verification of the current files. Not "I think it works".
