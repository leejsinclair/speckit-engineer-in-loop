---
description: Implement the tasks. Ambiguities are surfaced for a human decision, never assumed.
strategy: wrap
---

## Guard (engineer-in-the-loop)

If `.specify/extensions/eil/scripts/python/eil` does not exist, STOP. Tell the user to run `specify extension add eil` and then `specify preset add engineer-in-the-loop`, and do nothing else: continuing without the helper would let a story bypass its gates.

## Before the core command

Run `python3 .specify/extensions/eil/scripts/python/eil enter implement --json`.

- **Exit 3**: this feature is not a governed story. Skip everything in this wrapper and run the core command unchanged.
- **Any other non-zero exit**: STOP and show the helper's `refusals` (code, message, fix): a missing plan or task list, a pending clarification answer, an AI Specification that does not pass its check, or an alias the helper could not repair. Do not work around a refusal.

The files `spec.md`, `plan.md` and `tasks.md` are links (or read-only mirrors) to `s04`, `s05` and `s06`. Read them as usual; when the core command marks a task done, edit `tasks.md` only, and never replace any of the three with a separate file.

{CORE_TEMPLATE}

## While implementing (governed stories only)

- **Surface ambiguities; never assume.** If the AI Specification, the plan or a task is silent, unclear or contradictory on something that changes what you would build, **stop that piece of work**, put the question to the human, and record the answer through `/speckit-clarify` (or `/speckit-eil-resolve` when it belongs in an earlier stage). Do not proceed on an assumption nobody recorded (FR-041).
- Implement only what the approved design contains. If a task seems to need architecture the design does not contain, stop and raise it as a challenge.
- After each change to code that carries a task, note the commit or pull request against the task's item with a `(code: <sha>)` or `(code: PR#n)` clause, so the chain from requirement to code can be traced.
- Finish with `python3 .specify/extensions/eil/scripts/python/eil sync --json`.
