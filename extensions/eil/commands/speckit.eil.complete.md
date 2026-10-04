---
description: Close the story: summarise it, state that each approved diagram is current, and record the human's confirmation that the evidence was reviewed.
argument-hint: "Anything the developer wants recorded, such as deployment status"
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

Completion answers **are we satisfied?** It is a person's decision: one recorded confirmation, made after reading the evidence. It is refused while the Verification document is missing, or while a requirement or an approved artefact is unverified without an exception, unless a configured confirmer records a named override. Every gate below is decided by the `eil` helper, not by you.

Every call below is `python3 .specify/extensions/eil/scripts/python/eil <subcommand> --json`. **Stop on any non-zero exit** and show the helper's `refusals` (code, message, fix). Exit 3 means there is no governed story.

## Asking for the approval

Ask the helper's question and nothing more: `eil status --json` gives it as `next_action.question` (for example "Approve the Functional Specification as the behaviour you require?"); the helper records it beside the reply, so the record shows exactly what was confirmed. A reply of "ok", "yes" or "approved", or any other reply the person gives, is a complete answer: pass it verbatim. Do not ask for a longer statement, and do not offer example sentences as the wording to use. Ask the person's name once per session and reuse it for every `--by`, unless they name someone else. Silence, "just approve it", or a reply you would have to write for them is not an answer: ask the question again.

## Steps

1. **Synchronise**: run `eil sync --json`.
2. **Start the stage**: run `eil stage-init completion --json`. It is refused until the Verification document exists (`verification-missing`) and Requirements, Functional and Technical are approved. If `s08-completion.md` already exists, continue from it.
3. **Fill the record from what the other stages hold**, and nothing new: completion status, implementation summary, requirements satisfied, outstanding issues (including open tasks and accepted risks), accepted deviations, relevant technical decisions, verification summary, deployment status, and documentation and support implications. Ask the human for anything you cannot see, such as the deployment status. Tag every passage you write with `[ai-draft]`.
4. **Ask what implementation touched, one reply per list.** Run each of these lists and skip any that is empty; show a non-empty one with its `purpose` (awareness, understanding, decision, validation or approval) and take one reply from the developer, recorded with `eil review answer` (`--all`, `--all-except`, `--question` or `--reopen`, the person's words in `--reply`, the list's `--digest`):
   - `eil review list --stage completion --kind low-challenges --json`: every open low challenge on any stage, together. "Defer all, accepted as minor" is one reply: pass `--all --defer-reason "<their reason>"`; each challenge is closed as deferred with that reason and their name. Any they name as an exception stay open for them to accept or reject one by one with `eil challenge answer`. Completion is refused while any challenge is open.
   - `eil review list --stage verification --kind evidence --json`: only the evidence the helper could not confirm from files, and all manual evidence. Say that a row the helper confirmed means the named test exists; its result is attested (exists; result attested), never that it passed.
   - `eil review list --stage tasks --kind tasks --json`: ticked tasks completed against a version of their sources that has since changed.
   - `eil review list --stage completion --kind diagram-currency --json`: only the artefacts a task with code reached, or that changed since their approval. Ask whether each diagram is still current; never assume it.

   Then write Diagram Currency from that: a line `- ART-004: current` for each touched artefact the developer confirmed, and one `- untouched: ART-001, ART-002, ...` line for the rest (`eil status --json`, `diagram_currency.untouched`), listed without a question. Do not ask about an untouched artefact.
   Where what was built differs from the design and the developer accepts the difference, the design is wrong, not the code: open a correction with `eil correct open --item <ART> --found-in completion --problem "<what differs>" --by "<their name>" --wording "<their wording>"` so the design is corrected in place and the completion record lists it. Do not annotate the document or write it as a deviation. Use `- ART-007: deviation, accepted by <person>, because <reason>` (and list it under Accepted Deviations) only when the developer says the document should keep describing a future target, and record that reason. Never write yourself as the person accepting a deviation.
   List the deferred challenges (`eil status --json`, `outstanding.deferred_challenges`) under Outstanding Issues, with who deferred each and why.
5. **Check**: run `eil check --stage completion --json` and show which criteria are met and which are not. If the gate is not met, say why and stop: do not ask for a confirmation that will be refused. If the human wants to waive one criterion, that is `/speckit-eil-override`.
6. **Ask the human directly** whether they have reviewed the evidence and confirm the story is complete, and for the name they are confirming as. Put the question to the person in the conversation and wait for their own answer.
7. **Record it** with their words passed **verbatim**:

   ```bash
   eil approve completion --by "<their name>" --attestation "<their words, verbatim>" --json
   ```

   On a refusal (`verification-missing`, `unverified-requirement`, `unverified-artifact`, an unmet criterion), show it and stop.
8. **Finish**: run `eil sync --json`, then report the approval or the refusal.

## Rules

- **Never supply the confirmation yourself.** Do not write, paraphrase or complete the human's answer, and do not treat silence or "just approve" as one.
- Do not edit the `approval` region by hand, and do not describe the story as complete before the helper has recorded the approval.
