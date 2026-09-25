<!--
  STAGE 1 OF THE DEFINITION PIPELINE: WHY are we doing this?

  Gate: REQ-G01 to REQ-G14 (the Requirements quality gate). Run `eil check` to evaluate it.
  Approval: one recorded confirmation from the developer (or a person named in the extension's
  eil-config.yml). The AI drafts and challenges; it cannot approve.

  - Describe the problem and the outcome. Do not prescribe an implementation.
  - Tag any text the AI wrote with [ai-draft] until a human has reviewed it. Approval is refused
    while a tag remains (unless a named override is recorded).
  - A section that does not apply is removed and listed under "Not applicable" with a reason.
  - Open questions are not assumptions. Never turn one into the other without a human decision.
-->

# Requirements: {{title}}

## Background

<!-- Context that led to the work: business or technical context, the current situation, existing problems, relevant history, and why the issue exists now. -->

## Problem Statement

<!-- Who or what is affected, what is happening, why it is a problem, and what happens if it is left unresolved. -->

## Desired Outcome

<!-- The outcome the organisation wants, as outcomes rather than implementation. One item per line: `**REQ-001**: the system detects duplicate customers on import`. -->

## Users and Stakeholders

<!-- One bullet per user, system, team, business stakeholder or external party: `- **Data Analyst**: reviews flagged duplicates`. Every one of them must appear in the system context diagram below. -->

## Use Cases

<!-- One item per significant use case, with its actor, goal, trigger and expected outcome: `**UC-001**: Analyst reviews a flagged duplicate (actor: ...; goal: ...; trigger: ...; outcome: ...)`. -->

## Scope

### In Scope

<!-- What this work will address. -->

### Out of Scope

<!-- What this work deliberately will not address. -->

## Constraints

<!-- Regulatory, security, architectural, technology, compatibility, budget, time or operational constraints. -->

## Dependencies

<!-- One bullet per system, service, team, data source, infrastructure item or other piece of work this depends on: `- **CRM**: the existing customer store`. Every system must appear in the system context diagram below. -->

## Risks

<!-- Known risks to achieving the desired outcome. -->

## Assumptions

<!-- Assumptions being made now. Validate them where practical. These are not open questions. -->

## Open Questions

<!-- One item per question that could materially affect the solution: `**OQ-001**: Keep customer history? (status: open) (material: yes)`. A material question must be resolved (`status: resolved`), or accepted by a named person (`status: accepted` with `(accepted-by: NAME)`), before approval. -->

## Success Criteria

<!-- Observable outcomes that show the problem is solved. -->

## System Context

<!--
  The system as one box, with the people and systems around it (C4 Level 1). Every person under
  Users and Stakeholders and every system under Dependencies must appear here, and every element
  says whether it is [existing], [new] or [changed]. No screens and no internals belong here.

  **ART-001**: System context (traces: REQ-001)

  ```mermaid
  C4Context
    Person(analyst, "Data Analyst", "[existing] Reviews flagged duplicates")
    System(platform, "Customer Platform", "[changed] Detects duplicates on import")
    System_Ext(crm, "CRM", "[existing] Customer store")
    Rel(analyst, platform, "Reviews duplicates")
    Rel(platform, crm, "Reads customers")
  ```
-->

## Not applicable

<!-- Sections removed from this document, each with its reason: `- Constraints: none for this spike`. -->

## Challenges

<!-- Recorded by `eil challenge`. -->

## Overrides

<!-- Recorded by `eil override`, each naming who, what and why. -->

## Quality Assessment

<!-- eil:begin assessment -->
<!-- eil:end assessment -->

## Approval

<!-- eil:begin approval -->
<!-- eil:end approval -->
