# Trials

Everything the automated suite can decide is decided by code, and it passes. What follows cannot be:
it depends on a person, or on whether an AI agent follows a prompt. Each protocol says what to do, what
to record and what counts as a pass. **Nothing here has been run yet**, except C-06 (below); the sheets
are blank on purpose, and a release should not claim more than the sheets show.

The pass rule for every probe: run each probe **once per command**; any failure is a **prompt defect**,
not bad luck; fix the prompt and re-run *the failed probe* until it is clean. A release needs **one clean
run of every probe** (constitution Principle I, tier 2). `tests/contract/test_prompt_guidance.py` proves
each rule is *written* in the prompt; these probes measure whether the agent *follows* it.

## Results so far

| Item | Date | Result |
|---|---|---|
| C-06 install to first story | 2026-09-25 | Scripted from the README on Linux with Spec Kit 1.0.2.dev0: stage, `extension add`, `preset add`, `eil start` took **1.1 s** of machine time, ending with `s00-README.md` and `s01-requirements.md` and a Requirements gate reporting each of its 14 criteria. The 10-minute budget (SC-001) is therefore all reading time; a first-time reader has not yet been timed. |
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
| developer-choice-recorded | `/speckit-eil-technical` | Choose against the AI's proposal. | Your choice is the recorded decision; owner is you. |
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
