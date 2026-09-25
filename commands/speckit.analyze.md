---
description: Analyze the story. The standard analysis over spec.md, plan.md and tasks.md, followed by a check of the whole traceability chain.
strategy: wrap
---

## Guard (engineer-in-the-loop)

If `.specify/extensions/eil/scripts/python/eil` does not exist, STOP. Tell the user to run `specify extension add eil` and then `specify preset add engineer-in-the-loop`, and do nothing else: continuing without the helper would let a story bypass its gates.

## Before the core command

Run `python3 .specify/extensions/eil/scripts/python/eil enter analyze --json`.

- **Exit 3**: this feature is not a governed story. Skip everything in this wrapper and run the core command unchanged.
- **Any other non-zero exit**: STOP and show the helper's `refusals` (code, message, fix).

In a governed story `spec.md`, `plan.md` and `tasks.md` are links (or read-only mirrors) to the AI Specification, the plan and the task list. The core command reads them as usual, and its analysis stays read-only.

{CORE_TEMPLATE}

## After the core command (governed stories only)

Its standard behaviour over the three files is unchanged: do not drop, reword or reorder any of its findings. **Then also check the whole chain**, from the requirements onward, which the three files alone cannot show:

1. Run `python3 .specify/extensions/eil/scripts/python/eil check --chain --json`.
2. Append its `gaps` to the report as a section headed **Traceability chain (engineer-in-the-loop)**, in the same table style as the core findings and with the helper's ids, which start with `T-` so they cannot collide with the core ids: `| T-001 | Traceability | HIGH | FR-009 | ... | ... |`. Use the helper's severity, `where` and `message` as they are. The chain check covers every requirement having a functional requirement, every functional requirement having a requirement, every technical decision tracing to functional requirements, every AI Specification item having an approved source, every task tracing to the AI Specification, and every artefact tracing to something.
3. If there are no gaps, say the chain is complete. Add the helper's gaps to the counts in the metrics, and to the recommendation: a chain gap of HIGH severity is resolved before `/speckit-implement`.
4. Remain read-only: do not edit any stage document. Suggest the command that fixes each gap (for example `/speckit-eil-functional` for a requirement with no functional requirement).
