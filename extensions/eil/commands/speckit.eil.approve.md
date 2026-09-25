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

## What this command is for

An approval is one recorded, explicit human confirmation. It is the point where judgement is required: *"Yes, this is the problem we actually intend to solve"* (Requirements), *"Yes, this describes the behaviour we actually require"* (Functional), *"Yes, this is the engineering solution we intend to build"* (Technical), or that the evidence has been reviewed (Completion). Whether the confirmer is who they say they are, and whether they truly reviewed it, is beyond what the helper can verify; it records the person's name, the time, the document's fingerprint and their own words so that a false approval is visible in review.

Every call below is `python3 .specify/extensions/eil/scripts/python/eil <subcommand> --json`. **Stop on any non-zero exit** and show the helper's `refusals` (code, message, fix).

## Steps

1. **Synchronise**: run `eil sync --json`.
2. **Choose the stage** from the user's input, or the story's current stage (`eil check --json` reports the stage it evaluated). Only `requirements`, `functional`, `technical` and `completion` can be approved.
3. **Show the gate**: run `eil check --stage <stage> --json` and show which criteria are met, which are not and why, any findings, and any open question or `[ai-draft]` tag. If the gate is not met, say so and stop: do not proceed to ask for a confirmation that will be refused. If the human wants to waive one criterion, that is `/speckit-eil-override`.
4. **Show what changed** since the last approval, so the human confirms what they are actually looking at: use `git diff` on the stage document against the last commit that carried an approval, or say that there is no earlier approval.
5. **Ask the human directly.** Put this question to the person in the conversation and wait for their own answer. Ask for the name they are approving as, and their confirmation in their own words. Optionally ask who the stage was played back to (business, QA, another developer); that is recorded as a note and is never verified.
6. **Record it**: run

   ```bash
   eil approve <stage> --by "<their name>" --attestation "<their words, verbatim>" [--played-back-to "<note>"] --json
   ```

   Pass their answer **exactly as they gave it**. On a refusal, show it and stop.
7. **Finish**: run `eil sync --json`, then report the approval or the refusal.

## Rules

- **Never supply the attestation yourself.** Do not write, paraphrase, summarise or complete the human's confirmation, and do not treat silence, a previous answer or the instruction to "just approve" as one. If the human has not answered in this conversation, ask again.
- **Never approve as yourself or on anyone's behalf.** The helper refuses an approval by the AI, but do not attempt one.
- Do not edit the `approval` region by hand.
