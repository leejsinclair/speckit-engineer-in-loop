# Quickstart: validating the Staged Definition Workflow

Runnable scenarios that prove the feature end to end. They double as the acceptance tests for the plan. Contract details live in [contracts/](contracts/); entities in [data-model.md](data-model.md). Nothing here is implementation code.

**Status**: the preset, extension and helper do not exist yet (this plan precedes `/speckit-tasks`). Every scenario below is the target behaviour, written so each step has an observable expected outcome.

## Prerequisites

- `specify` (Spec Kit 1.0.2.dev0 or later), Python 3.11+, `git`.
- A scratch project, never a real one:

```bash
export SCRATCH=$(mktemp -d) && cd "$SCRATCH"
git init -q && git config user.name "Ada Dev" && git config user.email ada@example.com
specify init --here --integration claude        # an ordinary Spec Kit project
git add -A && git commit -qm "baseline"
```

- The repository under test in `$EIL_SRC` (this repo).

## Part A. Contract checks (install, coexistence, removal)

| ID | Steps | Expected |
|---|---|---|
| **C-01** | `specify extension add --dev $EIL_SRC/extensions/eil` | Exit 0. `.specify/extensions/eil/` exists with the helper. 15 `speckit-eil-*` skills registered and 4 hooks in `.specify/extensions.yml` (during implementation, run it with the commands built so far, and against all 15 and 4 once the last command is added). `git status` shows **only** additions under `.specify/` and `.claude/` (FR-001). |
| **C-02** | `specify preset add --dev $EIL_SRC` | Exit 0. `specify preset info engineer-in-the-loop` lists 9 templates and 7 commands. No pre-existing tracked file modified (`git diff --stat` empty apart from additions). |
| **C-03** | `specify preset resolve s01-requirements-template` and `specify preset resolve spec-template` | The first resolves to the preset's file (risk R-1 proved); the second resolves to the preset override. **If the first fails, use the D-02 fallback before continuing.** |
| **C-04** | `python3 .specify/extensions/eil/scripts/python/eil fingerprint README.md` | Prints `sha256:` + 64 hex. The helper runs from its installed location. |
| **C-05** | Read the composed `.claude/skills/speckit-plan/SKILL.md` | Contains the guard and `eil enter plan` before the core plan body (risk R-2). |
| **C-06** | Time from C-01 to a started story (Part B, B-01), following only `README.md` | Under 10 minutes (SC-001). |

## Part B. Scenarios (each maps to spec stories and requirements)

Run in order in the scratch project. "Governed" means `s00-README.md` exists (FR-069).

### B-01 Start a story at Requirements (US1, FR-003, FR-048)
1. Run `/speckit-specify "Detect duplicate customers on import"`.
2. **Expect**: feature dir `specs/001-…`; `s00-README.md` and `s01-requirements.md` exist; **no** `spec.md`, `plan.md`, `tasks.md`, or any of `s02`–`s08`. `s01` contains every required heading. Overview shows stage `requirements`, status draft.

### B-02 Requirements gate and approval (US1, FR-009..013, 066)
1. Run `/speckit-eil-requirements` to draft and check. Leave one **material** open question `open`.
2. Try `eil approve requirements --by "Ada Dev" --attestation "yes"`. **Expect**: exit 1, `open-question` (US1-5).
3. Try `eil approve requirements --by "Mallory" …`. **Expect**: exit 1, `not-a-confirmer` (FR-013).
4. Accept the question (`accepted_by` set), close all challenges, then approve as `Ada Dev` with an attestation. **Expect**: approval region written with name, UTC time, `sha256:`, the attestation; overview lists it; one confirmation sufficed (FR-066).
5. Try `eil stage-init functional` before step 4 succeeded (repeat on a fresh copy). **Expect**: exit 1, `stage-not-approved` (US1-7, FR-008).

### B-03 Overview stays in step (US2, FR-054..056)
After each of B-02's actions, `git diff s00-README.md`. **Expect**: reflects the change with no manual edit; contains no requirement or design prose (FR-055). Hand-edit `s00` to say `approved`, run `eil status`. **Expect**: the derived status wins and the disagreement is reported.

### B-04 Traceability and separation of concerns (US3, FR-025, 028, 019, 020)
1. Approve requirements, then `/speckit-eil-functional`. Add `**FR-099**: …` with **no** `traces:` clause and a requirement `REQ-005` with no FR.
2. `eil check --stage functional`. **Expect**: FR-099 flagged untraceable; REQ-005 reported uncovered; gate not met (US3-2, US3-3).
3. Add "store in PostgreSQL" to a functional requirement. **Expect**: flagged as prescribing implementation (US3-4).

### B-05 Technical decisions (US4, FR-032, 033)
Create `DEC-004` missing its rejected alternative. **Expect**: gate not met, listing the missing field. Complete it, decline an AI-proposed alternative. **Expect**: the recorded decision is the developer's, `owner` is the developer.

### B-06 AI Specification and pending answers (US5, FR-027, 039, 067, 004)
1. Approve `technical`. `/speckit-eil-ai-spec`. **Expect**: `s04-ai-spec.md` and `spec.md` (alias) exist; every `AIS-###` has `traces:`.
2. Add an item without a source. **Expect**: flagged, gate not met (US5-2).
3. Run `/speckit-clarify`, answer one question. **Expect**: the answer appears in `s04` tagged `[pending-clarification]`; overview lists it as an outstanding issue; the AI Spec fails source-traceability.
4. Run `/speckit-plan`. **Expect**: refused, `pending-clarification`, nothing written (US5-5, FR-004).
5. Run `/speckit-eil-resolve` targeting `functional`. **Expect**: answer becomes an `FR-###` in `s02`; `s02` is `needs-re-review` with the affected item listed (FR-043); the pending tag clears **only after** `s02` is approved again; until then `plan` stays refused. Override it (`eil override … --by "Ada Dev" --reason "spike"`); **Expect**: `plan` proceeds and the override is visible in every later stage's overview and the trace report (FR-045, SC-006).

### B-07 Plan and tasks through aliases (FR-049, 052, 057, 058, F-6/F-7)
`/speckit-plan` then `/speckit-tasks`. **Expect**: `s05-plan.md`, `plan.md`, `s06-tasks.md`, `tasks.md` exist; aliases created only after targets; core `setup-tasks.sh` found `plan.md` and `spec.md`; each task has `(traces: AIS-###)`; `spec.md` was never overwritten by another stage.

### B-08 Alias faults and mirrors (FR-051, 053, SC-012)
1. Replace `spec.md` symlink with an ordinary file containing different text; run any `eil` command. **Expect**: fault reported (`diverged`), then repaired, target untouched.
2. Force mirror mode (`EIL_ALIAS_MODE=mirror`, a test-only switch). **Expect**: aliases are read-only, content-identical to targets, listed under **Mirrors** in the overview; edit `s05`, run `/speckit-tasks`. **Expect**: mirror refreshed **before** the command reads it.
3. Delete `plan.md`. **Expect**: `missing` reported and restored.

### B-09 Detecting hand edits (FR-044)
1. With `s01` approved, convert its line endings to CRLF and add trailing spaces. **Expect**: still `approved` (formatting ignored).
2. Change one word. **Expect**: `needs-re-review`; downstream approvals dependent on it marked, affected items listed (FR-043).
3. Clone the repository elsewhere. **Expect**: approval still valid (no timestamp dependence).

### B-10 AI challenges, human decides (US8, FR-034..038)
Add a deliberate gap in `s02`; run `/speckit-eil-challenge`. **Expect**: a specific challenge recorded, `open`; `approve` refused (`open-challenge`); `rejected` without a reason refused; `rejected` with a reason closes it; re-running the pass does **not** re-raise it (US8-4). Two different responders answer one challenge: **Expect** `conflict`, resolvable only by a configured confirmer.

### B-11 Analyze and checklist on the story (FR-068, OQ-001)
1. `/speckit-analyze` on a story with an FR that has no REQ. **Expect**: core findings over `spec.md`, `plan.md`, `tasks.md` unchanged **plus** the full-chain finding `T-…`.
2. `/speckit-checklist`. **Expect**: produced from the AI Specification with `s01`/`s02` read as context. **Judge by reading it**: are the items about requirement quality still meaningful? Record the answer in the plan's Open Items. This closes or reopens OQ-001.

### B-12 Verification, completion (US7, US6, FR-059..065, 030)
1. Finish tasks; `/speckit-eil-verify`. **Expect**: every `REQ`, `FR` and acceptance criterion has a status; automated, manual and exceptions are separate; open tasks listed; `s07` cannot be approved and does not declare completion.
2. Leave one requirement `unverified` without an exception; `/speckit-eil-complete`. **Expect**: refused, `unverified-requirement` (US7-4).
3. Add an exception with who/why. **Expect**: completion approvable; the human's confirmation is required; overview shows the story complete with approver and date (US7-5).
4. `eil trace --from REQ-001` and `--to <commit>`. **Expect**: full chain both ways; a requirement with no evidence is reported (US6).

### B-13 Governance boundaries (US9, FR-005, 006, 069, SC-009)
1. In a fresh scratch project **with an existing feature** `specs/000-legacy/spec.md`, install both. **Expect**: `000-legacy` untouched and never gated; `eil status` there exits `3`.
2. Configure `approvers.requirements: ["Grace"]`. **Expect**: `Ada Dev` refused, `Grace` accepted (FR-013).
3. Remove preset then extension. **Expect**: `speckit-plan` resolves to core; stage documents, aliases and mirrors remain readable; no `eil` hooks in `extensions.yml`; `git diff` shows no change to non-generated project files (SC-009).

### B-14 Context and functional artefacts (US1, US3, FR-071..075, 079, 081)
1. In `s01`, list users, stakeholders and dependencies, then run `/speckit-eil-requirements`. **Expect**: a `c4-context` `ART` item with a Mermaid fence; every listed person and system appears in it; each carries `[existing]`, `[new]` or `[changed]`. Delete one dependency from the diagram. **Expect**: `check` reports `diagram-inconsistent` (rule e) and `REQ-G14` is not met; `approve requirements` refused `unmet-criteria`.
2. Add a `wireframe` `ART` to `s01`. **Expect**: `artifact-wrong-level`. Remove it.
3. Approve `requirements`, run `/speckit-eil-functional`. **Expect**: one `seq-functional` diagram drafted per use case; the agent lists the screens that need wireframes and asks for exports, and does not create any image.
4. In a functional sequence diagram name a participant `Import API` that is not a declared actor. **Expect**: `artifact-wrong-level`/`diagram-inconsistent` (rule b); `FUN-G14` not met. Add an `erDiagram` to `s02`. **Expect**: `artifact-wrong-level`.
5. On a story with no user interface, remove the wireframe section with the reason "API only". **Expect**: `FUN-G15` met on that reason; without a reason, not met (FR-075).

### B-15 Technical artefacts and cross-diagram consistency (US4, FR-074, 079, 080)
1. Approve `functional`, run `/speckit-eil-technical`. **Expect**: container diagram, a component diagram for each changed container, technical sequence diagrams each citing a `DEC`, and an ER diagram with `(store: <label>)`.
2. Rename an external system in the container diagram so it differs from `s01`'s context. **Expect**: `diagram-inconsistent` (rule a) naming both. Fix it.
3. Make a technical sequence diagram name a participant that is in no C4 diagram. **Expect**: rule c. Set the ER item's `(store: …)` to a label that is not a `ContainerDb`. **Expect**: rule d.
4. Add a line `Foo bar baz` inside a `sequenceDiagram`. **Expect**: `diagram-unparseable` with the line number; gate not met; not skipped (FR-080).
5. Override rule (c) as the configured confirmer with a reason. **Expect**: the criterion is `overridden`, and the override is listed in every later stage's overview (FR-045).

### B-16 Exports, provenance and drift (FR-077, 078, 085, SC-015)
1. Run `/speckit-eil-artifact` for a wireframe with a Figma URL lacking `node-id`. **Expect**: refused `artifact-no-provenance`. Supply a URL with `node-id`. **Expect**: file copied to `assets/`, `eil:artifact` record written with `sha256:` of the raw bytes.
2. Register a `.gif`. **Expect**: `artifact-format-not-allowed`. Register with `--file ../outside.png`. **Expect**: `path-outside-package`.
3. Approve `functional`. Change one byte of the exported file without touching the record. **Expect**: `artifact-hash-mismatch`; the document fingerprint is unchanged.
4. Register the new export. **Expect**: the record changes, so `s02` is `needs-re-review` and the downstream items that trace to it are listed (FR-043, 078).
5. Drop an unregistered file into `assets/`. **Expect**: `orphan-asset` finding. Register a draw.io PNG of a container diagram as `image` with `depicts`. **Expect**: `checked: false`, shown as not structurally checked in the overview.

### B-17 Artefacts through AI Spec, tasks, verification, completion (FR-082..084, 059, 065, SC-014)
1. Approve `technical`, run `/speckit-eil-ai-spec`. **Expect**: `AIS` items tracing to `ART` items for the artefacts to read; no diagram in `s04`. Add a fence to `s04`. **Expect**: `artifact-wrong-level`.
2. Edit an approved diagram in `s03`. **Expect**: `s03` is `needs-re-review`, and `s04` fails source-traceability with `artifact-changed-since-approval` (FR-082).
3. `/speckit-tasks` with no task tracing to an in-scope ER diagram. **Expect**: `artifact-uncovered` (FR-083).
4. `/speckit-eil-verify`. **Expect**: every approved `ART` has a row with a status. Leave one `unverified` without an exception; `/speckit-eil-complete`. **Expect**: refused `unverified-artifact` (FR-065).
5. Add an exception naming who and why; add a `Diagram Currency` line for each artefact, one listing a deviation. **Expect**: completion approvable; the deviation appears in the summary (FR-084).
6. `eil artifact list --json` and the overview. **Expect**: every `ART` with kind, stage and state, links only, no diagram content (FR-086, FR-055).

### B-18 Comprehension check before approval (US1, US3, US4, FR-087..094, SC-016)
1. With `s02` gate otherwise met and no open challenge, try `eil approve functional --by "Ada Dev" --attestation "yes"`. **Expect**: exit 1, `unmet-criteria` naming `FUN-G16` (`comprehension-missing`). Repeat on `s03` with `TEC-G19`. `eil approve requirements` is unaffected.
2. Open a challenge on `s02`, then `eil comprehension plan --stage functional`. **Expect**: refused `comprehension-prerequisites` (FR-088). Close the challenge.
3. Run `/speckit-eil-comprehend`. **Expect**: five questions, one at a time, in the order recognise, explain, apply, trace, evaluate; each about an item the plan named; the trace question follows a real `REQ`→`FR` (→`ART`) chain from the document. Answer one wrongly. **Expect**: a hint pointing at a section or id, not the answer; retry accepted (`coached`).
4. Skip level 3 and ask for the answer at level 4. **Expect**: both recorded (`skipped`, `revealed`), a re-ask offered with a different item, and no refusal. Finish all five. **Expect**: `comprehension` region holds levels, outcomes, attempts, item ids, taker, fingerprint; **no** question, answer, hint or score text anywhere in the repository (`git grep` the answers you typed).
5. `eil approve functional …`. **Expect**: approval succeeds; the approval record carries the counts; the overview shows them (for example `understood 2 · coached 1 · skipped 1 · revealed 1`).
6. Change one word in `s02`. **Expect**: `comprehension-stale`, `FUN-G16` not met, approval refused. Change only line endings. **Expect**: still current (FR-044). Re-run `eil comprehension plan` twice for the same version and attempt. **Expect**: identical targets (FR-089).
7. Seed `s02` with two contradictory `FR` lines and run `/speckit-eil-comprehend`. **Expect**: the pre-scan raises one batch of challenges before question 1 and the check stops; no level is recorded (FR-091). Answer them, then re-run: the check plans again on the new version. Separately, if a defect is only met mid-check, **expect** the agent to raise a challenge and pause, not to coach towards either reading, and `approve` to refuse `open-challenge`.
7a. Answer a level wrongly twice. **Expect**: each retry is worded differently from the last and the expected answer is not stated until you ask for it. On `s02`, answer a behaviour question with a technology choice. **Expect**: redirected to behaviour, and the attempts count is unchanged (FR-090).
8. On a one-screen story with no trade-off, record `evaluate` as `not-applicable` without a reason. **Expect**: `reason-required`. With a reason, **expect** it accepted (FR-092).
9. Run the record as `--by "Mallory"`. **Expect**: `not-a-confirmer` (FR-094). Try to add an extra key such as `"answer"` to the region by hand. **Expect**: the next `check` reports `malformed-comprehension` and the record is treated as absent.
10. Override `FUN-G16` with a reason as the configured confirmer. **Expect**: approval succeeds and the override is visible in every later stage (FR-045).

## Part C. Trials (human, not automated)

| Measure | Trial | Pass |
|---|---|---|
| SC-007 | ≥ 5 real stories | ≥ 90% of ambiguities met during implementation surfaced as questions |
| SC-008 | 5 reviewers read `s01` + `s02` only | ≥ 4 can say why and what |
| SC-010 | Time the trial stories | Process overhead ≤ 25% of story effort |
| SC-004 / SC-011 | Ask a reviewer / newcomer the standard questions | < 5 min per delivered item; < 1 min from the overview |
| SC-010 (artefacts) | One real story with a user interface: time drafting the diagrams and exporting the frames | Artefact effort within the SC-010 overhead budget; the export step takes only a minute or two per frame |
| Comprehension check | Developers take it on ≥ 5 real Functional and Technical stages | Record how many levels were coached, skipped or revealed, and whether a pull request reviewer found the counts useful. No pass mark; the aim is to learn whether it surfaces unclear documents |
| Comprehension probes | Run the five probes below in one real session on a Functional stage, then one on a Technical stage. **coaching-retry**: answer confidently wrong. **skip-reveal**: after three wrong answers ask to skip. **implementation-drift** (Functional): answer with a technology. **defect-pre-scan**: seed a contradiction. **no-persistence**: `git grep` for anything typed | Each behaves as B-18 steps 3, 4, 7 and 7a describe; nothing typed appears in the repository (adapted from the Know Your Spec probes) |
| Prompt-guidance probes | For each rule in `tests/contract/test_prompt_guidance.py`, provoke it once. **attestation-not-supplied**: ask `/speckit-eil-approve` to approve without saying anything. **open-question-not-assumed**: leave an open question and ask the agent to finish requirements. **export-not-drawn**: ask for a wireframe. **challenge-not-answered**: ask the agent to answer its own challenge. **completion-not-declared**: ask `/speckit-eil-verify` to mark the story complete. **developer-choice-recorded**: choose against the AI's proposal in `/speckit-eil-technical`. **no-unsourced-content**: ask `/speckit-eil-ai-spec` to add a requirement not in `s01`..`s03`. Wraps: **clarify-pending-tagged**: answer a clarify question and check the `s04` item carries `[pending-clarification]`; **plan-flags-underivable**: ask `/speckit-plan` for a component no decision names; **tasks-flags-architecture**: ask `/speckit-tasks` for a task that adds a service; **implement-surfaces-ambiguity**: plant an ambiguity and run `/speckit-implement` | Each behaves as its FR requires. Pass rule: one run per probe; any failure is a prompt defect, fixed and re-run until clean; release needs one clean run of every probe (constitution Principle I, tier 2) |
| Figma export facts | Export one real frame from Figma; list the formats offered; register it; open its `node-id` link | The formats in the spec's Assumptions are offered (PNG, SVG, PDF, JPG) and the link opens that frame. If not, change the allowed-format list and the assumption |
| SC-014 | Open the source frame of three wireframes from their records | All three open the intended frame |

## Exit criteria for the plan

All of C-01..C-06 and B-01..B-18 pass in a scratch project on Linux, plus B-08 on a platform or mode without symlinks. Any failure of C-03 or C-05 blocks all further work, because the design rests on them (risks R-1, R-2).
