---

description: "Task list template for feature implementation"
---

<!--
  STAGE 6 OF THE DEFINITION PIPELINE: What work is required?

  This document is `tasks.md` as Spec Kit sees it (an alias of this file).

  - Every task line ends with `(traces: AIS-###)`, the item of the AI Specification it carries out
    (or an approved decision, `DEC-###`). A task with no source is flagged.
  - A task that builds a screen, a schema or a technical flow also cites the artefact it implements,
    for example `(traces: AIS-014, ART-007)`. Every wireframe, ER diagram and technical sequence
    diagram listed in the AI Specification must be reached by at least one task.
  - A task must not introduce architecture that the approved design does not contain. Raise it as a
    challenge instead.
  - Gate: TSK-G01 to TSK-G03 (`eil check --stage tasks`). The task list is not approved by a person.
  - Keep the sections below the last phase (Not applicable, Challenges, Overrides, Quality Assessment).
-->

# Tasks: [FEATURE NAME]

**Input**: Design documents from `/specs/[###-feature-name]/`

**Prerequisites**: plan.md (required), spec.md (the AI Specification), research.md, data-model.md, contracts/

**Tests**: Include test tasks only where the AI Specification's Testing Requirements ask for them.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description (traces: AIS-###)`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions
- End every task with `(traces: AIS-###)`

## Phase 1: Setup (Shared Infrastructure)

<!--
  Sample task lines, for illustration only. Replace them with real tasks; do not keep these.

  - [ ] T001 Create project structure per implementation plan (traces: AIS-004)
  - [ ] T002 [P] Configure linting and formatting tools (traces: AIS-012)
-->

## Phase 2: Foundational (Blocking Prerequisites)

<!--
  Core infrastructure that must be complete before any user story:

  - [ ] T003 Add the DUPLICATE_MATCH migration in migrations/001.sql (traces: AIS-014, ART-007)
-->

## Phase 3: User Story 1 - [Title] (Priority: P1) 🎯 MVP

<!--
  **Goal**: what this story delivers.
  **Independent Test**: how to verify it on its own.

  - [ ] T004 [P] [US1] Create the worker in src/worker/matcher.py (traces: AIS-003)
-->

## Phase N: Polish & Cross-Cutting Concerns

<!--
  - [ ] T099 [P] Run the quickstart validation (traces: AIS-008)
-->

## Not applicable

<!-- Sections removed from this document, each with its reason. -->

## Challenges

<!-- Recorded by `eil challenge`. -->

## Overrides

<!-- Recorded by `eil override`, each naming who, what and why. -->

## Change Log

<!-- eil:begin changelog -->
<!-- eil:end changelog -->

## Record

<!-- eil:begin provenance -->
<!-- eil:end provenance -->

## Quality Assessment

<!-- eil:begin assessment -->
<!-- eil:end assessment -->
