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
   - **Tag every row you write with `[ai-draft]`.** A person removes the tag once they have checked the evidence exists.
5. **Exceptions.** Anything not verified, and any accepted deviation from the design, is an exception: `(status: excepted)` with `Accepted by:` and `Reason:` lines. **The person who accepts it is asked; never write yourself, or a name the human did not give, as the person accepting an exception.**
6. **List every open task** of `s06-tasks.md` under Open Tasks, by id. Do not hide one and do not write "None" while a task is open.
7. **Check**: run `eil check --stage verification --json` and fix what the code found.
8. **Report** the evidence and the gaps: every target that is unverified, failed or excepted, and every open task. **Never declare completion**, never write that the story is done, and do not offer an approval of this stage: say that `/speckit-eil-complete` is the next step, and that it is the human's decision.
9. **Finish**: run `eil sync --json`.

## Rules

- Do not write a Completion heading or any sentence saying the story is complete; the check reports it.
- You never record an approval or edit the `assessment` region by hand.
