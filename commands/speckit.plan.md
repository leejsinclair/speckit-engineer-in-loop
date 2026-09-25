---
description: Plan the implementation from the approved Technical Specification and the traceable AI Specification, writing through the plan.md link.
strategy: wrap
---

## Guard (engineer-in-the-loop)

If `.specify/extensions/eil/scripts/python/eil` does not exist, STOP. Tell the user to run `specify extension add eil` and then `specify preset add engineer-in-the-loop`, and do nothing else: continuing without the helper would let a story bypass its gates.

## Before the core command

1. Run `python3 .specify/extensions/eil/scripts/python/eil enter plan --json`.
   - **Exit 3**: this feature is not a governed story. Skip everything in this wrapper and run the core command unchanged.
   - **Any other non-zero exit**: STOP and show the helper's `refusals` (code, message, fix): a stage that is not approved, a missing AI Specification (`ai-spec-missing`), an item without a source (`ai-spec-not-traceable`) or a pending clarification answer (`pending-clarification`). Do not work around a refusal; a configured confirmer may record a named override with `/speckit-eil-override`, and that is theirs to decide.
2. Run `python3 .specify/extensions/eil/scripts/python/eil stage-init plan --json`. It creates `s05-plan.md` from the plan template and `plan.md` as a link to it. If it says `already-exists`, continue with the existing plan.

In a governed story `plan.md` is a link to `s05-plan.md`. The core command below must **write through it**: never replace it with a separate file, and never write `spec.md` or `tasks.md`. The supporting files the core command produces (research, data model, contracts, quickstart) are ordinary files beside it, not stages.

{CORE_TEMPLATE}

## After the core command (governed stories only)

- **The plan is derived, not designed.** Every `##` section of `plan.md` names, in its heading, the approved decision it derives from: `## Summary (traces: DEC-001)`, using ids of the approved Technical Specification. Content that is **not derivable** from an approved decision is not written: raise it with `/speckit-eil-challenge` or as an open question, and never introduce architecture the design does not contain (FR-057).
- Run `python3 .specify/extensions/eil/scripts/python/eil check --stage plan --json` and fix what the code found. For the judgment criterion, decide honestly whether the plan adds architecture beyond the approved decisions, and pass your verdict in a judgments file outside the repository with `--judgments`.
- Finish with `python3 .specify/extensions/eil/scripts/python/eil sync --json`, then report the gate result and anything you flagged.
