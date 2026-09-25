<!--
  STAGE 7 OF THE DEFINITION PIPELINE: Did we achieve it?

  This document records evidence and nothing else. It never says the story is complete: that is
  the Completion stage, and a person's decision. It is not approved by a person.

  Gate: VER-G01 to VER-G06 (`eil check --stage verification`).

  - One row for every requirement, functional requirement and approved artefact (diagram or
    wireframe), as an `EVD` item that traces to what it verifies and carries a status:

      **EVD-001**: Import test flags the duplicate (traces: FR-001, T001) (status: verified) (code: PR#12)
      Kind: automated
      Evidence: tests/scenario/test_import.py::test_flags_duplicates

    A row's status is verified, failed, unverified or excepted. A verified or failed row names its
    Kind (automated or manual) and its Evidence. Suits-the-kind evidence: a screenshot review for a
    wireframe, a schema or migration comparison for an ER diagram, an integration or end-to-end
    trace for a sequence diagram, conformance evidence or an exception for a container or component.
  - An exception (anything not verified, or an accepted deviation from the design) records who
    accepted it and why:

      **EVD-009**: Load test deferred (traces: NFR-001) (status: excepted)
      Accepted by: Ada Dev
      Reason: the performance environment is not ready until next sprint

  - List every open task under Open Tasks. Do not hide one.
  - Tag any text the AI wrote with [ai-draft] until a human has reviewed it.
-->

# Verification: {{title}}

## Automated Evidence

<!-- Rows whose Kind is automated: test results, build results, static analysis, security scans, linting, type checking. -->

## Manual Evidence

<!-- Rows whose Kind is manual: reviews, screenshots, walkthroughs, with a reference to where the evidence is kept. -->

## Exceptions

<!-- Rows with status excepted or unverified, each with Accepted by and Reason. -->

## Failed Evidence

<!-- Rows with status failed. -->

## Acceptance Criteria

<!-- How each acceptance criterion of the Functional Specification was checked, by functional requirement id. -->

## Open Tasks

<!-- Every task of the task list that is not done, by id (`T004`). Say "None." only if there are none. -->

## Not applicable

<!-- Sections removed from this document, each with its reason. -->

## Challenges

<!-- Recorded by `eil challenge`. -->

## Overrides

<!-- Recorded by `eil override`, each naming who, what and why. -->

## Quality Assessment

<!-- eil:begin assessment -->
<!-- eil:end assessment -->
