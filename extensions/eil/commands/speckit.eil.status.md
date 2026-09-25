---
description: Show where the story is, who approved what, what is outstanding, and the single next action.
argument-hint: "No input needed"
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## Guard (engineer-in-the-loop)

If `.specify/extensions/eil/scripts/python/eil` does not exist, STOP. Tell the user to run `specify extension add eil` and then `specify preset add engineer-in-the-loop`, and do nothing else: continuing without the helper would let a story bypass its gates.

## What this command is for

Report the state of the governed story: its current stage, each stage's derived state, who approved what and when, what is outstanding, and what to do next. It changes nothing except refreshing the generated overview and the alias mirrors, and it is also run automatically after `clarify`, `plan`, `tasks` and `implement` so those never leave the overview stale. **It never refuses anything** (a hook carries no refusal; the gates live in the helper's own commands).

Every call below is `python3 .specify/extensions/eil/scripts/python/eil <subcommand> --json`. Exit 3 means the feature is not governed by this workflow: say so in one sentence (`/speckit-eil-1-requirements` starts a story) and stop; that is not an error.

## Steps

1. **Synchronise**: run `eil sync --json`. It refreshes the overview and reports any alias fault (a missing, wrong or diverged `spec.md`, `plan.md` or `tasks.md`); state any fault plainly.
2. **Read the state**: run `eil status --json`.
3. **Report**, from the helper's output only:
   - the current stage and each stage's state (`not-started`, `draft`, `in-review`, `approved`, `needs-re-review`), with the reason for any `needs-re-review` and any abbreviated stage;
   - the approvals (who, when) and, for Functional and Technical, the comprehension counts;
   - what is outstanding: open questions, open challenges, pending clarifications, overrides, accepted risks, and any document error under `issues`;
   - the artefacts and any that are not `ok`;
   - the alias health;
   - if `overview.current` is false, that `s00-README.md` was hand-edited or out of date and has been regenerated: the stage documents are the authority.
4. **End with the single next action** exactly as `next` gives it. Do not invent a different one.

## Rules

- Report facts from the helper. Do not summarise, soften or add to a document's own text, and do not decide whether a stage is ready.
