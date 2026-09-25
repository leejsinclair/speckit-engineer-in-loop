---
description: Record a named, reasoned override of one unmet gate criterion.
argument-hint: "The stage and the criterion to override, for example: requirements REQ-G06"
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## Guard (engineer-in-the-loop)

If `.specify/extensions/eil/scripts/python/eil` does not exist, STOP. Tell the user to run `specify extension add eil` and then `specify preset add engineer-in-the-loop`, and do nothing else: continuing without the helper would let a story bypass its gates.

## What this command is for

A gate is a hard stop. The only way past an unmet criterion is a recorded override: one criterion, by a person configured to confirm that stage, with a reason. It is never blanket, and it stays visible in the stage document, the overview and every later report (FR-045). This is a human decision; you carry it out, you do not make it.

Every call below is `python3 .specify/extensions/eil/scripts/python/eil <subcommand> --json`. **Stop on any non-zero exit** and show the helper's `refusals` (code, message, fix).

## Steps

1. **Synchronise**: run `eil sync --json`.
2. **Show the unmet criteria**: run `eil check --stage <stage> --json` and list them with their reasons, so the human chooses from what is actually unmet. The check for `[ai-draft]` tags can be waived with the criterion id `unreviewed-ai-content`.
3. **Ask the human directly** which single criterion they want to override, the name they are acting as, and **why**. Ask for one criterion at a time. Do not propose a reason for them.
4. **Record it**: run

   ```bash
   eil override <stage> --criterion <ID> --by "<their name>" --reason "<their reason, verbatim>" --json
   ```

   On a refusal (for example `not-a-confirmer` or `reason-required`), show it and stop.
5. **Say where it is visible**: the override is recorded under `## Overrides` in the stage document (so it appears in the diff and in review) and is listed in the overview. Because it changes the document, the AI's verdicts need to be supplied again with `eil check --judgments` before approval.
6. **Finish**: run `eil sync --json`.

## Rules

- Never choose the criterion, write the reason, or override on a person's behalf without their explicit instruction in this conversation.
- Do not override a criterion to get past a problem you could fix in the document; offer the fix first.
