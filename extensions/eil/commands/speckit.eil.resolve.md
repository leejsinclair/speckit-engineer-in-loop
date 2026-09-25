---
description: Carry a pending clarification answer to the earliest stage it affects, then clear its pending mark once that stage is approved again.
argument-hint: "The pending item, for example AIS-007"
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## Guard (engineer-in-the-loop)

If `.specify/extensions/eil/scripts/python/eil` does not exist, STOP. Tell the user to run `specify extension add eil` and then `specify preset add engineer-in-the-loop`, and do nothing else: continuing without the helper would let a story bypass its gates.

## What this command is for

`/speckit-clarify` writes each accepted answer into the AI Specification as an item tagged `[pending-clarification]`. An answer changes what should be built, so it belongs in the earliest stage it affects (Requirements, Functional or Technical), where a human approves it. Until it has a source in an approved stage the AI Specification does not pass its check and Plan and Tasks are refused. The human decides where an answer belongs and what it says; you carry it there.

Every call below is `python3 .specify/extensions/eil/scripts/python/eil <subcommand> --json`. **Stop on any non-zero exit** and show the helper's `refusals` (code, message, fix). Exit 3 means there is no governed story.

## Steps

1. **Synchronise**: run `eil sync --json`, then `eil status --json` and list the pending clarification answers. If the user named one, use it; otherwise ask which.
2. **Decide with the human the earliest stage the answer affects**: `requirements` if it changes the problem, outcome, scope or a constraint; `functional` if it changes behaviour; `technical` if it changes how it is built. Ask; do not choose for them. Prefer the earliest stage that is affected.
3. **Carry it**: run `eil resolve --id <AIS-###> --stage <stage> --json`. The helper gives the answer a new id in that stage (`REQ`, `FR` or `DEC`), tagged `[ai-draft]`, traces the pending item to it, and — if that stage was approved — the stage is now `needs-re-review`, and so is every stage after it that depended on it. Say so plainly.
4. **Write the decision into that stage as a proper item**, in the human's words: replace the carried placeholder with the requirement, functional requirement or decision (with its `traces:` clause and, for a `DEC`, every field and the developer as owner). Then run `eil check --stage <stage> --json` and fix what it finds. Never approve it yourself.
5. **Tell the human what is left**: the stage needs its `[ai-draft]` tag reviewed and a fresh approval (`/speckit-eil-approve`), and the stages after it need re-review too.
6. **After the stage is approved again**, run `eil resolve --id <AIS-###> --stage <stage> --json` once more. It clears the pending mark only when the answer has a source in an approved stage, and says what remains if not.
7. **Finish**: run `eil sync --json` and report which answers are still pending.

## Rules

- Never remove a `[pending-clarification]` tag by hand, and never write a decision into an earlier stage that the human did not make.
- If the answer belongs nowhere (the human decides it was wrong), leave it pending and say so; do not delete it silently.
