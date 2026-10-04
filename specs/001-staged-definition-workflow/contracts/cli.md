# Contract: the `eil` helper CLI

The deterministic core (research D-04, D-05). Slash commands and preset wraps call it; it is also usable directly by a human or CI.

**Invocation**: `python3 .specify/extensions/eil/scripts/python/eil <subcommand> [options]`

**Working directory**: the project root. The feature directory is resolved as Spec Kit does: `--feature-dir`, else `SPECIFY_FEATURE_DIRECTORY`, else `.specify/feature.json`.

## Global behaviour

| Aspect | Contract |
|---|---|
| Output | Human text on stdout by default; `--json` prints exactly one JSON object on stdout and nothing else. Diagnostics go to stderr. |
| Exit codes | `0` ok; `1` **refusal** (a gate, approval, alias or authority rule stopped the action; the JSON `refusals[]` says why); `2` usage or input error; `3` not a governed feature (no `s00-README.md`); `4` internal error. |
| Not governed | Every subcommand except `start` and `fingerprint` exits `3` with `{"governed": false}` and changes nothing (FR-006, FR-069). `fingerprint` is a plain utility that works in any project (contract test C-04 runs it in an ungoverned one). Wraps treat `3` as "run the core command unchanged". |
| Side effects | A subcommand writes only what its row below says. It never edits a stage document's human content outside `eil` regions and never edits a target through an alias, with the three exceptions listed under "Helper edits to human content" below. |
| Idempotence | Running the same subcommand twice with the same inputs gives the same files (byte-identical). |
| Test switch | `EIL_ALIAS_MODE=mirror` forces the mirror fallback (used by quickstart B-08); it has no effect in normal use. |
| Refusal shape | `{"ok": false, "refusals": [{"code": "...", "message": "...", "fix": "..."}]}`. Codes are stable identifiers (below). |

## Subcommands

| Subcommand | Purpose | Writes | Refuses when (`code`) |
|---|---|---|---|
| `start --title T [--owner N]` | Create `s00-README.md` and `s01-requirements.md` from templates (resolved through Spec Kit's `resolve-template.sh`) in the feature directory, creating it if needed; the owner defaults to `--owner`, then `default_developer`, then the git identity; persist `.specify/feature.json` if absent (FR-003, FR-048). Needs `--feature-dir`, `SPECIFY_FEATURE_DIRECTORY` or an existing `feature.json`, else exit `2` | `s00`, `s01` | `already-governed`; `directory-has-spec-md` (an ordinary `spec.md` exists that is not ours) |
| `sync [--check-only]` | Classify aliases, report differences, refresh mirrors and symlinks, regenerate overview (FR-051, FR-053, FR-056) | aliases, `s00` | never refuses; reports faults with exit `0` and `alias_faults[]` unless `--strict`, which exits `1` on any fault |
| `enter <command>` | The single gate call used by wraps. Runs `sync`, then the entry rule for `<command>` (`specify`, `clarify`, `plan`, `tasks`, `analyze`, `checklist`, `implement`) | as `sync` | `stage-not-approved`, `ai-spec-missing`, `ai-spec-not-traceable`, `pending-clarification`, `plan-missing`, `alias-fault-strict`, `tasks-missing`, `already-governed`, per command (see commands.md) |
| `check [--stage S] [--chain] [--judgments PATH]` | Evaluate the stage's gate; write the assessment region; with `--chain`, also check the full trace chain (FR-068). `--judgments` merges the AI's verdicts on `judgment` criteria (file shape below) | assessment region, `s00` | never refuses; `ok` is false when any criterion is `not-met`; exit `0` (this is a report). `--strict` exits `1` when unmet |
| `stage-init S` | Create a stage's document from its template if absent, only if the preceding stage is approved (FR-008); create its alias when S is `ai-spec`, `plan` or `tasks` | document, alias, `s00` | `stage-not-approved`, `already-exists`, `unknown-stage` |
| `challenge add S --target ID --text T [--by N]` | Append an open challenge (FR-034/035) | stage doc | `duplicate-of-closed` (equivalent to a rejected/deferred one, FR-038) |
| `challenge answer ID --response accepted\|rejected\|deferred --by N [--reason R]` | Close a challenge (FR-036) | stage doc | `reason-required`, `not-a-confirmer`, `conflict` |
| `approve S --by N --attestation TEXT [--played-back-to TEXT]` | Record the approval (FR-011..013, 066) | stage doc, `s00` | `unknown-stage` (not a stage, or it has no document yet), `stage-not-approved` (prior), `unmet-criteria`, `open-challenge`, `open-question`, `unreviewed-ai-content`, `unverified-requirement` and `unverified-artifact` (completion only), the comprehension criterion inside `unmet-criteria` (functional and technical only), `not-a-confirmer`, `attestation-required`, `ai-approval` (`--by` is the AI: a whole-name match against a short list such as `claude` or `ai agent`, so "Ai Nguyen" is a person; attestation-level, see D-11), `not-approvable` (ai-spec, plan, tasks, verification). All applicable refusals are reported together, and nothing is written on any of them |
| `override S --criterion C --by N --reason R` | Record an override (FR-045). `C` is a criterion id of the stage, or `unreviewed-ai-content` to waive the `[ai-draft]` check | stage doc, `s00` | `unknown-stage` (no such stage or no document yet), `not-a-confirmer`, `reason-required`, `unknown-criterion` |
| `amend S --from ID[,ID…] --by N --attestation TEXT` | Re-sign `S`'s approval when it is `needs-re-review`, in place of a full `approve` (D-25). Succeeds only when every item changed since the last approval — its own edit, or an upstream one propagating in (D-26) — carries a `(decided: ID)` clause naming one of the cited ids (`CH`, `OQ`, `AIS` or `RVW`, D-24/D-28), every changed section has a matching `eil review` acceptance, no `[ai-draft]` tag remains, and the comprehension check (if the stage takes one) is current (D-27, D-29). The new approval is marked `"amended": true` with `"amends": [ID,…]` | stage doc, `s00` | `not-amendable` (stage not approvable, or not previously approved and `needs-re-review`), `unreviewed-ai-content`, `unknown-item` (a cited id does not exist or is not in an eligible state — D-24), `amend-not-covered` (a changed item cites none of `--from`, a section changed with no matching review, or the approval predates `section_fingerprints`), `comprehension-prerequisites` (the check for this version is not current and not everything is a recorded decision), `not-a-confirmer`, `attestation-required`, `ai-approval`; exit `2` if `--from` is empty |
| `review start --stage S` | Lists the items (new, changed, removed — including one affected only because it traces to a changed upstream item, D-26) and the section titles changed since `S`'s last approval, ids and titles only, never old or new text (D-28) | none | `not-amendable` (as `amend`) |
| `review accept --stage S [--items ID[,…]] [--sections NAME[,…]] --by N [--note TEXT]` | Records the human's acceptance of one or more changed items/sections, right now. For an item: writes `(decided: RVW-###)` onto its line, replacing `[ai-draft]` if present, and the `eil:review` record, as one action. For a section: the record only | stage doc | `not-amendable`, `unknown-item` (not actually changed since the last approval), `not-a-confirmer`, `ai-approval`; exit `2` if neither `--items` nor `--sections` is given |
| `review finish --stage S --by N --attestation TEXT` | Gathers every `eil:review` id recorded for `S` and re-signs its approval the same way `amend` does, marked `"reviewed_change_by_change": true` with `"reviewed_ids": [ID,…]` | stage doc, `s00` | same as `amend`, plus `amend-not-covered` when nothing has been reviewed yet |
| `abbreviate S --by N --reason R` | Mark a stage abbreviated (FR-040) | stage doc, `s00` | `not-an-authoriser`, `reason-required`, `cannot-skip` (S has no document) |
| `resolve --id AIS-### --stage S` | Carry a pending clarification answer upstream: assign it an ID in the earliest affected stage, mark that stage `needs-re-review` if approved (FR-042, 067) | target stage doc, `s04`, `s00` | `unknown-item`, `stage-not-eligible` |
| `artifact register --id ART-### --file PATH --kind wireframe\|image [--depicts K] --source-tool T --source-url URL [--exported-on DATE] [--exported-by N]` | Record an exported file for an existing `ART` item: copy it into `assets/` if it is not already there, hash its raw bytes, and write the `eil:artifact` record under the item line. Re-running for the same id replaces the record and the file (FR-077, FR-078) | `assets/<file>`, stage doc, `s00` | `unknown-item` (no such `ART` line), `artifact-missing` (source file unreadable), `artifact-format-not-allowed`, `artifact-no-provenance` (Figma URL without `node-id=`, or no URL), `artifact-wrong-level` (kind not permitted in the item's stage), `path-outside-package` |
| `comprehension plan --stage S [--level L] [--attempt K]` | Start or continue the comprehension check: return the deterministic target items for each level (or one level), including the full upstream chain for `trace` (FR-087..089). Prints ids and the section of each, never a question or an answer | none | `stage-not-eligible` (only `functional`, `technical`), `comprehension-prerequisites` (another criterion unmet and not overridden, or an open challenge, FR-088), `unknown-level` |
| `comprehension record --stage S --level L --outcome understood\|coached\|revealed\|skipped\|not-applicable --by N [--attempts A] [--items ID,…] [--reason R]` | Write one level's outcome into the `comprehension` region; replaces a stale record whole (FR-092, FR-093) | stage doc (region only), `s00` | `stage-not-eligible`, `unknown-level`, `not-a-confirmer`, `reason-required` (`not-applicable` needs one), `unknown-item` (an `--items` id not in the document or its approved upstream), `comprehension-prerequisites` |
| `artifact list [--stage S] [--json]` | List every `ART` with kind, stage, form, derived state and its traces (FR-086) | none | never refuses |
| `trace [--from ID] [--to ID] [--report]` | Forward and reverse chains, and gaps (FR-028..030) | none | never refuses; gaps listed in output |
| `status` | Derived per-stage state, approvals, overrides, outstanding items, alias health; regenerates nothing | none | never refuses |
| `overview` | Regenerate `s00-README.md` only | `s00` | never refuses |
| `fingerprint FILE` | Print the normalised-content fingerprint (debugging, CI) | none | exit `2` if unreadable |

## Refusal codes (stable)

`stage-not-approved`, `unmet-criteria`, `open-challenge`, `open-question`, `unreviewed-ai-content`, `pending-clarification`, `ai-spec-not-traceable`, `ai-spec-missing`, `plan-missing`, `unverified-requirement`, `unverified-artifact`, `verification-missing`, `artifact-missing`, `artifact-format-not-allowed`, `artifact-no-provenance`, `artifact-wrong-level`, `path-outside-package`, `comprehension-prerequisites`, `unknown-level`, `not-a-confirmer`, `not-an-authoriser`, `reason-required`, `attestation-required`, `ai-approval`, `already-governed`, `already-exists`, `alias-fault-strict`, `directory-has-spec-md`, `duplicate-of-closed`, `conflict`, `cannot-skip`, `unknown-stage`, `unknown-item`, `unknown-criterion`, `not-approvable`, `stage-not-eligible`, `tasks-missing`, `not-amendable`, `amend-not-covered`.

## `--judgments` file

A JSON file the agent writes and passes to `check`. It carries only verdicts on criteria whose kind is `judgment`, never document text.

```json
{"stage": "functional",
 "judgments": [{"id": "FUN-G09", "status": "met|not-met", "reason": "one sentence"}],
 "assessment": {"ambiguity": [], "missing": [], "contradictions": [], "unsupported_assumptions": [], "untestable": []}}
```

`assessment` is optional: the five lists of the specific problems the AI found (FR-009), each a list of strings; no other list name is accepted. Every entry needs exactly `id`, `status` and `reason`; a duplicate id, an unknown top-level key or a non-JSON file exits `2`.

The helper writes each verdict into the `assessment` region with the reason prefixed `AI assessment:`. An entry for a criterion that is not a `judgment` criterion, an unknown id, a `stage` that does not match, or a missing reason exits `2` and writes nothing. A `judgment` criterion with no entry stays `not-met` with the reason `no judgment supplied`. The AI cannot make any other kind of criterion `met`.

**Verdicts persist, for one version of the document.** The assessment region records the `fingerprint` of the text the AI assessed. A later `check` with no `--judgments` file keeps the recorded verdicts while that fingerprint is still current (so `approve` can use them); a `--judgments` file replaces every earlier verdict; after any content change the verdicts are stale and each judgment criterion is `no judgment supplied` again. A judgment criterion also has a **structural precondition**: if a section it is about is missing or empty (and not listed under Not applicable with a reason), it is `not-met` whatever the AI says. The `missing` list holds those section problems, prefixed `structure:`, ahead of any the AI adds.

## `status --json` shape

```json
{
  "governed": true,
  "feature_dir": "specs/012-customer-duplicates",
  "title": "…", "owner": "…",
  "current_stage": "technical",
  "stages": {
    "requirements": {"state": "approved", "abbreviated": false,
      "approval": {"by": "…", "at": "…", "fingerprint": "sha256:…"}},
    "functional":   {"state": "needs-re-review", "reason": "upstream requirements changed",
      "affected_items": ["FR-007", "FR-008"]},
    "technical":    {"state": "draft"},
    "ai-spec": {"state": "not-started"}
  },
  "outstanding": {"open_questions": [], "open_challenges": ["CH-002"],
    "pending_clarifications": [], "accepted_risks": ["OQ-004"], "overrides": []},
  "comprehension": {"functional": {"state": "complete", "counts": {"understood": 3, "coached": 1, "revealed": 0, "skipped": 1, "not_applicable": 0}},
                    "technical": {"state": "missing"}},
  "artifacts": [{"id": "ART-003", "kind": "c4-container", "stage": "technical", "form": "inline", "state": "ok"},
                {"id": "ART-011", "kind": "wireframe", "stage": "functional", "form": "file", "state": "hash-mismatch"}],
  "aliases": [{"name": "spec.md", "target": "s04-ai-spec.md", "form": "mirror", "fault": null}],
  "next": "Answer challenge CH-002, then approve technical.",
  "next_action": {"kind": "human", "stage": "technical", "command": "/speckit-eil-challenge",
                  "message": "Answer challenge CH-002, then approve technical."}
}
```

`next_action.kind` is `draft` or `check` (work the AI may do alone), `human` (a person must decide: an open
challenge, an approval or a re-review) or `done`. `/speckit-eil-next` runs `command` only for `draft` and
`check`, and stops after one step. Once tasks are approved and any task is still open, the step is
`/speckit-implement` before verification.

A stage an upstream change moved but did not affect (D-26) stays `approved` and carries a `note` instead
of a `reason`, for example: `{"state": "approved", "note": "upstream functional changed since approval; no
traced item is affected"}`.

## Determinism requirements (each has a unit test)

1. `fingerprint` of any two files that differ only in CRLF/LF, trailing whitespace, runs of blank lines, or leading/trailing blank lines is identical; any other difference changes it (FR-044).
2. Changing only the approval, assessment or comprehension region leaves the fingerprint unchanged.
3. `approve` on a document whose gate has an unmet, un-overridden criterion exits `1` and writes nothing (FR-010).
4. `approve` with `--by` not in the stage's configured approvers exits `1` (FR-013).
5. `approve` on `ai-spec`, `plan`, `tasks` or `verification` exits `1` with `not-approvable`.
6. `sync` on a mirror that differs from its target reports the fault **before** refreshing, then leaves the mirror content-identical (FR-053).
7. `sync` never creates an alias whose target does not exist, and never creates any alias other than the three (FR-049, FR-050).
8. Running any subcommand except `start` and `fingerprint` in a directory without `s00-README.md` changes nothing and exits `3` (FR-069).
9. `status` and `check` are read-only with respect to human content and identity (fingerprints unchanged after they run).
10. Each accepted Mermaid construct in [document-format.md](document-format.md) has a fixture that extracts the expected elements; a fixture with one unrecognised line reports `diagram-unparseable` naming that line and never yields an empty pass (FR-080).
11. Each consistency rule (D-20 a to f) has a passing and a failing fixture, and a failing one is reported by `check` as `diagram-inconsistent` and clears once overridden by a configured confirmer (FR-079, FR-045).
12. `artifact register` twice with identical inputs gives byte-identical output; with a changed file it changes the record's `sha256`, the owning document's fingerprint, and marks that stage `needs-re-review` if it was approved (FR-078).
13. Changing one byte of a registered file, with the record untouched, makes `check` report `artifact-hash-mismatch` and leaves every fingerprint unchanged (the document did not change).
14. `check` reports a wireframe defined in `s01`, an `er` diagram in `s02`, and a `mermaid` fence with no `ART` line, each with the code in the findings table.
15. `artifact register` never writes outside the feature directory; a `--file` or record path containing `..` or resolving outside the package is refused with `path-outside-package`.
16. An `AIS` item that traces to an `ART` whose item hash differs from its owning stage's approval makes the AI Specification fail source-traceability with `artifact-changed-since-approval` (FR-082).
17. `comprehension plan` for the same document version, stage, level and attempt prints identical targets on every run and on every machine; a different attempt number yields a different target when more than one is eligible; an empty eligible set is reported as `no-material` (FR-089).
18. `comprehension record` accepts only the keys in document-format.md; it exits `2` for any other key, never writes free text, and the region never contains a score (FR-092, SC-016).
19. After any content change to the document, `check` reports `comprehension-stale` and `FUN-G16`/`TEC-G19` is not met; a formatting-only change does not (FR-093, FR-044).
20. `approve functional` and `approve technical` exit `1` without a current, complete record, exit `0` when all five levels are `skipped` or `revealed`, and copy the counts into the approval record; `approve requirements` is unaffected (FR-093).
21. `check --judgments` writes verdicts only for `judgment` criteria, labels each as the AI's, exits `2` and writes nothing for an unknown id, a non-judgment criterion or a stage mismatch, and leaves a `judgment` criterion with no entry `not-met`; running it twice with the same file gives byte-identical output.


## Hand-off details (decisions made while building US5)

- **`sync`** reports every alias fault found (`missing`, `wrong-target`, `diverged`, `mirror-differs`, `target-missing`) in `alias_faults[]` *before* it repairs, then repairs. `--check-only` classifies and writes nothing; `--strict` exits `1` with `alias-fault-strict` after repairing. A read-only regular file that differs from its target is `mirror-differs` (a stale mirror); a writable one is `diverged`. A directory in an alias's place is reported and never removed. A new alias is a relative symlink, falling back to a read-only mirror; an existing valid mirror stays a mirror.
- **`enter`** applies: `specify` refuses `already-governed`; `clarify` needs `s04` (`ai-spec-missing`); `plan` and `tasks` need the three definition stages approved (`stage-not-approved`) and the AI Specification gate met (`pending-clarification` for `AIS-G03`, otherwise `ai-spec-not-traceable`); `tasks` also needs `s05` (`plan-missing`); `implement` needs `s05`, `s06` (`tasks-missing`), the AI Specification gate, and no alias fault that survived the repair (`alias-fault-strict`); `analyze` and `checklist` only synchronise. A named override of an AI Specification criterion lets `plan` proceed (FR-004). The AI Specification gate is `AIS-G01` sections, `AIS-G02` every item traces to an *approved* source and no text stands outside an item, `AIS-G03` no `[pending-clarification]` item, `AIS-G04` every referenced `ART` unchanged since its stage's approval (`artifact-changed-since-approval`), `AIS-G05` no diagram; all are decided by code.
- **`stage-init plan|tasks|verification|completion`** also needs the previous stage's document (`ai-spec-missing`, `plan-missing`, `tasks-missing`, `verification-missing`); `ai-spec|plan|tasks` create their alias after the document.
- **`resolve --id AIS-### --stage S`** (`S` is `requirements`, `functional` or `technical`): allocates the next `REQ`, `FR` or `DEC` id story-wide, inserts `**ID**: Carried from AIS-###: <text> [ai-draft]` at the end of the section that holds that kind (`Desired Outcome`, `Functional Requirements`, `Technical Decisions`; `stage-not-eligible` if the section is missing), adds the id to the `AIS` item's `traces`, and leaves the `[pending-clarification]` tag. The stage becomes `needs-re-review` if it was approved. Running it again once `S` is approved again clears the tag; before that it reports what remains. Refusals: `unknown-item` (not a pending `AIS`), `stage-not-eligible`, `ai-spec-missing`.
- **Plan and tasks gates**: `PLN-G01` every `##` section heading carries `(traces: DEC-###)` naming a decision of the approved Technical Specification (`plan-not-derivable`), `PLN-G02` judgment: no architecture beyond the decisions; `TSK-G01` every task traces to an `AIS` item or approved `DEC` (`task-untraced`), `TSK-G02` every wireframe, ER and technical sequence `ART` listed in the AI Specification is reached by a task, directly or through the `AIS` item that cites it (`artifact-uncovered`), `TSK-G03` judgment: no task introduces architecture.

## Decisions made while building US6 to US9

- **`trace`**: `--from ID|COMMIT|PR#n` walks downstream, `--to ID|COMMIT|PR#n` upstream (giving both is exit `2`; an id or change the story does not contain is exit `2`); with neither, or `--report`, it prints one row per `REQ` (`functional`, `decisions`, `ai_spec`, `tasks`, `artifacts`, `code`, `evidence`, `complete`, `ends_at`). A commit matches a task's or item's `(code: …)` by prefix in either direction (at least 7 hex digits); a pull request only exactly. Every output carries `overrides`, `abbreviated` and `accepted_risks`, and `gaps[]` in words (for example `no verification evidence (FR-030)`). A task id (`T012`) is a valid `traces:` target so evidence can trace to a task.
- **`check --chain`** (no `--stage`) returns `{"ok", "gaps":[{"id":"T-001","severity","where","message"}]}` and exits `0` (`--strict` exits `1` on any gap). It covers a requirement with no functional requirement, a functional requirement with no requirement or use case, a decision that traces to no `FR`/`NFR`, an `AIS` item with no approved source or still pending, an `ART` that traces to nothing, a task that traces to no `AIS` or `DEC`, and every dangling trace.
- **`status`** adds `affected_items` to any stage that holds an item that changed since its approval or depends on one that did (`impact.py`): an item is *changed* when its hash differs from the approval's recorded hash, or it is new or gone; *affected* is everything that traces to a changed item, directly or not. **The stage-level rule is item-level, not document-level (D-26)**: an approved stage becomes `needs-re-review` only when its own recorded `upstream_items` shows one of the ids it actually traces to has a different current hash (named in `reason`); if some upstream document changed but nothing traced is affected, the stage stays `approved` and carries a non-blocking `note` instead (`"upstream requirements changed since approval; no traced item is affected"`).
- **`challenge add STAGE --target ID|SECTION --text T [--by N]`**: `--by` defaults to `ai`; only definition stages (`requirements`, `functional`, `technical`, `ai-spec`) take challenges (`stage-not-eligible`, `unknown-stage` when the document is missing); the target must be an item id of the story or a section of the stage (`unknown-item`). A point already **rejected or deferred** on the same target with the same words (after normalising case and punctuation, or 90% similarity) is `duplicate-of-closed`, as is one still open; an **accepted** one may be raised again. The record: `id`, `stage`, `raised_by`, `raised_at`, `target`, `text`, `status` (`open`, `closed` or `conflict`) and, once answered, `response`, `responder`, `at`, `reason`.
- **`challenge answer ID --response accepted|rejected|deferred --by N [--reason R]`**: `rejected` and `deferred` need a reason (`reason-required`); `--by` must be a configured confirmer of the challenge's stage (`not-a-confirmer`) and never the AI (`ai-approval`); all refusals are reported together. The same person may change their answer; a *different* person answering the same way is a no-op; a different person answering **differently** turns the challenge into `status: conflict` with `responses[]`, which blocks approval until any configured confirmer answers again (`resolved_conflict: true`). `approve` refuses `open-challenge` while a challenge on that stage is `open` or in `conflict`, and this is not overridable.
- **`abbreviate S --by N --reason R`** writes `{"stage","by","at","reason"}` in an `eil:abbreviation` block under `## Abbreviation` (replacing an earlier one). The authoriser list is `abbreviation_authorisers`, else the story's developer (`not-an-authoriser`); the AI is `ai-approval`. The record is part of the document, so abbreviating an approved stage makes it `needs-re-review`, and the stage still passes its gate.
- **`approve completion`** maps its criteria to the stable refusal codes `verification-missing` (`CMP-G02`), `unverified-requirement` (`CMP-G03`) and `unverified-artifact` (`CMP-G04`); each is overridable by naming the criterion. Open tasks are listed in `s07` but do not block completion.
- **Performance**: a `Package` caches each stage document's parse and fingerprint for the life of one command (keyed on the text, so an edit is re-read), which took `status` on nine 1 MB documents from 3.7 s to about 0.5 s (`tests/unit/test_performance.py`).

## Feature 002 amendments (proportionate revalidation)

Folded in from `specs/002-proportionate-revalidation/contracts/cli.md` in the same change as the tests that pin
them. Where a row or rule below differs from the text above, this section governs. The 002 delta file is kept
as the record of the change.

### New subcommands

| Subcommand | Purpose | Writes | Refuses when (`code`) |
|---|---|---|---|
| `blocks list --stage S [--status ST]` | Every content block with key, class, derived status and, for derived stages, stale sources (D-31 to D-34) | none | never refuses |
| `blocks classify --stage S --file PATH` | Merge the AI's classification verdicts (D-32); recompute classes; re-render `[ai-draft]` cues | `provenance`, cue tags, `s00` | exit `2`: unknown block key, stage mismatch, unknown top-level key, not JSON |
| `blocks reclassify --stage S --block KEY --to inferred --by N [--reason R]` | Mark a restated block inferred (FR-013). Anyone may do this | `provenance`, cue tags | `unknown-item`; `not-restated` |
| `review list --stage S --kind K [--views FILE]` | Compute one review list (D-36). `--views` carries the AI's per-entry views (`{"stage","kind","views":[{"key","view"}]}`, verdicts only, like `--judgments`); each is shown prefixed `AI assessment:`. `K` is `inferred`, `changes`, `tasks`, `evidence`, `low-challenges`, `unknown-currency`, `diagram-currency` or `unsettled-challenges`. Output: `{kind, stage, purpose, entries[], digest, limits[]}` | none | `not-amendable` (`changes` on a stage never approved) |
| `review answer --stage S --kind K [--digest D] --by N --reply TEXT (--all \| --all-except IDS \| --question ID \| --reopen IDS) [--defer-reason R] [--summaries FILE]` | Record one reply to the list the person saw. `--digest` is required for a settling answer. A `--question` or `--reopen` answer may omit it and name any entry of that kind settled for the stage since its last approval (`changes`) or since it was recorded (other kinds) (D-36, FR-050). `--summaries` (kind `changes`, and kind `inferred` for an item under an open CR; same shape as on `confirm`): the AI's one-line summary per accepted change, shown in the list before the reply, becoming the Change Log text (D-39) | `provenance`, cue tags, challenge records (`low-challenges`), `s00` | `list-changed` (digest mismatch); `not-a-confirmer` (a settling answer by a non-confirmer, FR-048); `ai-approval`; `reply-required`; `reason-required` (deferral without a reason); `digest-required` (a settling answer without `--digest`); `unknown-item` (an id neither on the list nor, for question or reopen, a settled entry of that kind); `reply-mismatch` (a bare all-phrase reply without `--all`, or `--all` with a reply naming an entry key on the list, D-36). A different person's opposite answer to the same entry is recorded and marks it `conflict` (FR-050), not a refusal |
| `review confirm --stage S --by N --confirmation TEXT [--summaries FILE]` | Re-sign a previously approved stage (D-37). All changes covered: `reached: carried-forward`, and TEXT may be "ok". Otherwise `reached: reviewed`. `--summaries` (`{"stage","summaries":[{"key","summary"}]}`): the AI's one-line summary per change, shown before the sign-off, becoming the Change Log text (D-39). A summary may come from this flag or from `review answer --summaries`; any change, covered or uncovered, with no summary from either refuses `summary-missing`, so every change gets its Change Log entry (FR-043). On a never-approved stage (ai-spec, plan, tasks, verification) with an open CR, it closes each open CR whose item is settled (an open CR whose item is not yet settled stays open; the close is partial), writing its Change Log entry, and writes no approval (D-38) | `approval` (approvable stages only), `provenance` (`changes[]`, CR closure), `changelog`, `s00` | `changes-unanswered` (an uncovered change has no acceptance); `acceptance-conflict` (an entry is in conflict, FR-050); `comprehension-prerequisites` (an inferred uncovered change and the delta check not current, FR-019); `not-amendable` (never approved and no open CR; or, on a never-approved stage, an open CR whose item is not yet settled); `not-a-confirmer`; `ai-approval`; `confirmation-required` (empty); `summary-missing` (a change has no AI summary) |
| `correct propose --item ID --found-in STAGE[:ID] --problem TEXT` | Owning-stage candidates, `ambiguous`, impact list (D-38). Read-only | none | `unknown-item` |
| `correct open --item ID --found-in STAGE[:ID] --problem TEXT --by N [--owner STAGE] [--wording TEXT]` | Record `CR-###` in the owning stage. `--wording` is the person's corrected text, verbatim; with it, the CR can back a `(decided: CR-###)` clause (contracts/document-format.md) | `provenance`, `s00` | `owner-ambiguous` (several candidates and no `--owner`); `owner-not-candidate`; `unknown-item`; `ai-approval` (as the opener's name) |
| `challenge severity ID --to high\|medium\|low --by N` | Change a challenge's severity (D-40). Lowering needs a confirmer, raising does not | stage doc (challenge record) | `not-a-confirmer` (lowering); `ai-approval` (lowering); `unknown-item` |

### Changed subcommands

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

### New refusal codes (stable)

`list-changed`, `digest-required`, `reply-required`, `reply-mismatch`, `acceptance-conflict`, `changes-unanswered`, `confirmation-required`, `owner-ambiguous`, `owner-not-candidate`, `not-restated`, `work-blocked`, `review-finding-open`, `summary-missing`, `amend-not-covering`.

### New finding codes (reported by `check` and `status`)

`malformed-provenance`, `block-needs-review`, `source-changed`, `stale`, `unknown-currency`, `completed-while-blocked`, `evidence-for-earlier-version`, `task-completed-against-earlier-version`, `challenge-possibly-unsettled`, `correction-wording-mismatch`.

### `enter` success shape

```json
{"ok": true, "command": "implement",
 "blocked": [{"id": "T014", "because": ["DEC-003 changed since T014 was derived (stale via AIS-011)"],
              "fix": "/speckit-eil-accept technical, then re-derive AIS-011"}],
 "rederive": ["AIS-011"], "alias_faults": [], "aliases": [], "text": "May proceed with implement except T014."}
```

### `review list` shape

```json
{"kind": "inferred", "stage": "ai-spec", "purpose": "validation",
 "entries": [{"key": "AIS-007", "what": "<full block text>",
              "why": "adds beyond DEC-002", "ai_view": "AI assessment: adds a retry policy of 3 attempts"}],
 "digest": "sha256:…",
 "limits": ["Restated content is checked against its source by hash; the check cannot prove two wordings mean the same (FR-014).",
            "Your reply is recorded word for word; the helper checks only obvious mismatches between it and what is recorded as accepted."]}
```

For `changes`, entries carry `covered_by` (a decision or acceptance id) or `inferred: true`. For `inferred`, an entry whose item is under an open correction carries `correction` (the `CR` id), so the prompt knows to pass its summary. When any entry is covered by a `CR`, `limits[]` also carries: "Correction wording is recorded as given; the tool cannot tell who wrote it." For `tasks`, entries carry `ai_view` (whether the code is likely still valid) and are ordered likely-rework first. For `evidence`, entries carry `confirmed: false` and the reason. For `low-challenges`, entries carry `severity`.

### Determinism requirements (each has a unit test)

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

### Helper edits to human content

The helper edits the prose of a stage document in exactly three places. Each is narrow, and none changes the
stage's fingerprint or an item's hash except where stated.

1. **`review accept`** (D-28) appends `(decided: RVW-###)` to the defining line of the accepted item, replacing
   an `[ai-draft]` tag if present, and writes an `eil:review` record. The item's own words are not changed.
   `review answer` is the newer path and records the acceptance in the `provenance` region instead, editing no prose.
2. **`resolve`** carries a pending clarification upstream: it inserts a new `Carried from AIS-###: …` item,
   tagged `[ai-draft]`, into the named earlier stage's section (a new item, so the stage then needs
   re-approval), and once that item has an approved source it clears `[pending-clarification]` from the
   derived item. It is the one place the helper writes a new item into a stage the person owns.
3. **`[ai-draft]` cue rendering** (D-33) adds or removes the ` [ai-draft]` tag on the first line of a block
   whose recorded status is unreviewed, on `sync`, `blocks classify` and `review answer`/`confirm`. The tag is
   excluded from fingerprints and hashes (D-23) and is never read as status; hand-adding or removing it
   changes nothing until the next render (FR-046).

Everything else the helper writes goes to a marked region (`approval`, `assessment`, `comprehension`,
`provenance`, `changelog`), to a `challenge` or `eil:review` record block, or to `s00`.

## Feature 003 amendments (proportionate effort)

Folded in from `specs/003-proportionate-effort/contracts/cli.md`, in the same change as the tests that pin it. Where this section and an earlier one differ, this one wins.

### Every subcommand

- Each subcommand is declared in one table as `writes` or `read-only`:
  - **read-only**: `status`, `show`, `trace`, `fingerprint`, `blocks list`, `review list`, `review show`, `review start`, `artifact list`, `correct propose`, `comprehension plan`, `check` without `--judgments`, and `enter`, which records nothing. (`review start`, `artifact list` and `correct propose` were added while building US1: they write nothing.) A read-only call whose target is ambiguous runs but writes nothing at all, not even the generated overview or a refreshed assessment.
  - **writes**: every other subcommand.
- Every result has `story` (the target directory's name). The text form begins `Story <name>: `.
- A `writes` call whose target comes from the pointer, or from nothing, exits `1` with `ambiguous-story` when the target is ambiguous (data-model §Story target). It does so before reading any document for modification. The refusal names each candidate, and its fix is `--feature-dir <dir>` or `eil start`.

### Changed subcommands

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

### New subcommands

| Subcommand | Kind | Behaviour |
|---|---|---|
| `show <stage> [--items IDS] [--section NAME]` | read-only | Prints the clean view (D-49). JSON: `{story, stage, text, blocks:[{key, status, first_line, last_line}]}`. An unknown id gives exit `1` `unknown-item`. |
| `review show --stage S --kind K (--entry KEY \| --group NAME \| --all)` | read-only | Full text of entries, in chat. |
| `profile set small --by NAME --reason TEXT` | writes | Also records the scoped override of `unreviewed-ai-content` (plan and tasks entry). Exit `1` with `not-an-authoriser`, `reason-required` or `profile-active`. |
| `profile withdraw --by NAME --reason TEXT` | writes | Exit `1` with `not-an-authoriser`, `reason-required` or `no-profile`. |
| `comprehension waive --stage S --by NAME --reason TEXT` | writes | Records every level not yet recorded as `skipped` with `waived: true` and the helper's fixed `question`. Exit `1` with `reason-required`, or `nothing-to-waive` when all five levels are recorded. |

### Refusal codes added

`ambiguous-story`, `unexpected-branch`, `no-profile`, `profile-active`, `unknown-entry`, `not-own-decision`, `nothing-to-waive`, `nothing-classified`, `approval-record-missing`, `malformed-record-file`, `ai-decided-without-reason`.

### Determinism requirements 38 to 53

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

## Feature 004 amendments (browser review page)

Folded in from `specs/004-browser-review-page/contracts/cli.md`, in the same change as the tests that pin it. Where this section and an earlier one differ, this one wins. What the page shows and does is in `specs/004-browser-review-page/contracts/page.md`.

As built: `review answer --question` keeps its 003 meaning (the entries a whole-list reply questions) when given alone, and is the fixed question's text when given with `--entry` or `--rest`. An `entry-changed` refusal carries `current: {key, hash, what}`. `review serve` prints exactly one JSON line, `{story, address, pid}`, when the page listens, and nothing more when it stops. A comment's reopen and a section acceptance are refused `not-current` when they name a stage that is not the current review's.


This is a delta to 001 `contracts/cli.md`, as amended by 002 and 003. Anything not mentioned here is unchanged. It is folded into 001's file in the same pull request as the tests that pin it.

### Changed subcommands

| Subcommand | Change |
|---|---|
| `review list` | Adds `question` on every entry (D-64). While a session is open, it adds `answers: [{key, disposition, by, at, via, comment, question}]`. After a session closes, it adds `last_answers` with the `except` and `questioned` entries of the latest acceptance (D-72). `--current` replaces `--stage` and `--kind` with the current review (D-61). When there is none, it returns `current: null` and exits `0`. |
| `review answer` | Adds `--shown HASH` (refused with `entry-changed` when it is not the entry's current hash; the refusal carries `current: {key, hash, what}`), `--question TEXT` (`question-mismatch` unless it is the helper's question for the entry) and `--comment TEXT`, stored verbatim. Adds `--section NAME` with `--rest`: accept the unanswered entries of that section only, recorded with `together` and `seen: true`. `--reopen` accepts every settled block of the stage on the `inferred` kind, and writes the `reopened` mark (D-65). |
| every `writes` subcommand | Holds the record lock for its read-modify-write (D-67). If the lock is busy for more than 5 s it exits `1` with `record-busy`, writing nothing. Writes replace the record file atomically. |
| `show`, `status` | A block with a `reopened` mark is `needs-review`. `show` adds "(reopened by NAME: COMMENT)" after the block's review cue. |

### New subcommands

| Subcommand | Kind | Behaviour |
|---|---|---|
| `review serve --by NAME [--host H] [--port P] [--public-name N] [--idle-minutes M]` | writes (through the page only) | Starts the page for the story and prints `{story, address, pid}` as one JSON line, then serves until stopped. Starting writes nothing to the project. It refuses with `ai-approval` for an AI name, `ambiguous-story` (003), `page-running` (with the running address) when a live runtime file exists for the story, and `port-unavailable`. |
| `review serve --status` | read-only | `{running: bool, address, pid, started_at}` from the runtime file. A file whose pid is not running reports `running: false` and is removed (the file is outside the project). |
| `review serve --stop` | read-only for the project | Ends the page process and removes the runtime file. Answers already stored remain. |

### Page routes (served by `review serve`)

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
| `POST /section` | write | `{stage, kind, section}`. Calls `reviews.answer(rest=True, section=…, via="page")`. |
| `POST /reopen` | write | `{stage, key, shown, comment}`. Calls `reviews.answer(reopen=[key], …, via="page")`. A comment is required (`comment-required`). Allowed only on the current review's stage. |
| `POST /name` | process | `{name}`. Changes the in-memory name. An AI name is refused with `ai-approval`. Nothing is written to the project. |

No other path is served. No static file is read from disk: the CSS and script are constants. Every response carries the Content-Security-Policy of D-69, `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer` and `Cache-Control: no-store`.

### Refusal codes added

`entry-changed`, `question-mismatch`, `comment-required`, `not-current`, `record-busy`, `page-running`, `port-unavailable`.

### Determinism requirements 54 to 69

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

### Unchanged

Approval is untouched: `approve`, `review confirm` and every gate keep their 001 to 003 behaviour, and no page route reaches them (FR-020). `review answer` without the new flags behaves exactly as in 003.
