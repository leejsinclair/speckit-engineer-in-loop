# Quickstart: validating Proportionate Effort

This guide holds the scenarios that prove the feature end to end. The contracts are in [contracts/](contracts/), and the entities in [data-model.md](data-model.md).

## Prerequisites

- Python 3.11+ and `pytest`, as for 001 and 002.
- `tests/fixtures/reference_story.py` (002) builds the reference story. This feature adds two fixtures:
  - `tests/fixtures/legacy_upgrade.py`: a story whose Functional and Technical approvals carry `items` but no `section_fingerprints`, with one paragraph and one diagram changed since approval. It has the shape of the trial's `bd7a0d5` snapshot.
  - `tests/fixtures/two_stories.py`: story A with completion approved, story B in progress, and the pointer on A.

```bash
python -m pytest tests/unit tests/scenario tests/contract -q
```

## Scenarios

| Id | Story | What it shows | Test |
|---|---|---|---|
| B-29 | 1 | Ambiguous target. With the pointer on completed A and B in progress, each writing call is refused `ambiguous-story` and A and B stay byte-identical. Read-only calls name A. `start` for a new story C moves the pointer and reports the move. A start on `001-x` is refused until `--on-branch`. | `tests/scenario/test_b29_story_targeting.py` |
| B-30 | 7 | Upgrade migration on `legacy_upgrade`. Nothing needs review. One `legacy:` entry is re-signed by one reply as `re-signed-without-comparison`. No tag is written. Judgments on unchanged sections survive. | `tests/scenario/test_b30_upgrade_migration.py` |
| B-31 | 2 | Record file migration on the reference story. Fingerprints and approvals are unchanged. No JSON is left in any document. Deleting the file makes approvals unverifiable. `show` is clean. | `tests/scenario/test_b31_record_file.py` |
| B-32 | 3 | List modes. 5 entries are one at a time, 3 are answered, then a fresh `Package` is created (a stand-in for compaction) and the list resumes at the 4th. `--rest` closes it. 38 entries are a summary with `§Actors` as one entry. No settled block appears. | `tests/scenario/test_b32_list_modes.py` |
| B-33 | 4 | Profile. `set` is refused for a non-authoriser. Once set, the wireframe criterion is met by the profile, there is one `derived` list, implementation is refused until it is answered, comprehension asks two levels, and every approval is still required. `withdraw` restores it all. | `tests/scenario/test_b33_profile.py` |
| B-34 | 5 | `ai-decided`: no reason gives a finding. The DEC is on the inferred list in its own group. The approval lists it. Converting it to the developer's decision re-surfaces it once. | `tests/scenario/test_b34_ai_decided.py` |
| B-35 | 6 | Comprehension: an own DEC is skipped. When nothing else is eligible the level is `own-decision`. One `waive` records the rest as `skipped`. The approval and overview counts show both. | `tests/scenario/test_b35_comprehension.py` |
| B-36 | 9 | Defects: plan `Change Log` and `Record` headings pass, `classify` is additive, unknown keys are `skipped`, the terminal `reviewed` and `done` states appear, and status never says "Continue verification" after completion. | `tests/scenario/test_b36_defects.py` |
| B-37 | 10 | Approval by "ok": recorded verbatim with the helper's question and the name; the rendered line shows both; an empty reply is refused. | `tests/scenario/test_b37_short_approval.py` |
| SC-005 | all | The interaction count on the reference story under the profile against the 002 baseline is at least 50% fewer replies, with approvals and observable decisions equal. | `tests/scenario/test_interaction_count.py` (extended) |

## Manual check on the trial project

These steps run against a scratch copy, never the original.

1. Copy the rich specification viewer at commit `bd7a0d5` to a scratch directory, and install this branch's helper into its `.specify/extensions/eil/scripts`.
2. `eil status --feature-dir specs/001-rich-spec-viewer`: Functional and Technical are `needs-re-review` with **0** blocks needing review (before this feature: 17 and 19).
3. `eil sync --feature-dir specs/001-rich-spec-viewer`: `eil-record.json` appears, and `s06-tasks.md` shrinks by at least 75% (SC-002).
4. `eil show tasks --feature-dir …`: the task list, readable, with no hashes.

## Trial probes (human, `docs/trials.md`)

P-23 to P-31, one per Tier 2 rule in [contracts/commands.md](contracts/commands.md). Same pass rule as 002: one clean run each.

SC-003 and SC-004 are timed: run one small story under the profile, and record the total, process and implementation minutes and the compaction count in the SC-010 table.
