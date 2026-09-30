# Research: Proportionate Revalidation

Phase 0 decisions for [spec.md](spec.md). This feature extends the helper and prompts delivered by `specs/001-staged-definition-workflow`, so decisions continue that feature's numbering (D-01 to D-29 live in [001 research](../001-staged-definition-workflow/research.md)). Each decision names the requirements it serves.

Technical Context had no `NEEDS CLARIFICATION` entries: the language, dependency floor, storage and test strategy are fixed by the constitution (Principle III) and by 001. The unknowns below are design questions the spec leaves to planning.

---

### D-30 Bookkeeping lives in a new `provenance` region per stage document (FR-039, FR-043, FR-044)

**Decision**: Every stage document s01 to s08 gains a fourth marked region (s08 holds the acceptances of the completion-stage lists, `low-challenges` and `diagram-currency`, and the Change Log of a completion re-signing), `<!-- eil:begin provenance -->` … `<!-- eil:end provenance -->`, under a generated `## Record` heading placed before `## Approval`. It holds one JSON object: block hashes and classes, recorded source versions, review acceptances, change acceptances, backwards corrections and Change Log entries. Like `approval`, `assessment` and `comprehension`, the region is **excluded from the fingerprint** and from `section_fingerprints`, and `## Record` is added to `trace.ADMINISTRATIVE_SECTIONS`.

**Rationale**: FR-044 forbids bookkeeping in prose. A fingerprinted record block (the D-28 `eil:review` shape) would change the document fingerprint on every acceptance, so recording a review would itself be a change needing review. That is the regress D-28 had to design around. A region keeps the prose clean and makes recording neutral by construction.

**Limits**: As with the approval region (risk R-7), a hand edit to the region is not prevented, only visible in the diff. Stated as attestation-level (Principle II).

**Alternatives**: a sidecar file per document (rejected: 001's "state only in the nine documents" and "no other file" constraints); fingerprinted `eil:` record blocks (rejected: the regress above); one region per record kind (rejected: four more marker pairs per document for no reader benefit).

### D-31 Content-block identity: item id for numbered items, section plus hash for everything else (FR-039)

**Decision**: A new module, `content.py`, splits a document into content blocks exactly as FR-039 defines them. A numbered block (an item line with its continuation lines, a task line or an evidence row) is keyed by its **id**, and its recorded hash is compared with its current one. Any other block (a prose run, a table, a diagram with no `ART` line, a code fence) is keyed by **its `##` section title plus its hash**. It is settled when that exact hash is in the section's recorded set, and otherwise it needs attention. Block text is normalised as the item hash already is (the `[ai-draft]` and `[pending-clarification]` tags removed, whitespace steps 2, 5 and 6 of the fingerprint algorithm), so formatting never changes a block's hash (FR-007).

**Rationale**: Unnumbered paragraphs have no stable name. Ordinal positions shift when a paragraph is inserted above them, which would mark every later paragraph as changed. Keying by content means an insertion, deletion or reorder within a section touches only the blocks whose text actually changed. Scoping to the section keeps a paragraph moved to a different section, where its meaning may differ, as needing a look (conservative, as the spec's Assumptions require).

**Alternatives**: ordinal keys (rejected: insertion churn); a generated anchor comment on every paragraph (rejected: FR-044, bookkeeping in prose); fuzzy matching of edited paragraphs to their previous version (rejected: not deterministic enough to decide review status; the prompt still shows the `git diff` to the human, as 001 does).

### D-32 Provenance classification: the helper verifies, the AI's judgement only narrows (FR-009, FR-011, FR-013, FR-014)

**Decision**: A block's class is computed by `provenance` from three inputs, in this order:

1. **decided**: the block carries a `(decided: ID)` clause that passes the existing D-24 eligibility check. Deterministic.
2. **restated**: the block cites a source with `(traces: ID[, …])`, extended to prose blocks as a trailing clause. Every cited source exists and is **settled** (spec FR-009):
   - in s01 to s03, its stage's approval covers it (its hash matches that approval's `items`);
   - in s04 to s06, which are never approved, its own block status is `settled` and it is not stale (D-34), evaluated in stage order so an AIS item settles before the plan section and task citing it.

   In addition, the AI's latest classification file does **not** say the block adds anything significant beyond it. The source hashes are recorded.
3. **inferred**: everything else. This includes a block with no citation, a citation that fails verification, a restated block the AI says adds something (its stated addition is shown as the reason), and any block the AI supplied no verdict for.

The AI supplies its view in a classification file, `eil blocks classify --stage S --file PATH`. The file follows the `--judgments` pattern (verdicts only, labelled `AI assessment:` wherever shown, no document text): `{"stage": "...", "blocks": [{"block": "AIS-007", "adds": "retries three times"}, {"block": "Background#3f2a…", "adds": null}]}`. A person may reclassify a restated block as inferred at any time (`eil blocks reclassify`, open to anyone per FR-048 because it adds scrutiny). No path lets the AI turn an inferred block into restated or decided without a citation the helper verifies (FR-013).

Without the second bullet no plan section or task could ever be restated, because nothing below the Technical Specification is approved. Every derived block would need review, contradicting FR-041 (found by `/speckit-analyze`, I1).

**Rationale**: The deterministic facts are that the source exists, is settled and is unchanged. The judgement "adds nothing significant" is not deterministic, so it is allowed only to move a block **towards** "restated" when a verified citation already exists. When the AI says nothing, or says something was added, the block needs review. Misclassification therefore errs toward more review, as the spec's Assumptions require. The fidelity limit (FR-014) is printed on every list and report that shows a restated block.

**Alternatives**: classification by the AI alone (rejected: Principle I, since class decides whether review is required); string similarity between a block and its source (rejected: a paraphrase that adds a constraint can score higher than a faithful summary, which gives false assurance); treating any cited block as restated (rejected: this is exactly the "AI invents a retry policy and cites DEC-002" case of Story 2, scenario 3).

### D-33 Review status comes from recorded hashes; `[ai-draft]` becomes a cue the helper writes (FR-046, FR-010)

**Decision**: `approve`'s `unreviewed-ai-content` refusal is re-based on block status. It refuses while any inferred block's current hash is not recorded as reviewed, and no longer checks whether the literal tag is present. `eil sync` (and every helper command that writes a stage document) re-renders the cue: it adds ` [ai-draft]` to the first line of each unreviewed inferred block and removes it everywhere else. Editing the tag by hand therefore changes nothing: the next write re-renders it, and the fingerprint already ignores it (D-23). The existing `override S --criterion unreviewed-ai-content` still works (spec Edge Cases).

A block written by a person directly into the file is unknown to the helper and so is inferred. It appears in the next one-reply list, where one "ok" settles it. Git authorship is not used to tell it apart.

**Rationale**: A tag edited by hand is how "accept all" happens today, with nothing recorded. Tying status to recorded hashes makes each acceptance a helper action with a name and a time, and keeps the readable cue honest.

**Alternatives**: keeping the tag as the source of truth (rejected: the friction and the silent acceptance this feature removes); using git authorship to detect human-typed text (rejected: an AI agent commits under the developer's git identity, so authorship proves nothing).

### D-34 Item-level staleness in every layer: recorded source versions and transitive propagation (FR-001 to FR-008)

**Decision**: Whenever the helper records a derived block as settled (reviewed, restated, re-derived or re-confirmed), it also records that block's **source versions**: `{source_id: item_hash}` for each id the block traces to. This covers AIS items, plan sections (keyed by heading, sources from the heading's `(traces: …)`), tasks and EVD rows. `staleness.py` computes:

- **directly stale**: any recorded source hash differs from the source's current hash, or the source is gone;
- **transitively stale**: any source is itself stale, changed-and-unaccepted, pending, or an unreviewed inferred block (graph walk over `trace.build_graph`, cycle-safe; a cycle or a dangling id is a document error, never "unaffected");
- **unknown currency**: a derived block with no recorded source versions (a document written before this feature). This is reported once through the one-reply list of kind `unknown-currency`, and answering it records the snapshot (FR-008).

A completed task is additionally snapshotted the first time `sync` sees it ticked (`completed_against`). A later change to any of those sources puts it on the `tasks` list as "completed against an earlier version" (FR-005). An EVD row's `recorded_against` works the same way for FR-006.

**Rationale**: D-26 already made definition-stage approval item-level through `upstream_items`. The layers below it never recorded what they were derived from, so the only signal was the AI Specification gate as a whole. Recording per block, at the moment the helper already writes, closes that gap without a new document. Reverting an edit exactly clears staleness with no action (spec Edge Cases), because the comparison is by hash.

**Alternatives**: recomputing staleness from git history (rejected: the helper reads files, not history, and a squash-merge loses it); document-level snapshots for derived layers (rejected: that is the wholesale blocking FR-004 removes).

### D-35 `enter` becomes work-scoped: blocked ids instead of a document-wide refusal (FR-004, FR-025, FR-049, FR-038)

**Decision**: `eil enter plan|tasks|implement` returns `{"ok": true, "blocked": [{"id", "because": [...], "fix"}], "rederive": [ids]}` and refuses (exit 1) only when:

- a definition stage has **never** been approved (`stage-not-approved`; the first approval is unchanged, FR-038);
- the document the command needs does not exist (`plan-missing`, `tasks-missing`);
- an alias fault survives repair;
- the command names a specific target (`enter implement --task T012`) and that target is blocked (`work-blocked`, naming each blocking id and the command that resolves it);
- nothing is left that may proceed (`work-blocked`).

The blocking causes are: a source that is stale, or changed and not yet accepted; an unreviewed inferred block in s04 to s06; a `[pending-clarification]` AIS item; and an open backwards correction on an item it traces to. A stage in `needs-re-review` no longer blocks wholesale. Only its changed and affected items do. The `AIS-G03` gate criterion becomes item-scoped in the same way. `plan` and `tasks` receive `rederive` (the stale items to re-derive in place, FR-041) and `blocked` (the items not to derive from yet).

The implement wrap calls `enter implement` once for the list, then `enter implement --task T###` before starting each task. A task ticked while blocked is detected by `sync` (D-34 snapshot taken while the task was blocked) and appears first on the `tasks` list.

**Rationale**: The helper decides and names what is blocked (Tier 1). Whether the agent then skips a blocked task is the same attestation limit as 001's R-3, and the per-task call makes a bypass a visible refusal in the transcript. Detection after the fact closes the loop in files.

**Alternatives**: keep document-wide refusal (the status quo that Story 1 exists to remove); a helper that edits `tasks.md` to strike blocked tasks (rejected: the helper would rewrite core Spec Kit output, and the change would be noise in the diff).

### D-36 One review-list protocol for every list in the feature (FR-005, FR-006, FR-010, FR-017, FR-040, FR-049, FR-048)

**Decision**: A single helper family, `eil review list|answer|confirm`, serves every list kind: `inferred`, `changes`, `tasks`, `evidence`, `low-challenges`, `unknown-currency`, `diagram-currency`, `unsettled-challenges`. `review list --stage S --kind K` prints the entries in a fixed order (by severity or risk, then document order), each with an id or block key, its purpose (FR-032), what changed, and any AI view labelled as the AI's. It also prints a **list digest**: SHA-256 of the entries' keys and current hashes. `review answer` takes the digest shown, the parsed reply (`--all`, `--all-except IDS`, `--question ID`, `--reopen IDS`, `--defer-reason R`), the person's name and their **verbatim reply** (`--reply "ok except T014"`). It refuses `list-changed` when the digest no longer matches, so an answer is only ever recorded against the list the person saw. The AI turns the reply into flags, the helper records both, and the verbatim reply is what the audit shows.

Authority (FR-048): an answer that settles something (accept, re-confirm, re-establish, defer, lower severity, carry forward) requires a configured confirmer of the stage and is never the AI (`not-a-confirmer`, `ai-approval`). Question, reopen, raise severity and reclassify-as-inferred are open to anyone and recorded with the name given. The derived stages s04 to s07 gain optional config keys (`ai-spec`, `plan`, `tasks`, `verification`), each defaulting to the `technical` approvers list, and therefore to the story's developer when that list is empty.

**Limit (Constitution II)**: The helper cannot prove that the flags match the reply. The AI reads "ok, except T014" and passes `--all-except T014`. The helper records both, so a mismatch is visible in the record, and it refuses the two mismatches it can recognise deterministically, `reply-mismatch`:
- a reply that is only an all-phrase ("ok", "ok to all", "yes", "accept all", "approve all", "defer all", in any case, with trailing punctuation) given with any flag other than `--all`;
- `--all` given with a reply that names any entry key on the list, as a whole token (for example "ok to all except T014"). Ordinary words such as "but" are not tested, so "ok to all, but note the typo" with `--all` is accepted (found by `/speckit-analyze`, F3).

Anything subtler is attestation-level. That limit is printed in every list's `limits[]` and stated in the README.

**Answers that add scrutiny do not need the list (FR-050)**: A settling answer (accept, re-confirm, re-establish, defer) must carry the digest of the list the person saw. A `--question` or `--reopen` answer may instead name **any entry of that kind settled for the stage since its last approval** (for `changes`), or **since it was recorded** (every other kind), with no digest. An accepted entry leaves the list, so without this nobody could question it afterwards and the conflict below could never arise (found by `/speckit-analyze`, F1).

**Conflicting answers (FR-050)**: The first answer for an entry at a given content hash records it. A later answer by a **different** person that settles what the first left unsettled, or unsettles what the first settled, marks the entry `conflict` with both answers. A same-direction answer from another person is a no-op, and the same person may change their own answer. A conflicted entry:
- is excluded from coverage, so `confirm` refuses `acceptance-conflict`;
- blocks its dependants (D-35);
- is resolved only by a confirmer answering it again, recorded `resolved_conflict: true`.

This mirrors `challenge answer` (001 contracts/cli.md).

The existing `review start|accept|finish` (D-28) remain as compatibility aliases over `list --kind changes` and `answer`/`confirm`. `amend` remains as an alias that runs `confirm` with its `--from` ids checked as a subset of what the helper found.

**Rationale**: FR-017 requires one form everywhere, and one code path makes that a property of the implementation rather than of six prompts. The digest turns "one reply to one list" into something the helper can check.

**Alternatives**: a subcommand per list kind (rejected: six parsers for one protocol, and the forms drift apart); letting the AI record per-item acceptances in a loop (rejected: the per-item ceremony this removes, and no record of the one reply the person actually gave).

### D-37 Change acceptance and carried-forward approval (FR-015 to FR-020, FR-026)

**Decision**: `review list --kind changes --stage S` computes, with no ids from the person, every changed block and item since the last approval, including upstream items reaching in through `upstream_items` (D-26/D-28 core), and splits them into:

- **covered**: carries a valid `(decided: ID)`, or has a recorded acceptance since the approval;
- **uncovered**: everything else, flagged `inferred: true` where the block is inferred.

`review confirm --stage S --by N --confirmation TEXT` re-signs:

- If **every change is covered**, the approval is recorded with `"reached": "carried-forward"`, `"rests_on": [ids]` and `"sign_off": TEXT`. The helper's explanation (each change and its covering decision) is what the prompt shows first, and TEXT may be a bare "ok" (FR-018, Constitution II). No attestation length rule and no comprehension check apply.
- **Otherwise** the uncovered list must be fully answered first (`changes-unanswered`). When any uncovered change was inferred, the delta comprehension check (D-27) must be current (`comprehension-prerequisites`, FR-019). The approval is `"reached": "reviewed"` with the acceptance ids.

The first approval is `"reached": "first"`, and absent means first (FR-020). The overview's Approvals table and `status` show `reached` and `rests_on` as visibly as an override.

On confirm, any rejected or deferred challenge whose target is among the changed ids is listed as `unsettled-challenges` for the stage's confirmers (FR-026). This is surfaced as a `human` next action, not a refusal.

**Rationale**: `amend` and `review finish` already share one coverage core (D-28). This makes the helper compute the ids `amend` asked the person to type, and collapses three entry points into one.

**Alternatives**: carrying forward with no sign-off (rejected on 2026-09-30, clarification Q1: every approval is a recorded human act); keeping all three commands as first-class (rejected: the confusion Story 3 describes).

### D-38 Backwards correction as one action with an impact preview (FR-021 to FR-024, FR-027, FR-045)

**Decision**: `eil correct propose --item ID --found-in STAGE[:ID] --problem TEXT` is read-only. It returns:

- the **owning-stage candidates**: the stage that defines `ID`, plus, when `ID` is a restated block, the stages of its cited sources;
- `ambiguous: true` when there is more than one candidate;
- the **impact list**: every downstream id that would become stale, from `graph.downstream`.

`eil correct open --item ID --owner STAGE --found-in … --problem … --by N` records a correction `CR-###` in the owning stage's provenance region with its origin. It refuses `owner-ambiguous` when there are several candidates and `--owner` is absent, so the person decides and the AI does not (FR-023). An open CR blocks, through D-35, only the tasks tracing to the items it concerns (FR-025).

The AI then edits the owning document in place (FR-042). When the person gave the corrected wording, `correct open --wording` stores it verbatim in the CR, and the edit carries `(decided: CR-###)`. The helper accepts that clause only when the item's text equals the stored wording (it cannot tell who wrote the wording, an attestation-level limit printed on the `changes` list), so the change is covered and the stage carries forward on a sign-off (D-37). When the AI drafted the wording, the edit has no clause and flows through `review list --kind changes` like any other change. When that stage is re-signed, the CR closes, and a Change Log entry records `origin: CR-### (found in implementation, T014)`. A CR owned by a never-approved stage (ai-spec, plan, tasks, verification) cannot close on a re-signing, so `review confirm` on such a stage closes each open CR whose item is settled (decided by the CR's wording, or reviewed on the `inferred` list), writes its Change Log entry and writes no approval; it refuses `not-amendable` while the item is unsettled. A clause whose text no longer equals the wording (a mismatch, or one left behind after a later edit) is a non-blocking `decided-source-invalid`, which narrows the 001 integrity rule for `CR` only: the text drifting from the wording is ordinary review, not unverifiable provenance, so the change is simply uncovered. A `CR` id that does not exist stays an integrity finding. `trace --to ID` shows the CR in the item's chain (FR-024). A code-review finding (FR-027) is an `RF-###` item in a new s07 `## Review Findings` section with `Root: implementation | <upstream id>` and `(status: open|resolved|excepted)`. An upstream-rooted RF is the `--found-in` origin of a CR. `VER-G07` and completion refuse while an RF is open (`review-finding-open`). The completion approval records `review_findings: {RF-id: hash}`. `package.state("completion")` reports `needs-re-review` ("review finding recorded after completion") when s07 holds an RF that is new or changed against that snapshot. That is the spec's edge case of a finding reported after completion (found by `/speckit-analyze`, U2).

When completion finds a design/code difference the person accepts (FR-045), the complete prompt opens a CR against the design item with origin `completion`. An accepted deviation that keeps the document describing a future target remains possible as today, with its reason recorded.

**Rationale**: SC-005 allows at most 3 interactions from finding to re-signed stage when the correction is the person's own wording: the report with the wording, agreement to the impact preview, and the carried-forward sign-off. Making the person's recorded wording a decision is what keeps it to three. Without it, the same edit would be accepted twice (at the preview, then on the `changes` list, against Constitution IV), and an edit with no verdict is inferred, which adds the delta comprehension check (FR-019). The propose/open split gives the person the impact before anything changes (FR-022) without the helper editing prose.

**Alternatives**: routing corrections through `clarify` and `resolve` (the status quo, with origin lost); the helper writing the correction text (rejected: prose is the AI's to draft and the person's to accept; the helper only records).

### D-39 Documents describe current truth; the Change Log is generated (FR-042, FR-043)

**Decision**: The provenance region's `changes[]` holds one entry per change accepted when an approvable stage is re-signed after its first approval, and one per closed correction in a never-approved stage (re-derivations there are left to git): `{"at", "item", "summary", "summary_by", "origin", "accepted_by"}`. `summary` is written by the AI at acceptance time and shown to the person before they answer: on the list (`review answer --summaries`) for uncovered changes, and with the explanation before the sign-off (`review confirm --summaries`) for covered ones, so they accept it with the change. `confirm` refuses `summary-missing` for any change left without one. The helper renders `changes[]` into a second marked region, `changelog`, under a `## Change Log` heading at the end of the document, as a Markdown table. That region is excluded from the fingerprint and from section fingerprints. The overview shows the five most recent entries across the story. No superseded text is kept. Git holds it.

The summary is AI-drafted (Constitution II). The rendered column is headed **Change (AI-drafted, accepted as shown)**, and the entry records `summary_by: "ai"`. The person accepted it as shown, because it was on the list they answered, but it stays labelled as the AI's wording.

**Rationale**: The readable log must not be a changing input to the thing it logs. Rendering from the region keeps one source of truth, and blocks.py already knows how to read regions.

**Alternatives**: a hand-kept Change Log section (rejected: FR-043 says generated); a log inside the provenance JSON only (rejected: not readable in a pull request).

### D-40 Challenge severity and focused gate output (FR-028 to FR-031)

**Decision**: `eil:challenge` records gain `"severity": "high|medium|low"` and `"severity_history": [{from, to, by, at}]`. `challenge add --severity` is required from the AI (proposal, labelled). `challenge severity ID --to LEVEL --by N` changes it: lowering requires a confirmer, raising does not (FR-048). A record without a severity (written before this feature) is treated as **medium**, which keeps blocking as it does today. `approve` refuses `open-challenge` only for high and medium. Open low challenges are copied into the approval record as `"outstanding": [ids]` and listed in the overview. Completion still refuses any open challenge, and offers the `low-challenges` list (FR-040).

`check` output gains `"summary": {"met_structural": N}` and orders criteria unmet, then judgment, then met. Text output collapses met structural criteria into one line, and `--full` restores the full listing. Duplicate suppression already exists (`duplicate-of-closed` also covers an equivalent open challenge). The only change is that the refusal now returns the existing id, so the prompt shows it once (FR-031). Every `next_action` and every list entry carries `"purpose"` (FR-032).

**Rationale**: Blocking is proportionate (Constitution IV, Constraints of Record). Records predating the feature default to the current behaviour, so an upgrade silently loosens nothing.

**Alternatives**: defaulting old challenges to low (rejected: an upgrade would silently unblock approvals).

### D-41 Completion asks only about what implementation touched (FR-033 to FR-035)

**Decision**:

- **Touched artefact**: an `ART` reached, directly or through an AIS item citing it, by a task carrying a `(code: …)` clause, or an `ART` whose hash differs from its owning approval. Only touched artefacts appear on the `diagram-currency` list at completion. The rest are listed as untouched in s08 by the complete prompt from `status` output, with no question.
- **Confirmed automated evidence**: an EVD row with `Kind: automated` whose `Evidence` names a test as `path::name` (pytest node id form) or `path` plus a test name. It is confirmed when the file exists inside the repository and contains that name as an identifier (a `def`/`function`/`test(`/`it(` match or a plain whole-word match). That is file reading only: no execution and no network (FR-035). The report states "the test exists; its result is attested, not observed". Unconfirmed automated rows and all manual rows go on the `evidence` list.

**Alternatives**: running the tests (rejected: 001 constraint D-21, and CI already does it); asking about every artefact (the status quo).

### D-42 Upgrade adoption (FR-047, FR-008)

**Decision**: When a stage document has no provenance region, the first **writing** command (`sync`, which `enter` and every stage command run) creates it:

- **Approved and unchanged** (the approval fingerprint equals the current one): every block is recorded with `"class": "adopted"` and `"basis": "approval <by> <at>"`, which counts as reviewed. Nothing is asked.
- **Approved and changed since**: the blocks covered by the approval's `items` and unchanged `section_fingerprints` are adopted. The rest wait for `review list --kind changes`.
- **Never approved**: untagged blocks are adopted as reviewed under the earlier rules, and tagged blocks are inferred and unreviewed.
- **Derived documents (s04 to s07)**: no source versions, so each is `currency: unknown` until answered once (D-34).

`status` and `check` compute the same adoption in memory without writing, keeping determinism requirement 9 (read-only), so their output is identical before and after the first `sync`.

**Rationale**: The spec says an in-progress story is adopted without questions (FR-047). Doing it in the command that already writes keeps read-only commands read-only.

### D-43 Measuring SC-001: an interaction-counting scenario harness

**Decision**: A reference-story fixture (`tests/fixtures/reference_story.py`: 4 REQ, 3 UC, 12 FR, 5 DEC, 8 ART) and two scripted runs. The 001 command sequence cannot be replayed on the changed helper, so the **001 baseline is captured once**: the run uses the **current** harness and fixture against the **baseline helper** in a git worktree checked out at the tag `eil-001-baseline` (made on the commit of task T001). The fixture is built without the new regions and `RF` items, which the 001 helper does not know. The run writes its counts to `tests/fixtures/baseline-001-counts.json`, which is committed and regenerated only deliberately with `--update-baseline` (found by `/speckit-analyze`, A1). The 002 sequence runs on the current code. Both perform the same edits: one decision correction mid-implementation, one resolved question and one design/code deviation. The harness counts each helper call that carries a person's name (`--by`) and tags it `decision`, `first-approval`, `inferred-review` or `other` from the subcommand and list kind. SC-001 passes when `other` falls by at least 60% and the first two counts are equal. SC-002 to SC-005 are scenario assertions on the same fixture. SC-006 and SC-007 are added to `docs/trials.md` as probes and are not automated.

**Alternatives**: timing real sessions (rejected: the spec's Assumptions say scenario harness, not human timing).

### D-44 Performance

**Decision**: Block splitting and hashing reuse the per-command `Package` parse cache. The only new per-command costs are one SHA-256 per block and one graph walk. The existing budget (under 1 s for `status` on nine documents of 1 MB each, `tests/unit/test_performance.py`) is kept, and the same test gains a case with provenance regions holding 2,000 blocks.

---

## Risks and tests

| ID | Risk | Effect | Mitigation / test |
|----|------|--------|-------------------|
| R-16 | The AI marks a block "adds nothing" when it does add something | An inferred behaviour treated as restated | The person can reclassify (FR-013); the fidelity limit is printed on every list (FR-014); SC-006 trial probe; the classification file cannot create a citation, only narrow one |
| R-17 | Paragraph-level keys churn when a person rewraps text | Spurious "needs attention" | Whitespace normalisation (steps 2, 5, 6) removes rewrap differences; a unit test rewraps a paragraph and expects no change |
| R-18 | The agent implements a blocked task anyway | Work on a stale basis | Per-task `enter implement --task`; a task ticked while blocked is detected by `sync` and listed first (D-35); attestation-level like R-3 |
| R-19 | A list is answered after it changed (a concurrent edit) | Acceptance of something not seen | List digest; `list-changed` refusal (D-36) |
| R-20 | The upgrade silently loosens a gate | Loss of assurance | Old challenges default to medium; derived layers default to unknown currency; only approved-and-unchanged content is adopted (D-40, D-42); a scenario test upgrades a 001 fixture and asserts nothing previously blocked becomes unblocked except by an explicit answer |
| R-21 | A hand-edited provenance region forges a review | False "reviewed" status | Same class as R-7: visible in the diff (name, time, verbatim reply); not preventable; stated in the README |

## Outcome

No `NEEDS CLARIFICATION` remain. All 50 functional requirements map to D-30 to D-44 or are unchanged guarantees (FR-036 to FR-038, enforced by existing refusals and by D-36's authority rule, with a regression test for FR-038). `/speckit-analyze` (2026-09-30) findings C1, I1, U1, U2, A1 and I4 are resolved in D-36, D-32, D-38, D-43 and D-39.
