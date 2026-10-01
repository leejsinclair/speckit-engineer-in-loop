---
description: Re-sign a stage's approval when every change since it is covered by a cited human decision, in place of a full re-approval.
argument-hint: "The stage, and the human decisions that cover its changes, for example: functional CH-004,OQ-002"
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## Guard (engineer-in-the-loop)

If `.specify/extensions/eil/scripts/python/eil` does not exist, STOP. Tell the user to run `specify extension add eil` and then `specify preset add engineer-in-the-loop`, and do nothing else: continuing without the helper would let a story bypass its gates.

## Superseded by `/speckit-eil-accept`

This command is superseded. `amend` is now a short alias: `/speckit-eil-accept` lists the changes, shows which are covered and takes one sign-off, so prefer it. This command still works as described below.

## What this command is for

A stage can become `needs-re-review` for a reason that is nothing but the developer's own prior decision, already recorded — an accepted challenge, a resolved open question, a clarify answer carried upstream, **or an `eil review` acceptance** (`RVW-###`, from `/speckit-eil-review-changes`). Re-running the whole approval ceremony for that is unneeded work: `eil amend` re-signs the existing approval instead, but only when it can verify every change traces to a decision the developer names. It is not a lighter approval and not a rubber stamp: the helper still refuses it if anything unaccounted for changed, if `[ai-draft]` remains, or if a cited decision does not check out. It never supplies the attestation, the reason, or the list of decisions — the human gives all three.

If the changes are new — reworded just now, not quoted from an earlier decision — there is nothing yet to cite. Use `/speckit-eil-review-changes` first: it walks the human through each change and records their "ok" as the citation, then re-signs in one pass. Use `amend` directly only when the covering decisions already exist.

Every call below is `python3 .specify/extensions/eil/scripts/python/eil <subcommand> --json`. **Stop on any non-zero exit** and show the helper's `refusals` (code, message, fix).

## Steps

1. **Synchronise**: run `eil sync --json`, then `eil status --json` to confirm the stage is `needs-re-review` and was previously approved. If it was never approved, this is not the command: offer `/speckit-eil-approve`.
2. **Show what changed**: `git diff` the stage document against the last commit that carried its approval. Point out every item that changed, and which of them already carries a `(decided: ID)` clause.
3. **Ask the human directly** which recorded decisions cover every change (the `CH`, `OQ` or `AIS` ids), the name they are confirming as, and their confirmation in their own words — their answer to the decision itself may serve as this attestation if they already gave one. Do not choose the ids or write the attestation for them.
4. **Record it**: run

   ```bash
   eil amend <stage> --from <CH-004,OQ-002,...> --by "<their name>" --attestation "<their words, verbatim>" --json
   ```

   On a refusal, show it and say what it means:
   - `amend-not-covered`: an item changed with no matching `(decided: ...)` among the ids given, or a section outside any item changed with no matching `eil review` acceptance. Offer `/speckit-eil-review-changes` for what is left, or the full `/speckit-eil-approve`.
   - `unreviewed-ai-content`: an `[ai-draft]` tag remains; review and remove it first.
   - `unknown-item`: a cited id does not exist, or is not in an eligible state (a challenge not accepted, a question not resolved).
   - `not-amendable`: the stage is not approvable, or was never approved before.
5. **Say where it is visible**: the new approval is marked `amended`, naming the decisions it rests on, in the stage document, the overview and every later report — exactly as visibly as an override.
6. **Finish**: run `eil sync --json`.

## Rules

- **Never supply the attestation yourself**, and never choose the decisions the amendment cites without the human naming them.
- Never amend as yourself or on anyone's behalf; the helper refuses an approval by the AI, but do not attempt one.
- Do not edit the `approval` region by hand.
- Once you know the confirming person's name in this conversation, reuse it for every `--by` this session without asking again, unless the human names someone else.
