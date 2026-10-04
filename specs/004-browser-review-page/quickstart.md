# Quickstart: validating the Browser Review Page

This is a run guide. The behaviour each step proves is defined in [contracts/cli.md](contracts/cli.md) (routes and determinism 54 to 69), [contracts/page.md](contracts/page.md) and [contracts/commands.md](contracts/commands.md).

## Prerequisites

- Python 3.11+, with `pytest` and `ruff` for development, as for 001 to 003.
- A current desktop browser for the manual check.
- The repository's test fixtures. The new scenario tests build their stories with the existing fixture helpers (`tests/fixtures`).

## Automated

```bash
python3 -m pytest tests/unit -k "page or serve or entry_question or reopen or record_lock or current_review"
python3 -m pytest tests/scenario -k "b38 or b39 or b40 or b41 or b42 or b43 or b44"
python3 -m pytest tests/contract/test_prompt_guidance.py
python3 -m pytest            # the whole suite: every 001 to 003 refusal still refuses (SC-005)
ruff check .
```

The page tests start the server in a thread on a free port and talk to it with `urllib.request`. No browser is needed.

## Scenarios

| ID | Story | What it runs | Expected |
|---|---|---|---|
| B-38 | US1 | A Functional draft with 5 listed blocks. Through `POST /answer`: 3 accept, 1 send back with a comment, 1 question with a comment. | Five session answers, each with `via: page`, the fixed question, the name, the time and the comment verbatim. On the fifth, the session closes into acceptances that carry `via`, `questions` and `comments`. Block statuses equal those of the same answers given with `review answer --entry` (determinism 57; SC-001). |
| B-39 | US2 | After B-38: `review list --current`, then edit the sent-back block, then `GET /`. | `last_answers` holds the send-back and the question with comments and the name. After the edit, the sent-back block is listed and highlighted. The questioned block is still listed. A `POST /reopen` on a settled block lists it with `reopened`. |
| B-40 | US3 | The attacks of determinism 54 and 55, a stale answer (56), and a `0.0.0.0` start without `--host`. | Every attack is refused and the record file is byte-identical (SC-002). The default bind is `127.0.0.1`. |
| B-41 | US4 | A Functional stage citing `REQ-004` (defined once), `REQ-099` (undefined) and `DEC-002` (defined twice), with one `mermaid` fence, rendered with and without `review.diagram_script`. | REQ-004 links to `/doc/requirements#REQ-004` with a preview. REQ-099 and DEC-002 carry the error mark. The diagram source is always present, and the script and CSP follow determinism 64. |
| B-42 | US5 | Determinism 59 on a 12-entry list. | As stated there. |
| B-43 | US6 | An approved Functional stage with two changed items. Through the page: accept one, send back one. Then `review confirm` in the CLI. | `current` is `functional/changes`. The re-sign is refused, as after the same answers in chat. After rework and an accept on the page, it proceeds. |
| B-44 | FR-013 | A 6-entry list: 3 answered on the page, then `review list` and `review answer --entry` for the rest in the CLI. | No entry is asked twice. The session closes once, with page and chat groups recorded as separate acceptances. |

## Manual check on a scratch project

1. Install the preset and extension into a scratch project, as in 003's quickstart, and draft a Requirements stage with the agent.
2. When asked, choose the page. Open the address. Check:
   - the whole document is shown;
   - only the listed blocks are highlighted, each with its question;
   - the counter matches `review list`.
3. Accept one block, send one back with a comment, then edit a third block in the editor. Within 5 seconds the notice names it. Answer it without reloading: the stale refusal appears in that control only.
4. Say "done" in chat. The agent reworks the send-back, says what changed and asks for a reload.
5. Leave the page idle past `review.page_idle_minutes` (set to 1 for this check). The next answer shows "The review page has stopped". `review list` still holds the stored answers.
6. Stop the server with `eil review serve --stop`. Check that `git status` shows only `eil-record.json` and the documents the agent edited, and no runtime or lock file.

## Trial probes (human, `docs/trials.md`)

| Probe | Checks |
|---|---|
| P-32 | The surface is asked once per session, with its purpose, and not again unless the person asks |
| P-33 | With the page chosen, the agent gives the address, does not print the list, and does nothing with the review before "done". The agent makes no request to the page address itself (check the transcript's shell commands) |
| P-34 | After "done", each send-back is reworked with what changed, each question is answered in chat, and the agent asks for a reload rather than recording an answer in chat |
| P-35 | When the page cannot start, the agent says why in one line and reviews in chat |
| SC-004 | The timed run: Requirements, Functional and Technical reviewed on the page for a story comparable to the trial's story 002, compared with 003's chat review |
