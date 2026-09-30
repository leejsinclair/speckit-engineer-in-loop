# Contract delta: story package and document format

Changes to [001 contracts/document-format.md](../../001-staged-definition-workflow/contracts/document-format.md). Everything not named here is unchanged.

## Marked regions

Region names become `approval`, `assessment`, `comprehension`, `provenance`, `changelog`. **All five are excluded from the fingerprint** (algorithm step 3 gains the two new names) and from `section_fingerprints`. `provenance` and `approval` hold one JSON object in a ` ```json ` fence. `changelog` holds a generated Markdown table and is never parsed, only rewritten from `provenance.changes`.

`ADMINISTRATIVE_SECTIONS` gains `Change Log` and `Record`. Both headings are placed by the helper (on first write, D-42): `## Change Log` just before `## Record`, and `## Record` just before `## Comprehension Check` or `## Quality Assessment`, whichever comes first.

## Content blocks (FR-039)

Walk the document outside marked regions, `eil:` record blocks, HTML comments and administrative sections:

1. A heading line ends the current block and is not a block. The current `##` title becomes the section of the blocks after it.
2. An item line (the 001 item grammar, now including `RF`), a task line or a plan heading carrying `(traces: …)` starts a numbered block. It continues over its continuation lines by the 001 rules, including the DEC and EVD field rules and an `ART` item's attachment.
3. A fenced block (```` ``` ```` or `~~~`) not attached to an `ART` is one block. So is a table (a run of lines starting with `|`).
4. Any other run of non-blank lines is one block.

**Block hash**: the text of the block with `[ai-draft]` and `[pending-clarification]` removed, then fingerprint steps 2, 5 and 6, then `sha256:`. For a numbered item it equals the 001 item hash, so existing `items` and `upstream_items` snapshots stay comparable.

**Key**: the id for numbered blocks; `§` plus the heading text (without the `(traces:)` clause) for plan sections; otherwise `<section>#<first 12 hex digits of the hash>`.

## Clauses (extended)

- `(traces: ID[, ID…])` may end a **prose block** as well as an item. It is the block's citation for the restated class (D-32). Only the last line of the block is read for it.
- The item kinds regex gains `RF`: `^\s*(?:[-*]\s+)?\*\*(REQ|UC|FR|NFR|DEC|AIS|EVD|OQ|OVR|CH|ART|RF)-(\d{3})\*\*…`
- `RF` items take `(status: open|resolved|excepted)` and the labelled lines `Root`, `Accepted by` and `Reason`.
- `[ai-draft]` is written and removed **only by the helper** (D-33). Its presence is never read as status.
- `(decided: …)` also accepts `CR-###` (the 001 grammar `CH|OQ|AIS|RVW` gains `CR`). It is eligible only when that correction's `item` is this item and it has a `wording`, and the item's text equals the wording: the item's text after its `**ID**:` prefix, with its clauses and tags removed, compared with the wording, both normalised as fingerprint steps 2, 5 and 6. Otherwise `decided-source-invalid` (D-38). **This changes the 001 integrity rule for `CR` clauses only**: a `CR-###` that exists but whose wording is absent or differs from the item's text is a non-blocking finding. The change is uncovered and goes on the `changes` list (or, in a never-approved stage, the item is inferred and goes on the `inferred` list), and `check` does not fail on it. A `CR-###` that does not exist, and every `CH`/`OQ`/`AIS`/`RVW` case, remains an integrity finding as in 001. A later edit to the item replaces or removes the clause: the AI does this when it edits the item (Tier 2, contract test `test_decided_clause_removed_on_reedit`), and the helper reports a clause left behind with the same non-blocking finding.

## Provenance region

```json
{
  "version": 1,
  "currency": "known",
  "blocks": {
    "AIS-007": {"hash": "sha256:…", "class": "inferred", "adds": "retry policy of 3 attempts",
                "reviewed": {"by": "Ada Dev", "at": "…", "list": "RVW-012", "reply": "ok to all"},
                "sources": {"DEC-002": "sha256:…"}},
    "Background#3f2a91c0d4e1": {"hash": "sha256:…", "class": "restated", "cites": {"REQ-001": "sha256:…"}},
    "T014": {"hash": "sha256:…", "class": "inferred", "sources": {"AIS-011": "sha256:…"},
             "completed_against": {"AIS-011": "sha256:…"}, "blocked_at_completion": false}
  },
  "acceptances": [{"id": "RVW-012", "stage": "ai-spec", "kind": "inferred", "digest": "sha256:…", "by": "…", "at": "…",
                   "reply": "…", "accepted": [], "except": [], "questioned": [], "reopened": [], "reason": null}],
  "corrections": [{"id": "CR-003", "item": "FR-004", "owner": "functional",
                   "found_in": {"stage": "implementation", "item": "T014"}, "problem": "…", "wording": "…",
                   "impact": [], "opened_by": "…", "at": "…", "status": "open", "closed_by_approval": null}],
  "changes": [{"at": "…", "item": "FR-004", "summary": "…", "summary_by": "ai", "origin": "CR-003", "accepted_by": "…"}]
}
```

**Allowed keys only**. The complete set:

| Object | Allowed keys |
|---|---|
| Top level | `version`, `currency`, `blocks`, `acceptances`, `corrections`, `changes`, `conflicts` |
| Block (`blocks.<key>`) | `hash`, `class`, `cites`, `adds`, `reviewed`, `sources`, `completed_against`, `blocked_at_completion`, `basis` |
| `reviewed` | `by`, `at`, `list`, `reply` |
| Acceptance | `id`, `stage`, `kind`, `digest`, `by`, `at`, `reply`, `accepted`, `except`, `questioned`, `reopened`, `deferred`, `reason`, `resolved_conflict` |
| Correction | `id`, `item`, `owner`, `found_in` (`stage`, `item`), `problem`, `wording`, `impact`, `opened_by`, `at`, `status`, `closed_by_approval` |
| Change | `at`, `item`, `summary`, `summary_by`, `origin`, `accepted_by` |
| Conflict | `key`, `hash`, `answers` |

`class` ∈ `restated`, `decided`, `inferred`, `adopted`. An adopted block also carries `"basis": "approval <by> <at>" | "untagged before upgrade"`. Any other key, or unparseable JSON, is `malformed-provenance`: reported, and the region is treated as absent for status (everything needs review) but **not** rewritten by adoption. A person must repair or remove it, so a bad region never silently becomes "all adopted".

`conflicts` holds `[{"key", "hash", "answers": [RVW ids]}]` (FR-050).

`CR` and `RVW` numbers are story-wide sequences, allocated by the highest number found in any document's region (and, for `RVW`, any legacy `eil:review` block).

## Change Log region

```markdown
## Change Log
<!-- eil:begin changelog -->
| Date | Item | Change (AI-drafted, accepted as shown) | Found in | Accepted by |
|---|---|---|---|---|
| 2026-10-02 | FR-004 | Duplicate threshold is per tenant, not global | implementation (T014), CR-003 | Ada Dev |
<!-- eil:end changelog -->
```

The region is empty (markers only) until the first entry. In an approvable stage (requirements, functional, technical, completion) an entry is written for each change accepted when the stage is re-signed after its first approval. In a never-approved stage (ai-spec, plan, tasks, verification) an entry is written only when a correction owned by it closes (D-38); re-derivations there are recorded by git alone. The Change column is labelled as AI-drafted because every summary is written by the AI (`summary_by: "ai"`, Constitution II) and accepted as shown on the list the person answered. Cells are escaped (`|` → `\|`, newlines → space).

## Approval record (extended)

Adds `reached`, `rests_on`, `sign_off`, `outstanding`, `blocks` and, for completion, `review_findings` (see [data-model.md](../data-model.md)). A carried-forward approval has `sign_off` and no `attestation`. Every other approval has `attestation`, as today.

## Challenge record (extended)

Adds `severity` and `severity_history`. The duplicate rule is unchanged.

## s07 Verification (extended)

A new optional section, `## Review Findings`, holding `RF` items. `VER-G07`: no `RF` is `open`. An `RF` with `Root:` naming an upstream id must name a `CR` in a `(traces: CR-###)` clause once one is opened. The row grammar for `EVD` is unchanged. Automated evidence is **confirmable** when its `Evidence` line contains a `path::name` token, or a repository path plus a name, resolving to a file inside the project root (D-41).

## s08 Completion (changed wording only)

`Diagram Currency` needs a line only for **touched** artefacts (D-41). Untouched ones are listed on one line, `- untouched: ART-001, ART-002, …`. A deviation line remains possible and needs its reason.

## Fingerprint test vectors (added)

- A document that differs only inside a `provenance` or `changelog` region matches the same document without it.
- A document whose only difference is `[ai-draft]` added to or removed from a prose block matches (existing D-23 behaviour, now on every block kind).
