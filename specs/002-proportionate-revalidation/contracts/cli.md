# Contract delta: the `eil` helper CLI

Changes to [001 contracts/cli.md](../../001-staged-definition-workflow/contracts/cli.md). Global behaviour (output, exit codes, the not-governed rule, idempotence, the refusal shape) is unchanged. On implementation, this delta is folded into the 001 file in the same pull request as the tests that pin it (Constitution, Development Workflow).

## New subcommands

| Subcommand | Purpose | Writes | Refuses when (`code`) |
|---|---|---|---|
| `blocks list --stage S [--status ST]` | Every content block with key, class, derived status and, for derived stages, stale sources (D-31 to D-34) | none | never refuses |
| `blocks classify --stage S --file PATH` | Merge the AI's classification verdicts (D-32); recompute classes; re-render `[ai-draft]` cues | `provenance`, cue tags, `s00` | exit `2`: unknown block key, stage mismatch, unknown top-level key, not JSON |
| `blocks reclassify --stage S --block KEY --to inferred --by N [--reason R]` | Mark a restated block inferred (FR-013). Anyone may do this | `provenance`, cue tags | `unknown-item`; `not-restated` |
| `review list --stage S --kind K [--views FILE]` | Compute one review list (D-36). `--views` carries the AI's per-entry views (`{"stage","kind","views":[{"key","view"}]}`, verdicts only, like `--judgments`); each is shown prefixed `AI assessment:`. `K` is `inferred`, `changes`, `tasks`, `evidence`, `low-challenges`, `unknown-currency`, `diagram-currency` or `unsettled-challenges`. Output: `{kind, stage, purpose, entries[], digest, limits[]}` | none | `not-amendable` (`changes` on a stage never approved) |
| `review answer --stage S --kind K [--digest D] --by N --reply TEXT (--all \| --all-except IDS \| --question ID \| --reopen IDS) [--defer-reason R] [--summaries FILE]` | Record one reply to the list the person saw. `--digest` is required for a settling answer. A `--question` or `--reopen` answer may omit it and name any entry of that kind settled for the stage since its last approval (`changes`) or since it was recorded (other kinds) (D-36, FR-050). `--summaries` (kind `changes`, and kind `inferred` for an item under an open CR; same shape as on `confirm`): the AI's one-line summary per accepted change, shown in the list before the reply, becoming the Change Log text (D-39) | `provenance`, cue tags, challenge records (`low-challenges`), `s00` | `list-changed` (digest mismatch); `not-a-confirmer` (a settling answer by a non-confirmer, FR-048); `ai-approval`; `reply-required`; `reason-required` (deferral without a reason); `digest-required` (a settling answer without `--digest`); `unknown-item` (an id neither on the list nor, for question or reopen, a settled entry of that kind); `reply-mismatch` (a bare all-phrase reply without `--all`, or `--all` with a reply naming an entry key on the list, D-36). A settling answer on the `inferred` list also answers the `changes` entry for the same item at the same content hash, so it is not listed again (D-45). A different person's opposite answer to the same entry is recorded and marks it `conflict` (FR-050), not a refusal |
| `review confirm --stage S --by N --confirmation TEXT [--summaries FILE]` | Re-sign a previously approved stage (D-37). All changes covered: `reached: carried-forward`, and TEXT may be "ok". Otherwise `reached: reviewed`. `--summaries` (`{"stage","summaries":[{"key","summary"}]}`): the AI's one-line summary per change, shown before the sign-off, becoming the Change Log text (D-39). A summary may come from this flag or from `review answer --summaries`; any change, covered or uncovered, with no summary from either refuses `summary-missing`, so every change gets its Change Log entry (FR-043). On a never-approved stage (ai-spec, plan, tasks, verification) with an open CR, it closes each open CR whose item is settled (an open CR whose item is not yet settled stays open; the close is partial), writing its Change Log entry, and writes no approval (D-38) | `approval` (approvable stages only), `provenance` (`changes[]`, CR closure), `changelog`, `s00` | `changes-unanswered` (an uncovered change has no acceptance); `acceptance-conflict` (an entry is in conflict, FR-050); `comprehension-prerequisites` (an inferred uncovered change and the delta check not current, FR-019); `not-amendable` (never approved and no open CR; or, on a never-approved stage, an open CR whose item is not yet settled); `not-a-confirmer`; `ai-approval`; `confirmation-required` (empty); `summary-missing` (a change has no AI summary) |
| `correct propose --item ID --found-in STAGE[:ID] --problem TEXT` | Owning-stage candidates, `ambiguous`, impact list (D-38). Read-only | none | `unknown-item` |
| `correct open --item ID --found-in STAGE[:ID] --problem TEXT --by N [--owner STAGE] [--wording TEXT]` | Record `CR-###` in the owning stage. `--wording` is the person's corrected text, verbatim; with it, the CR can back a `(decided: CR-###)` clause (contracts/document-format.md) | `provenance`, `s00` | `owner-ambiguous` (several candidates and no `--owner`); `owner-not-candidate`; `unknown-item`; `ai-approval` (as the opener's name) |
| `challenge severity ID --to high\|medium\|low --by N` | Change a challenge's severity (D-40). Lowering needs a confirmer, raising does not | stage doc (challenge record) | `not-a-confirmer` (lowering); `ai-approval` (lowering); `unknown-item` |

## Changed subcommands

| Subcommand | Change |
|---|---|
| `enter plan\|tasks\|implement [--task T###]` | Work-scoped (D-35). Success output adds `blocked[]` (`{id, because[], fix}`) and `rederive[]`. `stage-not-approved` now means "never approved". A `needs-re-review` stage does not refuse. New refusal `work-blocked`: a named `--task` is blocked, or nothing may proceed. `pending-clarification` and `ai-spec-not-traceable` become per-item entries in `blocked[]` and refuse only through `work-blocked` |
| `approve S` | `unreviewed-ai-content` is decided by block status, not tag presence (D-33). For `approve completion` it also covers unreviewed inferred blocks in s07 (spec FR-049). `open-challenge` counts only high and medium; open low ones are written to `outstanding`. The record gains `reached: first` and `blocks` |
| `challenge add … --severity high\|medium\|low` | `--severity` is required when `--by` is the AI (default `ai`); a person may omit it (reads as `medium`). A duplicate of an open challenge now returns the existing id in `refusals[0].existing` |
| `check [--full]` | Criteria ordered unmet, then judgment, then met. `summary.met_structural` is added. Text output collapses met structural criteria unless `--full`. New criterion `VER-G07` (no open `RF`). `AIS-G03` becomes item-scoped (it reports pending ids and is met for gating purposes by D-35) |
| `sync` | Additionally: adopt existing documents on first run (D-42); snapshot newly ticked tasks (`completed_against`); re-render `[ai-draft]` cues and the `changelog` region |
| `status` | Per stage, adds `blocks: {settled, needs_review, stale, unknown}` (`source-changed` blocks are counted under `stale`), `outstanding_low[]`, `diagram_currency: {touched, untouched}`, `outstanding.deferred_challenges[]`, `approval.reached` and `approval.rests_on`. Top level adds `blocked_work[]`, `corrections[]` (open) and `recent_changes[]` (latest 5). `next_action` gains `purpose` |
| `trace --to ID` | Shows any `CR` whose item is on the chain, with its origin (FR-024) |
| `review start\|accept\|finish` | Kept as compatibility aliases (D-36): `start` = `list --kind changes`; `accept` = `answer --all-except` over the named items; `finish` = `confirm`. The aliases keep their historical records: `accept` writes `eil:review` records and `(decided: RVW-###)` on the item, where `review answer` writes an acceptance in the provenance region; `finish` records `reviewed_change_by_change` and `reviewed_ids` as well as `reached` and `rests_on`. `finish` is not byte-identical to `confirm` and needs no AI summary (no Change Log entry is written by the aliases) |
| `amend S --from IDS …` | Kept. The ids must be a subset of the covering decisions the helper finds (`change_rows`' `covered_by`, plus the ids of section reviews for the stage); an id outside it refuses `amend-not-covering` and writes nothing. Otherwise identical to `confirm` |

## New refusal codes (stable)

`list-changed`, `digest-required`, `reply-required`, `reply-mismatch`, `acceptance-conflict`, `changes-unanswered`, `confirmation-required`, `owner-ambiguous`, `owner-not-candidate`, `not-restated`, `work-blocked`, `review-finding-open`, `summary-missing`, `amend-not-covering`.

## New finding codes (reported by `check` and `status`)

`malformed-provenance`, `block-needs-review`, `source-changed`, `stale`, `unknown-currency`, `completed-while-blocked`, `evidence-for-earlier-version`, `task-completed-against-earlier-version`, `challenge-possibly-unsettled`, `correction-wording-mismatch`.

## `enter` success shape

```json
{"ok": true, "command": "implement",
 "blocked": [{"id": "T014", "because": ["DEC-003 changed since T014 was derived (stale via AIS-011)"],
              "fix": "/speckit-eil-accept technical, then re-derive AIS-011"}],
 "rederive": ["AIS-011"], "alias_faults": [], "aliases": [], "text": "May proceed with implement except T014."}
```

## `review list` shape

```json
{"kind": "inferred", "stage": "ai-spec", "purpose": "validation",
 "entries": [{"key": "AIS-007", "what": "<full block text>",
              "why": "adds beyond DEC-002", "ai_view": "AI assessment: adds a retry policy of 3 attempts"}],
 "digest": "sha256:…",
 "limits": ["Restated content is checked against its source by hash; the check cannot prove two wordings mean the same (FR-014).",
            "Your reply is recorded word for word; the helper checks only obvious mismatches between it and what is recorded as accepted."]}
```

For `changes`, entries carry `covered_by` (a decision or acceptance id) or `inferred: true`. For `inferred`, an entry whose item is under an open correction carries `correction` (the `CR` id), so the prompt knows to pass its summary. When any entry is covered by a `CR`, `limits[]` also carries: "Correction wording is recorded as given; the tool cannot tell who wrote it." For `tasks`, entries carry `ai_view` (whether the code is likely still valid) and are ordered likely-rework first. For `evidence`, entries carry `confirmed: false` and the reason. For `low-challenges`, entries carry `severity`.

## Determinism requirements (each has a unit test)

22. Block splitting follows FR-039 exactly: a numbered item with its continuation lines is one block; a table, diagram or fence is one block; headings, HTML comments and marked regions are none. Rewrapping a paragraph, or changing only whitespace, leaves every block hash unchanged.
23. Inserting a paragraph into a section changes the status of that paragraph only (D-31).
24. A block citing a settled, unchanged source with no AI `adds` is `restated`; the same block with `adds`, with no citation, with no verdict at all, or citing an unsettled source is `inferred` (D-32). A source in s01 to s03 is settled when its approval covers it; a source in s04 to s06 when its own block status is `settled` and it is not stale: a plan section restating a settled AIS item is `restated`, and one restating a stale or unreviewed inferred AIS item is `inferred`.
25. Adding or removing `[ai-draft]` by hand changes no block's status; the next `sync` re-renders the cue to match the recorded status (FR-046).
26. Changing one DEC marks exactly the blocks that trace to it, directly or transitively, as `stale` or `source-changed`. Reverting the change restores the previous statuses with no command run (FR-002, spec Edge Cases).
27. `enter implement --task T` exits `0` for a task tracing only to settled, current sources, and exits `1` `work-blocked` naming the changed source otherwise (SC-002).
28. `review answer` with a digest that no longer matches exits `1` `list-changed` and writes nothing.
29. A settling `review answer` from a person not configured for the stage, or from the AI, exits `1` and writes nothing. A `--question` or `--reopen` from anyone succeeds and records the name.
30. `review confirm` with every change covered records `reached: carried-forward` from a confirmation of "ok", asks for no comprehension, and writes nothing else to the prose (SC-004). A change carrying `(decided: CR-###)` counts as covered only when the CR has a `wording` equal to the item's text (compared as document-format.md says); otherwise it is the non-blocking finding `correction-wording-mismatch` and uncovered, while a `(decided: CR-999)` naming no CR stays a blocking integrity finding. A change, covered or uncovered, with no summary from `review answer --summaries` or `review confirm --summaries` refuses `summary-missing`, and nothing is written. On `ai-spec` with an open CR whose item is settled, `confirm` closes the CR, writes its Change Log entry and writes no `approval`; with the item unsettled, or no open CR, it refuses `not-amendable`.
31. `approve` succeeds with only low open challenges and records them in `outstanding`. It refuses with a medium or high one. A record with no severity counts as medium.
32. The first `sync` on an approved, unchanged 001-era document records every block as adopted, and the stage's derived state before and after is identical. `status` run before that `sync` reports the same statuses (D-42).
33. `status` and `check` leave the provenance and changelog regions byte-identical (they remain read-only).
34. An EVD row naming `tests/unit/test_x.py::test_y` is confirmed when that file contains `def test_y`, and unconfirmed when it does not. No subprocess is started (FR-034, FR-035).
35. `review answer --reply "ok" --all-except T014` and `--all --reply "ok except T014"` (T014 on the list) each exit `1` `reply-mismatch` and write nothing; `--all --reply "ok to all."` and `--all --reply "ok to all, but note the typo"` succeed.
36. After Ada accepts FR-013, Priya's `--reopen FR-013` with no digest succeeds although FR-013 is no longer on the list, and leaves it `conflict`; a settling answer with no digest exits `1` `digest-required`; `confirm` exits `1` `acceptance-conflict`; a confirmer's new answer clears it and records `resolved_conflict`.
37. Adding an `RF` item to s07 after completion was approved makes `status` report completion `needs-re-review`; an unrelated edit to s07 does not.
