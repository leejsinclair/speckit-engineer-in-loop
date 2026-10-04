# CLI contract delta: Browser Review Page

This is a delta to 001 `contracts/cli.md`, as amended by 002 and 003. Anything not mentioned here is unchanged. It is folded into 001's file in the same pull request as the tests that pin it.

## Changed subcommands

| Subcommand | Change |
|---|---|
| `review list` | Adds `question` on every entry (D-64). While a session is open, it adds `answers: [{key, disposition, by, at, via, comment, question}]`. After a session closes, it adds `last_answers` with the `except` and `questioned` entries of the latest acceptance (D-72). `--current` replaces `--stage` and `--kind` with the current review (D-61). When there is none, it returns `current: null` and exits `0`. |
| `review answer` | Adds `--shown HASH` (refused with `entry-changed` when it is not the entry's current hash; the refusal carries `current: {key, hash, what}`), `--question TEXT` (`question-mismatch` unless it is the helper's question for the entry) and `--comment TEXT`, stored verbatim. Adds `--section NAME` with `--rest`: accept the unanswered entries of that section only, recorded with `together` and `seen: true`. `--reopen` accepts every settled block of the stage on the `inferred` kind, and writes the `reopened` mark (D-65). |
| every `writes` subcommand | Holds the record lock for its read-modify-write (D-67). If the lock is busy for more than 5 s it exits `1` with `record-busy`, writing nothing. Writes replace the record file atomically. |
| `show`, `status` | A block with a `reopened` mark is `needs-review`. `show` adds "(reopened by NAME: COMMENT)" after the block's review cue. |

## New subcommands

| Subcommand | Kind | Behaviour |
|---|---|---|
| `review serve --by NAME [--host H] [--port P] [--public-name N] [--idle-minutes M]` | writes (through the page only) | Starts the page for the story and prints `{story, address, pid}` as one JSON line, then serves until stopped. Starting writes nothing to the project. It refuses with `ai-approval` for an AI name, `ambiguous-story` (003), `page-running` (with the running address) when a live runtime file exists for the story, and `port-unavailable`. |
| `review serve --status` | read-only | `{running: bool, address, pid, started_at}` from the runtime file after authenticating to its `GET /state`. An unverifiable file reports `running: false` and is removed (the file is outside the project). |
| `review serve --stop` | read-only for the project | Authenticates to `POST /stop`, ends the page process and removes the runtime file. It never signals the recorded pid. Answers already stored remain. |

## Page routes (served by `review serve`)

Every route checks:
- the `Host` header against `127.0.0.1`, `localhost`, the bound host and `--public-name`;
- the token: `?t=` on `GET /` and `GET /doc/<stage>`, and the `X-EIL-Token` header on everything else.

A failed check returns `403`, gives a short plain message and writes nothing. Every `POST` also requires an `Origin` header equal to the page's own origin and `Content-Type: application/json`. Any other method returns `405`.

| Route | Kind | Behaviour |
|---|---|---|
| `GET /?t=` | read | The current review's document, rendered, with answer controls on the listed entries, the counter, "Answering as NAME", the embedded state (D-68) and the token in a `<meta>` element |
| `GET /doc/<stage>?t=` | read | Another stage document of the story, read-only. `<stage>` is one of the nine stage names. Anything else returns `404`. |
| `GET /state` | read | `{current, doc, entries, answers}` (D-68). Does not count as use for the idle stop. |
| `POST /answer` | write | `{stage, kind, entry, disposition, shown, question, comment}`. Calls `reviews.answer(entry=…, via="page")` under the lock. Refused with `not-current` when stage and kind are not the current review. Returns the helper's result or refusals unchanged. |
| `POST /section` | write | `{stage, kind, section, shown: {entry: hash}}`. Under the record lock, refuses with `entry-changed` if any unanswered target is absent or no longer has its shown hash; otherwise calls `reviews.answer(rest=True, section=…, via="page")`. |
| `POST /reopen` | write | `{stage, key, shown, comment}`. Calls `reviews.answer(reopen=[key], …, via="page")`. A comment is required (`comment-required`). Allowed only on the current review's stage. |
| `POST /name` | process | `{name}`. Changes the in-memory name. An AI name is refused with `ai-approval`. Nothing is written to the project. |
| `POST /stop` | process | Authenticated lifecycle request used by `review serve --stop`. Schedules a clean server shutdown and writes nothing to the project. |

No other path is served. No static file is read from disk: the CSS and script are constants. Every response carries the Content-Security-Policy of D-69, `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer` and `Cache-Control: no-store`.

## Refusal codes added

`entry-changed`, `question-mismatch`, `comment-required`, `not-current`, `record-busy`, `page-running`, `port-unavailable`.

## Determinism requirements 54 to 69

54. A `POST /answer` with no token, a wrong token, an `Origin` of `http://evil.example`, no `Origin`, or a `Host` of `attacker.example` returns `403`. `eil-record.json` is byte-identical afterwards, and no lock file remains.
55. `GET /doc/../../etc/passwd`, `GET /doc/notastage`, `GET /eil-record.json` and `GET /static/x.js` return `404` or `403` and read no file outside the story's stage documents (the test patches `Path.read_bytes` to record every path read).
56. With an entry shown at hash H, editing the block so its hash is H', then answering with `shown: H`, exits with `entry-changed`. The record is byte-identical, and the refusal's `current.hash` is H'.
57. The same five answers (three accept, one send back, one question), given once through `POST /answer` and once through `review answer --entry` on identical copies of a fixture, produce the same settled blocks, the same `questioned` and `except` keys and the same block statuses. The two record files differ only in `via`, `questions`, `comments`, the reply wording, ids and times.
58. `review list` returns, for each kind of entry in the D-64 table, exactly the table's question. `--question` with any other text is refused with `question-mismatch`.
59. On a 12-entry list in three sections, answering two entries of section A individually and then `--rest --section A` stores `accept` with `together: A` and `seen: true` for A's other entries only. B and C have no answers, and A's two earlier answers are unchanged.
60. `POST /answer` with accept from a person who is not a confirmer is refused with `not-a-confirmer`, as `review answer --entry` is. `POST /name` with "Claude", "AI" or "assistant" is refused with `ai-approval`, and the name is unchanged.
61. A comment on a restated, settled block writes `reopened` with the comment verbatim. The block is then `needs-review`, appears on `review list --kind inferred`, and has an unchanged fingerprint and class. Accepting it removes `reopened`.
62. `review list --current` names, in turn: `requirements/inferred` on a fresh story, `functional/inferred` after Requirements is approved, `requirements/changes` after an approved Requirements block is edited, and `null` once Technical is approved and the current stage is `ai-spec`.
63. A block containing `<script>alert(1)</script>`, a comment of `<img src=x onerror=alert(1)>` and a name of `"><b>x` appear in the page HTML only escaped. The page has no inline event handler attributes and exactly one `<script>` element without `src`, carrying the nonce.
64. Without `review.diagram_script`, the page contains no URL with a scheme other than its own origin, and the CSP `script-src` is `'self' 'nonce-…'`. With `review.diagram_script: https://cdn.example/m.mjs`, the page names that URL once in text, and the CSP `script-src` adds exactly `https://cdn.example`.
65. With `idle_minutes` patched to a short value, a server receiving only `GET /state` stops. One receiving a `GET /` within the period does not. After the stop, every stored answer is still in `eil-record.json` and `review list` resumes the session.
66. `GET /state` reflects a block edit and an answer stored through the CLI on the next call. The page's poll interval constant is at most 5000 ms. The `GET /` HTML embeds the same state it was rendered from.
67. Twenty concurrent writes, half `review answer --entry` in subprocesses and half `POST /answer`, each to a different entry, all end up stored. The record file is valid JSON afterwards, and no lock file remains.
68. `review serve` start, `--status` and `--stop` leave every file under the project byte-identical. The runtime file is outside the project, with mode `0600` on POSIX.
69. On a summary-mode list (9 or more entries), `POST /answer` opens a session in summary mode, and `review list` afterwards returns the unanswered entries. A whole-list `review answer --all` then answers what remains, as in 003.

## Unchanged

Approval is untouched: `approve`, `review confirm` and every gate keep their 001 to 003 behaviour, and no page route reaches them (FR-020). `review answer` without the new flags behaves exactly as in 003.
