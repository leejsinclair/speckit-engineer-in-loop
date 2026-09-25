# Data Model: Staged Definition Workflow

All state is text in the story package (D-03 in [research.md](research.md)). "Stored" below means "recorded in a stage document or the extension config"; nothing is kept elsewhere. Entities come from the spec's Key Entities; FR references are to the spec.

## Story Package (directory)

`specs/<NNN>-<slug>/` where `NNN` is Spec Kit's feature number. Contains up to nine documents, three aliases and, once an export is registered, an `assets/` directory.

| Path | Kind | Created when |
|------|------|--------------|
| `s00-README.md` | Overview (generated) | Story started (FR-048) |
| `s01-requirements.md` | Stage document | Requirements stage begins |
| `s02-functional-spec.md` | Stage document | Functional Specification begins |
| `s03-technical-spec.md` | Stage document | Technical Specification begins |
| `s04-ai-spec.md` | Stage document | AI Specification begins |
| `s05-plan.md` | Stage document | first `plan` run |
| `s06-tasks.md` | Stage document | first `tasks` run |
| `s07-verification.md` | Stage document | Verification begins |
| `s08-completion.md` | Stage document | Completion begins |
| `spec.md` → `s04-ai-spec.md` | Alias | with its target |
| `plan.md` → `s05-plan.md` | Alias | with its target |
| `tasks.md` → `s06-tasks.md` | Alias | with its target |
| `assets/<file>` | Exported artefact (wireframe or diagram image) | `eil artifact register` (FR-047, FR-077) |

**Rules**
- **Governed** ⇔ `s00-README.md` exists (FR-069). Otherwise no gate, alias check or refusal applies (FR-006).
- A document never exists as an empty placeholder (FR-048). An alias never exists before its target (edge case "alias target not yet created").
- Stage documents are authoritative; the overview is derived (FR-056).
- No other file is created in the directory, except files under `assets/`. Document names use the `s` prefix and are never treated as numbers (FR-070).
- A file in `assets/` that no `ART` record names is reported as `orphan-asset` (a finding, not a refusal).

## Stage

Fixed ordered set. `order` is the stage's position; `document` its file.

| Stage | order | document | Approval required | Gate |
|-------|-------|----------|-------------------|------|
| requirements | 1 | s01 | yes | Requirements quality gate (13 criteria, plus `REQ-G14` context diagram) |
| functional | 2 | s02 | yes | Functional gate (13 criteria, plus `FUN-G14` sequence diagrams, `FUN-G15` wireframes, `FUN-G16` comprehension check taken on this version) |
| technical | 3 | s03 | yes | Technical gate (14 criteria, plus `TEC-G15` container, `TEC-G16` component, `TEC-G17` sequence, `TEC-G18` ER, `TEC-G19` comprehension check taken on this version) |
| ai-spec | 4 | s04 | **no** (automatic source-traceability check; human review optional, per spec Assumptions) | Source-traceability + no pending items + referenced artefacts unchanged since approval (FR-082) |
| plan | 5 | s05 | no | Derivable-from-decisions check (FR-057) |
| tasks | 6 | s06 | no | Trace + no-new-architecture check (FR-058) + every in-scope artefact covered (FR-083) |
| verification | 7 | s07 | no (evidence only, FR-062) | Every item, including every approved artefact, has status |
| completion | 8 | s08 | yes | Evidence reviewed; all verified or excepted (FR-064/065); each artefact current or a recorded deviation (FR-084) |

The added criteria are `structural` or `traceability` unless stated: each diagram criterion is one criterion covering existence (or a recorded reason it does not apply, FR-075), parsing (FR-080), level (FR-081) and consistency (FR-079). Wireframe *content* is a `judgment` criterion under `FUN-G15` and only a human closes it (D-21). `FUN-G16` and `TEC-G19` are `structural`: a current, complete Comprehension Record exists (FR-093). They can be overridden per criterion like any other.

The criteria lists are the process standard's, reproduced in the templates and in `gates.py` as data, not logic (one table row per criterion with an id, text and a check kind: `structural`, `traceability` or `judgment`).

**Derived stage state** (never stored):

`not-started` (document absent) → `draft` (exists, no approval) → `in-review` (gate evaluated, all criteria met or overridden, awaiting confirmation) → `approved` (valid approval, fingerprint matches) → `needs-re-review` (approval exists but own fingerprint or an upstream fingerprint no longer matches, FR-043/044).
Orthogonal flag: `abbreviated` (FR-040).

Transitions: `approve` moves `in-review → approved` and is refused unless the gate is met or every unmet criterion carries an override (FR-010). Any content change to an `approved` document, or to an upstream one, moves it to `needs-re-review`. A new approval on the current fingerprint moves it back to `approved`. `s07` is never `approved`; it is `complete-evidence` when every item has a status.

## Stage Document (file structure)

```text
# <Stage title>                     ← human content, fingerprinted
…sections per the stage's template… ← human content, fingerprinted
## Challenges                       ← record blocks, fingerprinted
## Overrides                        ← record blocks, fingerprinted
## Abbreviation                     ← optional record block, fingerprinted
## Comprehension Check (functional, technical only)
<!-- eil:begin comprehension -->
```json …```                       ← the Comprehension Record: NOT fingerprinted
<!-- eil:end comprehension -->
## Quality Assessment (FR-009)
<!-- eil:begin assessment -->
```json …```                       ← gate result written by `check`: NOT fingerprinted
<!-- eil:end assessment -->
## Approval
<!-- eil:begin approval -->
```json …```                       ← the Approval record: NOT fingerprinted
<!-- eil:end approval -->
```

Full grammar in [contracts/document-format.md](contracts/document-format.md).

## Approval

One per approvable stage; replaced (not appended) on re-approval, with the prior one preserved in git history. Stored in the stage document's approval region.

| Field | Type | Rule |
|-------|------|------|
| `stage` | enum | one of the approvable stages |
| `by` | string | MUST match a configured approver for the stage (FR-013) |
| `at` | RFC 3339 UTC | set by the helper, not supplied |
| `fingerprint` | `sha256:<hex>` | of the document at approval (FR-011) |
| `attestation` | string | the human's verbatim confirmation; non-empty (FR-012) |
| `played_back_to` | string, optional | free text only, never verified (FR-066) |
| `upstream` | map stage → fingerprint | fingerprints of every earlier definition document at approval time |
| `items` | map ID → `sha256:<hex>` | hash of each item's normalised text in this document, for impact analysis (FR-043) |
| `overrides_used` | list of override ids | overrides in force when approved |
| `comprehension` | counts, functional and technical only | `understood`, `coached`, `revealed`, `skipped`, `not_applicable` copied from the Comprehension Record at approval (FR-093) |

Validity: valid ⇔ `fingerprint` equals the current fingerprint (formatting-only differences ignored, FR-044). An approval whose `upstream` fingerprints no longer match is valid for its own content but the stage is `needs-re-review`.

## Quality Gate Result

Written into the document's Quality Assessment section, and returned by `eil check` as JSON.

| Field | Type | Rule |
|-------|------|------|
| `stage` | enum | |
| `criteria[]` | list | one per gate criterion |
| `criteria[].id` | string | e.g. `REQ-G07` |
| `criteria[].status` | enum | `met` / `not-met` / `overridden` (FR-009) |
| `criteria[].reason` | string | required when not `met` |
| `criteria[].kind` | enum | `structural` (code decided) / `traceability` (code decided) / `judgment` (AI assessment, human confirms) |
| `assessment` | object | `ambiguity`, `missing`, `contradictions`, `unsupported_assumptions`, `untestable`: each a list of findings (FR-009) |
| `evaluated_at` | timestamp | informational only |

Location and identity: the Quality Assessment lives in its own `eil:begin assessment` region, which is **excluded from the fingerprint** like the approval and the comprehension record. It is derived output, so re-running `check` (or `status`) never changes a document's identity or invalidates an approval. The approval, not the assessment, is what records the human's acceptance.

Rule: `judgment` criteria are the AI's assessment and are labelled as such; only the human's approval closes them (D-11). `structural` and `traceability` criteria are computed by code and cannot be marked `met` by the AI.

## Override

Stored in the stage document's Overrides section as a record block.

| Field | Type | Rule |
|-------|------|------|
| `id` | `OVR-###` | unique in the story |
| `stage` | enum | the stage whose gate is being passed |
| `criterion` | string | a criterion id of the stage, or `unreviewed-ai-content` (waives the `[ai-draft]` check, D-16), or (later stages) `plan-gate`, `tasks-gate`, `completion-evidence` |
| `by` | string | MUST be a configured confirmer for that stage (FR-045); no separate authority |
| `at` | timestamp | |
| `reason` | string | non-empty |

Visibility: every later stage's overview entry and the trace report list all overrides from earlier stages (FR-045, SC-006). An override is per criterion, never blanket (FR-010).

## Open Question

An item `OQ-###` in the Requirements document (may also appear in later stages).

| Field | Rule |
|-------|------|
| `status` | `open` / `resolved` / `accepted` |
| `material` | boolean |
| `accepted_by` | required when `accepted` (FR-023) |
| `resolution` | text or link to the decision, when `resolved` |

Rule: approval refused while any material question is `open` (FR-023). `accepted` questions are carried forward into every later stage's overview as accepted risks (FR-024). The AI must not change a question to an assumption; assumptions are a separate list (FR-022).

## Challenge

Stored in the Challenges section.

| Field | Rule |
|-------|------|
| `id` | `CH-###` |
| `stage` | |
| `raised_by` | `ai` or a person |
| `target` | item id or section |
| `text` | specific gap, contradiction or unstated assumption (FR-034) |
| `status` | `open` / `closed` |
| `response` | `accepted` (content changed) / `rejected` (reason required) / `deferred` (explicit risk acceptance required) (FR-036) |
| `responder`, `at`, `reason` | required when closed (FR-035) |

Rules: approval refused while any challenge on the stage is `open` (FR-037). A `rejected` or `deferred` challenge is a standing constraint; `challenge` must not re-raise one with the same `target` and equivalent text (FR-038). If two responders answer the same challenge differently, `check` reports a **conflict** that only a configured confirmer can resolve (edge case "conflicting answers").

## Technical Decision

Defined in `s03-technical-spec.md` as an item `DEC-###`.

| Field | Rule |
|-------|------|
| `id` | unique, never reused (FR-032) |
| `decision`, `reason`, `rejected_alternative`, `trade_off` | all required (FR-032, US4) |
| `owner` | the developer, including for AI-proposed decisions the developer adopted (FR-033) |
| `traces` | ≥ 1 of `FR-###`, `NFR-###` (FR-026) |

## Traceability Item and Link

An **item** is any line defining an ID (D-10). A **link** is a `traces:` reference from one item to an upstream item.

Chain: `REQ/UC ← FR ← DEC ← AIS ← T (task) ← code ← EVD`. Each arrow points from the derived item to its source. `ART` is a side branch: it traces to the items it illustrates, `AIS` items may trace to it, and `EVD` may trace to it.

| Item kind | Defined in | Must trace to | Rule |
|-----------|-----------|---------------|------|
| `REQ`, `UC` | s01 | (none, root) | |
| `ART` (context) | s01 | ≥ 1 `REQ`/`UC` | FR-071 |
| `FR`, `NFR` | s02 | ≥ 1 `REQ` or `UC` | FR-025; untraceable ⇒ gate not met |
| `ART` (sequence, wireframe) | s02 | ≥ 1 `FR`/`UC` | FR-071, FR-073 |
| `DEC` | s03 | ≥ 1 `FR`/`NFR` | FR-026 |
| `ART` (container, component, sequence, ER) | s03 | ≥ 1 `FR`/`NFR`/`DEC` | FR-071, FR-074; a technical sequence diagram cites the `DEC` it illustrates |
| `AIS` | s04 | ≥ 1 `REQ`/`FR`/`DEC`/`ART` | FR-027; none ⇒ "unapproved decision" (FR-039) |
| task `T###` | s06 | ≥ 1 `AIS` (or `DEC`) | FR-031, FR-058 |
| code change | s07 evidence | task id | `(code: sha|PR#n)` |
| `EVD` | s07 | ≥ 1 of `REQ`/`FR`/`ART`/acceptance criterion, plus code where applicable | FR-059 |

Coverage checks (all computed, FR-028/029/030/068/083): every approved `REQ` has ≥ 1 `FR`; every `FR` has ≥ 1 `REQ`/`UC`; every `REQ` reaches an `EVD` or an exception; every code reference reaches a `REQ`; every wireframe, ER and technical sequence `ART` named in `s04` is reached by ≥ 1 task through an `AIS`; every approved `ART` reaches an `EVD` or an exception. Both directions come from the same links, computed on demand.

## Artefact

An item `ART-###` in the stage document that owns it (FR-071, D-17, D-18).

| Field | Type | Rule |
|-------|------|------|
| `id` | `ART-###` | unique, never reused |
| `kind` | enum | `c4-context`, `c4-container`, `c4-component`, `sequence`, `er`, `wireframe`, `image` |
| `stage` | enum | derived from the document it is defined in; the kind must be permitted there (below) |
| `title` | string | the item line's text |
| `traces` | list | ≥ 1 source item (FR-071) |
| `store` | string, ER only | label of the data store it describes; must be a `ContainerDb` or `SystemDb` in the container diagram (FR-079d) |
| `form` | `inline` \| `file` | inline = a `mermaid` fence follows the item line; file = an `eil:artifact` record follows |
| `diagram` | text, inline only | the Mermaid source; `kind` derives from its first keyword |
| `file`, `sha256`, `format`, `source` | file only | see below |
| `checked` | boolean | `true` for inline diagrams; `false` for `image` (no structural checks, FR-076) |

**Kinds permitted by stage**

| Kind | s01 | s02 | s03 |
|---|---|---|---|
| `c4-context` | ✔ | ✘ | ✘ (referenced, not redrawn) |
| `c4-container`, `c4-component` | ✘ | ✘ | ✔ |
| `sequence` | ✘ | ✔ functional (participants: actors + `System`) | ✔ technical (participants: C4 elements) |
| `er` | ✘ | ✘ | ✔ |
| `wireframe` | ✘ (reference link only) | ✔ | ✘ |
| `image` | ✔ if it depicts a kind permitted in that stage | same | same |

A kind in a stage that does not permit it is `artifact-wrong-level` (FR-081). `s04` to `s08` define no `ART`.

**Export record** (`eil:artifact` block, fingerprinted with the document, file form only)

| Field | Rule |
|-------|------|
| `file` | path under `assets/`, no `..`, extension in `png`, `svg`, `pdf`, `jpg`, `jpeg` |
| `sha256` | `sha256:` of the file's **raw bytes** (FR-077) |
| `kind` | `wireframe` or `image`; `image` also carries `depicts` (a diagram kind) |
| `source.tool` | free text (`figma`, `draw.io`, …) |
| `source.url` | required; for `figma` it MUST contain `node-id=` (FR-077) |
| `source.exported_at`, `source.exported_by` | required |

**Artefact state** (derived, never stored): `ok` → `unparsed` (inline diagram yields nothing recognisable, FR-080) → `inconsistent` (a FR-079 finding is open) → `missing-file` → `hash-mismatch` (FR-078) → `unregistered` (a fence or record with no `ART` line, or an `ART` line with neither) → `changed-since-approval` (its item hash differs from the owning stage's approval, FR-082). Verification adds `verified`/`failed`/`unverified`/`excepted` (Verification Record).

Rule: re-registering an export rewrites the record, which changes the owning document's fingerprint, so its stage becomes `needs-re-review` and downstream references are listed as affected (FR-043, FR-078).

## Pending Clarification

An item in `s04-ai-spec.md` marked `[pending-clarification]` (FR-067).

| Field | Rule |
|-------|------|
| `id` | `AIS-###` |
| `answer` | the human's answer text |
| `target_stage` | the earliest stage it affects, set by `resolve` |
| `state` | `pending` → `carried` (recorded in `target_stage` with an ID) → cleared |

Rule: while any item is `pending`, the AI Specification fails its source-traceability check, Plan and Tasks are refused (unless overridden) and the overview lists it as an outstanding issue. Clearing requires the answer to have an ID in an *approved* stage; if that stage was approved before the change, it is marked `needs-re-review` (FR-043, FR-067).

## Verification Record

An item in `s07-verification.md`.

| Field | Rule |
|-------|------|
| `target` | a `REQ`, `FR`, `ART` or acceptance-criterion id (FR-059) |
| `status` | `verified` / `failed` / `unverified` / `excepted` |
| `evidence[]` | each `{kind: automated|manual, ref, summary}`; automated covers tests, builds, static analysis, scans, lint, type checks (FR-060) |
| `exception` | `{accepted_by, reason}` required when `excepted` or a design deviation (FR-061) |

Rule: the document describes evidence only and never declares completion (FR-062). An open task at Verification start is listed, not hidden (edge case).

## Completion Record

`s08-completion.md` content: status, implementation summary, requirements satisfied, outstanding issues, accepted deviations, relevant decisions, verification summary, deployment status, documentation and support implications, and the Approval (FR-063). It also states, for each approved `ART`, that it is current or lists the deviation under accepted deviations (FR-084). Approval is refused if `s07` is missing, if any requirement or approved artefact is `unverified` without an exception unless overridden (FR-064/065), and requires the human's explicit statement that the evidence was reviewed.

## Comprehension Record

Stored in the `comprehension` region of `s02` or `s03` (D-22, FR-092). One per stage, replaced whole when stale.

| Field | Rule |
|-------|------|
| `stage` | `functional` or `technical` only |
| `fingerprint` | the document version checked; **current** ⇔ equal to the document's current fingerprint |
| `taken_by` | MUST be a configured confirmer for the stage (FR-094) |
| `started_at`, `updated_at` | set by the helper |
| `levels[5]` | `recognise`, `explain`, `apply`, `trace`, `evaluate`, each `{outcome, attempts, items, reason?}` |
| `levels[].outcome` | `understood` (answered), `coached` (understood after hints), `revealed` (answer requested), `skipped`, `not-applicable` (reason required) |

Derived state (never stored): `missing` → `incomplete` (current, fewer than five levels) → `complete` (current, five levels) → `stale` (fingerprint differs). Only `complete` meets the criterion. Passing is not required (FR-093).

Never holds: a question, an answer, a hint, a score, a timer or a rank (FR-092, FR-094). Selection of the target items is deterministic (document-format.md §Question targets).

## Approver Configuration

Extension config (`.specify/extensions/eil/eil-config.yml`, machine-local override in `local-config.yml`).

```yaml
default_developer: null        # else resolved from git identity
approvers:                     # who may confirm (and override) each stage
  requirements: []             # empty = the story's developer
  functional: []
  technical: []
  completion: []
abbreviation_authorisers: []   # empty = the story's developer
```

Rules: an empty list means "the story's developer". A confirmation or override by anyone not listed is refused (FR-013). One listed person's confirmation suffices (FR-066). The same list governs override authority (FR-045).

## Overview (`s00-README.md`)

Derived, never hand-edited (D-14). Fields: title, owner, current stage, overall status, document index (link + derived status), artefact index (id, kind, stage, state, link; FR-086), approvals (who, when, fingerprint short form), outstanding open questions / challenges / pending clarifications / overrides / issues, accepted risks, abbreviated stages, and a **Mirrors** list naming each alias that is a mirror (FR-053, FR-054). Content restriction: only labels and values pulled from records, never document prose (FR-055).

## Alias

| Field | Rule |
|-------|------|
| `name` | `spec.md`, `plan.md` or `tasks.md` only (FR-049/050) |
| `target` | `s04-ai-spec.md`, `s05-plan.md`, `s06-tasks.md` |
| `form` | `symlink` or `mirror` |
| `fault` | none / `missing` / `wrong-target` / `diverged` (FR-051) |

Refresh procedure (FR-053), executed by `eil sync`: (1) classify each alias; (2) **report** any fault or difference; (3) recreate the symlink or rewrite the mirror from the target, read-only; (4) never modify the target.

## Relationships

```text
Story Package 1─┬─ 1 Overview (derived from all below)
                ├─ 1..8 Stage Document ─┬─ 0..1 Approval
                │                       ├─ 0..1 Comprehension Record (s02, s03)
                │                       ├─ 0..n Challenge
                │                       ├─ 0..n Override
                │                       ├─ 0..1 Abbreviation
                │                       ├─ n Traceability Item ── traces ─→ Traceability Item (upstream)
                │                       └─ n Artefact (an item) ── traces ─→ Traceability Item
                │                              └─ 0..1 exported file in assets/ (via Export record)
                └─ 3 Alias ──→ Stage Document (s04, s05, s06)
Approver Configuration (extension config) ── governs ── Approval, Override, Abbreviation
```
