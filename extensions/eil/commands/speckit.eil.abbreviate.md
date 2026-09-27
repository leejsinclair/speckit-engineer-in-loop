---
description: Record that a stage is abbreviated for a small story, who authorised it and why. A stage is shortened, never skipped.
argument-hint: "The stage to abbreviate"
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## Guard (engineer-in-the-loop)

If `.specify/extensions/eil/scripts/python/eil` does not exist, STOP. Tell the user to run `specify extension add eil` and then `specify preset add engineer-in-the-loop`, and do nothing else: continuing without the helper would let a story bypass its gates.

## What this command is for

A very small change may not warrant every stage in full. A stage may be abbreviated (a short document that still has its headings and its gate) but **never skipped**: the stage document must exist, the abbreviation, who authorised it and why is recorded in that document, and the stage is shown as abbreviated in the overview, in `eil status` and in the trace report. It still passes its gate and is still approved. Whether the story really is small is the authoriser's judgement, not yours.

Every call below is `python3 .specify/extensions/eil/scripts/python/eil <subcommand> --json`. **Stop on any non-zero exit** and show the helper's `refusals` (code, message, fix). Exit 3 means there is no governed story.

## Steps

1. **Synchronise**: run `eil sync --json`.
2. **Choose the stage** from the user's input. It must already have a document: if it does not, the helper refuses with `cannot-skip`, and the answer is to start the stage (`eil stage-init` or its command) and keep it short, not to leave it out.
3. **Ask the human directly**, in the conversation: who authorises the abbreviation (by default the story's developer; a team may name others in the configuration), and why this story does not need the stage in full. Wait for their answer. Do not decide that a story is small yourself, and do not write the reason for them.
4. **Record it**: run `eil abbreviate <stage> --by "<their name>" --reason "<their words>" --json`. On a refusal (`not-an-authoriser`, `reason-required`, `cannot-skip`), show it and stop.
5. **Say what changed**: the abbreviation is part of the stage document, so an approved stage now needs approving again, and the stage still has to pass its gate. Finish with `eil sync --json`.

## Rules

- Never authorise an abbreviation yourself, and never abbreviate to get past a gate: the gate is unchanged.
- Do not edit the abbreviation record by hand.
- Once you know the confirming person's name in this conversation, reuse it for every `--by` this session without asking again, unless the human names someone else.
