# Feature Specification: Proportionate Revalidation

**Feature Branch**: `002-proportionate-revalidation`

**Created**: 2026-09-30

**Status**: Draft

**Input**: User description: "based on this report" — the Developer Journey and Friction Analysis of the engineer-in-the-loop workflow (2026-09-30), which found that the developer's interactions concentrate on low-value confirmations (per-passage tag removal, re-signing already-decided changes, reading green gate criteria, per-artefact currency questions) while derived documents below the Technical Specification either block wholesale on any upstream edit or go stale without warning.

## Context

This feature refines the workflow delivered by `specs/001-staged-definition-workflow`. It does not remove any human decision point that feature established; it changes **what** the developer is asked to look at, **when**, and **how much**, so that every interaction has a discernible purpose. It builds on decisions D-23 to D-29 of that feature (tag-neutral fingerprints, `(decided: ID)` provenance, amend, item-level downstream impact, delta comprehension, change-by-change review, section-scoped judgments), extending the same item-level reasoning to the layers those decisions do not yet reach.

The governing test for every requirement below: *the developer should understand what is being built, know why, know what is theirs, and be told when something they validated needs another look — and should never be asked to confirm something they have already established unless it has materially changed.*

The binding constraints of 001 still apply: nine documents and exactly three aliases, state only in project files, hard gates with a recorded override, the AI never records an approval, and no gamification. Constitution 1.2.0 (2026-09-30) adds Principle IV, Proportionate Ceremony, which this feature implements, and amends Principle II and the hard-gate constraint so that FR-018 and FR-030 are compliant; the corresponding 001 requirements (FR-037, FR-088, FR-097) were amended in the same change.

## Clarifications

### Session 2026-09-30

- Q: When every change to an approved stage is covered by verified recorded decisions, does re-signing need the developer's confirmation? → A: The approval carries forward automatically, but each change is explained to the developer, who signs off with a short acknowledgement such as "ok" (FR-018).
- Q: Where are code-review findings recorded? → A: In a Review Findings section of the verification record, classified as implementation-rooted or upstream-rooted (FR-027).
- Q: Do low-severity challenges block approval? → A: No; they are listed as outstanding at approval (FR-030).
- Q: How is a paragraph the AI wrote judged to need the developer's review? → A: A paragraph that restates, and cites, content already reviewed and approved in an earlier document is treated as already approved, unless it adds anything significant (the AI's labelled judgement). Every paragraph has a hash recorded when it is reviewed or accepted as restated, so it stays settled until it or its source changes (FR-009, FR-011, FR-039). *(Refined by `/speckit-analyze`: "approved" became "settled", so that content restating the AI Specification, plan or tasks, which are never approved, can also count as restated; see FR-009.)*
- Q: What happens to a completed task when something it was built from changes? → A: All affected tasks are listed together, each with the change that affects it and the AI's labelled view of whether the code is likely still valid; the developer approves them all at once, or approves all except named tasks, which are reopened or questioned. Completion is refused until the list is answered (FR-005).
- Q: How many challenge severity levels are there, and who sets them? → A: Three — high, medium and low — so the developer has an order in which to resolve them. The AI proposes the level when it raises a challenge, labelled as its own; the developer can change it. High and medium block approval; low does not (FR-029, FR-030).
- Q: Must open low-severity challenges be answered before completion? → A: Yes, in one batch: at completion every open low challenge is listed, and the developer answers the whole list in one reply (for example "defer all, accepted as minor") or picks out any to act on (FR-040).
- Q: How are stale items brought up to date, given that documents must stay accurate and easy to read? → A: Only stale items are re-derived, in place; a re-derivation that simply restates its updated source is settled without review. Documents always describe the current truth (what will be built, then what was built), with no inline history; changes are recorded in a generated Change Log at the end of each document and in git; hashes and provenance are kept out of the prose; and when what was built differs from the design, the design is corrected rather than annotated (FR-041 to FR-045).
- Q: How are inferred paragraphs presented for review? → A: All inferred paragraphs in a stage are listed together, each with its full text and why it is inferred; the developer replies "ok to all", "ok except" named paragraphs (which are reworked), or questions any one (FR-010).
- Q: Do `[ai-draft]` markers still appear in document text? → A: Only on inferred paragraphs not yet reviewed; the system adds them and removes them on acceptance, so an approved document carries none and nobody edits a tag by hand (FR-046).
- Q: On upgrade, do paragraphs in already-approved documents count as reviewed? → A: Yes: where a document's current text matches its approval fingerprint, every paragraph's hash is recorded as reviewed on first run, with nothing asked; a document changed since approval follows the change-acceptance flow (FR-047).
- Q: What counts as one paragraph (content block)? → A: Each numbered item with its continuation lines is one block; every other run of text between blank lines is one block; a whole diagram, table or code block is one block; headings are not blocks (FR-039).
- Q: Who may answer the batch lists and change a challenge's severity? → A: Accepting, re-confirming, deferring or lowering a severity needs a person configured to confirm that stage; raising a severity or questioning an item can be done by anyone and is recorded with their name (FR-048).
- Q: Does unreviewed inferred content in the AI Specification, plan or tasks stop the next step? → A: Only for the work that depends on it: a task tracing to an unreviewed inferred paragraph cannot be implemented, everything else proceeds, and the paragraphs are listed for one "ok to all / ok except" reply (FR-049).
- Q: Are uncovered changes to an approved stage shown one at a time or as one list? → A: As one list, like every other review: each change shown with what changed, answered "ok to all", "ok except" or by questioning one, then one closing confirmation; stale evidence rows are handled the same way (FR-017, FR-006).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - An upstream edit stops only the work it affects (Priority: P1)

A developer is part-way through implementation. They notice a wording error in one technical decision and correct it. Today, that edit withdraws approval from every item in the Technical Specification, the AI Specification fails its check, and planning, task generation and implementation are all refused until the stage is re-signed. Instead, the developer is told exactly which AI Specification items, plan sections, tasks and verification rows trace to the corrected decision; those are marked stale; everything else continues.

**Why this priority**: This is the single largest source of "I have already reviewed this, why is everything blocked?" frustration, and the precondition for every other backwards-movement improvement. Without it, targeted revalidation elsewhere still ends in a whole-pipeline halt.

**Independent Test**: In a story with an approved Technical Specification, a derived AI Specification, a plan and tasks, change one decision's text. Verify that only items tracing (directly or transitively) to that decision are reported stale, that implementation of an unaffected task is permitted, and that implementation of an affected task is refused with a message naming the stale source.

**Acceptance Scenarios**:

1. **Given** an approved Technical Specification with decisions DEC-001 to DEC-005 and tasks tracing to each, **When** the developer edits DEC-003 only, **Then** the status report lists the AI Specification items, plan sections, tasks and verification rows that trace to DEC-003 as stale, and lists nothing else as stale.
2. **Given** the situation above, **When** implementation is requested for a task that traces only to DEC-001, **Then** it proceeds.
3. **Given** the situation above, **When** implementation is requested for a task that traces to DEC-003, **Then** it is refused, naming DEC-003 as the changed source and the command that resolves it.
4. **Given** a completed task that traces to an AI Specification item whose source has since changed, **When** the developer views status, **Then** the task is shown as "completed against an earlier version" rather than silently remaining complete.
5. **Given** a verification evidence row for FR-007, **When** FR-007 changes after the evidence was recorded, **Then** the row is reported as evidence for an earlier version and completion is refused until it is re-established or excepted.
6. **Given** an edit that changes only formatting, **When** status is computed, **Then** nothing is reported stale.
7. **Given** three completed tasks affected by one upstream change, **When** the developer is shown the list and replies "ok, except T014", **Then** the other two are re-confirmed against the current version, T014 is reopened, and nothing is asked task by task.

---

### User Story 2 - Review effort matches what the content is (Priority: P1)

A developer reviewing a drafted stage document is currently asked to remove an `[ai-draft]` tag from every paragraph the AI typed, whether it is a background paragraph, a paraphrase of the developer's own answer, or a behaviour the AI invented to fill a gap. Instead, content is distinguished by its provenance — **restated** from an approved source, **decided** by the developer in their own words, or **inferred** by the AI — and only inferred content requires the developer's review. Restated content is checked by the tool for fidelity to its source; decided content needs nothing more.

**Why this priority**: Per-paragraph tag removal is the highest-volume interaction in the workflow and trains developers to "accept all", which removes the value of the control. Directing attention to inferred content turns the same effort into real validation.

**Independent Test**: Draft a stage containing a restated paragraph, a decided paragraph and an inferred paragraph. Verify that approval is refused only while the inferred paragraph is unreviewed, that the restated paragraph is flagged if its source changes or it is judged to add something significant, that a reviewed paragraph is not presented again unless it or its source changes, and that the developer is shown a count and list of inferred paragraphs only.

**Acceptance Scenarios**:

1. **Given** a stage document where the AI has written 30 paragraphs of which 4 introduce content not present in any approved source or recorded decision, **When** the developer prepares to approve, **Then** they are asked to review those 4 paragraphs, and the other 26 are presented as restated or decided with their sources.
2. **Given** an AI Specification item that restates DEC-002, **When** DEC-002 is later changed, **Then** the item is flagged as no longer matching its source.
3. **Given** an AI Specification item that goes beyond its cited source (adds a constraint the source does not contain), **When** the stage is checked, **Then** the item is classified as inferred and presented for developer review, not accepted as restated.
4. **Given** any stage (definition or derived), **When** the developer asks what they are expected to check, **Then** the answer is the same rule in every stage: review inferred content; restated content is tool-checked; decided content is already yours.
5. **Given** a paragraph the AI classified as restated, **When** the developer disagrees with that classification, **Then** they can reclassify it as inferred, and the reclassification is recorded.
6. **Given** 4 inferred paragraphs, **When** the developer replies "ok except P3", **Then** the other 3 are recorded as reviewed by their hashes, P3 is reworked and presented again on its own, and nothing is asked paragraph by paragraph.
7. **Given** an AI Specification item the AI inferred (a retry policy no decision states), **When** implementation is requested for a task tracing to it, **Then** it is refused until the item is reviewed, while tasks not tracing to it proceed.

---

### User Story 3 - One way to accept a change to something already approved (Priority: P2)

After an approved stage changes, the developer currently chooses between a full re-approval, an amend (for which they must name the decision ids that cover each change and give a fresh attestation), and a change-by-change review (which asks for an attestation again after each change has already been accepted). Instead, there is one action: the tool shows what changed since the approval, identifies which changes are already covered by the developer's recorded decisions, walks the developer through only the uncovered changes, and records one confirmation.

**Why this priority**: The three-way choice is the most confusing point for a developer moving backwards, and naming ids the tool already verifies is pure repetition. It is P2 because User Story 1 must first make the change's reach precise.

**Independent Test**: Change an approved stage with one change carried from a resolved open question and one new reworded paragraph. Verify that the developer is asked about the reworded paragraph only, is not asked to name the open question's id, and gives one confirmation that re-signs the stage.

**Acceptance Scenarios**:

1. **Given** an approved stage where every change carries a verified recorded-decision marker, **When** the developer asks to accept the changes, **Then** the tool explains each change and the recorded decision covering it, the developer signs off with a short acknowledgement such as "ok", and the approval carries forward, with no id naming, no fresh attestation and no comprehension question.
2. **Given** an approved stage with a mix of covered and uncovered changes, **When** the developer accepts, **Then** only the uncovered changes are presented, together as one list the developer can accept in one reply or except named items from, and one confirmation at the end re-signs the stage.
3. **Given** an approved stage whose changes include newly inferred content, **When** the developer accepts, **Then** the delta comprehension check (at most two questions, about changed items only) is offered before the confirmation.
4. **Given** any re-signed approval, **When** the overview or any later report is read, **Then** it shows how the approval was reached (first approval, covered by recorded decisions, or reviewed change by change) and the ids it rests on, as visibly as an override.

---

### User Story 4 - Moving backwards is one action with an impact report (Priority: P2)

A developer working at a later stage — technical design, task breakdown, implementation, or code review — discovers that an earlier document is wrong. Currently this becomes a chain of separate commands (clarify, resolve, re-review, amend, resolve again) during which all implementation is refused, and nothing records where the problem was found. Instead, the developer states the problem once, confirms which stage it belongs to when that is genuinely ambiguous, and is shown the proposed upstream change together with everything downstream it would make stale — before anything is changed.

**Why this priority**: Backwards movement is where the workflow currently generates the most administrative work per unit of engineering value, and where discovery context is lost.

**Independent Test**: During implementation, report that an assumption in a functional requirement is wrong. Verify that one action produces the proposed upstream edit, the list of affected downstream items, and the origin of the discovery; that unaffected tasks remain implementable meanwhile; and that the recorded change names where it was found.

**Acceptance Scenarios**:

1. **Given** a developer in implementation who finds that FR-004 is wrong, **When** they report it, **Then** they are shown the stage the correction belongs to, the proposed edit, and every downstream item that would become stale, before the edit is applied.
2. **Given** a correction whose owning stage is unambiguous (it contradicts a single cited item), **When** it is reported, **Then** the developer is not asked which stage it belongs to.
3. **Given** a correction whose owning stage is genuinely ambiguous, **When** it is reported, **Then** the developer decides the stage, and that decision is recorded.
4. **Given** any backwards correction, **When** it is recorded, **Then** it carries the stage and item where it was discovered, visible in the trace for the changed item.
5. **Given** an implementation-time question that affects only some tasks, **When** it is pending, **Then** only tasks tracing to the affected items are refused.
6. **Given** an upstream change that alters the premise of an earlier rejected or deferred challenge, **When** the change is accepted, **Then** that challenge is reported as possibly no longer settled, for the developer to reconfirm or reopen.
7. **Given** a code-review finding, **When** the developer records it, **Then** it is written to the Review Findings section of the verification record, the developer classifies it as rooted in implementation or in a named upstream item, and an upstream-rooted finding follows the same backwards path as any other correction, with the finding as its origin.

---

### User Story 5 - The developer sees only what needs them (Priority: P3)

When a gate is checked, the developer currently reads every criterion (14 to 19 per stage), most of them already met. Challenges arrive from several passes with no indication of which matter. Instead, the gate view leads with unmet criteria and the AI's judgment calls, with met structural criteria summarised in one line; challenges carry a severity; and every request for the developer's attention states its purpose (awareness, understanding, decision, validation or approval).

**Why this priority**: This reduces reading effort and challenge fatigue but changes no decision point, so it follows the structural fixes.

**Independent Test**: Check a stage with 16 criteria of which 2 are unmet and 3 are AI judgments. Verify that the developer is shown 5 entries in detail and one summary line for the rest, and that full detail remains available on request.

**Acceptance Scenarios**:

1. **Given** a gate check, **When** it is presented, **Then** unmet criteria and AI-judged criteria appear first in detail, and met structural criteria are summarised with a count, expandable on request.
2. **Given** challenges raised against a stage, **When** they are presented, **Then** each carries a severity of high, medium or low (the AI's proposal labelled as such), and they are ordered high, then medium, then low.
3. **Given** a request for the developer to act, **When** it is presented, **Then** it states which of awareness, understanding, decision, validation or approval it is.
4. **Given** challenges from several passes over the same stage, **When** two raise the same point, **Then** the developer sees it once.
5. **Given** a stage whose only open challenges are low severity, **When** the developer approves, **Then** approval is permitted and the open challenges are listed as outstanding at approval and in the overview.
6. **Given** a low-severity challenge, **When** the developer raises it to medium or high, **Then** it blocks approval until answered.

---

### User Story 6 - Completion asks only about what implementation touched (Priority: P3)

At completion the developer is asked whether every approved diagram is still current, and must remove a tag from every evidence row. Instead, diagram currency is asked only for artefacts that implementation touched (reached by a task with linked code changes) or whose source changed; automated evidence that the tool can resolve is checked by the tool; and the developer reviews manual evidence, exceptions and the final confirmation.

**Why this priority**: Real but lower-volume friction at the end of the lifecycle.

**Independent Test**: Complete a story with 8 approved artefacts of which 3 were reached by implemented tasks. Verify the developer is asked about 3, the other 5 are listed as untouched, and automated evidence rows that resolve are not presented for manual review.

**Acceptance Scenarios**:

1. **Given** 8 approved artefacts of which 3 were reached by tasks with linked code changes, **When** completion is prepared, **Then** the developer is asked about the currency of those 3, and the other 5 are listed as untouched without a question.
2. **Given** an automated evidence row naming a test and its result, **When** the tool can confirm that the named test exists in the repository, **Then** the row does not require developer review.
3. **Given** a manual evidence row (a walkthrough, a screenshot review), **When** completion is prepared, **Then** the developer is asked to confirm it.
4. **Given** any artefact whose source changed after approval, **When** completion is prepared, **Then** its currency is asked even if no task reached it.
5. **Given** five open low-severity challenges across the story, **When** completion is prepared, **Then** they are listed together, the developer replies "defer all, accepted as minor", each is recorded as deferred with that reason and the developer's name, and the list appears in the completion record.
6. **Given** an approved design that differs from what was built, **When** the developer accepts the difference during completion, **Then** the design document is corrected to describe what was built, a Change Log entry records the correction, and the completion record lists it; no deviation note is left in the design's prose.

---

### Edge Cases

- A change to an item that nothing downstream traces to: nothing is reported stale, and the change is still visible as unreviewed in its own stage.
- A cycle or a missing id in trace references: reported as a document error, never treated as "unaffected".
- A derived item that cites several sources, only one of which changed: the item is stale.
- An approval recorded before this feature (no per-item source snapshot for derived layers): treated conservatively — the derived layer is reported as "unknown currency" and asked about once, never silently assumed current.
- The developer reverts an upstream edit exactly: items previously reported stale return to current without any action.
- A restated paragraph whose meaning matches its source but whose wording differs: the tool's fidelity check is attestation-level (it cannot prove equivalence of meaning), and the limit is stated where the check is reported.
- A carried-forward sign-off from someone not configured to confirm that stage: refused, exactly as an approval by them would be.
- A code-review finding reported after completion was approved: it reopens completion as `needs-re-review`, like any other change to an approved stage.
- A story in progress when this feature is installed: approved, unchanged documents are adopted as reviewed without any question (FR-047); only what changed since approval, or what is still tagged, is presented.
- A story abbreviated under 001: abbreviation rules are unchanged; the provenance rule applies to the shorter document.
- Two developers answer the same entry differently (one accepts it, another excepts, questions or reopens it at the same content): the entry is in conflict and blocks re-signing of that stage until a person configured to confirm it answers again, as challenge conflicts are today (FR-050).
- An override of the inferred-content review: allowed as a named, reasoned override of one criterion, visible everywhere, exactly as the existing `unreviewed-ai-content` override.

## Requirements *(mandatory)*

### Functional Requirements

**Item-level staleness in every layer (Story 1)**

- **FR-001**: Every item in the AI Specification, plan, task list and verification record MUST record the version of each source item it was derived from or verifies, at the time it was written or re-established.
- **FR-002**: The system MUST report a derived item as stale when any source it records has changed since, directly or transitively, and MUST NOT report it stale when no recorded source has changed.
- **FR-003**: A change to an approved stage MUST withdraw approval-derived standing only from the items that changed and the items that trace to them, not from every item in the stage.
- **FR-004**: Entry to planning, task generation and implementation MUST be refused only for work that traces to a stale, pending or unapproved item; work tracing only to current, approved items MUST be permitted.
- **FR-005**: A completed task whose sources have changed MUST be reported as completed against an earlier version. All such tasks MUST be presented to the developer together as one list, each line naming the task, the changed source and what changed, with the AI's view of whether the existing code is likely still valid (labelled as the AI's), those judged likely to need rework first. The developer MUST be able to answer the whole list in one reply: approve all, approve all except named tasks (which are reopened), or question a named task (which pauses only that task). An approved task is re-confirmed against the current source versions. Completion MUST be refused while any listed task is unanswered.
- **FR-006**: Verification evidence whose target has changed since the evidence was recorded MUST be reported as evidence for an earlier version, and completion MUST be refused while any such row is neither re-established nor excepted. All such rows MUST be presented together as one list, each naming the target and what changed, answerable in one reply: re-establish all, all except named rows, or question a named row.
- **FR-007**: Formatting-only changes MUST NOT make any item stale (consistent with the existing fingerprint rules).
- **FR-041**: When items go stale, the AI MUST re-derive only the stale items, against the current source versions, and MUST leave every other item untouched. A re-derived item that restates its updated source and adds nothing significant is settled without developer review; one that changed in substance or adds something significant is inferred and presented for review (FR-009).
- **FR-042**: Every stage document MUST read as the current truth: before implementation, what will be built; after it, what was built. A change MUST replace the text it changes, in place; superseded wording, strike-through and inline amendment notes MUST NOT remain in the document's content sections.
- **FR-043**: Each stage document MUST carry, after its content sections, a Change Log generated by the system: one line per accepted change after first approval (in the AI Specification, plan, task list and verification record, which are never approved, one line per closed backwards correction; re-derivations are left to version control), giving the date, the item, a short summary of what changed, where the change was found and who accepted it. The overview MUST show the most recent entries. The full previous text is left to version control.
- **FR-044**: Bookkeeping (paragraph hashes, source versions, provenance classes, review records) MUST be kept in the document's record region, not in the prose. Readable text MUST carry only the short clauses the item grammar already defines (for example `(traces: ...)`, `(decided: ...)`, `(status: ...)`, `(code: ...)`, `[pending-clarification]`) and the `[ai-draft]` cue of FR-046; no hash, provenance class, source version or review record may appear in it.
- **FR-045**: When what was built differs from the approved design and the developer accepts the difference, the design MUST be corrected through the backwards action (FR-021) so that it describes what was built, and the completion record MUST list each such correction. An accepted deviation, where the document intentionally still differs from the code, MUST remain available only when the developer decides the document should keep describing a future target, and MUST be recorded with that reason.
- **FR-047**: On the first run after upgrade, for each stage document whose current text matches its recorded approval fingerprint, the system MUST record every paragraph's hash as reviewed without asking anyone. A document changed since its approval MUST follow the change-acceptance action (FR-015). In a document never approved, a paragraph without an `[ai-draft]` tag (already reviewed under the earlier rules) MUST be recorded as reviewed, and a paragraph with one MUST be treated as inferred and unreviewed.
- **FR-008**: Where a derived layer has no recorded source versions (written before this feature), its currency MUST be reported as unknown and raised once for the developer, never assumed current.

**Provenance-proportionate review (Story 2)**

- **FR-009**: Every paragraph the AI writes MUST be classified as restated, decided or inferred. **Restated**: it cites an item already settled in an earlier document, and adds nothing significant to it; it is treated as already approved and needs no developer review. An item is settled when it is covered by a current approval (Requirements, Functional and Technical Specification), or, in the AI Specification, plan and task list, which are never approved, when it is itself restated, decided or reviewed and not stale. **Decided**: the developer's own recorded words, as today's `(decided: ID)`. **Inferred**: anything else, including a restated paragraph judged to add something significant.
- **FR-010**: Approval of a definition stage MUST be refused while any inferred paragraph is unreviewed; restated and decided paragraphs MUST NOT require per-paragraph developer review. All unreviewed inferred paragraphs of a stage MUST be presented together as one list, each with its full text and the reason it is inferred (no cited source, or what it adds beyond its source). The developer MUST be able to answer the list in one reply: accept all, accept all except named paragraphs (which are reworked and presented again), or question a named paragraph. Each accepted paragraph's hash is recorded as reviewed (FR-039).
- **FR-011**: For each restated paragraph the system MUST verify that the cited source exists and is settled (FR-009), and record the source's hash. The paragraph MUST be flagged when the source's hash changes, or when the AI judges that the paragraph adds something significant beyond its source; that judgement MUST be labelled as the AI's. A flagged paragraph is treated as inferred until reviewed.
- **FR-012**: The classification rule and what the developer must check MUST be the same in every stage, including the AI Specification, plan, tasks and verification record.
- **FR-013**: The developer MUST be able to reclassify any restated paragraph as inferred; the AI MUST NOT reclassify inferred content as restated or decided without a cited source that the system verifies.
- **FR-014**: The limit of the fidelity check (it cannot prove that two wordings mean the same) MUST be stated wherever the check's result is reported.
- **FR-049**: In the AI Specification, plan and task list, an unreviewed inferred paragraph MUST block only the work that depends on it: planning or task generation for what traces to it, and implementation of any task that is, or traces to, it. All other work MUST proceed. These paragraphs MUST be listed for review in the same one-reply form as FR-010, and the list MUST be offered whenever such a paragraph blocks requested work. In the verification record, an unreviewed inferred paragraph (for example an evidence row) MUST block completion approval, overridable as the existing `unreviewed-ai-content` override.
- **FR-046**: The `[ai-draft]` marker MUST appear in document text only on inferred paragraphs not yet reviewed. The system MUST add it when a paragraph is classified inferred and remove it when the paragraph is accepted; restated and decided paragraphs MUST NOT carry it. An approved document MUST carry none. The marker is a readable cue only: review status is determined by recorded hashes (FR-039), so adding or removing a marker by hand MUST NOT change it.
- **FR-039**: Every paragraph (formally a content block; "paragraph" is used as its everyday name throughout this specification) of a stage document MUST have a hash, kept in the document's record region and never in the prose, recorded by the system when the developer reviews it or when it is accepted as restated. Whether a paragraph has been reviewed MUST be held by the system from these hashes, not by the presence or absence of a tag edited by hand. A paragraph MUST need the developer's attention only when its own hash differs from the recorded one, its cited source's hash differs from the recorded one, or it has never been reviewed or accepted as restated. Formatting-only differences MUST NOT change a paragraph's hash. A content block is: each numbered item (for example REQ-001, FR-004, DEC-002, AIS-007, a task or an evidence row) together with its continuation lines; otherwise each run of text between blank lines; and each diagram, table or fenced code block as a whole. Headings, HTML comments and the record region are not content blocks.

**Single change-acceptance action (Story 3)**

- **FR-015**: There MUST be one developer action for accepting changes to a previously approved stage, replacing the choice between re-approval, amend and change-by-change review; the existing commands MAY remain as aliases.
- **FR-016**: The action MUST determine, without the developer naming ids, which changes are covered by verified recorded decisions and which are not.
- **FR-017**: The action MUST present only the uncovered changes, together as one list, each showing what changed; the developer MUST be able to answer it in one reply (accept all, accept all except named changes, or question a named change), and the action MUST end with exactly one recorded human confirmation in the developer's own words. Every review list in this feature (FR-005, FR-006, FR-010, FR-017, FR-040, FR-049) MUST use this same form. A person MUST NOT be asked again about a change they have already accepted, at the same content, on the inferred-items list (D-45); an exception, question or reopen on that list does not count as acceptance.
- **FR-018**: When every change since an approval is covered by verified recorded decisions, the approval MUST carry forward without a new attestation. The system MUST explain each change to the developer in plain terms (what changed, and which of their recorded decisions covers it), and the carry-forward is recorded only once the developer acknowledges the explanation with a short sign-off in their own words (for example "ok"), stored verbatim with their name and time. The AI MUST NOT supply the sign-off, and the carried-forward approval MUST be marked as such wherever approvals are shown.
- **FR-019**: Delta comprehension (as 001 FR-100) MUST be offered only when uncovered changes include inferred content.
- **FR-020**: Every re-signed approval MUST show how it was reached and the ids it rests on, in the stage document, the overview and every later report.

**Backwards movement (Story 4)**

- **FR-021**: The developer MUST be able to report a problem in an earlier artefact from any later stage in one action, stating the problem and the item it concerns.
- **FR-022**: Before any change is applied, the system MUST show the owning stage, the proposed change, and every downstream item that would become stale.
- **FR-023**: The developer MUST be asked which stage owns a correction only when that is ambiguous; the AI MUST NOT decide an ambiguous ownership.
- **FR-024**: Each backwards correction MUST record the stage and item where it was discovered, and that origin MUST appear in the trace of the changed item.
- **FR-025**: An implementation-time question MUST block only the tasks that trace to the items it concerns, replacing the current document-wide refusal while any clarification is pending.
- **FR-026**: When an accepted upstream change alters an item that an earlier rejected or deferred challenge targeted, that challenge MUST be reported as possibly unsettled, for the developer to reconfirm or reopen.
- **FR-027**: Code-review findings MUST be recorded in a Review Findings section of the verification record, each classified by the developer as rooted in the implementation or in a named upstream item. An upstream-rooted finding MUST follow the backwards-correction path (FR-021 to FR-024) with the finding as its origin, and completion MUST be refused while any finding is neither resolved nor excepted. A finding recorded or changed after completion was approved MUST make completion need re-review.

**Focused presentation (Story 5)**

- **FR-028**: Gate results MUST lead with unmet criteria and AI-judged criteria in detail and summarise met structural criteria with a count, with full detail available on request.
- **FR-029**: Every challenge MUST carry a severity of high, medium or low. The AI MUST propose the severity when it raises the challenge, labelled as the AI's; the developer MUST be able to change it at any time. Challenges MUST be presented in severity order, high first, so the developer has an order in which to resolve them.
- **FR-030**: Open low-severity challenges MUST NOT block approval; they MUST be listed as outstanding at the point of approval and in the overview, and remain open to be answered later. Open high- and medium-severity challenges block approval as today. Raising a low challenge to medium or high makes it blocking; lowering a challenge to low is a developer decision and MUST be recorded with the developer's name.
- **FR-031**: Duplicate challenges from different passes over the same stage MUST be shown to the developer once.
- **FR-032**: Every request for developer action MUST state its purpose as one of awareness, understanding, decision, validation or approval.

**Completion (Story 6)**

- **FR-040**: Completion approval MUST be refused while any challenge on any stage of the story remains open. Every open low-severity challenge MUST be presented at completion as one list, answerable in one reply: defer all with one reason and acceptance of the risk (recorded against each challenge, with the developer's name), or defer all except named challenges, which the developer then accepts or rejects individually. The deferred list MUST appear in the completion record.
- **FR-033**: Diagram currency MUST be asked only for artefacts reached by a task with linked code changes, or whose source changed after approval; other artefacts MUST be listed as untouched without a question.
- **FR-034**: Automated evidence naming a test or check MUST be confirmed by the system where the named test or check can be found in the repository; only evidence the system cannot confirm, and all manual evidence, MUST be presented to the developer.
- **FR-035**: The system MUST NOT execute tests or call any network service to confirm evidence (it reads files only, per 001 constraints); confirming that a named result is genuine remains attestation-level and MUST be stated as such.

**Preserved guarantees**

- **FR-048**: Every action that reduces what must still be reviewed or decided (accepting inferred paragraphs, re-confirming tasks, accepting changes, carrying an approval forward, deferring a challenge, or lowering a challenge's severity) MUST be refused from anyone not configured to confirm the stage concerned, as approvals are. Actions that only add scrutiny (raising a challenge's severity, questioning an item, reopening a task) MAY be taken by anyone, and MUST be recorded with their name. Wherever this specification says "the developer" accepts, approves, re-confirms or defers, it means a person configured to confirm that stage.
- **FR-050**: When two people give different answers to the same review-list entry for the same content (one settling it, another excepting, questioning or reopening it), the entry MUST be recorded as in conflict with both answers, and MUST block re-signing of its stage and the work that depends on it until a person configured to confirm the stage answers it again.
- **FR-036**: No change in this feature may allow the AI to record an approval, answer a challenge or open question, accept a risk or exception, or make a technical decision.
- **FR-037**: Every rule in this feature that decides whether an action proceeds or writes a record MUST be deterministic helper behaviour, not prompt text (Constitution Principle I).
- **FR-038**: The first approval of each definition stage, including the full comprehension check for Functional and Technical, is unchanged.

### Key Entities

- **Source version**: The recorded identity of an item's content at the moment a downstream item was derived from it or evidence was recorded against it; the basis for staleness.
- **Provenance class**: Restated, decided or inferred; attached to each AI-written paragraph and determining who must review it.
- **Content block**: A numbered item with its continuation lines, a run of text between blank lines, or a whole diagram, table or code block, of a stage document with its recorded hash, its provenance class, and (if restated) its cited source and that source's hash; the unit of review and of staleness.
- **Change acceptance**: One developer's acceptance of the changes to a previously approved stage, listing the covering decisions found automatically, the changes accepted individually, and the confirmation.
- **Backwards correction**: A reported problem in an earlier artefact, with its origin (stage and item where found), owning stage, proposed change and impact list.
- **Change Log entry**: A generated line recording one accepted change to a stage document after its first approval, or one closed backwards correction in a document that is never approved: date, item, summary, origin and who accepted it. The document's history lives here and in version control, not in its prose.
- **Challenge severity**: High, medium or low; proposed by the AI when a challenge is raised and changeable by the developer. It sets the order of resolution, and high and medium block approval (FR-030).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In the reference story (4 requirements, 3 use cases, 12 functional requirements, 5 decisions, 8 artefacts), the number of developer interactions that are not decisions, first approvals or reviews of inferred content falls by at least 60% compared with the 001 workflow, while the number of decision and first-approval interactions is unchanged.
- **SC-002**: A single-item correction to an approved stage during implementation leaves 100% of tasks that do not trace to it implementable, in scenario tests.
- **SC-003**: 100% of derived items and evidence rows whose recorded source changed are reported stale, and 0% whose sources are unchanged are reported stale, across the scenario suite.
- **SC-004**: Accepting changes that are entirely covered by recorded decisions takes exactly one short developer sign-off, zero id entries and zero fresh attestations.
- **SC-005**: A backwards correction from implementation reaches a re-signed upstream stage in no more than 3 developer interactions when the owning stage is unambiguous and the correction is the developer's own wording.
- **SC-006**: In the human trial protocol, at least 80% of trial developers can correctly state, for any checkpoint they are shown, what they are expected to check and why.
- **SC-007**: In the human trial protocol, no trial developer reports being asked to reconfirm something they had already confirmed without an intervening change, where 001 trials (once run) establish the baseline.

## Assumptions

- The 001 constraints on the solution remain binding: no new stage document, no new alias, no database or service, hard gates with named overrides, no gamification. Any new record (backwards corrections, change acceptances, source versions) is a record block inside an existing document.
- "Inferred" is defined conservatively: anything the system cannot match to a cited settled source or verified recorded decision is inferred. Misclassification errs toward more review, never less.
- Whether a restated paragraph adds something significant is the AI's judgement, not a proof; the deterministic part is that the cited source exists, is settled and is unchanged (by hash). Per Constitution Principle II this is stated as an attestation-level limit.
- The existing D-23 to D-29 mechanisms (item hashes, upstream snapshots, `(decided: ID)`, delta comprehension, section-scoped judgments) are reused rather than replaced.
- Existing commands (`approve`, `amend`, `review-changes`, `clarify`, `resolve`) remain callable for compatibility; the new single actions subsume them rather than remove them.
- The "reference story" in SC-001 is a scenario fixture to be defined in planning, and interaction counts are measured by the scenario harness, not by human timing.
- Human trials for 001 have not been run; SC-006 and SC-007 depend on the trial protocol in `docs/trials.md` being extended and run.
