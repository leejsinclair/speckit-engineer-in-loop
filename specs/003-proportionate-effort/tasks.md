---
description: "Task list for Proportionate Effort (first-pass proportionality and trial defects)"
---

# Tasks: Proportionate Effort

**Input**: Design documents from `specs/003-proportionate-effort/`

**Prerequisites**:
- plan.md and spec.md;
- research.md (D-46 to D-58, R-22 to R-28);
- data-model.md;
- contracts/ (deltas to cli.md, document-format.md and commands.md);
- quickstart.md (B-29 to B-36, probes P-23 to P-30).

**Tests**: Included and written first. Constitution Principle III requires it. The plan names determinism requirements 38 to 52, scenarios B-29 to B-36 and nine prompt contract tests. The spec also requires scenario tests for the upgrade migration and the ambiguous-target refusal (FR-043). Each test task is run and **seen to fail** before its implementation task starts.

**Organization**:
- Tasks are grouped by the spec's user stories, US1 to US9.
- Phases follow the plan's binding delivery order. That order differs from strict priority order in one place: US7 (P2) comes before US4 (P2), and US9 and US5/US6 (P2/P3) come before US4, because the profile (US4) composes the review-list, decision and comprehension changes.
- Each story phase ends with its CHANGELOG entry, which names the human interactions it adds or removes and their purpose (FR-042).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (a different file, and no dependency on an incomplete task).
- **[Story]**: US1 to US9.
- Paths are relative to the repository root. `eil/` means `extensions/eil/scripts/python/eil/`.
- `cli.py`, `package.py`, `gates.py`, `reviews.py`, `CHANGELOG.md`, `tests/helpers/package.py` and `tests/contract/test_prompt_guidance.py` are shared by many tasks. Tasks that edit them are never [P] with each other.

---

## Phase 1: Setup

**Purpose**: A clean baseline and the two fixtures that the tests use.

- [X] T098 Apply constitution PATCH 1.2.2 with `/speckit-constitution`, using `specs/003-proportionate-effort/constitution-patch-1.2.2.md`, with the repository owner's approval. Required before US10.
- [X] T001 Resolve the uncommitted pre-003 work in the tree (deleted `speckit.eil.amend.md` and `speckit.eil.review.md`, and the prompt, test, README, CHANGELOG and `specs/002-…/contracts/commands.md` edits). **Ask the repository owner** whether to commit it as its own change or discard it. Run `pytest` before and after. Do not mix it with 003 work.
- [X] T002 Commit the 003 design documents (`specs/003-proportionate-effort/`, `docs/trials.md` SC-010 row, `.specify/feature.json`) as "docs: add 003 proportionate-effort spec, plan and tasks".
- [ ] T003 [P] Create `tests/fixtures/legacy_upgrade.py`, the shape of trial snapshot `bd7a0d5`:
  - Functional and Technical approvals carry `items` but no `section_fingerprints`;
  - after approval, one prose paragraph and one sequence diagram change in each;
  - judgments are recorded in `assessment`;
  - `[ai-draft]` tags remain on two never-approved plan blocks.

  Build it on `tests/helpers/package.py`.
- [ ] T004 [P] Create `tests/fixtures/two_stories.py`: story A (`001-a`) with completion approved, story B (`002-b`) in progress at Functional, and `.specify/feature.json` pointing at A. Add an option to create a git repository on a named branch (local `git init` and `git checkout -b`, no network).
- [ ] T005 Add the `legacy_upgrade` and `two_stories` pytest fixtures, and a `files_snapshot(root)` helper (path → bytes) for byte-identity assertions, to `tests/conftest.py`.

---

## Phase 2: Foundational (blocking prerequisites)

**Purpose**: The single seam for record reads and writes. Every later story writes records through it. This phase is a pure refactor, with no change of behaviour.

**⚠️ No story work starts until this phase's checkpoint passes.**

- [ ] T006 Write `tests/unit/test_record_accessor.py`:
  - `Package.record(stage, name)` returns the same object as today's region read, for each of `approval`, `assessment`, `comprehension` and `provenance`;
  - `Package.write_record(stage, name, obj)` followed by `record` round-trips;
  - with records still inside the regions, the full existing suite's documents are byte-identical after a write-then-read of an unchanged object.
- [ ] T007 Add `Package.record()` and `Package.write_record()` to `eil/package.py`. For now they read and write the regions, exactly as today. Replace every direct `read_provenance`, `read_region` and `write_region` of the four JSON regions with them:
  - `eil/provenance.py`, `eil/reviews.py`, `eil/staleness.py`, `eil/blockstatus.py`, `eil/corrections.py`, `eil/changelog.py`;
  - `eil/records.py`, `eil/gates.py`, `eil/comprehension.py`, `eil/overview.py`, `eil/impact.py`, `eil/package.py`.

  The changelog region keeps its own writer.

**Checkpoint**: T006 passes and the full existing suite (`pytest`) passes unchanged. `grep -n "read_region\|write_region\|read_provenance" eil/*.py` shows uses only inside `blocks.py`, `package.py` and the changelog writer.

---

## Phase 3: User Story 1 - Every change lands on the intended story (Priority: P1) 🎯 MVP

**Goal**:
- starting a story moves the pointer;
- every write names its story;
- an ambiguous write is refused before anything is touched;
- a start on an unexpected branch waits for a person.

**Independent Test**: B-29 on the `two_stories` fixture.

### Tests for User Story 1

- [ ] T008 [P] [US1] Write `tests/unit/test_target.py` for determinism requirements 38 and 40:
  - resolution returns `directory`, `source` and `candidates` for argument, environment, pointer and none;
  - each ambiguity rule of data-model §Story target;
  - the test walks the `writes`/`read-only` table in `cli.py`. Each writes subcommand exits `1` `ambiguous-story` on `two_stories` and leaves `files_snapshot` unchanged; each read-only one exits `0`; every JSON result carries `story`.
- [ ] T009 [P] [US1] Write `tests/unit/test_branch_guard.py` for determinism requirements 39 and 41:
  - `start` for B with the pointer on A writes the pointer to B and returns `pointer.previous`;
  - the branch is refused on `001-x`, allowed on `main`, `master`, `002-b`, `002-other` and a configured `trunk`;
  - `--on-branch 001-x --by Ada` records `story.start.branch_confirmed_by`;
  - no repository or a detached HEAD gives `branch: null` with a note.
- [ ] T010 [P] [US1] Write `tests/scenario/test_b29_story_targeting.py`, the full B-29 flow from quickstart.md, including that A's approved `assessment` is byte-identical after a refused `check --judgments`.
- [ ] T011 [P] [US1] Add `test_pointer_not_reused` to `tests/contract/test_prompt_guidance.py`. `commands/speckit.specify.md` and `extensions/eil/commands/speckit.eil.requirements.md` must state:
  - the pointer is not reused when it names a governed story;
  - `--feature-dir` is always passed;
  - on `unexpected-branch`, a person is asked to switch or confirm.

### Implementation for User Story 1

- [ ] T012 [US1] Create `eil/target.py`: `resolve_target(cwd, argument, env) -> Target(directory, source, candidates)` and `is_ambiguous(target, project)`, applying the three rules (D-46). Detecting "completion approved" uses `Package.state("completion")`.
- [ ] T013 [US1] Add the branch guard to `eil/target.py`:
  - `current_branch(project)` runs `git symbolic-ref --short -q HEAD`, read-only, as in `eil/identity.py`, and returns `None` on any failure;
  - `branch_expected(branch, story_dir, main_branches)` applies the D-47 rule.

  Read `main_branches` in `eil/identity.py`'s configuration loader (default `[main, master]`). Add the key to `extensions/eil/config-template.yml`.
- [ ] T014 [US1] In `eil/cli.py`:
  - add the `writes`/`read-only` table (contracts/cli.md §Every subcommand);
  - refuse `ambiguous-story` for writes before dispatch;
  - add `story` to every result, and the `Story <name>: ` text prefix;
  - make `_persist_feature_json` always write and return `pointer: {previous, current}`;
  - add `--on-branch` and the `unexpected-branch` refusal to `start`, recording the confirmation in the story record (in the overview until US2 adds the record file).
- [ ] T015 [US1] Update `commands/speckit.specify.md` and `extensions/eil/commands/speckit.eil.requirements.md` (step 1): never reuse a pointer naming a governed story; always pass `--feature-dir`; handle `unexpected-branch` by asking the person and passing their name.
- [ ] T016 [US1] Add a CHANGELOG entry (Unreleased) for change 8 to `CHANGELOG.md`. It adds a story choice only when ambiguous, and a branch confirmation only on an unexpected branch (both decisions). It removes naming the story on every call.

**Checkpoint**: T008 to T011 pass, along with the existing suite. US1 ships alone: no write can reach the wrong story.

---

## Phase 4: User Story 2 - Stage documents hold content, not bookkeeping (Priority: P1)

**Goal**:
- every JSON record lives in `eil-record.json`;
- regions hold one rendered line each;
- `eil show` gives a clean view;
- the `[ai-draft]` cue leaves the document text;
- no fingerprint moves.

**Independent Test**: B-31 on the reference story.

### Tests for User Story 2

- [ ] T017 [P] [US2] Write `tests/unit/test_recordfile.py` for determinism requirements 42 to 44:
  - the schema and allowed keys (data-model §Record file), and sorted two-space output;
  - `malformed-record-file`;
  - `sync` migrates every JSON region and every stage document's `fingerprint` is unchanged;
  - half-migrated `status` reads both forms and writes nothing;
  - deleting the file makes each approved stage `needs-re-review` with reason "approval record missing or unreadable", never `approved`.
- [ ] T018 [P] [US2] Write `tests/unit/test_show.py` for determinism requirement 45:
  - no region body except rendered lines, and no HTML comment;
  - the cue appears after exactly the `needs-review` blocks;
  - `--items` and `--section` work;
  - an unknown id gives `unknown-item`;
  - JSON `blocks` with key, status and line range;
  - `show` writes nothing.
- [ ] T019 [P] [US2] Write `tests/unit/test_ai_draft_cue.py` (replacing its 002 assertions):
  - the helper writes no `[ai-draft]` into any document after classify, answer or sync;
  - `sync` strips existing tags without changing a fingerprint;
  - an agent-style text replacement of a block's original text succeeds after classification (FR-037).
- [ ] T020 [P] [US2] Write `tests/scenario/test_b31_record_file.py`, the B-31 flow. It also asserts that on the reference story the record portion left in each stage document is under 10% of its bytes.
- [ ] T021 [P] [US2] Add `test_show_not_raw` to `tests/contract/test_prompt_guidance.py`. Every stage command and wrap must read stages with `eil show` and say that `eil-record.json` is never read.

### Implementation for User Story 2

- [ ] T022 [US2] Create `eil/recordfile.py`:
  - load, validate (reusing `blocks.provenance_problems` and the other allowed-keys checks), save with sorted keys;
  - `migrate(package)`, which moves JSON region bodies into the file, and moves the branch confirmation US1 stored in the overview into `story.start`.
- [ ] T023 [US2] In `eil/package.py`, switch `record()` and `write_record()` to the file, with a JSON-region fallback. Add the `approval-record-missing` and `malformed-record-file` findings, and the resulting `needs-re-review` reason.
- [ ] T024 [US2] In `eil/blocks.py`, add rendered-line writers for each region (data-model §Marked regions). Keep the JSON-body reader for unmigrated documents. Add `strip_ai_draft(text)`.
- [ ] T025 [US2] In `eil/provenance.py`, remove the cue writing from `classify`, `reclassify` and the review settle paths (`render_stage_cues`, `refresh_cues`), and from any caller in `eil/reviews.py` and `eil/cli.py`. Status stays hash-based.
- [ ] T026 [US2] Wire migration and tag stripping into `sync` in `eil/cli.py`. `status` and `check` without `--judgments` stay read-only.
- [ ] T027 [US2] Create `eil/show.py` (D-49). Add the `show` subcommand (read-only) to `eil/cli.py`.
- [ ] T028 [US2] In `eil/overview.py`, add per-stage counts of blocks needing review (R-26) and the branch confirmation from `story.start`.
- [ ] T029 [US2] Update every stage command in `extensions/eil/commands/` and every wrap in `commands/` to read stages with `eil show` (or `--items`) and never read `eil-record.json`.
- [ ] T099 [US2] Switch the shared test utilities (`tests/helpers/package.py`, `tests/helpers/derived.py`, `tests/helpers/changes.py` and `tests/conftest.py`) and every test that reads a record from document text to read through `Package.record()`. Keep building JSON-region fixtures where a test covers an unmigrated document (the fallback path). The suite must pass with the same assertions: no test is weakened, skipped or deleted to make it pass. Numbered T099 because it was added after analysis.
- [ ] T030 [US2] Add a CHANGELOG entry for change 7 to `CHANGELOG.md`: no interaction added or removed; the agent's context and the developer's reading are reduced. It also records the cue change (amends 002 FR-046).

**Checkpoint**: T017 to T021 pass, and the full existing suite passes after T099. On the reference story every fingerprint and approval is unchanged before and after `sync`. US1 and US2 together form the MVP.

---

## Phase 5: User Story 3 - Reviews are sized to the list (Priority: P1)

**Goal**: one-at-a-time or summary mode by size; answers stored per entry in a session; "ok to the rest"; scaffolding sections as one entry; no settled block ever listed.

**Independent Test**: B-32.

### Tests for User Story 3

- [ ] T031 [P] [US3] Write `tests/unit/test_list_modes.py` for determinism requirements 46 and 48:
  - 8 entries → `one-at-a-time`, 9 → `summary`, threshold 3 → summary at 4;
  - `groups` and `summary` (title or first sentence, at most 120 characters);
  - 12 Actors blocks → one `§Actors` entry, and answering it settles all 12;
  - no list of any kind contains a `settled` or `settled-pending` block;
  - `review show --entry|--group|--all` is read-only.
- [ ] T032 [P] [US3] Write `tests/unit/test_review_sessions.py` for determinism requirement 47:
  - after `--entry` answers to 3 of 5, a fresh `Package` lists the 2 unanswered entries in the same mode;
  - changing an answered entry's text makes it unanswered again;
  - `--rest` records `seen: false` and closes the session through the existing apply path;
  - authority, conflict and verbatim-reply rules apply per entry;
  - a partial session settles nothing;
  - `--entry` with an unknown key gives `unknown-entry`;
  - every acceptance record, whole-list or per entry, stores `mode`, and stores ids and hashes only, never entry text.
- [ ] T033 [P] [US3] Write `tests/scenario/test_b32_list_modes.py`, the B-32 flow (5 entries, compaction stand-in, `--rest`; 38 entries in summary).
- [ ] T034 [P] [US3] Add `test_list_mode_no_tally` to `tests/contract/test_prompt_guidance.py`. Each command that presents a list must:
  - follow the helper's `mode`;
  - store each answer with `--entry`;
  - offer "ok to the rest";
  - state that no tally is kept in chat and no block the helper did not return is listed.

### Implementation for User Story 3

- [ ] T035 [US3] In `eil/reviews.py`, add `mode` and `threshold` (read `review.one_at_a_time_max` from configuration, default 8, and add it to `extensions/eil/config-template.yml`), `groups`, deterministic `summary`, and `SCAFFOLDING_SECTIONS` grouping with member settling.
- [ ] T036 [US3] In `eil/reviews.py`, add `mode` to every acceptance record, and add review sessions in the record file (`story.review_sessions`, data-model §Review session):
  - per-entry and rest answers;
  - lapse on a hash change;
  - close and apply through the existing `answer` path.

  `review list` returns the open session's mode and unanswered entries.
- [ ] T037 [US3] In `eil/cli.py`, add `review answer --entry/--rest` and `review show`, with `unknown-entry`.
- [ ] T038 [US3] Update the list-presenting prompts (`speckit.eil.{requirements,functional,technical,ai-spec,5-plan,6-tasks,accept,verify,complete,correct}.md`, and the wraps in `commands/` that present lists) to present lists by mode, store answers per entry and keep no tally.
- [ ] T039 [US3] Add a CHANGELOG entry for change 3 to `CHANGELOG.md`:
  - short lists become one reply per entry, with "ok to the rest" (validation);
  - long lists become one reply on summaries (validation);
  - restated and adopted blocks are never listed (awareness removed);
  - scaffolding sections become one entry each.

**Checkpoint**: T031 to T034 pass. A compaction mid-review loses no answer.

---

## Phase 6: User Story 7 - An upgrade adopts approved work without re-asking (Priority: P2)

**Goal**:
- unchanged approved content is adopted;
- a legacy approval re-signs on one reply;
- no tag is written;
- judgments on unchanged text survive.

**Independent Test**: B-30 on `legacy_upgrade`.

### Tests for User Story 7

- [ ] T040 [US7] Reproduce the trial's judgment loss on `legacy_upgrade` in `tests/unit/test_adoption.py` before changing code:
  - record which `assessment` lists and verdicts the current helper drops on `sync`, and why;
  - write the finding into `specs/003-proportionate-effort/research.md` under D-56.

  If the loss is fully explained by the wrong-story overwrite (fixed by US1), mark the re-keying part of T044 as dropped.
- [ ] T041 [P] [US7] Extend `tests/unit/test_adoption.py` for determinism requirement 50:
  - on `legacy_upgrade`, 0 Functional or Technical blocks `needs-review`;
  - unnumbered unchanged blocks become `adopted-pending`;
  - the stage is `needs-re-review`;
  - `review list --kind changes` holds one `legacy:functional` entry plus the changed blocks;
  - after one confirmer reply and `confirm`, every `adopted-pending` block is `adopted` and `reached` is `re-signed-without-comparison`;
  - no `unreviewed-ai-content` finding at any point.
- [ ] T042 [P] [US7] Write `tests/scenario/test_b30_upgrade_migration.py`, the B-30 flow:
  - `accept` never refuses `no-section-fingerprints`;
  - the approval line and overview show "re-signed without comparison";
  - judgments on unchanged sections survive `sync`;
  - no `[ai-draft]` appears in any document.

### Implementation for User Story 7

- [ ] T043 [US7] In `eil/blockstatus.py`:
  - add class `adopted-pending` and its status `settled-pending`, which is not `needs-review`, appears on no inferred list and raises no `unreviewed-ai-content`;
  - make `adopt` use it for unnumbered blocks when the approval lacks `section_fingerprints` and the document changed.
- [ ] T044 [US7] In `eil/reviews.py` and `eil/provenance.py`:
  - add the `legacy:<stage>` change entry with its fixed statement;
  - re-sign through `review confirm` with `reached: re-signed-without-comparison` (add it to `REACHED` in `eil/package.py`);
  - convert `adopted-pending` to `adopted`;
  - remove the `accept` refusal that pointed at a full re-approval.

  If T040 requires it, re-key assessment records written under an earlier fingerprint rule in `eil/recordfile.py`'s migration.
- [ ] T045 [US7] Render `re-signed without comparison` wherever approvals are shown: in `eil/records.py` (the approval line), `eil/overview.py` and `eil/trace.py`.
- [ ] T046 [US7] Update `extensions/eil/commands/speckit.eil.accept.md`: on a legacy approval, show the helper's statement and ask for the one reply. Never point to a full re-approval.
- [ ] T047 [US7] Add a CHANGELOG entry for change 2 to `CHANGELOG.md`:
  - re-review of unchanged approved blocks after upgrade is removed;
  - a full re-approval of a legacy approval is replaced by one reply (approval), marked as given without a comparison.

**Checkpoint**: T040 to T042 pass. The quickstart's manual check on a scratch copy of `bd7a0d5` shows 0 blocks needing review in Functional and Technical.

---

## Phase 7: User Story 9 - The helper does not get in its own way (Priority: P3)

**Goal**: additive classify, exempt plan headings, the challenge severity stated, and `reviewed`/`done` states.

**Independent Test**: B-36.

### Tests for User Story 9

- [ ] T048 [P] [US9] Extend `tests/unit/test_classify.py` for determinism requirement 49:
  - classifying {A} after {A, B} leaves B unchanged, including a restated numbered B;
  - an unknown key goes to `skipped` with the section's current keys, and the call exits `0`;
  - all keys unknown gives exit `2` `nothing-classified`.
- [ ] T049 [P] [US9] Extend `tests/unit/test_gates_aispec.py`: a plan with `## Change Log` and `## Record` and no `(traces:)` on them reports no `plan-not-derivable` for them.
- [ ] T050 [P] [US9] Extend `tests/unit/test_status.py`:
  - ai-spec, plan, tasks and verification reach `reviewed` when the document exists, code criteria are met and no block is `needs-review` or `stale`, and fall back to `draft` when that stops holding;
  - `current_stage` skips `reviewed`;
  - after completion is approved, `next_action.kind` is `done`, its text is "Story complete; approved by …", and no output contains "Continue verification".
- [ ] T051 [P] [US9] Write `tests/scenario/test_b36_defects.py`, the B-36 flow.
- [ ] T052 [P] [US9] Add `test_challenge_severity_written` to `tests/contract/test_prompt_guidance.py`: every prompt containing `challenge add` shows `--severity` and says it is required.

### Implementation for User Story 9

- [ ] T053 [US9] In `eil/provenance.py`, make `classify` additive and return `skipped` (D-57). In `eil/cli.py`, add exit `2` `nothing-classified`.
- [ ] T054 [US9] In `eil/gates.py`, build `_PLAN_EXEMPT` from `trace.ADMINISTRATIVE_SECTIONS` plus the plan's own non-derived headings.
- [ ] T055 [US9] Add the `reviewed` state:
  - to `STAGE_STATES`, `state()` and `current_stage()` in `eil/package.py`;
  - the `done` next action after completion approval in `eil/overview.py`.

  Update `extensions/eil/commands/speckit.eil.status.md` and `speckit.eil.next.md` to report both.
- [ ] T056 [US9] Add `--severity high|medium|low` and "required" to every `challenge add` example in `extensions/eil/commands/` (the challenge, comprehend, requirements, functional, technical, ai-spec, plan, tasks and verify prompts) and in the wraps in `commands/`.
- [ ] T057 [US9] Add a CHANGELOG entry for change 9 to `CHANGELOG.md`: no interaction added or removed. It removes retries, false trace clauses and the misleading "Continue verification".

**Checkpoint**: T048 to T052 pass.

---

## Phase 8: User Story 5 - The developer is asked about behaviour, not mechanism (Priority: P2)

**Goal**: choices with no observable effect become `ai-decided` decisions with a reason, validated on the review list. Only observable choices are asked, each with a recommendation.

**Independent Test**: B-34.

### Tests for User Story 5

- [ ] T058 [P] [US5] Write `tests/unit/test_ai_decided.py`:
  - `Owner: ai-decided` without `Reason:` gives the `ai-decided-without-reason` finding, and the technical gate is not met;
  - with a reason, it is met;
  - an `ai-decided` DEC is always classified `inferred`, even when it cites settled sources;
  - it is in the inferred list's "AI-decided decisions" group;
  - the approval record holds `ai_decided`, and the rendered line names them;
  - rewriting the owner to a person re-surfaces the block once.
- [ ] T059 [P] [US5] Write `tests/scenario/test_b34_ai_decided.py`, the B-34 flow.
- [ ] T060 [P] [US5] Add `test_mechanism_not_asked` to `tests/contract/test_prompt_guidance.py`:
  - the technical prompt asks only observable, scope or trade-off choices, with a recommended option; records the rest as `Owner: ai-decided` with `Reason:`; asks when unsure; names them in the summary;
  - the functional prompt never asks about mechanism;
  - the narrowed "a technical decision is the developer's" wording is present.

### Implementation for User Story 5

- [ ] T061 [US5] In `eil/gates.py`, accept `Owner: ai-decided` only with a non-empty `Reason:` (D-53). Any other owner must still be a person.
- [ ] T062 [US5] In `eil/provenance.py`:
  - always classify an `ai-decided` DEC as `inferred`;
  - in `eil/reviews.py`, group such DECs as "AI-decided decisions";
  - in `eil/records.py`, record `ai_decided` on approval and in the rendered line.
- [ ] T063 [US5] Update `extensions/eil/commands/speckit.eil.technical.md` and `speckit.eil.functional.md` per contracts/commands.md. Narrow the `developer-choice-recorded` probe text in `docs/trials.md`.
- [ ] T064 [US5] Add a CHANGELOG entry for change 4 to `CHANGELOG.md`:
  - questions about mechanism are removed (a decision becomes validation on the existing list);
  - observable questions are unchanged, now with a recommended option.

**Checkpoint**: T058 to T060 pass.

---

## Phase 9: User Story 6 - The comprehension check respects what the developer already knows (Priority: P2)

**Goal**: the person's own decisions are not asked (recorded `own-decision`); a one-line waiver; items shown first; behaviour questions; re-reading before a hint.

**Independent Test**: B-35.

### Tests for User Story 6

- [ ] T065 [P] [US6] Extend `tests/unit/test_comprehension.py` for determinism requirement 51:
  - `plan --by Ada` never targets a settled DEC owned by Ada, or a `decided` block whose record names Ada;
  - it takes the next eligible item;
  - with none left, the level is `own-decision` with the DEC id;
  - `record --outcome own-decision` is refused `not-own-decision` unless planned;
  - `waive` records every unrecorded level as `skipped` with `waived: true` and the reason, and gives `reason-required` and `nothing-to-waive`;
  - `own_decision` appears in the counts.
- [ ] T066 [P] [US6] Write `tests/scenario/test_b35_comprehension.py`, the B-35 flow, including the approval record and overview counts.
- [ ] T067 [P] [US6] Add `test_item_shown_before_question` and `test_behaviour_questions_and_reread` to `tests/contract/test_prompt_guidance.py`, against `extensions/eil/commands/speckit.eil.comprehend.md`.

### Implementation for User Story 6

- [ ] T068 [US6] In `eil/comprehension.py`:
  - add `own-decision` to `OUTCOMES` and `own_decision` to `COUNT_KEYS`;
  - add `--by` exclusion in `plan`, and the `own-decision` level;
  - add `waive`.

  Wire `comprehension plan --by` and `comprehension waive` in `eil/cli.py`. Show `own-decision` in `eil/overview.py`.
- [ ] T069 [US6] Update `extensions/eil/commands/speckit.eil.comprehend.md`:
  - pass `--by`;
  - show each item with `eil show --items` first;
  - ask about behaviour;
  - judge on meaning and re-read before hinting;
  - offer the waiver;
  - never ask an `own-decision` level.
- [ ] T070 [US6] Add a CHANGELOG entry for change 5 to `CHANGELOG.md`:
  - questions about the person's own current decisions are removed (understanding);
  - one skip per level becomes one waiver with a reason (decision);
  - the item is shown before each question.

**Checkpoint**: T065 to T067 pass.

---

## Phase 10: User Story 8 - Gaps are found while drafting, not after review (Priority: P3)

**Goal**: the drafting pass scans the comprehension targets before the first review list.

**Independent Test**: probe P-27, and the contract test below. This is prompt-only (Tier 2), and the helper's `comprehension plan` is already read-only.

- [ ] T071 [P] [US8] Add `test_gap_scan_while_drafting` to `tests/contract/test_prompt_guidance.py`. The functional and technical prompts (the two stages with a comprehension check) must run `eil comprehension plan --stage <stage>` before the first inferred list, check those targets for silent, ambiguous or self-contradicting text, and raise challenges first.
- [ ] T072 [US8] Add that step to `extensions/eil/commands/speckit.eil.functional.md` and `speckit.eil.technical.md`. Keep the comprehension prompt's pre-scan as the backstop.
- [ ] T073 [US8] Add a CHANGELOG entry for change 6 to `CHANGELOG.md`: a second review round after late gaps is removed where drafting finds them.

**Checkpoint**: T071 passes.

---

## Phase 11: User Story 4 - A small story takes a short path, authorised once (Priority: P2)

**Goal**: one authorised profile per story, bringing no wireframe exports, one combined derived review, two comprehension levels, and unchanged approvals.

**Independent Test**: B-33 and SC-005.

**Depends on**: US3 (lists), US5 and US6 (comprehension levels).

### Tests for User Story 4

- [ ] T074 [P] [US4] Write `tests/unit/test_profile.py` for determinism requirement 52:
  - `profile set` refusals: `not-an-authoriser`, `reason-required`, `profile-active`;
  - `withdraw` refusals: `no-profile`;
  - the Functional wireframe criterion is met with reason `small-story profile (by, at)`;
  - `comprehension plan` gives `explain` and `apply` only, the rest `not-applicable`;
  - `review list --stage derived` is refused `no-profile` without the profile and is the union with it;
  - `enter plan` and `enter tasks` proceed past unreviewed inferred upstream, and `enter implement` refuses until the derived list is answered;
  - `profile set` records the scoped override of `unreviewed-ai-content`, which `status` and the overview show as an override, and `withdraw` withdraws it;
  - after `withdraw`, everything reverts for stages not yet approved, and an approved Functional stage keeps `profile: small` in its record.
- [ ] T075 [P] [US4] Write `tests/scenario/test_b33_profile.py`, the B-33 flow. It asserts that every approval is still required.
- [ ] T076 [P] [US4] Extend `tests/scenario/test_interaction_count.py` with a profile run on the reference story. Developer replies from requirements to implementation must fall by at least 50% against the 002 count, while approvals and observable decisions stay equal (SC-005).
- [ ] T077 [P] [US4] Add `test_profile_proposed_not_authorised` to `tests/contract/test_prompt_guidance.py`:
  - the specify wrap, requirements and abbreviate prompts may propose the profile, naming signals and labelling it `AI assessment:`;
  - they ask who authorises and why, and never run `profile set` without the person's words;
  - they say when the story outgrows the profile.

  Update the existing abbreviation-not-authorised assertion so it still holds.

### Implementation for User Story 4

- [ ] T078 [US4] Create `eil/profile.py` (set, withdraw and the effects query) using `abbreviation_authorisers`. Store the profile in the record file under `story.profile`. Add the `profile` subcommand to `eil/cli.py`.
- [ ] T079 [US4] Apply the effects:
  - the Functional wireframe criterion in `eil/gates.py`;
  - the `derived` pseudo-stage list and its settling in `eil/reviews.py`;
  - the scoped override recorded and withdrawn with the profile, through the existing override path in `eil/records.py`, which `enter` in `eil/handoff.py` honours;
  - levels in `eil/comprehension.py`;
  - `profile` on approval records in `eil/records.py`;
  - the profile line in `eil/overview.py` and `eil/trace.py`.
- [ ] T080 [US4] Update the prompts:
  - `commands/speckit.specify.md`, `speckit.eil.requirements.md` and `speckit.eil.abbreviate.md` (proposal and set/withdraw);
  - `speckit.eil.functional.md` (no exports under the profile);
  - `speckit.eil.ai-spec.md`, `speckit.eil.5-plan.md` and `speckit.eil.6-tasks.md` (one derived list after tasks).
- [ ] T081 [US4] Add a CHANGELOG entry for change 1 to `CHANGELOG.md`:
  - one authorisation per story is added (decision);
  - wireframe exports are removed under the profile;
  - three derived lists become one (validation);
  - comprehension is cut to two levels.

**Checkpoint**: T074 to T077 pass. SC-005 is met.

---

## Phase 12: User Story 10 - Approving takes one word (Priority: P2)

**Goal**: the helper's question states what is confirmed; "ok" approves and is recorded with that question; the name is asked once per session.

**Independent Test**: B-37.

**Depends on**: constitution PATCH 1.2.2 applied (`/speckit-constitution`, see `constitution-patch-1.2.2.md`).

### Tests for User Story 10

- [ ] T092 [P] [US10] Extend `tests/unit/test_records_approval.py` for determinism requirement 53: `APPROVAL_QUESTIONS` covers every approvable stage; `approve --attestation ok` records `attestation: "ok"` and the stage's `question`; `review confirm` records its question too; `status` gives `next_action.question` when the next step is an approval; the rendered approval line contains the reply and the question; an empty reply is still refused `attestation-required`; the branch confirmation stores `reply` and its fixed `question`, and `comprehension waive` stores its fixed `question`.
- [ ] T093 [P] [US10] Write `tests/scenario/test_b37_short_approval.py`, the B-37 flow.
- [ ] T094 [P] [US10] Add `test_short_approval_accepted` to `tests/contract/test_prompt_guidance.py`: `speckit.eil.approve.md`, `speckit.eil.complete.md` and `speckit.eil.accept.md` ask the helper's question, accept a one-word reply as given, contain no full-sentence example presented as required wording, ask the name once per session, and still never supply the reply. Keep the existing `never supply the attestation` assertion passing.

### Implementation for User Story 10

- [ ] T095 [US10] In `eil/records.py`, add `APPROVAL_QUESTIONS` and record `question` on `approve` and on `review confirm` (`eil/reviews.py`); render it in the approval line. In `eil/overview.py`, add `next_action.question`. Record the fixed question and reply on the branch confirmation (`eil/target.py`, `eil/cli.py` `--reply`) and the question on the comprehension waiver (`eil/comprehension.py`).
- [ ] T096 [US10] Update `extensions/eil/commands/speckit.eil.approve.md`, `speckit.eil.complete.md` and `speckit.eil.accept.md` per contracts/commands.md.
- [ ] T097 [US10] Add a CHANGELOG entry for change 10 to `CHANGELOG.md`: a written attestation is replaced by a one-word reply to a stated question (approval); the name is asked once per session (repetition removed).

**Checkpoint**: T092 to T094 pass.

---

## Phase 13: Polish and cross-cutting concerns

- [ ] T082 [P] Extend `tests/unit/test_performance.py`. `status`, `check`, `enter` and `show` stay under 1 s on the 002 performance fixture after migration to the record file.
- [ ] T083 [P] Add probes P-23 to P-31 (contracts/commands.md, last table) to `docs/trials.md`, with the same pass rule as 002. Add an SC-003/SC-004 timing protocol under SC-010: one small story under the profile, recording total, process and implementation minutes and the compaction count.
- [ ] T084 [P] Update `README.md`:
  - what the developer is asked now (profile, list modes, `ai-decided`, own-decision, waiver, `show`);
  - attestation limits: the record file (R-25), the cue being absent from raw documents (R-26), summary-mode acceptance and `seen: false` (R-24), `ai-decided` as the AI's labelled judgement (R-23).
- [ ] T085 Add amendment notes citing 003:
  - in `specs/001-staged-definition-workflow/spec.md` (Constraints on the Solution: the record file beside the nine documents);
  - in `specs/002-proportionate-revalidation/spec.md` (FR-010 summary mode, FR-036 `ai-decided` decisions settled on the review list, FR-038 two comprehension levels under the profile, FR-046 cue, FR-047 adoption, and the records-inside-documents assumption).
- [ ] T086 Fold the three delta contracts into `specs/001-staged-definition-workflow/contracts/cli.md`, `document-format.md` and `commands.md`, in the same change as the tests that pin them (Constitution workflow).
- [ ] T087 [P] Extend `tests/contract/test_install.py`: the new configuration keys `main_branches` and `review.one_at_a_time_max` are in the installed `config-template.yml`, and `eil-record.json` survives extension removal (`tests/contract/test_removal_and_coexistence.py`).
- [ ] T088 Run `ruff check` and the full `pytest` suite, including the contract tests against a scratch Spec Kit project. Fix any failures.
- [ ] T089 Run the quickstart's manual check on a scratch copy of the trial project at `bd7a0d5`, never the original. Record the before and after numbers (blocks needing review; `s06-tasks.md` bytes) in `specs/003-proportionate-effort/research.md` under Evidence.
- [ ] T090 Run `/speckit-analyze` after these tasks change and before implementation begins (Constitution workflow). Fix any CRITICAL finding in the spec, plan or tasks. Confirm by grep that no prompt or code path lets the AI authorise the profile, waive a level, answer a list or record an approval (FR-045), and that every Tier 1 rule in contracts/cli.md has a unit test (FR-046).
- [ ] T100 After release, run the human timing trial for SC-003, SC-004 and SC-007 (protocol from T083) on one small story under the profile, and record the results in `docs/trials.md`. Numbered T100 because it was added after analysis; it does not block the pull request.
- [ ] T091 Draft the pull request description. It names the principles touched (I to IV), confirms that no gate, refusal or record exists only in a prompt, names the contract test and probe for each of the ten Tier 2 rules, and copies the spec's Principle IV table of interactions added and removed, with purpose.

---

## Dependencies and execution order

### Phase dependencies

- **Setup (T098, T001 to T005)**: T098 (constitution PATCH, numbered last because it was added after analysis) and T001 first, with the owner's answer, before anything else touches the tree.
- **Foundational (T006 to T007)**: after Setup. It blocks every story.
- **US1 (Phase 3)**: after Foundational. Done first because it protects every later write (plan, delivery step 1).
- **US2 (Phase 4)**: after US1. The record file needs `story.start` and the targeting table.
- **US3 (Phase 5)**: after US2. Sessions live in the record file.
- **US7 (Phase 6)**: after US2 (migration and no cue) and US3 (the legacy entry is a list entry).
- **US9 (Phase 7)**: after Foundational. Independent of other stories, but it shares `provenance.py` and `cli.py` with US2 and US7, so it is scheduled after them.
- **US5 (Phase 8)**: after US3 (the list group).
- **US6 (Phase 9)**: after US2 (`show --items` in the prompt). Independent of US5 except that both edit `comprehension.py` and `cli.py`.
- **US8 (Phase 10)**: after US6 (it relies on `comprehension plan` semantics). Prompt-only.
- **US4 (Phase 11)**: after US3, US5 and US6.
- **US10 (Phase 12)**: after US2 (rendered approval line) and T098. Independent of the other stories.
- **Polish (Phase 13)**: after every story. T090 is last before implementation.

### Story order at a glance

```text
Setup → Foundational → US1 → US2 ─┬─ US3 ─┬─ US7
                                  │       ├─ US5 ─┐
                                  ├─ US9  │       ├─ US4 → Polish
                                  └─ US6 ─┴─ US8 ─┘
```

### Within each story

Write the tests, see them fail, then the helper modules, then CLI wiring, then prompts, then the scenario, then the CHANGELOG entry.

## Parallel examples

```text
# Setup fixtures:
T003 legacy_upgrade.py   T004 two_stories.py

# US1 tests together:
T008 test_target.py   T009 test_branch_guard.py   T010 B-29   T011 contract

# US2 tests together:
T017 test_recordfile.py   T018 test_show.py   T019 test_ai_draft_cue.py   T020 B-31   T021 contract

# After US2, with two developers:
Developer A: US3 → US7 → US5        Developer B: US9, US6 → US8
Then together: US4

# Polish:
T082 performance   T083 trials   T084 README   T087 install contract
```

## Implementation strategy

- **MVP**: Setup, Foundational, **US1** and **US2** (both P1). This stops wrong-story damage and removes the record bulk behind the context exhaustion. Validate with B-29 and B-31 and the trial manual check, steps 3 and 4.
- **Increment 2**: US3 (P1) and US7. Lists sized to the developer, and upgrades that ask nothing needless. Validate with B-30 and B-32.
- **Increment 3**: US9, US5, US6 and US8. Defects, and asking at the right level. Validate with B-34 to B-36.
- **Increment 4**: US4, the profile, then Polish. SC-005 is measured by T076; SC-003 and SC-004 need the timed human run in T083.
- At every checkpoint the full existing suite passes. Each increment's pull request copies the Principle IV rows for its changes.
