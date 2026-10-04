# Research: Browser Review Page

Decisions are numbered after 003's (D-59, R-28). Each one names the requirements it serves.

## Evidence gathered for this plan

- **The review session already does most of the work.** `reviews.answer(entry=, disposition=, rest=)` stores one answer per entry in `story.review_sessions` of `eil-record.json`. Each answer is `{by, at, disposition, reply, hash, seen}`. `_close_or_keep` applies the stored answers through `_apply_split` once nothing remains, so the result is the same acceptance records a whole-list reply makes. `review list` already returns only unanswered entries while a session is open. A page answer can therefore be the same call with three more fields, and FR-007, FR-010 and FR-013 need no second path.
- **The session does not check what the person saw.** `_answer_session` stores the entry's *current* hash. An answer to text that changed after it was shown is stored against the new text. The page needs the shown version passed in and compared (FR-009).
- **A questioned entry stays listed after the session closes.** `_apply` reopens only `except` and `reopened` keys, and `questioned` keys are not settled. The next `review list` still returns them, which is what FR-015 needs.
- **Reopen works only on what a kind has settled.** `answer(reopen=)` accepts only keys in the kind's `settled` set. For the inferred kind that set (`_settled_inferred`) holds reviewed and adopted blocks. Restated and decided blocks are settled by their traces, not by a review, so they are not in it. `_reopen_inferred` also only drops `reviewed`, which does not put a restated block back on the list. FR-016 ("comment on any settled block") needs a reopen mark that `blockstatus` honours.
- **Record-file writes are not atomic and not serialised.** `recordfile.save` calls `write_bytes` directly. The CLI is one process per call, so this has been safe. A page server that writes while the agent runs a CLI write can lose one of the two updates.
- **Which stage is current is already decided.** `Package.current_stage()` returns the first stage that is not done. An approved stage that changed is no longer `approved`, so it is current again.
- **The viewer's parts are reusable.** `rich-specification-viewer/specview.py` (1,197 lines, standard library only) has the pieces the page needs:
  - a Markdown renderer (`tokenize`, `render_markdown`, `esc`, `safe_href`) that drops `eil:` regions;
  - a `host_allowed` check;
  - a `PathGuard`;
  - a reference index (`find_definitions`, `StoryIndex`);
  - page CSS and script.

  Two of its choices conflict with this feature: it loads Mermaid from a CDN unconditionally (constitution 1.3.0 Constraints of Record) and it uses `ThreadingHTTPServer` (see D-67). Its reference index uses its own regexes, not the helper's block model.
- **The helper already describes each block.** `content.Block` has `key`, `hash`, `section`, `first_line`, `last_line` and `id`. `show.py` builds the clean view with each line's document line number (`_view_lines`). A rendered block can therefore carry its review key without a second parser.

## Decisions

### D-60 The page lives in the helper, as two new modules (FR-001, FR-005, FR-023)

**Decision**: `eil review serve` is a helper subcommand. The work is split across two new modules:
- `reviewpage.py`: the server, its routes, the token and origin checks, the idle stop and the runtime file;
- `pagerender.py`: the Markdown renderer, block wrapping, reference previews, and the page's CSS and script as string constants.

The renderer is **copied** from the viewer and adapted. It is not a dependency: the viewer stays a separate, read-only product, and the copied code says where it came from. The server handles one request at a time (`http.server.HTTPServer`, not the threading variant).

**Rationale**: Constitution 1.3.0 requires every record to be written by the same helper functions as the command line. Only code inside the helper can call `reviews.answer` directly. Copying keeps the extension installable with nothing but itself (Principle III). It also lets the renderer use the helper's block model (D-62). Serving one request at a time serialises the page's own writes (see D-67 for writes from other processes).

**Alternatives considered**:
- Extending the viewer to call `eil` as a subprocess: two products to install, and the viewer would gain writes it was designed not to have.
- Importing the viewer as a library: it is not packaged, and its reference model differs from the helper's.
- A threading server: answers would race inside one process.

### D-61 Which review the page shows (FR-001, FR-019)

**Decision**: On every page load the helper works out the current review:
1. Take `stage = Package.current_stage()`. If it is not `requirements`, `functional` or `technical`, there is no current review.
2. If the stage has an approval record, the kind is `changes`; otherwise it is `inferred`.
3. If that list is empty, the page shows the document with every block settled and "Nothing to answer now". It does the same when there is no current review, showing the current stage's document if it is one of the three and otherwise the latest of them that exists.

The rule lives in `reviews.current_review(package)`. `review list --current` exposes it read-only, so the prompts and the page use one answer.

**Rationale**: FR-001 asks for one page per session, always showing what is current. Deriving it from `current_stage()` keeps the page stateless (FR-023). The agent never has to tell the page what to show, so a reload is all a new review needs.

**Alternatives considered**:
- The agent passes `--stage` at start and again at each review: that holds state in the server, and needs a restart or a control request for each review.
- Showing every pending list on one page: it mixes stages the person is not reviewing yet.

### D-62 Mapping review entries to rendered blocks (FR-002, FR-003, FR-006)

**Decision**: The page is built from the clean view (`show._view_lines`, made public as `show.view_lines`). Each record region becomes its one readable line and HTML comments are dropped. The lines are grouped by `Block.first_line..last_line`. Each block's lines are rendered by `pagerender` and wrapped in an element carrying `data-key` and `data-hash`. Lines outside any block (headings, blank lines) are rendered between them.

The page gives each kind of entry its own place:

| Entry | Where its answer control goes |
|---|---|
| A block | On the block |
| A scaffolding entry `§<Section>` | On the section heading, with the section's blocks marked as its members |
| A `changes` entry for a removed block | In a "Removed since approval" panel at the top, showing the removed text from the entry's `what` |
| The `legacy:<stage>` entry | In a panel at the top, with the helper's legacy statement |

Every value from a document or a person is escaped before it is placed in the page. The renderer's own output contains no raw HTML from the source: raw HTML in Markdown is shown as text, as the viewer already does.

**Rationale**: The helper already decides block boundaries and hashes. Using them means the page highlights exactly what `review list` returns (FR-002), and the shown version (`data-hash`) is the hash the stale check compares (D-63).

**Alternative considered**: The viewer's token stream with key matching by item id. Prose, table and fence blocks have no ids, so some entries could not be placed.

### D-63 One answer path, extended (FR-007 to FR-010, FR-012, FR-013)

**Decision**: `reviews.answer` gains four keyword arguments, all optional on the command line:

| Argument | Effect |
|---|---|
| `shown=<hash>` | Refused with `entry-changed` if it is not the entry's current hash. Nothing is written, and the refusal carries the current text. |
| `via="page"` | Stored on the session answer, and on the acceptance that closes the list. |
| `question=<text>` | The helper's fixed question for the entry (D-64), stored verbatim. The page sends the question it displayed. The helper refuses with `question-mismatch` if that is not its own wording for the entry now, so the record cannot hold a question the helper did not ask. |
| `comment=<text>` | Stored verbatim. Required for `except` and `question` on the page (`comment-required`). |

A page answer's `reply` is the person's comment if there is one. Otherwise it is the label of the answer they chose ("Accept"). This is the page form of a one-word reply to the helper's explicit question, which constitution 1.2.2 accepts.

Everything else is unchanged and shared with chat: the session, the confirmer and AI checks, superseding, conflicts and closing. `_close_or_keep` groups by `via` as well. Each acceptance it writes then carries `via`, plus `questions` and `comments` keyed by entry. That is how "answered on the page" is recorded (FR-010).

The command line gains `--shown`, `--question` and `--comment`. `--via` stays internal: a CLI call is never recorded as a page answer.

The page's names for the dispositions are Accept, Send back and Question. They map to the existing `accept`, `except` and `question`.

**Rationale**: FR-007 requires the same function and the same refusals. Adding arguments, rather than a second function, makes "the same outcome as chat" (SC-001) true by construction. A unit test still pins it (determinism 57).

**Alternative considered**: A separate `page_answer` that calls `answer`. It would duplicate the refusals that need the shown hash and the question.

### D-64 The fixed entry question (FR-003, FR-008)

**Decision**: `reviews.entry_question(kind, entry)` is a fixed table:

| Entry | Question |
|---|---|
| inferred block | "Accept {key} as written?" |
| inferred `§<Section>` | "Accept every block under {Section} as written?" |
| changes, changed block | "Accept {key} as it now reads?" |
| changes, added block | "Accept the new {key} as written?" |
| changes, removed block | "Accept the removal of {key}?" |
| `legacy:<stage>` | the existing `LEGACY_STATEMENT`, ending "Accept?" |

`review list` returns the question on every entry, so chat may show it too. Chat answers do not record it: their record is the person's own words, as now.

**Rationale**: Principle II asks for an explicit, fixed question beside each page answer, so the record shows what an "Accept" confirmed. A table keeps it deterministic and testable.

### D-65 Commenting on a settled block (FR-016)

**Decision**: A comment on a settled block becomes `answer(reopen=[key], reply=<comment>, via="page", comment=<comment>)` on the stage's `inferred` list. Two helper changes make that work for every settled block:
1. For a reopen, the inferred kind's settled set becomes every block of the stage whose status is `settled`, of any class. `_settled_inferred` stays as it is for settling; a new `_reopenable_inferred` is used for `--reopen`.
2. `_reopen_inferred` writes `reopened: {by, at, list, comment, via}` on the block's provenance entry. `blockstatus` treats a block with a `reopened` mark as `needs-review`, whatever its class. `_settle_inferred` removes the mark.

The block's fingerprint, class and traces do not change. A reopened block in an approved stage needs review again before the stage is re-signed, as a sent-back block does.

**Rationale**: FR-016 says "any settled block", and restated blocks are the most common settled blocks. A mark keeps the reason visible in `show` and `status`.

**Alternatives considered**:
- Recording the comment as a challenge: that is a different list, with different answers, and the spec asks for a reopen.
- Changing the block's class to `inferred`: that loses the fact that it restates an approved source.

### D-66 Starting, finding and stopping the page (FR-001, FR-015, FR-023)

**Decision**:
- `eil review serve --by <name> [--host H] [--port P] [--idle-minutes N]` runs in the foreground. The agent starts it in the background. It prints one JSON line with `{story, address, pid}` and serves until stopped.
- `--port` defaults to the first free port from 8100. `--host` defaults to `127.0.0.1`. Another host is used only when given, for example `0.0.0.0` in a container. The host check then also accepts the name the person passes with `--public-name`.
- The address carries the per-session token: `http://127.0.0.1:8100/?t=<token>`. The token is 32 bytes from `secrets.token_urlsafe`.
- A GET without the token is answered with a short page saying to open the address the agent gave. It never returns the token or the document.
- The page puts the token in a `<meta>` element. The script sends it in an `X-EIL-Token` header on every state-changing request and on `/state`.
- A runtime file holds `{story, address, pid, started_at}` with mode `0600`, in the user's temporary directory (`tempfile.gettempdir()/eil-review-<sha256(project root)[:12]>-<story>.json`). It is not in the project. It is removed on a clean stop, and ignored when its pid is not running.
- `eil review serve --status` (read-only) reads the runtime file and returns the address if the page is running. This is how the agent knows whether to start the page or ask for a reload, even after a compaction.
- `eil review serve --stop` ends it.
- The idle stop (default 60 minutes, configuration key `review.page_idle_minutes`) counts every request except `GET /state`.

**Rationale**:
- The runtime file lives outside the project, so removing the extension leaves only the records (FR-023), and nothing in the project changes when a page starts.
- The token in the first address is the simplest thing a person can open. Putting it in a header afterwards keeps it out of any request a third-party page could forge.
- Mode `0600` matters because the file holds the token-bearing address.

**Alternatives considered**:
- A cookie: it is sent on cross-site requests, unless SameSite is honoured, and adds nothing over a header.
- A project-local runtime file: it would put state in the project.
- Port 0 (any free port): addresses would change between restarts more than needed, and a container's published port has to be predictable.

### D-67 Writes are serialised and atomic (FR-007, FR-013)

**Decision**: `recordfile.save` writes to a temporary file in the same directory and replaces the record file with `os.replace`. Every write subcommand, and every page write, holds an exclusive lock for its whole read-modify-write. The lock is a sibling file `eil-record.json.lock`, created with `O_CREAT | O_EXCL`.
- A waiter retries for up to 5 seconds, then refuses with `record-busy` and writes nothing.
- A lock older than 60 seconds whose pid is not running is removed, and the refusal or result says so.
- The lock file is the only file the helper creates beside the record, and it never outlives a call.

**Rationale**: With a page server and the CLI both writing, a lost update would drop a person's answer silently. Principle I does not allow that. `fcntl` is not on Windows, and an exclusive-create file works on Linux, macOS and Windows with the standard library alone.

**Alternatives considered**:
- Optimistic re-read-and-compare: the `Package` caches records, so every write path would need a merge step.
- `fcntl` or `msvcrt` locks: two code paths, each tested on one platform only.

### D-68 Change notices without changing the page (FR-009)

**Decision**: `GET /state` (token required, read-only) returns:
- `current`: the stage and kind;
- `doc`: the document's fingerprint input hash;
- `entries`: `{key: hash}`;
- `answers`: `{key: [disposition, by, at]}`.

The page's script fetches it every 4 seconds and compares it with what was embedded at load. On any difference it shows one notice naming what changed, with a Reload button:
- "FR-003 changed";
- "FR-007 was answered elsewhere";
- "A new review is current: Technical";
- "The document changed outside the review blocks".

It never edits the rendered content. The interval is a constant in `pagerender`, and a unit test pins it at most 5 seconds.

**Rationale**: FR-009 forbids changing the content in place, and the script must decide nothing (constitution 1.3.0). Comparing two helper results and showing a message is presentation only. The stale refusal (D-63) remains the safeguard if the person answers anyway.

**Alternatives considered**:
- Server-sent events: a held connection blocks a one-request-at-a-time server.
- Filesystem watching: not in the standard library on every platform.

### D-69 References and diagrams (FR-017, FR-018)

**Decision**: References:
- Reference codes are resolved with the helper's own model: every `Block.id` of every existing stage document.
- A code is a link to `/doc/<stage>?t=…#<id>`, with the defining block's rendered text as its preview.
- A code with no definition, or more than one, gets the error mark and a title saying which.
- Other stage documents are shown read-only. They carry the reopen comment control only when that stage is the current review's stage, so a comment cannot land on a stage nobody is reviewing.

Diagrams:
- A `mermaid` fence is shown as source.
- Configuration key `review.diagram_script` (default `null`) may name one script URL. The page then loads that one script as a module and shows "Diagrams drawn by <url>" under the first diagram. The script draws each diagram beside its source, which stays visible when drawing fails.
- The page sends `Content-Security-Policy: default-src 'none'; script-src 'self' 'nonce-<n>' [script origin]; style-src 'self' 'nonce-<n>'; connect-src 'self'; img-src 'self' data:; base-uri 'none'; form-action 'self'; frame-ancestors 'none'`. Without the opt-in, no other origin appears.
- The helper never fetches the script.

**Rationale**: Using the helper's block ids means the page's resolution agrees with `trace` and `check`. The viewer's regex set would disagree on edge cases. The CSP enforces in the browser what the constitution requires: nothing loads from outside unless the project named it.

### D-70 Section acceptance (FR-011)

**Decision**: `answer(rest=True, section=<name>)`:
- stores `accept` for each unanswered entry whose `section` is `<name>`;
- marks each with `together: <name>` and `seen: true`, because the page showed every entry in full;
- leaves answered entries and other sections untouched.

`--rest` without `--section` keeps 003's meaning, recording `seen: false`.

**Rationale**: The record has to distinguish "accepted one by one" from "accepted with the rest of its section". `together` does that. `seen` keeps 003's meaning, "the full text was shown": on the page it was. Whether the person read it is beyond what any record can claim (FR-025).

### D-71 Prompts: choosing the surface and the page loop (FR-015, FR-021, FR-022)

**Decision**: The review step's shared prompt section ("Presenting a review list") in `requirements`, `functional` and `technical` gains "Reviewing on the page".

1. At the first review step of a session, ask once: "Review on a page in your browser, or here in chat?" Say it is about how they review, not what they approve.
2. Page chosen:
   - run `eil review serve --status`;
   - start the page in the background if it is not running, otherwise ask for a reload;
   - give the address and say to answer there and say "done";
   - do not print the list.
3. After "done":
   - `review list --current` returns the stored answers (FR-014);
   - rework each send-back and say what changed;
   - answer each question in chat, or raise a challenge;
   - then ask for a reload and an answer on the page;
   - never record a page-surface entry's answer in chat.
4. The page cannot start (a refusal, or a port the person cannot reach): say so and review in chat, as in 003.

Approval stays in chat, unchanged.

**Rationale**: These are presentation rules (Tier 2). The helper enforces everything that records: tokens, staleness, confirmers. The prompts only decide where the person is asked.

### D-72 `review list` returns stored answers (FR-014)

**Decision**: While a session is open, `review list` adds `answers: [{key, disposition, by, at, via, comment, question}]` for the stored answers, beside the unanswered `entries`. After a session closes, the acceptance records hold the same fields, and `review list` returns the latest acceptance's `except` and `questioned` entries under `last_answers`. The agent therefore acts on send-backs and questions without reading the record file.

**Rationale**: Today the agent learns answers from the chat. With the page, the helper is the only place they exist.

## Amendments carried by this feature

- `specs/001-staged-definition-workflow/research.md` D-21 gains an amendment paragraph:
  - the helper may serve local pages (constitution 1.3.0);
  - it still never renders a diagram or fetches anything;
  - a browser draws diagrams only when the project names a script (FR-024).
- `specs/003-proportionate-effort/spec.md` gains an amendment note: the review session has a second surface, and `--reopen` reaches every settled block (D-65).

## Risks

| ID | Risk | Effect | Mitigation |
|---|---|---|---|
| R-29 | An AI agent with browser tools answers on the page | An answer that looks like a person's | Stated as an attestation-level limit (FR-025), as for `--by`. The prompts never open or drive the page. Probe P-33 checks that the agent does not act before "done". |
| R-30 | The token leaks: shell history, browser history, a screen share | Another local process could answer | Loopback only by default. The token lives only as long as the page. The runtime file is `0600`. Answers still pass every helper refusal and carry the name. |
| R-31 | A record write from the page and one from the CLI at the same moment | A lost answer | D-67: lock and atomic replace. Determinism 67 races them. |
| R-32 | The copied renderer and the viewer drift apart | The page and the viewer render differently | Accepted: the page is for review, the viewer for reading. The copied tests travel with the code. |
| R-33 | The page is left open across a stage change | Answers to the wrong list | The stale check and the "A new review is current" notice (D-68). An answer names its list and is refused if the list is not current (`not-current`). |
| R-34 | A person answers on the page while the agent is mid-rework | Answers against text about to change | The stale refusal covers changed blocks. The prompt asks for a reload only after the rework. |
