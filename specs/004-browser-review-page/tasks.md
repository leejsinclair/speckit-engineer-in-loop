---
description: "Task list for the Browser Review Page"
---

# Tasks: Browser Review Page

**Input**: Design documents from `specs/004-browser-review-page/`

**Prerequisites**:
- plan.md and spec.md;
- research.md (D-60 to D-72, R-29 to R-34);
- data-model.md;
- contracts/ (cli.md with determinism 54 to 69, page.md, commands.md);
- quickstart.md (B-38 to B-44, probes P-32 to P-35).

**Tests**: Included and written first. Constitution Principle III requires it, and FR-026 names the rules that need a unit test. Each test task is run and **seen to fail** before its implementation task starts.

**Organization**:
- Tasks are grouped by the spec's user stories, US1 to US6, in priority order.
- The plan's delivery order is kept inside that grouping:
  - write safety, the current review, the copied renderer and the server's request checks are Foundational, because every story needs them;
  - the answer-path extension (`shown`, `question`, `comment`, `via`) is in US1, because the page's first answer needs all of it.
- Prompt changes sit with the story whose behaviour they describe. One CHANGELOG entry is written in Polish (FR-027).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (a different file, and no dependency on an incomplete task).
- **[Story]**: US1 to US6.
- Paths are relative to the repository root. `eil/` means `extensions/eil/scripts/python/eil/`. `commands/` means `extensions/eil/commands/`.
- Some files are shared by many tasks, so tasks that edit them are never [P] with each other:
  - `eil/cli.py`, `eil/reviews.py`, `eil/pagerender.py` and `eil/reviewpage.py`;
  - `tests/contract/test_prompt_guidance.py`;
  - the four prompt files `commands/speckit.eil.{requirements,functional,technical,accept}.md`.

---

## Phase 1: Setup

**Purpose**: A clean baseline and the shared test fixtures.

- [X] T001 Ask the repository owner two things:
  - whether to create a `004-browser-review-page` branch from `003-proportionate-effort` now;
  - whether to commit the constitution 1.3.0 amendment and `specs/004-browser-review-page/` (spec, plan, research, data model, contracts, quickstart, this file) as "docs: add 004 browser-review-page spec, plan and tasks".

  Run `pytest` before anything else changes, and record the pass count as the baseline.
- [X] T002 [P] Create `tests/fixtures/review_page.py`, built on `tests/helpers/package.py`. It holds:
  - a story with Requirements approved and a Functional draft listing five blocks across two sections (one prose paragraph, two items, one table, one `§Section` scaffolding entry);
  - one restated block that is settled;
  - one `mermaid` fence;
  - Functional text citing `REQ-004` (defined once), `REQ-099` (undefined) and `DEC-002` (defined twice).

  Add options for:
  - a 12-entry list in three sections (det 59);
  - a 38-entry Functional list (SC-003);
  - a 9-or-more-entry summary-mode list (det 69);
  - an approved Functional stage with two changed items, one removed item and the `legacy:functional` entry (US6).
- [X] T003 [P] Create `tests/helpers/page.py`:
  - `start_page(root, story, by, **opts)` runs `reviewpage` in a thread on a free port and returns `(address, token, stop)`;
  - `call(method, path, body=None, headers=None)` uses `urllib.request` and returns `(status, headers, text)`;
  - a `same_origin(address)` header builder.

  No browser is used.
- [X] T004 Add the pytest fixtures `review_page_story` and `page_server` to `tests/conftest.py`. They reuse `files_snapshot(root)` for byte-identity checks and assert after each test that no `eil-record.json.lock` remains.

---

## Phase 2: Foundational (blocking prerequisites)

**Purpose**: Everything every story needs:
- writes that a second writer cannot lose (plan step 1);
- the current-review rule;
- the copied renderer;
- a server skeleton whose request checks exist before any route that writes.

**⚠️ No story work starts until this phase's checkpoint passes.**

### Tests (write first, see them fail)

- [X] T005 [P] Write `tests/unit/test_record_lock.py` (D-67):
  - `recordfile.save` replaces the file atomically, and a failure mid-write leaves the old file intact and no temporary file behind;
  - `recordfile.record_lock(root)` is exclusive;
  - a second holder waits, then refuses with `record-busy` after 5 s (patched clock) and writes nothing;
  - a lock older than 60 s whose pid is not running is broken, and the result says so;
  - no lock file outlives a call;
  - **determinism 67, CLI half**: twenty concurrent `review answer --entry` subprocesses, each to a different entry, all stored. The record is valid JSON, and no lock remains.
- [X] T006 [P] Write `tests/unit/test_current_review.py`:
  - **determinism 62**: `requirements/inferred` on a fresh story, `functional/inferred` after Requirements approval, `requirements/changes` after an approved Requirements block is edited, and `null` once Technical is approved;
  - `review list --current --json` returns `current: null` and exits `0` when there is none;
  - the `document` field names the latest of the three stages that exists (data-model "Current review").
- [X] T007 [P] Copy `rich-specification-viewer/tests/unit/test_markdown.py` to `tests/unit/test_page_markdown.py`, adapted to import `eil.pagerender`. Add cases:
  - raw HTML in Markdown is rendered as text;
  - `eil:` regions are dropped;
  - `safe_href` refuses `javascript:` and `data:` links.

  Record the source path and commit at the top of the file.
- [X] T008 [P] Write `tests/unit/test_page_security.py` against the server skeleton:
  - **determinism 54**: a `POST /answer` with no token, a wrong token, `Origin: http://evil.example`, no `Origin`, `Host: attacker.example`, or a non-JSON content type returns `403`, the record is byte-identical, and no lock file remains;
  - any method other than GET or POST returns `405`;
  - **determinism 55**: `GET /doc/../../etc/passwd`, `GET /doc/notastage`, `GET /eil-record.json` and `GET /static/x.js` return `404` or `403`. With `Path.read_bytes` patched to record paths, no file outside the story's stage documents is read;
  - every response carries `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`, `Cache-Control: no-store` and a CSP header;
  - a `GET /` without the token returns the short "open the address the agent gave" page, with no token and no document text in it.

### Implementation

- [X] T009 Change `eil/recordfile.py` (D-67):
  - `save` writes a sibling temporary file and calls `os.replace`;
  - add `record_lock(root)`, a context manager using `O_CREAT | O_EXCL` on `eil-record.json.lock`, holding `{pid, at}`, with a 5 s wait, `record-busy`, and stale-break after 60 s for a dead pid.
- [X] T010 In `eil/cli.py`, wrap every `writes` subcommand's read-modify-write in `record_lock`, and add `record-busy` to the refusal codes. Run T005, then the full suite: it must match the T001 baseline (plan step 1 checkpoint).
- [X] T011 Add `reviews.current_review(package)` to `eil/reviews.py` (D-61), returning `{stage, kind, entries, document}` or `stage: null`.
- [X] T012 Add `--current` to `review list` in `eil/cli.py`. It replaces `--stage` and `--kind`, and returns `current` and the list. Run T006.
- [X] T013 [P] In `eil/show.py`, rename `_view_lines` to the public `view_lines` and update its two callers. The output of `show` is unchanged (existing `tests/unit/test_show.py`).
- [X] T014 Create `eil/pagerender.py` with the viewer's `tokenize`, `render_markdown`, `esc` and `safe_href`, copied from `rich-specification-viewer/specview.py`:
  - a header comment names the source file and commit;
  - the Mermaid CDN script and anything else that fetches is removed;
  - add `csp(nonce, diagram_origin=None)`, returning the D-69 policy.

  Run T007.
- [X] T015 Create `eil/reviewpage.py`:
  - `make_server(root, story, by, host, port)` on `http.server.HTTPServer` (single-threaded, D-60), with a per-process `secrets.token_urlsafe(32)` token;
  - a request handler that checks the Host header (`127.0.0.1`, `localhost`, the bound host, `--public-name`), the token (`?t=` on GET pages, the `X-EIL-Token` header elsewhere), and Origin plus `Content-Type: application/json` on every POST;
  - `403` for a failed check, `405` for other methods, and the security headers on every response;
  - a route table whose `/doc/<stage>` accepts only the nine stage names and resolves through the package's stage paths;
  - every other path returns `404`, and nothing is read from disk but stage documents and the record.

  Run T008.

**Checkpoint**: T005 to T008 pass, the full suite matches the baseline, and no `writes` subcommand can lose an update to a concurrent CLI write.

---

## Phase 3: User Story 1 - Review a stage's blocks in the browser (Priority: P1) 🎯 MVP

**Goal**: The agent starts the page and gives its address. The person sees the whole document with only the listed blocks highlighted, and accepts, sends back or questions each one with the helper's fixed question. Each answer is stored at once through `reviews.answer`, and the list closes exactly as it would in chat.

**Independent Test**: B-38. Five listed Functional blocks are answered through `POST /answer` (three accept, one send back with a comment, one question with a comment). Five session answers carry `via: page`, the fixed question, the name, the time and the comment. On the fifth, the session closes into acceptances carrying `via`, `questions` and `comments`. Block statuses equal those from the same answers given with `review answer --entry`.

### Tests for User Story 1 (write first, see them fail)

- [X] T016 [P] [US1] Write `tests/unit/test_entry_question.py`:
  - **determinism 58**: `review list` returns exactly the D-64 table's question for an inferred block, an inferred `§Section`, and changed, added and removed `changes` entries, plus `legacy:<stage>`;
  - `review answer --question` with any other text is refused with `question-mismatch` and writes nothing.
- [X] T016a [P] [US1] Write `tests/unit/test_review_list_answers.py`, the open-session half (D-72, FR-014). While a session is open, `review list` returns `answers: [{key, disposition, by, at, via, comment, question}]` beside the unanswered `entries`, for answers given on the page and in chat.
- [X] T017 [P] [US1] Write `tests/unit/test_review_answer_page.py` (D-63):
  - `--shown` with a stale hash is refused with `entry-changed`, the record is byte-identical, and the refusal's `current` holds `{key, hash, what}` with the new hash (**determinism 56**, CLI half);
  - `--comment` is stored verbatim, including Markdown, HTML and 10 KB of text;
  - `via="page"` with `except` or `question` and no comment is refused with `comment-required`;
  - `reply` is the comment, or "Accept" when there is none;
  - a CLI call never records `via`;
  - `_close_or_keep` groups by `via`. A list answered half on the page and half in chat closes into two acceptances, and only the page one carries `via`, `questions` and `comments`;
  - `recordfile.problems` accepts the new fields and still rejects unknown ones;
  - **determinism 60**: a page accept from a person who is not a confirmer is refused with `not-a-confirmer`;
  - **determinism 69**: on a summary-mode list, a page answer opens a session in summary mode, `review list` returns the unanswered entries, and `review answer --all` answers the rest as in 003.
- [X] T018 [P] [US1] Write `tests/unit/test_page_render.py`:
  - the page wraps each block from `show.view_lines` in an element with `data-key` and `data-hash`;
  - exactly the `review list` entries carry answer controls (FR-002), and a `§Section` entry's control is on its heading;
  - each control shows its fixed question and three native buttons labelled with the key;
  - each highlighted block carries the text "Needs review: KEY";
  - the header shows the story, the stage and list name, "N of M answered", "Answering as NAME" and the `n` shortcut;
  - the footer says "List complete. Return to the chat and say done." when nothing remains, and "Nothing to answer now." when nothing is listed;
  - the token is in a `<meta>` element;
  - with two entries already answered, the page shows each one's disposition, name and time with a Change button, the counter reads "2 of M answered", and the first unanswered control is the target of `n`;
  - **determinism 63**: block text `<script>alert(1)</script>`, a stored comment `<img src=x onerror=alert(1)>` and a name `"><b>x` appear only escaped. There is no inline event-handler attribute, and there is exactly one `<script>` without `src`, carrying the nonce.
- [X] T019 [P] [US1] Write `tests/unit/test_page_server.py`:
  - `GET /?t=` renders the current review (`review list --current`);
  - `POST /answer` stores through `reviews.answer` under the record lock, and returns the helper's result or refusals unchanged;
  - `POST /answer` naming a stage or kind that is not current is refused with `not-current` and writes nothing;
  - **determinism 60, page half**: `POST /name` with "Claude", "AI" or "assistant" is refused with `ai-approval`, and the name is unchanged; a valid name is used by the next answer;
  - two `POST /answer` calls for the same entry: the same person's later answer replaces the earlier one, and a different person's answer with another disposition goes to `superseded` as a conflict, matching 003 through the CLI;
  - with a malformed `eil-record.json`, `POST /answer` returns the same refusal and message as `review answer` and writes nothing, and `GET /` still renders the document, with the controls disabled and the refusal in the notice bar;
  - **determinism 57**: the same five answers through `POST /answer` and through `review answer --entry`, on identical copies of the fixture, give the same settled blocks, `questioned` and `except` keys and block statuses. The two records differ only in `via`, `questions`, `comments`, reply wording, ids and times.
- [X] T020 [P] [US1] Write `tests/unit/test_serve_runtime.py` (D-66):
  - `review serve --by NAME` prints one JSON line `{story, address, pid}` with the token in the address, binds `127.0.0.1`, and uses the first free port from 8100;
  - it refuses with `ai-approval` for an AI name, `ambiguous-story` on 003's two-stories fixture, `page-running` (with the running address) when a live runtime file exists, and `port-unavailable`;
  - `--status` returns `{running, address, pid, started_at}`, and removes a runtime file whose pid is not running;
  - `--stop` ends the process and removes the file;
  - **determinism 68**: start, `--status` and `--stop` leave every project file byte-identical, and the runtime file is under `tempfile.gettempdir()` with mode `0600` on POSIX.
- [X] T021 [P] [US1] Write `tests/scenario/test_b38_page_review.py` (quickstart B-38, SC-001).
- [X] T022 [US1] Add to `tests/contract/test_prompt_guidance.py`:
  - `test_review_surface_asked_once` (P-32);
  - `test_page_review_waits_for_done` (P-33);
  - `test_agent_never_uses_page` (P-33, extended);
  - `test_page_fallback_to_chat` (P-35);
  - `test_approval_stays_in_chat`.

  Each asserts on `commands/speckit.eil.{requirements,functional,technical,accept}.md` as contracts/commands.md specifies. `test_approval_stays_in_chat` also covers `speckit.eil.approve.md`.

### Implementation for User Story 1

- [X] T023 [US1] In `eil/reviews.py`, add `entry_question(kind, entry)` with the D-64 table, and return `question` on every `review list` entry. Run T016's list half.
- [X] T023a [US1] In `eil/reviews.py`, return `answers` in the list result while a session is open (D-72), and output it from `review list` in `eil/cli.py`. Run T016a.
- [X] T024 [US1] Extend `reviews.answer` in `eil/reviews.py` with `shown`, `via`, `question` and `comment` (D-63):
  - refusals `entry-changed` (with `current`), `question-mismatch` and `comment-required`;
  - store `via`, `question` and `comment` on the session answer;
  - `reply` is the comment or "Accept";
  - `_close_or_keep` groups by `via`, and writes `via`, `questions` and `comments` on each acceptance.
- [X] T025 [US1] In `eil/recordfile.py`, make `problems()` accept the new session-answer and acceptance fields (data-model.md).
- [X] T026 [US1] Add `--shown`, `--question` and `--comment` to `review answer` in `eil/cli.py`, plus the refusal codes `entry-changed`, `question-mismatch` and `comment-required`. There is no `--via` flag. Run T016 and T017.
- [X] T027 [US1] Add `page_html(...)` to `eil/pagerender.py` (D-62, contracts/page.md layout):
  - build the clean view from `show.view_lines`, group its lines by `Block.first_line..last_line`, and wrap each block with `data-key` and `data-hash`;
  - put an answer control on listed entries only, and the `§Section` control on its heading;
  - render entries already answered in the open session from `answers`, not only the unanswered `entries`, and count both in the counter;
  - render the header, an empty notice bar with `role="status"`, the footer, the embedded state and the token `<meta>`;
  - escape every value from a document or a person.
- [X] T028 [US1] Add the page's CSS and script to `eil/pagerender.py` as constants, served inline under the nonce:
  - Accept, Send back and Question; the comment box, sent only when non-empty;
  - the stored-answer display with Change;
  - refusal text shown verbatim in that control only;
  - the counter;
  - the `n` key moves to the next unanswered control;
  - the "Answering as NAME" Change form, posting to `/name`.

  The script decides nothing: it renders, sends `{stage, kind, entry, disposition, shown, question, comment}` with `X-EIL-Token`, and shows the result. Run T018.
- [X] T029 [US1] In `eil/reviewpage.py`, add these routes:
  - `GET /` renders `current_review` with `page_html`;
  - `POST /answer` checks `not-current`, then calls `reviews.answer(entry=…, via="page", …)` under `record_lock`, and returns the result as JSON;
  - `POST /name` changes the in-memory name, refusing an AI name.

  Each request loads the `Package` fresh. A write loads it inside `record_lock`, so the read and the write happen under one lock. On a record refusal, `GET /` renders with every control disabled and the refusal shown. Run T019.
- [X] T030 [US1] In `eil/reviewpage.py`, add the runtime file (D-66): `<tempfile.gettempdir()>/eil-review-<sha256(root)[:12]>-<story>.json`, mode `0600`, written at start and removed on a clean stop. Add `serve`, `status` and `stop` functions.
- [X] T031 [US1] In `eil/cli.py`, add `review serve --by NAME [--host H] [--port P] [--public-name N] [--idle-minutes M]`, `--status` and `--stop`. Add the refusal codes `page-running`, `port-unavailable` and `not-current`. Story targeting follows 003's rules. Run T020 and T021.
- [X] T032 [US1] In `commands/speckit.eil.requirements.md`, `speckit.eil.functional.md`, `speckit.eil.technical.md` and `speckit.eil.accept.md`, add "Reviewing on the page" to the "Presenting a review list" section (contracts/commands.md items 1, 2, 5 and 6, and the approval rule):
  - ask once per session, stating the purpose;
  - check `review serve --status --json`, then start the page or ask for a reload;
  - give the address and which list it shows, never print the list, and wait for "done";
  - on any refusal, say why in one line and continue in chat;
  - pass the person's name, never the AI's;
  - never open, fetch or post to the page address, only give it to the person;
  - pass `--host` only when the person asks for another address;
  - approval, overrides and waivers stay in chat.

  For `functional`, the gap scan runs before the page is offered. Run T022.

**Checkpoint**: B-38 passes, and determinism 54 to 58, 60, 63 and 68 pass. A person can review a Functional draft entirely on the page, and the helper's records match chat.

---

## Phase 4: User Story 2 - Return to the chat and act on the answers (Priority: P1)

**Goal**: After "done", the helper returns every stored answer with its comment and name. The agent reworks send-backs and answers questions, and the person's final answers go back on the page. A comment on any settled block reopens it.

**Independent Test**: B-39, after B-38:
- `review list --current` returns the send-back and the question with their comments and the name;
- after the sent-back block is edited, it is listed and highlighted on reload, and the questioned block is still listed;
- `POST /reopen` on a restated, settled block lists it with `reopened`.

### Tests for User Story 2 (write first, see them fail)

- [X] T033 [P] [US2] Extend `tests/unit/test_review_list_answers.py`, the closed-session half (D-72, FR-014):
  - after a session closes, `last_answers` holds the `except` and `questioned` entries of the latest acceptance, with their comments;
  - a questioned key stays on the list after the session closes.
- [X] T034 [P] [US2] Write `tests/unit/test_reopen_settled.py` (D-65), covering **determinism 61**:
  - a comment on a restated, settled block writes `reopened: {by, at, list, comment, via}` with the comment verbatim;
  - the block is then `needs-review`, is on `review list --kind inferred`, and keeps its fingerprint and class;
  - accepting it removes `reopened`;
  - editing a reopened block keeps the mark until it is settled;
  - `show` adds "(reopened by NAME: COMMENT)" after the block's cue;
  - `--reopen` on a block that is not settled is refused as in 003.
- [X] T035 [P] [US2] Extend `tests/unit/test_page_server.py`:
  - `POST /reopen {stage, key, shown, comment}` requires a comment (`comment-required`), is refused with `entry-changed` when `shown` is outdated, and is allowed only on the current review's stage;
  - the page renders a Comment button on settled blocks only, and after a stored reopen shows "Reopened by NAME".
- [X] T036 [P] [US2] Write `tests/scenario/test_b39_return_to_chat.py` (quickstart B-39).
- [X] T037 [P] [US2] Write `tests/scenario/test_b44_shared_session.py` (quickstart B-44, FR-013). On a 6-entry list, three entries are answered on the page, then the CLI's `review list` and `review answer --entry` answer the rest. No entry is asked twice, and the session closes once, with page and chat groups as separate acceptances.
- [X] T038 [US2] Add `test_page_answers_acted_on` (P-34) to `tests/contract/test_prompt_guidance.py`, for the four prompt files.

### Implementation for User Story 2

- [X] T039 [US2] In `eil/reviews.py`, return `last_answers` after a session closes, in the list result (D-72). Run T033.
- [X] T040 [US2] In `eil/reviews.py`, add `_reopenable_inferred` (every block of the stage whose status is `settled`, of any class) and use it for `reopen`. `_reopen_inferred` writes the `reopened` mark with the comment and `via`, and `_settle_inferred` removes it.
- [X] T041 [P] [US2] In `eil/blockstatus.py`, report a block with a `reopened` mark as `needs-review`, whatever its class.
- [X] T042 [P] [US2] In `eil/show.py`, add "(reopened by NAME: COMMENT)" after the block's review cue.
- [X] T043 [US2] In `eil/recordfile.py`, make `problems()` accept `reopened` on provenance entries. In `eil/cli.py`, pass `--comment` through `review answer --reopen`, and output `answers` and `last_answers`. Run T034.
- [X] T044 [US2] In `eil/reviewpage.py`, add `POST /reopen`, which calls `reviews.answer(reopen=[key], via="page", shown=…, comment=…)` under the lock. In `eil/pagerender.py`, add the Comment button and its box on settled blocks ("Send this block back for review with your comment"), and the "Reopened by NAME" display. Run T035 to T037.
- [X] T045 [US2] In the four prompt files, add "After done" and "A comment on a settled block" (contracts/commands.md items 3 and 4):
  - run `review list --current --json`;
  - show each send-back's comment, rework the block, and say what changed;
  - answer each question in chat, or raise a challenge;
  - ask for a reload;
  - never record a page-surface entry's answer in chat;
  - when the list is empty, continue to the comprehension check and approval in chat.

  Run T038.

**Checkpoint**: B-39 and B-44 pass, along with determinism 61. The full loop works: page, done, rework, reload, page.

---

## Phase 5: User Story 3 - The page is safe to leave open (Priority: P1)

**Goal**: The page cannot be used by anything but the person's own browser session. It never records an answer against text the person did not see. It notices changes without changing what is shown, and it stops when idle without losing anything.

**Independent Test**: B-40. The determinism 54 and 55 attacks, a stale answer (56) and a `0.0.0.0` start without `--host` are all refused, with the record byte-identical. The default bind is `127.0.0.1`.

### Tests for User Story 3 (write first, see them fail)

- [X] T046 [P] [US3] Write `tests/unit/test_page_state.py`:
  - **determinism 66**: `GET /state` returns `{current, doc, entries, answers}`, and reflects a block edit and a CLI-stored answer on the next call. The page's poll constant is at most 5000 ms, and the `GET /` HTML embeds the same state it was rendered from;
  - **determinism 65**: with `idle_minutes` patched short, a server receiving only `GET /state` stops, and one receiving `GET /` within the period does not. After the stop, every stored answer is in `eil-record.json`, and `review list` resumes the session;
  - `GET /state` answers in under 200 ms on the 002 performance fixture;
  - a CLI write made between two `GET /state` calls appears in the second, which proves there is no cached package.
- [X] T047 [P] [US3] Extend `tests/unit/test_page_security.py`:
  - **determinism 56, page half**: a `POST /answer` with an outdated `shown` returns `entry-changed` with the current text, and the record is byte-identical;
  - the default bind is `127.0.0.1`, and a non-loopback host is used only with `--host`;
  - with `--host 0.0.0.0 --public-name box.local`, `Host: box.local` is accepted and `Host: attacker.example` is refused;
  - **determinism 67, page half**: ten `POST /answer` calls and ten `review answer --entry` subprocesses, each to a different entry, are all stored, the record is valid JSON, and no lock remains.
- [X] T048 [P] [US3] Write `tests/scenario/test_b40_page_safety.py` (quickstart B-40, SC-002).

### Implementation for User Story 3

- [X] T049 [US3] In `eil/identity.py` and `extensions/eil/config-template.yml`, add `review.page_idle_minutes`, default `60` and a positive integer. Any other key under `review` is still refused.
- [X] T050 [US3] In `eil/reviewpage.py`, add `GET /state` (D-68), which loads the package fresh on each call, and the idle stop: `last_use` is updated by every request except `GET /state`, and a timer thread shuts the server down and removes the runtime file. `--idle-minutes` overrides the configuration. Also add the `--public-name` host acceptance, honoured only when the host is not loopback.
- [X] T051 [US3] In `eil/pagerender.py`, update the page script:
  - poll `/state` every 4000 ms;
  - compare with the embedded state and show one notice with a Reload button: "KEY changed", "KEY was answered elsewhere", "A new review is current: STAGE", or "The document changed outside the review blocks";
  - on `entry-changed`, replace the shown text in that control only, with "This block changed; read it again before answering";
  - on a failed connection, show "The review page has stopped; ask the agent to start it again";
  - never change rendered content.

  Run T046 to T048.

**Checkpoint**: B-40 passes, along with determinism 54 to 56, 65, 66 and 67 (both halves). SC-002 holds.

---

## Phase 6: User Story 4 - Diagrams and references on the page (Priority: P2)

**Goal**: Reference codes link to and preview their defining block, using the helper's own block ids. Diagrams show as source, and are drawn by the browser only when the project names a script.

**Independent Test**: B-41:
- `REQ-004` links to `/doc/requirements#REQ-004` with a preview;
- `REQ-099` and `DEC-002` carry the error mark;
- the diagram source is always present;
- the script and the CSP follow determinism 64.

### Tests for User Story 4 (write first, see them fail)

- [X] T052 [P] [US4] Write `tests/unit/test_page_references.py` (D-69):
  - codes resolve from `Block.id` across every existing stage document;
  - a resolved code is a link to `/doc/<stage>?t=…#<id>` with the defining block's rendered text as its preview;
  - an undefined or duplicated code carries the error mark and a title saying which;
  - `GET /doc/<stage>?t=` renders that stage read-only, and shows the Comment control only when it is the current review's stage.
- [X] T053 [P] [US4] Write `tests/unit/test_page_diagrams.py`:
  - a `mermaid` fence is shown as source;
  - **determinism 64**: without `review.diagram_script`, the page contains no URL with a scheme other than its own origin, and the CSP `script-src` is `'self' 'nonce-…'`. With `https://cdn.example/m.mjs`, the page names that URL once in text ("Diagrams drawn by URL"), and `script-src` adds exactly `https://cdn.example`;
  - `review.diagram_script` that is not an `https:` URL is refused by configuration loading;
  - the helper never opens a network connection (socket patched).
- [X] T054 [P] [US4] Write `tests/scenario/test_b41_references_diagrams.py` (quickstart B-41).

### Implementation for User Story 4

- [X] T055 [US4] In `eil/identity.py` and `extensions/eil/config-template.yml`, add `review.diagram_script`, default `null`, accepting only an `https:` URL.
- [X] T056 [US4] In `eil/pagerender.py`, add the reference index built from `Block.id` of every existing stage document: links, previews and the error mark. Add the diagram handling:
  - source always shown;
  - with the opt-in, one module script tag for the configured URL, the "Diagrams drawn by URL" line under the first diagram, and the drawing placed beside its source, which stays visible on failure;
  - `csp()` adds the script's origin only.
- [X] T057 [US4] In `eil/reviewpage.py`, render `GET /doc/<stage>` read-only through `page_html` on the route T015 guards, with the Comment control only for the current review's stage. Run T052 to T054.

**Checkpoint**: B-41 passes, along with determinism 64. Determinism 55 still passes with the rendered `/doc` route.

---

## Phase 7: User Story 5 - Answer a section at once, honestly recorded (Priority: P2)

**Goal**: "Accept the rest of this section" stores each unanswered entry of that section as accepted together, and records that every entry was shown in full.

**Independent Test**: B-42, which is determinism 59 on the 12-entry list.

### Tests for User Story 5 (write first, see them fail)

- [X] T058 [P] [US5] Write `tests/unit/test_review_answer_section.py`:
  - **determinism 59**: on a 12-entry list in three sections, answering two of section A individually and then `review answer --rest --section A` stores `accept` with `together: A` and `seen: true` for A's other entries only. B and C have no answers, and A's two earlier answers are unchanged;
  - `--rest` without `--section` keeps `seen: false`, as in 003;
  - the closing acceptance carries `together: {entry: section}`.
- [X] T059 [P] [US5] Extend `tests/unit/test_page_server.py`:
  - `POST /section {stage, kind, section}` calls the same path with `via: page`;
  - the page shows "Accept the rest of this section" only on headings with unanswered entries;
  - the button's first click asks "Accept the N unanswered blocks under SECTION?" and the second sends.
- [X] T060 [P] [US5] Write `tests/scenario/test_b42_section_accept.py` (quickstart B-42).

### Implementation for User Story 5

- [X] T061 [US5] In `eil/reviews.py`, add `section` to `answer(rest=True, …)` with `together` and `seen: true`, and write `together` on the acceptance. In `eil/recordfile.py`, `problems()` accepts `together`.
- [X] T062 [US5] Add `--section NAME` (valid only with `--rest`) to `review answer` in `eil/cli.py`. Run T058.
- [X] T063 [US5] In `eil/reviewpage.py`, add `POST /section`. In `eil/pagerender.py`, add the section button with its two-click confirmation. Run T059 and T060.

**Checkpoint**: B-42 passes, along with determinism 59.

---

## Phase 8: User Story 6 - Re-approving a changed stage (Priority: P3)

**Goal**: A changed, approved stage's `changes` list is reviewed on the page the same way. Removed entries and the legacy entry have their own panels, and the re-sign behaves as after chat answers.

**Independent Test**: B-43:
- `current` is `functional/changes`;
- after one accept and one send-back on the page, `review confirm` refuses the re-sign, as after the same answers in chat;
- after rework and an accept on the page, it proceeds.

### Tests for User Story 6 (write first, see them fail)

- [X] T064 [P] [US6] Extend `tests/unit/test_page_render.py` for the `changes` kind:
  - the header reads "…: changes since approval";
  - each changed entry is highlighted with what changed;
  - a "Removed since approval" panel has one control per removed entry, showing the removed block's full text (constitution Principle II), not a summary;
  - the `legacy:<stage>` entry has its own panel with the helper's legacy statement;
  - panel controls post the same `{stage, kind, entry, …}` body.
- [X] T065 [P] [US6] Write `tests/scenario/test_b43_changes_on_page.py` (quickstart B-43).

### Implementation for User Story 6

- [X] T066 [US6] In `eil/pagerender.py`, add the "Removed since approval" and legacy panels, and the `changes` header wording. Run T064 and T065.
- [X] T067 [US6] In `commands/speckit.eil.accept.md`, when the stage is Requirements, Functional or Technical and the page is the chosen surface, hand the `changes` review to the page. Other stages are unchanged. Re-run `tests/contract/test_prompt_guidance.py`.

**Checkpoint**: B-43 passes. Every story works on its own and together.

---

## Phase 9: Polish and cross-cutting concerns

- [ ] T068 [P] Extend `tests/unit/test_performance.py`:
  - `GET /` renders the 002 performance fixture's largest stage (about 100 KB) in under 1 s;
  - `GET /` renders the 38-entry Functional list from the T002 fixture, with every entry's full text, in under 1 s (SC-003);
  - `status`, `check`, `enter` and `show` stay under 1 s with the record lock in place.
- [ ] T069 [P] In `commands/speckit.eil.status.md` and `speckit.eil.next.md`, mention the address in one line when `review serve --status` reports a running page (contracts/commands.md). Add an assertion for it to `tests/contract/test_prompt_guidance.py`.
- [ ] T070 [P] Extend `tests/contract/test_install.py`:
  - `review.page_idle_minutes` and `review.diagram_script` are in the installed `config-template.yml`;
  - extension removal leaves `eil-record.json`, and no runtime or lock file, in the project (`tests/contract/test_removal_and_coexistence.py`).
- [ ] T071 [P] Add probes P-32 to P-35 (P-33 extended: the agent makes no request to the page address) and an SC-004 timing row (Requirements, Functional and Technical reviewed on the page, against 003's chat review) to `docs/trials.md`, with the same pass rule as 003.
- [ ] T072 [P] Update `README.md`:
  - how to review on the page: the surface question, `review serve`, `--status` and `--stop`, `--host` and `--public-name` for containers, and `review.diagram_script`;
  - the attestation limit (FR-025, R-29): the page cannot tell who used the browser, or whether an AI agent drove it, and a page answer is no stronger evidence than a chat reply.
- [ ] T073 Add a CHANGELOG entry to `CHANGELOG.md` (FR-027). It names the browser review page, the record lock (`record-busy`) and the wider `--reopen`, and copies the spec's Principle IV table of interactions added, moved and removed, with their purpose.
- [ ] T074 Add the amendments:
  - a D-21 amendment paragraph in `specs/001-staged-definition-workflow/research.md` (FR-024): the helper may serve local pages, never renders a diagram or fetches anything, and a browser draws diagrams only when the project names a script;
  - an amendment note in `specs/003-proportionate-effort/spec.md`: the review session gains a second surface, and `--reopen` reaches every settled block (D-65).
- [ ] T075 Fold `contracts/cli.md` and `contracts/commands.md` into `specs/001-staged-definition-workflow/contracts/cli.md` and `commands.md`, in the same change as the tests that pin them (Constitution workflow). `contracts/page.md` stays with this feature. If the release is split into several pull requests, do this once per pull request, for that pull request's part.
- [ ] T076 Run `ruff check .` and the full `pytest` suite, including the contract tests against a scratch Spec Kit project. Confirm that every 001 to 003 gate refusal still refuses the same input (SC-005), and fix any failure.
- [ ] T077 Run the quickstart's manual check (steps 1 to 6) on a scratch project in a desktop browser. Record what was seen in `specs/004-browser-review-page/research.md` under Evidence.
- [ ] T078 Run `/speckit-analyze` before implementation begins. Fix any CRITICAL finding in the spec, plan or tasks. Confirm by grep that:
  - no page route reaches `approve`, `review confirm`, an override or a waiver (FR-020);
  - the page's script decides nothing that the helper does not also refuse;
  - every determinism requirement from 54 to 69 has a unit test (FR-026).
- [ ] T079 Draft the pull request description. It must:
  - name the principles touched (I to IV);
  - confirm that no gate, refusal or record exists only in the page script or a prompt;
  - name the contract test and probe for each of the six Tier 2 rules;
  - name the two noted deviations (wider `--reopen`, `record-busy`);
  - copy the spec's Principle IV table.
- [ ] T080 After release, run the SC-004 timed human trial (T071's row) on a story comparable to the trial's story 002, and record the results in `docs/trials.md`. This does not block the pull request.

---

## Dependencies and execution order

### Phase dependencies

- **Setup (T001 to T004)**: T001 comes first and needs the owner's answer. T002 and T003 run in parallel, then T004.
- **Foundational (T005 to T015)**: after Setup. It blocks every story. T010 is the plan's step 1 checkpoint.
- **US1 (Phase 3)**: after Foundational. It is the MVP, and every later story uses its answer path and `page_html`.
- **US2 (Phase 4)**: after US1, because it needs stored page answers to return. Its prompt task (T045) follows US1's (T032) in the same files.
- **US3 (Phase 5)**: after US1, because `GET /state` and the stale display need the page and its answers. It is independent of US2, but both edit `reviewpage.py` and `pagerender.py`, so they run one after the other.
- **US4 (Phase 6)**: after US1. It is independent of US2 and US3 apart from shared files.
- **US5 (Phase 7)**: after US1. It is independent of US2 to US4 apart from shared files.
- **US6 (Phase 8)**: after US1. T067 follows T045 in `speckit.eil.accept.md`.
- **Polish (Phase 9)**: after every story. T078 is last before implementation, and T080 comes after release.

### Story order at a glance

```text
Setup → Foundational → US1 ─┬─ US2 ─┐
                            ├─ US3 ─┤
                            ├─ US4 ─┼─ Polish
                            ├─ US5 ─┤
                            └─ US6 ─┘
```

### Within each story

Write the tests and see them fail. Then work in this order:
1. `reviews.py` and the record changes;
2. the CLI flags;
3. `pagerender.py`;
4. `reviewpage.py` routes;
5. prompts;
6. the scenario.

## Parallel examples

```text
# Setup:
T002 fixtures/review_page.py   T003 helpers/page.py

# Foundational tests together:
T005 test_record_lock.py   T006 test_current_review.py   T007 test_page_markdown.py   T008 test_page_security.py

# US1 tests together:
T016 test_entry_question.py   T016a test_review_list_answers.py   T017 test_review_answer_page.py   T018 test_page_render.py
T019 test_page_server.py      T020 test_serve_runtime.py        T021 B-38

# US2 helper changes in different files:
T041 blockstatus.py   T042 show.py

# After US1, with two developers:
Developer A: US2 → US5        Developer B: US3 → US4 → US6
(Agree the order of edits to reviewpage.py and pagerender.py.)

# Polish:
T068 performance   T069 status/next prompts   T070 install contract   T071 trials   T072 README
```

## Implementation strategy

- **MVP**: Setup, Foundational and **US1**. A person reviews a stage on the page, and the record equals chat's. The token, origin and host checks are already in place from Foundational. Validate with B-38 and the manual check, steps 1 and 2.
- **Increment 2**: **US2** and **US3** (both P1). The loop back to chat, reopen by comment, change notices, the stale display and the idle stop. Release only after this increment: without it, comments on the page reach nobody. Validate with B-39, B-40 and B-44, and manual check steps 3 to 6.
- **Increment 3**: US4 and US5 (P2): references, diagrams and section acceptance. Validate with B-41 and B-42.
- **Increment 4**: US6 (P3), then Polish. Validate with B-43, and SC-004 by the timed trial.
- The feature ships as one pull request; the increments are checkpoints, not separate releases. If a release is split, the matching part of the contracts is folded into 001's contract files in that pull request (constitution: a contract change ships with the tests that pin it; T075).
- At every checkpoint the full existing suite passes (SC-005). Each pull request copies the Principle IV rows for its changes.
