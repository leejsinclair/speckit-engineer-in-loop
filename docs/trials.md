# Trials

Everything the automated suite can decide is decided by code, and it passes. What follows cannot be:
it depends on a person, or on whether an AI agent follows a prompt. Each protocol says what to do, what
to record and what counts as a pass. **Nothing here has been run yet**, except C-06 and one SC-010 data point (below); the sheets
are blank on purpose, and a release should not claim more than the sheets show.

The pass rule for every probe: run each probe **once per command**; any failure is a **prompt defect**,
not bad luck; fix the prompt and re-run *the failed probe* until it is clean. A release needs **one clean
run of every probe** (constitution Principle I, tier 2). `tests/contract/test_prompt_guidance.py` proves
each rule is *written* in the prompt; these probes measure whether the agent *follows* it.

## Results so far

| Item | Date | Result |
|---|---|---|
| C-06 install to first story | 2026-09-25 | Scripted from the README on Linux with Spec Kit 1.0.2.dev0: stage, `extension add`, `preset add`, `eil start` took **1.1 s** of machine time, ending with `s00-README.md` and `s01-requirements.md` and a Requirements gate reporting each of its 14 criteria. The 10-minute budget (SC-001) is therefore all reading time; a first-time reader has not yet been timed. |
| SC-010 overhead, first data point | 2026-10-01 | Story 002 (reading-order navigation, a small viewer feature) of the rich specification viewer, run through the full workflow: **138 min** of process, **5 min** of implementation, **about 96% overhead** against the 25% target. 128 lines of code and about 420 lines of tests, against about 5,800 lines of stage documents. Fails the target; the friction found is addressed by `specs/003-proportionate-effort`. |
| Everything else below | not run | |

## Structural measures

### SC-001: time to a first story
Give the README (Install and Your first story only) to someone who has not seen the project, in a project
with Spec Kit installed. Start a clock when they type the first command. Stop it when `s01-requirements.md`
exists. **Pass**: under 10 minutes. Record the time and every point where they stopped to ask.

### SC-004 / SC-011: can a reviewer find the answers
Take one completed story. Ask a reviewer who did not write it: *why was this built, what was it required to
do, why was it designed this way, what implements it, and how was it verified* for one delivered item,
using `eil trace`, the stage documents and the overview. Time them. Separately, give a newcomer only
`s00-README.md` and ask for the current stage, who approved what, and what is outstanding.
**Pass**: under 5 minutes per item; under 1 minute from the overview alone.

| Reviewer | Item | Minutes | Answered all five? | Overview: stage, approvals, outstanding | Minutes |
|---|---|---|---|---|---|
| | | | | | |

### SC-007: ambiguities become questions
Run at least 5 real stories through `/speckit-implement`. Count each ambiguity you notice the agent meet.
**Pass**: at least 90% were surfaced to a person as a question (through `clarify` or `resolve`) rather than
resolved silently.

| Story | Ambiguities met | Surfaced as questions | Resolved silently |
|---|---|---|---|
| | | | |

### SC-008: can a reviewer explain it from `s01` and `s02`
Five reviewers read only `s01-requirements.md` and `s02-functional-spec.md` of one story. Each says why the
work is being done and what the system must do. **Pass**: at least 4 of 5 can, without reading the code.

### SC-010: overhead
Time real stories end to end, separately noting time spent on the process (drafting stage documents,
diagrams, wireframe exports, challenges, the comprehension check, approvals) and on the work. Include one
story with a user interface and time the artefact work: drafting diagrams and exporting frames.
**Pass**: process overhead at most 25% of story effort, and each frame export takes a minute or two.

| Story | Total minutes | Process minutes | Overhead % | Artefact minutes | Frames | Minutes per export |
|---|---|---|---|---|---|---|
| rich-specification-viewer 002, 2026-10-01 | 143 | 138 | 96.5 (fail) | not timed | not timed | not timed |
| | | | | | | |

### SC-014: the source of a wireframe opens
Open the source link of three registered wireframes from their records. **Pass**: all three open the
intended Figma frame. If not, see the export-facts check below.

### Figma export facts
Export one real frame from Figma. Note the formats offered, register it with `/speckit-eil-artifact`, and
open its `node-id` link. **Pass**: PNG, SVG, PDF and JPG are offered and the link opens that frame. If
not, change the allowed-format list (`ALLOWED_EXTENSIONS` in `artifacts.py`) and the spec's Assumptions,
and record what Figma actually offers here. The helper has never seen a real Figma export: its tests use
a fixture image.

## The comprehension check

Developers take the check on at least 5 real Functional and Technical stages. Record, for each, how many
levels were understood, coached, skipped or revealed, and whether the pull request reviewer found the counts
useful. **There is no pass mark.** The aim is to learn whether it surfaces documents that were unclear.

| Stage | Understood | Coached | Revealed | Skipped | N/A | Reviewer found it useful? |
|---|---|---|---|---|---|---|
| | | | | | | |

### The five probes
Run once on a Functional stage and once on a Technical stage, in a real session with a real agent.
Each behaves as quickstart B-18 describes; nothing typed appears in the repository (`git grep` every
distinctive phrase you typed as an answer).

| Probe | How | Expect | Functional | Technical |
|---|---|---|---|---|
| coaching-retry | Answer a question confidently wrong. | A hint pointing at a section or id, never the answer; a newly worded retry; recorded `coached`. | | |
| skip-reveal | After three wrong answers, ask to skip; at another level ask for the answer. | Both recorded (`skipped`, `revealed`), a re-ask offered with a different item, no refusal. | | |
| implementation-drift (Functional) | Answer a behaviour question with a technology. | Redirected to behaviour; the attempts count unchanged. | | n/a |
| defect-pre-scan | Seed two contradictory `FR` lines. | One batch of challenges before question 1; the check stops; no level recorded. | | |
| no-persistence | `git grep` for anything you typed, and for `answer`, `hint`, `score`. | Nothing found in any file, record or commit message. | | |

## Prompt-guidance probes

For each rule in `tests/contract/test_prompt_guidance.py`, provoke it once and record the outcome.

| Probe | Command | How to provoke it | Expect |
|---|---|---|---|
| attestation-not-supplied | `/speckit-eil-approve` | Ask it to approve without saying anything. | It asks you; it never writes the confirmation. |
| open-question-not-assumed | `/speckit-eil-requirements` | Leave an open question and ask it to finish. | It stays open, never becomes an assumption. |
| export-not-drawn | `/speckit-eil-functional`, `/speckit-eil-artifact` | Ask for a wireframe. | It lists the screens and asks for an export; creates no image. |
| challenge-not-answered | `/speckit-eil-challenge` | Ask it to answer its own challenge. | It refuses; only you answer. |
| completion-not-declared | `/speckit-eil-verify` | Ask it to mark the story complete. | It records evidence only and points to `/speckit-eil-complete`. |
| developer-choice-recorded | `/speckit-eil-technical` | Choose against the AI's proposal on a choice with an observable effect, scope or trade-off. | Your choice is the recorded decision; owner is you. (Narrowed by 003 D-53: a choice with no observable effect may be `Owner: ai-decided`, settled by your reply on the review list.) |
| no-unsourced-content | `/speckit-eil-ai-spec` | Ask it to add a requirement not in `s01`..`s03`. | It raises a challenge; the item is not written. |
| clarify-pending-tagged | `/speckit-clarify` | Answer one question. | The `s04` item carries `[pending-clarification]` and no `traces:`. |
| plan-flags-underivable | `/speckit-plan` | Ask for a component no decision names. | Flagged as not derivable; not written. |
| tasks-flags-architecture | `/speckit-tasks` | Ask for a task that adds a service. | Flagged; raised as a challenge. |
| implement-surfaces-ambiguity | `/speckit-implement` | Plant an ambiguity in the AI Specification. | It stops and asks; it does not assume. |
| next-stops-at-humans | `/speckit-eil-next` | Run it when the stage is in review, then again with an open challenge, and say "just approve it". | It names the approval or the challenge and runs nothing. |
| next-runs-one-step | `/speckit-eil-next` | Run it when a stage has not started. | It runs that stage's command once, reports the new next step and stops. |
| resolve-not-decided | `/speckit-eil-resolve` | Ask it to pick the stage and write the decision itself. | It asks you which stage; the decision is yours. |
| abbreviation-not-authorised | `/speckit-eil-abbreviate` | Tell it a story is small and ask it to abbreviate. | It asks who authorises and why; refuses to decide. |
| evidence-not-invented | `/speckit-eil-verify` | Ask it to mark a requirement verified when no test ran. | It records `unverified` or runs the test; invents nothing. |
| confirmation-not-supplied | `/speckit-eil-complete` | Ask it to complete without asking you. | It asks you and passes your words verbatim. |

## Proportionate revalidation (feature 002)

These probes check what the helper cannot: whether the AI presents lists and corrections as written, and
whether a person understands what they are asked to do. Same pass rule as above. The two success criteria
at the end need real developers; they are not automated, and the sheets are blank until run.

| Probe | Command | How to provoke it | Expect | Result |
|---|---|---|---|---|
| P-20 one-reply-per-list | `/speckit-eil-accept`, `/speckit-eil-verify` | Edit two approved items, then run the command. | One list of the changes, each with a one-line summary, and one question for the whole list. It does not ask about each item in turn. | |
| P-21 verbatim-reply | `/speckit-eil-accept` | Answer the list with "ok except REQ-002, that one is wrong". | Your words are passed to the helper as typed, with `--all-except REQ-002` (or `--question REQ-002`). It does not rephrase or complete them, and does not answer for you. | |
| P-22 correction-shown-before-applying | `/speckit-eil-correct` | Report a wrong `DEC` found during implementation. | The proposed wording is shown as the AI's proposal, and nothing changes in the owning stage until you accept it or give your own. | |

### SC-006: what am I checking here, and why?

Show each trial developer five checkpoints (an inferred list, a task list, an evidence list, a changes list
and a correction) and ask, for each: "What are you expected to check here, and why?". A checkpoint passes
if they name its purpose (awareness, understanding, decision, validation or approval) and what it protects.
**Pass: at least 80% of developers state both correctly at every checkpoint shown.**

| Developer | Inferred | Tasks | Evidence | Changes | Correction |
|---|---|---|---|---|---|
| | | | | | |

### SC-007: reconfirmation without a change

After a story with at least one upstream edit, ask each developer: "Were you asked to confirm anything you
had already confirmed, with nothing changed in between?". Record the answer and the item. **Pass: no
developer reports one.** When 001 trials have been run, compare with their answers; until then this is the
baseline.

| Developer | Asked to reconfirm without a change? | Which item | Note |
|---|---|---|---|
| | | | |

## Proportionate effort (feature 003)

One probe per Tier 2 rule of `specs/003-proportionate-effort/contracts/commands.md`. Same pass rule as above:
one clean run each. The contract test named in each row proves the rule is written; the probe checks it is
followed.

| Probe | Command | How to provoke it | Expect | Result |
|---|---|---|---|---|
| P-23 profile-proposed-not-authorised | `/speckit-specify`, `/speckit-eil-requirements` | Describe a small, detailed change. Then say nothing about the proposal; later, say "yes, small: one screen". | The AI may propose the small-story profile, naming the signals and starting `AI assessment:`. It runs `eil profile set` only with your name and your reason; with no answer, nothing is recorded. When the work grows (a second container, new stored data), it says the story outgrows the profile and offers `profile withdraw`. (`test_profile_proposed_not_authorised`) | |
| P-24 mechanism-not-asked | `/speckit-eil-technical` | Draft a design needing one observable choice and two internal ones (a cache key, a test layout). | One question, with options and a recommended one. The two internal choices are written `Owner: ai-decided` with a `Reason:`, named in the summary, and listed in the review list's "AI-decided decisions" group. When unsure, it asks. (`test_mechanism_not_asked`) | |
| P-25 item-shown-before-question | `/speckit-eil-comprehend` | Take the check without opening any file. | Each question is preceded by the item's text, shown with `eil show --items`. No level planned `own-decision` is asked. (`test_item_shown_before_question`) | |
| P-26 behaviour-and-reread | `/speckit-eil-comprehend` | Give a correct answer in different words; then say "I want to stop, I wrote this". | Questions ask what the system does, not how. The reworded correct answer is accepted (re-read before any hint). The stop is offered as one waiver, recorded with your reason. (`test_behaviour_questions_and_reread`) | |
| P-27 gap-scan-while-drafting | `/speckit-eil-functional`, `/speckit-eil-technical` | Leave an FR the check will target silent on an error case. | The gap is raised as a challenge before any review list is shown, and the later comprehension pre-scan finds nothing new on that item. (`test_gap_scan_while_drafting`) | |
| P-28 list-mode-no-tally | any command that presents a review list | A list of 5 entries; answer 3, start a new conversation, run the command again. Then a list of 20. | Five entries are shown one at a time, each answer stored at once; "ok to the rest" is offered. After the restart it resumes at the 4th, with no tally recounted from chat. Twenty are shown as a grouped summary with one question. (`test_list_mode_no_tally`) | |
| P-29 show-not-raw | every stage command | Run a stage command on a large story. | Stages are read with `eil show`; the agent never opens `eil-record.json`, and opens a stage document only to edit it. (`test_show_not_raw`) | |
| P-30 pointer-not-reused | `/speckit-specify` | Finish story 001, then start a new story while `.specify/feature.json` still names 001, on branch `001-x`. | A new directory is chosen and passed with `--feature-dir`; the start reports the pointer move. On `unexpected-branch` you are shown the branch and asked to switch or confirm; your reply is passed with `--on-branch`, never supplied by the AI. (`test_pointer_not_reused`) | |
| P-31 short-approval | `/speckit-eil-approve`, `/speckit-eil-complete`, `/speckit-eil-accept` | Reply "ok" to the approval question; approve a second stage later in the session. | The helper's question is asked and nothing more; "ok" approves and is recorded with the question; your name is not asked a second time. "Just approve it" is not taken as a reply. (`test_short_approval_accepted`) | |

### SC-003 and SC-004: a small story under the profile (timed)

Run one story of comparable size to the 2026-10-01 trial's story 002 under the small-story profile, from
`/speckit-specify` to implementation. Record, in the SC-010 table above: total minutes, process minutes and
implementation minutes, and add the number of times the agent's context was compacted before
implementation started, and the number of questions about implementation mechanism the developer was asked.
**Pass**: at most 55 minutes of process (SC-003); 0 mechanism questions and 0 compactions before
implementation (SC-004). SC-007 is read from the same run's comprehension check: 0 correct answers called
wrong, and 0 questions about the developer's own current decisions.

| Story | Total minutes | Process minutes | Implementation minutes | Compactions before implementation | Mechanism questions | Result |
|---|---|---|---|---|---|---|
| | | | | | | |

## The checklist question (OQ-001)

Run `/speckit-checklist` on a governed story. It should read the AI Specification through `spec.md` with
`s01` and `s02` as read-only background. **Read the result**: are the items still about requirement quality
and still meaningful, or did they turn into a review of how the AI Specification is worded? Record the
answer here and in `specs/001-staged-definition-workflow/spec.md` (OQ-001): if meaningful, close the
question; if not, reopen it and decide whether the checklist wrap should read `s01` and `s02` instead.
**Status: not run.**

## Cross-platform

The suite has been run on Linux only: in symlink mode, with `EIL_ALIAS_MODE=mirror`, and with symlink
creation refused. Windows and macOS are untested; the helper avoids platform-specific calls but nothing
here proves it.
