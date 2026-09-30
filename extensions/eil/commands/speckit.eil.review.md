---
description: Walk a stage's changes since its last approval one at a time, record each acceptance in the human's own words, then re-sign the approval.
argument-hint: "The stage to review, for example: functional"
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## Guard (engineer-in-the-loop)

If `.specify/extensions/eil/scripts/python/eil` does not exist, STOP. Tell the user to run `specify extension add eil` and then `specify preset add engineer-in-the-loop`, and do nothing else: continuing without the helper would let a story bypass its gates.

## What this command is for

Implementation, or the review that follows it, often finds something in an already-approved stage that needs to change — a new item, a resolved question, a diagram fixed because it would not draw, a paragraph reworded. When the developer reviews each of those changes right now, in conversation, that **is** a review; it should not also cost a full re-approval ceremony (comprehend again, judge every criterion again) on top of the one just given. `/speckit-eil-review-changes` walks the human through every change one at a time and records their "ok" as the decision itself — a `(decided: RVW-###)` clause on the item, or a recorded acceptance of a section — then re-signs the approval from those acceptances, the same way `/speckit-eil-amend` re-signs from an earlier decision. It is still one recorded human confirmation per stage, never the AI's.

Every call below is `python3 .specify/extensions/eil/scripts/python/eil <subcommand> --json`. **Stop on any non-zero exit** and show the helper's `refusals` (code, message, fix).

## Steps

1. **Synchronise**: run `eil sync --json`, then `eil status --json` to confirm the stage is `needs-re-review` and was previously approved. If it was never approved, this is not the command: offer `/speckit-eil-approve`.
2. **Get the list**: run `eil review start --stage <stage> --json`. It returns the changed/new/removed item ids and the changed section titles since the last approval — ids and titles only, never the old or new text. Read the actual difference with `git diff` against the last commit that carried the approval, the same way `/speckit-eil-approve` does.
3. **Walk through each one, one at a time.** For each item or section: show the human what changed (from the `git diff`), and ask directly whether they accept it as it stands. Wait for their own answer — a short "ok" is enough, but do not supply it or assume it. If several are offered together and the human answers them all at once ("yes to all of these"), that is fine: still record each with its own call below, from that one reply.
4. **Record each acceptance**: run

   ```bash
   eil review accept --stage <stage> [--items ID[,ID…]] [--sections "Name"[,"Name"…]] --by "<their name>" [--note "<their words, if they gave any>"] --json
   ```

   For an item, the helper writes `(decided: RVW-###)` onto its line itself, removing any `[ai-draft]` tag — **you never edit the tag by hand** for an item accepted this way. A section has no line to tag; only the record is written. `--note` is optional and is their words, never yours.
5. **If the human wants to change the wording instead of accepting it as given**, that is an ordinary edit: make it, tag it `[ai-draft]` as usual, and it is not accepted by this flow — it needs its own review (or a human decision) afterwards, like any other draft.
6. **When every listed item and section has been accepted** (or genuinely does not need to be — say so if one turns out to be a false alarm and leave it for a full `/speckit-eil-approve` instead), **finish**: run

   ```bash
   eil review finish --stage <stage> --by "<their name>" --attestation "<their words, verbatim>" --json
   ```

   Ask for their confirming words the same way `/speckit-eil-approve` does — their answer to one of the changes may already serve as this, if they gave one, without asking again. This also takes care of the comprehension check for this version: if every change really is covered, nothing is asked; if the helper reports `comprehension-prerequisites`, run `/speckit-eil-comprehend` first (it will find little or nothing left to ask, for the same reason).
   On `amend-not-covered`, something is still outstanding: go back to step 2 or 3, or fall back to the full `/speckit-eil-approve`.
7. **Say where it is visible**: the new approval is marked `reviewed_change_by_change`, listing every `RVW` id it rests on, in the stage document, the overview and every later report.
8. **Finish**: run `eil sync --json`.

## Rules

- **Never accept a change on the human's behalf.** Do not choose "ok" for them, write their note, or treat silence as acceptance.
- **Never supply the attestation for `eil review finish`** — the same rule as `/speckit-eil-approve` and `/speckit-eil-amend`.
- Do not edit an `eil:review` record, or a `(decided: ...)` clause, by hand.
- Once you know the confirming person's name in this conversation, reuse it for every `--by` this session without asking again, unless the human names someone else.
