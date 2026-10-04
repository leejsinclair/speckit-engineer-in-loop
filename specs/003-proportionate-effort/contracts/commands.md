# Commands contract delta: Proportionate Effort

This file is a delta to 001 `contracts/commands.md`, as amended by 002. Prompts only call the helper and act on its exit code (Principle I). Every rule below that the helper cannot check is Tier 2: it is written as guidance and has the contract test and trial probe named in the last table.

## Changes to every stage command and wrap

- Read a stage with `eil show <stage>` (or `--items`), never by opening the stage document. Never read `eil-record.json`.
- Present a review list as the helper returns it, in its `mode`:
  - **one-at-a-time**: show each entry's full text in chat, ask for that entry's answer, and store it at once with `review answer --entry`. Offer "ok to the rest" (`--rest`).
  - **summary**: show the groups with each entry's summary and why it needs review, ask for one reply, and show full text on request (`review show`).
- Never keep a tally of answers in chat; the helper holds them.
- Never list blocks the helper did not return.
- Every `challenge add` example includes `--severity high|medium|low`, and the text says the severity is required.

## Command-by-command

| Command | Change |
|---|---|
| `speckit.specify` (wrap) | Never reuse `.specify/feature.json` when it names a governed story. Always pass `--feature-dir` to `eil start`. On `unexpected-branch`, show the branch and ask the developer to switch or confirm, then pass their name with `--on-branch`. May propose the small-story profile (below). |
| `speckit.eil.requirements` | Step 1 is the same as the wrap's. May propose the profile. |
| `speckit.eil.abbreviate` | "Do not suggest abbreviation" is replaced by: "you may propose the small-story profile or an abbreviation, naming the signals and labelling it AI assessment; only a person authorises". Adds the `profile set` and `withdraw` steps. |
| `speckit.eil.functional` | Never ask about mechanism; leave it to the Technical stage. Under the profile, do not ask for wireframe exports. Gap scan before the first list. |
| `speckit.eil.technical` | Ask only about choices with an observable effect, scope or trade-off, each with a recommended option. Record every other choice as `Owner: ai-decided` with `Reason:`. When unsure, ask. Name every `ai-decided` DEC in the stage summary. Gap scan before the first list. The rule "a technical decision is the developer's, never yours" is narrowed to observable choices. |
| `speckit.eil.comprehend` | Pass `--by` to `comprehension plan`. Before each question, show the item with `eil show --items`. Ask about behaviour. Judge on meaning, and re-read before hinting. Offer the one-line waiver (`comprehension waive`) when the person asks to stop. Never ask an `own-decision` level. |
| `speckit.eil.ai-spec`, `5-plan`, `6-tasks` | Under the profile, do not present each stage's list. After tasks, present the `derived` list once. |
| `speckit.eil.accept` | On a legacy approval, show the helper's statement and ask for the one reply. Never point to a full re-approval. |
| `speckit.eil.status`, `next` | Report `reviewed` and `done` as the helper gives them. |
| `speckit.eil.challenge` | `--severity` is required in every example. |
| `speckit.eil.approve`, `speckit.eil.complete`, `speckit.eil.accept` | Ask the helper's approval question (`next_action.question`) and nothing more. Accept "ok", "yes", "approved" or any reply as given. Do not ask for a longer statement or show full-sentence examples as required wording. Ask the name once per session. Never supply the reply; silence or "just approve it" is not a reply. |

## Proposing the small-story profile (Tier 2)

The command may propose the profile when it sees signals such as:
- a request that already states behaviour and acceptance in detail;
- few requirements;
- a change confined to one component.

It names the signals it saw and labels the proposal `AI assessment:`. It asks who authorises and why, and runs `profile set` only with the person's own words. When later work shows the story is larger (more than one container touched, new data stored, or more requirements than proposed), it says so and offers `profile withdraw`.

## Tier 2 rules added: contract test and probe

| Rule | Prompt(s) | Contract test (`tests/contract/test_prompt_guidance.py`) | Probe (`docs/trials.md`) |
|---|---|---|---|
| Profile proposed, never authorised by the AI | specify wrap, requirements, abbreviate | `test_profile_proposed_not_authorised` | P-23 |
| Mechanism not asked; `ai-decided` with reason; ask when unsure | functional, technical | `test_mechanism_not_asked` | P-24 |
| Item shown before each comprehension question | comprehend | `test_item_shown_before_question` | P-25 |
| Behaviour not mechanism; re-read before hint | comprehend | `test_behaviour_questions_and_reread` | P-26 |
| Gap scan before the first review list | functional, technical | `test_gap_scan_while_drafting` | P-27 |
| List presented in the helper's mode, no tally, answers stored per entry | every command that presents a list | `test_list_mode_no_tally` | P-28 |
| `show`, never the raw document or record file | every stage command and wrap | `test_show_not_raw` | P-29 |
| Challenge severity required | every command calling `challenge add` | `test_challenge_severity_written` | none (the helper refuses without it) |
| Approval asks the helper's question; a one-word reply is accepted; name asked once | approve, complete, accept | `test_short_approval_accepted` | P-31 |
| Pointer not reused for a governed story; branch confirmation asked of a person | specify wrap, requirements | `test_pointer_not_reused` | P-30 |
