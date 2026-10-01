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

## What this stage is for

Requirements answer **why**: the problem, the outcome wanted, who is affected, and what success looks like. They describe the problem and outcome without prescribing an implementation. The AI drafts and challenges; **a human decides and approves**. Every gate below is decided by the `eil` helper, not by you.

Every call below is `python3 .specify/extensions/eil/scripts/python/eil <subcommand> --json`. **Stop on any non-zero exit** and show the helper's `refusals` (code, message, fix). Exit 3 means there is no governed story yet.

## Steps

1. **Synchronise**: run `eil sync --json`. If it exits 3 there is no story yet: start one. Use `.specify/feature.json` if it names a feature directory; otherwise ask the user for a title and choose `specs/<NNN>-<short-name>` (the next free number), then run `eil start --title "<title>" --feature-dir "<directory>" --json`.
2. **Read** `s01-requirements.md` in the feature directory. Its headings are the process standard's; its HTML comments say what each section holds.
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
3. For each new finding run `eil challenge add <stage> --target <item id or section> --text "<a specific, actionable statement of the gap>" --json`. Be specific: name what is missing or contradicted and where. If the helper refuses it as `duplicate-of-closed`, that point is already settled; leave it.
4. Present the challenges to the human. **The human answers**: they accept it (the content is changed), reject it (with a reason) or defer it (accepting the risk). The human may answer several at once, by id or by saying "accept all"; record each answer with its own `eil challenge answer <CH-id> --response accepted|rejected|deferred --by "<their name>" [--reason "<their words>"]` call, only for what they have actually given in this conversation. **Never answer a challenge yourself**, never pick a response on their behalf, and never write the reason for them. When an accepted challenge is fixed in the human's own dictated words, write it untagged with `(decided: CH-id)` rather than `[ai-draft]`.
5. While any challenge is open the stage cannot be approved. Say so, and list them.

## Rules

- When you re-edit an item that carries a `(decided: CR-###)` clause, remove or replace the clause; never leave one that no longer matches the text.

- You never record an approval, edit the `assessment` or `approval` regions by hand, or answer an open question on the human's behalf.
- Do not offer to approve until the gate is met and no `[ai-draft]` tag remains; then tell the user to run `/speckit-eil-approve`.
- Once you know the confirming person's name in this conversation, reuse it for every `--by` this session without asking again, unless the human names someone else.
