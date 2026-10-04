---
description: Record a stage approval. The human's own confirmation is what approves; the AI never does.
argument-hint: "Which stage to approve (requirements, functional, technical or completion)"
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## Guard (engineer-in-the-loop)

If `.specify/extensions/eil/scripts/python/eil` does not exist, STOP. Tell the user to run `specify extension add eil` and then `specify preset add engineer-in-the-loop`, and do nothing else: continuing without the helper would let a story bypass its gates.

## Reading a stage

Read a stage with `python3 .specify/extensions/eil/scripts/python/eil show <stage> --json` (add `--items <ids>` for just those items, or `--section "<heading>"` for one section), never by opening the whole document: `show` gives the content as a person reads it, with `[ai-draft]` after each block that still needs review and one readable line in place of each record. Open a stage document only to edit the part you are changing. **Never read `eil-record.json`**: it is the helper's record file, and `eil status` and `eil show` report what is in it.

## Presenting a review list

Present every review list exactly as the helper returns it, in the helper's `mode`:

- `one-at-a-time`: show one entry at a time, with its full text (`what`) and why it needs review, ask for that entry's answer, and store it at once with `eil review answer --stage <stage> --kind <kind> --digest <digest> --entry <key> --by "<name>" --reply "<their words, verbatim>" [--disposition except|question] --json`. Offer "ok to the rest" as you go: if the person says it, record it with `--rest` in place of `--entry`; the helper marks those entries as accepted without being shown in full.
- `summary`: show the `groups`, with each entry's `summary` and why it needs review, and ask for one reply to the whole list (`--all`, `--all-except <keys>` or `--question <keys>`). Show the full text of an entry, a group or the whole list whenever asked: `eil review show --stage <stage> --kind <kind> --entry <key>` (or `--group "<section>"`, or `--all`).

The helper stores each answer as it is given. **Never keep a tally of answers in chat**: after a pause or a compaction, run `review list` again; it returns only what is still unanswered. **Never list a block the helper did not return**, and never ask again about one it settled. A `§<Section>` entry stands for every block of that section, answered together.

## What this command is for

An approval is one recorded, explicit human confirmation. It is the point where judgement is required: that this is the problem we intend to solve (Requirements), the behaviour we require (Functional), the engineering solution we intend to build (Technical), or that the evidence has been reviewed (Completion). The helper's question states which. Whether the confirmer is who they say they are, and whether they truly reviewed it, is beyond what the helper can verify; it records the person's name, the time, the document's fingerprint and their own words so that a false approval is visible in review.

Every call below is `python3 .specify/extensions/eil/scripts/python/eil <subcommand> --json`. **Stop on any non-zero exit** and show the helper's `refusals` (code, message, fix).

## Asking for the approval

Ask the helper's question and nothing more: `eil status --json` gives it as `next_action.question` (for example "Approve the Functional Specification as the behaviour you require?"); the helper records it beside the reply, so the record shows exactly what was confirmed. A reply of "ok", "yes" or "approved", or any other reply the person gives, is a complete answer: pass it verbatim. Do not ask for a longer statement, and do not offer example sentences as the wording to use. Ask the person's name once per session and reuse it for every `--by`, unless they name someone else. Silence, "just approve it", or a reply you would have to write for them is not an answer: ask the question again.

## Steps

1. **Synchronise**: run `eil sync --json`.
2. **Choose the stage** from the user's input, or the story's current stage (`eil check --json` reports the stage it evaluated). Only `requirements`, `functional`, `technical` and `completion` can be approved.
3. **Show the gate**: run `eil check --stage <stage> --json` and show the focused gate: the unmet criteria first, then the judgment ones, then a count of the met structural criteria (`summary.met_structural`; `eil check --full` lists them all), each unmet one with its reason, any findings, and any open question or `[ai-draft]` tag. If the gate is not met, say so and stop: do not proceed to ask for a confirmation that will be refused. If the human wants to waive one criterion, that is `/speckit-eil-override`.
4. **List the inferred blocks first.** Run `eil review list --stage <stage> --kind inferred --json`. If it lists anything, the human answers that one list in their own words (`eil review answer ... --reply "<their words>"`, verbatim) before you ask for the attestation; never answer for them. Approval is refused while a block is unreviewed.
5. **Show what changed** since the last approval, so the human confirms what they are actually looking at: use `git diff` on the stage document against the last commit that carried an approval, or say that there is no earlier approval. If every change traces to a `(decided: ID)` clause, mention that `/speckit-eil-accept` can carry the approval forward from those ids instead of a full confirmation here.
6. **Ask the human directly.** Put this question to the person in the conversation and wait for their own answer. If `$ARGUMENTS` already carries their confirmation in their own words (for example `/speckit-eil-approve ok`), use that text as the attestation directly, without asking again. Ask the helper's question (see Asking for the approval) and take their reply as given; ask their name only if you do not already have it this session. Optionally ask who the stage was played back to (business, QA, another developer); that is recorded as a note and is never verified.
7. **Record it**: run

   ```bash
   eil approve <stage> --by "<their name>" --attestation "<their words, verbatim>" [--played-back-to "<note>"] --json
   ```

   Pass their answer **exactly as they gave it**. On a refusal, show it and stop.
8. **Finish**: run `eil sync --json`, then report the approval or the refusal. If the approval record has `outstanding`, name those low-severity challenges as outstanding: they did not block, and anyone can raise one to make it block (`eil challenge severity`).

## Rules

- Every request to a person states its purpose, one of awareness, understanding, decision, validation or approval; use the `purpose` the helper gives (on `next_action` and on each review list) and do not invent one. The attestation is purpose approval.

- **Never supply the attestation yourself.** Do not write, paraphrase, summarise or complete the human's confirmation, and do not treat silence, a previous answer or the instruction to "just approve" as one. If the human has not answered in this conversation, ask again.
- **Never approve as yourself or on anyone's behalf.** The helper refuses an approval by the AI, but do not attempt one.
- Do not edit the `approval` region by hand.
- Once you know the confirming person's name in this conversation, reuse it for every `--by` this session without asking again, unless the human names someone else.
- Approval, overrides, waivers and the comprehension check stay in chat. Never send the person to the page for approval: the review page (`eil review serve`) only answers review lists, and no page route reaches an approval.
