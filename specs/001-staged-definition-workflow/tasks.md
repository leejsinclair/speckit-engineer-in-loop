---
description: "Task list for the Staged Definition Workflow (Engineer-in-the-Loop preset and extension)"
---

# Tasks: Staged Definition Workflow (Engineer-in-the-Loop Preset)

**Input**: Design documents from `specs/001-staged-definition-workflow/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/ (cli.md, document-format.md, manifests.md, commands.md), quickstart.md

**Tests**: Included. The plan requires them (Technical Context: unit, contract and scenario tests). Each story writes its tests first, confirms they fail, then implements. Scenario tests drive the `eil` helper directly, as the slash commands would; the parts that depend on an AI agent following instructions are covered by the human trials in `docs/trials.md`, not automated (research D-15).

**Organization**: Tasks are grouped by user story. Artefact (FR-071..086) and comprehension-check (FR-087..094) requirements have no user story of their own, so their tasks sit in the story whose stage owns them: context diagram in US1, functional artefacts, exports and the comprehension check in US3, technical artefacts in US4, artefact references and coverage in US5, artefact verification in US7.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1 to US9 (user stories in spec.md)
- Paths are relative to the repository root. The helper is `extensions/eil/scripts/python/eil/`.
- Files that several tasks append to (`preset.yml`, `extensions/eil/extension.yml`, `cli.py`, `gates.py`) are edited one task at a time, so those tasks are not marked [P].

## Notes

- This feature's own directory is not a governed package (no `s00-README.md`), so it keeps ordinary Spec Kit names (plan.md, FR-006, FR-069).
- Two gaps found while writing these tasks are closed: `check` needs a way to receive AI judgments (`--judgments`, now in contracts/cli.md and built in the requirements phase), and `python3 <dir>` runs `__main__.py` with the package's own directory on the path, so it must add the parent directory itself (foundational phase).
- After `/speckit-analyze` (2026-09-25) these decisions were applied: artefact requirements apply to every use case, screen state and new or changed container, each with a recorded not-applicable reason as the only way out (spec FR-073, FR-074); identifiers use the spelling `artifact`; the constitution is ratified first (T001).
- **Order of risk**: C-03 and C-05 run first and can change the design.

---
## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Repository skeleton, tooling and test scaffolding.

- [x] T001 Ratify the project constitution: run `/speckit-constitution` with the developer, so `.specify/memory/constitution.md` holds real principles (human-owned; the AI proposes, the developer decides). Then re-run the plan's Constitution Check and update its table in `specs/001-staged-definition-workflow/plan.md`; anything the principles reject becomes a Complexity Tracking entry or a design change before Phase 2. *Done 2026-09-25: v1.0.0, amended to v1.1.0 after analysis finding D1; plan table re-run.*
- [x] T002 Create the repository skeleton from plan.md at the repository root: `templates/`, `commands/`, `extensions/eil/commands/`, `extensions/eil/scripts/python/eil/`, `tests/unit/`, `tests/contract/`, `tests/scenario/`, `tests/fixtures/`, `tests/helpers/`
- [x] T003 Create `pyproject.toml`: Python >=3.11, no runtime dependencies (research D-04), dev-only `pytest`, pytest markers `contract`, `scenario`, `slow`, `testpaths = ["tests"]`, and a `ruff` config
- [x] T004 [P] Create `.gitignore` and `extensions/eil/.extensionignore` (caches out of installs; Spec Kit reads it from the extension's own directory, and a preset has no ignore mechanism, so installs use a staged copy of the shipped files, research F-16; contract test C-01 asserts the installed directories carry only shipped files) and `.github/pull_request_template.md` carrying the constitution's checklist: which principles the change touches; no gate, refusal or record exists only in a prompt (Principle I, tier 1); the contract test or trial probe for each new behavioural rule in a prompt (tier 2); the new tests were seen to fail before the code (Principle III); a contract file change lands with its tests
- [x] T005 [P] Create `LICENSE` (MIT), `CHANGELOG.md` (Unreleased section) and `README.md` skeleton with headings Install, Configure, Use, Remove, Trials
- [x] T006 [P] Create `tests/helpers/scratch.py`: build a scratch Spec Kit project in a temp directory (`git init`, set `user.name`/`user.email`, `specify init --here --integration claude`, baseline commit) and helpers to install/remove the extension and preset with `--dev`; skip the test when `specify` is not on PATH
- [x] T007 [P] Create `tests/helpers/package.py`: builder that writes story-package fixtures (s00 to s08 documents with items, record blocks, approvals) into a temp feature directory for unit and scenario tests
- [x] T008 [P] Create `tests/conftest.py` with fixtures `scratch_project`, `story_dir`, and a `run_eil(args, cwd)` helper that invokes `python3 extensions/eil/scripts/python/eil` and returns exit code, stdout JSON and stderr

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The two design-critical risk checks, then the helper core every story needs.

**⚠️ CRITICAL**: No user story work begins until the risk checkpoint passes. If C-03 or C-05 fails the design changes (plan Open Items, research R-1, R-2).

- [x] T009 RISK SPIKE: create a minimal stub extension `tests/contract/stubs/eil-stub/extension.yml` (one command, one script) and stub preset `tests/contract/stubs/preset-stub/preset.yml` providing a new template `s01-requirements-template`, an override of `spec-template`, and a `wrap` of `speckit.plan` whose body begins with the guard text and contains `{CORE_TEMPLATE}` once
- [x] T010 [P] RISK SPIKE: contract test C-03 in `tests/contract/test_c03_template_resolution.py`: install the stubs into a scratch project and assert `specify preset resolve s01-requirements-template` resolves to the preset file (R-1) and `spec-template` resolves to the preset override
- [x] T011 [P] RISK SPIKE: contract test C-05 in `tests/contract/test_c05_wrap_composition.py`: assert the composed `.claude/skills/speckit-plan/SKILL.md` contains the guard and the helper call before the core plan body (R-2)
- [x] T012 CHECKPOINT: run C-03 and C-05. Record each outcome in `specs/001-staged-definition-workflow/research.md` (rows R-1, R-2). If C-03 fails, apply the D-02 fallback (extension-provided templates) and update `specs/001-staged-definition-workflow/contracts/manifests.md` and `plan.md` before continuing. If C-05 fails, stop and redesign enforcement (D-05)
- [x] T013 [P] Collect Mermaid fixtures in `tests/fixtures/mermaid/`: for each of `C4Context`, `C4Container`, `C4Component`, `sequenceDiagram` and `erDiagram`, one example taken from the Mermaid documentation, one malformed (a line outside the accepted subset) and one borderline (aliases differ, boundary nesting, implied participants); record the Mermaid version in `tests/fixtures/mermaid/VERSION.md` (risk R-10)
- [x] T014 [P] Create sample exports in `tests/fixtures/assets/`: a small valid PNG, SVG, PDF and JPG, a `.gif` (format not allowed), a copy of the PNG with one byte changed (for `artifact-hash-mismatch`), and `README.md` saying what each file is for (used by the export tests)
- [x] T015 Create `extensions/eil/scripts/python/eil/__main__.py`: insert the package's parent directory into `sys.path`, then `from eil.cli import main` and exit with its code, so `python3 .specify/extensions/eil/scripts/python/eil <subcommand>` works from the installed location (contract test C-04); add `extensions/eil/scripts/python/eil/__init__.py`
- [x] T016 [P] Create `extensions/eil/scripts/python/eil/results.py`: `Refusal(code, message, fix)`, `Finding(code, where, message)`, exit-code constants 0 to 4, stable refusal-code registry from contracts/cli.md, and single-object JSON emission (nothing else on stdout under `--json`)
- [x] T017 [P] Write unit tests in `tests/unit/test_fingerprint.py`: the normative test vectors from contracts/document-format.md, formatting-only invariance (CRLF, trailing whitespace, blank-line runs, leading and trailing blanks), change on any other edit, invariance to edits inside `approval`, `assessment` and `comprehension` regions, `not-utf8` handling (determinism requirements 1 and 2)
- [x] T018 Implement `extensions/eil/scripts/python/eil/fingerprint.py` per the normative algorithm in contracts/document-format.md (FR-011, FR-044) so the fingerprint tests pass
- [x] T019 [P] Write unit tests in `tests/unit/test_blocks.py`: marked regions read and write, `malformed-region` on unmatched or nested markers, `eil:` record blocks read and rewrite in place preserving every other byte, `mermaid` fences extracted with line numbers, malformed JSON reported
- [x] T020 Implement `extensions/eil/scripts/python/eil/blocks.py`: region and record-block reading and writing, fence extraction, byte-preserving rewrite (contracts/document-format.md §Marked regions, §Record blocks)
- [x] T021 [P] Write unit tests in `tests/unit/test_items.py`: item-line regex for all ids including `ART`, trailing clauses (`traces`, `code`, `status`, `material`, `store`), tags `[ai-draft]` and `[pending-clarification]`, `duplicate-id`, `dangling-trace`, `malformed-item` (parse failures are findings, risk R-5), task lines `- [ ] T012 …`, item-hash rules including an `ART` attachment
- [x] T022 Implement item parsing and item hashing in `extensions/eil/scripts/python/eil/trace.py` (parse, ids, clauses, tags, hash; no chain or coverage logic yet) so the item tests pass
- [x] T023 [P] Write unit tests in `tests/unit/test_package.py`: feature-directory resolution order (`--feature-dir`, `SPECIFY_FEATURE_DIRECTORY`, `.specify/feature.json`), governed test (`s00-README.md` exists, FR-069), stage document paths, document names all match `s0N-` with a letter prefix and never a bare number (FR-070), derived stage state (`not-started`, `draft`, `in-review`, `approved`, `needs-re-review`) including upstream-fingerprint mismatch (FR-043, FR-044), current stage rule
- [x] T024 Implement `extensions/eil/scripts/python/eil/package.py`: discovery, governed test, document paths, stage derivation from approvals and fingerprints (data-model.md §Stage)
- [x] T025 [P] Write unit tests in `tests/unit/test_cli_skeleton.py`: every subcommand except `start` exits 3 with `{"governed": false}` and changes nothing in an ungoverned directory (determinism 8, FR-069); `--json` prints exactly one object; usage errors exit 2; refusals exit 1 with `refusals[]`
- [x] T026 Implement `extensions/eil/scripts/python/eil/cli.py`: argument parsing for all subcommands in contracts/cli.md (handlers stubbed to `not implemented` until their story), global flags `--json` and `--feature-dir`, exit-code handling, governed check
- [x] T027 [P] Write unit tests in `tests/unit/test_diagrams.py` over the fixtures in `tests/fixtures/mermaid/`: each accepted construct extracts the expected elements and relations; each malformed fixture yields `diagram-unparseable` naming the line, never an empty pass (determinism 10); element names compare case-insensitively with whitespace collapsed
- [x] T028 Implement `extensions/eil/scripts/python/eil/diagrams.py`: line-oriented extraction for the accepted Mermaid subset (contracts/document-format.md §Accepted Mermaid subset), diagram kind from first keyword, element-label normalisation, `diagram-unparseable` findings (FR-080, research D-20)
- [x] T029 [P] Write unit tests in `tests/unit/test_artifacts_inline.py`: `ART` item + attachment pairing (nearest preceding `ART` line, ended by another item line or heading), kind derivation from the fence's first keyword and owning stage, findings `artifact-unregistered`, `artifact-untraced`, `artifact-wrong-level` (kind not permitted in stage per data-model.md §Artefact)
- [x] T030 Implement inline-diagram handling in `extensions/eil/scripts/python/eil/artifacts.py`: pairing, kind derivation, permitted-kind table by stage, findings (FR-071, FR-076, FR-081); export records come in the functional-specification phase

**Checkpoint**: Risk checks C-03 and C-05 recorded as passing; `python3 extensions/eil/scripts/python/eil fingerprint <file>` works; all foundational unit tests pass.

---

## Phase 3: User Story 1 - Install the preset and define approved requirements (Priority: P1) 🎯 MVP

**Goal**: Install the preset and extension, start a story at the Requirements stage, evaluate the requirements gate, and record one human approval.

**Independent Test**: In a fresh Spec Kit project, install the preset and extension, then take one story through Requirements alone: recorded, gate passed, human approval recorded, no functional or technical content required.

- [x] T031 [P] [US1] Write unit tests in `tests/unit/test_gates_requirements.py`: criteria `REQ-G01`..`REQ-G14` as data (13 process-standard criteria plus the context diagram), each `structural`, `traceability` or `judgment`; required headings (FR-014) present or listed under `## Not applicable` with a reason (FR-018); material open question `open` blocks (FR-022, FR-023); context-diagram rules: every person under Users and Stakeholders and every system under Dependencies appears, `[existing]`/`[new]`/`[changed]` markers present (FR-072, FR-079e, f); a wireframe in `s01` gives `artifact-wrong-level`; `check --judgments` merges verdicts only for `judgment` criteria, labels them as the AI's, exits 2 and writes nothing for an unknown id, a non-judgment criterion or a stage mismatch, and leaves a `judgment` criterion with no entry `not-met` (determinism 21)
- [x] T032 [P] [US1] Write unit tests in `tests/unit/test_identity.py`: approver resolution from config, `git config user.name`/`user.email`, `default_developer`; empty list means the story's developer; `not-a-confirmer` for anyone else (FR-013, FR-066)
- [x] T033 [P] [US1] Write unit tests in `tests/unit/test_records_approval.py`: `approve` refusals `unmet-criteria`, `open-question`, `unreviewed-ai-content` (`[ai-draft]` remaining), `attestation-required`, `ai-approval`, `not-a-confirmer`, `not-approvable` (ai-spec, plan, tasks, verification), `stage-not-approved` (prior stage); a successful approval writes name, UTC time, fingerprint, attestation, `upstream` fingerprints and per-item hashes into the `approval` region only; `override` per criterion with `reason-required` and `unknown-criterion`; nothing is written on refusal (determinism 3, 4, 5)
- [x] T034 [P] [US1] Write contract tests C-01, C-02 and C-04 in `tests/contract/test_install.py`: `specify extension add --dev extensions/eil` then `specify preset add --dev .` in a scratch project; assert the commands and templates registered so far (3 commands and no hooks at this stage; the full 15 commands and 4 hooks are asserted after the last command is added), `git status` shows only additions under `.specify/` and the agent's command directory, plus in-place recomposition of the agent's generated skills for wrapped commands and no other tracked change (FR-001, research F-14), the installed directory has no tests or specs, and `python3 .specify/extensions/eil/scripts/python/eil fingerprint README.md` prints `sha256:` + 64 hex
- [x] T035 [P] [US1] Write scenario tests B-01 and B-02 in `tests/scenario/test_b01_b02_start_and_approve.py`, driving the helper as the stage commands would: start creates only `s00` and `s01` and no `spec.md`/`plan.md`/`tasks.md`; approval refused with an open material question, refused for `Mallory`, accepted after the question is accepted, one confirmation suffices (FR-066); `stage-init functional` refused before approval (FR-008); no `assets/` directory exists after `start` (FR-047)
- [x] T036 [US1] Create `extensions/eil/config-template.yml` with `default_developer`, per-stage `approvers` (requirements, functional, technical, completion) and `abbreviation_authorisers`, all empty by default (data-model.md §Approver Configuration)
- [x] T037 [US1] Implement `extensions/eil/scripts/python/eil/identity.py`: read `eil-config.yml` and `local-config.yml`, resolve the story's developer from git identity, check a name against a stage's approvers (FR-013, FR-066, research D-11)
- [x] T038 [P] [US1] Create `templates/s01-requirements-template.md`: every FR-014 heading using the process standard's names, a `## System Context` section with a commented example `ART` item and Mermaid fence, `## Not applicable`, empty Challenges and Overrides sections, and the `assessment` and `approval` marked regions, plus a comment naming the gate
- [x] T039 [US1] Implement `extensions/eil/scripts/python/eil/gates.py`: criteria-as-data loader (id, text, kind), gate evaluation for `structural` and `traceability` criteria, the requirements table `REQ-G01`..`REQ-G13` (G14 is added in a later task), `check --judgments PATH` per contracts/cli.md (merge verdicts for `judgment` criteria into the assessment region as the AI's, reject anything else, leave unsupplied judgment criteria `not-met`), assessment-region writing (written by `check`, excluded from the fingerprint), open-question and `[ai-draft]` detection
- [x] T040 [US1] Implement `extensions/eil/scripts/python/eil/records.py`: approval and override writing (approval region, override record block), per-item hashes and upstream fingerprints (FR-010..013, FR-045, FR-066)
- [x] T041 [US1] Implement the requirements context-diagram criterion `REQ-G14` (the last row of the requirements table) and rules (e) and (f) in `extensions/eil/scripts/python/eil/gates.py` using `extensions/eil/scripts/python/eil/diagrams.py` and `extensions/eil/scripts/python/eil/artifacts.py` (FR-072, FR-079)
- [x] T042 [P] [US1] Create `templates/s00-readme-template.md` (generated-file notice, Story and Status sections only) and add a minimal `overview.py` in the helper that renders it: title, owner, current stage, overall status, nine document rows (the complete overview is built in the next phase)
- [x] T043 [US1] Implement `start`, `stage-init`, `check` (with `--judgments`), `approve`, `override` and `fingerprint` handlers in `extensions/eil/scripts/python/eil/cli.py`: `start` creates `s00` and `s01` and persists `.specify/feature.json`, refusing `already-governed` and `directory-has-spec-md`; `stage-init` refuses `stage-not-approved`, `already-exists`, `unknown-stage` (FR-003, FR-008, FR-048)
- [x] T044 [US1] Create `preset.yml` (id `engineer-in-the-loop`, `requires.speckit_version >=1.0.2.dev0`) with templates `s00-readme-template`, `s01-requirements-template` and the `speckit.specify` replace override entry, following contracts/manifests.md; later phases add their entries
- [x] T045 [P] [US1] Create `commands/speckit.specify.md` (strategy `replace`): guard for the extension, create the feature directory and `.specify/feature.json` as core does but never write `spec.md`, refuse an already-governed feature and name the current stage's command, call `eil start`, then continue as `speckit.eil.requirements` (FR-003, commands.md)
- [x] T046 [P] [US1] Create `extensions/eil/commands/speckit.eil.requirements.md`: guard, `eil start` if ungoverned, draft `s01` with every heading, draft the C4 context diagram as an `ART` item with Mermaid fence and existing/new/changed markers, tag AI text `[ai-draft]`, never turn an open question into an assumption (FR-022), run `eil check` (writing judgments through `--judgments`), report the gate result
- [x] T047 [P] [US1] Create `extensions/eil/commands/speckit.eil.approve.md`: run `eil check`, show the gate result and diff since last approval, ask the human directly for explicit confirmation and optional playback note, pass their words as `--attestation`, never supply it (FR-012, research D-11)
- [x] T048 [P] [US1] Create `extensions/eil/commands/speckit.eil.override.md`: ask the human for the criterion and reason, call `eil override`, state where it will be visible (FR-045)
- [x] T049 [US1] Create `extensions/eil/extension.yml` (id `eil`, `requires.python3`, `provides.scripts` entry for the helper, config entry, commands `requirements`, `approve`, `override`, config defaults) per contracts/manifests.md; later phases append their commands and hooks
- [x] T050 [US1] Write the README Install and First story sections: prerequisites, `specify extension add`, `specify preset add` (extension first, then preset), starting a story, approving Requirements (supports SC-001)

**Checkpoint**: Run C-01, C-02, C-04 and scenarios B-01, B-02; run the MVP by hand in a scratch project. STOP and validate before continuing. Run `tests/contract/test_prompt_guidance.py` (entries for prompts that exist so far).

---

## Phase 4: User Story 2 - Find your way around a story package at a glance (Priority: P2)

**Goal**: A reader opens `s00-README.md` and knows the story's stage, approvals, outstanding items and where every document is, without any hand editing.

**Independent Test**: Start a story and advance it through one gate; the overview reflects the new status and approval with no manual edit and no specification content.

- [x] T051 [P] [US2] Write unit tests in `tests/unit/test_overview.py`: grammar of contracts/document-format.md §Overview (first-line generated notice, sections in fixed order, nine document rows, Approvals, Outstanding, Accepted risks, Abbreviated stages, Mirrors, Artefacts index); output contains only record values and fixed labels, never document prose (FR-055); regeneration is byte-identical (determinism idempotence); the stage documents win over a hand-edited overview and the disagreement is reported (FR-056)
- [x] T052 [P] [US2] Write unit tests in `tests/unit/test_status.py`: `status --json` shape from contracts/cli.md, derived per-stage state, outstanding items, single `next` action, read-only with respect to fingerprints (determinism 9)
- [x] T053 [P] [US2] Write scenario test B-03 in `tests/scenario/test_b03_overview.py`: after each action in B-02 `s00` reflects the change with no manual edit and contains no requirement or design prose; hand-editing `s00` to say `approved` is overridden by derived status
- [x] T054 [US2] Complete `extensions/eil/scripts/python/eil/overview.py`: full overview per contracts/document-format.md (Approvals, Outstanding, Accepted risks per FR-024, Abbreviated stages, Mirrors, Artefacts index per FR-086) rendered from records and fixed labels only (FR-054..056, research D-14)
- [x] T055 [US2] Implement `status`, `overview` and `sync` handlers in `extensions/eil/scripts/python/eil/cli.py`: `status` derives everything and regenerates nothing; `overview` rewrites only `s00`; `sync` regenerates the overview (alias handling is added in the AI Specification phase); wire overview regeneration into `approve`, `override`, `stage-init` and `check`
- [x] T056 [P] [US2] Create `extensions/eil/commands/speckit.eil.status.md`: guard, `eil sync`, `eil status`, report current stage, approvals, outstanding items, alias health and the single next action
- [x] T057 [US2] Append `speckit.eil.status` to `extensions/eil/extension.yml` and register the four `after_clarify`, `after_plan`, `after_tasks`, `after_implement` hooks pointing at it with `optional: false`; hooks carry no refusal (research D-05, F-5)

**Checkpoint**: Run unit overview and status tests and scenario B-03.

---

## Phase 5: User Story 3 - Turn approved requirements into traceable behaviour (Priority: P3)

**Goal**: Produce a functional specification from approved requirements, with traceable behaviour, sequence diagrams, exported wireframes, a comprehension check, and a gate that can be approved.

**Independent Test**: Given approved requirements, produce a functional specification; every FR traces to a requirement, the gate is evaluated, the comprehension check has been taken, and approval can be recorded.

- [x] T058 [P] [US3] Write unit tests in `tests/unit/test_gates_functional.py`: `FUN-G01`..`FUN-G16` as data; FR without `traces:` flagged untraceable and gate not met; REQ with no FR reported uncovered (FR-025, FR-028); implementation prescription and wrong-level artefacts flagged (FR-019, FR-020, FR-081); `FUN-G14` requires a functional sequence diagram per use case, or a recorded not-applicable reason, whose participants are only the declared Actors plus `System`; `FUN-G15` requires a wireframe per screen state for a story with a user interface, or a recorded not-applicable reason per screen (FR-073, FR-075); an ER diagram in `s02` is `artifact-wrong-level`
- [x] T059 [P] [US3] Write unit tests in `tests/unit/test_artifacts_export.py` using `tests/fixtures/assets/`: `artifact register` copies into `assets/`, hashes raw bytes, writes the `eil:artifact` record; refusals `unknown-item`, `artifact-missing`, `artifact-format-not-allowed`, `artifact-no-provenance` (Figma URL without `node-id=`), `artifact-wrong-level`, `path-outside-package`; re-registering is byte-identical for identical input and changes the record and the document fingerprint for a changed file (determinism 12, 15); one changed byte with the record untouched gives `artifact-hash-mismatch` and leaves every fingerprint unchanged (determinism 13); `orphan-asset` finding; the `assets/` directory is created by the first `register` and not before (FR-047); `image` kind is recorded as not structurally checked
- [x] T060 [P] [US3] Write unit tests in `tests/unit/test_comprehension.py`: deterministic target selection for the same fingerprint, level and attempt on repeated runs and a different attempt giving a different target (determinism 17); after a challenge is answered the plan is re-run on the new version (FR-091); eligibility per level and `no-material`; `record` accepts only allowed keys (determinism 18); staleness after content change but not formatting change (determinism 19); `comprehension-prerequisites` when another criterion is unmet or a challenge is open (FR-088); `not-a-confirmer`; `reason-required` for `not-applicable`; `approve functional` refused without a current complete record, allowed with all five levels skipped or revealed, counts copied to the approval record (determinism 20)
- [x] T061 [P] [US3] Write unit tests for the coverage checks in `tests/unit/test_trace_coverage.py`: every approved `REQ` has an `FR`, every `FR` has a `REQ`/`UC`, gaps listed in both directions (FR-028)
- [x] T062 [P] [US3] Write scenario tests B-04, B-14 and B-16 in `tests/scenario/test_b04_b14_b16_functional.py` and B-18 in `tests/scenario/test_b18_comprehension.py`, driving the helper as the commands would
- [x] T063 [US3] Implement chain coverage checks (REQ↔FR gaps, untraceable items) in `extensions/eil/scripts/python/eil/trace.py` (FR-025, FR-028)
- [x] T064 [P] [US3] Create `templates/s02-functional-spec-template.md`: every FR-015 heading, `## Sequence Diagrams` and `## Wireframes` sections with commented example `ART` items and attachments, Actors, `## Not applicable`, Challenges, Overrides, and the `comprehension`, `assessment` and `approval` regions
- [x] T065 [US3] Implement the functional gate table `FUN-G01`..`FUN-G16` in `extensions/eil/scripts/python/eil/gates.py` and the functional sequence rules (actors plus `System`, wrong-level checks) in `extensions/eil/scripts/python/eil/diagrams.py` (FR-073, FR-079b, FR-081)
- [x] T066 [US3] Implement export handling in `extensions/eil/scripts/python/eil/artifacts.py`: `eil:artifact` record, raw-byte SHA-256, format and provenance rules, `assets/` copy with path confinement, states `missing-file`, `hash-mismatch`, `unregistered`, `orphan-asset` (FR-077, FR-078, research D-19)
- [x] T067 [US3] Implement `extensions/eil/scripts/python/eil/comprehension.py`: deterministic target selection (contracts/document-format.md §Question targets), record read and write with the allowed-key check, staleness, summary counts, and the `FUN-G16`/`TEC-G19` criterion hook in `gates.py` (FR-087..094, research D-22)
- [x] T068 [US3] Implement `artifact register`, `artifact list` and `comprehension plan|record` handlers in `extensions/eil/scripts/python/eil/cli.py`; extend `approve` to copy comprehension counts into the approval record and refuse per the criterion; extend `overview.py` with the artefact rows' file states and comprehension counts
- [x] T069 [P] [US3] Create `extensions/eil/commands/speckit.eil.functional.md`: guard, `eil stage-init functional`, derive `FR`/`NFR` from approved `REQ`/`UC` with `traces:`, flag implementation prescription, draft system-level sequence diagrams, list required wireframes and ask the human to export them (never create one, FR-085), `check`, offer `speckit.eil.comprehend`
- [x] T070 [P] [US3] Create `extensions/eil/commands/speckit.eil.artifact.md`: ask the human for the exported file and the exact-frame Figma link, or the source link for a diagram image; never create, convert or edit the file; call `eil artifact register`; report the record and resulting stage state (FR-085)
- [x] T071 [P] [US3] Create `extensions/eil/commands/speckit.eil.comprehend.md` per contracts/commands.md: `eil comprehension plan`, a pre-scan of all five targets raising one batch of challenges and stopping before question 1 (FR-091), one question per level at rising difficulty, meaning-based judging labelled as AI's, multiple choice only for levels 1 and 2 and only with plausible alternatives, hints that point to a section or id without the answer, every retry newly worded at the same level, the expected answer stated only on a reveal, on Functional an implementation-drifting answer redirected without using an attempt (FR-090), skip and reveal recorded with an optional re-ask at attempt +1, challenge instead of coaching when the document is at fault, `eil comprehension record --by <human>` after each level, never write any question, answer or hint to any file (FR-087..094)
- [x] T072 [P] [US3] Write the prompt-guidance contract test `tests/contract/test_prompt_guidance.py` (constitution Principle I, tier 2; adapted from Know Your Spec's `test-no-persistence.sh`). One parametrised table of (prompt file, rule, required text pattern), each entry skipped while its prompt file does not yet exist and run at every later checkpoint. Rules: `speckit.eil.comprehend.md` never writes a question, answer or hint into any file, record or commit message, states that passing is not required and the check is required to run, rewords each retry and reveals the answer only on request, and contains none of the words points, score, streak, timer, rank or reward outside the sentence that forbids them (FR-092, FR-094, SC-016); `speckit.eil.approve.md` asks the human directly and never supplies the attestation (FR-012); `speckit.eil.requirements.md` never turns an open question into an assumption and tags AI text `[ai-draft]` (FR-022); `speckit.eil.functional.md` and `speckit.eil.artifact.md` never draw, convert or edit a wireframe or export (FR-085); `speckit.eil.technical.md` writes the developer's choice, AI only proposes (US4-3); `speckit.eil.challenge.md` never answers a challenge for the human (FR-036); `speckit.eil.verify.md` never declares completion (FR-062); `speckit.eil.complete.md` passes the human's verbatim confirmation (FR-065); `speckit.eil.ai-spec.md` introduces nothing without a source and raises a challenge instead (FR-039); the preset wraps in `commands/`: `speckit.specify.md` never writes `spec.md` (FR-003); `speckit.clarify.md` writes each accepted answer into `s04` as an `AIS-###` item tagged `[pending-clarification]` (FR-067); `speckit.plan.md` flags content not derivable from an approved decision (FR-057); `speckit.tasks.md` flags a task that introduces architecture and cites the `ART` of the screen, schema or flow it builds (FR-058, FR-083); `speckit.implement.md` surfaces ambiguities through clarify or resolve and never assumes them (FR-041); `speckit.checklist.md` reads `s01` and `s02` as read-only context (OQ-001); every prompt, extension and wrap, begins with the guard and calls `eil` for any gate (tier 1). This test is the tier-2 evidence for every prompt-only rule that has a text form; the behaviour itself is judged by the probes in the trial protocol
- [x] T073 [US3] Add templates `s02-functional-spec-template` to `preset.yml`; append commands `functional`, `artifact` and `comprehend` to `extensions/eil/extension.yml`

**Checkpoint**: Run scenarios B-04, B-14, B-16 and B-18 (functional part). Run `tests/contract/test_prompt_guidance.py` (entries for prompts that exist so far).

---

## Phase 6: User Story 4 - Record a developer-owned technical design with explicit decisions (Priority: P4)

**Goal**: A developer-owned technical specification with explicit decisions, C4, sequence and ER artefacts checked for consistency, a comprehension check and an approvable gate.

**Independent Test**: Given an approved functional specification, produce a technical specification; decisions are in the required form and attributed to the developer, the gate is evaluated, and approval can be recorded.

- [x] T074 [P] [US4] Write unit tests in `tests/unit/test_gates_technical.py`: `TEC-G01`..`TEC-G19` as data; `DEC` requires decision, reason, rejected alternative, trade-off and owner, listing the missing field (FR-032, FR-033); `DEC` traces to `FR`/`NFR` (FR-026); unresolved technical questions listed and gate not met; a component diagram per new or changed container and a technical sequence diagram per use case that crosses containers, each present or with a recorded not-applicable reason (FR-074)
- [x] T075 [P] [US4] Write unit tests in `tests/unit/test_diagram_rules_technical.py`: rule a (L2 external elements equal L1's, component diagram has a `Container_Boundary` naming an L2 container), rule c (technical sequence participants are C4 elements), rule d (ER item carries `(store: …)` naming a `ContainerDb` or `SystemDb`), a functional-only or unparseable diagram fails; every rule has a passing and a failing fixture and clears when overridden by a configured confirmer (determinism 11)
- [x] T076 [P] [US4] Write scenario tests B-05 and B-15 in `tests/scenario/test_b05_b15_technical.py`, plus the technical half of B-18
- [x] T077 [P] [US4] Create `templates/s03-technical-spec-template.md`: every FR-016 heading, `## Container View`, `## Component Views`, `## Sequence Diagrams`, `## Data Model` with commented example `ART` items, a `DEC` example with all fields, `## Not applicable`, Challenges, Overrides, and the `comprehension`, `assessment` and `approval` regions
- [x] T078 [US4] Implement the technical gate table `TEC-G01`..`TEC-G19` and `DEC` field validation in `extensions/eil/scripts/python/eil/gates.py` (FR-016, FR-032, FR-033)
- [x] T079 [US4] Implement the technical consistency rules a, c and d in `extensions/eil/scripts/python/eil/diagrams.py` and wire them to `TEC-G15`..`TEC-G18` in `extensions/eil/scripts/python/eil/gates.py` (FR-074, FR-079)
- [x] T080 [US4] Enable `comprehension` for stage `technical` in `extensions/eil/scripts/python/eil/comprehension.py` (`DEC`, `ART` eligibility per level) and `TEC-G19` in `extensions/eil/scripts/python/eil/gates.py`
- [x] T081 [P] [US4] Create `extensions/eil/commands/speckit.eil.technical.md`: guard, `eil stage-init technical`, capture `DEC` with owner = the developer, AI may propose alternatives but the developer's choice is written (US4-3), draft container, component, technical sequence and ER diagrams with `(store: …)`, `check`, offer `speckit.eil.comprehend`
- [x] T082 [US4] Add template `s03-technical-spec-template` to `preset.yml`; append command `technical` to `extensions/eil/extension.yml`

**Checkpoint**: Run scenarios B-05, B-15 and the technical half of B-18. Run `tests/contract/test_prompt_guidance.py` (entries for prompts that exist so far).

---

## Phase 7: User Story 5 - Give the AI agent an approved, bounded execution context (Priority: P5)

**Goal**: An AI Specification assembled only from approved material, exposed to Spec Kit through aliases, with plan and tasks refused until it is traceable and free of pending answers.

**Independent Test**: Given a fully approved chain, generate the AI Specification; every item traces to an approved source, nothing new is introduced, and a planted ambiguity is surfaced as a question rather than resolved.

- [x] T083 [P] [US5] Write unit tests in `tests/unit/test_aliases.py`: every fault class (`missing`, `wrong-target`, `diverged`, mirror differs) is reported before refresh and repaired after (determinism 6); no alias created before its target and never any alias other than `spec.md`, `plan.md`, `tasks.md` (determinism 7); symlink form is relative; `EIL_ALIAS_MODE=mirror` forces read-only mirrors; the target is never modified (FR-049..053)
- [x] T084 [P] [US5] Write unit tests in `tests/unit/test_gates_aispec.py`: source-traceability (every `AIS` traces, none without a source is `ai-spec-not-traceable`), `[pending-clarification]` fails the check, `ai-spec-missing`; `AIS` items referencing an `ART` whose item hash differs from its stage's approval give `artifact-changed-since-approval` (determinism 16, FR-082); a diagram in `s04` is `artifact-wrong-level`
- [x] T085 [P] [US5] Write unit tests in `tests/unit/test_enter_and_resolve.py`: `enter plan|tasks|implement|clarify` rules and refusals (`stage-not-approved`, `ai-spec-not-traceable`, `pending-clarification`, `plan-missing`, `ai-spec-missing`, `alias-fault-strict`); `resolve` carries a pending answer to the earliest affected stage, marks it `needs-re-review` if approved, clears the tag only after re-approval (FR-042, FR-067); plan and tasks gates: content not derivable from a `DEC` flagged, task introducing architecture flagged, in-scope wireframe/ER/technical-sequence artefact reached by no task is `artifact-uncovered` (FR-057, FR-058, FR-083)
- [x] T086 [P] [US5] Write scenario tests B-06, B-07, B-08 and B-17 in `tests/scenario/test_b06_b08_b17_aispec_aliases.py`, including a full run with `EIL_ALIAS_MODE=mirror`. Also a contract test in `tests/contract/test_core_accepts_aliases.py` that runs Spec Kit's own `.specify/scripts/bash/check-prerequisites.sh --json --require-tasks --include-tasks` in a governed package whose three aliases exist (symlink form, then `EIL_ALIAS_MODE=mirror`) and asserts it accepts them and reports the alias paths (research D-06)
- [x] T087 [US5] Implement `extensions/eil/scripts/python/eil/aliases.py`: classify, report, then refresh symlink or mirror; read-only mirrors; never touch targets; test switch `EIL_ALIAS_MODE` (FR-049..053, research D-06, D-07)
- [x] T088 [US5] Implement AI Specification, plan and tasks gates and artefact-reference and coverage checks in `extensions/eil/scripts/python/eil/gates.py` and `extensions/eil/scripts/python/eil/trace.py` (FR-027, FR-039, FR-057, FR-058, FR-067, FR-082, FR-083)
- [x] T089 [US5] Implement `enter`, `resolve` and alias-aware `sync` and `stage-init ai-spec|plan|tasks` (creating the alias only after its target) in `extensions/eil/scripts/python/eil/cli.py`
- [x] T090 [P] [US5] Create `templates/spec-template.md` (override of core `spec-template`; becomes the AI Specification skeleton with every FR-017 heading, `## Artefacts in Scope` as `AIS` items tracing to `ART`, and the gate comment), based on `.specify/templates/spec-template.md`
- [x] T091 [P] [US5] Create `templates/plan-template.md` and `templates/tasks-template.md` (overrides of the core templates, based on `.specify/templates/`) adding `(traces: DEC-###)` on plan sections and `(traces: AIS-###)` on task lines
- [x] T092 [P] [US5] Create `commands/speckit.clarify.md` (wrap): guard, `eil enter clarify` (exit 3 runs core unchanged, refuse `ai-spec-missing`), then core body, then write each accepted answer into `s04` as `AIS-###` tagged `[pending-clarification]` and point to `speckit.eil.resolve` (FR-067)
- [x] T093 [P] [US5] Create `commands/speckit.plan.md` (wrap): guard, `eil enter plan`, `eil stage-init plan`, core body writing through the alias, every section `(traces: DEC-###)`, flag plan content not derivable from an approved decision (FR-004, FR-057)
- [x] T094 [P] [US5] Create `commands/speckit.tasks.md` (wrap): guard, `eil enter tasks`, `eil stage-init tasks`, core body, each task `(traces: AIS-###)` and citing its `ART` for screens, schema or flows, then `eil check --stage tasks` (FR-031, FR-058, FR-083)
- [x] T095 [P] [US5] Create `commands/speckit.implement.md` (wrap): guard, `eil enter implement`; ambiguities are surfaced through `clarify` or `resolve`, never assumed (FR-041)
- [x] T096 [P] [US5] Create `extensions/eil/commands/speckit.eil.ai-spec.md`: guard, `eil stage-init ai-spec`, assemble only from approved stages with `AIS-### (traces: …)`, list approved artefacts to read as `AIS` items tracing to `ART`, draw no diagram, raise anything without a source as a challenge, `check` (FR-027, FR-082)
- [x] T097 [P] [US5] Create `extensions/eil/commands/speckit.eil.resolve.md`: decide the earliest affected stage with the human, `eil resolve`, write the decision as a proper item, re-run `check`, state any `needs-re-review` (FR-067)
- [x] T098 [US5] Add templates `spec-template`, `plan-template`, `tasks-template` and commands `speckit.clarify`, `speckit.plan`, `speckit.tasks`, `speckit.implement` to `preset.yml`; append commands `ai-spec` and `resolve` to `extensions/eil/extension.yml`
- [x] T099 [P] [US5] Write contract test in `tests/contract/test_wrap_guards.py`: all wrap commands begin with the identical guard text and contain `{CORE_TEMPLATE}` exactly once; the composed skills after install contain the guard (C-05 against the real preset)

**Checkpoint**: Run scenarios B-06, B-07, B-08 (symlink and mirror) and B-17; C-05 against the real preset. Run `tests/contract/test_prompt_guidance.py` (entries for prompts that exist so far).

---

## Phase 8: User Story 6 - Trace any delivered change back to its reason and forward to its evidence (Priority: P6)

**Goal**: Follow any requirement forward to its evidence, and any code change back to its requirement, with gaps reported and impact of upstream changes listed.

**Independent Test**: Choose one requirement in a completed story and produce its chain to evidence; choose one code change and produce its chain back to a requirement.

- [x] T100 [P] [US6] Write unit tests in `tests/unit/test_trace_chain.py`: forward and reverse chains across `REQ/UC → FR → DEC → AIS → T → code → EVD` with `ART` as a side branch, gaps reported in either direction, `--from` and `--to` by commit or PR, output lists overrides, abbreviated stages and accepted risks (FR-024, FR-029, FR-030, FR-040, FR-045)
- [x] T101 [P] [US6] Write unit tests in `tests/unit/test_impact.py`: changing an upstream item's hash marks every downstream stage that lists it as `needs-re-review` and `status` lists exactly the affected items; formatting-only change does not; clone elsewhere keeps approvals valid (FR-043, FR-044)
- [x] T102 [P] [US6] Write scenario tests B-09 and B-11 in `tests/scenario/test_b09_b11_trace_analyze.py`
- [x] T103 [US6] Implement full-chain traversal, gap detection, impact analysis and the `--chain` check in `extensions/eil/scripts/python/eil/trace.py`, and the `trace` handler in `extensions/eil/scripts/python/eil/cli.py` (FR-028..030, FR-043, FR-068)
- [x] T104 [P] [US6] Create `commands/speckit.analyze.md` (wrap): core analysis over the three aliases unchanged, then `eil check --chain --json`, appending findings in the same table style with `T-` ids (FR-068)
- [x] T105 [P] [US6] Create `commands/speckit.checklist.md` (wrap): core body over `spec.md` plus `s01` and `s02` as read-only context (OQ-001, research D-13); prepare the manual evaluation in scenario B-11
- [x] T106 [P] [US6] Create `extensions/eil/commands/speckit.eil.trace.md`: guard, `eil trace` forward, reverse and gaps
- [x] T107 [US6] Add `speckit.analyze` and `speckit.checklist` to `preset.yml`; append command `trace` to `extensions/eil/extension.yml`

**Checkpoint**: Run B-09 and B-11 (judge the checklist output by reading it and record the answer in the plan's Open Items to close or reopen OQ-001). Run `tests/contract/test_prompt_guidance.py` (entries for prompts that exist so far).

---

## Phase 9: User Story 7 - Verify with evidence, then close with human accountability (Priority: P7)

**Goal**: Verification records evidence for every requirement and approved artefact; completion needs an explicit human confirmation and is refused while anything is unverified without an exception.

**Independent Test**: Given an approved chain and finished implementation, produce verification and completion; every item has evidence or an exception and completion cannot be recorded without a human's explicit confirmation.

- [x] T108 [P] [US7] Write unit tests in `tests/unit/test_gates_verification.py`: every `REQ`, `FR`, acceptance criterion and approved `ART` has a status and evidence (FR-059); automated, manual and exception evidence separated (FR-060); exceptions record who and why (FR-061); open tasks listed; `s07` is never approvable and never declares completion (FR-062); `(code: sha|PR#n)` links parsed
- [x] T109 [P] [US7] Write unit tests in `tests/unit/test_gates_completion.py`: `approve completion` refused `verification-missing`, `unverified-requirement`, `unverified-artifact` unless overridden (FR-064, FR-065); a `Diagram Currency` line per approved artefact or a listed deviation (FR-084); explicit evidence-reviewed attestation required; overview shows complete with approver and date
- [x] T110 [P] [US7] Write scenario test B-12 (and the s07/s08 half of B-17) in `tests/scenario/test_b12_verification_completion.py`
- [x] T111 [P] [US7] Create `templates/s07-verification-template.md` (rows per `REQ`/`FR`/acceptance criterion/`ART`, evidence kinds, exceptions, open tasks) and `templates/s08-completion-template.md` (FR-063 headings including `Diagram Currency`, `approval` region)
- [x] T112 [US7] Implement verification and completion gate tables `VER-G*` and `CMP-G*` in `extensions/eil/scripts/python/eil/gates.py`, evidence and `code` link parsing in `extensions/eil/scripts/python/eil/trace.py`, and completion refusals in `extensions/eil/scripts/python/eil/records.py`
- [x] T113 [US7] Enable `stage-init verification|completion` and the completion display in `extensions/eil/scripts/python/eil/cli.py` and `extensions/eil/scripts/python/eil/overview.py`
- [x] T114 [P] [US7] Create `extensions/eil/commands/speckit.eil.verify.md`: guard, `eil stage-init verification`, list every item and approved artefact with status and evidence, distinguish automated, manual and exceptions, list open tasks visibly, never declare completion (FR-059..062)
- [x] T115 [P] [US7] Create `extensions/eil/commands/speckit.eil.complete.md`: guard, `eil stage-init completion`, fill content and Diagram Currency lines, ask the human directly to confirm the evidence was reviewed, `eil approve completion` with their verbatim answer (FR-063..065, FR-084)
- [x] T116 [US7] Add templates `s07-verification-template` and `s08-completion-template` to `preset.yml`; append commands `verify` and `complete` to `extensions/eil/extension.yml`

**Checkpoint**: Run B-12 and the verification and completion half of B-17. Run `tests/contract/test_prompt_guidance.py` (entries for prompts that exist so far).

---

## Phase 10: User Story 8 - AI challenges, human decides (Priority: P8)

**Goal**: AI raises specific, recorded challenges at any definition stage; a human answers; open challenges block approval.

**Independent Test**: In any single stage, AI raises a challenge about a deliberate gap; it is recorded, stays open until a human responds, and the response is reflected in the stage content.

- [x] T117 [P] [US8] Write unit tests in `tests/unit/test_challenges.py`: `challenge add` records an open challenge with a specific target; `challenge answer` with `accepted`, `rejected` (reason required) or `deferred` (explicit risk acceptance); `not-a-confirmer`, `conflict` when two responders differ (resolvable only by a configured confirmer); `duplicate-of-closed` prevents re-raising a rejected or deferred equivalent (FR-034..038)
- [x] T118 [P] [US8] Write unit test in `tests/unit/test_approve_open_challenge.py`: `approve` refuses `open-challenge` at every approvable stage
- [x] T119 [P] [US8] Write scenario test B-10 in `tests/scenario/test_b10_challenges.py`
- [x] T120 [US8] Implement `challenge add|answer` in `extensions/eil/scripts/python/eil/records.py` and `extensions/eil/scripts/python/eil/cli.py`, and the `open-challenge` refusal in `approve` (FR-037)
- [x] T121 [P] [US8] Create `extensions/eil/commands/speckit.eil.challenge.md`: review the named stage, raise specific challenges with `eil challenge add`, or record the human's response with `eil challenge answer`; never answer for the human; treat rejected and deferred answers as constraints (FR-034..038)
- [x] T122 [US8] Add the shared challenge pass (gaps, contradictions, unstated assumptions, untestable statements, wrong-level prescription, diagram-versus-text and wireframe-versus-text mismatches) to `extensions/eil/commands/speckit.eil.requirements.md`, `extensions/eil/commands/speckit.eil.functional.md` and `extensions/eil/commands/speckit.eil.technical.md` per contracts/commands.md
- [x] T123 [US8] Append command `challenge` to `extensions/eil/extension.yml`

**Checkpoint**: Run B-10. Run `tests/contract/test_prompt_guidance.py` (entries for prompts that exist so far).

---

## Phase 11: User Story 9 - Adopt, tailor and remove the preset safely (Priority: P9)

**Goal**: A team lead installs the preset safely, names who may approve, authorises abbreviations, and can remove everything without harming existing specs or standard Spec Kit behaviour.

**Independent Test**: Install into a project with existing feature specs; existing work is untouched; approvers are enforced; removal restores standard behaviour.

- [x] T124 [P] [US9] Write unit tests in `tests/unit/test_abbreviation_and_config.py`: `abbreviate` records who authorised and why, refuses `not-an-authoriser`, `reason-required`, `cannot-skip`; abbreviated status shows in the overview and trace report but the stage still passes a gate (FR-040); per-stage approvers and `local-config.yml` override enforced on `approve`, `override`, `challenge answer` (FR-013)
- [x] T125 [P] [US9] Write contract test in `tests/contract/test_removal_and_coexistence.py`: install into a project with `specs/000-legacy/spec.md` (untouched, never gated, `eil status` exits 3); remove preset then extension; `speckit-plan` resolves to core, stage documents, aliases and mirrors remain readable, no `eil` hooks in `.specify/extensions.yml`, `git diff` shows no change to non-generated files (FR-005, FR-006, SC-009)
- [x] T126 [P] [US9] Write scenario test B-13 in `tests/scenario/test_b13_governance.py`
- [x] T127 [US9] Implement `abbreviate` in `extensions/eil/scripts/python/eil/records.py` and `extensions/eil/scripts/python/eil/cli.py`; show abbreviated stages in `extensions/eil/scripts/python/eil/overview.py` and the trace report
- [x] T128 [P] [US9] Create `extensions/eil/commands/speckit.eil.abbreviate.md`: ask who authorises and why, call `eil abbreviate`, state the status note
- [x] T129 [US9] Append command `abbreviate` to `extensions/eil/extension.yml`; verify it now lists all 15 commands and the four hooks against contracts/manifests.md
- [x] T130 [US9] Write the README Configure and Remove sections: setting approvers, abbreviation authorisers, local overrides, removal order (preset then extension) and what remains (SC-001, SC-009)

**Checkpoint**: Run B-13 and the removal contract test.

---

## Phase 12: Polish & Cross-Cutting Concerns

**Purpose**: Whole-plan validation, documentation and release.

- [x] T131 [P] Write `docs/trials.md`: protocols and recording sheets for the human trials (SC-007, SC-008, SC-010 including artefact effort, SC-004/SC-011, SC-014, the comprehension-check trial and its five probes (coaching-retry, skip-reveal, implementation-drift, defect-pre-scan, no-persistence), the prompt-guidance probes for every rule in T072 (attestation-not-supplied, open-question-not-assumed, export-not-drawn, challenge-not-answered, completion-not-declared, developer-choice-recorded, no-unsourced-content), the wrap probes (clarify-pending-tagged, plan-flags-underivable, tasks-flags-architecture, implement-surfaces-ambiguity), and the Figma export-facts check in quickstart.md Part C). The pass rule is: run each probe once per command, treat any failure as a prompt defect, fix it and re-run the failed probe until it is clean; release needs one clean run of every probe
- [x] T132 [P] Write `tests/scenario/test_full_run.py`: replay B-01..B-18 in order in one scratch project, plus the mirror-mode run of B-08
- [x] T133 [P] Write `tests/unit/test_performance.py`: `sync`, `check` and `status` each complete in under 1 second on a story package of nine documents of about 1 MB (plan Performance Goals)
- [x] T134 Run C-06: time from `specify extension add` to a started story following only `README.md`; record the result; must be under 10 minutes (SC-001)
- [x] T135 Run the whole suite on Linux, then `tests/scenario` with `EIL_ALIAS_MODE=mirror` and with symlinks disabled; fix failures; confirm `tests/contract/test_prompt_guidance.py` skips no entry (all 15 prompts exist)
- [x] T136 [P] Complete `README.md` (Use, Trials) and `CHANGELOG.md` for version 0.1.0; document the attestation-level limits honestly and the coexistence note for Know Your Spec (its `after_specify` hook is harmless but noisy after this preset's `specify`, research D-22)
- [x] T137 Produce release archives for `specify extension add --from` and `specify preset add --from`; add a contract test that installs from the archives
- [x] T138 Update the checklist Notes in `specs/001-staged-definition-workflow/checklists/requirements.md` and close or reopen OQ-001 in `spec.md` from the B-11 result

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (T001-T008)**: none.
- **Foundational (T009-T030)**: depends on Setup. The risk spike and its checkpoint come first; nothing else starts until C-03 and C-05 are recorded. **Blocks all user stories.**
- **US1 (T031-T050)**: depends on Foundational. This is the MVP.
- **US2 (T051-T057)**: depends on US1 (extends its minimal overview).
- **US3 (T058-T073)**: depends on US1 (gate engine, approval records) and US2 (overview extensions).
- **US4 (T074-T082)**: depends on US3 (comprehension, artefact export handling, shared diagram rules).
- **US5 (T083-T099)**: depends on US4 (an approved technical stage feeds the AI Specification). Aliases and their tests can start after Foundational.
- **US6 (T100-T107)**: depends on the stages it traces across; the chain logic can be written after US3 and completed as stages arrive.
- **US7 (T108-T116)**: depends on US5 (tasks exist) and US6 (`code` links, coverage).
- **US8 (T117-T123)**: depends on US1's `approve`; the challenge pass edits the stage commands from US1, US3 and US4.
- **US9 (T124-T130)**: depends on US1; the removal and coexistence test needs all commands registered.
- **Polish (T131-T138)**: depends on all desired stories.

### Within Each Story

- Tests first, and confirm they fail; then helper modules; then templates and command prompts; then manifest entries.
- Helper before its command prompts; templates before the stage-init handler is finished.
- Manifest edits (`preset.yml`, `extension.yml`) come last in each story because they name files created earlier in it.

## Parallel Opportunities

- Setup: the four [P] tasks after the skeleton and `pyproject.toml`.
- Foundational: the C-03 and C-05 tests together; every `Write unit tests` task is independent of the others (implementations follow their tests); results.py alongside the fixtures.
- Each story: all `Write unit tests` tasks together; all `Create templates/...` and `Create ...speckit.eil.*.md` tasks together (different files).
- After US1, US3, US4 and US5 can be staffed in parallel only for tests, templates and command prompts; the shared `gates.py`, `cli.py` and manifests are edited serially.

Example, US3 in parallel: the five test-writing tasks, then `templates/s02-functional-spec-template.md`, `speckit.eil.artifact.md` and `speckit.eil.comprehend.md` together.

## Implementation Strategy

1. **Setup and Foundational**, including the C-03 and C-05 spike. If either fails, stop and redesign.
2. **MVP = US1**: install, start a story, gate Requirements, record an approval. Validate by hand in a scratch project before going on.
3. **Add US2** so the overview exists, then **US3 and US4** (the two stages that carry artefacts and the comprehension check), **US5** (AI Specification and Spec Kit hand-off), **US6**, **US7**, **US8**, **US9**, each independently tested by its own scenario.
4. **Polish**: full replay of B-01..B-18, mirror mode, performance, install-time, archives, docs, human trials.
5. Keep the `eil` helper the only place enforcement lives; prompts only call it (research D-05).
