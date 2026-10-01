---
description: Clarify the AI Specification. Each accepted answer is written into it as a pending item until it has been carried to the earliest stage it affects.
strategy: wrap
---

## Guard (engineer-in-the-loop)

If `.specify/extensions/eil/scripts/python/eil` does not exist, STOP. Tell the user to run `specify extension add eil` and then `specify preset add engineer-in-the-loop`, and do nothing else: continuing without the helper would let a story bypass its gates.

## Before the core command

Run `python3 .specify/extensions/eil/scripts/python/eil enter clarify --json`.

- **Exit 3**: this feature is not a governed story. Skip everything in this wrapper and run the core command unchanged.
- **Any other non-zero exit**: STOP and show the helper's `refusals` (code, message, fix). `ai-spec-missing` means there is nothing to clarify yet: the AI Specification comes first (`/speckit-eil-ai-spec`). Do not work around a refusal.

In a governed story the "spec file" of the core command below is `spec.md`, which is a link to `s04-ai-spec.md`. Write through it: never replace it with a separate file, and never write `plan.md` or `tasks.md` from this command.

{CORE_TEMPLATE}

## After the core command (governed stories only)

For **each answer the human accepted**, write it into `s04-ai-spec.md` as a new item in the section it belongs to, on one line: `**AIS-###**: the answer, stated as an instruction to the agent [pending-clarification]`. Use the next free `AIS` number, and give it **no** `(traces: ...)` clause yet: an answer has no source until it has been carried upstream. Do not put the answer anywhere else, and do not edit `s01`, `s02` or `s03` from here.

Then tell the human, for each pending answer, to run `/speckit-eil-resolve` so the answer is carried to the earliest stage it affects. Until that is done the items and tasks that trace to the pending answer are blocked and the overview lists the answer as an outstanding issue. Everything else stays open: run `python3 .specify/extensions/eil/scripts/python/eil enter implement --json` and tell the human which tasks remain implementable (those not in `blocked[]`) and which wait for the answer.

Finish with `python3 .specify/extensions/eil/scripts/python/eil sync --json`.
