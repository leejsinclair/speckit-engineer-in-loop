<!--
  STAGE 2 OF THE DEFINITION PIPELINE: WHAT must the system do?

  Gate: FUN-G01 to FUN-G16 (the Functional quality gate). Run `eil check --stage functional`.
  Approval: one recorded confirmation from the developer (or a person named in eil-config.yml),
  after the comprehension check has been taken on this version (`/speckit-eil-comprehend`).

  - Describe behaviour, not implementation. "Store it in PostgreSQL" belongs in the Technical stage.
  - Every functional requirement traces to an approved requirement or use case.
  - Tag any text the AI wrote with [ai-draft] until a human has reviewed it.
  - A section that does not apply is removed and listed under "Not applicable" with a reason.
-->

# Functional Specification: {{title}}

## Requirements Traceability

<!-- Which requirements each functional requirement satisfies, at a glance. The gate reads the `(traces: ...)` clauses on the items themselves. -->

## Actors

<!-- Everyone and everything that interacts with the capability: `- **Data Analyst**: reviews flagged duplicates`. Users, administrators, internal or external systems, scheduled processes, AI agents. Sequence diagrams below may name only these and the System. -->

## Functional Requirements

<!-- One item per behaviour, written "The system shall ...", each tracing to the requirements or use cases it satisfies: `**FR-001**: The system shall flag duplicate customers on import. (traces: REQ-001)`. -->

## Use Cases and Scenarios

<!-- For each use case from the Requirements (name it by its id, for example UC-001): preconditions, trigger, main flow, alternative flows, exception flows and expected outcome. -->

## Business Rules

<!-- Validation, eligibility, calculation, state-transition, ordering, uniqueness and retention rules, stated explicitly rather than implied by examples. -->

## Inputs

<!-- Required and optional inputs, formats, valid ranges, validation and sources. -->

## Outputs

<!-- Outputs, formats, required fields, expected states and consumers. -->

## State and Workflow

<!-- States, transitions, triggers, permitted transitions and terminal states. -->

## Validation

<!-- What is valid and invalid input. -->

## Error and Exception Behaviour

<!-- Invalid input, unavailable dependencies, unexpected conditions, partial failures, duplicate requests, conflicting operations. -->

## Security and Access Behaviour

<!-- Authentication, authorisation, data access, sensitive data handling. -->

## Audit and Compliance Behaviour

<!-- Audit trails, logging, retention, regulatory requirements, traceability. -->

## Non-Functional Requirements

<!-- Performance, availability, reliability, scalability, security, accessibility, maintainability, observability, recovery: `**NFR-001**: A 10 MB import completes within 60 seconds. (traces: REQ-001)`. -->

## Acceptance Criteria

<!-- Objectively verifiable conditions covering normal behaviour, important alternatives, significant errors and boundaries. -->

## Sequence Diagrams

<!--
  One system-level sequence diagram per use case, or a reason under "Not applicable" naming the use
  case (`- UC-002: a background job with no interaction to draw`). Participants are only the
  declared Actors and the System (as `participant System`); no container, component or technology.
  Show the main, alternative and exception flows. The item traces to its use case and to the
  functional requirements it shows.

  **ART-002**: Analyst reviews duplicates (traces: UC-001, FR-001)

  ```mermaid
  sequenceDiagram
    actor Analyst as Data Analyst
    participant System
    Analyst->>System: Upload customer file
    System->>Analyst: Flag duplicate matches
    alt no duplicates found
      System->>Analyst: Report a clean import
    end
  ```
-->

## Wireframes

<!--
  One wireframe per screen and per significant screen state (default, empty, loading, error),
  designed in Figma and exported as a static file (png, svg, pdf, jpg or jpeg). The AI lists each
  screen here as an ART line; a person exports it, and `/speckit-eil-artifact` records the export
  with the link to the exact Figma frame. The AI never draws or edits a wireframe.

  If the story has no user interface, remove this section and list "Wireframes" under Not
  applicable with the reason (for example: API only).

  **ART-003**: Duplicate review screen, default state (traces: FR-001, UC-001)
-->

## Not applicable

<!-- Sections and diagrams removed from this document, each with its reason: `- Wireframes: API only`, `- UC-002: no interaction to draw`. -->

## Challenges

<!-- Recorded by `eil challenge`. -->

## Overrides

<!-- Recorded by `eil override`, each naming who, what and why. -->

## Comprehension Check

<!-- The record of the check taken on this version: levels, outcomes, attempts and item ids only. Never a question, an answer, a hint or a score. -->

<!-- eil:begin comprehension -->
<!-- eil:end comprehension -->

## Quality Assessment

<!-- eil:begin assessment -->
<!-- eil:end assessment -->

## Approval

<!-- eil:begin approval -->
<!-- eil:end approval -->
