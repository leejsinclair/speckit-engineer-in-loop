# CLI contract delta: Proportionate Effort

This file is a delta to 001 `contracts/cli.md`, as amended by 002. Anything not mentioned here is unchanged. It is folded into 001's file in the same pull request as the tests that pin it (constitution, workflow).

## Every subcommand

- Each subcommand is declared in one table as `writes` or `read-only`:
  - **read-only**: `status`, `show`, `trace`, `fingerprint`, `blocks list`, `review list`, `review show`, `comprehension plan`, `check` without `--judgments`, and `enter`, which records nothing.
  - **writes**: every other subcommand.
- Every result has `story` (the target directory's name). The text form begins `Story <name>: `.
- A `writes` call whose target comes from the pointer, or from nothing, exits `1` with `ambiguous-story` when the target is ambiguous (data-model §Story target). It does so before reading any document for modification. The refusal names each candidate, and its fix is `--feature-dir <dir>` or `eil start`.

## Changed subcommands

| Subcommand | Change |
|---|---|
| `start` | Always writes `.specify/feature.json`, and returns `pointer: {previous, current}`. Branch guard: exits `1` `unexpected-branch` (naming the branch) unless the branch is in `main_branches` or is named for the new story. `--on-branch <branch> --by <name> --reply <words>` confirms the branch and records the reply with the helper's fixed question. The refusal returns that question. With no repository or a detached HEAD, it proceeds and returns `branch: null` with a note. |
| `sync` | Migration (idempotent): moves JSON region bodies into `eil-record.json`, renders region lines, and strips `[ai-draft]` tags. |
| `blocks classify` | Additive (D-57): blocks left out are kept when their hash is unchanged. Unknown keys go under `skipped: [{key, section, current_keys[]}]` and do not fail the call. Exit `0` if at least one key was recorded, otherwise `2` `nothing-classified`. |
| `review list` | Adds `mode`, `threshold` and `groups`, with `summary` per entry and scaffolding entries `§<Section>`. If a session is open for the digest, it returns the session's mode and only its unanswered entries. `--stage derived` requires an active profile, otherwise exit `1` `no-profile`. |
| `review answer` | Adds `--entry KEY` (one entry) and `--rest` ("ok to the rest", recording `seen: false`). Both write to the session. The existing whole-list flags are unchanged and still close the list in one call. `--entry` with a key not on the list exits `1` `unknown-entry`. |
| `review confirm` | Accepts the `legacy:<stage>` entry. The approval is recorded with `reached: re-signed-without-comparison`. |
| `accept` (prompt path) | Never refuses `no-section-fingerprints`. It lists the `legacy:<stage>` entry instead. |
| `comprehension plan` | Adds `--by <person>`, excluding their own decisions (D-54). A level may be planned as `own-decision` with `items`. Under the profile, `levels` holds `explain` and `apply`, and the rest are `not-applicable` with reason `small-story profile`. |
| `comprehension record` | Accepts `--outcome own-decision` only when the plan for that level says so. Otherwise exit `1` `not-own-decision`. |
| `check` | Technical: an `ai-decided` DEC needs `Reason:` (finding `ai-decided-without-reason`). Plan: headings in `ADMINISTRATIVE_SECTIONS` are never `plan-not-derivable`. Functional: under the profile, the wireframe criterion is met with reason `small-story profile (by, at)`. |
| `enter` | Under the profile: `plan` and `tasks` proceed because of the override the profile recorded (listed in the result's `overrides_used`); `implement` refuses until the `derived` list is answered. |
| `approve`, `review confirm` | Record `question` (from the helper's table for the stage) beside the verbatim attestation. Any non-empty reply is accepted, as before. |
| `status` | `next_action.question` holds the stage's approval question when the next step is an approval. Adds the stage state `reviewed`. When completion is approved, `next_action.kind` is `done` and the text is "Story complete; approved by X on DATE." It reports `approval-record-missing` and `malformed-record-file`. |

## New subcommands

| Subcommand | Kind | Behaviour |
|---|---|---|
| `show <stage> [--items IDS] [--section NAME]` | read-only | Prints the clean view (D-49). JSON: `{story, stage, text, blocks:[{key, status, first_line, last_line}]}`. An unknown id gives exit `1` `unknown-item`. |
| `review show --stage S --kind K (--entry KEY \| --group NAME \| --all)` | read-only | Full text of entries, in chat. |
| `profile set small --by NAME --reason TEXT` | writes | Also records the scoped override of `unreviewed-ai-content` (plan and tasks entry). Exit `1` with `not-an-authoriser`, `reason-required` or `profile-active`. |
| `profile withdraw --by NAME --reason TEXT` | writes | Exit `1` with `not-an-authoriser`, `reason-required` or `no-profile`. |
| `comprehension waive --stage S --by NAME --reason TEXT` | writes | Records every level not yet recorded as `skipped` with `waived: true` and the helper's fixed `question`. Exit `1` with `reason-required`, or `nothing-to-waive` when all five levels are recorded. |

## Refusal codes added

`ambiguous-story`, `unexpected-branch`, `no-profile`, `profile-active`, `unknown-entry`, `not-own-decision`, `nothing-to-waive`, `nothing-classified`, `approval-record-missing`, `malformed-record-file`, `ai-decided-without-reason`.

## Determinism requirements 38 to 53

38. With the pointer on completed story A and story B in progress, every `writes` subcommand called with no `--feature-dir` exits `1` `ambiguous-story`, and every file in A and B is byte-identical afterwards. Every `read-only` subcommand exits `0` and names A.
39. `start` for B with the pointer on A writes the pointer to B and returns `pointer.previous` = A.
40. Every subcommand's JSON result carries `story`. The test walks the subcommand table.
41. `start` on branch `001-x` for story `002-y` exits `1` `unexpected-branch`. It succeeds on `main`, on `002-y`, on `002-other`, and with `--on-branch 001-x --by Ada`, which records the confirmation. It succeeds outside a repository with `branch: null`.
42. After `sync`, no stage document contains JSON inside a region, and `fingerprint` of every stage document is unchanged from before `sync`.
43. `status` on a story whose records are half-migrated reads both forms and leaves every file byte-identical.
44. Deleting `eil-record.json` makes every approved stage `needs-re-review` with reason "approval record missing or unreadable". It never stays `approved`.
45. `show functional` contains no line of any region body other than the rendered lines, and no HTML comment. It shows `[ai-draft]` after the first line of exactly the blocks whose status is `needs-review`.
46. A list of 8 entries has `mode: one-at-a-time`. One of 9 has `summary`. With `review.one_at_a_time_max: 3`, a list of 4 has `summary`.
47. After `--entry` answers to 3 of 5 entries, `review list` returns the 2 unanswered entries in the same mode. Changing one answered entry's text makes it unanswered again. `--rest` closes the session and records `seen: false` for each remaining entry. A whole-list answer to a 9-entry list records `mode: summary` on its acceptance; an answer to a 5-entry list records `mode: one-at-a-time`.
48. No `review list` of any kind contains a block whose status is `settled` or `settled-pending`. A stage with 12 blocks under Actors yields one `§Actors` entry.
49. `blocks classify` with keys {A} after an earlier classification of {A, B} leaves B's entry unchanged. A key that no longer exists is returned in `skipped` with the section's current keys, and the call exits `0`.
50. On the `bd7a0d5`-shaped fixture (a legacy approval and a one-paragraph change), `status` reports 0 Functional blocks `needs-review`, the stage is `needs-re-review`, and `review list --kind changes` holds exactly one `legacy:functional` entry plus the changed blocks. After the confirmer's reply and `confirm`, every `adopted-pending` block is `adopted` and the approval's `reached` is `re-signed-without-comparison`.
51. `comprehension plan --by Ada` never targets a DEC owned by Ada whose block is settled. Where no other item is eligible for a level, that level is `own-decision` with that DEC's id. `comprehension waive` records each remaining level as `skipped` with the reason.
52. With the profile active, `check functional` reports the wireframe criterion met with reason `small-story profile`, `comprehension plan` names only `explain` and `apply`, and `enter implement` refuses while the `derived` list has an unanswered entry. `status` lists the profile's override with the authoriser's name and reason. After `profile withdraw`, all three revert for stages not yet approved and the override is shown as withdrawn.
53. `approve functional --attestation ok --by Ada` succeeds; the record holds `attestation: "ok"` and `question` equal to the helper's Functional question; `next_action.question` before it equals that question; the rendered approval line contains both.
