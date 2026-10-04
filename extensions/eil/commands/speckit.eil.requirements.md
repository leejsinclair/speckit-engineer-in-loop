---
description: Start a story and draft, challenge and gate the Requirements stage (why are we doing this?).
argument-hint: "Describe the problem or change the story is about"
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## Guard (engineer-in-the-loop)

If `.specify/extensions/eil/scripts/python/eil` does not exist, STOP. Tell the user to run `specify extension add eil` and then `specify preset add engineer-in-the-loop`, and do nothing else: continuing without the helper would let a story bypass its gates.

## Proposing the small-story profile

You may propose the **small-story profile** when the story looks small: for example the request already states the behaviour and how it will be accepted in detail, there are few requirements, or the change is confined to one component. Name the signals you saw and label the proposal as your own: start it with `AI assessment:`. Say what it changes (no wireframe exports, one review of the AI Specification, plan and tasks before implementation, two comprehension levels) and that every approval is still required.

Only a person authorises it. **Ask who authorises it and why**, and wait for their answer. If they agree, record their words: `eil profile set small --by "<their name>" --reason "<their words>" --json`. **Never run `profile set` without the person's own words**, and never decide the story is small yourself. If they decline or say nothing, the story follows the full workflow and nothing is recorded.

If later work shows the story is larger than proposed (more than one container touched, new data stored, or more requirements than you expected), say that it **outgrows the profile** and offer to withdraw it: `eil profile withdraw --by "<their name>" --reason "<their words>" --json`. Withdrawal restores the full workflow for every stage not yet approved.

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
3. **The page cannot start** (any refusal, such as `page-running`, `port-unavailable` or `ambiguous-story`), or the person cannot reach the address: say why in one line and review in chat exactly as above. If the person asks to switch to chat in the middle of a list, run `review list` and continue here: the helper already holds what was answered on the page.
4. **Name**: pass the name the person gave in chat (asked at most once per session). Never pass the AI's name. The page shows "Answering as <name>" and lets the person change it there.

Approval, overrides, waivers and the comprehension check stay in chat. Never send the person to the page for approval.

## What this stage is for

Requirements answer **why**: the problem, the outcome wanted, who is affected, and what success looks like. They describe the problem and outcome without prescribing an implementation. The AI drafts and challenges; **a human decides and approves**. Every gate below is decided by the `eil` helper, not by you.

Every call below is `python3 .specify/extensions/eil/scripts/python/eil <subcommand> --json`. **Stop on any non-zero exit** and show the helper's `refusals` (code, message, fix). Exit 3 means there is no governed story yet.

## Steps

1. **Synchronise**: run `eil sync --feature-dir "<directory>" --json` when you know the story's directory. If there is no story yet, start one:
   - **Never reuse `.specify/feature.json` when it names a governed story** (a directory holding `s00-README.md`): that is an earlier story, and writing to it would change its records. Use the pointer only when it names a directory that is not yet a story. Otherwise ask the user for a title and choose `specs/<NNN>-<short-name>` (the next free number).
   - **Always pass `--feature-dir`**: run `eil start --title "<title>" --feature-dir "<directory>" --json`, and pass the same `--feature-dir` on every later call. The start always moves the pointer to the new story and reports the move (`pointer.previous`); tell the user.
   - `ambiguous-story` means the helper could not tell which story a call was for; it wrote nothing. Ask the user which story, and pass it with `--feature-dir`.
   - `unexpected-branch` means the current git branch is neither the main branch nor named for the new story. Show the branch and the refusal's `question`, and **ask the developer to switch branch or confirm** that the story belongs on this branch. If they confirm, run the start again with `--on-branch <branch> --by "<their name>" --reply "<their words>"`. Never pass `--on-branch` yourself without their reply. The helper never creates or switches a branch; neither do you.
2. **Read the stage** with `eil show requirements --json`. Its headings are the process standard's. When you draft a section, open `s01-requirements.md` to edit it: its HTML comments say what each section holds.
3. **Draft from what the user said, and only from that.** Fill each section with what the user's input, the repository and the human's answers support. Where you would have to guess, do not guess: write an open question instead.
   - **Never turn an open question into an assumption.** An open question is `**OQ-001**: text (status: open) (material: yes)`. An assumption is a separate statement in Assumptions. Moving something from one to the other is a human decision, never yours (FR-022).
   - **Never write `[ai-draft]` by hand.** The helper renders that cue itself, from what you classify. Where a passage is your own inference rather than a restatement of an approved source, leave it plain: it is listed for review when you run the `inferred` list (below). Approval is refused while any block is unreviewed.
   - **Human-decided provenance.** When the text is the human's own words, copied verbatim from a decision they already made — an accepted challenge, a resolved open question, or a clarify answer carried by `/speckit-eil-resolve` — write it **untagged**, with `(decided: CH-004)`, `(decided: OQ-002)` or `(decided: AIS-007)` in place of `[ai-draft]`, naming the exact id. Everything else you write is still `[ai-draft]`.
   - Write desired outcomes as `**REQ-001**: ...` items and use cases as `**UC-001**: ... (actor: ...; goal: ...; trigger: ...; outcome: ...)`.
   - Do not prescribe an implementation.
   - A section that genuinely does not apply is removed and listed under `## Not applicable` with a reason. Never leave a required section empty.
4. **Draw the system context diagram** (C4 level 1) under `## System Context` as an `ART` item with a Mermaid `C4Context` block, and no other diagram in this document:
   - the system as one box, and **every** person under Users and Stakeholders and **every** system under Dependencies as an element, using the same names;
   - each element's description begins `[existing]`, `[new]` or `[changed]`;
   - `**ART-001**: System context (traces: REQ-001)` on the line above the block, and no wireframe or screen here (a design that already exists may only be listed under Dependencies as a reference).
5. **Check the gate**: run `eil check --stage requirements --json` and read `criteria` and `findings`. Fix what the code found, then re-run.
6. **Judge the judgment criteria.** For each criterion with `"kind": "judgment"`, decide honestly whether the document meets it. Write a judgments file **outside the repository** (for example in a temporary directory):

   ```json
   {"stage": "requirements",
    "judgments": [{"id": "REQ-G01", "status": "met", "reason": "one sentence"}],
    "assessment": {"ambiguity": [], "missing": [], "contradictions": [], "unsupported_assumptions": [], "untestable": []}}
   ```

   Include an entry for every judgment criterion. Fill the five assessment lists with the specific problems you find (ambiguous wording, missing information, contradictions, assumptions with no support, statements that cannot be tested); leave a list empty only if there are none. Then run `eil check --stage requirements --judgments <file> --json`. Your verdicts are recorded and labelled as the AI's. You cannot make any other criterion met, and a verdict is only honoured for the exact text you assessed: any later edit needs a new run.
7. **Classify and list the inferred blocks.** Write a classification file outside the repository: `{"stage": "requirements", "blocks": [{"block": "REQ-001", "adds": null}]}`, one entry per block you wrote or changed. A block that restates an approved source has no `adds`; a block that goes beyond its sources carries `adds`, one sentence saying what it adds. Run `eil blocks classify --stage requirements --file <path> --json`; the helper decides restated, decided or inferred from the traces and hashes, and renders the review cue itself. Then run `eil review list --stage requirements --kind inferred --json` and show the human that one list. They answer once, in their own words (for example "ok except REQ-003"); pass their reply verbatim to `eil review answer --stage requirements --kind inferred --digest <digest> --reply "<their words>" --by "<name>" [--all-except <ids>] --json`. Never answer for them. When you re-edit an item that carries a `(decided: ID)` clause, replace or remove the clause so it still matches the text.
8. **Report** the gate result: which criteria are met, which are not and why, and every remaining `[ai-draft]` tag and open question. Say plainly that a human still has to review the tagged text, decide the open questions and approve.
9. **Finish**: run `eil sync --json` so the overview reflects the outcome.

## The challenge pass

Before you report, review the stage document the way a careful colleague would, against its approved upstream documents. **AI challenges. Humans decide.**

1. Look for: **gaps** (a behaviour, failure or boundary with no definition), **contradictions**, **unstated assumptions**, **untestable statements**, **implementation prescription at the wrong level**, and **unresolved decisions**. Also compare each diagram and wireframe with the text: a flow in the text missing from its sequence diagram, a diagram element the text never mentions, a screen state with no wireframe, an error path shown in one place and not the other, or a container with no data store where the text implies persistence. You may review a wireframe's content only if you can view the image, and then it is your judgment, not a structural finding.
2. Run `eil status --json` and read the challenges already recorded on this stage. **A challenge a person has rejected or deferred is a standing constraint**: do not raise the same point again, and do not silently work against it. Treat an answer to a challenge as established.
3. For each new finding run `eil challenge add <stage> --target <item id or section> --severity high|medium|low --text "<a specific, actionable statement of the gap>" --json`. The severity is required (the helper exits 2 without it): `high` for a decision or behaviour that would be wrong or missing, `medium`, or `low` for wording or polish; it is shown as the AI's rating. Be specific: name what is missing or contradicted and where. If the helper refuses it as `duplicate-of-closed`, that point is already settled; leave it.
4. Present the challenges to the human. **The human answers**: they accept it (the content is changed), reject it (with a reason) or defer it (accepting the risk). The human may answer several at once, by id or by saying "accept all"; record each answer with its own `eil challenge answer <CH-id> --response accepted|rejected|deferred --by "<their name>" [--reason "<their words>"]` call, only for what they have actually given in this conversation. **Never answer a challenge yourself**, never pick a response on their behalf, and never write the reason for them. When an accepted challenge is fixed in the human's own dictated words, write it untagged with `(decided: CH-id)` rather than `[ai-draft]`.
5. While any challenge is open the stage cannot be approved. Say so, and list them.

## Rules

- When you re-edit an item that carries a `(decided: CR-###)` clause, remove or replace the clause; never leave one that no longer matches the text.

- You never record an approval, edit the `assessment` or `approval` regions by hand, or answer an open question on the human's behalf.
- Do not offer to approve until the gate is met and no `[ai-draft]` tag remains; then tell the user to run `/speckit-eil-approve`.
- Once you know the confirming person's name in this conversation, reuse it for every `--by` this session without asking again, unless the human names someone else.
