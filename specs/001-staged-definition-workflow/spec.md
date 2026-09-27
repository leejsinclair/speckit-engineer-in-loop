# Feature Specification: Staged Definition Workflow (Engineer-in-the-Loop Preset)

**Feature Branch**: `001-staged-definition-workflow`

**Created**: 2026-09-25

**Last Revised**: 2026-09-25 (reframed as a Spec Kit preset with companion extension; gate strength decided; story package layout with compatibility aliases decided)

**Status**: Draft

**Input**: User description: "Requirements, Functional Specification and Technical Specification — a standard and workflow for progressively turning a software story into an implementation-ready engineering solution, through Requirements, Functional Specification, Technical Specification and AI Specification stages, each resolving a different class of uncertainty and each closed by a human approval gate. AI challenges, humans decide, AI executes." Follow-up: "This will be a speckit preset like https://github.com/leejsinclair/speckit-presets-gamified but rigorous and process driven."

## Background

Software stories often move straight from an idea to code. When an AI coding agent is involved this is risky: decisions about intent, behaviour and design get made implicitly by the agent, and nobody can later say why something was built, what it was meant to do, or how it was verified.

Spec Kit's standard lifecycle (specify → plan → tasks → implement) does not separate *why*, *what* and *how*, and does not require a human to confirm each before the next begins. Its core specification and plan documents blend intent, behaviour and design.

The author's existing Spec Kit preset and companion extension, **speckit-presets-gamified** (Questmaster), takes the opposite stance to what is needed here: it is narrative, scored, and entirely **advisory** — nothing it produces blocks anything. This work is its deliberate counterpart: **rigorous and process-driven**, with hard human gates, a fixed document standard per stage, and end-to-end traceability, and no gamification.

The team's process standard defines four definition stages, each resolving one kind of uncertainty and each (except the last) closed by a human confirming their judgement:

| Stage | Primary uncertainty resolved | Human confirms |
|-------|------------------------------|----------------|
| Requirements | Why? | "This is the problem we actually intend to solve." |
| Functional Specification | What? | "This describes the behaviour we actually require." |
| Technical Specification | How? | "This is the engineering solution we intend to build." |
| AI Specification | How should the AI execute the approved design? | (Translation only — introduces no new decisions) |

The AI Specification is followed by the existing Plan and Tasks stages, then implementation, then two closing stages that separate evidence from accountability:

| Stage | Question answered | Human confirms |
|-------|-------------------|----------------|
| Verification | Did we actually build what we said we would build? | (Evidence only — describes, does not approve) |
| Completion | Is this story actually complete? | "We have reviewed the evidence and consider the story complete." |

The result is a **story package**: one directory holding a fixed, numbered set of documents that a human can read in order, from intent through to accountability.

## Constraints on the Solution

These are decided, not open:

- **One numbered story package per feature.** Each feature directory holds nine real documents in a fixed order: `s00-README.md` (navigation and status dashboard), `s01-requirements.md`, `s02-functional-spec.md`, `s03-technical-spec.md`, `s04-ai-spec.md`, `s05-plan.md`, `s06-tasks.md`, `s07-verification.md` and `s08-completion.md`. The feature directory name follows the project's existing Spec Kit naming convention (the customer-duplicate-detection name used in the design discussion is illustrative).
- **Compatibility aliases, not extra documents.** Spec Kit expects to find `spec.md`, `plan.md` and `tasks.md`. Exactly three aliases are provided: `spec.md` → `s04-ai-spec.md`, `plan.md` → `s05-plan.md`, `tasks.md` → `s06-tasks.md`. Each alias resolves to the one real document and is never an independently editable copy; where links are unavailable, the alias is a generated read-only mirror of that document (FR-053). No alias is created for `requirements.md` or any other document unless a specific tool is shown to require it.
- **The AI Specification is the Spec Kit "spec".** Spec Kit commands that read `spec.md` therefore read the AI Specification, which is the approved, implementation-oriented distillation of Requirements, Functional Specification and Technical Specification.
- **Design artefacts follow the C4 model, sequence diagrams and ER diagrams, with wireframes from Figma.** Architecture is shown with C4 Level 1 (system context), Level 2 (container) and Level 3 (component) diagrams, and never Level 4. Flows are shown with UML sequence diagrams and database structure with ER diagrams. Diagrams are authored as text in Mermaid inside the stage document, so that a change to a diagram is a change to the document. Wireframes are designed in Figma and stored in the story package as **static exports** (FR-077). Each artefact belongs to the stage that owns its level of abstraction (FR-072 to FR-074).

These are decided, not open:

- **Delivered as a Spec Kit preset plus a companion extension.** The preset overrides and composes existing templates and core commands; the companion extension adds the explicit stage commands and approval hooks that a preset cannot add by itself. Both install into an ordinary Spec Kit project without modifying Spec Kit itself.
- **State lives in the project's own files.** There is no database, service, web interface or external integration. Stage documents, approvals, challenges, decisions and traceability links are all recorded in files in the feature directory, under version control alongside the code.
- **Gates are hard stops with a recorded override.** The workflow refuses to advance past an unmet gate. A human may proceed anyway only by recording a named, reasoned override that stays visible in every later stage.
- **Not advisory, not gamified.** Unlike the preset it is modelled on, the outputs are mandatory-form, gate-relevant documents, and there is no scoring, narrative or reward mechanism.

## Clarifications

### Session 2026-09-25

- Q: On a platform that can't create or keep symbolic links, what should happen to `spec.md`, `plan.md` and `tasks.md`? → A: Each becomes a generated, read-only mirror of its real document, refreshed when that document changes; a mirror that differs from its target is reported as an alias fault.
- Q: When a stage names more than one person who may approve it, does one approving count, or must every named approver confirm? → A: The workflow records a single confirmation from the developer for each stage. Playback to business and technical stakeholders happens out of band, and the developer's confirmation attests that it took place and the stage was accepted. Two approvers on the pull request is repository policy, enforced by the version control platform, and is outside the workflow.
- Q: Who is allowed to record an override that lets a story proceed past an unmet quality gate? → A: The same person who may confirm that stage, with no separate override authority. The safeguard is visibility: every override is named, reasoned, carried into every later stage and the traceability report, and visible in the pull request diff.
- Q: When someone runs Spec Kit's clarify command on a story, where should the answers it collects be written? → A: Directly into the AI Specification (`spec.md`), with the affected earlier stage updated afterwards. Until that update is made, the answer is marked as pending and the AI Specification does not pass its source-traceability check (FR-067).
- Q: When someone runs Spec Kit's analyze command on a story, should it check only the three files it normally reads, or the whole chain from requirements onward? → A: The whole chain. Analyze also checks that every requirement has a functional requirement, every technical decision traces to functional requirements, and every AI Specification item has an approved source, reporting these alongside its usual results (FR-068).
- Q: How should the workflow identify the exact version of a stage document that was approved, so it can tell later whether it has changed? → A: A content fingerprint of the document, recorded in the approval record (FR-011, FR-044). Any change to the content makes it differ from the recorded one; timestamps are not used.
- Q: Should trivial formatting changes, such as extra spaces, blank lines or line-ending differences, count as a change to an approved document? → A: No. Formatting-only changes (line endings, trailing spaces, repeated blank lines) are ignored; any other change counts (FR-044).
- Q: How should the workflow tell a new, governed feature from one that predates installation? → A: A feature is governed if and only if its directory contains the overview document (`s00-README.md`) created when a story is started through the workflow; features without one are left alone (FR-006, FR-069).
- Q: When the real document changes, when should the workflow refresh its mirrored copy? → A: Automatically at the start of every workflow command and every Spec Kit command the preset intercepts, so a stale mirror is refreshed before anything reads it. The mirror stays content-identical to its target, and the overview lists which files are mirrors (FR-053).
- Q: Are the numbering styles of features (`001-…`) and documents (`01-…`) distinct enough, or do documents need a distinguishing prefix? → A: Documents carry a distinguishing `s` prefix (`s00-README.md` … `s08-completion.md`), so a document name can never be mistaken for a feature number (FR-047, FR-070).
- Q: Which diagrams and design artefacts must each stage document carry? → A: Requirements: C4 system context. Functional Specification: a system-level sequence diagram per use case, and Figma wireframes where the story has a user interface. Technical Specification: C4 container, C4 component, technical sequence diagrams and, where persistent data changes, an ER diagram. The AI Specification only references approved artefacts; Verification gives each a status; Completion confirms each is current (FR-071 to FR-086).
- Q: In what notation are diagrams written, and how far does the workflow check them? → A: Mermaid text inside the stage document, checked structurally, including consistency across diagrams (element names between C4 levels, sequence participants, ER entities against data stores). Other tools' diagrams may be attached as images but get no structural checks (FR-076, FR-079).
- Q: Should the Functional and Technical Specification stages include a comprehension check like the Know Your Spec preset's? → A: Yes. Before approval, the developer answers five questions about the document's own content at increasing difficulty (recognise, explain, apply, trace, evaluate), with coaching on wrong answers. Unlike that preset it is recorded, and approval requires that it was run on the current version of the document, but not that it was passed: skipped and revealed levels are recorded and shown, not blocked. It never stores answers and never scores (FR-087 to FR-094).
- Q: Should approved diagrams and wireframes be verified like requirements? → A: Yes. Each approved artefact has a status of verified, failed, unverified or excepted, and completion is refused while one is unverified without a recorded exception (FR-059, FR-065).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Install the preset and define approved requirements (Priority: P1)

A developer adds the preset and its companion extension to a Spec Kit project, starts a new story, and produces a requirements document that states why the work is needed and what success looks like, without prescribing a solution. AI helps by questioning assumptions and pointing out gaps. The appropriate human owner reviews the result out of band, and the developer confirms it is the problem the organisation actually intends to solve.

**Why this priority**: Every later stage depends on the problem being right. This is the smallest slice that delivers value — install, plus one fully gated stage — and it is the first gate.

**Independent Test**: In a fresh Spec Kit project, install the preset and extension, then take one real story through the Requirements stage alone. It is complete when the requirements are recorded, pass the requirements quality gate, and carry a recorded human approval — with no functional or technical content required.

**Acceptance Scenarios**:

1. **Given** a Spec Kit project without the preset, **When** the developer installs the preset and companion extension, **Then** the stage commands become available and no existing project file is edited.
2. **Given** an installed preset, **When** the developer starts a new story through the standard Spec Kit entry point or the stage command, **Then** the workflow begins at the Requirements stage rather than jumping to specification or planning.
3. **Given** a new story, **When** the Requirements stage begins, **Then** a requirements document is created containing all required content areas (background, problem statement, desired outcome, users and stakeholders, use cases, scope, constraints, dependencies, risks, assumptions, open questions, success criteria).
4. **Given** a draft requirements document, **When** it is checked against the requirements quality gate, **Then** each gate criterion is reported as met or not met, with the specific gap identified for each unmet criterion.
5. **Given** a requirements document with unresolved material open questions, **When** approval is attempted, **Then** approval is refused until each material open question is resolved or explicitly accepted by a named person.
6. **Given** requirements that pass the gate, **When** the developer records their confirmation, **Then** the approval (who, when, which version of the content) is recorded in the feature directory and the Functional Specification stage becomes available.
7. **Given** requirements that are not approved, **When** anyone attempts to begin the Functional Specification, **Then** the attempt is refused with an explanation of which approval is missing.

---

### User Story 2 - Find your way around a story package at a glance (Priority: P2)

Anyone opening a story's directory — a new team member, an approver, a reviewer — reads a short overview document that tells them the story's title, owner, current stage and status, which approvals are in place, what questions or issues are outstanding, and where each numbered document is. It is a table of contents and dashboard, not another specification.

**Why this priority**: The numbered package is only useful if a human can orient in it immediately; the overview is created with the story and is needed from the first stage.

**Independent Test**: Start a story and advance it through one gate; confirm the overview reflects the new status and approval without anyone editing it by hand, and contains no specification content.

**Acceptance Scenarios**:

1. **Given** a new story, **When** it is started, **Then** the overview document is created with the story title, owner, current stage, an index of all nine documents with their status, and an approvals section.
2. **Given** a stage is approved, an override recorded, a challenge opened, or a question raised, **When** the change is recorded, **Then** the overview reflects it without manual editing.
3. **Given** a story package, **When** a reader opens the overview, **Then** they can reach every stage document from it and see which approvals and issues are outstanding.
4. **Given** the overview, **When** it is checked, **Then** it contains no requirements, behaviour or design content of its own — only navigation, status and links.

---

### User Story 3 - Turn approved requirements into traceable behaviour (Priority: P3)

Using the approved requirements, the team produces a functional specification describing what the system must do — behaviour, business rules, inputs, outputs, states, validation, error handling, security, audit, non-functional needs and acceptance criteria. Every significant functional requirement points back to the requirement or use case it satisfies. Business and technical stakeholders review it out of band, and the developer confirms it describes the behaviour actually required.

**Why this priority**: This separates "what" from "how" and creates the first link in the traceability chain. It depends on Story 1 but delivers standalone value as a testable behavioural contract.

**Independent Test**: Given an already-approved requirements document, produce a functional specification and verify that every functional requirement traces to a requirement, the functional quality gate is evaluated, and approval can be recorded.

**Acceptance Scenarios**:

1. **Given** approved requirements, **When** the Functional Specification stage begins, **Then** the requirements are presented as its source and the functional specification is created with all required content areas.
2. **Given** a functional requirement with no link to any requirement or use case, **When** the quality gate is evaluated, **Then** it is flagged as untraceable and the gate is not met.
3. **Given** an approved requirement with no functional requirement tracing to it, **When** the quality gate is evaluated, **Then** the uncovered requirement is reported.
4. **Given** a functional requirement that names a specific technology or internal structure without necessity, **When** the quality gate is evaluated, **Then** it is flagged as prescribing implementation.
5. **Given** a functional specification that passes the gate, **When** the developer records their confirmation, **Then** the approval is recorded and the Technical Specification stage becomes available.

---

### User Story 4 - Record a developer-owned technical design with explicit decisions (Priority: P4)

The developer produces a technical specification describing how the behaviour will be built and why that approach is appropriate — architecture, components, data, interfaces, security, resilience, observability, performance, testing, deployment and migration, impact on existing systems, alternatives considered, and risks. Significant choices are recorded as numbered technical decisions, each with its reason, rejected alternative and trade-off. AI may propose alternatives and challenge choices, but the developer decides and approves.

**Why this priority**: This is where engineering judgement is applied and where decisions must become explicit rather than implicit. It depends on approved functional behaviour.

**Independent Test**: Given an approved functional specification, produce a technical specification and verify that significant decisions are recorded in the required form, each is attributed to the developer, the technical quality gate is evaluated, and approval can be recorded.

**Acceptance Scenarios**:

1. **Given** an approved functional specification, **When** the Technical Specification stage begins, **Then** the specification is created with all required content areas and each technical decision has a unique identifier.
2. **Given** a technical decision, **When** it is recorded, **Then** it captures the decision, the reason, the rejected alternative and the trade-off.
3. **Given** AI proposes an alternative design, **When** the developer declines it, **Then** the developer's chosen approach — not the AI's proposal — is what is recorded as the decision.
4. **Given** a technical specification with unresolved technical questions that could materially change implementation, **When** the quality gate is evaluated, **Then** the gate is not met and the questions are listed.
5. **Given** a technical specification that passes the gate, **When** the responsible developer or technical lead records their confirmation, **Then** the approval is recorded and the AI Specification stage becomes available.

---

### User Story 5 - Give the AI agent an approved, bounded execution context (Priority: P5)

After the technical specification is approved, the workflow assembles an AI Specification: an implementation-oriented context drawn only from approved requirements, functional behaviour and technical decisions, together with relevant existing code, interfaces, data structures, testing and security requirements, edge cases, explicit exclusions and traceability references. The AI coding agent works from this and does not introduce new functional or architectural decisions. If it finds an ambiguity, it reports it instead of resolving it silently.

**Why this priority**: This is the payoff — a coding agent that executes rather than decides. It depends on all earlier stages being approved.

**Independent Test**: Given a fully approved chain, generate the AI Specification and verify that every item in it traces to an approved source, nothing new has been introduced, and a deliberately planted ambiguity is surfaced as a question rather than resolved.

**Acceptance Scenarios**:

1. **Given** an approved technical specification, **When** the AI Specification is created, **Then** it contains all required content areas and every item carries a reference to its source requirement, functional requirement or technical decision.
2. **Given** content that does not trace to any approved source, **When** the AI Specification is checked, **Then** it is flagged as an unapproved decision and excluded or escalated.
3. **Given** the agent encounters an ambiguity during planning or implementation, **When** it cannot be resolved from approved content, **Then** the agent raises it for a human to decide and does not proceed on an assumed answer.
4. **Given** a human answers a raised ambiguity, **When** the answer is recorded, **Then** it is recorded in the AI Specification marked as pending, then carried into the earliest affected stage as a recorded decision, and that stage is marked for re-review if approved content changed; until then the AI Specification does not pass its source-traceability check.
5. **Given** an AI Specification that has not passed its own source-traceability check, **When** the Plan stage is attempted, **Then** it is refused.

---

### User Story 6 - Trace any delivered change back to its reason and forward to its evidence (Priority: P6)

A reviewer, auditor or new team member picks any piece of delivered work and follows the chain in either direction: requirement → functional requirement → technical decision → AI specification item → implementation task → code change → verification evidence. They can answer why it was built, what it was required to do, why it was designed that way, what implements it, and how it was verified.

**Why this priority**: Traceability is the lasting benefit of the process, but it requires the earlier stages to exist. It can be delivered incrementally as each stage adds its links.

**Independent Test**: Choose one requirement in a completed story and produce its full chain to verification evidence; then choose one code change and produce its chain back to a requirement.

**Acceptance Scenarios**:

1. **Given** a completed story, **When** a reviewer selects a requirement, **Then** they can see every functional requirement, technical decision, task, code change and piece of verification evidence linked to it.
2. **Given** a completed story, **When** a reviewer selects a code change, **Then** they can see the task, decision, functional requirement and requirement that justify it.
3. **Given** a requirement with no verification evidence, **When** the traceability view is produced, **Then** the gap is reported.
4. **Given** a story marked complete, **When** completion is attempted while any requirement lacks verification evidence, **Then** completion is refused unless a named override is recorded.

---

### User Story 7 - Verify with evidence, then close with human accountability (Priority: P7)

After implementation, the team records evidence that each requirement and functional requirement was met — automated results, manual checks and any accepted deviations — in a verification document. A human then reviews that evidence and confirms the story is complete in a separate completion document. Verification says "here is the evidence"; completion says "we have reviewed it and consider the story complete".

**Why this priority**: This closes the chain and makes the final human accountability explicit. It depends on the earlier stages and on implementation having happened.

**Independent Test**: Given a story with an approved chain and finished implementation, produce the verification and completion documents and confirm that every requirement has evidence or a recorded exception, and that completion cannot be recorded without a human's explicit confirmation.

**Acceptance Scenarios**:

1. **Given** a finished implementation, **When** the Verification stage begins, **Then** the verification document lists every requirement, functional requirement and acceptance criterion with its status and linked evidence.
2. **Given** a requirement or acceptance criterion with no evidence, **When** verification is assessed, **Then** it is reported as unverified and must be either evidenced or recorded as an exception with a reason.
3. **Given** a complete verification document, **When** the Completion stage begins, **Then** the completion document is created with the required content and requires explicit human approval.
4. **Given** unverified requirements without a recorded exception, **When** completion approval is attempted, **Then** it is refused unless a named override is recorded.
5. **Given** an approved completion, **When** a reviewer opens the story's overview document, **Then** it shows the story as complete with the approver and date.

---

### User Story 8 - AI challenges, human decides (Priority: P8)

At any definition stage, AI reviews the current content and raises challenges — gaps, contradictions, unstated assumptions, missing failure behaviour. The human answers each challenge, and the answer is recorded as a decision at the relevant stage. AI then treats the recorded answer as authoritative.

**Why this priority**: This is the behavioural heart of the process, but it operates within the earlier stories rather than standing apart from them, so it is sequenced after them.

**Independent Test**: In any single stage, have AI raise a challenge about a deliberate gap; verify that the challenge is recorded, remains open until a human responds, and the response is reflected in the stage content.

**Acceptance Scenarios**:

1. **Given** a stage document with an unspecified behaviour, **When** AI reviews it, **Then** AI raises a specific, actionable challenge identifying what is missing.
2. **Given** an open challenge, **When** the human responds (accept, reject with reasoning, or defer with acceptance of risk), **Then** the response is recorded with its author and the challenge is closed.
3. **Given** an open challenge, **When** stage approval is attempted, **Then** approval is refused until the challenge is answered.
4. **Given** a human has rejected a challenge with a stated reason, **When** AI later works from the specification, **Then** AI treats the human's answer as an established constraint and does not re-raise the same challenge.

---

### User Story 9 - Adopt, tailor and remove the preset safely (Priority: P9)

A team lead installs the preset for a team, names who may approve each stage, decides how abbreviated stages are authorised for small changes, and can later remove the preset without damaging existing specifications or breaking standard Spec Kit behaviour.

**Why this priority**: Adoption safety matters for real teams but does not affect whether the process itself works.

**Independent Test**: Install into a project that already has feature specs; confirm existing work is untouched; configure approvers; remove the preset and extension and confirm standard Spec Kit commands behave as before.

**Acceptance Scenarios**:

1. **Given** a project with existing feature specifications, **When** the preset is installed, **Then** existing feature directories and their contents are unchanged and existing features are not retroactively gated.
2. **Given** an installed preset, **When** the team lead configures who may record the confirmation for each stage (by default the story's developer), **Then** a confirmation is accepted only from a person so configured for that stage.
3. **Given** an installed preset, **When** it is removed, **Then** the stage commands and preset template overrides are gone, standard Spec Kit commands behave as before, and recorded stage documents remain as ordinary files.

---

### Edge Cases

- **Upstream change after approval**: A requirement, functional requirement or technical decision changes after a downstream stage was approved. Affected downstream approvals must be marked as needing re-review, and the affected items identified.
- **Confirming developer unavailable**: The developer configured to confirm a stage is unavailable. Approval must not be silently delegated to AI; it waits for a human with the authority, or is proceeded past only through a recorded override.
- **Small or trivial story**: A very small change may not warrant every stage in full. Stages may be abbreviated but never skipped; the abbreviation, who authorised it and why must be recorded (FR-040).
- **Discovery during later stages**: Implementation reveals that a requirement was wrong. The finding may first be recorded as a pending answer in the AI Specification, but it must then be routed back to the earliest stage affected rather than left as a local patch, and the pending mark must not be cleared until it has been.
- **Traceability gap in either direction**: A requirement with no functional coverage, or a functional requirement with no requirement, must both be detected.
- **Open question carried forward deliberately**: A material open question the owner explicitly accepts must remain visible in later stages as an accepted risk, not disappear.
- **Override used**: Any override of an unmet gate must remain visible in every later stage and in the traceability report, so it cannot be forgotten or hidden.
- **Conflicting answers**: Two humans answer the same challenge differently. The conflict must be surfaced and require resolution by the accountable owner.
- **AI-added content not reviewed by a human**: Anything AI adds that the human has not reviewed must be visibly distinguished from human-approved content.
- **Approved content edited by hand afterwards**: A human or tool edits an approved document without going through the workflow. The change must be detectable, and the approval treated as no longer covering the edited content.
- **Wrong level of detail**: Requirements that name technologies, or functional specifications that dictate internal structure, must be flagged rather than silently accepted.
- **Existing features started before installation**: These are not retroactively blocked by gates they never had a chance to satisfy.
- **Writing through an alias**: Because `spec.md` is an alias for the AI Specification, a Spec Kit command that would normally write a new `spec.md` must not silently overwrite the AI Specification or replace the alias with a divergent real file. The standard specify entry point starts at Requirements instead (FR-003).
- **Alias replaced by a real file**: If an alias is deleted or replaced by an ordinary file (by a tool, a merge, or a platform that cannot store links), there would be two documents claiming to be the same one. This must be detected and reported, not silently tolerated.
- **Platform without link support**: Some environments cannot create or preserve links. The alias is then a generated read-only mirror of its real document, and the real document remains the only one that is edited (FR-053). Someone edits a mirror directly: the difference from its target must be detected and reported, and the target's content prevails.
- **Overview out of date**: The overview shows a status that disagrees with the stage documents. The stage documents are authoritative; the disagreement must be detectable.
- **Alias target not yet created**: `spec.md`, `plan.md` and `tasks.md` must not exist as dangling aliases before the document they point to exists.
- **Verification before implementation is finished**: The Verification stage is started while tasks remain incomplete. Outstanding tasks must be shown, not hidden.
- **Completion with accepted deviations**: A story may be completed with deviations from the design, but each must be recorded with who accepted it and why.
- **Document edited after the comprehension check**: The record no longer matches the document's fingerprint and is stale. The check must be taken again on the current version before approval (FR-093).
- **Developer skips or reveals every level**: The check is complete and approval is not blocked, but the record shows five skipped or revealed levels, and the count is carried into the approval record and the overview where a reviewer will see it (FR-093).
- **Question the document cannot answer**: The developer's answer, or a correct-sounding one, is unsupported because the document is silent or contradicts itself. That is a defect in the document, raised as a challenge, not a wrong answer (FR-091).
- **Story too small for a level**: A trivial story has no traced chain to follow or no trade-off to evaluate. That level is recorded as not applicable with a reason (FR-092).
- **Exported file edited by hand**: Someone touches up a wireframe export, or replaces it, without recording the new export. The difference from the recorded fingerprint must be reported as a fault (FR-078).
- **Design changed in Figma after export**: The source design moves on while the export stays as approved. The workflow cannot see this; the export in the package is the approved version, and the record links to the exact frame so a reviewer can compare. Recording a fresh export triggers re-review.
- **Diagram that does not parse**: A diagram has a syntax error or uses a construct the workflow cannot interpret. It must be reported and fail the gate, not be skipped (FR-080). A diagram made in another tool is attached as an image and is not structurally checked.
- **No user interface, no persistent data**: A story with no screens or no data changes has no wireframes or ER diagram. The stage records that each does not apply and why, rather than leaving it blank (FR-075).
- **Diagram contradicts the text**: A functional sequence diagram shows a system-internal component, or the container diagram omits a data store the ER diagram uses. Both are reported as inconsistencies (FR-079, FR-081).
- **Artefact changes after approval**: An approved diagram is edited. It is a change to the owning document, so the approval no longer covers it and downstream artefact references in the AI Specification fail their check (FR-044, FR-082).

## Requirements *(mandatory)*

### Functional Requirements

**Delivery and coexistence**

- **FR-001**: The preset and companion extension MUST be installable into an ordinary Spec Kit project with the standard preset and extension install commands, without editing any existing Spec Kit or project file.
- **FR-002**: The preset MUST provide the stage documents' templates, and the companion extension MUST provide an explicit command for each definition stage, so that each stage can be started and advanced deliberately.
- **FR-003**: The standard Spec Kit entry point for starting a specification MUST begin the workflow at the Requirements stage when the preset is installed.
- **FR-004**: The standard Spec Kit Plan and Tasks commands MUST refuse to run for a feature until that feature's AI Specification is complete and traceable, unless a named override is recorded.
- **FR-005**: Removing the preset and companion extension MUST leave all recorded stage documents, exported artefact files and the three compatibility aliases in place, and restore standard Spec Kit behaviour.
- **FR-006**: Features that predate installation MUST NOT be retroactively gated.
- **FR-069**: A feature MUST be treated as governed by the workflow if and only if its directory contains the overview document created when a story was started through the workflow. Gates, alias checks and refusals MUST NOT apply to a feature without it, and a feature's current stage MUST be derived from which stage documents exist and which carry a recorded approval.

**Stage structure and gating**

- **FR-007**: The workflow MUST support four sequential definition stages for a story: Requirements, Functional Specification, Technical Specification and AI Specification, in that order.
- **FR-008**: The workflow MUST refuse to start a stage until the preceding stage carries a recorded human approval.
- **FR-009**: For each stage, the workflow MUST evaluate the stage document against that stage's quality gate criteria as defined in the process standard, and report each criterion as met, not met, or overridden, with the specific reason for any criterion not met. The result MUST be recorded in a quality assessment section of that stage's document, covering at least ambiguity, missing information, contradictions, unsupported assumptions and untestable statements.
- **FR-010**: The workflow MUST refuse to record approval of a stage while any of its quality gate criteria is unmet, unless a person configured to confirm that stage records a named override for that specific criterion with a reason.
- **FR-011**: The workflow MUST record each approval with the confirming developer's name, the date and time, and a fingerprint of the document's content at the moment of approval, which serves as the identifier of the version that was approved.
- **FR-012**: The workflow MUST NOT allow an approval to be recorded by AI on behalf of a human; each approval MUST be an explicit human confirmation.
- **FR-013**: The workflow MUST support configuring, per stage, who may record the confirmation that approves it (by default the story's developer), and MUST refuse confirmations from anyone else.
- **FR-066**: One recorded confirmation from a person configured for that stage MUST be sufficient to record its approval. The workflow MUST NOT require confirmations from several people, and MUST NOT verify or record stakeholder playback beyond the developer's attestation; the approval record MAY carry a free-text note naming who the stage was played back to.

**Stage content**

- **FR-014**: The Requirements stage MUST capture: background, problem statement, desired outcome, users and stakeholders, use cases (each with actor, goal, trigger and expected outcome), scope (in and out), constraints, dependencies, risks, assumptions, open questions and success criteria, together with the system context diagram (FR-072).
- **FR-015**: The Functional Specification stage MUST capture: requirements traceability, actors, functional requirements, use cases and scenarios (preconditions, trigger, main flow, alternative flows, exception flows, expected outcome), business rules, inputs, outputs, state and workflow, validation, error and exception behaviour, security and access behaviour, audit and compliance behaviour, non-functional requirements and acceptance criteria, together with the sequence diagrams and wireframes of FR-073.
- **FR-016**: The Technical Specification stage MUST capture: technical requirements, architecture, component design, data design, API and integration design, security design, error handling and resilience, observability, performance, testing strategy, deployment and migration, existing system impact, alternatives considered, risks and trade-offs, and technical decisions, together with the diagrams of FR-074 (architecture and component design are shown as container and component diagrams; data design as an ER diagram).
- **FR-017**: The AI Specification stage MUST capture: relevant functional requirements, relevant business rules, approved technical decisions, architectural constraints, relevant existing code, interfaces, data structures, testing requirements, security requirements, known edge cases, explicit exclusions, implementation constraints, and traceability to source requirements and decisions, including the approved artefacts the agent must read (FR-082). It MAY also provide agent guidance: relevant files and directories, existing patterns to follow, patterns explicitly not to follow, commands and tests to run, and constraints on modification.
- **FR-018**: Content areas that do not apply to a particular story MUST be removable with a recorded reason rather than left blank; the workflow MUST identify any required area that is missing or empty without such a reason.

**Separation of concerns**

- **FR-019**: The workflow MUST flag Requirements content that prescribes an implementation.
- **FR-020**: The workflow MUST flag Functional Specification content that prescribes an implementation without necessity.
- **FR-021**: The Technical Specification MAY contain implementation detail and MUST be recorded as owned by the responsible developer.

**Open questions and assumptions**

- **FR-022**: The workflow MUST keep open questions distinct from assumptions and MUST NOT allow AI to convert an open question into an assumption without a human decision.
- **FR-023**: The workflow MUST require each material open question to be resolved or explicitly accepted, with the accepting person recorded, before the stage containing it can be approved.
- **FR-024**: Open questions that are explicitly accepted MUST remain visible in all later stages as accepted risks.

**Traceability**

- **FR-025**: Every significant functional requirement MUST reference at least one requirement or use case from the approved requirements.
- **FR-026**: Every significant technical decision MUST reference the functional requirements and non-functional requirements it satisfies.
- **FR-027**: Every item in the AI Specification MUST reference the approved requirement, functional requirement or technical decision it derives from.
- **FR-028**: The workflow MUST report any approved requirement that has no functional requirement, and any functional requirement that has no requirement.
- **FR-029**: The workflow MUST maintain the chain Requirement → Functional Requirement → Technical Decision → AI Specification → Implementation Task → Code Change → Verification Evidence, readable in both directions.
- **FR-030**: The workflow MUST report, for any requirement, where the chain is incomplete (for example, no verification evidence), and MUST refuse to mark a story complete while any requirement lacks verification evidence, unless a named override is recorded.
- **FR-031**: The Plan and Tasks stages MUST carry the traceability references forward so that each task can be traced to its source requirement and decision.
- **FR-068**: Where the preset is installed, Spec Kit's analyze command MUST, in addition to its standard checks over `spec.md`, `plan.md` and `tasks.md`, check the full traceability chain (FR-025 to FR-029) across all stage documents and report any gap alongside its usual findings. Its standard behaviour over those three files MUST be preserved.

**Technical decisions**

- **FR-032**: Each technical decision MUST have a unique identifier and MUST record the decision, the reason, the rejected alternative(s) and the accepted trade-off.
- **FR-033**: The workflow MUST record the developer as the owner of each technical decision, including decisions that AI proposed and the developer adopted.

**AI challenge and human decision**

- **FR-034**: AI MUST be able to raise challenges at any definition stage, each identifying the specific gap, contradiction or unstated assumption.
- **FR-035**: The workflow MUST record each challenge, its status (open or closed), the human response, the responder and the date.
- **FR-036**: A human response to a challenge MUST be one of: accepted (content changed), rejected (with reason), or deferred (with explicit acceptance of the risk).
- **FR-037**: The workflow MUST refuse to record approval of a stage while a challenge on it remains open.
- **FR-038**: AI MUST treat recorded human responses as established constraints and MUST NOT silently override them.

**AI execution boundaries**

- **FR-039**: The AI Specification MUST NOT introduce any functional or architectural decision that is not present in the approved stages, and the workflow MUST flag AI Specification content that lacks a source in an approved stage. The only exception is a pending clarification answer (FR-067), which MUST be visibly marked as pending and MUST be treated as lacking a source until carried upstream.
- **FR-040**: The workflow MUST allow a stage to be recorded as abbreviated, including who authorised the abbreviation and why, and MUST show this in the stage's status and in the traceability report. A stage MUST NOT be skipped.
- **FR-041**: When an AI agent encounters an ambiguity during planning or implementation, the workflow MUST require it to surface the ambiguity for a human decision and MUST NOT allow it to proceed on an unrecorded assumption.
- **FR-042**: A human decision resolving a surfaced ambiguity MUST end up recorded against the earliest stage it affects, either directly or by being carried there from a pending clarification answer (FR-067).
- **FR-067**: Answers collected by Spec Kit's clarify command MAY be written directly into the AI Specification, where each MUST be marked as pending. The workflow MUST then require the affected earlier stage to be updated with the answer, MUST mark that stage for re-review if it was approved, and MUST clear the pending mark only once the answer has a source in an approved stage. While any answer is pending, the AI Specification MUST fail its source-traceability check, Plan and Tasks MUST be refused unless a named override is recorded (FR-004), and the overview MUST list it as an outstanding issue.

**Change, override and history**

- **FR-043**: When approved content in an earlier stage changes, the workflow MUST mark every downstream approval that depends on the changed content as requiring re-review, and identify which items are affected.
- **FR-044**: The workflow MUST detect when an approved document has been changed after approval and treat the approval as no longer covering the current content. A document whose current content fingerprint differs from the one recorded at approval MUST be treated as changed, and a document whose content is unchanged MUST NOT be, however it was copied, checked out or merged. Formatting-only differences (line endings, trailing spaces, repeated blank lines) MUST NOT count as a change; any other difference MUST.
- **FR-045**: An override MUST be recordable by any person configured to confirm the stage it applies to, and no separate override authority is required. Every override MUST record who authorised it, what it overrode, and why, and MUST remain visible in every later stage and in the traceability report.
- **FR-046**: Stage content, approvals, challenges, decisions and overrides MUST be recorded in the project's files so that history can be reviewed through ordinary version control.

**Story package layout and aliases**

- **FR-047**: Each story MUST be recorded as a single feature directory containing, in this fixed numbered order, the documents `s00-README.md`, `s01-requirements.md`, `s02-functional-spec.md`, `s03-technical-spec.md`, `s04-ai-spec.md`, `s05-plan.md`, `s06-tasks.md`, `s07-verification.md` and `s08-completion.md`, plus an `assets` directory for exported artefact files (FR-077), created only when the first export is recorded.
- **FR-048**: The overview document MUST be created when the story starts. Each other document MUST be created when its stage begins, and MUST NOT exist as an empty placeholder before then.
- **FR-049**: The workflow MUST provide exactly three compatibility aliases — `spec.md` for `s04-ai-spec.md`, `plan.md` for `s05-plan.md`, and `tasks.md` for `s06-tasks.md` — each created when its target document is created, and each resolving to that single document and never an independently editable copy.
- **FR-050**: The workflow MUST NOT create an alias for any other document unless a specific tool is shown to require it.
- **FR-051**: The workflow MUST detect and report an alias that is missing, points to the wrong document, has been replaced by a separate file whose content may diverge from its target, or, where the alias is a mirror, differs from its target.
- **FR-052**: The workflow MUST ensure that Spec Kit commands which would write `spec.md`, `plan.md` or `tasks.md` do so only to the aliased document as intended for that stage, and never overwrite the AI Specification with content from another stage.
- **FR-053**: On platforms where links cannot be created or preserved, each compatibility alias MUST instead be a generated, read-only mirror of its real document. The workflow MUST refresh the mirror at the start of every workflow command and every intercepted Spec Kit command, so a stale mirror is refreshed before anything reads it, MUST keep it content-identical to its target, MUST identify it as a mirror in the overview, and MUST report any mirror whose content differs from its target as an alias fault before refreshing it. Edits are made only to the real document. If the preset is removed, mirrors remain as ordinary files.
- **FR-070**: The prefix on document names MUST be distinct from the feature directory's numeric prefix, so that no tool or person can mistake a document name for a feature number; the workflow MUST NOT treat a bare number as an identifier of either.

**Overview document**

- **FR-054**: The overview document MUST show: the story title, the owner, the current stage, the overall status, an index of all documents with links and each one's status, the approvals recorded so far and by whom, and any outstanding open questions, open challenges, overrides and issues.
- **FR-055**: The overview document MUST contain navigation and status only; it MUST NOT contain requirements, functional behaviour or design content.
- **FR-056**: The workflow MUST keep the overview consistent with the stage documents whenever an approval, override, challenge or question is recorded, and MUST treat the stage documents as authoritative if they disagree.

**Plan and tasks**

- **FR-057**: The Plan MUST be derived from the approved Technical Specification and MUST NOT introduce new architecture; content in the Plan not derivable from an approved decision MUST be flagged.
- **FR-058**: Tasks MUST be traceable to the design where useful and MUST NOT introduce new architecture; a task that does so MUST be flagged.

**Verification**

- **FR-059**: The Verification stage MUST record, for every requirement, functional requirement, acceptance criterion and approved artefact (diagram or wireframe), a status (verified, failed, unverified or excepted) and the evidence supporting it.
- **FR-060**: The Verification document MUST distinguish automated evidence (for example test results, build results, static analysis, security scans, linting and type checking), manual evidence, and exceptions.
- **FR-061**: Every exception, meaning anything not verified or any accepted deviation from the design, MUST record who accepted it and why.
- **FR-062**: The Verification document MUST describe evidence only; it MUST NOT itself declare the story complete.

**Completion**

- **FR-063**: The Completion stage MUST capture: completion status, summary of implementation, requirements satisfied, outstanding issues, accepted deviations, relevant technical decisions, verification summary, deployment status, documentation and support implications, and the human approval.
- **FR-064**: The workflow MUST refuse to record completion approval unless the Verification document exists, and MUST require an explicit human confirmation that the evidence was reviewed.
- **FR-065**: The workflow MUST refuse to record completion approval while any requirement or approved artefact is unverified without a recorded exception, unless a named override is recorded.

**Design artefacts (diagrams and wireframes)**

An *artefact* is a diagram or wireframe that a stage document contains or relies on. "Required" below means the stage's gate is not met without it, unless the person recording the stage states that it does not apply and why (FR-018).

- **FR-071**: Every artefact MUST be recorded with a unique identifier, its kind, a title, the stage that owns it, and the requirements, functional requirements or decisions it traces to. An artefact that traces to nothing MUST be flagged, and artefacts MUST be traceable in both directions like every other item in the chain (FR-029).
- **FR-072**: The Requirements stage MUST include a system context diagram (C4 Level 1) showing the system as a single element with every person named under users and stakeholders and every system named under dependencies, and marking what is existing and what is new or changed. Wireframes MUST NOT be authored in this stage; an existing design MAY be listed as a reference input only, and it is not binding until the Functional Specification adopts an export of it.
- **FR-073**: The Functional Specification stage MUST include (a) a system-level sequence diagram for each use case, or a recorded not-applicable reason for that use case, whose participants are only the declared actors and the system as one participant, and which shows the main, alternative and exception flows, and (b) a wireframe for each screen or screen state of a story that has a user interface, or a recorded not-applicable reason for it, each tracing to the functional requirement or use case it shows. It MUST NOT include a data-structure diagram.
- **FR-074**: The Technical Specification stage MUST include (a) a container diagram (C4 Level 2) of the system, (b) a component diagram (C4 Level 3) for each new or changed container, or a recorded not-applicable reason for it, (c) a sequence diagram for each use case that crosses more than one container, or a recorded not-applicable reason for it, each citing the decision it illustrates (for example asynchronous processing, retries and idempotency, authentication and integration), and (d) an ER diagram wherever persistent data is added or changed.
- **FR-075**: For each required artefact the workflow MUST report the gate criterion as not met when the artefact is missing and no not-applicable reason is recorded, and MUST list the missing artefacts by kind and the item that requires them.
- **FR-076**: Diagrams MUST be authored as text in the decided notation inside the stage document that owns them, so that a change to a diagram is a change to the document (FR-044). A diagram made with another tool MAY be attached as an image under FR-077, and MUST then be recorded as not structurally checked. Only C4 Levels 1 to 3, sequence diagrams and ER diagrams are recognised kinds.
- **FR-077**: A wireframe, and any attached image of a diagram, MUST be a static export stored in the story package. Its record MUST hold the file, a content fingerprint of the file, the file format, and its source: the tool, a link that identifies the exact frame in the design, the export date and who exported it. A wireframe without a link identifying the frame MUST be flagged.
- **FR-078**: The workflow MUST detect an exported file whose content differs from the fingerprint in its record and report it as a fault. Recording a new export MUST change the owning document, so that the stage needs re-review under FR-044 and the affected downstream approvals under FR-043.
- **FR-079**: The workflow MUST check that artefacts are consistent with each other and with the document text, and report each inconsistency as a finding that can be overridden (FR-045): (a) the external people and systems in the container diagram match those in the system context diagram by name, and each component diagram names the container it details; (b) the participants of a functional sequence diagram are the declared actors and the system, and nothing else; (c) the participants of a technical sequence diagram are elements of the container or component diagrams; (d) each ER diagram declares the data store it describes, and that store is shown in the container diagram; (e) every person in users and stakeholders and every system in dependencies appears in the system context diagram.
- **FR-080**: A text diagram that cannot be interpreted MUST be reported as a finding that fails the stage's gate, and MUST NOT be silently ignored or treated as absent.
- **FR-081**: The workflow MUST flag an artefact at the wrong level of abstraction, for example a functional sequence diagram naming an internal component or technology, a wireframe in Requirements, or a data-structure diagram in the Functional Specification (FR-019, FR-020).
- **FR-082**: The AI Specification MUST list, as traced items, the approved artefacts the AI agent is to read, and MUST NOT contain an artefact of its own. It MUST fail its source-traceability check when a listed artefact differs from the version approved with its owning stage.
- **FR-083**: Each wireframe, ER diagram and technical sequence diagram listed in the AI Specification MUST be covered by at least one task that traces to it, and the workflow MUST report any that is not.
- **FR-084**: The Completion stage MUST state, for each approved artefact, that it is current with what was built, or list the deviation under accepted deviations with who accepted it and why.
- **FR-085**: AI MAY draft text diagrams, which MUST be marked as AI-authored until a human has reviewed them, and MAY challenge a diagram against the document text. AI MUST NOT create or alter a wireframe export; it MUST list the required wireframes and ask the human to supply the exports.
- **FR-086**: The overview MUST list every artefact with its identifier, kind, owning stage and state, as links and status only (FR-055).

**Comprehension check (Functional and Technical Specification)**

The comprehension check confirms that the person about to approve a stage can actually explain it, which is what the stage's own last gate criterion asks for. It is adapted from the Know Your Spec preset; the differences are stated in the Assumptions.

- **FR-087**: Before the Functional Specification or the Technical Specification can be approved, the workflow MUST offer a comprehension check: five questions, asked one at a time, at fixed increasing difficulty: *recognise* (identify something the document states), *explain* (say what an item means and why), *apply* (say what the document requires in a new scenario), *trace* (follow a real chain of traced items), *evaluate* (judge a trade-off, risk or the effect of a change). The recognise and explain questions MAY be multiple choice, only where plausible alternatives exist; the other three MUST be free text.
- **FR-088**: The check MUST only start when the stage document is otherwise ready for review: its other gate criteria met or overridden and no open challenge. Otherwise it MUST report what is missing and not start.
- **FR-089**: Every question MUST be about content actually present in the stage document or its approved upstream documents, and the trace question MUST use a real traceability chain from the story. The items each question concerns MUST be chosen by the workflow from the document, not invented by AI, and the same version of a document MUST yield the same choices for the same attempt.
- **FR-090**: Answers MUST be judged on meaning, not wording. A wrong answer MUST receive a hint pointing to the relevant part of the document without stating the answer; the developer MAY retry without limit, MAY skip a question, and MAY ask for the answer, without ending the check. A skipped or revealed level MAY be asked again with a different item. Each retry MUST be a newly worded question at the same level, never the same wording twice, and the expected answer MUST NOT be stated after a wrong answer, only when the developer asks for it. On the Functional Specification, an answer that drifts into implementation detail MUST be redirected to behaviour and the question asked again without counting as an attempt (FR-020).
- **FR-091**: When a developer's answer differs from the document because the document is ambiguous, contradictory or silent, AI MUST raise a challenge (FR-034) instead of coaching towards either reading. Before the first question, AI MUST also check the items chosen for all five levels for those defects and raise every one it finds as challenges in a single batch; if it raises any, the check stops before question 1 and is planned again on the resulting version once they are answered, so that a fix does not make already-recorded levels stale. A defect met mid-check pauses the whole check in the same way.
- **FR-092**: The workflow MUST record, for each of the five levels, the outcome (understood, coached, revealed, skipped, or not applicable with a stated reason), the number of attempts and the items asked about, together with who took the check, when, and the fingerprint of the document version checked. It MUST NOT record questions' answers, the developer's answers, or any score. A level for which the document has no suitable material (for example no traced chain in a small story) MAY be recorded as not applicable with a reason.
- **FR-093**: The workflow MUST refuse to record approval of the Functional or Technical Specification unless a comprehension record exists for the document's current content with all five levels resolved to one of the outcomes in FR-092, unless a named override of that criterion is recorded (FR-010, FR-045). A change to the document after the check MUST make the record stale. Passing is not required: skipped and revealed levels do not block approval, but MUST be counted in the approval record and shown in the overview, so the reviewer of the pull request can see them.
- **FR-094**: The check MUST be taken by a person configured to confirm that stage (FR-013), never by AI. The judgement of whether an answer shows understanding is AI's assessment and MUST be labelled as such; it does not replace the developer's own confirmation of the stage (FR-012). The check MUST NOT use points, ranks, streaks, timers or rewards of any kind.

**Human-decided provenance and amendment** (dogfooding feedback: re-approval churn on an edit that is nothing but a decision the developer already made)

- **FR-095**: The content fingerprint (FR-011, FR-044) MUST be unaffected by adding or removing an `[ai-draft]` tag: reviewing and untagging AI-authored text is not a change to the content. It MUST remain affected by any other difference, including removal of a `[pending-clarification]` tag, which is a human decision made only through FR-067's carry, not a formatting no-op.
- **FR-096**: The workflow MUST let AI mark a passage as a human's own words, copied verbatim from a specific recorded decision (an accepted challenge, a resolved open question, or a clarify answer carried under FR-067), in place of tagging it `[ai-draft]`. The workflow MUST check that the cited decision exists and is in an eligible state (a challenge accepted; a question resolved or accepted; a clarify answer), and MUST report a citation that does not check out as an integrity fault that cannot be overridden. It MUST NOT, and does not claim to, verify that the marked text is a faithful transcription of what the human said (Principle II).
- **FR-097**: The workflow MUST provide a way to re-sign a stage's approval, once it needs re-review, without a full new approval, when every change since the last approval is covered by decisions the confirming person cites under FR-096, no AI-authored text remains unreviewed, and nothing outside a traceable item changed. It MUST refuse, and record nothing, otherwise. The re-signed approval MUST be as visible in the overview and every later report as an override is (FR-045), MUST NOT be recordable by AI, and MUST carry the same human confirmation FR-012 requires of a first approval.
- **FR-098**: When content approved in an earlier stage changes, the workflow MUST mark a later, already-approved stage as requiring re-review only when that stage's own approved content actually traces to the changed content, directly or not (refining FR-043 to be checked per stage-pair, not by whether any upstream document changed at all). A stage whose approval predates this distinction MUST be treated as affected until it is approved again under the refined rule.
- **FR-099**: When an earlier stage's document changes but nothing in a later, already-approved stage traces to the change, that later stage MUST remain approved, and the workflow MUST still surface that the earlier stage changed, as a non-blocking note.
- **FR-100**: On a stage's first comprehension check (FR-087) all five levels apply. On a check taken for a re-approval, the workflow MUST restrict each level to items affected by a change since the stage's last approval, MUST ask no more than two levels, and MUST require no question at all, recording every level not applicable with the reason, when every changed item is covered by a decision cited under FR-096.

### Key Entities *(include if feature involves data)*

- **Story**: The unit of work being defined. Has a title, a current stage and links to its stage documents.
- **Stage Document**: The recorded content of one stage for a story. Has a version, a status (draft, in review, approved, needs re-review, abbreviated) and content areas.
- **Quality Gate Result**: The outcome of evaluating a stage document against its gate. Lists each criterion as met, not met, or overridden.
- **Approval**: The developer's recorded confirmation of a specific version of a stage document, attesting that any out-of-band stakeholder playback took place. Records confirmer, date and time, version, and an optional note of who it was played back to.
- **Override**: A named human's decision to proceed past an unmet gate criterion. Records who, what and why.
- **Amendment**: A re-signed approval, recorded when every change since the prior approval is covered by cited human decisions. Records who, what decisions it cites, and carries the same confirmer and attestation fields as a first approval.
- **Requirement**: A statement of why and what outcome is needed. Has an identifier and links to functional requirements.
- **Use Case**: A significant way the capability is used, with actor, goal, trigger and expected outcome.
- **Functional Requirement**: A testable statement of required behaviour. Has an identifier and links to requirements or use cases.
- **Technical Decision**: A recorded engineering choice. Has an identifier, decision, reason, rejected alternative, trade-off, owner, and links to the functional and non-functional requirements it serves.
- **Open Question**: An unresolved question that could materially affect the solution. Has a status (open, resolved, accepted) and, when accepted, the accepting person.
- **Challenge**: An AI-raised point about a stage document. Has a status, response type, responder and date.
- **Ambiguity**: A gap discovered during planning or implementation, escalated for human decision. Its answer is a pending clarification in the AI Specification until carried into the earliest affected stage.
- **Traceability Link**: A directed relationship between two items in the chain from requirement to verification evidence.
- **Verification Evidence**: A record showing a requirement or behaviour was verified (for example, a test result or review record).
- **Approver Configuration**: Who may record the confirmation for each stage, and who may authorise abbreviation.
- **Story Package**: The feature directory holding the nine numbered documents, three aliases and, when needed, the assets directory for one story.
- **Compatibility Alias**: A second name for one real document (`spec.md`, `plan.md` or `tasks.md`) that lets standard Spec Kit commands find it. It is a link to that document or, where links are unavailable, a generated read-only mirror of it; it is never a separately edited document.
- **Overview**: The `s00-README.md` navigation and status dashboard for a story package.
- **Comprehension Record**: The evidence that a developer took the comprehension check on a specific version of the Functional or Technical Specification. Holds, per level, the outcome, attempts and items asked about, plus who took it, when, and the document fingerprint. Never holds answers or a score.
- **Artefact**: A diagram or wireframe belonging to one stage. Has an identifier, a kind (system context, container, component, sequence, ER or wireframe), a title, the items it traces to and, for an exported file, the file, its fingerprint and its source (tool, frame link, export date, exporter). A text diagram lives in its stage document; an exported file lives in the story package's assets.
- **Verification Record**: The evidence-oriented status of one requirement, functional requirement, acceptance criterion or artefact, with linked evidence or a recorded exception.
- **Completion Record**: The human-approved closure of a story, summarising what was delivered, accepted deviations and outstanding issues.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A developer can install the preset and companion extension into an existing Spec Kit project and begin a story at the Requirements stage in under 10 minutes, following only the documentation.
- **SC-002**: For 100% of stories completed under the process, a reviewer can identify who approved each of the first three stages, when, and which version.
- **SC-003**: For 100% of completed stories, every code change can be traced back to a requirement, and every requirement forward to verification evidence, or its absence is explicitly reported.
- **SC-004**: A reviewer can answer "why was this built, what was it required to do, why was it designed this way, what implements it, and how was it verified" for any delivered item in under 5 minutes, without asking the original author.
- **SC-005**: Zero functional or architectural decisions appear in AI-generated implementation context that cannot be traced to an approved stage.
- **SC-006**: In testing, 100% of attempts to start a stage without the prior stage's approval, or to plan without a traceable AI Specification, are refused unless a named override is recorded; 100% of overrides are visible in every later stage.
- **SC-007**: In a trial of at least 5 stories, at least 90% of ambiguities encountered during implementation are surfaced to a human as questions rather than resolved silently by the AI.
- **SC-008**: Reviewers who read a story's requirements and functional specification can each explain why the work is being done and what the system must do, without reading the implementation — confirmed by at least 4 out of 5 reviewers in a trial.
- **SC-009**: After removal of the preset and companion extension, 100% of standard Spec Kit commands behave as they did before installation, and all recorded stage documents remain readable.
- **SC-010**: Process overhead for a typical story, including human review time, does not exceed 25% of total story effort in a trial.
- **SC-011**: A person opening a story package for the first time can state its current stage, who has approved what, and what is outstanding, using only the overview document, in under 1 minute.
- **SC-012**: In 100% of story packages, each compatibility alias is either a link to, or a content-identical generated mirror of, exactly one real document, and no story package contains two differing copies of any document.
- **SC-013**: 100% of completed stories have a completion approval by a named human that follows a verification record listing each requirement as verified or excepted.
- **SC-014**: In 100% of completed stories, every approved diagram and wireframe is recorded as verified or excepted, and a reviewer can open the exact source frame of any wireframe from its record.
- **SC-015**: In testing, 100% of stories missing a required artefact without a recorded not-applicable reason, 100% of exported files that differ from their recorded fingerprint, and 100% of the inconsistencies listed in FR-079 are reported, and none of them is silently accepted.
- **SC-016**: In testing, 100% of attempts to approve the Functional or Technical Specification without a comprehension record for its current version, or with a stale one, are refused unless a named override is recorded; and 0% of comprehension records contain answer text or a score.

## Assumptions

- The four stages, their required content and their quality gates are as defined in the process standard supplied as input; that standard is the authoritative source for each stage's content and gate criteria.
- Gates are enforced by the workflow's instructions to the AI agent and by the commands it provides. They are **attestation-level, not tamper-proof**: a determined human editing files directly can bypass them, but such edits must be detectable (FR-044) and are visible in version control.
- Approver identity is recorded as a name the human supplies or that the project's version control identity provides; cryptographic signing is not required.
- Stakeholder review of each stage (business or requirements owner for Requirements; business and technical stakeholders for the Functional Specification; the technical lead for the Technical Specification) happens out of band, through playback outside the workflow. The workflow records only the developer's confirmation that it took place and the stage was accepted (FR-066). Requiring two approvers on a pull request is repository policy enforced by the version control platform, not by this workflow.
- The Plan, Tasks, Implementation, Verification and Completion stages already exist as part of Spec Kit's workflow; this work adds the definition stages before them and a hand-off from the AI Specification into Plan and Tasks.
- The AI Specification is assembled from approved material and introduces no decisions of its own, so it has no separate human approval; its gate is an automated source-traceability check, and a human review of the assembled context is optional.
- A single developer is usually the primary driver of a story; multi-person approval is supported but not required for every stage.
- For a small story the default is an abbreviated but still recorded stage, never a skipped gate.
- Verification evidence (tests, reviews) is produced by existing engineering practice; the workflow links to it rather than replacing it.
- Trial-based success criteria (SC-007, SC-008, SC-010) assume a small number of real stories can be run through the process for evaluation.
- The story package layout and the three aliases are as proposed by the author in the design discussion; the document order is fixed and the aliases exist purely for Spec Kit compatibility. The document names carry an `s` prefix (`s00-` to `s08-`) so they cannot be confused with the three-digit feature number.
- Documents are created as their stage begins rather than all scaffolded up front, so an absent document means "stage not yet reached" and the overview is the place that shows what is pending.
- Verification and Completion follow implementation and are gated in the same way as earlier stages; only Completion requires a human approval, because Verification records evidence and does not decide.
- The design of the author's existing preset (speckit-presets-gamified) is a structural reference only; no gamified or advisory behaviour is inherited.
- The comprehension check is adapted from the Know Your Spec preset (five questions at Recognise, Explain, Apply, Trace and Evaluate levels, meaning-based judging, hints that point to the document, unlimited retries, skip and reveal). It differs deliberately in three ways: it runs on the Functional and Technical Specification before approval rather than after `specify`; it leaves a record of levels and outcomes, never answers or scores; and approval requires that it was taken on the current version, not that it was passed. Whether an answer shows understanding is AI's fallible judgement, and whether the person answering is the confirmer is attestation-level like every other gate.
- Wireframes are drawn in Figma by a person and exported as static files (Figma offers PNG, SVG, PDF and JPG; stated from general knowledge and confirmed in the first trial, quickstart Part C). The workflow records and fingerprints the export; it cannot read Figma, cannot tell whether the source design changed after export, and cannot judge whether a wireframe is a good design. That is attestation-level like every other gate.
- The workflow checks text diagrams for structure and consistency. It does not render them, so whether a diagram displays correctly is checked by the team's own tooling. Mermaid's C4 support is marked experimental, so the constructs the workflow accepts are a stated subset that may need adjusting as the notation changes.
- Artefact requirements apply to every use case, screen or screen state, and new or changed container; the stage owner decides which are trivial by recording a not-applicable reason, and the AI challenge pass may dispute that reason. "Significant" is used only for the traceability of functional requirements and technical decisions (FR-025, FR-026), where it remains the owner's judgement.
- Verification evidence for an artefact is whatever suits its kind (for example a screenshot review for a wireframe, a schema comparison for an ER diagram, an integration test trace for a sequence diagram); the workflow links to it (FR-059).

## Open Questions

These are recorded, not assumed. They concern design and are for the Technical Specification to resolve; none changes what the workflow must do.

- **OQ-001** *(narrowed — relationship to Spec Kit files is now decided)*: `spec.md`, `plan.md` and `tasks.md` are aliases for `s04-ai-spec.md`, `s05-plan.md` and `s06-tasks.md`. Clarify's write target is decided (see Clarifications). Analyze's scope is decided (see Clarifications). Still open: Spec Kit's checklist command expects `spec.md` to hold user stories and functional requirements. Is the AI Specification's content sufficient for it, or does that command need adjusting by the preset? *(Build status 2026-09-25: the preset wraps `checklist` so it also reads `s01` and `s02` as read-only context; whether the result is still meaningful is unjudged and stays open until the trial in `docs/trials.md` is run.)*
- **OQ-002** *(resolved — content fingerprint; formatting-only changes ignored, see Clarifications)*
- **OQ-003** *(resolved — governed by presence of the overview document, see Clarifications)*
- **OQ-004** *(resolved — mirrors refreshed automatically before any command reads them, see Clarifications)*
- **OQ-005** *(resolved — documents carry an `s` prefix, see Clarifications)*

## Out of Scope

- Defining organisational roles, approval authority or delegation policy beyond recording and checking who confirmed.
- Running or verifying stakeholder playback, and enforcing pull request approval counts; both are out-of-band and left to the team and the version control platform.
- Replacing or redesigning Spec Kit's Plan, Tasks and Implement stages, beyond carrying traceability references into them and enforcing the package layout.
- Creating aliases beyond `spec.md`, `plan.md` and `tasks.md`.
- Running the verification tools themselves (tests, scans, linters); the workflow records and links their results.
- Any database, service, web interface, or external ticketing or project-management integration.
- Cryptographic signing of approvals.
- Scoring, narrative, or reward mechanics of any kind.
- Measuring individual developer performance.
- Modifying Spec Kit itself.
- Rendering diagrams, connecting to Figma (its API or plugins), or detecting changes in a Figma source after export.
- C4 Level 4 (code) and the C4 deployment and dynamic views; UML state, activity and use-case diagrams; a conceptual data diagram in the Functional Specification. State and workflow stay as text in the Functional Specification. These can be added later as further artefact kinds.
- Judging the design quality or visual styling of a wireframe.
- A comprehension check for the Requirements or AI Specification stages, requiring the check to be passed, recording answers, scoring or ranking developers, or verifying who is actually answering. These can be added later.

## Dependencies

- A Spec Kit version that supports presets, companion extensions, command overrides with composition, and extension hooks.
- Availability of the confirming developer at each gate, and of stakeholders for out-of-band playback.
- A small set of real stories to trial against SC-007, SC-008 and SC-010.
- For stories with a user interface, access to the Figma designs, and a person able to export frames from them.
