# Feature Specification: Proportionate Effort

**Feature Branch**: `003-proportionate-effort`

**Created**: 2026-10-02

**Status**: Draft

**Input**: User description: "Start a new governed story, `003-proportionate-effort`, that fixes the friction found in a real run of this extension on 2026-10-01." The run took story 002 of the rich specification viewer (a small viewer feature) through the full workflow: 138 minutes of process against 5 minutes of implementation, 128 lines of code and about 420 lines of tests against about 5,800 lines of stage documents. The maintainer's direction: preserve every human-only gate, approval, attestation and recorded override, and reduce only asks that are duplicated, of low value or aimed at the wrong level; size reviews to the list; never ask the developer implementation-level questions; do everything in chat, never requiring a file to be opened.

## Context

This feature refines the workflow delivered by `specs/001-staged-definition-workflow` and `specs/002-proportionate-revalidation`. 002 made revalidation proportionate (what must be looked at again after a change). This feature makes the **first pass** proportionate (how much is asked of a person for a story of a given size), fixes the defects that made the 2026-10-01 run slower than it needed to be, and removes the record bulk that drove the agent's context to 166k tokens and forced five compactions in two and a half hours.

The governing test is the same as 002's, applied to the first pass: *every request for a person's attention must earn its place (Constitution Principle IV), and no gate, approval, attestation or recorded override gets weaker.* Any new waiver, skip or shortened path is authorised by a named person with a reason, recorded, and shown wherever the gate it affects is shown.

The 2026-10-01 run is the first data point for 001's SC-010 (process overhead at most 25% of story effort). At about 96% it misses that target by a wide margin, and is recorded in `docs/trials.md`.

### Root cause of the wrong-story targeting (investigated 2026-10-02)

- **The active-story pointer was never moved.** The helper writes the project's active-story pointer only when none exists, so starting story 002 left it naming story 001. The Requirements command also tells the AI to reuse that pointer when it names a feature directory, without checking that the directory is a different, already-governed story. Every later call without an explicit target went to 001, and the first judgments call overwrote 001's approved assessment record. **This is a defect.**
- **No branch was created, by design but without warning.** Neither the helper nor any stage command creates a git branch; in Spec Kit, branch creation belongs to the optional git extension's pre-specify hook. The trial project has only this extension installed, so story 002 was written and committed on the branch `001-rich-spec-viewer`. Leaving git alone is consistent with 001's constraint that installation and the helper change no project or Spec Kit state beyond the story's own files, but nothing tells the developer, so it reads as a fault. FR-006 makes the start stop and ask before writing on any branch other than the main branch or one named for the new story.

## Clarifications

### Session 2026-10-02

- Q: A new story is started while the git branch is named for a different story. What happens? → A: The start is refused until the developer switches branch or confirms in one reply, recorded with their name; the helper never creates or switches branches (FR-006).
- Q: How far does the small-story profile shorten the comprehension check? → A: To two levels chosen by the helper; the other three are recorded as not applicable, citing the profile (FR-021).
- Q: How is a comprehension target that is the person's own decision recorded? → A: As a distinct outcome, `own-decision`, so a reviewer can see it was not asked (FR-032).
- Q: Under the small-story profile, may planning and task generation proceed before the AI Specification's inferred content is reviewed? → A: Yes; for a small story, developer experience takes priority. The profile authorisation is recorded as a named, reasoned override of `unreviewed-ai-content` for those two entries only; implementation still waits for the combined review (FR-022).
- Q: Must a developer write a custom sentence to approve a stage? → A: No. The approval question states what is being confirmed, and a reply such as "ok", "yes" or "approved" is a complete approval, recorded verbatim with the question it answered; the name is asked once per session (FR-047 to FR-049). Constitution Principle II is clarified to match (PATCH 1.2.2).
- Q: Do `ai-decided` decisions appear in the stage's review list of AI-written content, or only in the summary? → A: In the review list, as their own group, answered by the same one reply; they are also named in the summary (FR-027).
- Q: Can a developer end a one-at-a-time list early with "ok to the rest"? → A: Yes; every remaining entry is accepted in that one reply and marked in the record as accepted without being shown in full (FR-015).
- Q: What is the developer shown before the one reply that re-signs an approval older than section-level records, on a changed document? → A: Only a statement that the document changed since an approval the tool cannot compare; the reply is recorded as given on that statement (FR-025).
- Q: When does the current git branch count as named for a different story, so that a start is refused until confirmed? → A: Whenever it is any branch other than the project's main branch, unless its name matches the new story (FR-006).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Every change lands on the intended story (Priority: P1)

A developer finishes story 001 and starts story 002. Today the project keeps pointing at 001, so the next helper call that does not name a story silently rewrites 001's approved records, and the developer has to name the story on about a hundred later calls. Instead, starting a story makes it the active one; every call that changes a record says which story it changed; and when the intended story cannot be told for certain, the call is refused with the one step that resolves it, before anything is written.

**Why this priority**: This is the only friction in the run that damaged an approved record. Every other improvement is about effort; this one is about integrity.

**Independent Test**: In a project with a completed story 001 and the pointer still on it, start story 002. Verify the pointer names 002, a mutating call without a target changes only 002 and names it, and a mutating call made in an ambiguous situation is refused with nothing written to either story.

**Acceptance Scenarios**:

1. **Given** a project whose active-story pointer names story 001, **When** a new story 002 is started, **Then** the pointer names 002 and the start reports that it moved, naming both stories.
2. **Given** any call that writes a record, **When** it completes, **Then** its output names the story it wrote to.
3. **Given** a pointer naming a story whose completion is approved while another story in the project is in progress, **When** a call that writes a record is made with no explicit story, **Then** it is refused, nothing is written, and the refusal names both stories and the way to choose one.
4. **Given** the same situation, **When** a read-only call (status, show, trace) is made, **Then** it proceeds and names the story it read.
5. **Given** a new story started while the current git branch is neither the main branch nor named for the new story (for example `001-rich-spec-viewer` when starting 002), **When** the start completes, **Then** the start is refused, naming the branch, until the developer switches branch or confirms in one reply that the story belongs on this branch; the confirmation is recorded with their name.

---

### User Story 2 - Stage documents hold content, not bookkeeping (Priority: P1)

A developer or agent opens a stage document to read it. Today 58% to 87% of each document is the machine record (84 KB of a 97 KB task list), so reading one document fills the agent's context and the developer scrolls past hashes to find the text. Instead, the record lives beside the documents in the story directory, each document carries only its content, a short readable approval line and its Change Log, and a `show` command prints a clean view of any stage in chat.

**Why this priority**: Context exhaustion caused five compactions, and each compaction lost working state (including in-progress review tallies), which caused repeated questions. It multiplies the cost of every other step.

**Independent Test**: Migrate the trial story's documents. Verify that every approval and review recorded before the migration is still valid afterwards, that no stage document contains block hashes, classifications or assessment details, and that `show` for each stage prints its content with its open review cues and nothing else.

**Acceptance Scenarios**:

1. **Given** a story whose stage documents carry their records inline, **When** the upgrade runs, **Then** the records move to the story's record file, every approval, review and judgment stays valid, and nobody is asked anything.
2. **Given** an approved stage, **When** its document is opened, **Then** it shows who approved it, when and how the approval was reached in one readable line, with no hashes.
3. **Given** any stage, **When** the developer or the agent asks to see it, **Then** `show` prints its content in chat, optionally limited to named items, without the record.
4. **Given** a record file deleted or edited by hand, **When** status is computed, **Then** the affected approvals are reported as unverifiable, exactly as a tampered inline record is today, never silently treated as valid.

---

### User Story 3 - Reviews are sized to the list (Priority: P1)

A developer is shown the inferred content of a stage. Today every list is one long message, the agent keeps a running tally of partial answers in the chat (which a compaction can lose), restated and adopted blocks are listed beside new ones, and every Actors or Dependencies line is its own entry. Instead, the helper picks the presentation from the list's size: a few items are walked one at a time in chat; many are shown as a grouped summary answered with one reply ("ok", or "ok except X"). Partial answers are stored by the helper as they are given. Restated and adopted blocks are never listed, and scaffolding sections are one line each.

**Why this priority**: The 38-block review in the trial was the longest single interaction, and lost tallies caused repeated asks.

**Independent Test**: Produce one list of 5 entries and one of 38. Verify the first is presented one at a time and the second as a grouped summary; that answering 3 of the 5 and then resetting the conversation leaves 2 unanswered entries; and that no restated, adopted or individual scaffolding block appears in either.

**Acceptance Scenarios**:

1. **Given** a review list of at most the configured threshold (default 8) entries, **When** it is presented, **Then** each entry is shown in chat with its full text, one at a time, and answered on its own.
2. **Given** a review list longer than the threshold, **When** it is presented, **Then** entries are grouped by section, each with a one-line summary and why it needs review, and the developer answers the whole list in one reply; the full text of any entry, group or the whole list is shown in chat on request.
3. **Given** a one-at-a-time list with 2 of 5 entries answered, **When** the developer replies "ok to the rest", **Then** the other 3 are accepted in that reply and each is recorded as accepted without being shown in full.
4. **Given** a one-at-a-time list with 3 of 5 entries answered, **When** the conversation is compacted or restarted, **Then** the helper still holds the 3 answers and the list resumes at the 4th.
5. **Given** a stage with 12 Actors, Dependencies, Not applicable, Inputs or Outputs blocks, **When** its list is built, **Then** each of those sections is one entry.
6. **Given** blocks classified restated, or adopted as reviewed by an earlier approval, **When** any review list is built, **Then** none of them appears.

---

### User Story 4 - A small story takes a short path, authorised once (Priority: P2)

A developer brings a detailed request for a small change. Today the only shortening is per-stage abbreviation, which the agent is forbidden to suggest, so nobody uses it. Instead, at the start the agent may propose the small-story profile, naming the signals it saw (labelled as its judgement); the developer authorises it once, with their name and reason; and the story then skips wireframe exports, reviews the AI Specification, plan and tasks as one list, and takes a shorter comprehension check (two levels). Every gate and approval still applies.

**Why this priority**: The largest single lever on overhead for small stories, but it depends on the review and record changes above to be worth taking.

**Independent Test**: Start a story, accept the proposed profile with a name and reason, and run it to implementation. Verify the authorisation is recorded and shown in the overview and every gate it affects; no wireframe export is requested; one review list covers the AI Specification, plan and tasks; the comprehension check asks the shortened set; and every approval is still required.

**Acceptance Scenarios**:

1. **Given** a new story whose request is detailed or whose change is small, **When** the story starts, **Then** the agent may propose the profile, listing the signals it saw and labelling the proposal as its own.
2. **Given** a proposal, **When** the developer authorises it with their name and reason, **Then** the profile is recorded with both and shown in the overview, at every gate it affects and in the trace report.
3. **Given** a proposal, **When** the developer declines it or says nothing, **Then** the story follows the full workflow and nothing is recorded as authorised.
4. **Given** a profiled story at the Functional stage, **When** its gate is checked, **Then** the wireframe criterion is met by the recorded authorisation, shown as such, and no export is asked for.
5. **Given** a profiled story whose tasks are generated, **When** review is requested, **Then** the inferred content of the AI Specification, plan and tasks is one list, and implementation is refused until it is answered; planning and task generation proceeded under the override recorded with the profile, which is shown as an override.
6. **Given** a profiled story, **When** a stage is to be approved, **Then** approval is required exactly as in the full workflow.
7. **Given** a profiled story that turns out larger than proposed, **When** the agent notices, **Then** it says so; the developer may withdraw the profile, which restores the full requirements for every stage not yet approved.

---

### User Story 5 - The developer is asked about behaviour, not mechanism (Priority: P2)

During the Functional and Technical stages of the trial, the developer was asked about sort keys, alias detection rules, test layout and caching. Instead, a choice that does not change what a user of the system observes is made by the agent, recorded as a decision marked `ai-decided` with its reason, and shown in the stage summary. Only choices that change observable behaviour, scope or a trade-off are asked, each with a recommended option. The developer's approval still covers the whole document, and any `ai-decided` decision can be turned into a question.

**Why this priority**: Mis-aimed questions cost time and train the developer to answer without thinking, which empties the decisions that matter.

**Independent Test**: Draft a Technical Specification needing one observable choice and two non-observable ones. Verify one question is asked with a recommended option, two decisions are recorded as `ai-decided` with reasons and listed in the summary, and approval of the document is still required.

**Acceptance Scenarios**:

1. **Given** a choice that changes what a user observes, the scope, or a trade-off, **When** it arises, **Then** the developer is asked, with the options and a recommended one.
2. **Given** a choice that changes none of those, **When** it arises, **Then** the agent decides it, records it as an `ai-decided` decision with its reason, names it in the stage summary, and includes it, as its own group, in the stage's review list.
3. **Given** an `ai-decided` decision, **When** the developer asks to decide it themselves, **Then** it becomes an ordinary question, and their answer is recorded as their decision.
4. **Given** a stage with `ai-decided` decisions, **When** it is approved, **Then** the approval record lists them as covered by the approval.

---

### User Story 6 - The comprehension check respects what the developer already knows (Priority: P2)

In the trial the comprehension check asked about mechanism rather than behaviour, withheld the item text from a developer working remotely, asked about items the same developer had just decided, required one skip per level to opt out, and called one correct answer wrong. Instead, questions target behaviour; the item text is shown before each question; the developer's own recent decisions are not asked; one reply with a reason waives the remaining levels; and answers are judged on meaning, re-read before any hint.

**Why this priority**: The check guards the approval; a check that feels arbitrary is skipped, which defeats it.

**Independent Test**: Run the check on a stage where one target item is the developer's own recorded decision. Verify that item is not asked and is recorded as `own-decision`; every question shows its item first and asks about behaviour; and one waiver records every remaining level as skipped with the name and reason.

**Acceptance Scenarios**:

1. **Given** any comprehension question, **When** it is asked, **Then** the item it concerns is shown in chat first, and the question is about what the system does, not how it is built.
2. **Given** a target item that the person taking the check decided, at its current content, **When** the check runs, **Then** it is not asked and is recorded as `own-decision`, naming the decision.
3. **Given** a check in progress, **When** the developer says they waive the rest, with a reason, **Then** every remaining level is recorded as skipped with their name and that reason, in one step.
4. **Given** an answer the agent first judges wrong, **When** it is about to give a hint, **Then** it re-reads the answer against the item, and if the answer could be right in meaning, accepts it or asks the developer to expand instead of hinting.

---

### User Story 7 - An upgrade adopts approved work without re-asking (Priority: P2)

When the trial project upgraded to 002, already-approved stages were re-tagged `[ai-draft]`, `unreviewed-ai-content` fired on text the developer had approved, recorded judgments were dropped, and `accept` refused an older approval with a pointer to a full re-approval. Instead, unchanged content of an approved stage is adopted as reviewed by that approval, with no tag and no question; judgments on unchanged text are kept; and where an old approval cannot be compared section by section, `accept` names the one reply that re-signs it.

**Why this priority**: Every installed user meets this on upgrade, but only once per story.

**Independent Test**: Upgrade a fixture story with one approved, unchanged stage and one approved stage changed in one section. Verify the first needs nothing, and the second presents only the changed section's blocks.

**Acceptance Scenarios**:

1. **Given** an approved stage unchanged since approval, **When** an upgrade adopts it, **Then** every block is recorded as reviewed by that approval, no `[ai-draft]` tag is added, and no `unreviewed-ai-content` finding is raised.
2. **Given** an approved stage with recorded judgments, **When** an upgrade adopts it, **Then** the judgments for unchanged text are kept.
3. **Given** an approved stage changed in one section since approval, with section-level fingerprints, **When** an upgrade adopts it, **Then** blocks in unchanged sections are adopted and only the changed section's blocks go to change acceptance.
4. **Given** an approval that predates section-level fingerprints, on a document changed since, **When** `accept` is run, **Then** it states that the document changed since an approval it cannot compare, names the single reply that re-signs the stage, and records it when given, marked as given without a comparison, instead of refusing.

---

### User Story 8 - Gaps are found while drafting, not after review (Priority: P3)

In the trial, the comprehension pre-scan found two gaps after a 38-block review had been answered, which sent two requirements back into review. Instead, the drafting pass runs the same targeted gap checks before the first review list is shown.

**Why this priority**: Saves a second review round when it applies; lower frequency than the items above.

**Independent Test**: Seed a stage with a gap in an item the comprehension check would target. Verify the gap is raised as a challenge during drafting, before any review list, and the later pre-scan raises nothing new on that item.

**Acceptance Scenarios**:

1. **Given** a drafted stage, **When** its first review list is about to be shown, **Then** the gap checks the comprehension pre-scan uses have already run over the items it would target, and any gaps are raised as challenges first.

---

### User Story 9 - The helper does not get in its own way (Priority: P3)

The trial hit several small defects: the helper's own Change Log and Record headings tripped `plan-not-derivable`, so the agent patched them with a false trace; the helper's `[ai-draft]` tag broke the agent's text-match edits; classifying some blocks discarded earlier classifications, and block ids changed when text changed; the agent retried `challenge add` four times for a missing severity; and status said "Continue verification" after completion was approved. Each is fixed.

**Why this priority**: Each is small, but together they caused retries, false records and confusion.

**Independent Test**: One scenario per defect, each reproducing the trial's failure and showing it no longer occurs.

**Acceptance Scenarios**:

1. **Given** a plan with the helper's Change Log and Record headings, **When** its gate is checked, **Then** neither is reported as not derivable.
2. **Given** a paragraph the helper has tagged `[ai-draft]`, **When** the agent edits it by matching the text it wrote, **Then** the edit applies.
3. **Given** blocks already classified, **When** a classification of other blocks is submitted, **Then** the earlier classifications remain.
4. **Given** a numbered item whose text changes, **When** it is classified or reviewed again, **Then** it keeps its id.
5. **Given** an approved completion, **When** status is shown, **Then** it reports the story as complete and names no next step.
6. **Given** an AI Specification, plan or task list whose inferred content is all reviewed and none stale, **When** status is shown, **Then** that stage is shown as reviewed.

---

### User Story 10 - Approving takes one word (Priority: P2)

In the trial, approving a stage meant writing a sentence of confirmation, because the prompt asked for the confirmation "in their own words" and showed full-sentence examples, and it asked for the developer's name each time. Instead, the approval question states exactly what is being confirmed, a reply of "ok", "yes" or "approved" approves, and the name is asked once per session.

**Why this priority**: Approvals happen at every definition stage; a written attestation of something the question already states adds effort without assurance.

**Independent Test**: Approve a stage replying "ok" to the helper's approval question. Verify the approval is recorded with "ok" verbatim, the question it answered and the developer's name, and that a later approval in the same session does not ask the name again.

**Acceptance Scenarios**:

1. **Given** a stage ready for approval, **When** the AI asks for approval, **Then** it asks the helper's approval question for that stage, which states what is being confirmed, and nothing more.
2. **Given** that question, **When** the developer replies "ok", **Then** the stage is approved, and the record holds "ok" verbatim, the question, the developer's name and the time.
3. **Given** an approval already given in this session, **When** another stage is approved, **Then** the developer's name is not asked again.
4. **Given** no reply, or an instruction to "just approve it" without answering the question, **When** approval is requested, **Then** nothing is recorded and the question is asked again.

---

### Edge Cases

- A start outside a git repository, or with no branch checked out: nothing to compare, so FR-006 does not refuse; the start names the situation.
- A start on a branch already named for the new story (for example one the git extension created): proceeds without a question.
- A project with one story and no pointer: that story is the target; nothing is ambiguous.
- A pointer naming a directory that no longer exists: mutating calls are refused as ambiguous; read-only calls report the missing directory.
- An explicit story given on the call (argument or environment): always the target, never ambiguous, and still named in the output.
- A deliberate change to a completed story (a code-review finding after completion, 002 FR-027): permitted when the story is named explicitly.
- A profile proposed after the first stage has been approved: allowed; it applies only to stages not yet approved, and approved stages are not reopened by it.
- A profile authorised by someone not configured to authorise abbreviations: refused, as an abbreviation by them is today.
- A review list whose length crosses the threshold while being answered (an exception reworks entries back in): the mode fixed when its first answer was recorded holds until the list is closed.
- A one-at-a-time list where two people answer the same entry differently: a conflict, as 002 FR-050.
- An `ai-decided` decision that later turns out to change observable behaviour: raised as a challenge, and the decision becomes the developer's to make.
- A comprehension target decided by a different person from the one taking the check: asked as normal.
- A waiver given before any level is asked: every level is recorded as skipped; the approval still requires the check to be recorded, which the waiver satisfies.
- An upgrade on a stage whose document no longer matches any recorded fingerprint and has no section fingerprints: no block is adopted; the stage goes to `accept` as in User Story 7 scenario 4.
- A record file present for some stages and inline records for others (a partial migration): status reads both, and the next write completes the migration for that stage.

## Requirements *(mandatory)*

### Functional Requirements

**Story targeting (Story 1, change 8)**

- **FR-001**: Starting a story, through Spec Kit's specify command or through the extension's own start, MUST set the project's active-story pointer to the new story, replacing any previous value, and MUST report the change, naming the previous and the new story.
- **FR-002**: Every call that writes a record MUST name, in its output, the story it wrote to.
- **FR-003**: A call that writes a record MUST be refused, with nothing written, when its target story is ambiguous: no story is named explicitly, and either the pointer is missing while the project has more than one story, the pointer names a directory that does not exist, or the pointer names a story whose completion is approved while another story in the project is not complete. The refusal MUST name the candidate stories and how to choose one.
- **FR-004**: Read-only calls MUST NOT be refused for ambiguity; they MUST name the story they read.
- **FR-005**: The stage commands MUST NOT start a new story in a directory taken from the pointer when that directory already holds a governed story.
- **FR-006**: When a story is started while the current git branch is neither the project's main branch (configurable; by default `main` or `master`) nor named for the new story (its name equals the new story's directory name or starts with its number prefix), the start MUST be refused, naming the branch, until the developer either switches branch or confirms with one reply that the new story is to be written on this branch. The confirmation MUST be recorded with their name. The helper MUST NOT create or switch branches.

**Records out of the documents (Story 2, change 7)**

- **FR-007**: Block hashes, provenance classes, review records, source versions and gate assessment details MUST be kept in one record file per story, in the story's directory, and MUST NOT appear in any stage document.
- **FR-008**: Each approved stage document MUST keep one readable line per approval or override: who, when, and how the approval was reached (first approval, carried forward, or reviewed change by change), so a reader of the document alone still sees it (Principle II). Its full record is in the record file.
- **FR-009**: Fingerprints MUST be computed over the same content as before this feature, so that moving records out of a document invalidates no approval, review or judgment.
- **FR-010**: The first run after upgrade MUST move existing inline records to the record file without asking anyone and without changing any approval's standing.
- **FR-011**: A record file that is missing, unreadable or inconsistent with the documents MUST be reported as unverifiable for each approval it affects, never treated as valid; Principle II's attestation-level limits apply to the record file as they did to inline records.
- **FR-012**: A `show` command MUST print any stage's content in chat, optionally limited to named items, without its record, and with its open review cues. The stage commands MUST use it rather than reading a whole document.
- **FR-013**: Removing the extension MUST leave the record file in place, as it leaves every document.

**Review list modes (Story 3, change 3)**

- **FR-014**: The helper MUST choose a review list's presentation from its length: one at a time when it has at most the configured threshold of entries, a grouped summary when it has more. The threshold MUST be configurable and default to 8. The mode MUST be fixed when the list's first answer is recorded, and recorded with every answer.
- **FR-015**: In one-at-a-time mode each entry MUST be shown with its full text and answered on its own, except that the developer MAY end the list with one reply accepting every remaining entry ("ok to the rest"); each entry so accepted MUST be marked in the record as accepted without being shown in full. In summary mode entries MUST be grouped by section, each with a one-line summary and the reason it needs review, answerable in one reply as 002 FR-017; the full text of any entry, group or the whole list MUST be available in chat on request. This amends 002 FR-010, which showed every entry's full text in every list.
- **FR-016**: The helper MUST store each per-entry answer as it is given, with the answerer's name, so that a list can be resumed after the conversation is compacted or restarted, presenting only unanswered entries. The prompts MUST NOT keep a tally of answers in chat.
- **FR-017**: A review list MUST NOT include a block classified restated or adopted as reviewed by an approval (FR-023).
- **FR-018**: The blocks of each Actors, Dependencies, Not applicable, Inputs and Outputs section MUST be one entry per section.

**Small-story profile (Story 4, change 1)**

- **FR-019**: The agent MAY propose the small-story profile when a story starts, or later for stages not yet approved, naming the signals it saw (for example a detailed request, few requirements, a change touching few components) and labelling the proposal as its own judgement. The prompt rule that forbids the agent to suggest abbreviation MUST be replaced by this rule; the agent still MUST NOT authorise.
- **FR-020**: The profile MUST be authorised once per story by a person allowed to authorise abbreviations, with their name and reason, recorded and shown in the overview, at every gate it affects and in the trace report. Withdrawal MUST be recorded the same way and restores the full requirements for every stage not yet approved.
- **FR-021**: Under the profile: the wireframe criterion of the Functional gate MUST be met by the recorded authorisation, shown as such; the inferred content of the AI Specification, plan and tasks MUST be reviewed as one list after tasks are generated, and implementation MUST be refused until that list is answered; the comprehension check MUST ask two levels, chosen by the helper by a fixed formula, about behaviour items; the other three levels MUST be recorded as `not-applicable` with the profile as the reason.
- **FR-022**: Under the profile every approval, gate, challenge rule and override is unchanged, except (a) the wireframe criterion of FR-021 and (b) entry to planning and task generation, which proceeds past unreviewed inferred content in the AI Specification and plan. (b) MUST be recorded, when the profile is authorised, as a named, reasoned override of `unreviewed-ai-content` for those two entries, citing the profile and shown wherever overrides are shown; withdrawing the profile withdraws it. Entry to implementation is not overridden.

**Upgrade migration (Story 7, change 2)**

- **FR-023**: When an upgrade adopts an approved stage, every block whose content is unchanged since that approval (by the whole-document fingerprint, or by the section fingerprint of its section) MUST be recorded as reviewed by that approval, MUST NOT be tagged `[ai-draft]`, and MUST NOT raise `unreviewed-ai-content`. This strengthens 002 FR-047, whose adoption the trial showed did not take effect.
- **FR-024**: Recorded judgments MUST be kept on upgrade for every section whose text is unchanged.
- **FR-025**: When `accept` meets an approval with no section-level fingerprints on a document changed since, it MUST state that the document changed since an approval the tool cannot compare section by section, name the single reply that re-signs the stage, and record that reply when given, instead of refusing. The re-signed approval MUST be marked, wherever approvals are shown, as given without a comparison (Principle II).

**Implementation decisions (Story 5, change 4)**

- **FR-026**: The Functional and Technical stage commands MUST ask the developer only about choices that change what a user of the system observes, the scope, or a trade-off, each with the options and a recommended one.
- **FR-027**: A choice that changes none of those MUST be decided by the agent and recorded as a decision marked `ai-decided`, with its reason, labelled as the agent's, and named in the stage summary. `ai-decided` decisions MUST appear in the stage's review list of inferred content as their own group, answered by the same one reply as the rest of the list. In the Functional stage such a choice is not part of the behaviour and MUST be left to the Technical stage, where it is recorded.
- **FR-028**: The helper MUST require every `ai-decided` decision to carry a reason, and every approval of a stage containing them MUST list them as covered by the approval.
- **FR-029**: The developer MUST be able to turn any `ai-decided` decision into a question, after which it is decided and owned by them as any other decision.

**Comprehension check (Story 6, change 5)**

- **FR-030**: Comprehension questions MUST be about behaviour (what the system does or what a user observes), not mechanism.
- **FR-031**: Each question MUST be preceded, in chat, by the text of the item it concerns.
- **FR-032**: A target item whose content is a recorded decision by the person taking the check, at its current content, MUST NOT be asked, and MUST be recorded with the distinct outcome `own-decision`, naming the decision, so a reviewer can see the level was not asked; the helper picks the next eligible item for that level where one exists. The helper determines this from the records, not the agent.
- **FR-033**: The person taking the check MUST be able to waive all remaining levels in one reply with a reason; the helper MUST record each as skipped with their name and reason.
- **FR-034**: The agent MUST judge answers on meaning and, before giving a hint after judging an answer wrong, re-read the answer against the item; where the answer could be right in meaning, it MUST accept it or ask the person to expand rather than hint.

**Gaps found while drafting (Story 8, change 6)**

- **FR-035**: Before a stage's first review list is shown, the drafting pass MUST run the gap checks the comprehension pre-scan uses (silent, ambiguous, self-contradicting) over the items the comprehension check would target for the current version, and raise any gap as a challenge first.

**Smaller defects (Story 9, change 9)**

- **FR-036**: The headings the helper writes itself (Change Log, Record) MUST NOT be reported as not derivable in the plan.
- **FR-037**: An edit the agent makes by matching text it wrote MUST succeed whether or not the helper has since tagged that text `[ai-draft]`.
- **FR-038**: Submitting a classification for some blocks MUST NOT remove the classifications of others, and a numbered item MUST keep its block id when its text changes.
- **FR-039**: The prompts that raise challenges MUST state that a severity is required.
- **FR-040**: After completion is approved, status MUST report the story as complete and name no next step. The AI Specification, plan, task list and verification record MUST have a terminal "reviewed" state, reached when all their inferred content is reviewed and none is stale.

**Short approvals (Story 10, change 10)**

- **FR-047**: The helper MUST provide, for each approvable stage, a fixed approval question stating what is being confirmed (for example "Approve the Functional Specification as the behaviour you require?"), and every approval MUST record the question it answered together with the reply. Every other confirmation the helper records MUST likewise record what it answered: a review list by its digest and entries, and the branch confirmation (FR-006) and comprehension waiver (FR-033) by a fixed helper question.
- **FR-048**: A reply of "ok", "yes", "approved" or any other non-empty reply to that question MUST be accepted as a complete approval and recorded verbatim. The prompts MUST NOT ask for a longer statement or show full-sentence examples as required wording.
- **FR-049**: The confirming person's name MUST be asked at most once per session and reused for every later confirmation in that session unless the person names someone else. The AI MUST NOT supply the reply, and silence or an instruction to approve without answering the question MUST NOT count as one.

**Evidence, tests and records**

- **FR-041**: `docs/trials.md` MUST record the 2026-10-01 run as the first SC-010 data point: 143 minutes total, 138 minutes of process, about 96% overhead; 128 lines of code, about 420 lines of tests, about 5,800 lines of stage documents.
- **FR-042**: Each change (1 to 10) MUST have a CHANGELOG entry naming the human interactions it adds or removes, with their purpose.
- **FR-043**: Every prompt rule this feature adds or changes MUST have a prompt contract test, and a probe in `docs/trials.md` where following it cannot be checked from files. The upgrade migration (FR-023 to FR-025) and the ambiguous-target refusal (FR-003) MUST each have scenario tests.

**Preserved guarantees**

- **FR-044**: No gate, approval, attestation or recorded override becomes weaker. Every waiver, skip, profile and `ai-decided` decision introduced here MUST be recorded with a name (a person's, or the agent's label) and a reason, and shown wherever the gate or approval it affects is shown.
- **FR-045**: The agent MUST NOT authorise the profile, waive a comprehension level, record an approval, answer a review list or decide a choice that changes observable behaviour, scope or a trade-off.
- **FR-046**: Every rule here that decides whether an action proceeds or writes a record MUST be deterministic helper behaviour (Constitution Principle I): story targeting, list mode, stored answers, adoption on upgrade, the profile's effects, the `ai-decided` reason check, own-decision exclusion and the waiver.

### Human interactions added and removed (Constitution Principle IV)

| Change | Interaction | Added or removed | Purpose |
|---|---|---|---|
| 1 Profile | Authorise the small-story profile once, with a reason | Added (one reply per story) | Decision |
| 1 Profile | Wireframe exports | Removed under the profile | (was validation) |
| 1 Profile | Separate inferred-content reviews of AI Specification, plan and tasks | Three lists become one | Validation |
| 2 Migration | Re-review of unchanged approved blocks after upgrade | Removed | (was validation; already approved) |
| 2 Migration | Full re-approval of an older approval | Replaced by one named reply | Approval |
| 3 Lists | Restated and adopted blocks listed for review | Removed | (was awareness; already settled) |
| 3 Lists | Each scaffolding block as its own entry | One entry per section | Validation |
| 4 Decisions | Questions about implementation mechanism | Removed; reviewed as a group in the existing one-reply list instead | Validation (was decision) |
| 4 Decisions | Questions about behaviour, scope and trade-offs | Unchanged, now with a recommended option | Decision |
| 5 Comprehension | Questions about the person's own current decisions | Removed | (was understanding) |
| 5 Comprehension | One skip per level to opt out | One waiver with a reason | Decision |
| 6 Gaps | Second review round after late gaps | Removed where the drafting pass finds them | (was validation) |
| 8 Targeting | Choose the story when the target is ambiguous | Added (only when ambiguous) | Decision |
| 8 Targeting | Naming the story on every call | Removed | (was repetition) |
| 10 Approvals | Writing a sentence of attestation | Replaced by a one-word reply to a stated question | Approval |
| 10 Approvals | Giving one's name at every approval | Asked once per session | (was repetition) |
| 8 Targeting | Starting a story on an unexpected branch | Added (one reply, only when not on the main branch or a branch named for the new story) | Decision |

### Key Entities

- **Active-story pointer**: The project's record of which story calls without an explicit target act on; set when a story starts.
- **Record file**: One per story, beside its documents: block hashes, provenance, review records and answers, source versions, assessment details and the full approval records. Not a stage document.
- **Small-story profile**: A per-story authorisation (who, why, when, withdrawn or not) that shortens the path as FR-021 states without changing any approval.
- **Review list mode**: One-at-a-time or summary, fixed for a list when first presented, recorded with its answers.
- **`ai-decided` decision**: A decision on a choice with no observable effect, made and labelled by the agent with its reason, covered by the stage approval, convertible to a developer decision.
- **Comprehension waiver**: One recorded reply that records every remaining level as skipped, with the person's name and reason.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Across the scenario suite, 0 record changes land on a story other than the one intended, and 100% of record-writing calls name the story they wrote to.
- **SC-002**: After migration, no stage document of the trial story contains block hashes, provenance or assessment details, its task list is at least 75% smaller than the 97 KB it was, and 100% of its approvals and reviews remain valid.
- **SC-003**: A story of comparable size to the trial's story 002, run under the profile, takes at most 55 minutes of process time (a 60% cut from 138), recorded in `docs/trials.md` against SC-010.
- **SC-004**: In that run the developer is asked 0 questions about implementation mechanism, and the agent's context needs no compaction before implementation starts.
- **SC-005**: In the reference story scenario fixture, the number of developer replies from requirements to implementation falls by at least 50% compared with 002, while the number of approvals and of decisions on observable behaviour is unchanged.
- **SC-006**: After an upgrade, 0 blocks of an unchanged approved stage are tagged or listed for review, in scenario tests.
- **SC-007**: In the comprehension probes, 0 correct answers are called wrong and 0 questions are asked about the person's own current decisions.
- **SC-008**: Every gate refusal in the 001 and 002 scenario suites still refuses the same input, and 100% of waivers, skips, profiles and `ai-decided` decisions carry a name and a reason.

## Assumptions

- The constraints of 001 and 002 remain binding except where this specification amends them, and each amendment is named: 002 FR-010 (full text in every list, FR-015), 002 FR-047 (adoption, FR-023), 002 FR-046 (the `[ai-draft]` cue appeared in document text; it now appears only in `show` and review lists, FR-037), 002 FR-036 (the AI makes no technical decision; narrowed to choices with an observable effect, since each `ai-decided` decision is settled by a person's reply on the review list, FR-027), 002 FR-038 (the full five-level comprehension check at first approval, which the small-story profile shortens to two levels, FR-021), and 002's assumption that new records live inside existing documents (FR-007). 001's "nine documents" constraint is kept: the record file is a record, not a document, as the assets directory is.
- `ai-decided` decisions are compliant with Principle IV's "MUST NOT let the AI make [a human decision]" because a choice with no observable effect, scope or trade-off is not a human decision under this definition, the agent's decision is labelled as its own (Principle II), and the developer's approval of the document covers it. The Technical Specification prompt's "a technical decision is the developer's, never yours" and the `developer-choice-recorded` probe are narrowed to decisions with observable effect. Whether this needs a PATCH clarification of the constitution is raised at `/speckit-analyze`.
- Whether a choice changes what a user observes is the agent's judgement, labelled as such. It errs toward asking: when unsure, it asks.
- A summary-mode review is the developer's validation of summaries plus whatever they ask to see; the recorded mode makes that visible to a later reader (Principle II).
- The comprehension check's "same session" is defined by the records, not by conversation state: an item is the person's own decision when it carries their recorded decision at its current content. The helper cannot know conversation sessions.
- The threshold default of 8 is a starting point, to be revisited after trials.
- SC-003 and SC-004 depend on a human trial; SC-010's 25% target is not expected to be met by a five-minute implementation and remains the long-term target.
- Branch creation stays with Spec Kit's git extension; this feature does not create branches.
- FR-048 relies on Constitution Principle II (1.2.2): a short reply to an explicit approval question is an ordinary confirmation; the "short acknowledgement ... when, and only when" clause governs confirmations given without a fresh question (carry-forward). The amendment was applied on 2026-10-02 with `/speckit-constitution`.
