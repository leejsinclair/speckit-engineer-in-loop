# Quickstart: validating Proportionate Revalidation

Runnable scenarios that prove the feature works end to end. They continue 001's numbering (B-01 to B-18 in [001 quickstart](../001-staged-definition-workflow/quickstart.md)) and are automated in `tests/scenario/` against a scratch Spec Kit project, as 001's are. Command details are in [contracts/cli.md](contracts/cli.md), record shapes in [data-model.md](data-model.md).

## Prerequisites

- Python 3.11+, `pytest`, and Spec Kit `>=1.0.2.dev0` (as 001).
- The reference story, built by `tests/fixtures/reference_story.py`: a package approved through tasks, containing 4 REQ, 3 UC, 12 FR, 5 DEC (DEC-001 to DEC-005), 8 ART, AIS items, a plan and tasks T001 to T012, with T001 to T006 ticked and carrying `(code: …)`.
- A helper alias for the examples: `eil() { python3 .specify/extensions/eil/scripts/python/eil "$@" --json; }`

```bash
pytest tests/scenario -k "b19 or b2"      # this feature's scenarios
pytest tests/unit                         # determinism requirements 22–37
pytest tests/scenario/test_interaction_count.py   # SC-001
```

## Scenarios

**B-19: an upstream edit blocks only what it reaches (Story 1, SC-002, SC-003)**

1. Copy the reference story and run `eil sync`. Expected: adoption only; `status` is unchanged from before.
2. Edit the text of DEC-003.
3. `eil status`. Expected: `blocked_work` lists exactly the AIS items, plan sections, tasks and EVD rows tracing to DEC-003, and nothing else is stale.
4. `eil enter implement --task T002` (traces only to DEC-001). Expected: exit `0`.
5. `eil enter implement --task T009` (traces to DEC-003). Expected: exit `1` `work-blocked`, naming DEC-003 and `/speckit-eil-accept technical`.
6. Revert DEC-003 exactly. Expected: `status` shows nothing stale, with no command run.
7. Change only whitespace in DEC-004. Expected: nothing stale.

**B-20: completed tasks and evidence after a change (FR-005, FR-006)**

1. From B-19 step 2, with T004 to T006 ticked and tracing to DEC-003: `eil review list --stage tasks --kind tasks`. Expected: three entries, each naming DEC-003 and what changed, AI views labelled, and a digest.
2. `eil review answer --kind tasks --all-except T005 --reply "ok, except T005" --digest <d> --by "Ada Dev"`. Expected: T004 and T006 re-confirmed against the current version; T005 reopened; one acceptance record holding the verbatim reply.
3. Repeat step 2 with the old digest after editing DEC-003 again. Expected: `list-changed`.
4. `eil approve completion` while an EVD row verifies an FR changed after the evidence. Expected: refused, and the row appears on the `evidence` list.

**B-21: review effort by provenance (Story 2)**

1. Draft an AI Specification where 26 blocks cite approved sources and 4 do not, plus AIS-007 citing DEC-002 while adding a retry policy.
2. `eil blocks classify --stage ai-spec --file verdicts.json`, where verdicts say AIS-007 adds "retry policy". Expected: 5 inferred (the 4, plus AIS-007 with its `adds` reason), 26 restated; `[ai-draft]` on exactly those 5.
3. Remove the `[ai-draft]` from AIS-007 by hand and run `eil sync`. Expected: status unchanged and the tag re-rendered.
4. `eil enter implement --task T011` (traces to AIS-007). Expected: `work-blocked` (unreviewed inferred); other tasks proceed (FR-049).
5. Answer the `inferred` list with "ok except AIS-003". Expected: 4 settled by hash; AIS-003 stays inferred and is the only entry on the next list.
6. Edit DEC-002. Expected: the 26 restated blocks citing DEC-002 become `source-changed`; the others stay settled.
7. `eil blocks reclassify --block <restated key> --to inferred --by "Sam QA"`. Expected: accepted from a non-confirmer (adds scrutiny) and recorded with the name.

**B-22: one way to accept a change (Story 3, SC-004)**

1. Approved functional stage; resolve OQ-002 and carry it in with `(decided: OQ-002)`.
2. `eil review list --stage functional --kind changes`. Expected: one entry, covered by OQ-002, and no uncovered entries.
3. `eil review confirm --stage functional --by "Ada Dev" --confirmation "ok"` without `--summaries`. Expected: `summary-missing`, nothing written. Repeat with `--summaries summaries.json` (the AI's one-line summary for the OQ-002 change). Expected: approval `reached: carried-forward`, `rests_on: ["OQ-002"]`, `sign_off: "ok"`; no comprehension asked; overview shows "carried forward (OQ-002)"; one Change Log row with the Change column labelled AI-drafted.
4. Add a reworded paragraph and a new inferred FR. `review confirm` now refuses `changes-unanswered`. Answer the `changes` list "ok to all", passing the AI's summaries with `--summaries`; `confirm` then refuses `comprehension-prerequisites` until the delta check (at most two questions) is recorded; then succeeds with `reached: reviewed`.
5. `review confirm --by claude`. Expected: `ai-approval`. With a non-confirmer: `not-a-confirmer`.
6. After the step 4 re-signing, edit FR-013 again, so it is a change since the latest approval. Ada answers the `changes` list "ok to all". FR-013 is now settled and no longer on the list. Priya then says "I don't agree with FR-013", recorded as `review answer --kind changes --reopen FR-013 --reply "I don't agree with FR-013" --by "Priya QA"` with no digest. Expected: accepted; FR-013 is `conflict`; `confirm` refuses `acceptance-conflict`; a confirmer answers FR-013 again and `confirm` succeeds.
7. `review answer --reply "ok" --all-except FR-013`. Expected: `reply-mismatch`.
8. After re-signing, `approve functional` on a fresh story still requires the full five-level comprehension check (FR-038 unchanged).

**B-23: moving backwards (Story 4, SC-005)**

1. During implementation: `eil correct propose --item FR-004 --found-in implementation:T014 --problem "…"`. Expected: owner `functional`, not ambiguous, impact list, nothing written.
2. `eil correct propose --item AIS-011 …` where AIS-011 restates DEC-003. Expected: `ambiguous: true` with candidates `ai-spec` and `technical`. `correct open` without `--owner` refuses `owner-ambiguous`.
2a. On a separate copy of the story, open it with `--owner ai-spec` and the person's wording (CR-001 there), and rewrite AIS-011 with `(decided: CR-001)`. `review confirm --stage ai-spec --confirmation "ok" --summaries s.json --by "Ada Dev"`. Expected: CR-001 closed, one Change Log row in the AI Specification, and no approval record written. With the text differing from the wording, AIS-011 is inferred and on the `inferred` list, and `confirm` refuses `not-amendable` until that list is answered.
3. Ada gave the corrected wording with her report. `eil correct open --item FR-004 … --wording "<Ada's words>" --by "Ada Dev"`, rewrite FR-004 in place as those words with `(decided: CR-001)`, then `review confirm --stage functional --confirmation "ok" --summaries s.json --by "Ada Dev"` (the AI's summary is shown with the explanation, not a separate interaction). Expected: three person interactions in total (report with wording, agreement to the preview, sign-off); no `changes` list and no comprehension question; `reached: carried-forward`, `rests_on: ["CR-001"]`; CR-001 closed; Change Log row "found in implementation (T014), CR-001"; `trace --to FR-004` shows CR-001.
3a. Repeat with FR-004's text differing from the recorded wording by one word. Expected: a non-blocking `decided-source-invalid` (`check` does not fail), and the change is uncovered on the `changes` list. With `(decided: CR-999)`, which names no correction, `check` fails with the integrity finding as in 001. Repeat with no `--wording` (the AI drafted the edit, applied without a clause). Expected: the edit is on the `changes` list, and the flow is as B-22 step 4.
4. While CR-001 is open: tasks not tracing to FR-004 pass `enter implement --task`.
5. A challenge CH-003 on FR-004 was rejected earlier. Expected after confirm: `unsettled-challenges` lists CH-003.
6. Add `RF-001` with `Root: DEC-002` under Review Findings. Expected: `VER-G07` unmet and completion refused until it is resolved or excepted.
7. With completion approved, add `RF-002`. Expected: completion is `needs-re-review` ("review finding recorded after completion").

**B-24: re-derivation in place (FR-041, FR-042)**

1. From B-19 step 2: `eil enter plan`. Expected: `rederive` holds exactly the plan sections tracing to DEC-003.
2. Run `/speckit-plan`. Expected: only those sections change (byte-compare the others); no strike-through or amendment note; the rederived sections are listed on the `inferred` list only if they add something.

**B-25: focused presentation and severity (Story 5)**

1. A stage with 16 criteria, 2 unmet and 3 judgment. `eil check --stage functional`. Expected: 5 detailed lines plus "11 structural criteria met"; `--full` lists all 16.
2. Raise CH-001 (low), CH-002 (medium) and CH-003 (high). Expected: listed high, medium, low.
3. Answer CH-002 and CH-003; approve. Expected: approved with `outstanding: ["CH-001"]`, shown in the overview.
4. `eil challenge severity CH-001 --to high --by "Sam QA"` (not a confirmer). Expected: accepted; approval of the next change now refuses `open-challenge`. Lowering it again as Sam: `not-a-confirmer`.
5. Raise the same point twice. Expected: the second returns the first's id.

**B-26: completion asks only what implementation touched (Story 6)**

1. 8 approved ART, of which 3 are reached by tasks carrying `(code: …)`. `eil review list --stage completion --kind diagram-currency`. Expected: 3 entries; `status` lists the 5 untouched.
2. EVD-004 `Evidence: tests/unit/test_dupes.py::test_threshold`. Expected: confirmed if the file defines it, otherwise on the `evidence` list; no process started (run under a monkeypatched `subprocess` that fails if called).
3. Five open low challenges. Answer the `low-challenges` list "defer all, accepted as minor". Expected: each closed `deferred` with that reason and the name; listed in s08.
4. Accept a design/code difference on ART-006. Expected: a CR with origin `completion`, ART-006 corrected in place, and a Change Log entry; no deviation text in the prose.

**B-27: upgrade of a story in progress (FR-047, FR-008)**

1. A 001-era package: requirements to technical approved and unchanged, functional edited since approval, AI Spec and tasks present.
2. `eil status` before and after `eil sync`. Expected: identical block statuses; after `sync`, provenance regions exist; the three unchanged stages are adopted with nothing asked; functional's edit appears on its `changes` list; the derived layers are `unknown-currency` and appear once on an `unknown-currency` list.
3. Answer "ok to all". Expected: snapshots recorded; nothing previously blocked is now unblocked except through that answer (R-20).
4. Repeat with a story whose functional stage was abbreviated under 001. Expected: the abbreviation record and its gate behaviour are unchanged, and the provenance rule applies to the shorter document.

**B-28: interaction count (SC-001)**

`tests/scenario/test_interaction_count.py` replays the reference story through the 001 and 002 sequences with the same edits. Expected: `decision` and `first-approval` counts equal; `other` reduced by ≥ 60%.

## Human trial probes (added to `docs/trials.md`)

- P-20 one reply per list
- P-21 verbatim reply
- P-22 correction shown before being applied
- SC-006 "what am I checking here, and why?" at five checkpoints
- SC-007 reconfirmation without a change
