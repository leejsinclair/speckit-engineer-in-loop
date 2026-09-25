<!--
  STAGE 3 OF THE DEFINITION PIPELINE: HOW will the system do it?

  Gate: TEC-G01 to TEC-G19 (the Technical quality gate). Run `eil check --stage technical`.
  Approval: one recorded confirmation from the responsible developer (or a person named in
  eil-config.yml), after the comprehension check has been taken on this version
  (`/speckit-eil-comprehend`).

  - The developer owns the design. The AI may propose alternatives and challenge decisions; what is
    written as a decision is the developer's choice, and its owner is a person.
  - Every decision traces to the functional or non-functional requirements it serves.
  - Tag any text the AI wrote with [ai-draft] until a human has reviewed it.
  - A section or diagram that does not apply is removed and listed under "Not applicable" with a reason.
-->

# Technical Specification: {{title}}

## Technical Requirements

<!-- Requirements derived from the functional and non-functional requirements, the existing architecture, security, operations and platform constraints. -->

## Architecture

<!-- Components, services, boundaries, dependencies, communication, data flow and external systems. The container view below shows it. -->

## Component Design

<!-- For each significant component: responsibility, interfaces, dependencies, implementation constraints. The component views below show it. -->

## Data Design

<!-- Structures, entities, relationships, schema changes, indexes, ownership, lifecycle and migration. The data model below shows it; if no persistent data changes, list "Data Design" and "Data Model" under Not applicable with the reason. -->

## API and Integration Design

<!-- Endpoints, operations, request and response structures, authentication, authorisation, error responses, versioning, integration behaviour. -->

## Security Design

<!-- Trust boundaries, authentication, authorisation, secrets, encryption, sensitive data, auditability, threats. -->

## Error Handling and Resilience

<!-- Failures, retries, timeouts, partial failures, idempotency, concurrency, dependency failures, recovery. -->

## Observability

<!-- Logging, metrics, tracing, alerts, operational diagnostics. -->

## Performance

<!-- Expected volumes, latency, throughput, resource use, constraints. -->

## Testing Strategy

<!-- Unit, integration, contract, end-to-end, security, performance and migration tests, and what each one verifies. -->

## Deployment and Migration

<!-- Deployment sequence, infrastructure changes, database and data migration, backwards compatibility, feature flags, rollback, operational changes. -->

## Existing System Impact

<!-- Effects on existing components, APIs, databases, integrations, infrastructure, monitoring and support processes. -->

## Alternatives Considered

<!-- For each significant decision: the alternatives, their advantages and disadvantages, and why one was chosen. Not every idea, only the ones worth preserving. -->

## Risks and Trade-offs

<!-- Technical, architectural, operational and security risks, maintainability concerns, known limitations. Technical questions still open go here as `**OQ-001**: ... (material: yes)`; a material one blocks approval until resolved or accepted by a named person. -->

## Technical Decisions

<!--
  One item per significant decision. Every field is required; the owner is a person (the developer
  who decided), including when the AI proposed the option.

  **DEC-001**: Use asynchronous processing (traces: FR-001, NFR-001)
  Decision: Duplicate analysis runs asynchronously in a worker.
  Reason: A 10 MB import can exceed the synchronous latency limit.
  Rejected alternative: Analyse inside the import request.
  Trade-off: Results are not available to the caller straight away.
  Owner: Ada Dev
-->

## Container View

<!--
  C4 level 2. One container diagram of the system: deployable units, data stores, technology and
  communication. The external people and systems must match the system context in the
  Requirements, by name. Mark every element [existing], [new] or [changed] in its description.

  **ART-004**: Containers of the platform (traces: FR-001, DEC-001)

  ```mermaid
  C4Container
    Person(analyst, "Data Analyst", "[existing] Reviews duplicates")
    System_Ext(crm, "CRM", "[existing] Customer store")
    System_Boundary(platform, "Customer Platform") {
      Container(api, "Import API", "REST", "[existing] Accepts imports")
      Container(worker, "Duplicate Worker", "Python", "[new] Analyses duplicates")
      ContainerDb(db, "Customer DB", "PostgreSQL", "[existing] Customer records")
    }
    Rel(analyst, api, "Uploads files")
    Rel(api, worker, "Queues analysis")
    Rel(worker, db, "Reads and writes")
    Rel(api, crm, "Reads customers")
  ```
-->

## Component Views

<!--
  C4 level 3. One component diagram for each new or changed container, naming it as a
  Container_Boundary that is also in the container view; or a reason under "Not applicable" naming
  the container (`- Duplicate Worker: one module, nothing to show`). No level 4 (code).

  **ART-005**: Inside the duplicate worker (traces: FR-001, DEC-001)

  ```mermaid
  C4Component
    ContainerDb(db, "Customer DB", "PostgreSQL", "[existing] Customer records")
    Container_Boundary(worker, "Duplicate Worker") {
      Component(matcher, "Matcher", "Python", "[new] Compares customers")
      Component(results, "Result Store", "Python", "[new] Saves matches")
      Rel(matcher, results, "Hands matches to")
      Rel(results, db, "Writes")
    }
  ```
-->

## Sequence Diagrams

<!--
  One technical sequence diagram for each use case that crosses more than one container (or a
  reason under "Not applicable" naming the use case: `- UC-002: stays inside the import API`).
  Participants are elements of the container or component views only. The item cites the decision
  it illustrates (asynchronous processing, retries and idempotency, authentication, integration).

  **ART-006**: Asynchronous analysis (traces: UC-001, DEC-001)

  ```mermaid
  sequenceDiagram
    actor Analyst as Data Analyst
    participant API as Import API
    participant Worker as Duplicate Worker
    participant DB as Customer DB
    Analyst->>API: Upload file
    API->>Worker: Queue analysis
    Worker->>DB: Store matches
  ```
-->

## Data Model

<!--
  An ER diagram wherever persistent data is added or changed, with `(store: NAME)` naming the
  database of the container view that holds it. Indexes and migrations stay in the text above.
  If nothing persistent changes, list "Data Model" under Not applicable with the reason.

  **ART-007**: Duplicate match data (traces: DEC-001) (store: Customer DB)

  ```mermaid
  erDiagram
    CUSTOMER ||--o{ DUPLICATE_MATCH : "has"
  ```
-->

## Not applicable

<!-- Sections and diagrams removed from this document, each with its reason: `- Data Model: no persistent data changes`, `- UC-002: stays inside one container`, `- Duplicate Worker: one module`. -->

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
