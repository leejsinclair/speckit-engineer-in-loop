# Data Model: Proportionate Effort

This file only describes what changes: new and changed entities. Everything else is as in 001 and 002 `data-model.md`.

## Record file (`specs/<story>/eil-record.json`) — new (D-48)

```json
{
  "version": 1,
  "story": {
    "start":   {"at": "...", "branch": "feature/x", "branch_confirmed_by": "Ada", "previous_pointer": "specs/001-..."},
    "profile": {"name": "small", "by": "Ada", "reason": "...", "at": "...",
                "withdrawn": null},
    "review_sessions": {"<stage>/<kind>/<digest>": { "see Review session" }}
  },
  "stages": {
    "functional": {
      "approval":      { "as 001/002 approval record, plus ai_decided[]" },
      "assessment":    { "as 001 assessment record" },
      "comprehension": { "as 001 comprehension record" },
      "provenance":    { "as 002 provenance record" }
    }
  }
}
```

- Keys are sorted, the JSON has two-space indentation, and each stage's records sit under that stage. A stage with no records has no key.
- **Validation.**
  - Unknown top-level or stage-level keys give `malformed-record-file`.
  - Each per-stage object is validated by the same allowed-keys check as its region was (`blocks.provenance_problems` and the others).
  - A file that cannot be parsed makes every approval in the story unverifiable (FR-011).
- **Reading.** `Package.record(stage, name)` reads the file, falling back to the region's JSON body (a document not yet migrated).
- **Writing.** `Package.write_record(stage, name, obj)` writes the file, then re-renders the region line.

## Marked regions — changed (D-48)

The same five names and positions. The body is rendered Markdown, never JSON:

| Region | Rendered body (example) |
|---|---|
| `approval` | `Approved by Ada on 2026-10-02 (first approval). AI-decided: DEC-004, DEC-006.` One line per approval or override. A re-signing without comparison says so. |
| `comprehension` | `Comprehension: 2 understood, 1 own-decision, 2 not-applicable (small-story profile).` |
| `assessment` | `Gate: 14 of 15 criteria met; FUN-G15 met by small-story profile (Ada, 2026-10-02).` |
| `provenance` | `Blocks: 41 settled, 3 need review, 0 stale.` |
| `changelog` | Unchanged (002 D-39). |

The regions are excluded from fingerprints, as before (`fingerprint.EXCLUDED_REGIONS`).

## Block classes — changed (D-56)

Adds `adopted-pending`: a block covered by a legacy approval (one with no `section_fingerprints`) on a document changed since that approval.
- Its derived status is `settled-pending`. It does not need review, does not raise `unreviewed-ai-content` and appears on no inferred list.
- Re-signing through the `legacy:<stage>` change entry turns it into `adopted` with basis `re-signed without comparison by <name> <at>`.

## Approval record — changed (D-53, D-56)

- `reached` gains `re-signed-without-comparison`.
- `ai_decided`: the list of DEC ids with `Owner: ai-decided` at the approved content.
- `question`: the helper's fixed approval question for the stage, recorded beside the verbatim `attestation` (D-59). The rendered approval line shows the reply and the question.

## Other confirmations — changed (D-59)

- `story.start` gains `reply` and `question` ("Write story <dir> on branch <branch>?") when the branch was confirmed.
- A waived comprehension level gains `question` ("Waive the remaining comprehension levels for <stage>?").

## Stage state — changed (D-58)

`STAGE_STATES` gains `reviewed`, which applies to the derived stages ai-spec, plan, tasks and verification. A stage is `reviewed` when all of these hold:
- the document exists;
- its code-decided criteria are met;
- no block is `needs-review` or `stale`.

Transitions: `draft` → `reviewed` when those conditions hold; `reviewed` → `draft` when they stop holding. A `reviewed` stage is never "current" for `next_action`. When completion is `approved`, `next_action` is `done`.

## Review list and review session — changed (D-51)

- **List** gains:
  - `mode` (`one-at-a-time` or `summary`) and `threshold`;
  - `groups`: section, then entries;
  - per entry, `summary` (title or first sentence, at most 120 characters);
  - scaffolding entries with key `§<Section>` and `members[]`.
- **Review session** (record file, `story.review_sessions`): created by the first `--entry` or `--rest` answer.
  - Fields: `stage`, `kind`, `digest`, `mode`, `opened_at`, `entries` (key to hash), and `answers` (key to `{by, at, disposition, reply, hash, seen}`).
  - It closes, applying all its answers through the existing answer path, when every entry has an answer at its current hash. After that it is removed from the file.
  - An answer whose entry hash has changed lapses, and the entry is unanswered again.
- **Acceptance record** (every review-list answer, whole-list or per entry) gains `mode`, the list's mode when answered, beside the existing `hashes` (entry id to content hash; no entry text is stored). A summary-mode acceptance is rendered as "N items accepted on summaries by <name>".
- **Pseudo-stage `derived`**: accepted by `review list` and `review answer` only when the profile is active. It is the union of the inferred lists of ai-spec, plan and tasks, and settling it settles each member in its own stage's provenance.

## Small-story profile — new (D-52)

| Field | Rule |
|---|---|
| `name` | `small`, the only profile |
| `by` | must be in `abbreviation_authorisers` (empty list: the story's developer) |
| `reason` | required, verbatim |
| `at` | set by the helper |
| `withdrawn` | `null` or `{by, reason, at}`, with the same authority |

**Effects while active:**
- the Functional gate's wireframe criterion is met by the profile;
- the derived list is combined;
- an override of `unreviewed-ai-content`, scoped to `enter plan` and `enter tasks`, is recorded with the profile's `by` and `reason` and withdrawn with it; `enter implement` is not overridden;
- comprehension asks `explain` and `apply` only.

Stages approved while the profile was active keep `profile: small` in their approval record.

## Comprehension — changed (D-54)

- `OUTCOMES` adds `own-decision`, and `COUNT_KEYS` adds `own_decision`.
- A level record with outcome `own-decision` carries `items: [the decision's id]` and no attempts.
- `comprehension plan --by <person>` excludes the person's own decisions, as defined in D-54.
- `comprehension waive` writes one record per level not yet recorded, each `{outcome: skipped, reason, by, waived: true}`.

## Technical decision (DEC) — changed (D-53)

`Owner:` takes a person's name or the literal `ai-decided`. An `ai-decided` DEC requires `Reason:`. Its block is always `inferred` until a person settles it on the review list.

## Configuration — changed

| Key | Default | Used by |
|---|---|---|
| `main_branches` | `[main, master]` | D-47 branch guard |
| `review.one_at_a_time_max` | `8` | D-51 list mode |

## Story target — new (D-46)

The result of resolving the target story has three fields:
- `directory`;
- `source` (`argument`, `environment`, `pointer` or `none`);
- `candidates`, the stories considered when the target is ambiguous.

It is ambiguous when the source is `pointer` or `none`, and any of these holds:
- the source is `none` and the project has more than one story;
- the pointer names a directory that does not exist;
- the pointer names a story whose completion is approved while another story is not complete.
