---
description: Report a problem found in an earlier artefact from any later stage, show the fix and its impact, and apply it only after the person agrees.
argument-hint: "The problem and the item, for example: REQ-003 says 24 hours, the customer needs 48"
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## Guard (engineer-in-the-loop)

If `.specify/extensions/eil/scripts/python/eil` does not exist, STOP. Tell the user to run `specify extension add eil` and then `specify preset add engineer-in-the-loop`, and do nothing else: continuing without the helper would let a story bypass its gates.

## What this command is for

A problem found in planning, tasks, implementation, verification or code review often belongs to an earlier artefact. This command fixes it at its owner, in place, with one report, one agreement and one sign-off. The helper opens a correction (`CR-###`), works out the owner and the impact, and blocks work on what depends on the item until the correction is confirmed.

Every call below is `python3 .specify/extensions/eil/scripts/python/eil <subcommand> --json`. **Stop on any non-zero exit** and show the helper's `refusals` (code, message, fix).

## Steps

1. **Synchronise**: run `eil sync --json`.
2. **Take the report**: the problem, the item id and where it was found (`--found-in <stage>[:item]`, or `implementation` or `code-review`). Take the person's corrected wording if they give it; do not ask for it if they have not.
3. **Propose**: run `eil correct propose --item <ID> --found-in <where> --problem "<text>" --json`. It writes nothing. **Show before applying**: the owning stage, the edit you intend, and the impact list (what the change reaches). Ask which stage owns the item **only** if `ambiguous` is true.
4. **Get agreement**: wait for the person to agree to the owner, the edit and the impact. Do not open or edit anything before that.
5. **Open**: run `eil correct open --item <ID> --found-in <where> --problem "<text>" --by "<their name>" [--owner <stage>] [--wording "<their words, verbatim>"] --json`. Pass `--wording` only with the person's own words, verbatim. Never pass text you wrote as `--wording`.
6. **Apply in place** in the owning stage document:
   - **The person's wording**: replace the item's text with exactly that wording and add `(decided: CR-###)`.
   - **Your own draft**: apply it with no `(decided: …)` clause. It is an uncovered change the person answers on the `changes` list.
   - If the item already carries an earlier `(decided: CR-###)` clause and you edit it again, remove that clause, or replace it only when the new text is exactly the recorded wording of the clause you keep. Never leave a clause that no longer matches the text.
7. **Re-derive only what is listed**: run `eil status --json` and re-derive only the stages and sections in `rederive[]`, in place, leaving all other text byte-identical. Never derive from an id in `blocked_work`.
8. **Continue as accept**: hand over to `/speckit-eil-accept` for the owning stage. For each change, give a one-line summary, labelled as a draft by the AI, and pass the summaries with `--summaries` to `eil review answer` or `eil review confirm`. For a stage nobody approves (AI Specification, plan, tasks, verification), `review confirm` closes the correction and writes no approval.
9. **Finish**: run `eil sync --json`.

## Rules

- **Never supply the person's wording, sign-off or confirmation.** The correction is opened in the name of the person who reported it.
- Do not edit the `provenance` or `changelog` regions by hand.
- Once you know the person's name in this conversation, reuse it for every `--by` this session without asking again, unless the human names someone else.
