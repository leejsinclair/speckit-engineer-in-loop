---
description: Do the next step the story is waiting for, and stop at every point where a person must decide.
argument-hint: "Nothing, or 'show' to see the next step without running it"
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

Save the developer from remembering command names. It reads the story's state and does the one next step **only if that step is drafting or checking that the AI may do alone**. At any point that needs a person it stops and says exactly what is needed. AI challenges. Humans decide. AI executes.

Every call below is `python3 .specify/extensions/eil/scripts/python/eil <subcommand> --json`. Exit 3 means the feature is not governed: say so in one sentence (`/speckit-eil-1-requirements` starts a story) and stop.

## Steps

1. **Synchronise and read**: run `eil sync --json`, then `eil status --json`, and take `next_action` from it. Its `kind`, `stage`, `command`, `message` and `purpose` come from the helper; **do not choose a different step, and do not work out the step yourself.**
2. **Act on `kind`, and only on `kind`**:
   - `done`: say every stage is complete and stop.
   - `human`: **stop.** Give the `message`, say its `purpose` (awareness, understanding, decision, validation or approval), name the `command` the person should run, and if it is a challenge, show it. Run nothing.
   - `draft` or `check`: say in one line which command you are about to run and why, then run that `command` with no extra input, following it completely.
3. If the user's input says "show", "what", "dry run" or similar, report the `message` and `command` and run nothing.
4. **After one step, stop.** Run `eil status --json` again and report the new `next`. Never start a second step in the same call: the person decides whether to go on.

## Rules

- Every request to a person states its purpose, one of awareness, understanding, decision, validation or approval; use the `purpose` the helper gives (on `next_action` and on each review list) and do not invent one.

- Never approve a stage, record an override, accept a risk, abbreviate a stage, answer a challenge, take a comprehension check or mark anything verified, however the step is worded. Those stay with a person, through their own commands.
- Never edit an approved stage. If `next_action` points at one, that is a `human` step.
- Never run a command the helper did not name.
- Report the helper's refusals as they are (code, message, fix); do not work around one.
