---
description: Trace the chain from a requirement to its evidence, or from a change back to its requirement, and list the gaps.
argument-hint: "A requirement id, an item id, a commit, or a pull request (PR#n); or leave empty for the whole story"
user-invocable: true
disable-model-invocation: false
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

The story is a chain: requirement, functional requirement, technical decision, AI Specification item, task, code change and verification evidence, with artefacts as a side branch. This command reads it in either direction so anyone can answer *why was this built?* and *how was it verified?* It reads and reports; it writes nothing and decides nothing.

Every call below is `python3 .specify/extensions/eil/scripts/python/eil <subcommand> --json`. **Stop on any non-zero exit** and show the helper's `refusals` (code, message, fix). Exit 3 means there is no governed story.

## Steps

1. **Synchronise**: run `eil sync --json`.
2. **Choose the question** from the user's input:
   - a requirement or other item id and "forward", or just a requirement id: `eil trace --from <id> --json`;
   - a task, decision, or a **commit** or **pull request** ("why was this change made?"): `eil trace --to <id, sha or PR#n> --json`;
   - nothing, or "report": `eil trace --report --json`, one row per requirement showing where its chain ends.
3. **Report the chain** as the helper gives it: each item's id, stage and title, in order. Then list, verbatim, every **gap** it names (for example a requirement with no functional requirement, no code change linked, or no verification evidence), and every **override**, **abbreviated stage** and **accepted risk**, which the helper includes because they qualify anything that looks complete.
4. **Say what would close each gap**, and which command does it. Do not close a gap yourself, and do not describe a chain as complete when the helper lists a gap.
5. For a change the helper cannot find on any task, say so: the task line needs a `(code: <sha or PR#n>)` clause.
