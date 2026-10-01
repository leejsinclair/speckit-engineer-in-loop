# Changelog

All notable changes to this project are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses semantic versioning.

## [Unreleased]

### Added

- Proportionate revalidation (feature 002): fewer, better-explained requests for a developer's attention,
  and staleness that follows what actually changed.
  - Every request states its purpose (awareness, understanding, decision, validation or approval), and a
    person is not asked to reconfirm anything already established (constitution 1.2.0, Principle IV).
  - One reply per list: `eil review list` and `eil review answer` present inferred content, changes, tasks,
    evidence, low-severity challenges, unknown-currency content, diagram currency and unsettled challenges
    as a single list answered in one verbatim reply ("ok to all", "ok except ...", or a question).
  - Content blocks carry a hash and a class (restated, decided, inferred, adopted) in a new `provenance`
    region, and a generated `changelog` region records what changed and why. Both are excluded from the
    fingerprint. `[ai-draft]` is now a cue the helper renders from recorded status, never read as status.
  - Item-level staleness: changing one decision marks only the blocks, tasks and evidence that trace to it.
    `eil enter` is work-scoped and refuses only blocked work (`work-blocked`).
  - `/speckit-eil-accept` (`eil review confirm`): one sign-off re-signs an edited stage; if every change is
    covered by a recorded decision it is carried forward and marked so. `amend` and `review start|accept|finish`
    remain as aliases.
  - `/speckit-eil-correct` (`eil correct propose|open`): backwards corrections from implementation, with the
    corrected wording shown before it is applied and recorded verbatim (`CR-###`, `(decided: CR-###)`).
  - Challenge severity: a low-severity challenge is listed as outstanding and does not block approval.
    Anyone may raise a severity; only a configured confirmer may lower it, recorded with their name.
  - Review findings (`RF`) in `s07`, task snapshots, and evidence confirmed by finding the named test.
  - Existing stories are adopted on first `sync` (blocks recorded as adopted, no state changes); an
    upgrade never loosens a gate silently (R-20).
  - Attestation limits, stated where the feature is documented: restated-content fidelity is by hash only
    (FR-014); evidence confirmation finds a test, it does not run it (FR-035); a reply is mapped to flags
    with only obvious mismatches refused (D-36); correction wording is recorded as given, and the helper
    cannot tell who wrote it (D-38); a hand-edited `provenance` region is an attestation-level limit (R-21).
  - Contract deltas folded into `specs/001-staged-definition-workflow/contracts/`, including the three
    places the helper edits human content (`review accept`, `resolve`, `[ai-draft]` cue rendering).
  - Interaction count (SC-001): the harness in `tests/scenario/test_interaction_count.py` replays the same
    edits under the 001 baseline and this code. On the current replay the number of non-decision,
    non-first-approval interactions is **not** reduced (5 under 001, 5 under 002), so the 60% target is
    not met; the test is marked `xfail` until it is.
- Release workflow: pushing a `v*` tag builds the extension and preset zips and attaches them to a GitHub release; `tools/stage.py --tag` refuses a tag that does not match the manifest versions. Added a CI workflow (lint and unit tests).
- Numbered command names that match the document numbers: `/speckit-eil-0-status`, `-1-requirements`,
  `-2-functional`, `-3-technical`, `-4-ai-spec`, `-5-plan`, `-6-tasks`, `-7-verify` and `-8-complete`. They are
  Spec Kit aliases (or, for plan and tasks, thin commands that run `/speckit-plan` and `/speckit-tasks`); the
  original names still work. The status report and the README use the numbered names.
- `/speckit-eil-next`, which does the single next step when it is drafting or checking and stops at every
  human decision. `eil status --json` gains `next_action` (`kind`, `stage`, `command`, `message`), so the
  choice is made by the helper and not by the AI.
- Cut the re-approval churn a human-decided edit used to cost (dogfooding feedback):
  - The document fingerprint is now neutral to `[ai-draft]` tag removal outside an HTML comment, so
    reviewing and untagging a human's own words no longer invalidates an assessment, comprehension
    record or approval comparison. (A first cut stripped the substring unconditionally; every shipped
    template's own header comment says the word without it being a tag, so every stage document's
    fingerprint moved on upgrade with nothing actually edited. Found via dogfooding the fix itself and
    corrected before release — see `_strip_ai_draft` in `fingerprint.py` and research D-23.)
  - A new `(decided: CH-###|OQ-###|AIS-###|RVW-###)` clause marks text copied verbatim from a recorded
    human decision — an accepted challenge, a resolved open question, a carried clarify answer, or an
    `eil review` acceptance (below) — written untagged instead of `[ai-draft]`. The helper checks the
    citation is real and in an eligible state.
  - `eil amend <stage> --from <ids> --by <name> --attestation <text>` re-signs a stage's approval when
    it is `needs-re-review` and every item that changed since the last approval — its own edit, or an
    upstream one propagating in — carries a matching `(decided: ...)` clause, every changed section is
    covered by an `eil review` acceptance, and the comprehension check for the version is current. It
    is visible in the overview and every report exactly as an override is.
  - `/speckit-eil-review-changes` (`eil review start`/`accept`/`finish`) walks the human through every
    item and section changed since a stage's last approval, one at a time, and records each "ok" as the
    citation itself — an item's line gets `(decided: RVW-###)` and its `[ai-draft]` tag removed, together,
    as one helper action, never an AI hand-edit trusted after the fact. Finishing re-signs the approval
    from those acceptances, sharing `amend`'s coverage core, visibly marked `reviewed_change_by_change`.
  - Downstream re-review is now item-level, not document-level: a stage becomes `needs-re-review` only
    when one of its own recorded `upstream_items` actually changed, tracked per stage so a re-approval
    elsewhere in the chain does not erase the signal. An upstream change that affects nothing traced
    leaves the stage `approved`, with a non-blocking `note`.
  - The comprehension check taken for a re-approval is now a **delta** check: only the changed items are
    eligible, capped at two questions, and skipped entirely (recorded `not-applicable` with the reason,
    asking nothing) when every change is a recorded human decision. `eil amend`/`eil review finish` now
    complete this check themselves rather than silently skipping it, so it never blocks silently either.
  - A judgment criterion's recorded verdict is now voided only by an edit to the sections it actually
    reads (`Criterion.headings`), not by any edit anywhere in the document — a real bug, not just
    friction: four criteria used to be re-judged for an edit none of them read.
  - `/speckit-eil-comprehend`'s pre-scan is now explicitly a backstop for the stage command's own
    end-of-drafting challenge sweep, not a second full pass.
  - Several commands now accept a batched reply covering several open challenges at once, reuse a
    confirmer's name for the rest of the session once given, and `/speckit-eil-approve` accepts an
    attestation already given inline in its arguments without asking again.

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
