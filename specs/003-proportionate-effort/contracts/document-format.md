# Document format delta: Proportionate Effort

This file is a delta to 001 `contracts/document-format.md`, as amended by 002.

## Story directory

```text
specs/<story>/
├── s00-README.md … s08-completion.md   # nine documents (unchanged)
├── spec.md, plan.md, tasks.md          # three aliases (unchanged)
├── assets/                             # when needed (unchanged)
└── eil-record.json                     # NEW: the story's machine records (D-48)
```

`eil-record.json` is a record file, not a document. It is not one of the nine, it is never an alias, and it is never rendered.
- Removing the extension leaves it in place.
- People do not edit it. A hand edit is detectable, not prevented (R-25).

## Marked regions

The names and positions are unchanged. Each body is now rendered Markdown, one line per entry; data-model §Marked regions gives the forms. A region whose body is JSON is a document not yet migrated:
- it is read as before;
- the next `writes` call on that stage migrates it.

## Review cue

The `[ai-draft]` tag is no longer written into documents (D-50). `sync` removes existing tags. A tag typed by hand is ignored, as before, because status comes from hashes. The cue appears in `eil show` and in review lists.

## Technical decision

```markdown
**DEC-004**: Cache rendered pages by document modification time (traces: FR-007, NFR-001)
Decision: ...
Reason: Rendering is the slowest step; this choice changes nothing a user sees.
Rejected alternative: ...
Trade-off: ...
Owner: ai-decided
```

`Owner: ai-decided` requires a non-empty `Reason:`. Any other owner must be a person.

## Plan exempt headings

The plan's level-2 headings `Change Log` and `Record` (and every heading in `ADMINISTRATIVE_SECTIONS`) need no `(traces: DEC-…)` clause.
