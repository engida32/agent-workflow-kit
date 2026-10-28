# 01 - Choosing the pattern

Principle (Anthropic, "Building effective agents"): find the simplest solution that works and add complexity only
when results prove it is needed. Start with the model API directly; many patterns are a few lines of code.

**Workflow** = predefined code path with model calls at each step. Predictable, cheap, testable.
**Agent** = the model decides its own steps and tool use in a loop. Flexible, costlier, needs guardrails.

Decision order:
1. Can one well-prompted call, with retrieval and a couple of examples, do it? Stop there.
2. Are the steps known in advance? Use a workflow pattern below.
3. Are the steps unknown and the task open-ended? Use one agent loop with tools and skills, plus the guardrails in
   this kit.

| Pattern | Use when | Example here |
|---|---|---|
| Prompt chaining | Task splits cleanly into fixed sequential steps | route -> criteria -> plan |
| Routing | Different input types need different handling | profile selects the task skill |
| Parallelization (sectioning) | Independent subtasks can run at once | researching several sub-questions |
| Parallelization (voting) | One check is unreliable, run it several times | judging a subjective rubric item |
| Orchestrator-workers | Subtasks cannot be predicted up front | a large change touching unknown files |
| Evaluator-optimizer | Clear criteria, and iteration measurably helps | work -> independent verify -> fix |

Keep a separate subagent only when it earns its context: parallel research in fresh contexts, independent
verification, or work that reads far more than the main agent needs afterwards. Otherwise fold it into one loop
that loads skills on demand.

Measure before you add structure: run the same small eval before and after every architectural change.
