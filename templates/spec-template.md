<!--
  STAGE 4 OF THE DEFINITION PIPELINE: how should the AI execute the approved design?

  This document is `spec.md` as Spec Kit sees it (an alias of this file). It translates the approved
  Requirements, Functional and Technical Specifications into an implementation context for an AI
  coding agent. It does not redesign anything.

  Gate: AIS-G01 to AIS-G05 (`eil check --stage ai-spec`). This stage is not approved by a person: a
  passing check is the gate, and a human review is optional. Plan and Tasks refuse to start until it passes.

  - Every item is one line `**AIS-001**: text (traces: FR-001, DEC-004)` naming the approved
    requirement, functional requirement, decision or artefact it comes from. Text without a source is
    not written: it is raised as a challenge or a question.
  - Do not add a functional or architectural decision that is not in an approved stage.
  - Do not draw a diagram here. List the approved artefacts the agent must read, under Artefacts in
    Scope, as items tracing to their `ART` ids.
  - An answer collected by /speckit-clarify is written as an item tagged [pending-clarification]
    until it has been carried to the earliest stage it affects (/speckit-eil-resolve).
  - A section that does not apply is removed and listed under "Not applicable" with a reason.
-->

# AI Specification: {{title}}

## Functional Requirements

<!-- The functional requirements to build, restated for the agent: `**AIS-001**: Flag duplicate customers on import. (traces: FR-001)`. -->

## Business Rules

<!-- The rules that govern behaviour, each traced to its functional requirement. -->

## Technical Decisions

<!-- The approved decisions, each with the constraint it imposes: `**AIS-003**: Analysis runs asynchronously in a worker. (traces: DEC-001)`. -->

## Architectural Constraints

<!-- Boundaries the agent must respect: what may depend on what, and where things live. -->

## Existing Code

<!-- Existing files, modules and patterns to reuse or follow, and those not to follow. If the story is wholly new, list this section under Not applicable. -->

## Interfaces

<!-- Endpoints, operations, messages and their contracts, from the approved design. -->

## Data Structures

<!-- Entities, fields, keys and relationships, from the approved design. -->

## Testing Requirements

<!-- What must be tested, at which level, and how each is verified. -->

## Security Requirements

<!-- Authentication, authorisation, secrets and sensitive-data rules the implementation must meet. -->

## Edge Cases

<!-- Known edge cases and the behaviour required for each. -->

## Explicit Exclusions

<!-- What must not be built or changed, from the approved scope. -->

## Implementation Constraints

<!-- Performance limits, compatibility, migration and rollout constraints. -->

## Artefacts in Scope

<!--
  The approved diagrams and wireframes the agent must read, each as an item tracing to its ART id.
  A wireframe, ER diagram or technical sequence diagram listed here must be covered by a task.

  **AIS-013**: Read the container view before changing the API. (traces: ART-004)
-->

## Agent Guidance

<!-- Optional. Relevant files and directories, existing patterns to follow, commands and tests to run, constraints on modification. Delete this section if unused. -->

## Not applicable

<!-- Sections removed from this document, each with its reason: `- Existing Code: a new component`. -->

## Challenges

<!-- Recorded by `eil challenge`. -->

## Overrides

<!-- Recorded by `eil override`, each naming who, what and why. -->

## Quality Assessment

<!-- eil:begin assessment -->
<!-- eil:end assessment -->
