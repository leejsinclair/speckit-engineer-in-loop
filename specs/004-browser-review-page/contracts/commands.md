# Commands contract delta: Browser Review Page

This is a delta to 003's `contracts/commands.md`. Anything not mentioned here is unchanged.

## Changes to the review step of `requirements`, `functional` and `technical`

The shared section "Presenting a review list" gains a subsection, "Reviewing on the page" (research D-71). In order:

1. **Choose the surface once per session.** At the first review step of a session, ask: "Review on a page in your browser, or here in chat?" Say that this is about how they review, not what they approve. Use the answer for every later review in the session. Ask again only if the person asks to change it.
2. **Page chosen:**
   - run `eil review serve --status --json`;
   - if it is not running, start it in the background with `eil review serve --by "<name>" --json` and read the address from its first line;
   - if it is running, tell the person to reload;
   - give the address, say which stage and list it shows, and ask them to answer there and say "done";
   - **do not print the list in chat**, and do not act on the review until they say done;
   - never open, fetch or post to the page address yourself. Give it to the person only;
   - pass `--host` only when the person asks for another address, for example in a container.
3. **After "done":**
   - run `eil review list --current --json`;
   - for each send-back in `last_answers` or `answers`: show the comment, rework the block, and say what changed;
   - for each question: answer it in chat, or raise a challenge if the document is wrong, and rework the block if the answer changes it;
   - then ask the person to reload the page and answer those blocks there;
   - never record a page-surface entry's answer in chat with `review answer`;
   - when the list is empty, continue the stage (the comprehension check, then approval in chat, as now).
4. **A comment on a settled block** arrives as a reopened entry on the list, with its comment. Act on it as on a send-back.
5. **The page cannot start** (any refusal), or the person cannot reach the address: say why in one line and review in chat exactly as in 003. If the person asks to switch surface mid-list, run `review list` and continue in chat. The helper's session already holds what was answered.
6. **Name**: pass the name the person gave in chat (asked at most once per session, 003). Never pass the AI's name. The page shows "Answering as <name>" and lets the person change it there.

Approval, overrides, waivers and the comprehension check stay in chat. The prompts never send the person to the page for them.

## Command-by-command

| Command | Change |
|---|---|
| `speckit.eil.requirements` | Review step: "Reviewing on the page" (above) for the `inferred` list and, when re-approving, the `changes` list |
| `speckit.eil.functional` | Same; the gap scan still runs before the page is offered |
| `speckit.eil.technical` | Same |
| `speckit.eil.accept` | When the stage is one of the three and the page is the chosen surface, it hands the `changes` review to the page as above. Other stages are unchanged. |
| `speckit.eil.status`, `speckit.eil.next` | When `review serve --status` reports a running page, mention its address in one line |
| others | Unchanged (FR-019) |

## Tier 2 rules added: contract test and probe

| Rule | Prompt(s) | Contract test (`tests/contract/test_prompt_guidance.py`) | Probe (`docs/trials.md`) |
|---|---|---|---|
| Surface asked once per session, with its purpose; never asked again unless the person asks | requirements, functional, technical, accept | `test_review_surface_asked_once` | P-32 |
| On the page: address given, list not printed, nothing acted on before "done" | requirements, functional, technical, accept | `test_page_review_waits_for_done` | P-33 |
| After "done": send-backs reworked with what changed; questions answered in chat, then answered on the page after a reload; no chat answer recorded for a page-surface entry | requirements, functional, technical, accept | `test_page_answers_acted_on` | P-34 |
| The agent never opens, fetches or posts to the page address; it only gives it to the person (research R-29) | requirements, functional, technical, accept | `test_agent_never_uses_page` | P-33 (extended: no request to the page address in the transcript's shell commands) |
| The page cannot start: one line why, then the 003 chat review | requirements, functional, technical, accept | `test_page_fallback_to_chat` | P-35 |
| Approval, overrides and waivers never sent to the page | requirements, functional, technical, approve | `test_approval_stays_in_chat` | none (no page route exists for them; determinism 54 and the route table pin it) |
