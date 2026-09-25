---
description: Assemble the AI Specification from the approved stages (how should the AI execute the approved design?).
argument-hint: "Anything the developer wants emphasised, such as files to reuse or patterns to follow"
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## Guard (engineer-in-the-loop)

If `.specify/extensions/eil/scripts/python/eil` does not exist, STOP. Tell the user to run `specify extension add eil` and then `specify preset add engineer-in-the-loop`, and do nothing else: continuing without the helper would let a story bypass its gates.

## What this stage is for

The AI Specification translates the **approved** Requirements, Functional and Technical Specifications into an implementation context that an AI coding agent can execute. It does not redesign anything and it decides nothing: it restates what a human has already approved, with a pointer back to where each thing came from. There is no human approval of this stage; the passing check is the gate, and a human review is offered. Every gate below is decided by the `eil` helper, not by you.

Every call below is `python3 .specify/extensions/eil/scripts/python/eil <subcommand> --json`. **Stop on any non-zero exit** and show the helper's `refusals` (code, message, fix). Exit 3 means there is no governed story: offer `/speckit-eil-requirements`.

## Steps

1. **Synchronise**: run `eil sync --json`.
2. **Start the stage**: run `eil stage-init ai-spec --json`. It is refused (`stage-not-approved`) until Requirements, Functional and Technical all carry a current approval; do not work around that. It creates `s04-ai-spec.md` and `spec.md` as a link to it. If `s04-ai-spec.md` already exists, continue from it.
3. **Read** the approved `s01`, `s02` and `s03`, and `s04-ai-spec.md`. Read the existing code the design touches.
4. **Assemble only from the approved stages.** Under each section of the template write items, one per line: `**AIS-001**: the instruction, stated for the agent (traces: FR-001, DEC-004)`.
   - Every item traces to at least one approved `REQ`, `UC`, `FR`, `NFR`, `DEC` or `ART`. The check reports any item without a source, any trace to something that is not approved, and any text outside an item.
   - **Do not write anything without a source.** If you find something the approved stages do not say (a missing edge case, an unstated constraint, a decision nobody made), do not fill it in: raise it as a challenge with `eil challenge add`, or put it to the human as an open question, and leave it out. The human decides; you execute. Never introduce a functional or architectural decision here.
   - **Tag every passage you write with `[ai-draft]`.** A person removes the tag once they have reviewed the text.
   - `Existing Code` and the optional `Agent Guidance` may name files, patterns and commands from the repository; each still needs an item tracing to the requirement or decision it serves.
5. **List the artefacts the agent must read** under `Artefacts in Scope`, one `AIS` item per approved `ART`, tracing to its id: `**AIS-013**: Read the container view before changing the API. (traces: ART-004)`. **Draw no diagram of your own** here: the approved Mermaid diagrams are directly readable, and a wireframe is read from its export. Any wireframe, ER diagram or technical sequence diagram you list must later be covered by a task.
6. **Check**: run `eil check --stage ai-spec --json` and fix what the code found. The gate is source-traceability, no pending clarification answer, and no listed artefact changed since its stage was approved. Re-run until it is met.
7. **Report** the result, every `[ai-draft]` tag, every challenge you raised and every artefact that changed since approval. Offer a human review of the document, and say that `/speckit-plan` can start once the check passes.
8. **Finish**: run `eil sync --json`.

## Rules

- You never record an approval or edit the `assessment` region by hand, and you never answer a challenge on the human's behalf.
- A clarification answer you collect later is written as a pending item and carried upstream with `/speckit-eil-resolve`; it is not a source until then.
