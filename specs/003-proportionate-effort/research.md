# Research: Proportionate Effort

Decisions continue the numbering of 001 and 002 (D-46 onwards; risks R-22 onwards). Each decision names the requirement it serves, what was found in the code or in the 2026-10-01 trial, the choice, and what was rejected.

## Evidence gathered for this plan

- **Trial snapshot reproduction (upgrade).** The rich specification viewer at commit `2cceacc` (story 001 before the 2026-10-01 session) was copied to a scratch directory, and this repository's current helper was run against it. At `2cceacc` every approved stage adopts cleanly (Functional 64 settled, Technical 33 settled). At the next commit, `bd7a0d5`, one paragraph and one diagram changed in each of s02 and s03. The approvals there have an `items` map but no `section_fingerprints`, so `blockstatus.adopt` adopted the numbered items and **no unnumbered block**: Functional reports 17 blocks and Technical 19 as needing review. That matches the 18 and 19 `inferred` entries in the trial's final records. This is the root cause behind change 2.
- **Record bulk.** Provenance regions in the trial are 58% to 87% of each stage document. For example, `s06-tasks.md` of story 002 is 96,859 bytes, 83,574 of them in the provenance region.
- **Targeting.** `cli._persist_feature_json` returns early when `.specify/feature.json` exists. `commands/speckit.specify.md` says it "records `.specify/feature.json` if there is none". `speckit.eil.requirements.md` step 1 reuses the pointer whenever it names a directory.
- **Branch.** The trial project's `.specify/extensions.yml` installs only `eil`. No `before_specify` hook exists, and nothing in this extension touches git except `identity.py`, which reads `git config user.name`.
- **Classify.** In `provenance.classify`, a numbered block that is left out of a submission falls through to the "inferred" branch, so a restated item becomes inferred. An unknown key fails the whole submission with "not a block".
- **Plan headings.** `_PLAN_EXEMPT` in `gates.py` lacks "Change Log" and "Record", which `trace.ADMINISTRATIVE_SECTIONS` already holds.
- **Cue.** `provenance.render_cues` appends ` [ai-draft]` to the first line of each unreviewed block. An agent edit whose matched text spans that line's end therefore fails.
- **Terminal state.** `overview.next_action` falls through to "Continue {stage}" for verification, which is never approved, even after completion is approved.

- **SC-005 measured (T076, 2026-10-03).** `tests/scenario/test_interaction_count.py::first_pass` counts a developer's replies from requirements to implementation on the reference story, with the helper deciding every count it can (decisions asked, the wireframe criterion, comprehension levels planned as questions after each stage's list is answered, the lists themselves):
  - under 002: 3 approvals, 5 decision questions, 1 wireframe export, 6 review lists, 10 comprehension questions: **25 replies**;
  - under 003 with the profile: 1 authorisation, 3 approvals, 3 decision questions (the 2 with no observable effect are `ai-decided`), 0 exports, 4 review lists, 4 comprehension questions: **15 replies**.
  - That is a **40%** reduction, short of SC-005's 50%. Approvals (3) and observable decisions (3) are unchanged, as SC-005 requires. The test asserting 50% is marked `xfail(strict=True)` so the gap stays visible. The remaining replies are the three definition lists, the approvals and the observable decisions, which this feature deliberately keeps; reaching 50% would need a further cut that the spec does not authorise (for example one list for all three definition stages). The human timing run (T100) is the measure that matters for SC-003.

- **Manual check on the trial project (T089, 2026-10-03).** Run on a scratch clone of the rich specification viewer, never the original, with this branch's helper copied in:
  - at `bd7a0d5`, story 001: `status` reports Functional and Technical `needs-re-review` with **0** blocks needing review (17 and 19 `settled-pending`), against 17 and 19 before this feature. `sync` moved every record to `eil-record.json`, and every stage document's fingerprint was unchanged (only the generated `s00-README.md` differs). The documents shrank only 6% to 25% at this commit, because their records were still small;
  - at `a267058`, story 002 (the trial's): `s06-tasks.md` went from **96,894 to 12,434 bytes (87% smaller; SC-002 asks for at least 75%)**, `eil show tasks` prints 11,153 bytes, every stage fingerprint and every stage state is unchanged, and the record file holds 241,256 bytes.

## Decisions

### D-46 The active-story pointer and the target of every call (FR-001 to FR-005)

**Decision.**
- `eil start` always writes `.specify/feature.json` and returns `pointer: {previous, current}`.
- Resolution returns the directory together with its **source**: `argument`, `environment` or `pointer`.
- Each subcommand is declared `writes` or `read-only` in one table in `cli.py`.
- For a `writes` call whose source is `pointer` (or none), the helper applies the FR-003 rules and refuses with `ambiguous-story` before any read-modify-write. The refusal lists the candidates and `--feature-dir` as the fix.
- Every result of every subcommand carries `story` (the directory name), and the text form starts with `Story <name>:`.
- `speckit.specify.md` and `speckit.eil.requirements.md` no longer reuse a pointer that names a governed story.

**Rationale.** The pointer is the only implicit state, so making it correct at start and checking it before writes removes both the damage (an approved record overwritten) and the hundred `--feature-dir` flags. Classifying subcommands in one table makes the rule testable: the test iterates the table.

**Rejected.**
- *Requiring `--feature-dir` on every write.* That is the repetition the trial complained of.
- *Inferring the story from the current branch.* Branch and directory names are independent in Spec Kit.

### D-47 Starting a story on an unexpected branch (FR-006)

**Decision.**
- `eil start` reads the current branch with `git symbolic-ref --short -q HEAD`. This is a local, read-only git query, as `identity.py` already makes for `user.name`; there is no network access.
- The start is refused with `unexpected-branch` unless the branch is one of `main_branches` (a new configuration key, default `[main, master]`), or the branch equals the new story's directory name or starts with its number prefix (`003-`).
- The developer confirms with `eil start ... --on-branch <branch> --by <name>`. The confirmation is recorded in the record file (`story.start`) and shown on the overview.
- With no repository, or a detached HEAD, the start proceeds and its result says so.
- The helper never creates or switches branches.

**Rationale.** This is the clarified behaviour (2026-10-02). Configurable main branches avoid false refusals in projects that use `trunk` or `develop`.

**Rejected.**
- *Creating the branch.* That is the git extension's job, and doing it here would change project state outside the story.
- *Reading `.git/HEAD` directly.* That breaks in worktrees, where `.git` is a file.

### D-48 One record file per story (FR-007 to FR-011, FR-013)

**Decision.**
- Each story directory gains `eil-record.json`. Its shape is in data-model §Record file: per-stage `provenance`, `assessment`, `approval` and `comprehension` objects, plus story-level `profile`, `start` and `review_sessions`.
- The marked regions stay in the documents, with the same names and the same positions, but each now holds **rendered Markdown only**:
  - `approval`: one line per approval or override;
  - `comprehension`: one line of counts;
  - `assessment`: one line of met and unmet counts;
  - `changelog`: as today;
  - `provenance`: one line of block counts by status.
- Fingerprinting already excludes all five regions (`fingerprint.EXCLUDED_REGIONS`), so no fingerprint changes and every approval stays valid (FR-009).
- All reads go through one `Package.record(stage, name)` accessor, which prefers the file and falls back to a JSON region body (a document not yet migrated, which is the partial-migration edge case). All writes go through `Package.write_record(stage, name, obj)`, which writes the file and re-renders the region line.
- The JSON is written sorted with two-space indentation, stage by stage, so that diffs stay local.

**Integrity (FR-011).** An approval line in a document with no matching record in the file reports `approval-record-missing`, and the stage becomes `needs-re-review` with the reason "approval record missing or unreadable". A malformed file reports `malformed-record-file`. Neither is ever treated as valid. The attestation limit is unchanged and stated as R-25.

**Migration (FR-010).** `sync` (a write) moves each JSON region body into the file and renders its line. `status` and `check` without `--judgments` read both forms and write nothing (determinism 33 still holds).

**Rationale.** The trial's context exhaustion came from agents reading documents whose bulk was records. Keeping the regions as rendered lines keeps a reader of the document alone informed (Principle II) and leaves the fingerprint rules untouched.

**Rejected.**
- *A file per stage.* That is nine more files beside nine documents, more confusing to readers.
- *A hidden `.eil/` directory.* Records would be missed in review.
- *Compressing the regions.* Still bulk in the document, and unreadable.

### D-49 `eil show` (FR-012)

**Decision.**
- `eil show <stage> [--items ID,...] [--section NAME]` is read-only.
- It prints the document with every region replaced by its rendered line, HTML comments dropped and fences kept.
- After the first line of each block that needs review it prints a cue (`[ai-draft]`, see D-50). `ai-decided` decisions are marked `[ai-decided]`.
- `--items` prints those items' blocks with their section headings.
- The JSON form also returns `blocks` with key, status and line range, so a prompt can address a block without reading the file.
- Every stage prompt replaces "read `sNN-*.md`" with `eil show`, and states that `eil-record.json` is never read directly.

**Rationale.** FR-012, and the "do it in chat" principle.

### D-50 The review cue leaves the document text (FR-037)

**Decision.**
- The helper no longer writes `[ai-draft]` into documents. The cue appears in `eil show`, in review lists and on the overview, where the count of blocks needing review is given per stage.
- `sync` strips existing tags once. Tags are fingerprint-neutral (D-23), so no approval moves.
- The helper then writes no prose at all, which restores 001's invariant that it edits only regions and records (the D-28 and `resolve` exceptions remain).
- This amends 002 FR-046 (the tag appeared in the document).

**Rationale.** Any tag inside text that an agent edits by matching will break some match. Status has been hash-based since 002 (FR-039), so the tag carries no information the helper needs.

**Rejected.**
- *Keeping the tag and telling the agent to re-read before editing.* That is Tier 2 only, and the trial shows it fails.
- *Moving the tag into an HTML comment line above the block.* That still breaks multi-line matches.

**Trade-off.** A person reading a raw document no longer sees which paragraphs await review. The overview's count and `show` cover this (R-26).

### D-51 Review list modes and stored answers (FR-014 to FR-018)

**Decision.**

*Choosing the mode*
- `review list` returns `mode` and `threshold`. The mode is `one-at-a-time` when the list has at most `review.one_at_a_time_max` entries (new configuration key, default 8), and `summary` otherwise.
- The mode is fixed by the list's digest. Once the first answer is stored, the open **review session** in the record file holds the mode, and later `review list` calls return that session's mode and only its unanswered entries (FR-016).

*Answering one at a time*
- `review answer` gains `--entry KEY` for one entry and `--rest` for "ok to the rest".
- `--rest` records each remaining entry as accepted with `seen: false`.
- A session closes when every entry is answered. Its answers are then applied exactly as a whole-list answer is today, through the same authority, conflict and verbatim-reply rules (002 D-36). A partial session settles nothing, so an interrupted list blocks no less than an unanswered one.

*Summary mode*
- Entries are grouped by section. Each carries `summary`, computed deterministically: the item title for a numbered item, otherwise the first sentence, cut at 120 characters.
- `review show --entry KEY|--group NAME|--all` prints full text (read-only).

*What appears on a list*
- The blocks of `SCAFFOLDING_SECTIONS` (Actors, Dependencies, Not applicable, Inputs, Outputs) form one entry per section, with key `§<Section>`. Answering it answers every member block.
- A list only ever holds blocks whose status is `needs-review`, so restated and adopted blocks cannot appear. A unit test pins this, and the prompts are told to present the list as given.
- Every acceptance record, whole-list or per entry, stores `mode`, so a reader can see that a summary-mode "ok" was given on summaries (R-24).
- A stored answer applies only to the entry's hash. If the entry changes before the session closes, its answer lapses and it reappears.

**Rationale.** These are the clarified behaviours. Storing answers in the helper removes the in-chat tally that compaction lost, and a deterministic summary keeps the AI out of what is shown as a summary.

**Rejected.**
- *AI-written summaries.* Not deterministic, and they would let the AI shape what the developer validates.
- *Recording the mode when the list is first listed.* That would make `review list` a write.

### D-52 Small-story profile (FR-019 to FR-022)

**Decision.**

*Recording it*
- `eil profile set small --by <name> --reason <words>` and `eil profile withdraw --by <name> --reason <words>` are writes. Their authority is `abbreviation_authorisers`, as for `abbreviate`.
- The profile is stored in the record file under `story.profile`, rendered on the overview, at every affected gate and in `trace`.

*Its effects (Tier 1)*
- **Functional gate:** the wireframe criterion is met with the reason "small-story profile, authorised by X on DATE" and shown as such.
- **Derived review:** `review list --stage derived --kind inferred` builds one list from the AI Specification, plan and tasks. `profile set` also records an override of `unreviewed-ai-content` scoped to `enter plan` and `enter tasks`, with `by` and `reason` taken from the profile and `basis: small-story profile`; `enter` honours it exactly as any recorded override, and `profile withdraw` withdraws it, recorded the same way. This keeps the constitution's rule that a gate criterion is passed only by a named, reasoned override (clarified 2026-10-02: for a small story, developer experience takes priority over the rework risk). `enter implement` refuses until every entry of that list is answered (in one reply or entry by entry), so implementation is never reached with an unreviewed inferred block (the 002 FR-049 guarantee holds at implementation).
- **Comprehension:** `comprehension plan` asks two fixed levels, `explain` and `apply`. The other three are recorded `not-applicable` with the reason "small-story profile (authorised by X)".
- Every other criterion, approval, challenge rule and override is unchanged (FR-022).

*Proposing it (Tier 2)*
- The specify wrap and the Requirements command may propose the profile, naming the signals they saw, labelled "AI assessment:".
- The abbreviate prompt's "do not decide that a story is small yourself" stays. Its ban on suggesting abbreviation is replaced by "you may propose; only a person authorises".

*Withdrawing it*
- Withdrawal restores every effect for stages not yet approved. An approved Functional stage without wireframes stays approved, and its record shows the profile it was approved under.

**Why `explain` and `apply`.** They test understanding of behaviour. `recognise` is trivial once the item text is shown (D-54), and `trace` and `evaluate` are the costliest to answer.

**Rejected.**
- *A profile per stage.* That is today's `abbreviate`, which nobody used.
- *Skipping the derived review entirely.* That would let unreviewed inferred content reach implementation.
- *Keeping planning blocked until the AI Specification is reviewed.* No override needed, but it keeps the separate review step the profile exists to remove.

### D-53 `ai-decided` decisions (FR-026 to FR-029)

**Decision.**

*Recording*
- A DEC may have `Owner: ai-decided`. The Technical gate's decision-fields criterion accepts it only with a non-empty `Reason:`. All other DEC fields stay required, and a person's name is still required for every other owner.
- An `ai-decided` DEC is always classified `inferred` (never `restated` or `decided`), so it is always on the stage's inferred review list, in its own group, "AI-decided decisions". The developer's one reply validates it (clarification 2026-10-02).
- The approval record lists `ai_decided: [DEC ids]`, and the approval line in the document names them.

*Converting one to a developer decision*
- The developer says they want to decide it. The prompt asks the question, then rewrites the owner to the person. The block's hash changes, and it is reviewed as any other change.

*Prompt rules (Tier 2)*
- Technical prompt: ask only about choices that change observable behaviour, scope or a trade-off, with a recommended option. Decide everything else as `ai-decided` with a reason. When unsure, ask.
- Functional prompt: never ask about mechanism; leave it to the Technical stage.
- The Technical prompt's "a technical decision is the developer's, never yours" and the `developer-choice-recorded` probe are narrowed to decisions with an observable effect.

**Constitution.** The AI does not make a human decision here. Every `ai-decided` DEC is put to the person on the review list and settled only by their reply, so the person still validates each one; what is removed is the question-and-answer turn about mechanism. No amendment is needed. See plan, Constitution Check.

**Rejected.**
- *Listing `ai-decided` only in the summary.* This was the clarified alternative. It would have left them settled without a person's reply.

### D-54 Comprehension changes (FR-030 to FR-034)

**Decision.**

*Own decisions*
- `comprehension plan` gains `--by <person>`.
- A target item counts as the person's own decision when either:
  - its block is classified `decided` and the decision record it cites (challenge answer, open-question resolution, correction or clarification) names that person; or
  - it is a DEC whose `Owner` is that person and whose block is settled.
- Such an item is skipped. The plan takes the level's next eligible item by the existing fixed formula. Where none remains, the level is planned as `own-decision`, naming the decision, and recorded with that outcome.
- `own-decision` is added to `OUTCOMES`, and `own_decision` to `COUNT_KEYS`, so approval records and the overview show it beside `skipped`.

*Waiver*
- `comprehension waive --stage --by --reason` records every level not yet recorded as `skipped`, with that reason, in one write.

*Prompt rules (Tier 2)*
- Before each question, show the target item's text with `eil show <stage> --items <ID>`.
- Ask about behaviour, not mechanism.
- Judge on meaning. Before hinting, re-read the answer against the item. If it could be right in meaning, accept it or ask the person to expand.

**Rationale.** These are the clarified behaviours. Who decided is a fact in the records, so the helper establishes it (Principle IV, third bullet).

### D-55 Gap checks while drafting (FR-035)

**Decision.**
- Before showing a stage's first inferred list, the Functional and Technical commands (the two stages with a comprehension check) run `eil comprehension plan --stage <stage>`, which is read-only and returns the targets for the current version.
- They apply the pre-scan's three checks (silent, ambiguous, self-contradicting) to those targets and their sections, raising any gap as a challenge.
- The comprehension prompt's existing pre-scan stays as the backstop.
- This is Tier 2, with a contract test and probe P-27.

**Rationale.** The helper's target formula is deterministic, so drafting can scan exactly what the check will ask about. In the trial, CH-007 and CH-008 would have been raised before the 38-block review.

### D-56 Upgrade adoption of approved stages (FR-023 to FR-025)

**Decision.**

*Adoption*
- `adopt` keeps its three paths. It adds one: an approval with no `section_fingerprints` on a changed document. In that case the unnumbered blocks are not left unadopted, which is today's behaviour. They are recorded as `adopted-pending`, a new class that means "covered by a legacy approval that cannot be compared".
- `adopted-pending` blocks are not `needs-review`, so they raise no `unreviewed-ai-content` and appear on no inferred list.
- Numbered items are adopted as today, by the approval's `items` map.

*Re-signing*
- The stage is `needs-re-review` as today. Its `changes` list gains one entry, `legacy:<stage>`, carrying the statement "this document changed since an approval the tool cannot compare section by section".
- The confirmer's single reply to that entry, then `review confirm`, re-signs the stage with `reached: re-signed-without-comparison` (a new `REACHED` value, shown wherever approvals are shown) and turns every `adopted-pending` block into `adopted`.
- `accept` uses this path instead of refusing (FR-025).

*Tags and judgments*
- No cue is written (D-50).
- Judgment verdicts are already kept per criterion basis (D-29).
- Assessment lists are kept when the document fingerprint is unchanged. Migration re-keys an assessment record written under an earlier fingerprint rule when that rule's fingerprint still matches the document.
- The first implementation task reproduces the trial's judgment loss on the `bd7a0d5` snapshot before the re-keying is built. If the loss came only from the wrong-story overwrite (D-46), re-keying is dropped and that finding recorded.

**Finding of the reproduction (T040, 2026-10-02).** On the `legacy_upgrade` fixture (`tests/unit/test_adoption.py::test_t040_the_trial_judgment_loss_is_reproduced_and_explained`):
- `sync` itself drops no judgment.
- The loss came from two causes, not one. The first is the wrong-story overwrite (fixed by D-46). The second is independent of it: a verdict written before 002's per-criterion basis (D-29) carries no `basis`, so `_prior_judgments` never treated it as current, and the first `check` after the upgrade discarded it even where nothing it judged had changed. The five assessment lists were dropped the same way when 002's `[ai-draft]` stripping changed the whole-document fingerprint of a tagged 001 document.
- So the re-keying is **kept**, and done where the judgments are read rather than in the migration: a verdict with no basis is current while the record's fingerprint matches the document's, under either the current rule or the 001 rule (tags not stripped). A verdict with no basis on a document that has changed since cannot be compared section by section, so it is still re-judged.

**Comprehension on a legacy re-signing.** Re-signing through the `legacy:<stage>` entry asks no comprehension question: the reply re-signs an approval the person already gave, is recorded as given without a comparison, and FR-025 names a single reply. The comprehension record already held is copied into the approval as before.

**Rationale.** This reproduces and removes the trial's 17 and 19 needless review items, and replaces a full re-approval with the one reply that was clarified.

### D-57 Classification is additive (FR-038)

**Decision.**
- A block left out of a `blocks classify` submission keeps its entry when its hash is unchanged. A numbered block is never reclassified merely because it was left out.
- An unknown key no longer fails the submission. It is returned under `skipped` with the current keys of the same section, and the known keys are recorded.
- Numbered items keep their id as their key, which is already so.

**Rationale.** These are the two trial failures. Ids for unnumbered blocks stay `section#hash`, because positional ids would shift on every insertion. The `skipped` list tells the agent the new key instead.

### D-58 Smaller defects (FR-036, FR-039, FR-040)

**Decision.**
- `_PLAN_EXEMPT` is built from `trace.ADMINISTRATIVE_SECTIONS` plus the plan's own non-derived headings, so the two can no longer drift apart.
- Every prompt that calls `challenge add` shows `--severity high|medium|low` in its example and says it is required. The helper's usage error already names it.
- AI Specification, plan, tasks and verification gain a terminal state, `reviewed`. It is reached when the document exists, its gate's code-decided criteria are met, and no block is `needs-review` or `stale`. `current_stage` skips `reviewed` stages.
- When completion is approved, `next_action` returns `done` with "Story complete; approved by X on DATE." `STAGE_STATES` gains `reviewed`.

### D-59 Short approvals (FR-047 to FR-049)

**Decision.**
- `eil` holds one fixed approval question per approvable stage (`APPROVAL_QUESTIONS` in `eil/records.py`), returned by `status` in `next_action.question` when the next step is an approval.
- `approve` records `question` (taken from that table by the helper, never from the AI) beside the verbatim `attestation`. The rendered approval line shows both: `Approved by Lee on 2026-10-03: "ok" to "Approve the Functional Specification as the behaviour you require?"`.
- The helper's acceptance rule is unchanged: any non-empty reply. Only the prompts change: ask the helper's question, accept the reply as given, ask the name once per session.
- The same applies to `complete` (completion approval) and to `review confirm` (change acceptance).
- The other short confirmations record what they answered too (constitution 1.2.2): a review-list reply is already tied to its digest and entries; the branch confirmation records `question: "Write story <dir> on branch <branch>?"` and the comprehension waiver records `question: "Waive the remaining comprehension levels for <stage>?"`, both fixed by the helper.

**Rationale.** The trial's friction was the prompt asking for a sentence, not the helper. Recording the question next to the reply keeps the record as clear as a written sentence (Principle II): a reader sees exactly what "ok" confirmed. The question comes from the helper so the AI cannot word what is being confirmed.

**Constitution.** Principle II's clause "A human confirmation MAY be a short acknowledgement ... when, and only when, every change since an approval is covered ..." reads as limiting short replies to carry-forward. A PATCH (1.2.2) clarifies that a short reply to an explicit approval question is an ordinary confirmation, and that the clause governs confirmations given without a fresh question. No principle's intent changes. See `constitution-patch-1.2.2.md` in this directory, applied with `/speckit-constitution`.

**Rejected.**
- *Requiring a minimum length or restatement.* Adds effort, not assurance: the question already states the content.
- *Letting the AI word the question.* The AI would then shape what the person confirms.

## Risks

- **R-22: merge conflicts in one record file.** Two branches that touch the same story produce conflicting JSON.
  - Mitigation: sorted, stage-scoped layout, so conflicts are local; a malformed file is reported loudly (D-48).
  - Accepted: one developer drives a story (002 scale assumption).
- **R-23: the AI marks an observable choice `ai-decided`.**
  - Mitigation: each `ai-decided` DEC is on the review list for a person's reply; the prompt says to ask when unsure; probe P-24.
- **R-24: summary-mode acceptance of unseen text.** The developer may accept entries on their summaries.
  - Mitigation: the session records the mode, and `seen: false` for entries accepted with "ok to the rest", so a later reader sees what was looked at (Principle II).
- **R-25: record file edited or deleted.** It is plain project text, like the regions it replaces.
  - Mitigation: approvals become unverifiable, never valid; the limit is stated in README (as R-7 and R-21).
- **R-26: the cue is gone from raw documents.** A reader in an editor or the viewer no longer sees unreviewed markers.
  - Mitigation: overview counts per stage; `show`.
- **R-27: branch-guard false positives.** A team using `feature/...` branches is asked once per story.
  - Mitigation: one recorded confirmation; configurable `main_branches`.
- **R-29: "ok" given without reading.** A one-word reply is easier to give carelessly than a sentence.
  - Mitigation: the question states what is confirmed and is recorded with the reply; the inferred-content list must still be answered first; the comprehension check still runs.
- **R-28: profile misuse.** A large story is run under the profile.
  - Mitigation: authorised by a named person with a reason, visible everywhere; every approval unchanged; the AI must say when the story outgrows it (Tier 2, P-23).
