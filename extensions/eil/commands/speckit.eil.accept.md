---
description: Accept the changes made to a previously approved stage, with one short confirmation when every change is already a recorded decision.
argument-hint: "The stage whose approval is out of date, for example: functional"
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## Guard (engineer-in-the-loop)

If `.specify/extensions/eil/scripts/python/eil` does not exist, STOP. Tell the user to run `specify extension add eil` and then `specify preset add engineer-in-the-loop`, and do nothing else: continuing without the helper would let a story bypass its gates.

## What this command is for

A stage that was approved and has since changed is `needs-re-review`. This command brings it back without repeating the whole approval. The helper works out what changed and which changes are **covered** by a decision the person already recorded (an accepted challenge, a resolved question, a clarify answer or an earlier review). It carries the approval forward on a short sign-off only when every change is covered; otherwise the person answers the uncovered changes once, in one reply. It is not a lighter approval: the helper records who confirmed, in their own words, and how the approval was reached.

Every call below is `python3 .specify/extensions/eil/scripts/python/eil <subcommand> --json`. **Stop on any non-zero exit** and show the helper's `refusals` (code, message, fix).

## Steps

1. **Synchronise**: run `eil sync --json`, then `eil status --json` to confirm the stage is `needs-re-review` and was approved before. If it was never approved, this is not the command: offer `/speckit-eil-approve`.
2. **List the changes**: run `eil review list --stage <stage> --kind changes --json`. Show every entry with the helper's own words. For an entry with `covered_by`, say which decision covers it. Any one-line summary you add is a draft by the AI and must be labelled as such.
3. **If nothing is uncovered** (every entry has `covered_by`): ask the person for their sign-off in their own words ("ok" is enough), then go to step 5.
4. **Otherwise ask once**: show the uncovered entries and ask for one reply. Record it with `eil review answer --stage <stage> --kind changes --digest <digest from step 2> --by "<their name>" --reply "<their words, verbatim>"` plus exactly one of `--all`, `--all-except IDS`, `--question IDS`, `--reopen IDS`, matching what they said. On `list-changed`, show the new list and ask again. On `reply-mismatch`, re-read the reply and pass the flags it actually means; never change the reply. On `acceptance-conflict`, show both answers and ask a configured confirmer to answer again. If the stage takes a comprehension check, run `/speckit-eil-comprehend` for the delta when the helper asks for it.
5. **Confirm**: draft a one-line summary for every change, covered or not (a draft by the AI, labelled as such; it becomes the Change Log text), write them to a file as `{"stage": "<stage>", "summaries": [{"key": "<ID>", "summary": "<text>"}]}`, and run

   ```bash
   eil review confirm --stage <stage> --by "<their name>" --confirmation "<their words, verbatim>" --summaries FILE --json
   ```

   Pass the same file with `--summaries` to `eil review answer` in step 4 for the uncovered changes. `summary-missing` means a change has no summary: add it and run again.

   On a refusal, show it and say what it means: `changes-unanswered` (an uncovered change has no answer yet: go back to step 4), `comprehension-prerequisites` (the delta check must be taken first), `confirmation-required`, `not-a-confirmer`, `ai-approval`, `acceptance-conflict`, `not-amendable`.
6. **Say how it was reached**: the approval is marked `carried-forward` or `reviewed`, naming the decisions it rests on, in the stage document, the overview and every later report.
7. **Unsettled challenges**: if `eil review list --stage <stage> --kind unsettled-challenges --json` is not empty, show it and ask once. A challenge that was rejected or deferred and whose target has since changed is either reconfirmed by a configured confirmer or reopened by anyone (`--reopen`).
8. **Finish**: run `eil sync --json`.

## Rules

- **Never supply the sign-off or the confirmation yourself**, and never answer the list on the person's behalf. Only their own words are recorded.
- Never pass a reply you wrote as the person's. Do not choose which changes to accept.
- Do not edit the `approval` region by hand.
- If you edit an item that carries an earlier `(decided: CR-###)` clause, remove or replace the clause; never leave one that no longer matches the text.
- Once you know the confirming person's name in this conversation, reuse it for every `--by` this session without asking again, unless the human names someone else.
