# Implementation Plan: Proportionate Effort

**Branch**: `003-proportionate-effort` (spec directory; work is on `main`, no branch created) | **Date**: 2026-10-02 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/003-proportionate-effort/spec.md`

## Summary

This feature makes the first pass through a story proportionate to its size. It fixes the defects behind the 2026-10-01 trial, where process overhead was about 96% against the 25% target. The helper makes every decision that blocks or records; the prompts only present. The decisions are in [research.md](research.md).

1. **Targeting** (D-46, D-47):
   - `start` always moves the active-story pointer.
   - Every write names its story.
   - A write with an ambiguous target is refused before anything is touched.
   - A start on an unexpected branch is refused until a person confirms it.
2. **Records out of the documents** (D-48 to D-50):
   - One `eil-record.json` per story holds every JSON record.
   - The regions in each document keep one rendered line each.
   - `eil show` gives a clean view in chat.
   - The `[ai-draft]` cue leaves the document text, so the agent's text-match edits stop breaking.
   - Fingerprints are untouched, so no approval moves.
3. **Lists sized to the developer** (D-51):
   - The helper picks one-at-a-time or summary mode from the list size (threshold 8, configurable).
   - Per-entry answers are stored in a review session that survives compaction.
   - "ok to the rest" closes a list.
   - Scaffolding sections count as one entry each.
4. **Small-story profile** (D-52): authorised once by a named person with a reason, it brings:
   - no wireframe exports;
   - one combined review of the AI Specification, plan and tasks before implementation;
   - two comprehension levels.

   Every approval is unchanged.
5. **Asking at the right level** (D-53 to D-55):
   - Choices with no observable effect become `ai-decided` decisions, validated on the review list.
   - Comprehension skips the developer's own decisions, gains a one-line waiver, and shows each item before asking.
   - The gap scan runs during drafting.
6. **One-word approvals** (D-59): the helper's fixed approval question states what is confirmed; "ok" approves and is recorded with that question; the name is asked once per session. Relies on constitution 1.2.2 (Principle II clarification), applied 2026-10-02.
7. **Upgrade and defects** (D-56 to D-58):
   - Legacy approvals adopt unchanged content and re-sign on one reply (the root cause was reproduced on the trial snapshot).
   - `classify` is additive.
   - The plan's own headings are exempt.
   - A `reviewed` terminal state is added, and status reports `done` after completion.

## Technical Context

**Language/Version**: Python 3.11+, standard library only (Constitution III). Markdown prompts and templates, YAML manifests.

**Primary Dependencies**: None at runtime (`json`, `hashlib`, `re`, `pathlib`, and `subprocess` for one read-only `git symbolic-ref`, as `identity.py` already does for `git config`). Development only: `pytest`, `ruff`. Spec Kit `>=1.0.2.dev0`, unchanged.

**Storage**: Files only.
- New: `specs/<story>/eil-record.json` (D-48).
- Changed: the five marked regions hold rendered lines, not JSON.
- New configuration keys: `main_branches` and `review.one_at_a_time_max`.

**Testing**:
- pytest unit tests, written first, for determinism requirements 38 to 53 ([contracts/cli.md](contracts/cli.md)).
- Scenario tests B-29 to B-37 ([quickstart.md](quickstart.md)), including the required scenario tests for the upgrade migration (B-30) and the ambiguous-target refusal (B-29).
- Prompt contract tests for the ten Tier 2 rules ([contracts/commands.md](contracts/commands.md)).
- Trial probes P-23 to P-31, and the SC-003/SC-004 timing run.

**Target Platform**: Linux, macOS and Windows, wherever Spec Kit runs (unchanged).

**Project Type**: Spec Kit preset plus extension (unchanged).

**Performance Goals**:
- `status`, `check`, `enter` and `show` stay under 1 s on the 002 performance fixture (`tests/unit/test_performance.py`), now with records in the file.
- `show` of a 100 KB stage prints at most 25% of the bytes that reading the document did on the trial story.

**Constraints**:
- No gate, approval, attestation or recorded override becomes weaker (FR-044).
- The AI authorises, waives, approves and answers nothing (FR-045).
- Read-only subcommands write nothing, including during migration.
- The helper never creates or switches branches and never calls the network.
- Fingerprints are computed exactly as in 002.

**Scale/Scope**: One story package with up to a few thousand blocks. The record file is a few hundred KB at most and is never read by the agent.

## Constitution Check

*GATE: must pass before Phase 0 research; re-checked after Phase 1 design.*

Checked against constitution **1.2.2** (applied 2026-10-02; Principle II clarified for short replies to an explicit approval question).

| Principle | Pre-research | Post-design | Evidence |
|---|---|---|---|
| I. Enforcement lives in the helper | Pass | Pass | **Tier 1** (all helper code, each with a determinism test 38 to 52): story targeting and refusal, branch guard, record file and integrity, list mode, review sessions, scaffolding grouping, adoption with `adopted-pending`, legacy re-signing, profile effects, the `ai-decided` reason check, own-decision exclusion, the waiver, additive classify, plan exemptions, `reviewed`/`done`. **Tier 2**: nine prompt rules, each with a contract test and probe ([contracts/commands.md](contracts/commands.md), last table). No gate, refusal or record exists only in a prompt. |
| II. Honest attestation limits | Pass | Pass | Several records make plain what a person did and did not look at: `own-decision` is distinct from `understood`; `seen: false` marks entries accepted without being seen in full; `re-signed-without-comparison` marks legacy re-signings; `ai-decided` is labelled as the AI's; the profile is shown at every affected gate. The record file has the same attestation-level limit as the regions it replaces (R-25), stated in README. The AI never supplies a reply or confirmation. One-word approvals (D-59) rely on the clarification that a short reply to an explicit approval question is an ordinary confirmation; the reply is recorded verbatim with the helper's question, so the record shows what was confirmed. |
| III. Test-first, no runtime dependencies | Pass | Pass | Standard library only. The one `subprocess` call is read-only local git, with precedent in `identity.py`. Tests are written first for each determinism requirement. Contract deltas land with their tests. |
| IV. Proportionate Ceremony | Pass | Pass | Every interaction added or removed is in the spec's Principle IV table and is repeated in the PR description. Who decided, which list mode applies and whether content changed are established by the helper, not asked (D-51, D-54, D-56). No human decision is removed: `ai-decided` decisions are each settled by a person's reply on the review list (clarification 2026-10-02), so the AI proposes and the person validates. The AI makes no decision of its own. |

| Constraint of Record | Post-design | Evidence |
|---|---|---|
| Nine documents, three aliases, no install-time edits, state in project files | Pass, with a deviation noted below | The documents and aliases are unchanged. `eil-record.json` is a record file in the story directory, like `assets/`. |
| Proportionate hard gates with named overrides | Pass | The profile meets the wireframe criterion through the criterion's own "recorded reason" clause. Its relaxation of plan and task entry is a recorded, named, reasoned override of `unreviewed-ai-content`, shown as an override. Every other criterion is unchanged. |
| No rendering, no network | Pass | A read-only local git query only. |
| Removal leaves records in place | Pass | The record file is plain project text. |

**Deviations noted (not violations).**
1. **A new record file.** 002 D-30 kept every record inside the documents, and 002's spec assumed new records would be record blocks inside existing documents. This feature reverses that for the reason in D-48. 001's Constraints on the Solution names nine documents, three aliases and an assets directory. Its text is amended in the same change to name `eil-record.json` as a record file, as 002 amended 001 before. See Complexity Tracking.
2. **002 FR-010 and FR-046 amended.** Summary mode shows summaries, with full text on request (spec FR-015). The `[ai-draft]` cue no longer appears in document text (D-50; spec FR-037 allows either form). 002's spec gains an amendment note citing 003, as 002 did for 001.
3. **The `developer-choice-recorded` probe** is narrowed to observable choices (D-53).

## Project Structure

### Documentation (this feature)

```text
specs/003-proportionate-effort/
├── spec.md              # Feature specification (input)
├── plan.md              # This file
├── research.md          # Phase 0: D-46..D-58, R-22..R-28, trial reproduction
├── data-model.md        # Phase 1: record file, regions, classes, sessions, profile, outcomes
├── quickstart.md        # Phase 1: B-29..B-36, manual trial check, probes
├── checklists/
│   └── requirements.md  # Spec quality checklist
└── contracts/
    ├── cli.md               # Delta: write/read table, new and changed subcommands, determinism 38–52
    ├── document-format.md   # Delta: record file, rendered regions, ai-decided DEC, exempt headings
    └── commands.md          # Delta: prompt changes, Tier 2 rules with tests and probes
```

### Source Code (repository root)

Only files that change or are added are shown. The layout is 001's.

```text
extensions/eil/
├── config-template.yml              # + main_branches, review.one_at_a_time_max
├── extension.yml                    # (no new command; `show`, `profile` are helper subcommands)
├── commands/
│   ├── speckit.eil.requirements.md  # pointer rule, profile proposal, show
│   ├── speckit.eil.functional.md    # mechanism not asked, profile wireframes, gap scan, list modes
│   ├── speckit.eil.technical.md     # ai-decided rule, gap scan, list modes
│   ├── speckit.eil.comprehend.md    # --by, item shown, behaviour, reread, waive
│   ├── speckit.eil.abbreviate.md    # propose-not-authorise, profile set/withdraw
│   ├── speckit.eil.{ai-spec,5-plan,6-tasks}.md  # derived list under the profile
│   ├── speckit.eil.{accept,approve,verify,complete,correct,resolve,challenge}.md  # list modes, severity, show
│   └── speckit.eil.{status,next}.md # reviewed, done
└── scripts/python/eil/
    ├── recordfile.py     # NEW  eil-record.json read/write/validate, migration (D-48)
    ├── target.py         # NEW  story resolution with source, ambiguity, branch guard (D-46, D-47)
    ├── show.py           # NEW  clean view (D-49)
    ├── profile.py        # NEW  small-story profile set/withdraw/effects (D-52)
    ├── package.py        # record()/write_record(); state 'reviewed'; resolve via target.py
    ├── blocks.py         # regions render lines; JSON-body fallback; tag stripping
    ├── provenance.py     # classify additive + skipped; no cue rendering; ai-decided always inferred
    ├── blockstatus.py    # adopted-pending (D-56)
    ├── reviews.py        # mode, groups, summaries, scaffolding, sessions, --entry/--rest, legacy entry, derived
    ├── records.py        # approval ai_decided[], reached re-signed-without-comparison, rendered line
    ├── comprehension.py  # own-decision, --by, waive, profile levels
    ├── gates.py          # ai-decided reason, _PLAN_EXEMPT from ADMINISTRATIVE_SECTIONS, profile wireframe, assessment via record()
    ├── handoff.py        # enter under profile
    ├── overview.py       # reviewed/done, profile line, per-stage review counts, branch confirmation
    ├── identity.py       # main_branches config
    └── cli.py            # write/read-only table, `story` on every result, new subcommands and flags
commands/speckit.specify.md          # pointer rule, --feature-dir always, branch confirmation, profile proposal
tests/
├── unit/        test_target.py, test_branch_guard.py, test_recordfile.py, test_show.py,
│                test_list_modes.py, test_review_sessions.py, test_profile.py, test_ai_decided.py,
│                test_comprehension_own.py, test_classify.py (+), test_adoption.py (+), test_status.py (+),
│                test_gates_aispec.py (+ plan exempt)
├── scenario/    test_b29…b36_*.py, test_interaction_count.py (+ profile run)
├── contract/    test_prompt_guidance.py (+9 rules), test_install.py (config keys)
└── fixtures/    legacy_upgrade.py, two_stories.py
docs/trials.md                       # P-23..P-30; SC-010 row (done 2026-10-02)
README.md, CHANGELOG.md              # one CHANGELOG entry per change 1–9 with its Principle IV interactions; R-25, R-26 limits
specs/001-staged-definition-workflow/spec.md, specs/002-proportionate-revalidation/spec.md  # amendment notes
```

**Structure Decision**: The same single repository. Four new focused modules keep `cli.py` (1,003 lines) and `gates.py` (1,771 lines) from growing further. Every record read and write moves behind `Package.record` and `Package.write_record`, the only seam the record-file change needs (53 references to `read_provenance`, `read_region`, `write_region` and `write_provenance`, including their definitions).

## Delivery order

Each step is test-first. The checkpoints are binding for `/speckit-tasks`.

1. **Targeting first**, because it protects every later step's records: `target.py`, the write/read table, `story` on results, the `start` pointer and branch guard, and the prompt pointer rule. Checkpoint: determinism 38 to 41 and B-29.
2. **Record file**: `recordfile.py`, the `Package` accessors, rendered regions, migration in `sync`, integrity, and `show`. Checkpoint: determinism 42 to 45 and B-31. Fingerprints of the reference story must be byte-for-byte unchanged.
3. **Upgrade**: reproduce the trial judgment loss on the `legacy_upgrade` fixture first (D-56), then `adopted-pending`, the legacy entry and re-signing, and cue stripping. Checkpoint: determinism 50 and B-30.
4. **Lists**: modes, summaries, scaffolding, sessions, `--entry` and `--rest`, and `review show`. Checkpoint: determinism 46 to 48 and B-32.
5. **Smaller defects**: classify additive, plan exemptions, `reviewed`/`done`, and severity in prompts. Checkpoint: determinism 49 and B-36.
6. **Decisions and comprehension**: `ai-decided`, own-decision, waive, and the gap scan in prompts. Checkpoint: determinism 51, B-34 and B-35.
7. **Profile**, last because it composes steps 4 and 6: `profile.py`, the gate, enter, the derived list and comprehension levels. Checkpoint: determinism 52, B-33 and SC-005.
8. **Docs and measurement**: the nine prompt contract tests (written with each prompt change above, verified here), probes P-23 to P-30, README limits, one CHANGELOG entry per change, the 001 and 002 amendment notes, and the folded contracts.

## Complexity Tracking

| Departure | Why needed | Simpler alternative rejected because |
|---|---|---|
| A record file beside the nine documents (departs from 002 D-30, not from the constitution's text) | Records were 58% to 87% of each document and drove context exhaustion (5 compactions, 166k tokens) | Compressing or shortening the regions still leaves the bulk in the document an agent reads; separate files per stage add nine files that confuse readers |

## Phase Outputs

| Phase | Artifact | Status |
|---|---|---|
| 0 | [research.md](research.md) | Complete. No `NEEDS CLARIFICATION` in Technical Context |
| 1 | [data-model.md](data-model.md) | Complete |
| 1 | [contracts/](contracts/) | Complete (3 delta files) |
| 1 | [quickstart.md](quickstart.md) | Complete |
| 2 | `tasks.md` | Not part of this command; run `/speckit-tasks` |

## Open Items Carried Forward

- **Uncommitted work in the tree**: the working tree still holds uncommitted changes from before this feature (the `amend` and `review` command files deleted, with prompt and test edits). Commit or discard them, as their own change, before implementation starts.
- **Judgment loss in the trial**: the cause is not yet proven. Step 3 reproduces it first. If the wrong-story overwrite (D-46) explains it fully, the re-keying in D-56 is dropped and the finding recorded in research.md.
- **Constitution 1.2.2** (Principle II, short replies to an explicit approval question): applied 2026-10-02 with `/speckit-constitution` (T098); see `constitution-patch-1.2.2.md`.
- **SC-003 and SC-004** need a timed human run under the profile. They are not automated.
- **No branch was created for this story**, as in the trial. The work is on `main` and `.specify/feature.json` points at 003. Once FR-006 ships, starting a story on `main` stays allowed.
