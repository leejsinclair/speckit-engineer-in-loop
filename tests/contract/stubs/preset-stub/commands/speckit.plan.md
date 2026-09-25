---
description: Stub wrap of speckit.plan used by the risk-spike contract tests.
strategy: wrap
---

## Guard (engineer-in-the-loop)

If `.specify/extensions/eil/scripts/python/eil` does not exist, STOP and tell the user to run
`specify extension add eil` and then `specify preset add engineer-in-the-loop`.

Run `python3 .specify/extensions/eil/scripts/python/eil enter plan --json`. On a non-zero exit,
print the refusals and stop. Exit 3 means the feature is not governed: continue with the core command.

{CORE_TEMPLATE}
