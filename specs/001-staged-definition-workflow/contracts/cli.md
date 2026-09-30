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
| Side effects | A subcommand writes only what its row below says. It never edits a stage document's human content outside `eil` regions and never edits a target through an alias. |
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
