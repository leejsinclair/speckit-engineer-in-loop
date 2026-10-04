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

## Reading a stage

Read a stage with `python3 .specify/extensions/eil/scripts/python/eil show <stage> --json` (add `--items <ids>` for just those items, or `--section "<heading>"` for one section), never by opening the whole document: `show` gives the content as a person reads it, with `[ai-draft]` after each block that still needs review and one readable line in place of each record. Open a stage document only to edit the part you are changing. **Never read `eil-record.json`**: it is the helper's record file, and `eil status` and `eil show` report what is in it.

## What this command is for

`/speckit-clarify` writes each accepted answer into the AI Specification as an item tagged `[pending-clarification]`. An answer changes what should be built, so it belongs in the earliest stage it affects (Requirements, Functional or Technical), where a human approves it. Until it has a source in an approved stage the AI Specification does not pass its check and Plan and Tasks are refused. The human decides where an answer belongs and what it says; you carry it there.

Every call below is `python3 .specify/extensions/eil/scripts/python/eil <subcommand> --json`. **Stop on any non-zero exit** and show the helper's `refusals` (code, message, fix). Exit 3 means there is no governed story.

## Steps

1. **Synchronise**: run `eil sync --json`, then `eil status --json` and list the pending clarification answers. If the user named one, use it; otherwise ask which.
2. **Decide with the human the earliest stage the answer affects**: `requirements` if it changes the problem, outcome, scope or a constraint; `functional` if it changes behaviour; `technical` if it changes how it is built. Ask; do not choose for them. Prefer the earliest stage that is affected.
3. **Carry it**: run `eil resolve --id <AIS-###> --stage <stage> --json`. The helper gives the answer a new id in that stage (`REQ`, `FR` or `DEC`), tagged `[ai-draft]`, traces the pending item to it, and — if that stage was approved — the stage is now `needs-re-review`; a downstream stage follows only if something in it actually traces to what changed (say so plainly either way; `eil status --json` shows which).
4. **Write the decision into that stage as a proper item.** Show the human the exact text the clarify answer recorded (the AIS-### item's own words) next to what you are about to write, so they can confirm it is unchanged. When it is a **verbatim carry** of that recorded answer, write it **untagged**, with `(decided: AIS-###)` in place of `[ai-draft]` (with its `traces:` clause and, for a `DEC`, every field and the developer as owner). If the human changes the wording rather than confirming it as given, that changed text is `[ai-draft]` like any other draft, until they review it themselves. Then run `eil check --stage <stage> --json` and fix what it finds. Never approve it yourself.
5. **Tell the human what is left.** If the carried text is untagged (`decided: AIS-###`) and nothing else in the stage was touched, ###` in place of a full re-approval; otherwise the stage needs a fresh `/speckit-eil-approve`. Say plainly which downstream stages, if any, need re-review too.
6. **After the stage is approved or amended again**, run `eil resolve --id <AIS-###> --stage <stage> --json` once more. It clears the pending mark only when the answer has a source in an approved stage, and says what remains if not.
7. **Finish**: run `eil sync --json` and report which answers are still pending.

## Rules

- Never remove a `[pending-clarification]` tag by hand, and never write a decision into an earlier stage that the human did not make.
- If the answer belongs nowhere (the human decides it was wrong), leave it pending and say so; do not delete it silently.
- Once you know the confirming person's name in this conversation, reuse it for every `--by` this session without asking again, unless the human names someone else.
