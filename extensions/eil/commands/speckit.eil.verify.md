---
description: Record verification evidence for every requirement, functional requirement and approved artefact (did we achieve it?).
argument-hint: "Anything the developer wants emphasised, such as where test results are kept"
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

## Presenting a review list

Present every review list exactly as the helper returns it, in the helper's `mode`:

- `one-at-a-time`: show one entry at a time, with its full text (`what`) and why it needs review, ask for that entry's answer, and store it at once with `eil review answer --stage <stage> --kind <kind> --digest <digest> --entry <key> --by "<name>" --reply "<their words, verbatim>" [--disposition except|question] --json`. Offer "ok to the rest" as you go: if the person says it, record it with `--rest` in place of `--entry`; the helper marks those entries as accepted without being shown in full.
- `summary`: show the `groups`, with each entry's `summary` and why it needs review, and ask for one reply to the whole list (`--all`, `--all-except <keys>` or `--question <keys>`). Show the full text of an entry, a group or the whole list whenever asked: `eil review show --stage <stage> --kind <kind> --entry <key>` (or `--group "<section>"`, or `--all`).

The helper stores each answer as it is given. **Never keep a tally of answers in chat**: after a pause or a compaction, run `review list` again; it returns only what is still unanswered. **Never list a block the helper did not return**, and never ask again about one it settled. A `§<Section>` entry stands for every block of that section, answered together.

## What this stage is for

Verification answers **did we achieve it?** It records the evidence for each requirement, functional requirement, acceptance criterion and approved artefact, and it describes evidence only. It is not approved by a person, and it **never declares the story complete**: completion is the next stage and a person's decision. Every gate below is decided by the `eil` helper, not by you.

Every call below is `python3 .specify/extensions/eil/scripts/python/eil <subcommand> --json`. **Stop on any non-zero exit** and show the helper's `refusals` (code, message, fix). Exit 3 means there is no governed story.

## Steps

1. **Synchronise**: run `eil sync --json`.
2. **Start the stage**: run `eil stage-init verification --json`. It is refused until the task list exists (`tasks-missing`). If `s07-verification.md` already exists, continue from it.
3. **List what needs a row**: run `eil trace --report --json` and `eil artifact list --json`. Every `REQ`, every `FR` and `NFR`, and every `ART` of an approved stage needs at least one row.
4. **Write one `EVD` row per target** (or one row for several targets it genuinely covers) in the section that fits: the row traces to what it verifies, carries `(status: verified|failed|unverified|excepted)`, and, for a verified or failed row, a `Kind:` (automated or manual) and an `Evidence:` line that points at something real: a test name and result, a build, a scan report, a review record. Add `(code: <sha or PR#n>)` where the change is known.
   - **Automated evidence** is test, build, static analysis, security scan, lint and type-check results. **Manual evidence** is a review, a screenshot check, a walkthrough. Keep them apart.
   - Evidence suits the kind of thing verified: a screenshot review for a wireframe, a schema or migration comparison for an ER diagram, an integration or end-to-end trace for a sequence diagram, conformance evidence or an exception for a container or component.
   - **Never invent evidence.** If you did not see a result, do not record it as verified: record the row `unverified`. Run the tests, or ask the human for the result.
   - **Never write `[ai-draft]` by hand.** The helper renders that cue from your classification; a person reviews the rows on the `inferred` list.
5. **Exceptions.** Anything not verified, and any accepted deviation from the design, is an exception: `(status: excepted)` with `Accepted by:` and `Reason:` lines. **The person who accepts it is asked; never write yourself, or a name the human did not give, as the person accepting an exception.**
   - **Classify the rows**: write the classification file and run `eil blocks classify --stage verification`, then the `inferred` list (`eil review list --stage verification --kind inferred`), exactly as every stage does. Never write `[ai-draft]` by hand.
   - **Record code-review findings** under `## Review Findings` as `RF-###` items with `(status: open|resolved|excepted)`, a `Root:` line (`implementation`, or the upstream stage that is wrong) and, for an excepted one, `Accepted by:` and `Reason:`. Ask the person for the root of each finding; never decide it yourself. A finding rooted upstream is handed to `/speckit-eil-correct` with the finding as its origin. Completion is refused while a finding is open.
6. **List every open task** of `s06-tasks.md` under Open Tasks, by id. Do not hide one and do not write "None" while a task is open.
7. **Check**: run `eil check --stage verification --json` and fix what the code found.
8. **Report** the evidence and the gaps: every target that is unverified, failed or excepted, and every open task. **Never declare completion**, never write that the story is done, and do not offer an approval of this stage: say that `/speckit-eil-complete` is the next step, and that it is the human's decision.
9. **Finish**: run `eil sync --json`.

## Rules

- Do not write a Completion heading or any sentence saying the story is complete; the check reports it.
- You never record an approval or edit the `assessment` region by hand.
