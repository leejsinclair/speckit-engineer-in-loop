---
description: Break the plan into tasks, each traced to the AI Specification, writing through the tasks.md link.
strategy: wrap
---

## Guard (engineer-in-the-loop)

If `.specify/extensions/eil/scripts/python/eil` does not exist, STOP. Tell the user to run `specify extension add eil` and then `specify preset add engineer-in-the-loop`, and do nothing else: continuing without the helper would let a story bypass its gates.

## Under the small-story profile

If `eil status --json` shows an active `profile`, do not present this stage's own inferred list. The AI Specification, plan and tasks are reviewed together, once, after the tasks are generated: run `eil review list --stage derived --kind inferred --json` and present it in the helper's `mode` (see Presenting a review list), recording the reply with `eil review answer --stage derived --kind inferred ...`. Planning and task generation proceed under the override the profile recorded (`overrides_used` in the `enter` result); implementation is refused until the derived list is answered.

## Reading a stage

Read a stage with `python3 .specify/extensions/eil/scripts/python/eil show <stage> --json` (add `--items <ids>` for just those items, or `--section "<heading>"` for one section), never by opening the whole document: `show` gives the content as a person reads it, with `[ai-draft]` after each block that still needs review and one readable line in place of each record. Open a stage document only to edit the part you are changing. **Never read `eil-record.json`**: it is the helper's record file, and `eil status` and `eil show` report what is in it.

## Presenting a review list

Present every review list exactly as the helper returns it, in the helper's `mode`:

- `one-at-a-time`: show one entry at a time, with its full text (`what`) and why it needs review, ask for that entry's answer, and store it at once with `eil review answer --stage <stage> --kind <kind> --digest <digest> --entry <key> --by "<name>" --reply "<their words, verbatim>" [--disposition except|question] --json`. Offer "ok to the rest" as you go: if the person says it, record it with `--rest` in place of `--entry`; the helper marks those entries as accepted without being shown in full.
- `summary`: show the `groups`, with each entry's `summary` and why it needs review, and ask for one reply to the whole list (`--all`, `--all-except <keys>` or `--question <keys>`). Show the full text of an entry, a group or the whole list whenever asked: `eil review show --stage <stage> --kind <kind> --entry <key>` (or `--group "<section>"`, or `--all`).

The helper stores each answer as it is given. **Never keep a tally of answers in chat**: after a pause or a compaction, run `review list` again; it returns only what is still unanswered. **Never list a block the helper did not return**, and never ask again about one it settled. A `§<Section>` entry stands for every block of that section, answered together.

## Before the core command

1. Run `python3 .specify/extensions/eil/scripts/python/eil enter tasks --json`.
   - **Exit 3**: this feature is not a governed story. Skip everything in this wrapper and run the core command unchanged.
   - **Any other non-zero exit**: STOP and show the helper's `refusals` (code, message, fix): a missing plan (`plan-missing`), or an artefact or diagram check that fails. Do not work around a refusal.
   - **Exit 0**: read `blocked[]` and `rederive[]`. **Never derive a task from an id in `blocked[]`**; say which tasks you are leaving out and show the `fix`. With an existing task list, re-derive **only** the tasks listed in `rederive[]`, in place, leaving all other text byte-identical, and keep each ticked box as it is.
2. Run `python3 .specify/extensions/eil/scripts/python/eil stage-init tasks --json`. It creates `s06-tasks.md` from the tasks template and `tasks.md` as a link to it. If it says `already-exists`, continue with the existing task list.

In a governed story `tasks.md` is a link to `s06-tasks.md`. The core command below must **write through it**: never replace it with a separate file, and never write `spec.md` or `plan.md`. Keep the sections after the last phase of the template (Not applicable, Challenges, Overrides, Quality Assessment).

{CORE_TEMPLATE}

## After the core command (governed stories only)

- **Every task line ends with `(traces: AIS-###)`**, naming the item of the AI Specification it carries out (or an approved decision, `DEC-###`). A task with no source is flagged, not accepted.
- **A task that builds a screen, a schema or a technical flow also cites the `ART` it implements**, for example `(traces: AIS-014, ART-007)`. Every wireframe, ER diagram and technical sequence diagram the AI Specification lists must be reached by at least one task; the check reports each one that is not.
- **A task must not introduce architecture** that the approved design does not contain. If a task would, do not write it: raise a challenge (`/speckit-eil-challenge`) so the human decides (FR-058).
- Run `python3 .specify/extensions/eil/scripts/python/eil check --stage tasks --json` and fix what the code found. For the judgment criterion, decide honestly whether any task introduces architecture, and pass your verdict in a judgments file outside the repository with `--judgments`.
- When you re-derive a task that carries a `(decided: CR-###)` clause, replace the clause with the current decision or remove it.
- Write a classification file outside the repository, run `python3 .specify/extensions/eil/scripts/python/eil blocks classify --stage tasks --json`, then run the one-reply list of `inferred` blocks: `eil review list --stage tasks --kind inferred --json`. Never write `[ai-draft]` by hand.
- Finish with `python3 .specify/extensions/eil/scripts/python/eil sync --json`, then report the gate result and anything you flagged.
