---
description: Assemble the AI Specification from the approved stages (how should the AI execute the approved design?).
argument-hint: "Anything the developer wants emphasised, such as files to reuse or patterns to follow"
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

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

## What this stage is for

The AI Specification translates the **approved** Requirements, Functional and Technical Specifications into an implementation context that an AI coding agent can execute. It does not redesign anything and it decides nothing: it restates what a human has already approved, with a pointer back to where each thing came from. There is no human approval of this stage; the passing check is the gate, and a human review is offered. Every gate below is decided by the `eil` helper, not by you.

Every call below is `python3 .specify/extensions/eil/scripts/python/eil <subcommand> --json`. **Stop on any non-zero exit** and show the helper's `refusals` (code, message, fix). Exit 3 means there is no governed story: offer `/speckit-eil-requirements`.

## Steps

1. **Synchronise**: run `eil sync --json`.
2. **Start the stage**: run `eil stage-init ai-spec --json`. It is refused (`stage-not-approved`) until Requirements, Functional and Technical all carry a current approval; do not work around that. It creates `s04-ai-spec.md` and `spec.md` as a link to it. If `s04-ai-spec.md` already exists, continue from it.
3. **Read** the approved Requirements, Functional and Technical Specifications, and the AI Specification, with `eil show <stage> --json` (or `--items` for the ids you need). Read the existing code the design touches.
4. **Assemble only from the approved stages.** Under each section of the template write items, one per line: `**AIS-001**: the instruction, stated for the agent (traces: FR-001, DEC-004)`.
   - Every item traces to at least one approved `REQ`, `UC`, `FR`, `NFR`, `DEC` or `ART`. The check reports any item without a source, any trace to something that is not approved, and any text outside an item.
   - **Do not write anything without a source.** If you find something the approved stages do not say (a missing edge case, an unstated constraint, a decision nobody made), do not fill it in: raise it as a challenge with `eil challenge add ... --severity high|medium|low` (the severity is required), or put it to the human as an open question, and leave it out. The human decides; you execute. Never introduce a functional or architectural decision here.
   - **Never write `[ai-draft]` by hand.** The helper renders that cue itself, from your classification file (see the classification step). A person reviews only the blocks you mark `inferred`.
   - `Existing Code` and the optional `Agent Guidance` may name files, patterns and commands from the repository; each still needs an item tracing to the requirement or decision it serves.
5. **List the artefacts the agent must read** under `Artefacts in Scope`, one `AIS` item per approved `ART`, tracing to its id: `**AIS-013**: Read the container view before changing the API. (traces: ART-004)`. **Draw no diagram of your own** here: the approved Mermaid diagrams are directly readable, and a wireframe is read from its export. Any wireframe, ER diagram or technical sequence diagram you list must later be covered by a task.
6. **Check**: run `eil check --stage ai-spec --json` and fix what the code found. The gate is source-traceability, no pending clarification answer, and no listed artefact changed since its stage was approved. Re-run until it is met.
7. **Classify and list the inferred blocks.** Write a classification file outside the repository: `{"stage": "ai-spec", "blocks": [{"block": "AIS-001", "adds": null}]}`, one entry per block you wrote or changed. A block that restates an approved source has no `adds`; a block that goes beyond its sources carries `adds`, one sentence saying what it adds. Run `eil blocks classify --stage ai-spec --file <path> --json`; the helper decides restated, decided or inferred from the traces and hashes, and renders the review cue itself. Then run `eil review list --stage ai-spec --kind inferred --json` and show the human that one list. They answer once, in their own words (for example "ok except AIS-003"); pass their reply verbatim to `eil review answer --stage ai-spec --kind inferred --digest <digest> --reply "<their words>" --by "<name>" [--all-except <ids>] --json`. Never answer for them. When you re-edit an item that carries a `(decided: ID)` clause, replace or remove the clause so it still matches the text.
8. **Report** the result, every `[ai-draft]` tag, every challenge you raised and every artefact that changed since approval. Offer a human review of the document, and say that `/speckit-plan` can start once the check passes.
9. **Finish**: run `eil sync --json`.

## Rules

- When you re-edit an item that carries a `(decided: CR-###)` clause, remove or replace the clause; never leave one that no longer matches the text.

- You never record an approval or edit the `assessment` region by hand, and you never answer a challenge on the human's behalf.
- A clarification answer you collect later is written as a pending item and carried upstream with `/speckit-eil-resolve`; it is not a source until then.
