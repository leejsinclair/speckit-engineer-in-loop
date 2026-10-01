---
description: "Task list for Proportionate Revalidation (refinement of the Engineer-in-the-Loop workflow)"
---

# Tasks: Proportionate Revalidation

**Input**: Design documents from `specs/002-proportionate-revalidation/`

**Prerequisites**: plan.md, spec.md, research.md (D-30 to D-44), data-model.md, contracts/ (cli.md, document-format.md, commands.md deltas), quickstart.md (B-19 to B-28)

**Tests**: Included and written first. Constitution Principle III requires it, and the plan names determinism requirements 22 to 37, scenarios B-19 to B-28 and prompt contract tests. Each test task is run and **seen to fail** before its implementation task starts.

**Organization**: Tasks are grouped by the spec's user stories, US1 to US6. The review-list core (list, digest, answer, authority) is shared by every story, so it is in the Foundational phase. Each story then adds its own list kind.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (a different file, and no dependency on an incomplete task).
- **[Story]**: US1 to US6.
- Paths are relative to the repository root. `eil/` means `extensions/eil/scripts/python/eil/`.
- `cli.py`, `gates.py`, `records.py`, `handoff.py`, `extension.yml` and `tests/helpers/package.py` are shared by many tasks, so tasks that edit them are never [P] with each other.

---

## Phase 1: Setup

**Purpose**: A clean baseline, the fixture and the scaffolding every later test uses.

- [X] T001 Commit the prerequisite work already in the tree as its own change: D-23 to D-29 helper code and tests, `speckit.eil.review.md`, constitution 1.2.1 and the 001 spec amendments. Suggested message: "feat: cut re-approval churn (D-23..D-29); docs: amend constitution to v1.2.1". Confirm that `pytest` passes before and after. Tag the commit `eil-001-baseline`: T083 measures the 001 interaction baseline there (research D-43). This feature builds on that code.
- [X] T002 Create the reference-story fixture builder in `tests/fixtures/reference_story.py`. It builds a package approved through tasks with 4 REQ, 3 UC, 12 FR, 5 DEC (DEC-001 to DEC-005), 8 ART, AIS items tracing to them, a plan whose sections trace to DECs, and tasks T001 to T012 tracing to AIS/DEC. T001 to T006 are ticked with `(code: …)`, and the s07 EVD rows are included. Build it on `tests/helpers/package.py` (quickstart prerequisites).
- [X] T003 [P] Add a `reference_story` pytest fixture and an `eil_json(args)` helper, which returns the exit code and parsed JSON, to `tests/conftest.py`.
- [X] T004 [P] Add `provenance` and `changelog` region support and `RF` items to the story-package builder in `tests/helpers/package.py`, so tests can write documents with pre-recorded blocks, acceptances and corrections.

---

## Phase 2: Foundational (blocking prerequisites)

**Purpose**: Content blocks, the new regions, adoption on upgrade and the one-reply list core. Every story depends on these.

**⚠️ No story work starts until this phase's checkpoint passes.**

### Tests first

- [X] T005 [P] Write `tests/unit/test_content.py` for determinism requirements 22 and 23. Cover the FR-039 block kinds: an item with continuation lines, DEC fields over blank lines, an EVD row, a task line, a plan heading with `(traces:)`, a table, a fence, an ART with its attachment, a prose run, and headings, comments and regions excluded. A rewrapped or whitespace-only change leaves hashes unchanged, and an inserted paragraph changes only itself. Numbered blocks have the same hash as `trace.item_hash`. Test the prose `(traces:)` clause on a block's last line and the key forms (`id`, `§heading`, `section#hash12`).
- [X] T006 [P] Write `tests/unit/test_regions.py`. `provenance` and `changelog` are read and written, and excluded from the fingerprint and from `section_fingerprints`. `Change Log` and `Record` are administrative sections. The allowed-keys check follows the table in contracts/document-format.md: every key the helper writes is accepted, and an unknown key at any level, or bad JSON, reports `malformed-provenance`. The new fingerprint test vectors from contracts/document-format.md are included.
- [X] T007 [P] Write `tests/unit/test_adoption.py` for determinism requirements 32 and 33 and FR-047:
  - approved and unchanged: every block `adopted` with `basis: approval …`, and stage state identical before and after;
  - approved and changed: only covered blocks adopted;
  - never approved: untagged adopted, tagged inferred;
  - derived documents: `currency: unknown`;
  - a malformed region is never auto-adopted;
  - `status` before `sync` equals `status` after;
  - `status` and `check` leave the regions byte-identical.
- [X] T008 [P] Write `tests/unit/test_reviews_core.py` for determinism requirements 28 and 29:
  - the list digest is stable for the same state and changes when any entry's hash changes;
  - `answer` with a stale digest gives `list-changed` and writes nothing;
  - `--all`, `--all-except`, `--question` and `--reopen` record one acceptance holding the verbatim `reply`;
  - `reply-required`;
  - a settling answer by a non-confirmer gives `not-a-confirmer`, and by the AI `ai-approval`;
  - question and reopen from anyone are recorded with the name;
  - `RVW` numbering continues past legacy `eil:review` ids;
  - determinism requirement 35: a bare all-phrase reply with other flags, or `--all` with a reply naming a listed entry key, gives `reply-mismatch` and writes nothing; `--all` with "ok to all, but note the typo" succeeds;
  - determinism requirement 36 (FR-050): `--question`/`--reopen` may name an entry settled since the last approval with no digest, and a settling answer without one gives `digest-required`; opposite answers by two people mark the entry `conflict`, it blocks dependants, and a confirmer's new answer clears it with `resolved_conflict`;
  - every list's `limits[]` includes the reply-check limit.
- [X] T009 [P] Write `tests/unit/test_identity_derived.py`. `approvers.ai-spec`, `plan`, `tasks` and `verification` default to the `technical` list, and then to the story's developer, and an explicit list overrides that (data-model Configuration).

### Implementation

- [X] T010 Add the `provenance` and `changelog` regions to `eil/blocks.py`: `REGION_NAMES`; a Markdown-body region for `changelog`; a `read_provenance`/`write_provenance` pair with allowed-keys validation that reports `malformed-provenance`; and placement of `## Change Log` and `## Record` per contracts/document-format.md.
- [X] T011 Exclude the two new regions in `eil/fingerprint.py` (step 3), and add `Change Log` and `Record` to `ADMINISTRATIVE_SECTIONS` in `eil/trace.py`. Run T006.
- [X] T012 Implement `eil/content.py`: the FR-039 block walker, the block hash (tags removed; steps 2, 5 and 6), keys, and the prose `(traces:)` citation. Reuse `trace.parse_document` item spans so numbered blocks match `item_hash`. Run T005.
- [X] T013 Add the `RF` item kind to `eil/trace.py` (`KINDS`, the item regex, `(status: open|resolved|excepted)`, and the `Root`, `Accepted by` and `Reason` labelled lines, reusing the EVD field rules).
- [X] T014 Implement derived block status in a new `eil/blockstatus.py`: `settled`, `needs-review`, `source-changed` and `unknown-currency` from the provenance region, current hashes and approvals, per data-model "Derived status". Cache it on `Package` per command, like the existing parse cache.
- [X] T015 Implement adoption (D-42) in `eil/blockstatus.py` as a pure function that returns the region an upgrade would write. Have `eil sync` in `eil/cli.py` persist it only when the region is absent, and have `status` and `check` use the in-memory result. Run T007.
- [X] T016 Extend approvers to the derived stages in `eil/identity.py` and `extensions/eil/config-template.yml`. Run T009.
- [X] T017 Implement the review-list core in `eil/reviews.py`: `ListEntry`, `ReviewList` (kind, stage, purpose, entries, digest, limits), a registry mapping each list kind to an entry builder, `answer()` (digest check for settling answers only, with `digest-required`; question and reopen may name any entry of the kind settled since the last approval or since recorded, reply flags, authority per FR-048, acceptance record in the provenance region, `RVW` allocation shared with `provenance._highest_review_number`), and the settle and reopen hooks each kind supplies, the `reply-mismatch` check and the FR-050 conflict state (conflicted entries feed `blocked_work` once T024 exists). Run T008.
- [X] T018 Wire `review list --stage S --kind K` and `review answer …` into `eil/cli.py`, following contracts/cli.md. Keep `review start|accept|finish` working unchanged until US3 reroutes them.
- [X] T019 Wire `blocks list --stage S [--status ST]` into `eil/cli.py`, using `blockstatus`.

**Checkpoint**: T005 to T009 pass, the full existing suite still passes, and B-27 steps 1 and 2 (upgrade with no change of state) hold on the reference story.

---

## Phase 3: User Story 1 - An upstream edit stops only the work it affects (Priority: P1) 🎯 MVP

**Goal**: Item-level staleness in every layer, and blocking of only the work that traces to it (FR-001 to FR-008, FR-025, FR-041).

**Independent Test**: B-19 and B-20. Edit DEC-003 in the reference story. Only its dependants are stale. `enter implement --task T002` passes and `--task T009` gives `work-blocked`. Affected completed tasks are answered in one reply.

### Tests for User Story 1

- [X] T020 [P] [US1] Write `tests/unit/test_staleness.py` for determinism requirement 26 and FR-002/003/007. Changing one DEC marks exactly its direct and transitive dependants across AIS, plan sections, tasks and EVD. A multi-source item goes stale when one source changes. A revert clears staleness with no command. A whitespace-only change does nothing. A cycle or dangling id is a document error, not "unaffected".
- [X] T021 [P] [US1] Write `tests/unit/test_enter_scoped.py` for determinism requirement 27 and FR-004/025/038:
  - `enter implement --task` passes for an unaffected task and refuses `work-blocked` for an affected one, naming the source and the fix;
  - a stage that was never approved still gives `stage-not-approved`;
  - a `needs-re-review` stage does not refuse wholesale;
  - a `[pending-clarification]` AIS blocks only the tasks tracing to it;
  - `enter plan` returns `rederive` and `blocked`;
  - `work-blocked` when nothing may proceed.
- [X] T022 [P] [US1] Write `tests/unit/test_task_evidence_lists.py` for FR-005, FR-006 and FR-008:
  - `sync` snapshots newly ticked tasks (`completed_against`, `blocked_at_completion`);
  - a changed source puts the task on the `tasks` list, likely-rework first, with a labelled AI view;
  - "ok except T014" re-confirms the others and reopens T014;
  - completion refuses while the list is unanswered;
  - completion refuses `unreviewed-ai-content` while an inferred s07 block (an evidence row) is unreviewed, and the override still works (FR-049);
  - the `evidence` list works the same way, with `evidence-for-earlier-version`;
  - derived documents with no snapshot appear once on the `unknown-currency` list, and answering records the snapshot.
- [X] T023 [P] [US1] Write the scenario test `tests/scenario/test_b19_b20_scoped_staleness.py`, replaying quickstart B-19 and B-20 on the reference story.

### Implementation for User Story 1

- [X] T024 [US1] Implement `eil/staleness.py`: record source versions when a block is settled; compute directly stale, transitively stale (cycle-safe graph walk over `trace.build_graph`) and unknown currency; and return `blocked_work(pkg)` as `{id: [causes]}`, covering stale sources, unaccepted changes, pending AIS and, later, open corrections through a hook. Run T020.
- [X] T025 [US1] Make `enter` work-scoped in `eil/handoff.py` (D-35): `stage-not-approved` only for a stage never approved; per-item `blocked[]` and `rederive[]`; the `--task` argument; and the `work-blocked` refusal. Make `AIS-G03` item-scoped in `eil/gates.py`, so a pending item blocks only its dependants.
- [X] T026 [US1] Add `--task` to `enter` in `eil/cli.py`, and add the new success shape (contracts/cli.md "`enter` success shape"). Run T021.
- [X] T027 [US1] Add task snapshots to `eil sync` in `eil/cli.py` via `staleness`: record `completed_against` the first time a task is seen ticked, and mark `blocked_at_completion` (finding `completed-while-blocked`).
- [X] T028 [US1] Register the `tasks`, `evidence` and `unknown-currency` list kinds in `eil/reviews.py`:
  - builders with the ordering rules and the `AI assessment:` view field (the AI's view comes in through an optional `--views FILE` on `review list`, verdicts only, like `--judgments`);
  - settle hooks that re-record source versions;
  - a reopen hook that clears `completed_against`.
- [X] T029 [US1] Refuse completion in `eil/gates.py` and `eil/records.py` while any `tasks` or `evidence` entry is unanswered. Map this to the completion refusals `task-completed-against-earlier-version` and `evidence-for-earlier-version`, overridable as other completion criteria are. Also refuse `approve completion` with `unreviewed-ai-content` while any inferred s07 block is unreviewed (FR-049), using `blockstatus`. Run T022.
- [X] T030 [US1] Add `blocks: {settled, needs_review, stale, unknown}` per stage (`source-changed` counted as `stale`) and top-level `blocked_work[]` to `eil status` in `eil/package.py`, and add a Blocked work section to the overview in `eil/overview.py`.
- [X] T031 [US1] Update the preset wraps `commands/speckit.implement.md` (call `enter implement --task` before each task, skip on `work-blocked` and say why, run `eil sync` after ticking, offer the `tasks` list) and `commands/speckit.plan.md` and `commands/speckit.tasks.md` (re-derive only `rederive` items in place, never derive from `blocked`). In the plan and tasks wraps, after writing, also write the classification file, run `eil blocks classify --stage plan|tasks`, and run the one-reply `inferred` list (FR-012, FR-049). In both wraps, when re-deriving an item that carries `(decided: CR-###)`, replace or remove the clause (contracts/commands.md, Tier 2 rules). Update `commands/speckit.clarify.md` to say which tasks remain implementable.
- [X] T032 [US1] Run T023 (B-19, B-20) and fix until it passes.

**Checkpoint**: SC-002 and SC-003 hold on the scenario suite. US1 is shippable alone: a correction blocks only its dependants.

---

## Phase 4: User Story 2 - Review effort matches what the content is (Priority: P1)

**Goal**: Restated, decided and inferred provenance. Only inferred content is reviewed, in one list. Review status comes from hashes, and `[ai-draft]` is a cue the helper renders (FR-009 to FR-014, FR-039, FR-046, FR-049).

**Independent Test**: B-21. In a 30-block AI Specification, only the 5 inferred blocks are listed. Removing a tag by hand changes nothing. "ok except AIS-003" settles 4. A task tracing to an unreviewed inferred item is blocked while others proceed.

### Tests for User Story 2

- [X] T033 [P] [US2] Write `tests/unit/test_classify.py` for determinism requirement 24 and FR-009/011/013:
  - class rules and precedence (decided, then restated, then inferred);
  - a citation to an unsettled or changed source is inferred: in s01 to s03 settled means covered by the approval; in s04 to s06 it means the source's own block status is settled and not stale (a plan section restating a settled AIS item is restated; one restating a stale or unreviewed inferred AIS item is inferred; a task restating that plan section follows it);
  - an `adds` verdict is inferred, with its reason;
  - no verdict at all is inferred;
  - the classify file is validated (exit 2 on an unknown key or block, or a stage mismatch);
  - `reclassify --to inferred` is accepted from anyone, and there is no path from inferred to restated.
- [X] T034 [P] [US2] Write `tests/unit/test_ai_draft_cue.py` for determinism requirement 25 and FR-046:
  - `approve` refuses `unreviewed-ai-content` while an inferred block is unreviewed, even with no tag present;
  - it passes once the block is reviewed, even if a tag was hand-added;
  - `sync` re-renders tags on exactly the unreviewed inferred blocks;
  - the fingerprint is unchanged by re-rendering;
  - the override of `unreviewed-ai-content` still works.
- [X] T035 [P] [US2] Write `tests/unit/test_inferred_list.py` for FR-010, FR-049 and FR-014:
  - the `inferred` list shows full text and reason;
  - "ok except" settles the rest, and the excepted block reappears alone;
  - an edited reviewed block reappears, and an unchanged one never does;
  - an unreviewed inferred AIS, plan section or task blocks only its dependants via `blocked_work`;
  - the fidelity limit line is present on every list showing restated content.
- [X] T036 [P] [US2] Write the scenario test `tests/scenario/test_b21_provenance.py`, replaying quickstart B-21.

### Implementation for User Story 2

- [X] T037 [US2] Implement classification (D-32) in `eil/provenance.py`. Compute classes from `(decided:)`, verified `(traces:)` citations with source hashes against settled sources (approval coverage in s01 to s03; settled, non-stale block status in s04 to s06, evaluated in stage order; spec FR-009, D-32), and the latest AI verdicts, and write `class`, `cites` and `adds` into the provenance region. Add `blocks classify --stage S --file PATH` and `blocks reclassify` in `eil/cli.py`. Run T033.
- [X] T038 [US2] Add cue rendering (D-33) to `eil/provenance.py`: `render_cues(text, statuses)` adds or removes ` [ai-draft]` on the first line of blocks and touches nothing else. Call it from `sync`, `blocks classify`, `review answer` and every writer of stage documents.
- [X] T039 [US2] Re-base `unreviewed-ai-content` on block status in `eil/records.py` (approve) and `eil/gates.py`, keeping the override path. Run T034.
- [X] T040 [US2] Register the `inferred` list kind in `eil/reviews.py`, with a settle hook recording the reviewed hash and an except hook that leaves the block inferred. Feed unreviewed inferred blocks in s04 to s06 into `staleness.blocked_work` (FR-049). Run T035.
- [X] T041 [US2] Update the drafting prompts `extensions/eil/commands/speckit.eil.requirements.md`, `speckit.eil.functional.md`, `speckit.eil.technical.md` and `speckit.eil.ai-spec.md`: cite restated sources, never hand-write `[ai-draft]`, write the classification file and run `blocks classify`, then run the one-reply `inferred` list (contracts/commands.md); when re-editing an item that carries `(decided: CR-###)`, replace or remove the clause. Update `speckit.eil.approve.md` to run the `inferred` list before asking for the attestation.
- [X] T042 [US2] Add prompt contract tests `test_one_reply_lists`, `test_reply_verbatim` and `test_no_manual_ai_draft` to `tests/contract/test_prompt_guidance.py`, covering every prompt changed in T041 and T031.
- [X] T043 [US2] Run T036 (B-21) and fix until it passes.

**Checkpoint**: US1 and US2 together form the MVP. Blocking is proportionate, and review goes only to inferred content.

---

## Phase 5: User Story 3 - One way to accept a change to something already approved (Priority: P2)

**Goal**: One action finds covered changes automatically, lists only uncovered ones, and records one confirmation. When every change is covered, the approval carries forward on an explained "ok" (FR-015 to FR-020).

**Independent Test**: B-22. A change covered by OQ-002 re-signs on "ok" with `reached: carried-forward` and no ids typed. Mixed changes need the `changes` list, then the delta comprehension check if inferred, then one confirmation.

### Tests for User Story 3

- [X] T044 [P] [US3] Write `tests/unit/test_accept_changes.py` for determinism requirement 30 and FR-016 to FR-020:
  - the `changes` list splits covered changes (`covered_by`) from uncovered ones (`inferred` flag), with no ids supplied, including upstream items reaching in through `upstream_items`;
  - `confirm` with everything covered gives `reached: carried-forward`, `rests_on`, `sign_off: "ok"` and no comprehension;
  - uncovered and unanswered gives `changes-unanswered`;
  - uncovered and inferred without a current delta check gives `comprehension-prerequisites`;
  - `reached: reviewed` otherwise;
  - `confirmation-required`, `not-a-confirmer` and `ai-approval`;
  - `acceptance-conflict` while any entry is in conflict (FR-050);
  - an old record without `reached` reads as `first`;
  - regression for FR-038: a first approval of functional or technical still needs the full five-level comprehension check and an attestation.
- [X] T045 [P] [US3] Write `tests/unit/test_legacy_aliases.py`. `amend --from` with ids that are a subset of the covering set succeeds, and ids outside it are refused. `review start|accept|finish` produce the same records as `list`, `answer` and `confirm`. Existing `test_review.py` and amend tests still pass.
- [X] T046 [P] [US3] Write the scenario test `tests/scenario/test_b22_accept.py`, replaying quickstart B-22.

### Implementation for User Story 3

- [X] T047 [US3] Register the `changes` list kind in `eil/reviews.py`, built on the existing coverage core in `eil/provenance.py` (`_changed_roots`, `_uncovered_items`, `_uncovered_sections`). Mark coverage by `(decided:)` or by an acceptance since the approval, and flag inferred entries.
- [X] T048 [US3] Implement `confirm()` in `eil/reviews.py`: carry-forward versus reviewed, the delta comprehension prerequisite (reuse `_ensure_comprehension_current`), and an approval record with `reached`, `rests_on`, `sign_off` or `attestation`, `blocks` and `outstanding`. Wire `review confirm` in `eil/cli.py`. Run T044.
- [X] T049 [US3] Reroute `amend`, `review start`, `review accept` and `review finish` in `eil/provenance.py` and `eil/cli.py` as aliases over `list`, `answer` and `confirm` (D-36). Run T045.
- [X] T050 [US3] Show `reached` and `rests_on` in `eil/overview.py` (Approvals table: "carried forward (OQ-002)", "reviewed (RVW-012)") and in `eil status` in `eil/package.py`, as visibly as an override (FR-020).
- [X] T051 [US3] Create `extensions/eil/commands/speckit.eil.accept.md` (contracts/commands.md). Replace the bodies of `speckit.eil.amend.md` and `speckit.eil.review.md` with a short "superseded, running accept" alias. Register the command in `extensions/eil/extension.yml`.
- [X] T052 [US3] Update `tests/contract/test_install.py` to expect `speckit.eil.accept` and the new config keys.
- [X] T053 [US3] Run T046 (B-22) and fix until it passes.

**Checkpoint**: SC-004 holds. A fully covered change re-signs with one short sign-off, zero ids and zero attestations.

---

## Phase 6: User Story 4 - Moving backwards is one action with an impact report (Priority: P2)

**Goal**: Report a problem once and see the owner and impact before anything changes. The origin is recorded. Only dependants block. Documents are corrected in place with a generated Change Log (FR-021 to FR-027, FR-042, FR-043, FR-045 partial).

**Independent Test**: B-23 and B-24. A correction from implementation reaches a re-signed stage in three interactions. The Change Log and trace show the origin. Unaffected tasks stay implementable. Re-derivation leaves other text byte-identical.

### Tests for User Story 4

- [X] T054 [P] [US4] Write `tests/unit/test_corrections.py` for FR-021 to FR-025:
  - `propose` is read-only and returns candidates, `ambiguous` and impact;
  - an unambiguous item is not ambiguous;
  - a restated item gives its own stage plus its source's stage;
  - `open` without `--owner` when ambiguous gives `owner-ambiguous`, and `owner-not-candidate`;
  - an open CR blocks only tasks tracing to its item and impact;
  - `open --wording` stores the words verbatim; `(decided: CR-###)` is eligible only when the CR's item is this item and the item's text equals the wording (normalised), otherwise `decided-source-invalid`; a CR without `wording` is never eligible; a `changes` list with a CR-covered entry prints the wording limit in `limits[]`;
  - a mismatched or left-behind `(decided: CR-###)` is a non-blocking `decided-source-invalid` (neither `check` nor `approve` fails on it, and the change is uncovered), while `(decided: CR-999)` naming no CR stays a blocking integrity finding;
  - a CR owned by `ai-spec` (quickstart B-23 step 2a): `confirm --stage ai-spec` refuses `not-amendable` while the item is unsettled, then closes the CR, writes its Change Log entry and writes no `approval`;
  - with an eligible `(decided: CR-###)`, `confirm` carries forward on "ok" with `rests_on` naming the CR and asks no comprehension (SC-005);
  - confirming the owning stage closes the CR;
  - `trace --to` shows the CR with its origin.
- [X] T055 [P] [US4] Write `tests/unit/test_changelog.py` for FR-043 and FR-044. A `changes[]` entry is written on each confirm after first approval, with the AI's summary supplied through `review answer --summaries FILE` (uncovered changes) or `review confirm --summaries FILE` (covered changes, including a carry-forward) and recorded `summary_by: "ai"`. A change with no summary from either flag, whether covered or uncovered, refuses `summary-missing` and writes nothing. A closed CR in a never-approved stage writes one entry, and a re-derivation there writes none. The `changelog` region renders as a table (escaped cells), with the Change column labelled AI-drafted (Constitution II). Rendering changes no fingerprint. The overview shows the latest 5 story-wide. No bookkeeping appears in the prose.
- [X] T056 [P] [US4] Write `tests/unit/test_unsettled_and_rf.py` for FR-026 and FR-027:
  - after a confirm, a rejected or deferred challenge targeting a changed id appears on the `unsettled-challenges` list and as a `human` next action;
  - an `RF` item with `(status: open)` fails `VER-G07`, and completion refuses `review-finding-open`;
  - an upstream-rooted RF must trace to a CR;
  - determinism requirement 37: an RF added or changed after completion was approved makes completion `needs-re-review`, and an unrelated s07 edit does not.
- [X] T057 [P] [US4] Write the scenario test `tests/scenario/test_b23_b24_backwards.py`, replaying quickstart B-23 and B-24 and counting person interactions for SC-005.

### Implementation for User Story 4

- [X] T058 [US4] Implement `eil/corrections.py`: `propose()` (owner candidates from the defining stage plus the cited-source stages of restated blocks, and impact from `graph.downstream`), `open()` (CR allocation story-wide, stored in the owning stage's provenance region, with the optional verbatim `wording`), and closure on confirm, including `confirm` on a never-approved owning stage, which closes CRs whose item is settled and writes no approval (contracts/cli.md). Extend `decided_eligible` in `eil/provenance.py` and the `decided:` clause grammar in `eil/trace.py` to accept `CR-###` by the text-equality rule, with a mismatch reported as a non-blocking finding (contracts/document-format.md). Plug open CRs into `staleness.blocked_work`. Wire `correct propose|open` (with `--wording`) in `eil/cli.py`. Run T054.
- [X] T059 [US4] Add CR entries to the `trace --to` output in `eil/chain.py` (FR-024).
- [X] T060 [US4] Implement `eil/changelog.py`: append a `changes[]` entry in `reviews.confirm()` (item, the AI summary accepted with the change, origin CR, decision or `edit`, and `accepted_by`), and render the `changelog` region. Add `--summaries FILE` to `review answer` (the `changes` kind, and `inferred` entries under an open CR) and to `review confirm`, and refuse `summary-missing` for any change left without one. Mark `inferred` list entries whose item is under an open CR with `correction` (contracts/cli.md). Show recent changes in `eil/overview.py`. Run T055.
- [X] T061 [US4] Register the `unsettled-challenges` list kind in `eil/reviews.py`, with answers reconfirm (by a confirmer) or reopen (anyone). Add `VER-G07` and the `review-finding-open` refusal in `eil/gates.py` and `eil/records.py`. Add `## Review Findings` to `templates/s07-verification-template.md`. Record `review_findings` in the completion approval (`eil/records.py`) and report completion `needs-re-review` for a new or changed RF (`eil/package.py`). Run T056.
- [X] T062 [US4] Add `## Change Log` and `## Record` sections to `templates/s01-requirements-template.md` through `templates/s08-completion-template.md`, including `templates/spec-template.md`, `plan-template.md` and `tasks-template.md` (the s04 to s06 templates), placed as contracts/document-format.md says.
- [X] T063 [US4] Create `extensions/eil/commands/speckit.eil.correct.md`: take the problem, the item and the person's wording if given; propose; show owner, edit and impact before applying; ask about the owner only if ambiguous; open (with the person's words verbatim as `--wording`, never AI text); apply in place, with `(decided: CR-###)` only for the person's wording, and remove an earlier `(decided: CR-###)` from an item it edits again; then continue as accept (contracts/commands.md). Update `speckit.eil.verify.md` to classify its evidence rows (`blocks classify --stage verification` and the `inferred` list, FR-012), and to record code-review findings as `RF` items with their root, handing upstream roots to correct. Register the command in `extensions/eil/extension.yml` and `tests/contract/test_install.py`.
- [X] T064 [US4] Add prompt contract tests `test_correct_shows_before_apply`, `test_rederive_only_listed`, `test_decided_clause_removed_on_reedit` (the `correct` and `accept` prompts, the drafting commands and the `plan`/`tasks` wraps) and `test_summaries_passed` (`accept`, `correct`) to `tests/contract/test_prompt_guidance.py`.
- [X] T065 [US4] Run T057 (B-23, B-24) and fix until it passes.

**Checkpoint**: SC-005 holds. Backwards movement is one action with an impact report and a recorded origin.

---

## Phase 7: User Story 5 - The developer sees only what needs them (Priority: P3)

**Goal**: Focused gate output, challenge severity with proportionate blocking, de-duplicated challenges and purpose labels (FR-028 to FR-032, FR-048 severity rules).

**Independent Test**: B-25. There are 5 detailed criteria and one summary line. Challenges are ordered high, medium, low. Approval succeeds with only low challenges open and lists them as outstanding. Raising is open to anyone, and lowering needs a confirmer.

### Tests for User Story 5

- [X] T066 [P] [US5] Write `tests/unit/test_severity.py` for determinism requirement 31 and FR-029, FR-030 and FR-048:
  - `challenge add --by ai` without `--severity` exits 2, and a person may omit it (reads as medium);
  - a legacy record without severity counts as medium;
  - `approve` passes with only low challenges open and records `outstanding`;
  - it refuses with a medium or high one;
  - `challenge severity` raising by anyone is accepted, and lowering by a non-confirmer gives `not-a-confirmer`;
  - `severity_history` is recorded;
  - a duplicate open challenge returns the existing id.
- [X] T067 [P] [US5] Write `tests/unit/test_focused_check.py` for FR-028 and FR-032: criteria ordered unmet, then judgment, then met; `summary.met_structural`; text output collapses met structural criteria unless `--full`; `next_action.purpose` and each list's `purpose` are always one of the five values.
- [X] T068 [P] [US5] Write the scenario test `tests/scenario/test_b25_focus_severity.py`, replaying quickstart B-25.

### Implementation for User Story 5

- [X] T069 [US5] Add severity to challenges in `eil/records.py`: the `--severity` rule, the medium default, `challenge severity` with the raise/lower authority rule and `severity_history`, the approve rule (only high and medium block), `outstanding` in the approval record, and the existing id on duplicates. Wire it in `eil/cli.py`. Run T066.
- [X] T070 [US5] Add criterion ordering, `summary.met_structural` and `--full` to `eil/gates.py` and `eil/cli.py`. Run T067.
- [X] T071 [US5] Add `purpose` to `next_action` in `eil/package.py` or the module that builds status, and add open low challenges (outstanding) to `eil/overview.py`.
- [X] T072 [US5] Update `extensions/eil/commands/speckit.eil.challenge.md` (high first, raise with `--severity`, change severity), `speckit.eil.approve.md` (focused gate, outstanding lows), and `speckit.eil.status.md` and `speckit.eil.next.md` (purpose, blocked work, open corrections, recent changes). Add the prompt contract test `test_purpose_stated` to `tests/contract/test_prompt_guidance.py`.
- [X] T073 [US5] Run T068 (B-25) and fix until it passes.

**Checkpoint**: Gate reading and challenge fatigue are reduced, and no decision point is removed.

---

## Phase 8: User Story 6 - Completion asks only about what implementation touched (Priority: P3)

**Goal**: Currency questions only for touched artefacts. Automated evidence is confirmed from files. Low challenges are answered in one batch. Accepted design differences are corrected, not annotated (FR-033 to FR-035, FR-040, FR-045).

**Independent Test**: B-26. 3 of 8 artefacts are asked about and 5 listed as untouched. A resolvable automated evidence row is not presented, and no subprocess runs. Five low challenges are deferred in one reply. A design difference becomes a CR and a Change Log entry.

### Tests for User Story 6

- [X] T074 [P] [US6] Write `tests/unit/test_evidence_confirm.py` for determinism requirement 34 and FR-034 and FR-035. `path::name` and path-plus-name forms are confirmed when the file inside the project defines the name. A missing file, a missing name or a path outside the project root is unconfirmed. `subprocess` is monkeypatched to fail if called. The limit line "exists; result attested" is present.
- [X] T075 [P] [US6] Write `tests/unit/test_completion_lists.py` for FR-033 and FR-040:
  - touched means reached (directly or through AIS) by a task with `(code:)`, or the ART hash differs from its approval;
  - the `diagram-currency` list at completion holds only touched artefacts;
  - the `low-challenges` list "defer all" closes each as `deferred` with the shared reason and name, and "except" leaves the named ones for individual answer;
  - completion refuses any open challenge.
- [X] T076 [P] [US6] Write the scenario test `tests/scenario/test_b26_completion.py`, replaying quickstart B-26.

### Implementation for User Story 6

- [X] T077 [US6] Implement `eil/evidence.py`: token extraction from `Evidence:` lines, resolution inside the project root, and identifier search, with no subprocess or network. Use it in the `evidence` list builder in `eil/reviews.py` so confirmed rows are excluded. Run T074.
- [X] T078 [US6] Add touched-artefact computation to `eil/staleness.py`. Register the `diagram-currency` list kind in `eil/reviews.py` (completion stage). Register the `low-challenges` list kind, whose defer answer closes challenges via `eil/records.py` with `reason-required` enforced. Run T075.
- [X] T079 [US6] Update `templates/s08-completion-template.md` so Diagram Currency covers touched artefacts only, with an `- untouched: …` line. Accept that line format in the s08 criterion in `eil/gates.py`.
- [X] T080 [US6] Update `extensions/eil/commands/speckit.eil.complete.md`: run the `low-challenges`, `evidence`, `tasks` and `diagram-currency` lists as one reply each (only if non-empty), list untouched artefacts without a question, and open a correction with origin `completion` for an accepted design difference (FR-045). Keep an accepted deviation only with a future-target reason.
- [X] T081 [US6] Run T076 (B-26) and fix until it passes.

**Checkpoint**: Completion asks only what implementation touched.

---

## Phase 9: Polish and cross-cutting concerns

- [X] T082 Write `tests/scenario/test_b27_upgrade.py` replaying quickstart B-27, including R-20 (nothing previously blocked becomes unblocked except through an explicit answer) and step 4 (an abbreviated story is unaffected).
- [X] T083 Write `tests/scenario/test_interaction_count.py` for SC-001 (D-43). Capture the 001 baseline once: add `git worktree` at tag `eil-001-baseline` (from T001), then run the **current** harness and reference-story fixture (built with no `provenance` or `changelog` regions and no `RF` items, which the 001 helper does not know) against the **baseline helper** at `<worktree>/extensions/eil/scripts/python/eil`, running the 001 command sequence, writing `tests/fixtures/baseline-001-counts.json` (regenerated only with `--update-baseline`). Replay the 002 sequence on the current code with the same edits, classify each `--by` call as `decision`, `first-approval`, `inferred-review` or `other`, and assert that `other` falls by at least 60% and the first two counts are equal. **Status: met after D-45 (an `inferred` acceptance also answers the matching `changes` entry): other = 6 under 001, at most 2 under 002 (a fall of at least 67%, target 60%); the xfail is removed.**
- [X] T084 [P] Extend `tests/unit/test_performance.py` with nine 1 MB documents whose provenance regions hold 2,000 blocks. `status`, `check` and `enter` must each run in under 1 s (D-44).
- [X] T085 [P] Add probes P-20 (one reply per list), P-21 (verbatim reply), P-22 (correction shown before applying), SC-006 (what am I checking, and why, at five checkpoints) and SC-007 (reconfirmation without change) to `docs/trials.md`.
- [X] T086 Fold the three delta contracts into `specs/001-staged-definition-workflow/contracts/cli.md`, `document-format.md` and `commands.md`. Include the list of helper edits to human content (D-28 `review accept`, `resolve`, D-33 cue rendering), in the same change as the tests that pin them (Constitution workflow rule).
- [X] T087 [P] Update `README.md`: what the developer is now asked and why (the five purposes), the one-reply lists, accept and correct, and the attestation limits for the fidelity check (FR-014), evidence confirmation (FR-035), the mapping of a person's reply to what is recorded as accepted (D-36), correction wording whose author the tool cannot tell (D-38), and a hand-edited provenance region (R-21). Update `CHANGELOG.md` (Unreleased).
- [X] T088 [P] Update `.github/pull_request_template.md` with the Principle IV line (the human interactions added or removed, with their purpose), if it is not already present.
- [X] T089 Run `ruff check` and the full `pytest` suite, including the contract tests against a scratch Spec Kit project (`tests/contract/test_install.py`, `test_wrap_guards.py`, `test_removal_and_coexistence.py`), and fix any failures.
- [X] T090 Run `/speckit-analyze` on this feature after these tasks change and before implementation begins (Constitution workflow). Fix any CRITICAL finding in the spec, plan or tasks. Also confirm FR-036 and FR-037 as cross-cutting regressions: no code path or prompt writes an approval, answers a challenge or open question, or accepts a risk on the AI's behalf (grep the helper and prompts, and the T064 contract tests), and every Tier 1 rule in `contracts/cli.md` has a unit test. **Status: grep check for FR-036/FR-037 done, no violation found; `/speckit-analyze` run 9 done; its A1 finding fixed by D-45.**

---

## Dependencies and execution order

### Phase dependencies

- **Setup (T001 to T004)**: T001 first, because everything builds on the committed D-23 to D-29 code.
- **Foundational (T005 to T019)**: after Setup, and it blocks every story.
- **US1 (Phase 3)**: after Foundational.
- **US2 (Phase 4)**: after Foundational. It feeds `staleness.blocked_work` (T040), so it depends on T024 from US1.
- **US3 (Phase 5)**: after Foundational. It uses the coverage core only, so it is independent of US1 and US2, but B-22 is cleanest after US2, because inferred flags on changes come from classification (T037).
- **US4 (Phase 6)**: after US3 (corrections close on `confirm`, and the Change Log is written by `confirm`) and T024 (blocking).
- **US5 (Phase 7)**: after Foundational. Independent of the other stories.
- **US6 (Phase 8)**: after US1 (task and evidence lists and staleness) and US4 (corrections for FR-045). The low-challenge list also needs US5's severity.
- **Polish (Phase 9)**: after the stories it measures. T083 needs every story, and T090 is last before implementation.

### Story order at a glance

```text
Setup → Foundational ─┬─ US1 ── US2 ──┐
                      ├─ US3 ─────────┼── US4 ──┐
                      └─ US5 ─────────┴─────────┴── US6 ── Polish
```

### Within each story

Write the tests, see them fail, then implement modules, then CLI wiring, then prompts, then run the scenario.

## Parallel examples

```text
# Foundational tests (different files):
T005 test_content.py   T006 test_regions.py   T007 test_adoption.py
T008 test_reviews_core.py   T009 test_identity_derived.py

# US1 tests together:
T020 test_staleness.py   T021 test_enter_scoped.py   T022 test_task_evidence_lists.py   T023 scenario B-19/20

# After Foundational, with two developers:
Developer A: US1 → US2        Developer B: US5, then US3

# Polish:
T084 performance   T085 trials   T087 README   T088 PR template
```

## Implementation strategy

- **MVP**: Setup, Foundational, then **US1 and US2** (both P1). Stop and validate B-19 to B-21. That removes the two largest frictions, wholesale blocking and per-paragraph untagging, and is shippable on its own.
- **Increment 2**: US3 and US4 (P2). One accept action and backwards corrections, validated by B-22 to B-24.
- **Increment 3**: US5 and US6 (P3), then Polish with SC-001 measured by T083.
- At each checkpoint the full existing suite still passes, so 001 behaviour is never broken mid-way. Each increment's pull request states the human interactions added or removed, with their purpose (Constitution IV).
