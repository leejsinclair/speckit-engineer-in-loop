# Implementation Plan: Proportionate Revalidation

**Branch**: `002-proportionate-revalidation` | **Date**: 2026-09-30 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/002-proportionate-revalidation/spec.md`

## Summary

Refine the Engineer-in-the-Loop workflow (001) so the developer is asked only what earns their attention. Four mechanisms in the stdlib-only `eil` helper do this, and the prompts only present them. Decisions are in [research.md](research.md).

1. **Content blocks with recorded hashes and provenance** (D-30 to D-33). Every paragraph, item, table and diagram is a block, hashed and recorded in a new non-fingerprinted `provenance` region. The helper classifies each block as restated, decided or inferred. The AI's judgement can only narrow a verified citation, never create one. Only inferred blocks need review, and review status comes from recorded hashes, not from hand-edited `[ai-draft]` tags.
2. **Item-level staleness in every layer** (D-34, D-35). AI Specification items, plan sections, tasks and evidence rows record the source versions they were derived from. Staleness propagates through the trace graph, and `enter` blocks only the work that traces to something stale, pending, unreviewed or under correction.
3. **One review-list protocol** (D-36, D-37). Every review (inferred content, changes, affected tasks, stale evidence, low challenges, unknown or diagram currency) is one list with a digest, answered in one verbatim reply and recorded with the person's name. Changes to an approved stage are accepted through one action. When every change is covered by recorded decisions, the approval carries forward on an explained "ok".
4. **Backwards corrections and a generated Change Log** (D-38, D-39). A problem found downstream is one action with an impact preview and a recorded origin. Documents are corrected in place to describe current truth, and a Change Log region records each accepted change.

Presentation changes are smaller: challenge severity, focused gate output, purpose labels, and a completion step scoped to what implementation touched (D-40, D-41). An upgrade adopts approved, unchanged content without asking anything (D-42).

## Technical Context

**Language/Version**: Python 3.11+, standard library only (Constitution III), as 001. Markdown for prompts and templates, and YAML for the manifests.

**Primary Dependencies**: None at runtime (`hashlib`, `json`, `re`, `pathlib`). Development only: `pytest`, `ruff`. Spec Kit `>=1.0.2.dev0`, unchanged.

**Storage**: Files only. New marked regions `provenance` (JSON) and `changelog` (generated Markdown) in each stage document s01 to s08 (s08 holds the completion-stage lists' acceptances and, after a re-signing of completion, its Change Log). Challenge and approval records gain fields. The `RF` item kind is added to s07. Optional `approvers` keys are added for the derived stages. No new file, document or alias.

**Testing**: pytest unit tests for determinism requirements 22 to 37 ([contracts/cli.md](contracts/cli.md)), written first. Scenario tests B-19 to B-28 ([quickstart.md](quickstart.md)) on a new reference-story fixture. Prompt contract tests for each new Tier 2 rule ([contracts/commands.md](contracts/commands.md)). Trial probes P-20 to P-22, SC-006 and SC-007 in `docs/trials.md`.

**Target Platform**: Linux, macOS and Windows, anywhere Spec Kit runs (unchanged).

**Project Type**: Spec Kit preset plus extension (a text-and-script package), unchanged.

**Performance Goals**: `status`, `check` and `enter` stay under 1 s on nine 1 MB documents with provenance regions holding 2,000 blocks (D-44, `tests/unit/test_performance.py`).

**Constraints**:

- The 001 Constraints on the Solution: nine documents, three aliases, state only in project files, proportionate hard gates with named overrides, no gamification.
- The AI never records an approval, reply, sign-off, decision or risk acceptance (FR-036).
- No rendering, no test execution and no network (FR-035, D-21).
- Read-only commands stay read-only (determinism requirements 9 and 33).
- An upgrade never loosens a gate silently (R-20).

**Scale/Scope**: One story package; tens to low hundreds of items, and up to a few thousand blocks per story. One developer drives a story, and conflicts are handled by version control.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Checked against constitution **1.2.1** (2026-09-30). 1.2.1 only rewords the severity bullet (anyone may raise, only a confirmer may lower); the design already follows it (FR-030, FR-048).

| Principle | Pre-research | Post-design | Evidence |
|---|---|---|---|
| I. Enforcement lives in the helper (two tiers) | Pass | Pass | **Tier 1**: every decision that blocks or records is a helper subcommand with a determinism test: block class, review status, staleness, work blocking, list digest, authority, carry-forward, correction ownership, evidence confirmation (cli.md 22 to 37; D-32 to D-38, D-41). The `[ai-draft]` cue is rendered by the helper and never read as status (D-33). **Tier 2**: the eight new prompt rules are listed with their contract test or trial probe (commands.md, last table) |
| II. Honest attestation limits | Pass | Pass | Carry-forward uses the Principle II acknowledgement exactly: explained, covered-only, verbatim, from a confirmer, marked `carried-forward` with `rests_on` (D-37). The fidelity limit is printed on every list showing restated content (FR-014). Evidence confirmation says "exists, result attested" (D-41). A hand-edited provenance region is R-21, stated like R-7. Every AI view carries `AI assessment:`, and AI-drafted Change Log summaries are labelled (D-39). The helper cannot prove that the parsed flags match the verbatim reply; it refuses the recognisable mismatches and states the rest as a limit on every list (D-36) |
| III. Test-first, no runtime dependencies | Pass | Pass | Stdlib only; unit tests before code for each determinism requirement; contract changes land with their tests (plan §Delivery order) |
| IV. Proportionate Ceremony | Pass | Pass | Each list and next action carries `purpose` (FR-032). No reconfirmation without a change: hash-settled blocks, adoption on upgrade (D-31, D-42). The helper establishes coverage, staleness, ownership and evidence existence rather than asking (D-34, D-37, D-38, D-41). Blocking is scoped to dependants (D-35), and low challenges are outstanding, not blocking (D-40). No human decision is removed: first approvals, the comprehension check and every settling answer still need a confirmer (FR-038, FR-048) |

| Constraint of Record | Post-design | Evidence |
|---|---|---|
| Nine documents, three aliases, no install-time edits, state in project files | Pass | New state is two regions inside existing documents (D-30, D-39); no file is added to the package |
| Proportionate hard gates with a named override | Pass | Low-challenge rule per Constraints of Record; every other criterion is still a hard stop; `unreviewed-ai-content` remains overridable (D-33, D-40) |
| Helper never renders or calls a network service | Pass | Evidence confirmation reads files only; a scenario asserts no subprocess is started (B-26) |
| Removal leaves documents in place | Pass | Regions are plain text in the documents |

| Workflow rule | How it is met |
|---|---|
| `/speckit-analyze` after `tasks.md`, before implementation | Scheduled as the gate between `/speckit-tasks` and implementation |
| Pull request states principles touched, no prompt-only gate, Tier 2 tests, and human interactions added or removed with purpose | The PR description for this feature lists: removed per-paragraph untagging, id naming in amend, per-change attestation, per-criterion reading, and all-artefact currency questions; added the one-reply lists (validation or approval), carry-forward sign-off (approval), correction ownership only when ambiguous (decision), and severity change (decision) |
| Contract file changes land with their tests | The delta contracts here are folded into 001's `contracts/*.md` in the same pull request as the tests that pin them |

**Deviation noted (not a violation)**: 001 cli.md says the helper "never edits a stage document's human content outside `eil` regions". D-28 (`review accept`) and `resolve` already make narrow, fingerprint-neutral or recorded exceptions. This feature adds one: re-rendering the `[ai-draft]` cue, which is fingerprint-neutral (D-23). The 001 contract text is amended to list the three exceptions explicitly.

**Complexity Tracking** is empty: no principle is departed from.

## Project Structure

### Documentation (this feature)

```text
specs/002-proportionate-revalidation/
├── spec.md              # Feature specification (input)
├── plan.md              # This file
├── research.md          # Phase 0: decisions D-30..D-44, risks R-16..R-21
├── data-model.md        # Phase 1: content block, provenance record, review list/answer, correction, RF
├── quickstart.md        # Phase 1: scenarios B-19..B-28, trial probes
├── checklists/
│   └── requirements.md  # Spec quality checklist
└── contracts/
    ├── cli.md               # Delta to 001 cli.md: new/changed subcommands, codes, determinism 22–37
    ├── document-format.md   # Delta to 001 document-format.md: regions, blocks, clauses, records
    └── commands.md          # Delta to 001 commands.md: one-reply list, new commands, wraps, Tier 2 rules
```

### Source Code (repository root)

Only files that change or are added are shown. The layout is 001's.

```text
extensions/eil/
├── extension.yml                    # + speckit.eil.accept, speckit.eil.correct; config keys
├── config-template.yml              # + approvers.ai-spec/plan/tasks/verification (default: technical)
├── commands/
│   ├── speckit.eil.accept.md        # NEW  one action for changes to an approved stage (D-37)
│   ├── speckit.eil.correct.md       # NEW  backwards correction (D-38)
│   ├── speckit.eil.amend.md         # → alias of accept
│   ├── speckit.eil.review.md        # → alias of accept
│   ├── speckit.eil.{requirements,functional,technical,ai-spec}.md  # classify + inferred list
│   ├── speckit.eil.{approve,challenge,complete,verify,status,next}.md
└── scripts/python/eil/
    ├── content.py        # NEW  FR-039 block splitting, block hash, keys (D-31)
    ├── blockstatus.py    # NEW  derived block status, upgrade adoption computed in memory (D-33, D-42)
    ├── staleness.py      # NEW  source versions, transitive staleness, blocked work (D-34, D-35)
    ├── reviews.py        # NEW  review list/answer/confirm, digest, authority (D-36, D-37)
    ├── corrections.py    # NEW  correct propose/open, CR lifecycle (D-38)
    ├── changelog.py      # NEW  changes[] → changelog region (D-39)
    ├── evidence.py       # NEW  automated-evidence confirmation, file reads only (D-41)
    ├── provenance.py     # classification (D-32); amend/review become wrappers over reviews.py
    ├── blocks.py         # + provenance, changelog regions; allowed-keys validation
    ├── fingerprint.py    # step 3 excludes the two new regions
    ├── trace.py          # RF kind; prose (traces:) clause; ADMINISTRATIVE_SECTIONS += Change Log, Record
    ├── handoff.py        # enter: work-scoped blocking, rederive (D-35)
    ├── package.py        # state(): block counts; adoption computed in memory (D-42)
    ├── gates.py          # unreviewed-ai-content by status; AIS-G03 item-scoped; VER-G07; ordering + summary
    ├── records.py        # approve: outstanding, reached, blocks; challenge severity (D-40)
    ├── identity.py       # derived-stage approvers
    ├── overview.py       # reached/rests_on, outstanding low, blocked work, recent changes
    └── cli.py            # new subcommands and flags
commands/                            # preset wraps
├── speckit.plan.md, speckit.tasks.md, speckit.implement.md, speckit.clarify.md
templates/
├── s01…s08 templates                # + ## Change Log and ## Record sections; s07 + ## Review Findings
└── s08-completion-template.md       # Diagram Currency: touched only, untouched on one line
tests/
├── unit/        test_content.py, test_regions.py, test_adoption.py, test_reviews_core.py,
│                test_staleness.py, test_classify.py, test_corrections.py, test_changelog.py,
│                test_evidence_confirm.py, … (full list in tasks.md) (+ updates)
├── scenario/    test_b19…b28_*.py, test_interaction_count.py
├── contract/    test_prompt_guidance.py (+6 rules), test_install.py (new commands, config keys)
└── fixtures/reference_story.py   # reference-story builder (SC-001 fixture)
docs/trials.md                       # P-20..P-22, SC-006, SC-007
README.md, CHANGELOG.md              # what the developer is asked now, and why; attestation limits R-21
```

**Structure Decision**: This is the existing single repository (preset at the root, extension in `extensions/eil/`). New logic goes into six focused helper modules rather than growing `gates.py` (already 1,689 lines) and `provenance.py`. The existing commands `amend` and `review` keep working as aliases, so stories in progress and muscle memory are not broken.

## Delivery order

The binding checkpoints are in the order `/speckit-tasks` should keep. Each step is test-first.

1. **Foundations**: `content.py` (blocks and hashes), the new regions in `blocks.py` and `fingerprint.py`, adoption (D-42), and the review-list core (list, digest, answer, authority, reply check, conflicts; D-36), which every story uses. Checkpoint: determinism requirements 22, 23, 32 and 33 pass, and B-27 shows an upgraded 001 story unchanged in state.
2. **Story 1**: `staleness.py` and work-scoped `enter`. Checkpoint: B-19 (SC-002, SC-003).
3. **Story 2**: classification in every stage (including plan, tasks and verification, FR-012), status-based `unreviewed-ai-content`, cue rendering, and the `inferred` list.
4. **Story 3**: `changes` list, `confirm`, carry-forward, and `amend`/`review` as aliases. Checkpoint: B-22 (SC-004).
5. **Story 4**: corrections, RF, unsettled challenges, Change Log. Checkpoint: B-23 (SC-005), B-24.
6. **Stories 5 and 6**: severity, focused `check`, purpose labels, completion lists, evidence confirmation. Checkpoint: B-25, B-26.
7. **Measurement and docs**: interaction-count harness (SC-001), trial probes, README and CHANGELOG, and 001 contracts folded in.

## Phase Outputs

| Phase | Artifact | Status |
|---|---|---|
| 0 | [research.md](research.md) | Complete. No `NEEDS CLARIFICATION` in Technical Context |
| 1 | [data-model.md](data-model.md) | Complete |
| 1 | [contracts/](contracts/) | Complete (3 delta files) |
| 1 | [quickstart.md](quickstart.md) | Complete |
| 2 | `tasks.md` | Not part of this command; run `/speckit-tasks` |

## Open Items Carried Forward

- **Uncommitted work in the tree**: D-23 to D-29 (`review`, `amend`, the item-level `state()`, and section-scoped judgments) are implemented but uncommitted, together with the constitution 1.2.1 and 001 amendments. This plan builds on them, so commit them first, as their own change.
- **R-16 (AI "adds nothing" misjudged)**: mitigated, not removed. SC-006 and probe P-21 measure it once human trials run (SC-006 and SC-007 depend on the 001 trials, which have not run yet).
- **Reference story fixture**: defined here (quickstart prerequisites) as the spec's Assumptions require. Its exact contents are fixed by the first task.
- **Paragraph moves between sections** re-surface as needing review (D-31). This is accepted as conservative. Revisit only if trials show churn.
