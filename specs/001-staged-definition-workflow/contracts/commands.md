# Contract: slash command behaviour

Each command is a prompt that drives the AI agent and calls the helper (`eil`, [cli.md](cli.md)). "Guard" means the extension-present check (research D-08). Every command begins: **guard → `eil sync` → command-specific steps**, and **stops on a non-zero exit** from any helper call, printing the helper's `refusals[]` (code, message, fix). A governed-feature check (exit `3`) means: for a *wrap*, run the core command unchanged; for an `eil` command, say the feature is not governed and offer `speckit.eil.requirements` to start one.

## Preset overrides (D-13)

| Command | Strategy | Behaviour |
|---|---|---|
| `speckit.specify` | replace | Create the feature directory and `.specify/feature.json` exactly as core does, but **never write `spec.md`**. If the feature is already governed, refuse and point to the current stage's command. Otherwise call `eil start`, then continue as `speckit.eil.requirements` (FR-003, edge "writing through an alias"). The user's description becomes the input to the Requirements draft. |
| `speckit.clarify` | wrap | Before the core body: `eil enter clarify`. Exit `3` ⇒ core unchanged. If `s04` does not exist, refuse (`ai-spec-missing`) and say clarify needs an AI Specification; otherwise core runs. After each accepted answer the agent writes it into `s04-ai-spec.md` as a new `AIS-###` item tagged `[pending-clarification]`, with `target_stage` proposed but unset, and tells the human to run `speckit.eil.resolve` (FR-067). |
| `speckit.plan` | wrap | `eil enter plan`: sync, refuse unless `s04` exists, has no `[pending-clarification]` and passes source-traceability (`ai-spec-not-traceable`, `pending-clarification`) (FR-004). Then `eil stage-init plan` creates `s05-plan.md` and `plan.md`; core plan runs writing through the alias (F-7). Plan content not derivable from an approved `DEC` is flagged (FR-057). Every plan section carries `(traces: DEC-###)`. |
| `speckit.tasks` | wrap | `eil enter tasks`: sync, refuse unless `s05` exists and `s04` still passes. `eil stage-init tasks` creates `s06-tasks.md` and `tasks.md`. Each task line carries `(traces: AIS-###)` (FR-031); a task that introduces architecture is flagged (FR-058). A task that builds a screen, schema or technical flow cites the `ART` it implements, and `eil check --stage tasks` reports any in-scope wireframe, ER or technical sequence diagram reached by no task (`artifact-uncovered`, FR-083). |
| `speckit.analyze` | wrap | Core analysis over the three aliased files, unchanged, **followed by** `eil check --chain --json`; findings are appended in the same table style, ids prefixed `T-` (trace) so they don't collide with core ids (FR-068). |
| `speckit.checklist` | wrap | Core body over `spec.md`, plus instruction to also read `s01` and `s02` as read-only context (OQ-001, D-13). |
| `speckit.implement` | wrap | `eil enter implement`: sync, refuse unless `s05`, `s06` exist, no pending clarification, no unresolved alias fault. Ambiguities found while implementing are surfaced and answered through `clarify` or `resolve`, never assumed (FR-041). |

## Extension commands

All refuse on the conditions in [cli.md](cli.md); the table gives what the *agent* must do around the call.

| Command | Preconditions | Agent steps | Ends with |
|---|---|---|---|
| `speckit.eil.requirements` | none (creates the story if none) | `eil start` if not governed; draft `s01` from the user's input with every required heading; draft the **system context diagram** (C4 Level 1) as an `ART` item with a Mermaid fence, from the users, stakeholders and dependencies just written, marking each element `[existing]`, `[new]` or `[changed]` (FR-072); tag anything AI-authored `[ai-draft]`; do **not** convert an open question to an assumption (FR-022); run `eil check`; run the challenge pass (below) | Report gate result and open challenges; do not offer to approve until both are clear |
| `speckit.eil.functional` | `requirements` approved | `eil stage-init functional`; derive `FR`/`NFR` from approved `REQ`/`UC`, each with `(traces: …)`; flag implementation prescription (FR-020); draft one **system-level sequence diagram** per use case (or record why none applies), participants only the declared actors plus `System` (FR-073a); list each screen or screen state that needs a **wireframe** as an `ART` item and ask the human to export it (`speckit.eil.artifact`), never drawing or editing one (FR-085); `check`; challenge pass; then offer `speckit.eil.comprehend` (FR-087) | as above |
| `speckit.eil.technical` | `functional` approved | `eil stage-init technical`; capture decisions as `DEC` with reason, rejected alternative, trade-off, owner = the developer (FR-032/033); AI may *propose* alternatives, but the developer's choice is what is written (US4-3); draft the **container diagram** (C4 L2, external elements matching s01's context), a **component diagram** per new or changed container (or record why none applies), a **technical sequence diagram** per use case that crosses containers (or record why none applies), each citing its `DEC`, and an **ER diagram** with `(store: …)` where persistent data changes (FR-074); `check`; challenge pass; then offer `speckit.eil.comprehend` (FR-087) | as above |
| `speckit.eil.ai-spec` | `technical` approved | `eil stage-init ai-spec`; assemble only from approved stages, every item `AIS-### (traces: …)` (FR-027); list each approved artefact the agent must read as an `AIS` item tracing to its `ART` (FR-082) and **draw no diagram of its own**; anything without a source is not written, it is raised as a challenge; `check` (source-traceability, including artefact currency) | Report; a passing check is the gate (no human approval, spec Assumptions); a human review is offered |
| `speckit.eil.verify` | `tasks` exist | `eil stage-init verification`; list every `REQ`, `FR`, acceptance criterion and approved `ART` with status and evidence (wireframe: screenshot review; ER: schema or migration comparison; sequence: integration or end-to-end trace; container and component: conformance evidence or exception); distinguish automated, manual, exceptions; list open tasks visibly; each exception records who and why (FR-059..061); never declare completion (FR-062) | Evidence summary and gaps |
| `speckit.eil.complete` | `verification` exists | `eil stage-init completion`; fill required content, including a **diagram currency** line per approved `ART` (current, or listed under accepted deviations with who and why, FR-084); ask the human directly to confirm they reviewed the evidence; `eil approve completion` with the verbatim answer | Approval or refusal (`unverified-requirement`, `unverified-artifact`, `verification-missing`) |
| `speckit.eil.comprehend` | `functional` or `technical` exists; `eil comprehension plan` accepts (other criteria met or overridden, no open challenge) | Run `eil comprehension plan --stage S`. **On a re-approval this is a delta check (D-27)**: the response carries `delta`; if `delta.human_decided` is true every level is `no-material` and is recorded `not-applicable` with the given reason, asking nothing; otherwise at most two levels are named (the rest are `no-material` the same way). **Pre-scan** — a backstop for the drafting pass's own sweep, not a second full one — the (at most five, or on a delta check at most two) target items for silence, ambiguity or contradiction and, if any is found, raise them all as one batch of challenges and stop before question 1 (plan again on the new version once they are answered); then for each named level in order, ask **one** question about the returned target items in the agent's own words (levels 1 and 2 may be multiple choice only where plausible alternatives exist; levels 3 to 5 are free text), wait for the human's answer, judge it on meaning (label it as the AI's judgement); on a wrong answer give a hint that points to a section or id **without stating the answer** and re-ask as a **newly worded** question at the same level, never the same wording twice; on `functional`, if the answer drifts into implementation, redirect to behaviour and re-ask without counting an attempt; on skip or reveal, say so plainly, record it, and offer a re-ask with `--attempt k+1`; if the document is silent, ambiguous or self-contradictory on the point, **raise a challenge (`eil challenge add`) and pause the check** rather than coaching either way (FR-091); after each level call `eil comprehension record --by <the human's configured name>`; **never write any question, answer or hint into any file, record or commit message**; no points, timers or praise mechanics (FR-094) | Counts by outcome, any challenges raised, and the next step: `approve`. Passing is not required (FR-093) |
| `speckit.eil.artifact` | an `ART` item exists that needs an export | Ask the human for the exported file and the Figma link to the exact frame (with `node-id`), or the source-tool link for an image of a diagram; **do not create, convert or edit the file**; run `eil artifact register`; report the record and the resulting stage state (re-review if the stage was approved) | The record, or the refusals (`artifact-no-provenance`, `artifact-format-not-allowed`, …) |
| `speckit.eil.challenge` | governed | Review the named stage; raise specific challenges with `eil challenge add`, or, when given a challenge id (or several, answered together in one reply), record the human's response with `eil challenge answer`; **never** answer on the human's behalf (FR-038); when an accepted challenge's fix is the human's own dictated words, write it untagged with `(decided: CH-id)` instead of `[ai-draft]` (D-24) | List of open challenges |
| `speckit.eil.approve` | stage is `in-review` | Run `eil check`; show the gate result and the diff since the last approval, and for `functional` and `technical` the comprehension counts (a stage with skipped or revealed levels is stated as such, FR-093); **ask the human directly** for their explicit confirmation (unless it is already given verbatim in the command's own arguments) and, optionally, who it was played back to; pass their words as `--attestation`; the agent MUST NOT supply the attestation itself (FR-012, D-11) | The approval record, or the refusals |
| `speckit.eil.override` | a gate is unmet | Ask the human for the criterion and reason; call `eil override`; state where it will be visible | Confirmation and where it now appears |
| `speckit.eil.amend` | stage is `needs-re-review` and was previously approved | Show the diff since the last approval; ask the human which recorded decisions (`CH`/`OQ`/`AIS`/`RVW` ids) cover every change, their name and their attestation; call `eil amend --from <ids>`; on `amend-not-covered` offer `speckit.eil.review` for what is left, or the full `speckit.eil.approve` (D-25) | The amended approval, or the refusals |
| `speckit.eil.review` | stage is `needs-re-review` and was previously approved | `eil review start`; walk the human through each changed item and section **one at a time**, showing the `git diff`; for each accepted one, `eil review accept --items`/`--sections`, one call per acceptance (or several from one batched reply); when every listed change is accepted, `eil review finish` — this also completes the comprehension check for the version if it is not already current, asking nothing when every change is covered (D-27); on `amend-not-covered` go back and review what is left, or fall back to `speckit.eil.approve` (D-28) | The re-approval, marked `reviewed_change_by_change`, or the refusals |
| `speckit.eil.abbreviate` | stage exists | Ask who authorises and why; `eil abbreviate` | Status note |
| `speckit.eil.resolve` | a `[pending-clarification]` exists | Decide with the human the earliest affected stage; `eil resolve`; show the human the recorded clarify answer next to the item being written, and write it **untagged** with `(decided: AIS-###)` when it is a verbatim carry (D-24), `[ai-draft]` otherwise; re-run `check` on it; if it was approved, it is now `needs-re-review` (only downstream stages that actually trace to the change follow, D-26) | Pending cleared or still blocked, with what remains; offer `speckit.eil.amend` in place of a full re-approval when the carry is the only change |
| `speckit.eil.trace` | governed | `eil trace` (forward, reverse, gaps) | Chain report |
| `speckit.eil.status` | governed | `eil sync` and `eil status`; regenerate overview | Current stage, approvals, outstanding items, alias health, the single next action |

## The challenge pass (used by the four definition-stage commands)

1. Read the stage document and its approved upstream documents.
2. Look for: gaps (a behaviour, failure or boundary with no definition), contradictions, unstated assumptions, untestable statements, implementation prescription at the wrong level, and unresolved decisions. Also compare each diagram and wireframe with the document text: a flow in the text missing from its sequence diagram, a diagram element the text never mentions, a screen state with no wireframe, an error path shown in one place and not the other, or a container with no data store where the text implies persistence. Wireframe content may be reviewed only if the agent can view the image, and is then a `judgment` finding, not a structural one (D-21).
3. For each finding, `eil challenge add` with a specific, actionable text and a `--target` item id. Do not re-raise an equivalent challenge that a human already `rejected` or `deferred` (FR-038).
4. Present the challenges to the human; the human answers; the agent records the answer with `eil challenge answer`. `accepted` means the document is changed; `rejected` needs a reason; `deferred` needs an explicit statement accepting the risk (FR-036).

Example, in the process standard's own words:

> AI: "The functional specification does not define what happens when two duplicate-detection requests arrive simultaneously."
> Developer: "That is intentional. Requests must be idempotent using the customer ID and analysis version."
> → recorded as challenge CH-004, `accepted`, and a technical decision `DEC-004`.

## Invariants for every command

- An `eil` command never writes an approval on its own initiative; only `approve` (with a configured human and their attestation) does.
- No command edits a stage document through an alias.
- No command creates a document before its stage begins, or an alias before its target (FR-048, FR-049).
- No command creates, converts or edits a wireframe or other exported file; only a human supplies one, and `artifact register` records it (FR-085).
- No command persists a comprehension question, answer or hint, and none records a comprehension outcome the human did not take part in (FR-092, FR-094).
- No command draws a diagram in `s04` to `s08` (FR-082, D-17).
- Whenever a command finishes, the overview reflects the outcome (FR-056), either directly or via the `after_*` hook.

## Feature 002 amendments (proportionate revalidation)

Folded in from `specs/002-proportionate-revalidation/contracts/commands.md` in the same change as the tests that pin
them. Where a row or rule below differs from the text above, this section governs. The 002 delta file is kept
as the record of the change.

### The one-reply list (used by every command that asks a person to review)

1. Run `eil review list --stage S --kind K --json`.
2. Show the `purpose` first, then each entry: its key, what it is or what changed, why it is on the list and any `ai_view` (already labelled), then the `limits` lines.
3. Ask for **one** reply: "ok to all", "ok except <ids>", or a question about one id. Do not walk the entries one at a time.
4. Call `eil review answer` with the list's `digest`, the person's name, their words **verbatim** as `--reply`, and the flags the reply means. Never supply, complete or improve the reply. For kind `changes` (and an `inferred` entry under an open correction), also pass the one-line summaries shown with the entries as `--summaries`; they are labelled AI-drafted and become the Change Log text.
5. On `list-changed`, show the new list and ask again. On `reply-mismatch`, re-read the person's reply and pass the flags it actually means; never change the reply. On a question, answer it, then offer the remaining list again. On `acceptance-conflict`, show both answers and ask a confirmer to answer again.

### New and changed extension commands

| Command | Change |
|---|---|
| `speckit.eil.accept` (new) | Accept changes to a previously approved stage (FR-015). Every change, covered or not, is shown with a one-line summary drafted by the AI and labelled as such. Show the helper's explanation of **covered** changes (each change and the decision covering it) and pass their summaries to `eil review confirm --summaries`. If there is no uncovered change, ask for a sign-off ("ok" is enough) and `eil review confirm`. Otherwise run the one-reply list of kind `changes` (its summaries go to `review answer --summaries`), then the delta comprehension check if the helper requires it, then one confirmation. For a correction owned by a never-approved stage (ai-spec, plan, tasks, verification): run its `inferred` list if the item is on it, then ask for the sign-off and `eil review confirm`, which closes the correction and writes no approval. After confirm, show any `unsettled-challenges` list |
| `speckit.eil.correct` (new) | Report a problem in an earlier artefact from any later stage (FR-021). Take the problem, the item and, if the person gives it, the corrected wording. `eil correct propose`, then show the owning stage, the edit (the person's wording, or a draft by the AI, labelled as such) and the impact list, before anything is applied. Ask which stage owns it **only** if `ambiguous`. On agreement, `eil correct open`. **Person's wording**: pass it verbatim as `--wording`, apply it in place with `(decided: CR-###)`, then run `speckit.eil.accept`, where the change is covered and needs only the sign-off (SC-005: report, agreement, sign-off). **AI-drafted wording**: apply it without a `(decided: …)` clause; it is an uncovered change on the `changes` list of `speckit.eil.accept`. Never pass AI text as `--wording` |
| `speckit.eil.amend`, `speckit.eil.review` | Become short aliases that say they are superseded and run `speckit.eil.accept` |
| Drafting commands (`requirements`, `functional`, `technical`, `ai-spec`) | Write each block with a citation when it restates a settled source (spec FR-009). Never hand-write `[ai-draft]`. After drafting, write the classification file and run `eil blocks classify`, then `eil check`, the challenge pass (each challenge with `--severity`), and the one-reply list of kind `inferred` |
| `speckit.eil.approve` | Present the gate with unmet and judgment criteria first and the met structural count on one line (`check` text output). Before asking for the attestation, run the `inferred` list if it is not empty. State open low challenges as outstanding |
| `speckit.eil.challenge` | Present challenges high first. Offer a severity change (`eil challenge severity`) and record who changed it |
| `speckit.eil.complete` | Run the `low-challenges`, `evidence`, `tasks` and `diagram-currency` lists (only for those that are non-empty), each as one reply. List untouched artefacts without a question. For an accepted design/code difference, open a correction with origin `completion` so the design is corrected rather than annotated (FR-045) |
| `speckit.eil.verify` | After drafting evidence rows, write the classification file and run `eil blocks classify --stage verification` and the `inferred` list, as every stage does (FR-012). Record code-review findings as `RF` items under `## Review Findings`, asking the person for each finding's root. For an upstream root, hand off to `speckit.eil.correct` with the RF as the origin |
| `speckit.eil.status`, `speckit.eil.next` | Show `blocked_work`, open corrections, recent changes and the `purpose` of the next action |

### Preset wraps

| Command | Change |
|---|---|
| `speckit.plan`, `speckit.tasks` | Use `enter`'s `rederive` and `blocked`. With an existing document, re-derive **only** the `rederive` items, in place, leaving all other text byte-identical (FR-041); never derive from a `blocked` id. Then `blocks classify` and the `inferred` list |
| `speckit.implement` | `eil enter implement` once for the list; before each task, `eil enter implement --task T###`, and skip it on `work-blocked`, saying why and naming the fix. After ticking tasks, `eil sync`. If the helper reports a `tasks` list, offer it |
| `speckit.clarify` | An answer that affects only some items blocks only them (FR-025); say which tasks remain implementable |

### Behavioural rules added to prompts (Tier 2) and their checks

| Rule | Check |
|---|---|
| Present a list as one list and ask for one reply | Prompt contract test `test_prompt_guidance.py::test_one_reply_lists` (text of each command using a list) + trial probe P-20 |
| Pass the person's reply verbatim; never write a sign-off, reply or correction `--wording` on their behalf | Prompt contract test `::test_reply_verbatim` + trial probe P-21 |
| State the purpose before any request for attention | Prompt contract test `::test_purpose_stated` |
| Never hand-write or remove `[ai-draft]` | Prompt contract test `::test_no_manual_ai_draft`; the helper re-renders the cue anyway (D-33) |
| Re-derive only the listed stale items in place | Prompt contract test `::test_rederive_only_listed`; scenario B-24 checks that non-listed text is byte-identical |
| Draft a correction but apply it only after the person agrees | Prompt contract test `::test_correct_shows_before_apply` + trial probe P-22 |
| When re-editing an item that carries `(decided: CR-###)`, replace or remove the clause (keep it only if the new text is exactly that correction's recorded wording) | Prompt contract test `::test_decided_clause_removed_on_reedit` (text of `correct`, `accept`, the drafting commands and the `plan`/`tasks` wraps); the helper reports a clause left behind as non-blocking `decided-source-invalid` and treats the change as uncovered |
| Pass the AI's one-line change summaries as `--summaries`, labelled AI-drafted | Prompt contract test `::test_summaries_passed`; the helper refuses `summary-missing` anyway |

## Feature 003 amendments (proportionate effort)

Folded in from `specs/003-proportionate-effort/contracts/commands.md`, in the same change as the tests that pin it. Where this section and an earlier one differ, this one wins.

### Changes to every stage command and wrap

- Read a stage with `eil show <stage>` (or `--items`), never by opening the stage document. Never read `eil-record.json`.
- Present a review list as the helper returns it, in its `mode`:
  - **one-at-a-time**: show each entry's full text in chat, ask for that entry's answer, and store it at once with `review answer --entry`. Offer "ok to the rest" (`--rest`).
  - **summary**: show the groups with each entry's summary and why it needs review, ask for one reply, and show full text on request (`review show`).
- Never keep a tally of answers in chat; the helper holds them.
- Never list blocks the helper did not return.
- Every `challenge add` example includes `--severity high|medium|low`, and the text says the severity is required.

### Command-by-command

| Command | Change |
|---|---|
| `speckit.specify` (wrap) | Never reuse `.specify/feature.json` when it names a governed story. Always pass `--feature-dir` to `eil start`. On `unexpected-branch`, show the branch and ask the developer to switch or confirm, then pass their name with `--on-branch`. May propose the small-story profile (below). |
| `speckit.eil.requirements` | Step 1 is the same as the wrap's. May propose the profile. |
| `speckit.eil.abbreviate` | "Do not suggest abbreviation" is replaced by: "you may propose the small-story profile or an abbreviation, naming the signals and labelling it AI assessment; only a person authorises". Adds the `profile set` and `withdraw` steps. |
| `speckit.eil.functional` | Never ask about mechanism; leave it to the Technical stage. Under the profile, do not ask for wireframe exports. Gap scan before the first list. |
| `speckit.eil.technical` | Ask only about choices with an observable effect, scope or trade-off, each with a recommended option. Record every other choice as `Owner: ai-decided` with `Reason:`. When unsure, ask. Name every `ai-decided` DEC in the stage summary. Gap scan before the first list. The rule "a technical decision is the developer's, never yours" is narrowed to observable choices. |
| `speckit.eil.comprehend` | Pass `--by` to `comprehension plan`. Before each question, show the item with `eil show --items`. Ask about behaviour. Judge on meaning, and re-read before hinting. Offer the one-line waiver (`comprehension waive`) when the person asks to stop. Never ask an `own-decision` level. |
| `speckit.eil.ai-spec`, `5-plan`, `6-tasks` | Under the profile, do not present each stage's list. After tasks, present the `derived` list once. |
| `speckit.eil.accept` | On a legacy approval, show the helper's statement and ask for the one reply. Never point to a full re-approval. |
| `speckit.eil.status`, `next` | Report `reviewed` and `done` as the helper gives them. |
| `speckit.eil.challenge` | `--severity` is required in every example. |
| `speckit.eil.approve`, `speckit.eil.complete`, `speckit.eil.accept` | Ask the helper's approval question (`next_action.question`) and nothing more. Accept "ok", "yes", "approved" or any reply as given. Do not ask for a longer statement or show full-sentence examples as required wording. Ask the name once per session. Never supply the reply; silence or "just approve it" is not a reply. |

### Proposing the small-story profile (Tier 2)

The command may propose the profile when it sees signals such as:
- a request that already states behaviour and acceptance in detail;
- few requirements;
- a change confined to one component.

It names the signals it saw and labels the proposal `AI assessment:`. It asks who authorises and why, and runs `profile set` only with the person's own words. When later work shows the story is larger (more than one container touched, new data stored, or more requirements than proposed), it says so and offers `profile withdraw`.

### Tier 2 rules added: contract test and probe

| Rule | Prompt(s) | Contract test (`tests/contract/test_prompt_guidance.py`) | Probe (`docs/trials.md`) |
|---|---|---|---|
| Profile proposed, never authorised by the AI | specify wrap, requirements, abbreviate | `test_profile_proposed_not_authorised` | P-23 |
| Mechanism not asked; `ai-decided` with reason; ask when unsure | functional, technical | `test_mechanism_not_asked` | P-24 |
| Item shown before each comprehension question | comprehend | `test_item_shown_before_question` | P-25 |
| Behaviour not mechanism; re-read before hint | comprehend | `test_behaviour_questions_and_reread` | P-26 |
| Gap scan before the first review list | functional, technical | `test_gap_scan_while_drafting` | P-27 |
| List presented in the helper's mode, no tally, answers stored per entry | every command that presents a list | `test_list_mode_no_tally` | P-28 |
| `show`, never the raw document or record file | every stage command and wrap | `test_show_not_raw` | P-29 |
| Challenge severity required | every command calling `challenge add` | `test_challenge_severity_written` | none (the helper refuses without it) |
| Approval asks the helper's question; a one-word reply is accepted; name asked once | approve, complete, accept | `test_short_approval_accepted` | P-31 |
| Pointer not reused for a governed story; branch confirmation asked of a person | specify wrap, requirements | `test_pointer_not_reused` | P-30 |
