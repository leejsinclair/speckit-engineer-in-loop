---
description: Draft, challenge and gate the Functional Specification (what must the system do?).
argument-hint: "Anything the developer wants emphasised or already knows"
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

## Under the small-story profile

If `eil status --json` shows an active `profile`, do not ask for wireframe exports: the wireframe criterion (FUN-G15) is met by the recorded authorisation, and `eil check` says so. Everything else in this stage, including its approval, is unchanged.

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

In this stage, the gap scan of the drafting pass runs before you offer the page.

## What this stage is for

The Functional Specification answers **what** the system must do to satisfy the approved requirements, independently of how it is built. It must be understandable by developers, analysts, testers and business stakeholders. The AI drafts and challenges; **a human decides and approves**. Every gate below is decided by the `eil` helper, not by you.

Every call below is `python3 .specify/extensions/eil/scripts/python/eil <subcommand> --json`. **Stop on any non-zero exit** and show the helper's `refusals` (code, message, fix). Exit 3 means there is no governed story: offer `/speckit-eil-requirements`.

## Steps

1. **Synchronise**: run `eil sync --json`.
2. **Start the stage**: run `eil stage-init functional --json`. It is refused (`stage-not-approved`) until Requirements carry an approval; do not work around that. If `s02-functional-spec.md` already exists, continue from it.
3. **Read** the approved Requirements and the Functional Specification with `eil show requirements --json` and `eil show functional --json`. When you draft a section, open `s02-functional-spec.md` to edit it: the template's comments say what each section holds.
   - **Never ask the developer about mechanism** (how something will be built: storage, caching, sort keys, module layout, test structure). The Functional Specification describes behaviour; leave mechanism to the Technical stage, where it is decided with the developer or recorded as `ai-decided`.
4. **Derive the behaviour from the approved requirements, and only from them.**
   - Write each behaviour as a functional requirement, `**FR-001**: The system shall ... (traces: REQ-001)`, and each measurable quality as `**NFR-001**: ... (traces: REQ-001)`. Every one traces to at least one approved `REQ` or `UC`; every approved `REQ` is covered by at least one.
   - Describe every use case from Requirements under Use Cases and Scenarios, naming it by its id: preconditions, trigger, main flow, alternative flows, exception flows, expected outcome.
   - Fill Actors, Business Rules, Inputs, Outputs, State and Workflow, Validation, Error and Exception Behaviour, Security and Access Behaviour, Audit and Compliance Behaviour and Acceptance Criteria from what the requirements and the human support. Where you would have to guess, write an open question (`**OQ-###**: ... (status: open) (material: yes)`) instead of assuming.
   - **Never write `[ai-draft]` by hand.** The helper renders that cue itself, from what you classify. Where a passage is your own inference rather than a restatement of an approved source, leave it plain: it is listed for review when you run the `inferred` list (below). Approval is refused while any block is unreviewed.
   - **Human-decided provenance.** When the text is the human's own words, copied verbatim from a decision they already made — an accepted challenge, a resolved open question, or a clarify answer carried by `/speckit-eil-resolve` — write it **untagged**, with `(decided: CH-004)`, `(decided: OQ-002)` or `(decided: AIS-007)` instead of `[ai-draft]`, naming the exact id. Everything else you write is still `[ai-draft]`.
   - **Flag implementation prescription.** If a requirement names a technology, a data store, a protocol or a design ("store it in PostgreSQL"), do not accept it as functional content: raise a challenge that it belongs in the Technical stage, and write the behaviour it needs instead (FR-020).
5. **Draw one system-level sequence diagram per use case** under Sequence Diagrams, as an `ART` item with a Mermaid `sequenceDiagram` block that traces to its use case and to the functional requirements it shows. Participants are **only the declared Actors and the System** (`participant System`): no container, component, class or technology. Show the main, alternative and exception flows. If a use case genuinely has no interaction to draw, list it under `## Not applicable` by its id with the reason. Do not draw an ER or a C4 diagram here.
6. **List the screens and states that need wireframes.** If the story has a user interface, add one `ART` line per screen and per significant state (default, empty, loading, error) under Wireframes, each tracing to the requirement or use case it shows, and **ask the human to export each frame from Figma** and run `/speckit-eil-artifact`. **Never draw, create, convert or edit a wireframe or any exported file yourself**, and never invent a link to one. If the story has no user interface, list "Wireframes" under `## Not applicable` with the reason.
7. **Check the gate**: run `eil check --stage functional --json`, fix what the code found, and re-run.
8. **Judge the judgment criteria.** For each criterion with `"kind": "judgment"` decide honestly whether the document meets it, and write a judgments file **outside the repository**:

   ```json
   {"stage": "functional",
    "judgments": [{"id": "FUN-G10", "status": "met", "reason": "one sentence"}],
    "assessment": {"ambiguity": [], "missing": [], "contradictions": [], "unsupported_assumptions": [], "untestable": []}}
   ```

   Include an entry for every judgment criterion and fill the five lists with the specific problems you find (including any wireframe that contradicts the text, if you can view it: that is your judgment, not a structural check). Run `eil check --stage functional --judgments <file> --json`. Your verdicts are labelled as the AI's, apply only to the exact text you assessed, and cannot make a code-decided criterion met.
9. **Classify and list the inferred blocks.**

   **Before the first review list, scan for gaps.** Run `eil comprehension plan --stage functional --json` (it only reads) and look at the items it names, their sections and, for `trace`, the whole chain: is the document silent on something they need, ambiguous about it, or does it contradict itself? Raise each gap as a challenge first (`eil challenge add ... --severity high|medium|low`, the severity is required), before any list is shown, so it is settled before the person reviews. If the plan is refused because the gate is not met yet, scan the items you expect it to name (the stage's numbered items) the same way. The comprehension check's own pre-scan stays as the backstop.

   Write a classification file outside the repository: `{"stage": "functional", "blocks": [{"block": "FR-001", "adds": null}]}`, one entry per block you wrote or changed. A block that restates an approved source has no `adds`; a block that goes beyond its sources carries `adds`, one sentence saying what it adds. Run `eil blocks classify --stage functional --file <path> --json`; the helper decides restated, decided or inferred from the traces and hashes, and renders the review cue itself. Then run `eil review list --stage functional --kind inferred --json`. **If chat is the chosen surface**, show the human that one list. They answer once, in their own words (for example "ok except FR-003"); pass their reply verbatim to `eil review answer --stage functional --kind inferred --digest <digest> --reply "<their words>" --by "<name>" [--all-except <ids>] --json`. If the page is the chosen surface, follow "Reviewing on the page" above instead: do not show or answer the list in chat. Never answer for them. When you re-edit an item that carries a `(decided: ID)` clause, replace or remove the clause so it still matches the text.
10. **Report** the gate result, every remaining `[ai-draft]` tag and open question, and any screen still waiting for an export. When the gate is otherwise met, offer `/speckit-eil-comprehend`: the developer takes the comprehension check on this version before approving.
11. **Finish**: run `eil sync --json`.

## The challenge pass

Before you report, review the stage document the way a careful colleague would, against its approved upstream documents. **AI challenges. Humans decide.**

1. Look for: **gaps** (a behaviour, failure or boundary with no definition), **contradictions**, **unstated assumptions**, **untestable statements**, **implementation prescription at the wrong level**, and **unresolved decisions**. Also compare each diagram and wireframe with the text: a flow in the text missing from its sequence diagram, a diagram element the text never mentions, a screen state with no wireframe, an error path shown in one place and not the other, or a container with no data store where the text implies persistence. You may review a wireframe's content only if you can view the image, and then it is your judgment, not a structural finding.
2. Run `eil status --json` and read the challenges already recorded on this stage. **A challenge a person has rejected or deferred is a standing constraint**: do not raise the same point again, and do not silently work against it. Treat an answer to a challenge as established.
3. For each new finding run `eil challenge add <stage> --target <item id or section> --severity high|medium|low --text "<a specific, actionable statement of the gap>" --json`. The severity is required (the helper exits 2 without it): `high` for a decision or behaviour that would be wrong or missing, `medium`, or `low` for wording or polish; it is shown as the AI's rating. Be specific: name what is missing or contradicted and where. If the helper refuses it as `duplicate-of-closed`, that point is already settled; leave it.
4. Present the challenges to the human. **The human answers**: they accept it (the content is changed), reject it (with a reason) or defer it (accepting the risk). The human may answer several at once, by id or by saying "accept all"; record each answer with its own `eil challenge answer <CH-id> --response accepted|rejected|deferred --by "<their name>" [--reason "<their words>"]` call, only for what they have actually given in this conversation. **Never answer a challenge yourself**, never pick a response on their behalf, and never write the reason for them. When an accepted challenge is fixed in the human's own dictated words, write it untagged with `(decided: CH-id)` rather than `[ai-draft]`.
5. While any challenge is open the stage cannot be approved. Say so, and list them.

## Rules

- When you re-edit an item that carries a `(decided: CR-###)` clause, remove or replace the clause; never leave one that no longer matches the text.

- You never record an approval, edit the `assessment`, `comprehension` or `approval` regions by hand, or answer an open question or a challenge on the human's behalf.
- Do not offer to approve until the gate is met and the comprehension check has been taken on this version.
- Once you know the confirming person's name in this conversation, reuse it for every `--by` this session without asking again, unless the human names someone else.
