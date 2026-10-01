<!--
  STAGE 8 OF THE DEFINITION PIPELINE: Are we satisfied?

  Gate: CMP-G01 to CMP-G05 (`eil check --stage completion`).
  Approval: one recorded confirmation from the developer (or a person named in eil-config.yml) that
  the evidence was reviewed. It is refused while the Verification document is missing, or while a
  requirement or approved artefact is unverified without an exception.

  - No new requirements, decisions or diagrams here: this summarises what the other stages hold.
  - Diagram Currency has a line only for the artefacts implementation touched (`eil status` lists
    them under diagram_currency), and one `- untouched: ART-001, ART-002, ...` line for the rest:
      - ART-004: current
      - ART-007: deviation, accepted by Ada Dev, because the index was renamed in review
      - untouched: ART-001, ART-002, ART-003
    A deviation is also listed under Accepted Deviations, with who accepted it and why. A deviation is
    only for a document that intentionally keeps describing a future target; a difference accepted
    because the code is right is a correction (`eil correct`), not a deviation.
  - Tag any text the AI wrote with [ai-draft] until a human has reviewed it.
-->

# Completion: {{title}}

## Completion Status

<!-- Complete, or what remains. This is the person's statement, made with their approval. -->

## Implementation Summary

<!-- What was built, briefly. -->

## Requirements Satisfied

<!-- Each requirement and how it was satisfied, by id. -->

## Outstanding Issues

<!-- Anything still open, including open tasks and accepted risks. -->

## Accepted Deviations

<!-- Each deviation from the approved design, including any artefact deviation, with who accepted it and why. -->

## Relevant Technical Decisions

<!-- The decisions that shaped the result, by DEC id. -->

## Verification Summary

<!-- The result of the Verification document in a few lines: what is verified, failed, excepted. -->

## Deployment Status

<!-- Where and when it was deployed, or that it has not been. -->

## Documentation and Support Implications

<!-- Runbooks, user documentation, monitoring and support processes that change. -->

## Diagram Currency

<!-- One line per touched ART: `- ART-004: current` or `- ART-007: deviation, accepted by NAME, because REASON`, and `- untouched: ART-001, ART-002, ...` for the rest. -->

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

## Approval

<!-- eil:begin approval -->
<!-- eil:end approval -->
