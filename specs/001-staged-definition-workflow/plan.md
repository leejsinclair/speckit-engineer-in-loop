# Implementation Plan: Staged Definition Workflow (Engineer-in-the-Loop Preset)

**Branch**: `001-staged-definition-workflow` | **Date**: 2026-09-25 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/001-staged-definition-workflow/spec.md`

## Summary

Deliver a Spec Kit **preset** plus a companion **extension** (working name `eil`, "engineer-in-the-loop") that turns a story into a nine-document package, gated by four definition stages, each closed by one recorded developer confirmation.

The approach, decided in [research.md](research.md):

- **Preset** (`preset.yml`): templates for the nine documents, a replacement of `speckit.specify` so a story starts at Requirements, and `wrap` overrides of `clarify`, `plan`, `tasks`, `analyze`, `checklist` and `implement` so each syncs aliases, refuses when a gate is unmet, and (for clarify and analyze) applies the pending-answer and full-chain rules.
- **Extension** (`extensions/eil/`): the stage, artefact, approval, challenge, override, abbreviation, trace and status commands, plus a **deterministic, stdlib-only Python helper** that owns everything that must not depend on an AI following instructions: content fingerprints, alias and mirror handling, gate evaluation, traceability checks, diagram and exported-file checks, record writing and overview generation.
- **Comprehension check** (adapted from the Know Your Spec preset, D-22): before approving Functional or Technical, the developer answers five questions of rising difficulty about the document's own content. The helper picks the targets deterministically and records levels and outcomes, never answers. Approval requires it was taken on the current version, not that it was passed.
- **Design artefacts** follow the C4 model (context, container, component), sequence diagrams and ER diagrams, written as Mermaid inside the stage document that owns them (D-17, D-18). Wireframes are Figma **static exports** kept in the package's `assets/` directory with their source frame and file fingerprint (D-19). The helper checks structure and cross-diagram consistency (D-20) but never renders (D-21).
- **State** lives in the nine documents themselves (machine-readable JSON blocks inside marked regions) and, for exported files, the `assets/` directory. No extra state files, no database, no service.
- Gates are **attestation-level** (spec Assumptions): the helper makes bypasses detectable and refusals mechanical; it cannot stop a person editing files.

## Technical Context

**Language/Version**: Python 3.11+ (stdlib only) for the helper, the same floor as `specify-cli` itself (`Requires-Python >=3.11`). Markdown for templates and command prompts. YAML for the two manifests.

**Primary Dependencies**: None at runtime beyond the Python standard library (`hashlib`, `json`, `re`, `pathlib`, `os`, `shutil` to copy exports, `subprocess` for `git config`). Diagram checks use line-oriented regexes over a stated Mermaid subset, with no Mermaid or image library. Development only: `pytest`. Spec Kit `>=1.0.2.dev0` (the installed version, F-13; presets with `wrap`/`prepend`/`append` and script strategies, extension hooks and `provides.scripts` are all present in it).

**Storage**: Files only. Stage documents in the feature directory, each carrying its own approval, challenge, override and artefact-export records as delimited JSON blocks; exported wireframe and diagram-image files under `assets/`. Approver configuration in the extension's config file. No other state.

**Testing**: `pytest` unit tests for the helper; contract tests that install the preset and extension into a scratch Spec Kit project (`specify preset add --dev`, `specify extension add --dev`) and assert manifests, resolution and registered commands; scenario tests that replay the [quickstart](quickstart.md) against a scratch project; a small set of prompt-behaviour trials for the SC-007/008/010 measures (human-run, not automated).

**Target Platform**: Linux, macOS and Windows (any platform Spec Kit supports). One Python implementation avoids separate bash and PowerShell variants; the symlink-or-mirror fallback (FR-053) covers Windows without link support.

**Project Type**: Spec Kit preset + extension (a text-and-script package, not an application). Closest analogue: the reference preset `speckit-presets-gamified`, laid out the same way (root `preset.yml`, `extensions/<id>/`, `tests/`).

**Performance Goals**: A helper invocation (`sync`, `check`, `status`) completes in under 1 second for a story package (nine files, each well under 1 MB). Install-to-first-story under 10 minutes (SC-001) is a documentation and prerequisites goal, not a compute one.

**Constraints**: No edits to existing Spec Kit or project files at install (FR-001); clean removal (FR-005, SC-009); every gate a hard stop with a recorded override; no gamification; state visible in ordinary version control (FR-046); the AI cannot record an approval (FR-012), enforced by command design and by recording the human's verbatim confirmation, and honestly documented as attestation-level.

**Scale/Scope**: One story package per feature: 9 documents plus 3 aliases and an `assets/` directory; tens to low hundreds of traceable items per story. No multi-user concurrency: one developer drives a story, and merge conflicts are handled by version control.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

The constitution is ratified (v1.1.0, 2026-09-25) with three principles. The table below checks the plan against them first, then against the spec's decided **Constraints on the Solution**.

| Principle | Pre-research | Post-design | Evidence |
|---|---|---|---|
| I. Enforcement lives in the helper (two tiers) | n/a (ratified after the first plan) | Pass | Tier 1: gates, refusals, fingerprints, aliases, artifact checks and comprehension records are all `eil` subcommands with determinism tests (contracts/cli.md 1 to 21); hooks carry no refusal (D-05). Tier 2: prompt-only guidance (reworded retries, no assumed open questions, no drawn exports) is covered by the prompt contract test and the trial probes (tasks T072, T131) |
| II. Honest attestation limits | n/a | Pass | Spec Assumptions and D-11, D-21, D-22 state each limit; the README states them (T136); AI verdicts carry `AI assessment:` (cli.md `--judgments`); the AI cannot record an approval (FR-012, `ai-approval`) |
| III. Test-first, no runtime dependencies | n/a | Pass | Technical Context: stdlib only, `pytest` dev-only; tasks write tests first per story; every determinism requirement has a unit test and C-01..C-05 are contract tests |

| Constraint (spec) | Pre-research | Post-design | Evidence |
|---|---|---|---|
| Nine documents, exactly three aliases, no other aliases | Pass | Pass | [contracts/document-format.md](contracts/document-format.md) §Package; helper creates only the three. The `assets/` directory holds exports, not documents or aliases |
| Design artefacts: C4 L1-L3, sequence, ER, Mermaid text, Figma static exports | n/a (added after the first plan) | Pass | research D-17..D-21; [data-model.md](data-model.md) §Artefact; document-format §Artefacts in documents |
| AI Specification is the Spec Kit "spec" (`spec.md` alias) | Pass | Pass | research D-06; core scripts confirmed to require `spec.md`/`plan.md`/`tasks.md` by name |
| Preset plus companion extension; no edit to Spec Kit | Pass | Pass | research D-01, D-08; install touches only `.specify/` managed locations |
| State in project files; no DB, service, UI | Pass | Pass | research D-03; [data-model.md](data-model.md) |
| Hard-stop gates with a recorded override | Pass | Pass | contracts/cli.md exit codes; override entity |
| Not advisory, not gamified | Pass | Pass | no scoring or narrative anywhere in the model; the comprehension check (D-22) records outcomes only, has no score, streak, timer or reward, and is required to be taken, not to be passed |

**Complexity Tracking** is empty: no violations to justify.

## Project Structure

### Documentation (this feature)

```text
specs/001-staged-definition-workflow/
├── spec.md              # Feature specification (input)
├── plan.md              # This file
├── research.md          # Phase 0: decisions D-01..D-22, alternatives, risks
├── data-model.md        # Phase 1: entities, identifiers, states, validation
├── quickstart.md        # Phase 1: runnable validation scenarios
├── checklists/
│   └── requirements.md  # Spec quality checklist
└── contracts/
    ├── cli.md               # The `eil` helper: subcommands, flags, exit codes, JSON output
    ├── document-format.md   # Stage document layout, machine blocks, fingerprint algorithm
    ├── manifests.md         # preset.yml, extension.yml, config, hooks (shape and rules)
    └── commands.md          # Behavioural contract of every slash command and wrap
```

`tasks.md` is produced later by `/speckit-tasks` and is not created here. This feature's own directory is not a governed package (no `s00-README.md`), so it keeps ordinary Spec Kit file names (FR-006, FR-069).

### Source Code (repository root)

```text
preset.yml                          # Preset manifest (id: engineer-in-the-loop)
templates/
├── s00-readme-template.md          # Overview skeleton (generated content region)
├── s01-requirements-template.md
├── s02-functional-spec-template.md
├── s03-technical-spec-template.md      # each stage template also carries its artefact sections (D-17)
├── spec-template.md                # Override: becomes the AI Specification (s04) skeleton
├── plan-template.md                # Override: adds trace references (s05)
├── tasks-template.md               # Override: adds trace references (s06)
├── s07-verification-template.md
└── s08-completion-template.md
commands/                           # Preset command overrides
├── speckit.specify.md              # strategy: replace  (start at Requirements)
├── speckit.clarify.md              # strategy: wrap     (pending answers into AI Spec)
├── speckit.plan.md                 # strategy: wrap     (sync + gate + s05 creation)
├── speckit.tasks.md                # strategy: wrap     (sync + gate + s06 creation)
├── speckit.analyze.md              # strategy: wrap     (adds full-chain check)
├── speckit.checklist.md            # strategy: wrap     (adds s01/s02 as read-only context)
└── speckit.implement.md            # strategy: wrap     (sync + gate)
extensions/eil/
├── extension.yml
├── .extensionignore                # read by `specify extension add` from here (research F-16)
├── config-template.yml             # Approver configuration
├── commands/                       # 15 commands
│   ├── speckit.eil.requirements.md   # also starts the story and creates s00 + s01
│   ├── speckit.eil.functional.md
│   ├── speckit.eil.technical.md
│   ├── speckit.eil.ai-spec.md
│   ├── speckit.eil.verify.md
│   ├── speckit.eil.complete.md
│   ├── speckit.eil.artifact.md        # register a wireframe or diagram-image export
│   ├── speckit.eil.comprehend.md      # comprehension check before approving s02 or s03
│   ├── speckit.eil.challenge.md
│   ├── speckit.eil.approve.md
│   ├── speckit.eil.override.md
│   ├── speckit.eil.abbreviate.md
│   ├── speckit.eil.resolve.md         # carry a pending answer upstream (FR-067)
│   ├── speckit.eil.trace.md
│   └── speckit.eil.status.md
└── scripts/python/eil/
    ├── __main__.py                 # entry: `python3 <dir>`; adds its parent to sys.path, then calls cli.main
    ├── results.py                  # Refusal and Finding types, exit codes, single-object JSON output
    ├── clock.py                    # the one wall-clock read, so tests can replace it
    ├── templates.py                # load a template through Spec Kit's resolve-template.sh
    ├── cli.py                      # argument parsing, exit codes, JSON/text output
    ├── package.py                  # feature-dir discovery, governed test (FR-069), stage derivation
    ├── blocks.py                   # read/write the delimited JSON blocks
    ├── fingerprint.py              # normalisation + SHA-256 (FR-011, FR-044)
    ├── aliases.py                  # symlink-or-mirror, fault detection, refresh (FR-049..053)
    ├── gates.py                    # per-stage criteria, structural checks, gate result
    ├── trace.py                    # ID extraction, chain checks, impact (FR-025..031, 043, 068)
    ├── artifacts.py                # ART items, attachments, export records, file hashes (FR-071..078, 082..083)
    ├── diagrams.py                 # Mermaid subset extraction and consistency rules (FR-079..081)
    ├── comprehension.py            # deterministic target selection, record, staleness (FR-087..094)
    ├── records.py                  # approvals, overrides, challenges, abbreviations
    ├── identity.py                 # approver resolution and configuration check (FR-013, FR-066)
    └── overview.py                 # generate s00-README.md (FR-054..056)
tests/
├── unit/                           # fingerprint, blocks, aliases, gates, trace, records, overview, artifacts, diagrams, comprehension
├── fixtures/                       # mermaid/ (passing, failing, borderline, VERSION.md), assets/ (sample exports)
├── helpers/                        # scratch.py (scratch Spec Kit project), package.py (story-package builder)
├── conftest.py
├── contract/                       # install into a scratch project; manifest and resolution asserts; stubs/ (risk spike), prompt guidance, core-accepts-aliases
└── scenario/                       # replay quickstart.md scenarios end to end
README.md                           # Install, configure, use, remove (SC-001 documentation)
CHANGELOG.md
LICENSE                             # MIT
pyproject.toml                      # Python >=3.11, no runtime dependencies, pytest markers, ruff config
.gitignore
tools/stage.py                      # stages the shipped files for install and release archives (F-16)
.github/pull_request_template.md    # constitution checklist (Principles I to III)
docs/trials.md                      # human-trial protocols and recording sheets (SC-007, 008, 010, 014, comprehension and prompt probes)
```

**Structure Decision**: A single repository shaped like the reference preset: preset at the root, extension in `extensions/eil/`, tests alongside. The preset cannot declare a dependency on the extension (its manifest schema only carries `requires.speckit_version`), so every preset wrap begins with a guard that stops with install instructions if the extension's helper is absent (research D-08). The helper lives in the extension, not the preset, because only extensions can register hooks and own a config file.

## Phase Outputs

| Phase | Artifact | Status |
|---|---|---|
| 0 | [research.md](research.md) | Complete. No `NEEDS CLARIFICATION` remain in Technical Context. |
| 1 | [data-model.md](data-model.md) | Complete |
| 1 | [contracts/](contracts/) | Complete (4 files) |
| 1 | [quickstart.md](quickstart.md) | Complete |
| 2 | `tasks.md` | Not part of this command; run `/speckit-tasks` |

## Open Items Carried Forward

- **OQ-001 (checklist compatibility)**: resolved in design by wrapping `speckit.checklist` to add `s01`/`s02` as read-only context alongside the aliased AI Specification (D-13). The decision is only proven by quickstart scenario B-11 against the real command; until then the spec's OQ-001 stays open.
- **R-1 custom template names**: the design relies on presets accepting template names beyond Spec Kit's five core ones. Contract test C-03 proves it before any other work builds on it; fallback is in research D-02.
- **R-14 and R-15 comprehension**: AI's judgement of understanding is fallible and skipping is allowed by design; the safeguard is that skipped and revealed counts reach the approval record and the overview.
- **R-10 Mermaid C4 is experimental**: the accepted syntax is a stated subset in document-format.md, pinned by fixtures; the fallback for an unsupported diagram is a registered image with no structural checks.
- **Wireframe review**: the helper proves an export exists, matches its record and links to a frame; only a human can confirm it is the right screen (D-21).
- **Constitution**: ratified v1.1.0; the Constitution Check above was re-run against it. Principle I's two tiers were clarified after `/speckit-analyze` found the first wording contradicted the design.
