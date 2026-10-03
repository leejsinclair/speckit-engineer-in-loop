# Changelog

All notable changes to this project are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses semantic versioning.

## [Unreleased]

### Changed: Proportionate Effort (feature 003)

Each entry names the human interactions it adds or removes, and their purpose (constitution Principle IV).

- **Change 8, story targeting** (US1, FR-001 to FR-006). `eil start` always points `.specify/feature.json`
  at the new story and reports the move (`pointer.previous`, `pointer.current`). Every subcommand is
  declared `writes` or `read-only`; every result names its `story` (text form: `Story <name>: `). A writing
  call whose story came from the pointer, or from nothing, is refused `ambiguous-story` before anything is
  touched when the story cannot be told for certain (no pointer and several stories, a pointer to a missing
  directory, or a pointer to a completed story while another is in progress). `eil start` on a branch that
  is neither a main branch (`main_branches`, default `main`, `master`) nor named for the new story is
  refused `unexpected-branch` until a person confirms (`--on-branch`, `--by`, `--reply`); the helper never
  creates or switches a branch.
  - Added: choosing the story, only when the target is ambiguous (decision).
  - Added: confirming an unexpected branch, one reply, only when it applies (decision).
  - Removed: naming the story on every call (was repetition).
- **Change 7, records out of the documents** (US2, FR-007 to FR-013, FR-037). Every JSON record
  (`approval`, `assessment`, `comprehension`, `provenance`) moves to one record file per story,
  `specs/<story>/eil-record.json` (sorted, two-space JSON). Each region in a document keeps one readable
  line ("Approved by Ada on 2026-10-02 (first approval): ..."). Fingerprints are unchanged, so no approval
  moves. `eil sync` migrates an existing story (idempotent); a document not yet migrated is read as before.
  A missing or malformed record file makes the approvals it held unverifiable (`approval-record-missing`,
  `malformed-record-file`), never valid. `eil show <stage> [--items IDS] [--section NAME]` prints a stage as
  a person reads it, with the review cue and without records; every stage command and wrap reads stages
  with it and never reads the record file. The overview gains a per-stage count of blocks needing review.
  - The `[ai-draft]` cue is no longer written into documents (amends 002 FR-046): it appears in `eil show`
    and the review lists, and `sync` strips existing tags. An agent's edit that matches text it wrote no
    longer fails because the helper appended a tag.
  - No interaction added or removed. The agent's context and the developer's reading are reduced.
  - Attestation limit: the record file is plain project text, exactly as the regions it replaces were; a
    hand edit is detectable, not prevented (R-25). A reader of a raw document no longer sees which
    paragraphs await review; the overview's count and `eil show` do (R-26).
- **Change 3, lists sized to the person** (US3, FR-014 to FR-018). `eil review list` returns a `mode`:
  `one-at-a-time` for at most `review.one_at_a_time_max` entries (default 8), `summary` above that, with
  `groups` by section and a deterministic `summary` per entry (an item's title or the first sentence, at
  most 120 characters). `review answer --entry KEY` stores one entry's answer in a review session in the
  record file, so a compacted conversation resumes at the next unanswered entry; `--rest` ("ok to the rest")
  accepts every remaining entry and records them as `unseen`. A partial session settles nothing; the last
  answer applies the session through the ordinary answer path. `review show` prints full text on request.
  Every acceptance records the `mode` it was given in. Each Actors, Dependencies, Not applicable, Inputs and
  Outputs section is one `§<Section>` entry.
  - Short lists: one reply per entry, with "ok to the rest" (validation).
  - Long lists: one reply on grouped summaries (validation); full text shown on request.
  - Restated and adopted blocks are never listed (awareness removed).
  - Each scaffolding section becomes one entry (validation).
  - Attestation limit: a summary-mode answer, or "ok to the rest", accepts text the person may not have
    read in full; the recorded `mode` and `unseen` say so (R-24).
- **Change 2, upgrade adoption** (US7, FR-023 to FR-025, SC-006). When an approval predates section-level
  records (no `section_fingerprints`) and its document changed since, every block the approval cannot be
  compared against is adopted as `adopted-pending` (status `settled-pending`): it needs no review, is on
  no inferred list and raises no `unreviewed-ai-content`. The stage's changes list gains one
  `legacy:<stage>` entry stating that the document changed since an approval the tool cannot compare;
  one reply to that list and `review confirm` re-sign the stage with `reached: re-signed-without-comparison`,
  shown wherever approvals are shown (the approval line, the overview, `status`, `trace --report`), and
  every `adopted-pending` block becomes `adopted`. `accept` no longer refuses such an approval. A judgment
  recorded before 002's per-criterion basis is kept while its document is unchanged (also under 001's
  fingerprint rule, which did not strip tags), instead of being dropped on the first check after upgrade.
  - Removed: re-review of unchanged approved blocks after upgrade (was validation; already approved).
  - Replaced: a full re-approval of a legacy approval, by one reply (approval), marked as given without
    a comparison.
- **Change 9, the helper does not get in its own way** (US9, FR-036 to FR-040). `eil blocks classify` is
  additive: a block left out keeps its recorded classification while unchanged, and an unknown key is
  returned under `skipped` with the section's current keys instead of failing the call (exit 2
  `nothing-classified` only when no key is known). The plan's own headings (`Change Log`, `Record` and
  every administrative heading) are never `plan-not-derivable`. The AI Specification, plan, tasks and
  verification gain the end state `reviewed`; after completion is approved, `status` reports `done` ("Story
  complete; approved by ... on ...") and never "Continue verification". Every prompt that raises a challenge
  shows `--severity` and says it is required.
  - No interaction added or removed. Removes retries, false trace clauses and a misleading next step.
- **Change 4, behaviour, not mechanism** (US5, FR-026 to FR-029). The Technical stage asks the developer only
  about choices with an observable effect, the scope or a trade-off, each with a recommended option, and
  records every other choice as a decision with `Owner: ai-decided` and a `Reason:`. The helper refuses an
  `ai-decided` decision without a reason (`ai-decided-without-reason`), always classifies it `inferred`, lists
  it on the stage's review list in its own group ("AI-decided decisions"), marks it `[ai-decided]` in `eil
  show`, and names it in the approval record (`ai_decided`) and the approval line. Rewriting its owner to a
  person surfaces it for review again. The Functional stage never asks about mechanism.
  - Removed: questions about implementation mechanism; each such choice is now validated in the existing
    one-reply review list (validation; was a decision).
  - Unchanged: questions about behaviour, scope and trade-offs, now with a recommended option (decision).
  - Attestation limit: whether a choice is observable is the AI's labelled judgement; it asks when unsure,
    and every `ai-decided` decision is put to a person on the list (R-23).
- **Change 5, comprehension respects what the person knows** (US6, FR-030 to FR-034).
  `eil comprehension plan --by <person>` leaves out that person's own decisions, established from the
  records (a settled DEC they own, or a `decided` block whose decision record names them); where nothing
  else is eligible the level is `own-decision`, naming the decision, and is recorded with that outcome
  (`not-own-decision` refuses it anywhere else). `eil comprehension waive --stage --by --reason` records every
  remaining level as `skipped`, `waived`, with the reason and the helper's fixed question. Approval records
  and the overview count `own-decision` beside `skipped`. The prompt shows each item (`eil show --items`)
  before its question, asks about behaviour, judges on meaning and re-reads before hinting.
  - Removed: questions about the person's own current decisions (was understanding).
  - Replaced: one skip per level, by one waiver with a reason (decision).
  - The item is shown before each question (no file to open).
- **Change 6, gaps found while drafting** (US8, FR-035). The Functional and Technical stage commands run
  `eil comprehension plan` before their first review list and check the items it names for silent,
  ambiguous or self-contradicting text, raising any gap as a challenge first. The comprehension pre-scan
  stays as the backstop.
  - Removed, where the drafting pass finds the gap: a second review round after late gaps (was validation).
- **Change 1, the small-story profile** (US4, FR-019 to FR-022). `eil profile set small --by --reason` and
  `eil profile withdraw --by --reason`, by a person allowed to authorise abbreviations. While the profile is
  in force: the Functional wireframe criterion (FUN-G15) is met by it and says so; entry to planning and
  task generation proceeds under an override of `unreviewed-ai-content` recorded with the profile (named,
  reasoned, shown wherever overrides are shown, withdrawn with it); the AI Specification, plan and tasks are
  reviewed as one `derived` list (`review list --stage derived`) and `enter implement` refuses until it is
  answered; comprehension asks `explain` and `apply`, recording the other levels not applicable with the
  profile as the reason. Approvals given under it record `profile: small`. The overview, `status` and
  `trace --report` show it. Prompts may propose it, labelled `AI assessment:`; only a person authorises it.
  - Added: one authorisation per story, with a reason (decision).
  - Removed under the profile: wireframe exports (was validation).
  - Three derived lists become one (validation). Comprehension is cut to two levels (understanding).
  - Measured on the reference story: 40% fewer developer replies from requirements to implementation
    (25 to 15), short of SC-005's 50% target; recorded in research.md and kept visible as a strict xfail.
- **Change 10, one-word approvals** (US10, FR-047 to FR-049; constitution 1.2.2). The helper holds one fixed
  approval question per approvable stage (`records.APPROVAL_QUESTIONS`), offers it as `next_action.question`
  in `status`, and records it beside the verbatim reply on `approve`; `review confirm` records its
  re-approval question the same way. The approval line reads, for example, `Approved by Ada on 2026-10-03
  (first approval): "ok" to "Approve the Functional Specification as the behaviour you require?"`. The branch
  confirmation and the comprehension waiver record their own fixed questions. The prompts ask the helper's
  question, accept "ok", "yes" or "approved" as given, and ask the name once per session.
  - Replaced: writing a sentence of attestation, by a one-word reply to a stated question (approval).
  - Removed: giving one's name at every approval (was repetition).

### Removed

- The `speckit.eil.amend` and `speckit.eil.review` prompt commands. Use `/speckit-eil-accept`. The `eil amend`
  and `eil review` helper subcommands are unchanged.

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
