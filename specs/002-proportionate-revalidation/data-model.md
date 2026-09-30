# Data Model: Proportionate Revalidation

All state is still text in the story package (001 D-03). This feature adds one marked region per stage document and extends three existing records. Nothing is stored anywhere else. Entities come from the spec's Key Entities, and decisions are in [research.md](research.md). The full grammar is in [contracts/document-format.md](contracts/document-format.md).

## Stage document (additions)

```text
# <Stage title>
…content sections…                  ← human content, fingerprinted; the only markers are
                                      (traces: …), (decided: …) and the [ai-draft] cue
## Review Findings                  ← s07 only: RF-### items (fingerprinted, D-38)
## Challenges / ## Overrides / …    ← unchanged
## Change Log
<!-- eil:begin changelog -->        ← generated Markdown table: NOT fingerprinted (D-39)
<!-- eil:end changelog -->
## Record
<!-- eil:begin provenance -->       ← the Provenance Record: NOT fingerprinted (D-30)
<!-- eil:end provenance -->
## Comprehension Check / ## Quality Assessment / ## Approval   ← unchanged
```

`Change Log` and `Record` are administrative sections: they are never "changed sections" and never content blocks.

## Content Block

The unit of review and of staleness (FR-039, D-31).

| Field | Type | Rule |
|---|---|---|
| `key` | string | Item id (`FR-004`, `AIS-007`, `T014`, `EVD-003`, `RF-002`) for a numbered block; plan sections use `§<heading>`; otherwise `<section title>#<hash prefix 12>` |
| `hash` | `sha256:…` | Normalised block text (tags removed, whitespace normalised). For an `ART`, it includes the attachment, as the item hash does |
| `class` | `restated` \| `decided` \| `inferred` \| `adopted` | Computed (D-32). `adopted` means recorded at upgrade (D-42) and is treated as reviewed |
| `cites` | `{id: hash}` | Restated only: each verified source and its hash when classified |
| `adds` | string \| null | Inferred-because-adds only: the AI's stated addition, shown with the `AI assessment:` label |
| `reviewed` | `{by, at, list, reply}` \| null | Set by an accepting `review answer`. `reply` is the person's verbatim words |
| `sources` | `{id: hash}` | Derived blocks (s04 to s07): the version of each traced source when last settled (FR-001, D-34) |
| `completed_against` | `{id: hash}` | Tasks only: sources when first seen ticked |
| `blocked_at_completion` | bool | Tasks only: the task was blocked when first seen ticked (finding `completed-while-blocked`) |
| `basis` | string | Adopted only: `"approval <by> <at>"` or `"untagged before upgrade"` (D-42) |

**Derived status** (never stored):

| Status | Condition |
|---|---|
| `settled` | Class `decided`; or `restated` with every `cites` hash current, every cited source still settled (approved in s01 to s03; settled and not stale in s04 to s06, spec FR-009) and no `adds`; or `reviewed` with the recorded hash equal to the current one; or `adopted` with the hash unchanged |
| `needs-review` | Inferred and not settled, for any reason (new, edited, never reviewed, reclassified) |
| `source-changed` | Restated or reviewed, but a `cites` or `sources` hash differs from the current one |
| `stale` | Derived block whose own sources changed, or any source is not `settled`, transitively (D-34). `status` counts `source-changed` blocks under `stale` |
| `unknown-currency` | Derived block with no `sources` recorded (FR-008) |

**Validation**: a numbered key appears at most once per story (the existing `duplicate-id` rule). An unnumbered key that repeats in one section (identical paragraphs) is one entry: reviewing one reviews both.

## Provenance Record (the `provenance` region, one per stage document)

```json
{
  "version": 1,
  "blocks": {"AIS-007": { … Content Block fields … }, "Background#3f2a91c0d4e1": { … }},
  "acceptances": [ … Review Answer … ],
  "corrections": [ … Backwards Correction … ],
  "changes": [ … Change Log Entry … ],
  "conflicts": [ … Conflict (FR-050, see Review Answer) … ],
  "currency": "known" | "unknown"
}
```

Only keys listed in [contracts/document-format.md](contracts/document-format.md) are accepted. Anything else makes the region `malformed-provenance`, which is reported and treated as no record, so everything becomes needs-review (the conservative choice).

## Review List (derived, never stored) and Review Answer (stored)

A **Review List** is computed by `eil review list`:

| Field | Rule |
|---|---|
| `kind` | `inferred`, `changes`, `tasks`, `evidence`, `low-challenges`, `unknown-currency`, `diagram-currency`, `unsettled-challenges` |
| `stage` | The stage it belongs to (`completion` for `low-challenges`) |
| `purpose` | `awareness` \| `understanding` \| `decision` \| `validation` \| `approval` (FR-032) |
| `entries[]` | `{key, what, why, ai_view?, severity?, covered_by?, correction?}`. `ai_view` is always prefixed `AI assessment:` |
| `digest` | SHA-256 over the sorted `key|current hash` pairs; changes whenever any entry would change |
| `limits[]` | Attestation limits printed with the list: the reply check on every list (D-36), plus FR-014 fidelity, FR-035 evidence and the correction-wording limit (a `changes` list with a CR-covered entry, D-38) where they apply |

Ordering: severity or likely-rework first where that applies, then document order.

A **Review Answer** is stored in the provenance region's `acceptances[]`:

```json
{"id": "RVW-012", "stage": "tasks", "kind": "tasks", "digest": "sha256:…",
 "by": "Ada Dev", "at": "2026-10-02T09:12:44Z", "reply": "ok, except T014",
 "accepted": ["T011", "T012"], "except": ["T014"], "questioned": [], "reopened": ["T014"],
 "reason": null}
```

`RVW` numbering continues the existing story-wide sequence (D-28), so `(decided: RVW-###)` stays valid.

**State transitions per entry**:

- `accepted`: settled at its current hash; for tasks and evidence, the snapshot is re-recorded against the current sources.
- `except` on an `inferred` list: returns to the AI for rework, then appears on the next list.
- `except` on a `tasks` list: reopened (unticked by the implement prompt, and its `completed_against` cleared).
- `questioned`: stays unsettled, and blocks only its own dependants.
- `deferred`: low challenges only. The challenge is closed as `deferred` with the shared reason, per challenge.

**Authority**: accepted, except (on tasks), deferred and carried forward need a configured confirmer of `stage`. Questioned and reopened are open to anyone (FR-048).

**Conflict (FR-050)**: when a different person's answer to the same entry at the same content hash goes the other way (settling versus excepting, questioning or reopening), the entry is `conflict`. It records both answers in `conflicts[] {key, hash, answers: [RVW ids]}`, blocks `confirm` and its dependants, and clears only when a confirmer answers it again (`resolved_conflict: true` on that acceptance).

**Reply check**: the acceptance stores the verbatim `reply` next to the parsed flags. The helper refuses the recognisable mismatches (`reply-mismatch`, research D-36). Anything else is an attestation-level limit.

## Approval record (extended)

New fields, alongside 001's:

| Field | Rule |
|---|---|
| `reached` | `first` \| `carried-forward` \| `reviewed`. Absent means `first` (FR-020) |
| `rests_on` | Ids of the decisions and acceptances it relies on (carried-forward and reviewed) |
| `sign_off` | Verbatim, carried-forward only (may be "ok"). `attestation` stays the field for `first` and `reviewed` |
| `outstanding` | Open low-severity challenge ids at the moment of approval (FR-030) |
| `blocks` | `{key: hash}` of every block settled at approval, so a later diff is per block |
| `review_findings` | Completion only: `{RF-id: hash}` of s07's review findings at approval. A new or changed RF makes completion `needs-re-review` (FR-027) |

`amended`/`amends` and `reviewed_change_by_change`/`reviewed_ids` (D-25, D-28) are still read. New records write `reached` and `rests_on` instead.

## Challenge record (extended)

`severity` (`high` \| `medium` \| `low`) and `severity_history[] {from, to, by, at}`. A missing severity reads as `medium` (D-40). `status` is unchanged. `deferred` from the `low-challenges` list carries the shared reason and the person's name, like any deferral.

## Backwards Correction

Stored in the owning stage's provenance region `corrections[]`:

```json
{"id": "CR-003", "item": "FR-004", "owner": "functional",
 "found_in": {"stage": "implementation", "item": "T014"}, "problem": "…",
 "wording": "Duplicates are detected per tenant, not globally." | null,
 "impact": ["AIS-011", "T014", "T015", "EVD-006"],
 "opened_by": "Ada Dev", "at": "…", "status": "open" | "closed", "closed_by_approval": "…at…"}
```

- **Lifecycle**: `open` (blocks only tasks tracing to `item` and its impact list) → `closed` when the owning stage is re-signed with `item` covered, or, for an owner that is never approved (ai-spec, plan, tasks, verification), by `review confirm` on that stage once `item` is settled (no approval is written).
- `found_in.stage` is any stage later than the owner (FR-021): a stage name, `implementation`, `code-review` (then `item` is an `RF` id) or `completion`.
- `wording`: the person's corrected text, verbatim, when they gave it; `null` when the AI drafted it. With a `wording`, the edit carries `(decided: CR-###)` and is a covered change, verified by text equality (contracts/document-format.md), so the stage carries forward on a sign-off (SC-005). Without one, the edit is an uncovered change on the `changes` list.

## Review Finding (new item kind, s07)

`**RF-###**: <finding> (status: open|resolved|excepted)`, followed by labelled lines `Root:` (`implementation` or an upstream id) and, for `excepted`, `Accepted by` and `Reason`, as for evidence rows. An `RF` rooted upstream names the `CR` it opened. `VER-G07`: no `RF` is `open`.

## Change Log Entry

`{"at", "item", "summary", "summary_by", "origin", "accepted_by"}`. `summary_by` is always `"ai"` (the AI drafts every summary); the rendered column says so (Constitution II). `origin` is a `CR` id, a decision id or `edit`. Written for each change accepted when an approvable stage is re-signed, and for each closed correction in a never-approved stage; never for a re-derivation. Every entry needs a summary (`summary-missing` otherwise). Rendered one per row in the `changelog` region, oldest first. The overview shows the latest five story-wide.

## Configuration (extended)

`approvers` gains optional `ai-spec`, `plan`, `tasks` and `verification` lists. An absent or empty list resolves as the `technical` list does, which falls back to the story's developer (D-36).
