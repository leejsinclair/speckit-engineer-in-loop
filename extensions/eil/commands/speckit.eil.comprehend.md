---
description: Take the comprehension check on the Functional or Technical Specification before approving it.
argument-hint: "functional or technical"
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## Guard (engineer-in-the-loop)

If `.specify/extensions/eil/scripts/python/eil` does not exist, STOP. Tell the user to run `specify extension add eil` and then `specify preset add engineer-in-the-loop`, and do nothing else: continuing without the helper would let a story bypass its gates.

## What this command is for

Approving a specification is a human decision, and it is only worth something if the person understands what they are approving. So, before approving the Functional or Technical Specification, the developer answers **five questions of rising difficulty about the document's own content**: recognise, explain, apply, trace, evaluate. The check is required to be taken and recorded on the version to be approved. **Passing is not required**: a person may skip a level, ask for the answer, or answer wrongly, and still approve. Those outcomes are recorded as they are and are visible in review. The check is a conversation, never an exam.

The `eil` helper chooses which items each level asks about, by a fixed formula, so the same version always gives the same targets. **You choose only the wording.** You may not choose a different item. You judge answers by meaning, and your judgment is yours: label it as such ("in my judgment ..."); it is not verified.

Every call below is `python3 .specify/extensions/eil/scripts/python/eil <subcommand> --json`. **Stop on any non-zero exit** and show the helper's `refusals` (code, message, fix).

## Steps

1. **Synchronise**: run `eil sync --json`.
2. **Choose the stage** (`functional` or `technical`) from the user's input or the story's current stage.
3. **Get the plan**: run `eil comprehension plan --stage <stage> --json`. If it is refused with `comprehension-prerequisites`, show the reasons (another criterion is unmet, or a challenge is open) and stop: the check is taken on the version to be approved, after those are fixed. `stage-not-eligible` means only Functional and Technical have a check.
   - **A re-approval is a delta check (D-27).** If the response carries a `delta` field, the stage was approved before and this check is only about what changed since then: `delta.changed` names the affected items. When `delta.human_decided` is true, **ask nothing**: every level in `levels` is `no-material` with the given reason (every changed item is a recorded human decision) — go straight to step 7 for each. Otherwise at most two levels are named; the rest are `no-material` too and are recorded the same way, with no question.
4. **Pre-scan before asking anything — a backstop, not a second full sweep.** The stage command's own drafting pass already swept the whole document for gaps before you got here; this only re-checks the (at most five, and on a delta check, at most two) target items the plan just named, their sections, and (for `trace`) the whole chain. Look for anything the document is **silent** on, **ambiguous** about, or **contradicts itself** on, at those items only. If you find any, raise **all of them as one batch of challenges** (`eil challenge add <stage> --target <ID> --text "<the specific gap>" --by ai`), tell the human, and **stop before question 1**: record no level. When the challenges are answered and the document has changed, plan again on the new version and start over.
5. **Ask the five questions, one at a time, in this order**: recognise, explain, apply, trace, evaluate — or, on a delta check, only the levels the plan named. Each is **one question in your own words about the item the plan named for that level**:
   - Levels 1 and 2 may be multiple choice, but only where plausible alternatives exist; levels 3 to 5 are free text.
   - Level 3 (apply) sets a situation and asks what the specification says should happen.
   - Level 4 (trace) follows the real chain the plan gives, from the item back to its requirement or use case (and, if it names one, the artifact), and asks the developer to walk it.
   - Level 5 (evaluate) asks about a limit, a rule, or a trade-off and rejected alternative.
   Wait for the human's own answer. Do not answer for them.
6. **Judge on meaning, not wording.** If the answer is right, say so briefly and go on (level outcome `understood`, or `coached` if it took a hint).
   - **A wrong answer**: give a hint that names a section or an id, **without stating the answer**, then re-ask as a **newly worded** question at the **same level**. **Never the same wording twice.** Do not state the expected answer after a wrong answer.
   - **On Functional**: if an answer drifts into implementation (a technology, a table, a class), redirect the human to the behaviour and re-ask; this does not use up an attempt.
   - **A skip**: say so plainly, record the level as `skipped`, and offer to ask again about a different item (`eil comprehension plan --stage <stage> --level <level> --attempt <k+1>`).
   - **A request for the answer**: state the expected answer **only when the human asks for it**, record the level as `revealed`, and offer the same re-ask.
   - **The document at fault**: if while asking you find the document is silent, ambiguous or contradicts itself on the matter at hand, **raise a challenge (`eil challenge add`) and pause the whole check**. Do not coach the human toward either reading. When it is resolved, plan again.
   - A level with nothing to ask about (the plan says `no-material`) is recorded as `not-applicable` with that reason.
7. **After each level** record it: `eil comprehension record --stage <stage> --level <level> --outcome <understood|coached|revealed|skipped|not-applicable> --attempts <n> --items <ids> --by "<the human's name>" [--reason "<why>"]`. Only a person can take the check: record it under the developer's own name, and never record an outcome for a level the human did not take part in.
8. **Never write any question, answer or hint into any file, record or commit message.** The record holds levels, outcomes, attempt counts and item ids only. Do not save the conversation.
9. **No game mechanics.** Never use points, scores, streaks, timers, rankings or rewards, and no praise beyond a brief acknowledgement.
10. **Finish**: report the counts by outcome, any challenges you raised, and the next step. On a first approval that is `/speckit-eil-approve`; on a re-approval where every change is a recorded human decision, `/speckit-eil-amend <stage> --from <ids>` may cover it instead — say so. State plainly that skipped or revealed levels will show in the approval record. Run `eil sync --json`.

## Rules

- The check must be taken on the current version: any edit to the document afterwards makes the record stale and it must be taken again. A change of line endings or trailing spaces does not.
- You never decide that someone has understood enough. There is no pass mark; the human decides whether to approve.
- Once you know the confirming person's name in this conversation, reuse it for every `--by` this session without asking again, unless the human names someone else.
