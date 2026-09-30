# Contract delta: slash command behaviour

Changes to [001 contracts/commands.md](../../001-staged-definition-workflow/contracts/commands.md). The per-command invariants there still hold. Every gate or record below is a helper call; prompt text only presents and relays (Constitution I). The behavioural rules added to prompts are listed at the end with their contract test.

## The one-reply list (used by every command that asks a person to review)

1. Run `eil review list --stage S --kind K --json`.
2. Show the `purpose` first, then each entry: its key, what it is or what changed, why it is on the list and any `ai_view` (already labelled), then the `limits` lines.
3. Ask for **one** reply: "ok to all", "ok except <ids>", or a question about one id. Do not walk the entries one at a time.
4. Call `eil review answer` with the list's `digest`, the person's name, their words **verbatim** as `--reply`, and the flags the reply means. Never supply, complete or improve the reply. For kind `changes` (and an `inferred` entry under an open correction), also pass the one-line summaries shown with the entries as `--summaries`; they are labelled AI-drafted and become the Change Log text.
5. On `list-changed`, show the new list and ask again. On `reply-mismatch`, re-read the person's reply and pass the flags it actually means; never change the reply. On a question, answer it, then offer the remaining list again. On `acceptance-conflict`, show both answers and ask a confirmer to answer again.

## New and changed extension commands

| Command | Change |
|---|---|
| `speckit.eil.accept` (new) | Accept changes to a previously approved stage (FR-015). Every change, covered or not, is shown with a one-line summary drafted by the AI and labelled as such. Show the helper's explanation of **covered** changes (each change and the decision covering it) and pass their summaries to `eil review confirm --summaries`. If there is no uncovered change, ask for a sign-off ("ok" is enough) and `eil review confirm`. Otherwise run the one-reply list of kind `changes` (its summaries go to `review answer --summaries`), then the delta comprehension check if the helper requires it, then one confirmation. For a correction owned by a never-approved stage (ai-spec, plan, tasks, verification): run its `inferred` list if the item is on it, then ask for the sign-off and `eil review confirm`, which closes the correction and writes no approval. After confirm, show any `unsettled-challenges` list |
| `speckit.eil.correct` (new) | Report a problem in an earlier artefact from any later stage (FR-021). Take the problem, the item and, if the person gives it, the corrected wording. `eil correct propose`, then show the owning stage, the edit (the person's wording, or a draft by the AI, labelled as such) and the impact list, before anything is applied. Ask which stage owns it **only** if `ambiguous`. On agreement, `eil correct open`. **Person's wording**: pass it verbatim as `--wording`, apply it in place with `(decided: CR-###)`, then run `speckit.eil.accept`, where the change is covered and needs only the sign-off (SC-005: report, agreement, sign-off). **AI-drafted wording**: apply it without a `(decided: …)` clause; it is an uncovered change on the `changes` list of `speckit.eil.accept`. Never pass AI text as `--wording` |
| `speckit.eil.amend`, `speckit.eil.review` | Become short aliases that say they are superseded and run `speckit.eil.accept` |
| Drafting commands (`requirements`, `functional`, `technical`, `ai-spec`) | Write each block with a citation when it restates a settled source (spec FR-009). Never hand-write `[ai-draft]`. After drafting, write the classification file and run `eil blocks classify`, then `eil check`, the challenge pass (each challenge with `--severity`), and the one-reply list of kind `inferred` |
| `speckit.eil.approve` | Present the gate with unmet and judgment criteria first and the met structural count on one line (`check` text output). Before asking for the attestation, run the `inferred` list if it is not empty. State open low challenges as outstanding |
| `speckit.eil.challenge` | Present challenges high first. Offer a severity change (`eil challenge severity`) and record who changed it |
| `speckit.eil.complete` | Run the `low-challenges`, `evidence`, `tasks` and `diagram-currency` lists (only for those that are non-empty), each as one reply. List untouched artefacts without a question. For an accepted design/code difference, open a correction with origin `completion` so the design is corrected rather than annotated (FR-045) |
| `speckit.eil.verify` | After drafting evidence rows, write the classification file and run `eil blocks classify --stage verification` and the `inferred` list, as every stage does (FR-012). Record code-review findings as `RF` items under `## Review Findings`, asking the person for each finding's root. For an upstream root, hand off to `speckit.eil.correct` with the RF as the origin |
| `speckit.eil.status`, `speckit.eil.next` | Show `blocked_work`, open corrections, recent changes and the `purpose` of the next action |

## Preset wraps

| Command | Change |
|---|---|
| `speckit.plan`, `speckit.tasks` | Use `enter`'s `rederive` and `blocked`. With an existing document, re-derive **only** the `rederive` items, in place, leaving all other text byte-identical (FR-041); never derive from a `blocked` id. Then `blocks classify` and the `inferred` list |
| `speckit.implement` | `eil enter implement` once for the list; before each task, `eil enter implement --task T###`, and skip it on `work-blocked`, saying why and naming the fix. After ticking tasks, `eil sync`. If the helper reports a `tasks` list, offer it |
| `speckit.clarify` | An answer that affects only some items blocks only them (FR-025); say which tasks remain implementable |

## Behavioural rules added to prompts (Tier 2) and their checks

| Rule | Check |
|---|---|
| Present a list as one list and ask for one reply | Prompt contract test `test_prompt_guidance.py::test_one_reply_lists` (text of each command using a list) + trial probe P-20 |
| Pass the person's reply verbatim; never write a sign-off, reply or correction `--wording` on their behalf | Prompt contract test `::test_reply_verbatim` + trial probe P-21 |
| State the purpose before any request for attention | Prompt contract test `::test_purpose_stated` |
| Never hand-write or remove `[ai-draft]` | Prompt contract test `::test_no_manual_ai_draft`; the helper re-renders the cue anyway (D-33) |
| Re-derive only the listed stale items in place | Prompt contract test `::test_rederive_only_listed`; scenario B-24 checks that non-listed text is byte-identical |
| Draft a correction but apply it only after the person agrees | Prompt contract test `::test_correct_shows_before_apply` + trial probe P-22 |
| When re-editing an item that carries `(decided: CR-###)`, replace or remove the clause (keep it only if the new text is exactly that correction's recorded wording) | Prompt contract test `::test_decided_clause_removed_on_reedit` (text of `correct`, `accept`, the drafting commands and the `plan`/`tasks` wraps); the helper reports a clause left behind as non-blocking `decided-source-invalid` and treats the change as uncovered |
| Pass the AI's one-line change summaries as `--summaries`, labelled AI-drafted | Prompt contract test `::test_summaries_passed`; the helper refuses `summary-missing` anyway |
