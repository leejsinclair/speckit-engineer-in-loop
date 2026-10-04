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

## Proposing the small-story profile

You may propose the **small-story profile** when the story looks small: for example the request already states the behaviour and how it will be accepted in detail, there are few requirements, or the change is confined to one component. Name the signals you saw and label the proposal as your own: start it with `AI assessment:`. Say what it changes (no wireframe exports, one review of the AI Specification, plan and tasks before implementation, two comprehension levels) and that every approval is still required.

Only a person authorises it. **Ask who authorises it and why**, and wait for their answer. If they agree, record their words: `eil profile set small --by "<their name>" --reason "<their words>" --json`. **Never run `profile set` without the person's own words**, and never decide the story is small yourself. If they decline or say nothing, the story follows the full workflow and nothing is recorded.

If later work shows the story is larger than proposed (more than one container touched, new data stored, or more requirements than you expected), say that it **outgrows the profile** and offer to withdraw it: `eil profile withdraw --by "<their name>" --reason "<their words>" --json`. Withdrawal restores the full workflow for every stage not yet approved.

## What this command is for

A very small change may not warrant every stage in full. A stage may be abbreviated (a short document that still has its headings and its gate) but **never skipped**: the stage document must exist, the abbreviation, who authorised it and why is recorded in that document, and the stage is shown as abbreviated in the overview, in `eil status` and in the trace report. It still passes its gate and is still approved. Whether the story really is small is the authoriser's judgement, not yours.

Every call below is `python3 .specify/extensions/eil/scripts/python/eil <subcommand> --json`. **Stop on any non-zero exit** and show the helper's `refusals` (code, message, fix). Exit 3 means there is no governed story.

## Steps

1. **Synchronise**: run `eil sync --json`.
2. **Choose the stage** from the user's input. It must already have a document: if it does not, the helper refuses with `cannot-skip`, and the answer is to start the stage (`eil stage-init` or its command) and keep it short, not to leave it out.
3. **Ask the human directly**, in the conversation: who authorises the abbreviation (by default the story's developer; a team may name others in the configuration), and why this story does not need the stage in full. Wait for their answer. Do not decide that a story is small yourself, and do not write the reason for them. You may propose an abbreviation, or the small-story profile, naming the signals you saw and labelling it `AI assessment:`; only a person authorises either.
4. **Record it**: run `eil abbreviate <stage> --by "<their name>" --reason "<their words>" --json`. On a refusal (`not-an-authoriser`, `reason-required`, `cannot-skip`), show it and stop.
5. **Say what changed**: the abbreviation is part of the stage document, so an approved stage now needs approving again, and the stage still has to pass its gate. Finish with `eil sync --json`.

## Rules

- Never authorise an abbreviation yourself, and never abbreviate to get past a gate: the gate is unchanged.
- Do not edit the abbreviation record by hand.
- Once you know the confirming person's name in this conversation, reuse it for every `--by` this session without asking again, unless the human names someone else.
