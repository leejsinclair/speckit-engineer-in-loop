# Changelog

All notable changes to this project are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses semantic versioning.

## [Unreleased]

### Added

- Release workflow: pushing a `v*` tag builds the extension and preset zips and attaches them to a GitHub release; `tools/stage.py --tag` refuses a tag that does not match the manifest versions. Added a CI workflow (lint and unit tests).
- Numbered command names that match the document numbers: `/speckit-eil-0-status`, `-1-requirements`,
  `-2-functional`, `-3-technical`, `-4-ai-spec`, `-5-plan`, `-6-tasks`, `-7-verify` and `-8-complete`. They are
  Spec Kit aliases (or, for plan and tasks, thin commands that run `/speckit-plan` and `/speckit-tasks`); the
  original names still work. The status report and the README use the numbered names.
- `/speckit-eil-next`, which does the single next step when it is drafting or checking and stops at every
  human decision. `eil status --json` gains `next_action` (`kind`, `stage`, `command`, `message`), so the
  choice is made by the helper and not by the AI.

## [0.1.0]

First release: a Spec Kit preset (`engineer-in-the-loop`) and companion extension (`eil`) that turn a story
into an implementation-ready package through eight gated stages.

### Added

- The `eil` helper (Python 3.11+, standard library only): content fingerprints that ignore formatting,
  quality gates as data (Requirements 14, Functional 16, Technical 19, AI Specification 5, Plan 2, Tasks 3,
  Verification 6, Completion 5 criteria), approvals that record a named person's own words, per-criterion
  overrides, challenges (open, accepted, rejected, deferred, conflict), abbreviation, derived stage state,
  impact analysis by item, forward and reverse traceability, and a generated overview.
- Design artefacts: Mermaid diagrams (C4 context, container, component; sequence; ER) checked structurally
  and against each other, and Figma wireframes as registered exports with a SHA-256 and a link to the
  exact frame. Nothing is rendered.
- The comprehension check before approving Functional or Technical: deterministic target selection, a
  record that holds outcomes and item ids only, never a question, an answer or a score.
- `spec.md`, `plan.md` and `tasks.md` as aliases (a relative symlink, else a read-only mirror), refreshed
  and checked at the start of every command, so Spec Kit's own commands work on a governed story.
- Fifteen slash commands and seven wrapped Spec Kit commands (`specify` replaced; `clarify`, `plan`,
  `tasks`, `analyze`, `checklist`, `implement` wrapped), and nine document templates.
- Release archives (`tools/stage.py --archives`), and human trial protocols in `docs/trials.md`.

### Known limits

- Gates are attestation-level: a person editing files directly can bypass them, and it will be visible.
- Diagrams are read, never rendered; Mermaid's C4 support is experimental.
- The AI following its prompts is unproven until the trials in `docs/trials.md` are run.
- Linux only has been tested. OQ-001 (does `/speckit-checklist` stay meaningful over the AI Specification)
  is open.
- Know Your Spec's `after_specify` hook, if installed, still fires after this preset's `specify` and is
  harmless but noisy (research D-22).
