---
description: Draft, challenge and gate the Functional Specification (what must the system do?).
argument-hint: "Anything the developer wants emphasised or already knows"
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## Guard (engineer-in-the-loop)

If `.specify/extensions/eil/scripts/python/eil` does not exist, STOP. Tell the user to run `specify extension add eil` and then `specify preset add engineer-in-the-loop`, and do nothing else: continuing without the helper would let a story bypass its gates.

## What this stage is for

The Functional Specification answers **what** the system must do to satisfy the approved requirements, independently of how it is built. It must be understandable by developers, analysts, testers and business stakeholders. The AI drafts and challenges; **a human decides and approves**. Every gate below is decided by the `eil` helper, not by you.

Every call below is `python3 .specify/extensions/eil/scripts/python/eil <subcommand> --json`. **Stop on any non-zero exit** and show the helper's `refusals` (code, message, fix). Exit 3 means there is no governed story: offer `/speckit-eil-requirements`.

## Steps

1. **Synchronise**: run `eil sync --json`.
2. **Start the stage**: run `eil stage-init functional --json`. It is refused (`stage-not-approved`) until Requirements carry an approval; do not work around that. If `s02-functional-spec.md` already exists, continue from it.
3. **Read** the approved `s01-requirements.md` and `s02-functional-spec.md`. The template's comments say what each section holds.
4. **Derive the behaviour from the approved requirements, and only from them.**
   - Write each behaviour as a functional requirement, `**FR-001**: The system shall ... (traces: REQ-001)`, and each measurable quality as `**NFR-001**: ... (traces: REQ-001)`. Every one traces to at least one approved `REQ` or `UC`; every approved `REQ` is covered by at least one.
   - Describe every use case from Requirements under Use Cases and Scenarios, naming it by its id: preconditions, trigger, main flow, alternative flows, exception flows, expected outcome.
   - Fill Actors, Business Rules, Inputs, Outputs, State and Workflow, Validation, Error and Exception Behaviour, Security and Access Behaviour, Audit and Compliance Behaviour and Acceptance Criteria from what the requirements and the human support. Where you would have to guess, write an open question (`**OQ-###**: ... (status: open) (material: yes)`) instead of assuming.
   - **Tag every passage you write with `[ai-draft]`.** A person removes the tag once they have reviewed the text.
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
9. **Report** the gate result, every remaining `[ai-draft]` tag and open question, and any screen still waiting for an export. When the gate is otherwise met, offer `/speckit-eil-comprehend`: the developer takes the comprehension check on this version before approving.
10. **Finish**: run `eil sync --json`.

## The challenge pass

Before you report, review the stage document the way a careful colleague would, against its approved upstream documents. **AI challenges. Humans decide.**

1. Look for: **gaps** (a behaviour, failure or boundary with no definition), **contradictions**, **unstated assumptions**, **untestable statements**, **implementation prescription at the wrong level**, and **unresolved decisions**. Also compare each diagram and wireframe with the text: a flow in the text missing from its sequence diagram, a diagram element the text never mentions, a screen state with no wireframe, an error path shown in one place and not the other, or a container with no data store where the text implies persistence. You may review a wireframe's content only if you can view the image, and then it is your judgment, not a structural finding.
2. Run `eil status --json` and read the challenges already recorded on this stage. **A challenge a person has rejected or deferred is a standing constraint**: do not raise the same point again, and do not silently work against it. Treat an answer to a challenge as established.
3. For each new finding run `eil challenge add <stage> --target <item id or section> --text "<a specific, actionable statement of the gap>" --json`. Be specific: name what is missing or contradicted and where. If the helper refuses it as `duplicate-of-closed`, that point is already settled; leave it.
4. Present the challenges to the human. **The human answers**: they accept it (the content is changed), reject it (with a reason) or defer it (accepting the risk). The human may answer several at once, by id or by saying "accept all"; record each answer with its own `eil challenge answer <CH-id> --response accepted|rejected|deferred --by "<their name>" [--reason "<their words>"]` call, only for what they have actually given in this conversation. **Never answer a challenge yourself**, never pick a response on their behalf, and never write the reason for them. When an accepted challenge is fixed in the human's own dictated words, write it untagged with `(decided: CH-id)` rather than `[ai-draft]`.
5. While any challenge is open the stage cannot be approved. Say so, and list them.

## Rules

- You never record an approval, edit the `assessment`, `comprehension` or `approval` regions by hand, or answer an open question or a challenge on the human's behalf.
- Do not offer to approve until the gate is met and the comprehension check has been taken on this version.
- Once you know the confirming person's name in this conversation, reuse it for every `--by` this session without asking again, unless the human names someone else.
