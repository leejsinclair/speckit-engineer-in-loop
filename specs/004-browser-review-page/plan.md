# Implementation Plan: Browser Review Page

**Branch**: `004-browser-review-page` (spec directory; work continues on the current branch, no branch created) | **Date**: 2026-10-04 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/004-browser-review-page/spec.md`

## Summary

The helper gains a local review page: `eil review serve`. The page shows the current review's document as a person reads it. It puts an answer control on exactly the entries `review list` returns (accept, send back, question, each with the helper's fixed question) and stores every answer through the same `reviews.answer` call a chat answer uses. The browser decides nothing and writes nothing. The decisions are in [research.md](research.md).

1. **One answer path** (D-63, D-64, D-70, D-72):
   - `reviews.answer` gains `shown` (stale check), `via`, `question` and `comment`, and `--rest --section`;
   - `review list` returns each entry's fixed question and the stored answers;
   - page answers and chat answers share one session, so either surface continues where the other stopped.
2. **Reopen any settled block** (D-65): a `reopened` mark on the block's provenance puts it back on the inferred list without changing its class or fingerprint.
3. **The page** (D-60 to D-62, D-66, D-68, D-69):
   - `reviewpage.py` serves one request at a time, on loopback by default, with a per-session token and an origin check, for one story for the session;
   - it shows whatever `review list --current` names;
   - `pagerender.py` renders the clean view block by block with the renderer copied from the rich specification viewer, plus reference previews from the helper's own block ids;
   - diagrams are shown as source unless `review.diagram_script` names one script;
   - a 4-second state check shows change notices without changing the page;
   - a runtime file outside the project lets the agent find a running page after a compaction.
4. **Safe concurrent writes** (D-67): record-file writes become atomic, under an exclusive lock file, so a page answer and a CLI write never lose each other.
5. **Prompts** (D-71): the three stage commands, and `accept`:
   - ask once per session where to review;
   - hand the review to the page;
   - act on the stored answers after "done";
   - fall back to chat.

   Approval stays in chat.

## Technical Context

**Language/Version**: Python 3.11+, standard library only (Constitution III). Markdown prompts. One page of HTML, CSS and JavaScript held as string constants in the helper.

**Primary Dependencies**: None at runtime. Uses `http.server`, `secrets`, `hmac`, `json`, `html`, `tempfile`, `os`, `threading` (idle timer only) and `urllib.parse`. The browser loads no script but the page's own, and the one diagram script a project may name. Development only: `pytest` and `ruff`, unchanged.

**Storage**: Files only.
- Changed: `eil-record.json` gains fields on session answers, acceptances and block provenance (see [data-model.md](data-model.md)).
- New: `eil-record.json.lock`, present only during a write.
- New: a runtime file in the OS temporary directory, never in the project.
- New configuration keys: `review.page_idle_minutes` and `review.diagram_script`.

**Testing**:
- pytest unit tests, written first, for determinism requirements 54 to 69 ([contracts/cli.md](contracts/cli.md)). The server runs in a thread on a free port and is driven with `urllib.request`.
- Scenario tests B-38 to B-44 ([quickstart.md](quickstart.md)).
- Prompt contract tests for the six Tier 2 rules ([contracts/commands.md](contracts/commands.md)).
- The viewer's renderer tests are carried over with the code.
- Trial probes P-32 to P-35, and the SC-004 timed run.

**Target Platform**: Linux, macOS and Windows (unchanged). The page targets current desktop browsers.

**Project Type**: Spec Kit preset plus extension (unchanged). The extension gains a local web page served by its helper.

**Performance Goals**:
- `GET /` renders the 002 performance fixture's largest stage in under 1 s.
- `GET /state` answers in under 200 ms on the same fixture.
- `status`, `check`, `enter` and `show` stay under 1 s, as in 003.

**Constraints**:
- No gate, approval, attestation or recorded override becomes weaker (SC-005).
- The browser decides nothing and writes nothing (constitution 1.3.0).
- The helper never renders a diagram or fetches anything.
- Loopback by default.
- Every state change needs the token and the same origin.
- No state outside the record file except an ephemeral runtime file and a lock that lasts one write.

**Scale/Scope**: One person and one story per page, lists of up to about 40 entries (SC-003), and stage documents of up to about 100 KB.

## Constitution Check

*GATE: must pass before Phase 0 research; re-checked after Phase 1 design.*

Checked against constitution **1.3.0** (amended 2026-10-04 for this feature).

| Principle | Pre-research | Post-design | Evidence |
|---|---|---|---|
| I. Enforcement lives in the helper | Pass | Pass | **Tier 1** (helper code, each with a determinism test from 54 to 69): the token, origin and host checks; the path guard; the stale check; the fixed question and its mismatch refusal; the confirmer and AI checks, shared with chat; section acceptance; the reopen mark; the current-review rule; escaping; the CSP; the idle stop; the record lock. The page's script only renders, polls and sends. Every record is written by `reviews.answer`, the function the CLI calls (D-63). **Tier 2**: six prompt rules, each with a contract test and a probe ([contracts/commands.md](contracts/commands.md)). |
| II. Honest attestation limits | Pass | Pass | Each page answer records the name, time, fixed question, shown version and verbatim comment. `via: page` makes the surface visible. `together` and `seen` say what was answered as a group and what was shown. The identity limit, including an AI agent driving the browser, is documented (FR-025, R-29). A page answer is treated as no stronger than a chat reply. The prompts never open or drive the page. |
| III. Test-first, no runtime dependencies | Pass | Pass | Standard library only. The viewer's renderer is copied, not depended on. Tests are written first for each determinism requirement. The renderer's tests travel with it. |
| IV. Proportionate ceremony | Pass | Pass | The spec's Principle IV table lists every interaction added, moved or removed. The surface is asked once per session. Answer controls appear only on listed entries, and settled blocks need nothing. A comment is never required to proceed. Section acceptance keeps long lists proportionate. No human decision is removed, and no new approval is added. |

| Constraint of Record | Post-design | Evidence |
|---|---|---|
| Nine documents, three aliases, state in project files | Pass | No new document. New records are fields in `eil-record.json`. The runtime file is outside the project, and the lock file lives only for one write. |
| Proportionate hard gates with named overrides | Pass | No gate, override or approval is reachable from the page (FR-020, route table). |
| D-21, as widened by 1.3.0: the helper may serve local pages; diagrams drawn only on the project's opt-in | Pass | The helper serves; it never renders or fetches. `review.diagram_script` is the single opt-in, named on the page and enforced by the CSP (D-69, determinism 64). 001 research D-21 is amended in the same change (FR-024). |
| Local pages: the per-session token and the same origin for state changes; only the story's documents and helper results; loopback by default | Pass | D-66, the route table, determinism 54, 55 and 68 |
| Removal leaves records in place | Pass | Everything the page causes is in `eil-record.json` (FR-023) |

**Deviations noted (not violations).**
1. **003's `--reopen` widens** from blocks a review settled to every settled block (D-65). 003's spec gains an amendment note citing 004.
2. **Record writes gain a lock** (D-67). Every write subcommand can now refuse with `record-busy`. Before 004 that could not happen, and it does not occur without a concurrent writer.

## Project Structure

### Documentation (this feature)

```text
specs/004-browser-review-page/
├── spec.md              # Feature specification (input)
├── plan.md              # This file
├── research.md          # Phase 0: D-60..D-72, R-29..R-34
├── data-model.md        # Phase 1: session answer, acceptance, reopen mark, current review, page process, runtime file, lock, config
├── quickstart.md        # Phase 1: B-38..B-44, manual check, probes P-32..P-35
├── checklists/
│   └── requirements.md  # Spec quality checklist
└── contracts/
    ├── cli.md           # Delta: review list/answer/serve, page routes, refusals, determinism 54–69
    ├── page.md          # What the page shows and does; keyboard and accessibility; performance
    └── commands.md      # Delta: "Reviewing on the page", Tier 2 rules with tests and probes
```

### Source Code (repository root)

Only files that change or are added are shown. The layout is 001's.

```text
extensions/eil/
├── config-template.yml              # + review.page_idle_minutes, review.diagram_script
├── commands/
│   ├── speckit.eil.{requirements,functional,technical}.md  # "Reviewing on the page"
│   ├── speckit.eil.accept.md        # changes review handed to the page for the three stages
│   └── speckit.eil.{status,next}.md # running page address in one line
└── scripts/python/eil/
    ├── reviewpage.py     # NEW  server, routes, token/origin/host, idle stop, runtime file, serve/status/stop (D-60, D-66, D-68)
    ├── pagerender.py     # NEW  renderer copied from rich-specification-viewer, block wrapping, references, CSS/JS constants, CSP (D-62, D-69)
    ├── reviews.py        # shown/via/question/comment, entry_question, --section, current_review, answers in list, reopenable set (D-61, D-63–D-65, D-70, D-72)
    ├── blockstatus.py    # `reopened` mark means needs-review (D-65)
    ├── recordfile.py     # atomic save, record lock, new fields accepted by problems() (D-67)
    ├── show.py           # view_lines public; reopened note after the cue
    ├── identity.py       # review.page_idle_minutes, review.diagram_script
    └── cli.py            # review serve; new review list/answer flags; lock around writes; refusal codes
tests/
├── unit/        test_entry_question.py, test_review_answer_page.py, test_reopen_settled.py,
│                test_current_review.py, test_record_lock.py, test_page_render.py,
│                test_page_server.py, test_page_security.py, test_page_state.py,
│                test_serve_runtime.py, test_performance.py (+ page)
├── scenario/    test_b38…b44_*.py
└── contract/    test_prompt_guidance.py (+5 rules), test_install.py (config keys)
docs/trials.md                       # P-32..P-35, SC-004 row
README.md, CHANGELOG.md              # page usage, attestation limit (FR-025), Principle IV interactions (FR-027)
specs/001-staged-definition-workflow/research.md   # D-21 amendment (FR-024)
specs/003-proportionate-effort/spec.md             # amendment note: second surface, wider reopen
```

**Structure Decision**: The same single repository. Two new modules keep the server and the renderer out of `cli.py` (1,265 lines) and `reviews.py` (1,316 lines). `reviews.py` gains only the answer-path arguments and two small functions (`entry_question` and `current_review`). The page reaches records only through `reviews.answer`.

## Delivery order

Each step is test-first. The checkpoints are binding for `/speckit-tasks`.

1. **Write safety first**, because the page adds a second writer: atomic save and the record lock in `recordfile.py`, then the lock around CLI writes. Checkpoint: determinism 67 with CLI writers only, and the full 003 suite green.
2. **Page skeleton and request checks**: the copied renderer with its tests, and the server's host, token and origin checks with the stage-name guard. No route writes yet. Checkpoint: determinism 54 and 55. The request checks exist before any route that writes, so the page is never served unprotected.
3. **Answer path and first page (US1)**: `entry_question`, then `shown`, `question`, `comment` and `via`, then the stored answers while a session is open, then `current_review`. Each is tested through the CLI before its page route. Then block wrapping, escaping and the CSP, `GET /`, `POST /answer`, and serve, status and stop. Checkpoint: determinism 56 to 58, 60, 62, 63, 68 and 69, and B-38.
4. **The rest by story**: reopen with the `reopened` mark (US2, determinism 61); state, change notices and the idle stop (US3, determinism 65 to 67); references and diagrams (US4, determinism 64); section acceptance (US5, determinism 59); the changes-list panels (US6). Checkpoint: B-39 to B-44.
5. **Prompts**: "Reviewing on the page" in the three stage commands and `accept`, written with their contract tests, each with the story it describes. Checkpoint: the six Tier 2 tests.
6. **Docs and amendments**:
   - README usage and the attestation limit (FR-025);
   - a CHANGELOG entry with the Principle IV interactions (FR-027);
   - the 001 D-21 amendment (FR-024) and the 003 amendment note;
   - probes P-32 to P-35;
   - folding the contracts into 001's files.

## Complexity Tracking

| Departure | Why needed | Simpler alternative rejected because |
|---|---|---|
| A long-running helper process (`review serve`), where every other subcommand is one call | A browser page needs something to answer it | A static HTML file with answers pasted back into chat: the browser cannot write through the helper, and copying answers by hand defeats the feature |
| A lock file around record writes | Two writers (the page and the CLI) | No lock: a lost answer. A platform lock (`fcntl`/`msvcrt`): two code paths, each tested on one platform |
| About 500 lines of renderer copied from the viewer | The page must render Markdown with no dependency | Depending on the viewer: an extra install, and its reference model differs from the helper's |

## Phase Outputs

| Phase | Artifact | Status |
|---|---|---|
| 0 | [research.md](research.md) | Complete. No `NEEDS CLARIFICATION` in Technical Context |
| 1 | [data-model.md](data-model.md) | Complete |
| 1 | [contracts/](contracts/) | Complete (cli.md, page.md, commands.md) |
| 1 | [quickstart.md](quickstart.md) | Complete |
| 2 | `tasks.md` | Not part of this command; run `/speckit-tasks` |

## Open Items Carried Forward

- **Uncommitted**: the constitution 1.3.0 amendment and this feature's spec and plan are not committed yet.
- **Branch**: the checked-out branch is `003-proportionate-effort`. No `004-browser-review-page` branch exists, and `.specify/feature.json` points at 004. Create the branch before implementation if wanted.
- **SC-004** needs a timed human run. It is not automated.
- **Accessibility and performance**, deferred from clarification, are settled in [contracts/page.md](contracts/page.md).
