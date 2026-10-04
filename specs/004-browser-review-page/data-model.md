# Data Model: Browser Review Page

This is a delta to 003's data model. Anything not mentioned here is unchanged. Every record named here lives in `specs/<story>/eil-record.json`, and `recordfile.problems` accepts the new fields. Nothing new is stored in a stage document.

## Review session answer — changed (D-63, D-70)

Each answer in `story.review_sessions[<key>].answers[<entry>]`:

| Field | Type | Meaning |
|---|---|---|
| `by`, `at`, `disposition`, `reply`, `hash`, `seen` | as 003 | unchanged |
| `via` | `"page"` or absent | Absent means chat. Set only by the page server. |
| `question` | string or absent | The helper's fixed question for the entry, as shown on the page (D-64). Present on every page answer. |
| `comment` | string or absent | Verbatim. Required for `except` and `question` on the page. |
| `together` | section name or absent | Accepted with the rest of that section in one action (D-70) |

Rules:
- The answer is stored only if the `shown` hash it carries equals the entry's current hash (`entry-changed` otherwise).
- A section action carries `{entry: shown hash}` for every unanswered target; every target is validated under the same record lock before any answer is stored.
- `reply` is the comment, or the chosen answer's label ("Accept") when there is no comment.
- An answer from another person with a different disposition is moved to `superseded`, as in 003.

## Acceptance record — changed (D-63)

An acceptance is written when a session closes, one per group of answers. The grouping key gains `via`. The new fields:

| Field | Type | Meaning |
|---|---|---|
| `via` | `"page"` or absent | The group was answered on the page |
| `questions` | `{entry: question}` or absent | The fixed question for each entry answered on the page |
| `comments` | `{entry: comment}` or absent | Each comment, verbatim |
| `together` | `{entry: section}` or absent | The entries accepted with their section |

The existing `accepted`, `except`, `questioned`, `unseen`, `hashes`, `digest` and `mode` fields are unchanged. An acceptance made from page answers is therefore read by every existing consumer exactly as one made in chat.

## Block provenance entry — changed (D-65)

`stages.<stage>.provenance.blocks[<key>]` gains:

| Field | Type | Meaning |
|---|---|---|
| `reopened` | `{by, at, list, comment, via}` or absent | A person commented on the settled block. It needs review again. |

State transitions:
- **Settled to needs-review**: `answer(reopen=[key])` writes `reopened`. `blockstatus` reports `needs-review` while it is present and the block's hash equals the entry's `hash`. The class and traces are unchanged.
- **Needs-review to settled**: `_settle_inferred` (an accept on the inferred list) removes `reopened` and records `reviewed` as usual.
- **Text edited while reopened**: the hash differs, so the block needs review because it changed, as in 003. `reopened` stays until it is settled, so `show` can say why.

## Current review — new (D-61)

Derived on every call. It is never stored.

| Field | Value |
|---|---|
| `stage` | `Package.current_stage()` if it is `requirements`, `functional` or `technical`; otherwise `null` |
| `kind` | `changes` if that stage has an approval record, otherwise `inferred` |
| `entries` | the list's entries, possibly empty |
| `document` | the stage shown: `stage`, or, when it is `null`, the latest of the three stages that exists |

## Review page process — new (D-60, D-66)

Held in memory by `eil review serve`. Nothing here is a record.

| Field | Meaning |
|---|---|
| `story` | the story directory, resolved once at start (003 targeting rules; an ambiguous target refuses to start) |
| `token` | `secrets.token_urlsafe(32)`, for the life of the process |
| `name` | the person answering. Set from `--by` and changeable on the page. An AI name is refused. |
| `host`, `port` | `127.0.0.1` and the first free port from 8100, unless given |
| `public_name` | an extra name the host check accepts, only when the host is not loopback |
| `idle_minutes` | from `--idle-minutes`, else `review.page_idle_minutes`, else 60 |
| `last_use` | time of the last request other than `GET /state` |

## Runtime file — new (D-66)

`<tempfile.gettempdir()>/eil-review-<sha256(project root)[:12]>-<story>.json`, mode `0600`:

```json
{"story": "004-browser-review-page", "address": "http://127.0.0.1:8100/?t=…", "pid": 12345, "started_at": "2026-10-04T10:00:00Z"}
```

- It is written at start and removed on a clean stop.
- `review serve --status` proves the record still names the page by calling its token-protected `GET /state`; an unreachable or unauthenticated record is removed.
- `review serve --stop` uses the same proof and token-protected `POST /stop`. The recorded `pid` is informational and is never signalled.
- It is never in the project and never read by anything but `review serve`.

## Record lock — new (D-67)

`specs/<story>/eil-record.json.lock`, created exclusively for one read-modify-write. It holds `{pid, at}`.
- It is removed when the write ends.
- It is broken when it is older than 60 seconds and its pid is not running.
- Waiting gives up after 5 seconds with `record-busy`.

## Configuration — changed

| Key | Default | Meaning |
|---|---|---|
| `review.page_idle_minutes` | `60` | The page stops after this many minutes without a request other than `GET /state`. A positive integer. |
| `review.diagram_script` | `null` | One script URL the browser loads to draw diagrams. `null` shows diagram source only. It must be an `https:` URL. The page never serves the script itself (FR-005). |

`identity.load_config` refuses any other key under `review`, as now.

## Fixed entry question — new (D-64)

This is a table in `reviews.py`, not a record. It is copied into each page answer's `question`. See research D-64 for the wording.
