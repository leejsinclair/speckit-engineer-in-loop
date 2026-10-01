---
description: Raise specific challenges against a stage, or record a person's answer to one. AI challenges; humans decide.
argument-hint: "A stage to challenge, or a challenge id (CH-001) to record an answer to"
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## Guard (engineer-in-the-loop)

If `.specify/extensions/eil/scripts/python/eil` does not exist, STOP. Tell the user to run `specify extension add eil` and then `specify preset add engineer-in-the-loop`, and do nothing else: continuing without the helper would let a story bypass its gates.

## What this command is for

Any definition stage can be challenged: the AI questions assumptions, points out gaps and contradictions and proposes alternatives, and a person decides. The objective is not to stop the AI questioning decisions; it is to stop important decisions being made implicitly by the AI. A recorded answer is a constraint you keep.

Every call below is `python3 .specify/extensions/eil/scripts/python/eil <subcommand> --json`. **Stop on any non-zero exit** and show the helper's `refusals` (code, message, fix). Exit 3 means there is no governed story.

## Steps

1. **Synchronise**: run `eil sync --json`, then `eil status --json` to see every stage, its open challenges and its recorded ones.
2. **Choose the mode** from the user's input:
   - a stage name (or none, meaning the current stage): **raise** challenges (step 3);
   - a challenge id: **record the person's answer** (step 4).
3. **Raise challenges.** Read the stage document and the approved documents upstream of it. Find gaps (a behaviour, failure or boundary with no definition), contradictions, unstated assumptions, untestable statements, prescription at the wrong level, unresolved decisions, and mismatches between a diagram or wireframe and the text. Rate each by how much it matters: `high` (a decision or behaviour that would be wrong or missing), `medium`, or `low` (minor wording or polish). The rating is required for you (`--severity high|medium|low`; the helper exits 2 without it) and is shown as the AI's rating, so label it as the AI's when you report it. For each, run `eil challenge add <stage> --target <item id or section> --severity <high|medium|low> --text "<a specific, actionable statement>" --json`. Raise the high ones first. **Do not re-raise a point a person already rejected or deferred**: read the recorded challenges first, and if the helper refuses with `duplicate-of-closed`, leave it. A challenge that says only "this is unclear" is not specific enough: say what is unclear and where.
4. **Record an answer.** Ask the person directly, in the conversation: is the challenge **accepted** (the document is changed, so change it with them), **rejected** (they give a reason), or **deferred** (they give the reason and explicitly accept the risk)? If several challenges are open, they may answer them all in one reply (by id, or "accept all"); record each with its own call. Ask for the name they are answering as, once, and reuse it for the rest of this session unless they name someone else. Then run `eil challenge answer <CH-id> --response <accepted|rejected|deferred> --by "<their name>" [--reason "<their words, verbatim>"] --json` for each. If two people have answered differently the helper reports a conflict; say so and ask the person who owns the stage to settle it. When an accepted challenge's fix is the human's own dictated words, write it into the document untagged with `(decided: CH-id)` instead of `[ai-draft]`.
5. **Change a severity** only when a person asks: `eil challenge severity <CH-id> --to <high|medium|low> --by "<their name>" --json`. Anyone may raise a severity; only a person configured to confirm the stage may lower it (the helper refuses `not-a-confirmer`). Never lower one yourself.
6. **Report** the challenges now open, high first, then medium, then low, each with the AI's rating labelled. Say the stage cannot be approved while a high or medium one is open; low ones are listed as outstanding at approval and do not block. Each question to the person names its purpose (decision for an answer).
7. **Finish**: run `eil sync --json`.

## Rules

- Every request to a person states its purpose, one of awareness, understanding, decision, validation or approval; use the `purpose` the helper gives (on `next_action` and on each review list) and do not invent one.

- **Never answer a challenge on the human's behalf**: do not choose the response, write the reason or treat silence as agreement.
- Treat a rejected or deferred answer as an established constraint and do not work against it.
- Do not edit a challenge record by hand.
- Once you know the confirming person's name in this conversation, reuse it for every `--by` this session without asking again, unless the human names someone else.
