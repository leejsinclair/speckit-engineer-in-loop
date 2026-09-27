---
description: Capture, challenge and gate the developer-owned Technical Specification (how will we build it, and why this way?).
argument-hint: "Anything the developer wants emphasised, already decided or already ruled out"
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## Guard (engineer-in-the-loop)

If `.specify/extensions/eil/scripts/python/eil` does not exist, STOP. Tell the user to run `specify extension add eil` and then `specify preset add engineer-in-the-loop`, and do nothing else: continuing without the helper would let a story bypass its gates.

## What this stage is for

The Technical Specification answers **how** the approved behaviour will be built and **why this approach is appropriate**. It is deliberately implementation-oriented, and **the developer owns it**. You may propose alternatives, identify risks and challenge decisions, and you draft the documentation, but a technical decision is the developer's, never yours. Every gate below is decided by the `eil` helper, not by you.

Every call below is `python3 .specify/extensions/eil/scripts/python/eil <subcommand> --json`. **Stop on any non-zero exit** and show the helper's `refusals` (code, message, fix). Exit 3 means there is no governed story: offer `/speckit-eil-requirements`.

## Steps

1. **Synchronise**: run `eil sync --json`.
2. **Start the stage**: run `eil stage-init technical --json`. It is refused (`stage-not-approved`) until the Functional Specification carries an approval; do not work around that. If `s03-technical-spec.md` already exists, continue from it.
3. **Read** the approved `s01-requirements.md` and `s02-functional-spec.md`, and `s03-technical-spec.md`. The template's comments say what each section and diagram holds.
4. **Capture the decisions with the developer, one at a time.** For each significant choice (asynchronous processing, retries and idempotency, authentication, integration, storage and so on) ask the developer what they decide, and write it as a `DEC` item with **all** of these fields: the decision, the reason, the rejected alternative, the accepted trade-off and the owner.

   ```text
   **DEC-001**: Use asynchronous processing (traces: FR-001, NFR-001)
   Decision: ...
   Reason: ...
   Rejected alternative: ...
   Trade-off: ...
   Owner: <the developer>
   ```

   - **Propose, do not decide.** You may propose alternatives with their advantages and disadvantages and say which you would choose and why. What is written is the developer's choice, even when it is the option you argued against; a proposal the developer declines is recorded as the rejected alternative, with their reason. Never write a decision the developer has not made.
   - **The owner is the developer** who decided, including when the option came from you. Never write an owner that is you or another AI.
   - Every decision traces to at least one `FR` or `NFR` it serves. If you find behaviour the decisions do not serve, or a decision no requirement needs, raise a challenge.
   - **Tag every passage you write with `[ai-draft]`.** A person removes the tag once they have reviewed the text. A decision is not tagged once the developer has stated it in their own words.
   - **Human-decided provenance.** When other text you write (outside a `DEC`'s own fields) is copied verbatim from a decision already made — an accepted challenge, a resolved open question, or a clarify answer carried by `/speckit-eil-resolve` — write it **untagged**, with `(decided: CH-004)`, `(decided: OQ-002)` or `(decided: AIS-007)` instead of `[ai-draft]`, naming the exact id.
   - A question the developer cannot answer yet is an open question (`**OQ-###**: ... (status: open) (material: yes)`), never an assumption. A material one blocks approval until it is resolved or accepted by a named person.
5. **Fill the sections** (technical requirements, architecture, component design, data design, API and integration design, security design, error handling and resilience, observability, performance, testing strategy, deployment and migration, existing system impact, alternatives considered, risks and trade-offs) from the decisions and from what the developer supports. Where you would have to guess, ask.
6. **Draw the diagrams as Mermaid text in the document**, each as an `ART` item followed by its `mermaid` block, tracing to what it shows. The helper checks them for consistency; it never renders them.
   - **Container view** (`C4Container`): the deployable units, data stores, technology and communication. Its external people and systems must be the same, by name, as in the system context of `s01`. Mark every element `[existing]`, `[new]` or `[changed]` in its description.
   - **Component view** (`C4Component`) for each new or changed container: a `Container_Boundary` naming a container of the container view. If a container has nothing worth showing, list it under `## Not applicable` by name with the reason.
   - **Technical sequence diagram** for each use case that crosses more than one container: participants are only elements of the container and component views, and the item cites, in its `traces`, the `DEC` it illustrates. If a use case stays inside one container, list its id under `## Not applicable` with the reason.
   - **ER diagram** wherever persistent data is added or changed, with `(store: NAME)` on its `ART` line naming a `ContainerDb` or `SystemDb` of the container view. If nothing persistent changes, list "Data Model" (and "Data Design") under `## Not applicable` with the reason.
   - No C4 level 4, no wireframe, and no diagram in another notation: an image from another tool is attached through `/speckit-eil-artifact` and is not structurally checked.
7. **Check the gate**: run `eil check --stage technical --json`, fix what the code found (missing decision fields, an inconsistency between diagrams, a diagram that does not parse) and re-run. An inconsistency is fixed by correcting the diagram or the text, never by hiding it; if the developer wants to accept one, that is `/speckit-eil-override` and theirs alone.
8. **Judge the judgment criteria.** For each criterion with `"kind": "judgment"` decide honestly whether the document meets it, and write a judgments file **outside the repository**:

   ```json
   {"stage": "technical",
    "judgments": [{"id": "TEC-G01", "status": "met", "reason": "one sentence"}],
    "assessment": {"ambiguity": [], "missing": [], "contradictions": [], "unsupported_assumptions": [], "untestable": []}}
   ```

   Include an entry for every judgment criterion, and fill the five lists with the specific problems you find, including where the design leaves a functional requirement unserved or contradicts the functional text. Run `eil check --stage technical --judgments <file> --json`. Your verdicts are labelled as the AI's, apply only to the exact text you assessed, and cannot make a code-decided criterion met.
9. **Challenge** the design the way a reviewer would: what happens on retry, on a duplicate request, when a dependency is down, when two requests arrive together, and which requirement is unserved. Record each as a challenge for the developer to answer; never answer one yourself.
10. **Report** the gate result, every remaining `[ai-draft]` tag and open question, and any inconsistency. When the gate is otherwise met, offer `/speckit-eil-comprehend`: the developer takes the comprehension check on this version before approving.
11. **Finish**: run `eil sync --json`.

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
