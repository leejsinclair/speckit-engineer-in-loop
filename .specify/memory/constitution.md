<!--
Sync Impact Report
Version change: (unratified template) -> 1.0.0 -> 1.1.0 (same day)
1.1.0 (MINOR): Principle I widened into two tiers after /speckit-analyze finding D1 showed the
  original wording ("no prompt rule without a helper check") contradicted the design, which relies
  on prompt-only behavioural rules (research D-15). Nothing compliant with 1.0.0 becomes
  non-compliant. Workflow bullet on pull requests updated to match.
Modified principles: I (two tiers); II and III unchanged
Added principles: I. Enforcement Lives in the Helper; II. Honest Attestation Limits;
  III. Test-First, No Runtime Dependencies
Added sections: Constraints of Record; Development Workflow and Quality Gates; Governance
Removed sections: the template's fourth and fifth principle slots (three principles chosen)
Deferred items: none. A fourth principle, "Humans decide, no gamification", was offered and not
  selected on 2026-09-25; it remains a constraint in specs/001-staged-definition-workflow/spec.md
  and can be added later as a MINOR amendment.
Templates reviewed: none modified (dependent commands read this file at runtime)
-->
# Engineer-in-the-Loop Constitution

## Core Principles

### I. Enforcement Lives in the Helper (NON-NEGOTIABLE)

Enforcement has two tiers.

**Tier 1, gates and records.** Any rule that decides whether an action proceeds, or that writes a
record (a gate, refusal, approval, fingerprint, alias, artifact check or comprehension record), MUST
be deterministic code in the `eil` helper, covered by a unit test. Command prompts and preset wraps
MUST only call the helper and act on its exit code. A gate, refusal or record that exists only as
prompt text is a defect.

**Tier 2, behavioural guidance.** An instruction that tells the AI how to behave where no
mechanical check is possible (for example: reword each retry, never turn an open question into an
assumption, never draw an export) MAY live in a prompt if all of the following hold:

- it is written as guidance and is not described anywhere as enforcement;
- it cannot by itself allow a gate to pass or produce a record the helper would accept;
- it is covered by a prompt contract test (a text check of the prompt) or by a probe in the human
  trial protocol.

Where the effect of guidance is observable in a file, the helper SHOULD check it (for example the
allowed keys of a comprehension record).

Rationale: AI following prose is probabilistic, so anything a reviewer must be able to rely on is
deterministic and rerunnable. Some of the process's value, such as asking a better question, cannot
be checked by code. Naming those rules, and testing or trialling each, keeps them honest without
pretending they are enforced.

### II. Honest Attestation Limits

Gates make a bypass detectable and a refusal mechanical. They MUST NOT be described as
tamper-proof, and no document, message or prompt may claim they are. The AI MUST NOT record an
approval; the human's own confirmation is recorded verbatim. Anything the helper cannot verify (a
Figma source changing after export, whether the person answering is the confirmer, whether an AI
judgment of understanding is right) MUST be stated as an attestation-level limit where the feature
is documented, and AI judgments MUST be labelled as the AI's.

Rationale: a governance tool that overstates its guarantees trains people to trust it beyond what it
does. Stating the limits is what keeps the recorded approvals meaningful.

### III. Test-First, No Runtime Dependencies

Tests MUST be written and seen to fail before the code that satisfies them. The helper MUST run on
the Python 3.11+ standard library alone; a runtime dependency requires an amendment to this
constitution. `pytest` is the only development dependency. Every determinism requirement in
`contracts/cli.md` MUST have a unit test, and every installation and resolution assumption MUST have
a contract test against a scratch Spec Kit project.

Rationale: the helper is installed into other people's repositories and runs in their CI. Adding no
dependency keeps installation trivial, and tests written first are the only proof the enforcement
in Principle I works.

## Constraints of Record

- The feature's decided **Constraints on the Solution** in
  `specs/001-staged-definition-workflow/spec.md` bind the implementation: nine documents and exactly
  three aliases, no edit to Spec Kit or project files at install, state only in project files, hard
  gates with a recorded override, and no gamification.
- The helper MUST NOT render diagrams or call any network service (research D-21). It parses text and
  hashes files.
- Removal of the preset and extension MUST leave every recorded document and export in place.

## Development Workflow and Quality Gates

- The order of work in `specs/001-staged-definition-workflow/tasks.md` is binding where it states a
  checkpoint. The C-03 and C-05 risk checks MUST pass and be recorded before any story work is built
  on them.
- `/speckit-analyze` MUST be run after `tasks.md` changes and before implementation begins.
  A conflict with this constitution is CRITICAL and is fixed in the spec, plan or tasks, never by
  reinterpreting a principle.
- Each pull request description MUST state which principles it touches, confirm that no gate,
  refusal or record exists only in a prompt, and name the contract test or probe for each new
  behavioural rule added to a prompt (Principle I).
- A change to a contract file (`contracts/*.md`) MUST land in the same pull request as the tests
  that pin it.

## Governance

This constitution supersedes other practices for this repository. Amendments are made only with
`/speckit-constitution`, recorded in the Sync Impact Report, and approved by the repository owner.
Versioning follows semantic versioning: MAJOR for removing or redefining a principle, MINOR for
adding a principle or section or materially widening guidance, PATCH for clarification. Compliance
is reviewed at each `/speckit-analyze` run and in each pull request. Complexity that departs from a
principle MUST be justified in the plan's Complexity Tracking table before it is built.

**Version**: 1.1.0 | **Ratified**: 2026-09-25 | **Last Amended**: 2026-09-25
