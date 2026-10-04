# Feature Specification: Browser Review Page

**Feature Branch**: `004-browser-review-page`

**Created**: 2026-10-04

**Status**: Draft

**Input**: User description: "Review the documents as a developer using the web view of the .md files. Particularly for the requirements, functional and technical specifications, the developer is guided to open the current document to review, then uses checkboxes to approve or add comments to each block." Scope agreed in conversation on 2026-10-04: a review page served by the extension's own helper, reusing the reading experience of the rich specification viewer (`/home/lee/projects/rich-specification-viewer`), with every answer recorded through the helper's review sessions. Constitution amended to 1.3.0 for it the same day.

## Context

Today a developer reviews a stage in chat. The agent prints the blocks that need review (one at a time for short lists, as grouped summaries for long ones, 003 FR-014), and the developer replies in words. That works, but the developer reads the document through the agent's rendering of it, a summary at a time. They do not see it as a document, with its sections around each block, and they cannot follow a reference code to its definition.

The rich specification viewer already shows a story's documents well: rendered Markdown, a hover preview of the section that defines each reference code, diagrams, and a reading order. It is read-only by design.

This feature adds a **review page** to the extension. The stage command tells the developer to open the current document in the browser. The page shows the whole document and marks the blocks the helper lists for review. The developer accepts each one, sends it back with a comment, or asks a question about it, and then returns to the chat. Each answer is stored by the helper as it is given, in the same review session a chat answer uses (003 FR-016). The record is therefore the same whichever surface the person used, and the agent picks the answers up from the helper.

The governing test is unchanged: *every request for a person's attention must earn its place, and no gate, approval, attestation or recorded override gets weaker* (Principles II and IV). Constitution 1.3.0 sets the limits this feature works within:
- the browser decides nothing and writes no record (Principle I);
- a page answer is a human confirmation, recorded with the helper's fixed question, and its identity limit is stated (Principle II);
- the page offers an answer only on what the helper lists for review (Principle IV);
- diagrams are drawn by the browser only when the project opts in, and a page that can cause a record is protected by a per-session token and an origin check (Constraints of Record).

## Clarifications

### Session 2026-10-04

- Q: Which blocks get an answer control? → A: Only the blocks the helper lists for review. Restated and adopted blocks are shown as settled (constitution 1.3.0, Principle IV).
- Q: How are diagrams shown? → A: As source, unless the project's configuration names one browser diagram script. Then the browser loads it and the page says which script it loads and from where (constitution 1.3.0, Constraints of Record).
- Q: What does a comment on a block that is not on the review list do? → A: It reopens the block, sending it back to review with the comment (FR-016).
- Q: Where is the stage approved? → A: In chat only, after the review and, for Functional and Technical, the comprehension check. The page offers no approval (FR-020).
- Q: How is the review surface chosen? → A: The agent asks the person once per session, page or chat, and uses that answer for every later review in the session (FR-021).
- Q: Should one review page run for the whole session and show whichever stage is up for review, or should each review start its own page? → A: One page per story for the session. It shows the current stage's review list, each new review is a reload, and it stops when the session ends or after a period with no use (FR-001).
- Q: When someone answers on the review page, whose name should the answer be recorded under? → A: The name the person gave in chat, passed by the agent when it starts the page; the page shows "Answering as <name>" with a way to change it, and asks no extra question (FR-012).
- Q: When the document or the stored answers change while the review page is open, should the page update itself or wait for a reload? → A: The page checks every few seconds and shows a notice naming what changed, with a reload button; nothing on the page changes until the person reloads (FR-009).
- Q: After the person questions a block on the page and the agent answers in chat, where does the person give their final answer on it? → A: On the page: the agent answers in chat, reworking the block if needed, then asks the person to reload and answer that block there (FR-015).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Review a stage's blocks in the browser (Priority: P1)

The agent finishes drafting the Functional Specification and its gap scan. Instead of printing the list in chat, it says: "Open the review page for the Functional Specification: <address>. Answer each highlighted block, then say done here." The developer opens it and sees the whole document rendered, with the blocks that need review highlighted and a counter of how many remain. On each one they choose accept, send back (with a comment saying what is wrong) or question (with their question). Each choice is stored as soon as it is made. When the counter reaches zero the page says the list is complete and asks them to return to the chat.

**Why this priority**: This is the feature. Every other story extends it.

**Independent Test**: On a story with a Functional Specification holding five blocks that need review, open the page, accept three, send one back with a comment and question one. Verify that the helper holds five stored answers with the developer's name, the time, the fixed question for each entry and the comments verbatim, and that the list is recorded as answered exactly as if the same answers had been given in chat.

**Acceptance Scenarios**:

1. **Given** a stage with blocks that need review and a person who chose the page for this session, **When** the stage command reaches its review step, **Then** it gives the developer the page's address for that stage and tells them to answer there and return to the chat; it does not print the list in chat as well.
2. **Given** no surface chosen yet in this session, **When** the stage command first reaches a review step, **Then** the agent asks the person once whether to review on the page or in chat, and uses the answer for every later review in the session.
3. **Given** the page is open, **When** it is displayed, **Then** the whole document is shown rendered, each block that needs review is highlighted with its fixed question and three answers (accept, send back, question), every other block is shown as settled, and a counter shows how many entries remain.
4. **Given** a highlighted block, **When** the developer accepts it, **Then** the helper stores the answer at once with their name and the time, and the page shows it as answered.
5. **Given** a highlighted block, **When** the developer sends it back or questions it, **Then** the page requires a comment, and the helper stores the answer with the comment verbatim.
6. **Given** every entry answered, **When** the last answer is stored, **Then** the helper records the list as answered through the same path a chat answer takes, and the page says the list is complete and to return to the chat.
7. **Given** a developer who is not configured to confirm the stage, **When** they accept an entry, **Then** the helper refuses it exactly as it would in chat, and the page shows the refusal.

---

### User Story 2 - Return to the chat and act on the answers (Priority: P1)

The developer says "done" in the chat. The agent asks the helper for the list's state, which now returns the stored answers and their comments. Accepted blocks are settled. For each block sent back, the agent shows the comment, reworks the block and says what it changed. For each question, the agent answers in chat or raises a challenge. A reworked block needs review again, and the page shows it as needing review when reloaded.

**Why this priority**: Without this loop, comments on the page reach nobody.

**Independent Test**: After User Story 1's test, ask the helper for the list. Verify that it returns the send-back and the question with their comments and the developer's name, and that after the agent edits the sent-back block, the block is on the list again and highlighted on the reloaded page.

**Acceptance Scenarios**:

1. **Given** answers stored from the page, **When** the agent asks the helper for the list, **Then** the helper returns each stored answer with its disposition, the person's name and the comment, without the agent reading the record file.
2. **Given** a block sent back with a comment, **When** the agent reworks it, **Then** the block's content changes, it needs review again, and the reloaded page highlights it.
3. **Given** a block questioned on the page, **When** the agent has answered the question in chat, **Then** the block is still on the list, and the agent asks the developer to reload the page and answer it there.
4. **Given** a settled block shown on the page, **When** the developer comments on it, **Then** the helper reopens the block with the comment verbatim and the person's name, it is on the review list again, and the agent acts on the comment as on a send-back.
5. **Given** a list half answered on the page, **When** the developer says they want to continue in chat instead (changing the session's surface, FR-021), **Then** the chat continues the same stored session, and no entry is asked twice.

---

### User Story 3 - The page is safe to leave open (Priority: P1)

The page can cause records, so it must not be usable by anything other than the person's own browser session. It must also never record an answer against text the person did not see.

**Why this priority**: A page that writes records without these protections would make a bypass easy, not just possible (constitution 1.3.0).

**Independent Test**: Send state-changing requests to a running page without its token, with a wrong origin and with an outdated entry version. Verify that each is refused and nothing is written. Then change a highlighted block in the document while the page is open, answer it, and verify that the answer is refused and the page shows the new text.

**Acceptance Scenarios**:

1. **Given** a running page, **When** a request that would store an answer arrives without the page's per-session token, or from another origin, **Then** it is refused and nothing is written.
2. **Given** the page is open and a highlighted block changes in the document, **When** the next check runs, **Then** within 5 seconds the page shows a notice naming the changed block with a reload button, and leaves the displayed content as it was.
3. **Given** that notice, **When** the developer answers the changed block without reloading, **Then** the answer is refused as stale, nothing is written, and the page shows the current text to answer again.
4. **Given** the page is started with no address chosen, **When** it listens, **Then** it is reachable only from the same machine. Another address is used only when the person chooses it, for example in a container.
5. **Given** any request for a file, **When** it names something outside the story's documents, **Then** it is refused.

---

### User Story 4 - Diagrams and references on the page (Priority: P2)

A developer reviewing a block that cites `REQ-004` or `DEC-002` wants to read that item without leaving the page. A Functional Specification also holds diagrams.

**Why this priority**: These are what make the page better to read than chat, but a review can be done without them.

**Independent Test**: Open the page for a stage citing items from earlier stages and holding a diagram. Verify that each reference code shows the section that defines it and links to it, that unresolved codes are marked, and that the diagram is shown as source without the opt-in and drawn with it, with its source still shown if it fails.

**Acceptance Scenarios**:

1. **Given** a block citing an item of this or an earlier stage, **When** the developer points at the code, **Then** the page shows the section that defines it, and a click opens that document on the page.
2. **Given** a code with no definition, or more than one, **When** it is displayed, **Then** it is marked as an error.
3. **Given** no diagram script configured, **When** a diagram block is displayed, **Then** its source is shown and nothing is fetched.
4. **Given** a diagram script configured, **When** a diagram block is displayed, **Then** the browser draws it, and the page names the script and where it comes from; a diagram that fails to draw still shows its source.

---

### User Story 5 - Answer a section at once, honestly recorded (Priority: P2)

A long list (for example 38 blocks) has sections in which every block is fine. The developer wants to accept the rest of a section in one action, as "ok to the rest" does in chat.

**Why this priority**: It keeps a long page proportionate (Principle IV). It is secondary to answering block by block.

**Independent Test**: On a 12-entry list, answer two entries of a section individually and accept the rest of that section in one action. Verify that the other entries of that section are stored as accepted, marked as accepted together without being answered one by one, and that entries in other sections are untouched.

**Acceptance Scenarios**:

1. **Given** a section with unanswered highlighted blocks, **When** the developer accepts the rest of the section, **Then** each unanswered block in it is stored as accepted and marked in the record as accepted in one action, not one by one.
2. **Given** that action, **When** an entry in the section was already sent back or questioned, **Then** that answer is unchanged.

---

### User Story 6 - Re-approving a changed stage (Priority: P3)

An approved stage changed. Its changes list (002's revalidation list) is answered before the stage is re-signed. The developer reviews those changes on the page the same way.

**Why this priority**: The same mechanism covers both list kinds, but first reviews are the main use.

**Independent Test**: Change two items of an approved Functional Specification, open the page for its changes list, accept one and send the other back. Verify that the answers are stored and that the re-sign then proceeds or is refused exactly as it would after the same answers in chat.

**Acceptance Scenarios**:

1. **Given** an approved stage with changes, **When** the page is opened for its changes list, **Then** each changed entry is highlighted with what changed, and answered as in User Story 1.
2. **Given** the changes list answered on the page, **When** the stage is re-signed in chat, **Then** the result is the same as after the same answers given in chat.

---

### Edge Cases

- The page is opened for a stage with nothing to review: it shows the document with every block settled and says there is nothing to answer.
- Two browser windows are open on the same list: each answer is stored as given. The later answer from the same person replaces the earlier one, as in chat. An answer from a different person that conflicts is kept as a conflict, as 002 records.
- The developer closes the browser half way: the stored answers remain, and the page resumes at the next unanswered entry.
- The document is edited by hand while the page is open: the page shows a notice naming the changed blocks; an answer to a changed block before reloading is refused as stale (User Story 3).
- The record file is malformed: the page refuses to store answers and says why, exactly as the command line does (003 FR-011).
- The helper is ended while the page is open, or the page stopped after its idle period: the browser says it cannot reach the page, and no answer is lost because none was pending. The agent starts it again at the next review step, with a new address and token.
- The page is reloaded when no review is current (for example during the comprehension check, or after approval): it shows the current stage's document with every block settled and says there is nothing to answer now.
- The story's target is ambiguous (003 FR-003): the page is not started and the refusal is shown in chat.
- A comment is very long or contains Markdown or HTML: it is stored verbatim and displayed as plain text, never as markup.
- The page is used for a stage other than Requirements, Functional or Technical: see FR-019.

## Requirements *(mandatory)*

### Functional Requirements

**Serving the page (Stories 1, 3)**

- **FR-001**: The helper MUST be able to serve one review page per story for a session, and report its address. At any time the page MUST show the review that is current: the stage and list kind the helper reports as awaiting review, with that stage's whole document rendered for reading. A new review is shown on reload, at the same address. The page MUST stop when the person or the agent stops it, or after a configurable period with no request (default 60 minutes); stopping it loses no stored answer.
- **FR-002**: The page MUST mark, with an answer control, exactly the entries on the helper's review list for that stage and kind, and nothing else. Every other block MUST be shown as settled (constitution 1.3.0, Principle IV).
- **FR-003**: Each answer control MUST show the entry's fixed question, worded by the helper (for example "Accept FR-003 as written?"), and three answers: accept, send back and question. Send back and question MUST require a comment.
- **FR-004**: The page MUST show how many entries remain, and say when the list is complete that the person should return to the chat.
- **FR-005**: A page MUST refuse every state-changing request that lacks its per-session token or comes from another origin, MUST serve nothing but the story's documents and the helper's results, and MUST listen only on the same machine unless the person chooses another address.
- **FR-006**: Every value shown on the page that came from a document or a person (block text, comments, names) MUST be displayed as text, never interpreted as markup or script.

**Recording answers (Stories 1, 2, 5)**

- **FR-007**: Each answer given on the page MUST be stored by the helper, at once, in the list's review session, through the same function and under the same refusals as the equivalent chat answer (003 FR-016). The browser MUST NOT decide whether an answer is accepted, and MUST NOT write any record (constitution 1.3.0, Principle I).
- **FR-008**: A page answer MUST be recorded with the person's name, the time, the entry's fixed question, the version of the entry that was shown, its disposition, and any comment verbatim (Principle II).
- **FR-009**: An answer to an entry that has changed since the page showed it MUST be refused as stale, with nothing written, and the page MUST then show the current text. While open, the page MUST check with the helper at least every 5 seconds whether the document, the review list or its stored answers changed, and if so show a notice naming what changed (for example "FR-003 changed") with a reload button. It MUST NOT change the displayed content until the person reloads. These checks MUST NOT count as use for the idle stop of FR-001.
- **FR-010**: When the last entry is answered, the helper MUST record the list as answered through the same path as a chat answer, recording that it was answered on the page.
- **FR-011**: Accepting the rest of a section in one action MUST store each of its unanswered entries as accepted, marked as accepted together rather than one by one, and MUST NOT change entries already answered.
- **FR-012**: The page MUST record each answer under the name the person gave in chat (asked at most once per session, 003 FR-049), passed by the agent when it starts the page. The page MUST show "Answering as <name>" beside the answer controls and let the person change it there, after which later answers use the new name; it MUST NOT ask for the name otherwise. A name that is the AI MUST be refused. Settling answers MUST be refused from anyone not configured to confirm the stage, as in chat.
- **FR-013**: Answers given on the page and in chat MUST belong to the same session for the same list, so either surface continues where the other stopped and no entry is asked twice.

**Returning to the chat (Story 2)**

- **FR-014**: The helper's review list MUST return, for a list with stored answers, each answer's disposition, the person's name and the comment, so the agent can act on them without reading the record file (003 FR-012).
- **FR-015**: When the person chose the page for the session (FR-021), the stage commands for Requirements, Functional and Technical MUST, at their review step, start the page if it is not running and give the person its address, or, if it is running, tell them to reload it. They MUST tell the person to answer there and say when done, and then act on the stored answers: rework each block sent back, saying what changed; answer each question in chat, or raise it as a challenge, reworking the block if the answer changes it. A questioned block stays on the list; the agent MUST then ask the person to reload the page and answer it there, and MUST NOT record an answer to it in chat while the page is the session's chosen surface.
- **FR-016**: The page MUST let the person comment on any settled block of the stage under review. Other stages' documents are shown read-only (research D-69). When no review is current, comments are given in chat. Such a comment MUST reopen the block through the helper's existing reopen, recorded with the comment verbatim, the person's name and the time, so that the block is on the review list again and the agent acts on it as on a send-back. A comment is never required to proceed.

**Reading aids (Story 4)**

- **FR-017**: Each reference code on the page MUST show the section that defines it when pointed at, link to its document, and be marked as an error when it has no definition or more than one in the story.
- **FR-018**: Diagram blocks MUST be shown as source unless the project's configuration names a browser diagram script. When one is named, the browser draws the diagrams, the page names the script and where it comes from, and a diagram that fails still shows its source. The helper itself MUST NOT draw diagrams or fetch anything (constitution 1.3.0).

**Scope**

- **FR-019**: The page MUST be available for the Requirements, Functional and Technical stages, for both their review lists (blocks that need review, and changes since approval). Other stages keep their chat review.
- **FR-020**: Approval MUST stay in chat, after the review and, for Functional and Technical, the comprehension check. The page MUST NOT offer approval, an override, a waiver or any other confirmation beyond answering review entries and commenting on blocks.
- **FR-021**: At the first review step of a session, the agent MUST ask the person once whether to review on the page or in chat, stating the purpose (a decision about how they review), and MUST use that answer for every later review in the session unless the person changes it. The choice is a preference, not a record: it decides nothing the helper enforces.
- **FR-022**: Every review MUST remain possible entirely in chat: when the page cannot start, or the person prefers chat, the chat review of 003 applies unchanged.

**Records, tests and documentation**

- **FR-023**: The page MUST keep no state of its own. Everything it shows MUST come from the documents and the helper, and everything it causes MUST be in the record file, so removing the extension leaves nothing behind but the records (Constraints of Record).
- **FR-024**: `specs/001-staged-definition-workflow/research.md` D-21 MUST be amended in the same change to state that the helper may serve local pages and that diagrams are drawn by the browser only on the project's opt-in, as constitution 1.3.0 requires.
- **FR-025**: The attestation limit MUST be documented with the feature: the page cannot tell who used the browser, or whether an AI agent drove it, and a page answer is no stronger evidence of identity than a chat reply (Principle II).
- **FR-026**: Every rule here that decides whether an answer is stored, refused or recorded MUST be deterministic helper behaviour with a unit test (Principle I): the token and origin checks, the stale check, the fixed question, the confirmer check, the section action and the session shared with chat. Every new prompt rule MUST have a prompt contract test, and a probe in `docs/trials.md` where it cannot be checked from files.
- **FR-027**: A CHANGELOG entry MUST name the human interactions this feature adds or removes, with their purpose.

### Human interactions added and removed (Constitution Principle IV)

| Interaction | Added or removed | Purpose |
|---|---|---|
| Choosing page or chat for reviews | Added (one reply per session) | Decision |
| Opening the review page from the address the agent gives | Added (once per session, when the page is chosen; each later review is a reload) | Awareness |
| Answering each block needing review on the page instead of in chat | Moved, not added: the same answers on another surface | Validation |
| Reading the whole document around the blocks being reviewed | Added (optional; the page shows it, nothing requires reading it) | Understanding |
| Saying "done" in chat after answering on the page | Added (one reply per review) | Awareness |
| Asking the agent to print a block's full text in a summary-mode list | Removed when reviewing on the page (every entry is shown in full) | (was understanding) |
| Accepting the rest of a section in one action | Added as an option on the page, equivalent to "ok to the rest" | Validation |
| Commenting on a settled block | Added as an option; reopens the block with the comment | Validation |

### Key Entities

- **Review page**: A local page served by the helper for one story for one session, with its own token, showing whichever review is current. It holds no state of its own.
- **Page answer**: One stored answer given on the page: entry, version shown, disposition (accept, send back, question), the fixed question, the comment, the person's name and the time. It is the same answer a chat reply stores, marked as given on the page.
- **Fixed entry question**: The helper's wording of what accepting an entry confirms. It is recorded with every page answer.
- **Section acceptance**: One action that accepts every unanswered entry in a section, recorded as accepted together.
- **Reopen comment**: A comment on a settled block, recorded as a reopen of that block with the comment, the person's name and the time.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In the scenario suite, 100% of answers given on the page are recorded with the person's name, the time, the fixed question and the entry version, and produce the same recorded outcome as the same answers given in chat.
- **SC-002**: In the scenario suite, 0 state-changing requests without the page's token, from another origin, against a stale entry or naming a file outside the story are accepted, and 0 of them write anything.
- **SC-003**: A developer can answer a 38-entry Functional review on the page without asking the agent for any entry's text, and closing the browser half way loses 0 stored answers.
- **SC-004**: In a human trial of a story comparable to the trial's story 002, the developer completes the Requirements, Functional and Technical reviews on the page, and the trial records how long each review took against the chat review of 003, in `docs/trials.md`.
- **SC-005**: Every gate refusal in the 001, 002 and 003 scenario suites still refuses the same input; the page adds no way to settle an entry that chat does not have.

## Assumptions

- The rich specification viewer's reading experience (rendering, reference previews, reading order) is reused, not its code as a dependency. The viewer stays a separate, read-only product. How much of its code is carried into the extension is a planning decision.
- The extension stays on the Python standard library (Principle III). The page needs no installation beyond the extension, and works in any current desktop browser.
- The agent cannot see the browser. It learns the outcome only from the helper, when the person says they are done. A probe in the trial protocol checks that the agent does not act before then.
- The helper runs one page per story for the session. Starting it in the background is the agent's job; the person may also start it themselves. The 60-minute idle stop is a starting value, to be revisited after trials.
- An AI agent with browser tools could drive the page, just as it could pass a name on the command line. The token and origin checks make that detectable, not impossible, and this is documented as an attestation-level limit (FR-025).
- The constraints of 001, 002 and 003 remain binding. This feature amends only 001 research D-21 (FR-024), and adds a second surface to 003's review lists without changing their modes in chat.
