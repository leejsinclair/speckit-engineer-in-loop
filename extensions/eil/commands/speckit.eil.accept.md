---
description: Accept the changes made to a previously approved stage, with one short confirmation when every change is already a recorded decision.
argument-hint: "The stage whose approval is out of date, for example: functional"
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

### Reviewing on the page

The person may review the Requirements, Functional and Technical lists on a page in their browser instead of here. The page shows the whole document, highlights exactly the entries the helper lists, asks each one's fixed question, and stores each answer through the helper as it is given, the same way an answer in chat is stored.

1. **Choose the surface once per session.** At the first review step of a session, ask: "Review on a page in your browser, or here in chat?" Say that this is about how they review, not what they approve. Ask this once per session and use the answer for every later review; ask again only if the person asks to change it.
2. **Page chosen:**
   - run `eil review serve --status --json`;
   - if no page is running, start it in the background with `eil review serve --by "<name>" --json` and read the address from its first line; if one is running, ask the person to reload it;
   - give them the address, say which stage and list it shows, and ask them to answer there and say "done";
   - **do not print the list in chat**, and do nothing with the review until they say "done";
   - **never open, fetch or post to the page address yourself**: give it to the person only. You never answer on the page;
   - pass `--host` only when the person asks for another address (in a container, for example: `--host 0.0.0.0 --public-name <name>`).
3. **After "done":**
   - run `eil review list --current --json`; it returns what the person answered on the page, in `answers` while the list is still open and in `last_answers` once it closed, each with the person's comment and name;
   - for each send-back: show the comment, rework the block, and say what changed;
   - for each question: answer it in chat, or raise a challenge if the document is wrong, and rework the block if the answer changes it;
   - then ask the person to reload the page and answer those blocks there;
   - **never record a page-surface entry's answer in chat** with `review answer`: the person answers it on the page;
   - when the list is empty, continue the stage: the comprehension check, then approval in chat, as before.
4. **A comment on a settled block** arrives as a reopened entry on the list, with the person's comment ("reopened by <name>: <comment>"). Act on it as on a send-back.
5. **The page cannot start** (any refusal, such as `page-running`, `port-unavailable` or `ambiguous-story`), or the person cannot reach the address: say why in one line and review in chat exactly as above. If the person asks to switch to chat in the middle of a list, run `review list` and continue here: the helper already holds what was answered on the page.
6. **Name**: pass the name the person gave in chat (asked at most once per session). Never pass the AI's name. The page shows "Answering as <name>" and lets the person change it there.

Approval, overrides, waivers and the comprehension check stay in chat. Never send the person to the page for approval.

The page reviews only the Requirements, Functional and Technical stages: when the stage is one of them and the person chose the page, hand its `changes` review to the page as above. For any other stage, review in chat.

## What this command is for

A stage that was approved and has since changed is `needs-re-review`. This command brings it back without repeating the whole approval. The helper works out what changed and which changes are **covered** by a decision the person already recorded (an accepted challenge, a resolved question, a clarify answer or an earlier review). It carries the approval forward on a short sign-off only when every change is covered; otherwise the person answers the uncovered changes once, in one reply. It is not a lighter approval: the helper records who confirmed, in their own words, and how the approval was reached.

Every call below is `python3 .specify/extensions/eil/scripts/python/eil <subcommand> --json`. **Stop on any non-zero exit** and show the helper's `refusals` (code, message, fix).

## Asking for the approval

Ask the helper's question and nothing more: `eil status --json` gives it as `next_action.question` (for example "Approve the Functional Specification as the behaviour you require?"); the helper records it beside the reply, so the record shows exactly what was confirmed. A reply of "ok", "yes" or "approved", or any other reply the person gives, is a complete answer: pass it verbatim. Do not ask for a longer statement, and do not offer example sentences as the wording to use. Ask the person's name once per session and reuse it for every `--by`, unless they name someone else. Silence, "just approve it", or a reply you would have to write for them is not an answer: ask the question again.

## Steps

1. **Synchronise**: run `eil sync --json`, then `eil status --json` to confirm the stage is `needs-re-review` and was approved before. If it was never approved, this is not the command: offer `/speckit-eil-approve`.
2. **List the changes**: run `eil review list --stage <stage> --kind changes --json`. Show every entry with the helper's own words. For an entry with `covered_by`, say which decision covers it. Any one-line summary you add is a draft by the AI and must be labelled as such.
2a. **An approval older than section-level records**: if the list holds a `legacy:<stage>` entry, the stage was approved before the tool kept section-level records and has changed since, so the tool cannot compare it section by section. Show the entry's own statement (its `what`) as written, with the changed items listed beside it, and ask for **one reply** to the whole list. That reply, recorded like any other in step 4, re-signs the stage; the approval is then marked "re-signed without comparison" everywhere it is shown. **Never point the person to a full re-approval** for this: one reply is all that is needed.
3. **If nothing is uncovered** (every entry has `covered_by`): ask the person for their sign-off ("ok" is enough; the helper records it with its re-approval question), then go to step 5.
4. **Otherwise ask once**: show the uncovered entries and ask for one reply. Record it with `eil review answer --stage <stage> --kind changes --digest <digest from step 2> --by "<their name>" --reply "<their words, verbatim>"` plus exactly one of `--all`, `--all-except IDS`, `--question IDS`, `--reopen IDS`, matching what they said. On `list-changed`, show the new list and ask again. On `reply-mismatch`, re-read the reply and pass the flags it actually means; never change the reply. On `acceptance-conflict`, show both answers and ask a configured confirmer to answer again. If the stage takes a comprehension check, run `/speckit-eil-comprehend` for the delta when the helper asks for it.
5. **Confirm**: draft a one-line summary for every change, covered or not (a draft by the AI, labelled as such; it becomes the Change Log text), write them to a file as `{"stage": "<stage>", "summaries": [{"key": "<ID>", "summary": "<text>"}]}`, and run

   ```bash
   eil review confirm --stage <stage> --by "<their name>" --confirmation "<their words, verbatim>" --summaries FILE --json
   ```

   Pass the same file with `--summaries` to `eil review answer` in step 4 for the uncovered changes. `summary-missing` means a change has no summary: add it and run again.

   On a refusal, show it and say what it means: `changes-unanswered` (an uncovered change has no answer yet: go back to step 4), `comprehension-prerequisites` (the delta check must be taken first), `confirmation-required`, `not-a-confirmer`, `ai-approval`, `acceptance-conflict`, `not-amendable`.
6. **Say how it was reached**: the approval is marked `carried-forward`, `reviewed` or `re-signed-without-comparison`, naming the decisions it rests on, in the stage document, the overview and every later report.
7. **Unsettled challenges**: if `eil review list --stage <stage> --kind unsettled-challenges --json` is not empty, show it and ask once. A challenge that was rejected or deferred and whose target has since changed is either reconfirmed by a configured confirmer or reopened by anyone (`--reopen`).
8. **Finish**: run `eil sync --json`.

## Rules

- **Never supply the sign-off or the confirmation yourself**, and never answer the list on the person's behalf. Only their own words are recorded.
- Never pass a reply you wrote as the person's. Do not choose which changes to accept.
- Do not edit the `approval` region by hand.
- If you edit an item that carries an earlier `(decided: CR-###)` clause, remove or replace the clause; never leave one that no longer matches the text.
- Once you know the confirming person's name in this conversation, reuse it for every `--by` this session without asking again, unless the human names someone else.
