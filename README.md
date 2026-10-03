# Engineer in the Loop

A Spec Kit **preset** plus a companion **extension** (`eil`) that gives a hard-gated, staged
definition workflow: Requirements, Functional Specification, Technical Specification and AI
Specification, then Plan, Tasks, Verification and Completion. Each approvable stage is closed by
one recorded developer confirmation.

> AI challenges. Humans decide. AI executes.

## Install

**You need**: Spec Kit (`specify`) 1.0.2.dev0 or later, Python 3.11 or later, and `git`. The helper uses only the Python standard library, so there is nothing to `pip install`.

Install the **extension first, then the preset**. The preset's commands check that the extension is present and refuse to run without it, because a story that skipped the helper would skip every gate.

```bash
# from a checkout of this repository, stage the files that ship
python3 tools/stage.py /tmp/eil-stage

# then, in your Spec Kit project
specify extension add --dev /tmp/eil-stage/extension
specify preset add --dev /tmp/eil-stage/preset
```

Stage first: `specify preset add --dev .` copies the whole directory it is given, so running it from the repository root would put this repository's `.venv`, `specs/` and `tests/` into your project. Released archives (`--from <archive>`) contain only the shipped files.

Installing changes nothing you wrote. It adds files under `.specify/` and the agent's command directory, and it recomposes the agent's generated skill for each command the preset replaces or wraps (Spec Kit does that in place, and regenerates it when you remove the preset).

## Your first story

1. **Start it.** Run `/speckit-specify "Detect duplicate customers on import"`. With the preset installed this begins a *story* at the Requirements stage: it creates `s00-README.md` (a generated overview) and `s01-requirements.md`, and never a `spec.md`.
2. **Draft the Requirements.** `/speckit-eil-requirements` drafts each section from what you said, draws the system context diagram, and asks you about anything it would have had to guess. Anything the AI wrote that you have not yet reviewed is marked `[ai-draft]` when you read the stage with `eil show` (the tag is never written into the document itself).
3. **See the gate.** `python3 .specify/extensions/eil/scripts/python/eil check --stage requirements` (or the command above) lists each of the 14 criteria as met, not met or overridden, with the reason.
4. **Decide.** You resolve or accept each material open question, review the AI's text in one list, and answer the AI's challenges.
5. **Approve.** `/speckit-eil-approve` shows you the gate and asks the helper's question, for example "Approve the Requirements as the problem we intend to solve?". "ok" is a complete answer: it is recorded verbatim with that question, your name, the time and a fingerprint of the document. Your name is asked once per session. One confirmation from one configured person is enough.

Only then can the next stage begin: `stage-init functional` is refused while Requirements is unapproved, and edits to an approved document after the fact mean it needs a new confirmation.

*AI challenges. Humans decide. AI executes.*

## Configure

Installing the extension scaffolds `.specify/extensions/eil/eil-config.yml` from a template. Edit it to say who may confirm what:

```yaml
default_developer: null          # else the story's owner, else `git config user.name`
approvers:
  requirements: []               # [] means "the story's developer"
  functional: []
  technical: [Ada Dev]           # or one or more names
  completion: []
abbreviation_authorisers: []     # who may abbreviate a stage; [] means the story's developer
```

- **One listed person's confirmation is enough** (there is no two-person rule here; require two approvers on the pull request in your repository settings if you want one).
- The same list decides who may **override** a criterion, who may **answer a challenge**, and who may **amend** an approval for that stage.
- A machine-local `local-config.yml` in the same directory overrides the shared file key by key. Keep it out of version control.
- A configuration file that cannot be read is an error, never a silent default.
- `abbreviate` records that a small story shortened a stage, who authorised it and why. A stage is abbreviated, never skipped, and it still passes its gate.

These checks are **attestation-level**. The helper records a name, a time, a document fingerprint and the person's own words, and refuses an approval by anyone not on the list or by a name that is the AI. It cannot prove who typed the name, and a person who edits the files directly can bypass any gate. What it provides is that such an edit is *detectable*: any change to an approved document changes its fingerprint, the approval stops covering it, and the record is in your version control history for the pull request review.

## Use

The eight stages, and the command for each. Every stage starts only when the one before it is done.

| Stage | Document | Command (also `/speckit-eil-N-…`) | Closed by |
|---|---|---|---|
| 1 Requirements | `s01-requirements.md` | `/speckit-eil-1-requirements` (or `/speckit-specify`) | your approval |
| 2 Functional | `s02-functional-spec.md` | `/speckit-eil-2-functional` | the comprehension check, then your approval |
| 3 Technical | `s03-technical-spec.md` | `/speckit-eil-3-technical` | the comprehension check, then your approval |
| 4 AI Specification | `s04-ai-spec.md` (`spec.md`) | `/speckit-eil-4-ai-spec` | a passing source-traceability check |
| 5 Plan | `s05-plan.md` (`plan.md`) | `/speckit-eil-5-plan` | its gate |
| 6 Tasks | `s06-tasks.md` (`tasks.md`) | `/speckit-eil-6-tasks`, then `/speckit-implement` | its gate |
| 7 Verification | `s07-verification.md` | `/speckit-eil-7-verify` | evidence for every item |
| 8 Completion | `s08-completion.md` | `/speckit-eil-8-complete` | your approval |

The number in each command is the number in the document's file name, and `/speckit-eil-0-status` shows where you are. The original names (`/speckit-eil-functional`, `/speckit-plan` and so on) keep working.

**Not sure what comes next?** Run `/speckit-eil-next`. It reads the story and does the one next step only if that step is drafting or checking. It stops, and says what it needs, at every point where a person decides: approvals, open challenges, comprehension checks, overrides and accepted risks. It never approves anything, and it never runs a second step.

`s00-README.md` is a generated overview: the current stage, who approved what and when, what is outstanding. Read it first; never edit it.

**Around the stages**

- `/speckit-eil-challenge`: the AI raises specific gaps; **you** answer each (accepted, rejected with a reason, or deferred with the risk accepted). An open challenge blocks approval. A rejected point is not raised again.
- `/speckit-eil-comprehend`: before you approve Functional or Technical, five questions about the document, one at a time, in the AI's own words. Passing is not required; skipping or asking for an answer is recorded and counted, and no question or answer is ever written down.
- `/speckit-eil-artifact`: you export a wireframe from Figma (PNG, SVG, PDF or JPG) and the helper records the file, its SHA-256 and the link to the exact frame. The AI never draws or edits one.
- `/speckit-clarify` then `/speckit-eil-resolve`: an answer collected during clarification is written into the AI Specification as *pending* and must be carried to the earliest stage it affects. Plan and Tasks are refused while any is pending.
- `/speckit-eil-override`: a configured person waives one criterion, naming the reason. It stays visible in every later stage.
- `/speckit-eil-accept`: brings a changed, previously approved stage back. It lists what changed and which changes a recorded human decision already covers; if all are covered, one sign-off carries the approval forward, otherwise you answer the uncovered changes in one reply and confirm. The approval records how it was reached (`first`, `carried-forward` or `reviewed`) and what it rests on.
- `/speckit-eil-abbreviate`, `/speckit-eil-trace`, `/speckit-eil-status`, `/speckit-analyze` (which also checks the whole traceability chain) and `/speckit-checklist`.

**What you are asked, and why.** Every request for your attention states its purpose: *awareness*, *understanding*, *decision*, *validation* or *approval*. You are not asked to reconfirm something already established (an approval, an answer, a recorded decision) unless it has materially changed, and what the helper can work out itself (coverage, traceability, whether content changed, whether a cited decision exists) it works out rather than asking you.

- **One reply per list.** Anything that needs your review comes as a single list: what each entry is, why it is there, and the limits of the check. Reply once, in your own words: "ok to all", "ok except REQ-002" or a question about one entry. Your reply is recorded word for word; the AI never supplies or completes it. `/speckit-eil-accept` does this for changed stages, and the same list shape is used for AI-inferred content, tasks that may need rework, evidence rows, low-severity challenges and content of unknown currency.
- **Only what depends on a change is stale.** Changing one decision marks the blocks, tasks and evidence that trace to it, not the whole package. `enter` refuses only the work that depends on the changed item (`work-blocked`); other tasks continue.
- **Accept and correct.** `/speckit-eil-accept` brings an edited stage back; if every change is covered by a decision you already recorded, one "ok" carries the approval forward, marked as carried forward and naming what it rests on. `/speckit-eil-correct` handles a mistake found later, in implementation or verification: it proposes the owning stage, shows the corrected wording before anything is applied, and records your wording verbatim.
- **Lists sized to you.** A list of up to 8 entries (`review.one_at_a_time_max`) is walked one entry at a time, each answer stored by the helper as you give it, with "ok to the rest" to finish early; a longer one is a grouped summary answered in one reply, with full text on request. A compacted or restarted conversation resumes where you were. Each Actors, Dependencies, Not applicable, Inputs and Outputs section is one entry.
- **Behaviour, not mechanism.** The Technical stage asks you only about choices you would observe (behaviour, scope, a trade-off), each with a recommended option. Every other choice is recorded as `Owner: ai-decided` with its reason, listed in its own group on the review list for your one reply, and named by the approval.
- **The comprehension check knows what you decided.** Your own recorded decisions are not asked (recorded `own-decision`); each question shows its item first; one waiver with a reason ends the check (`comprehension waive`).
- **The small-story profile.** For a small, well-specified story the AI may propose it, labelled as its assessment; you authorise it once with a reason (`eil profile set small`). It drops wireframe exports, reviews the AI Specification, plan and tasks as one list before implementation, and cuts comprehension to two levels. Every approval still applies, and it is shown wherever it changes a gate.
- **Records out of the documents.** Hashes, classes, review records and assessment details live in one record file per story, `eil-record.json`; each document keeps one readable line per record ("Approved by Ada on ... (first approval): ..."). Read a stage with `eil show <stage>`; nobody needs to open the record file.
- **The right story.** `eil start` always moves the active-story pointer and says so; a write that cannot tell which story it is for is refused before anything is touched (`ambiguous-story`), and every result names its story. A story started on another story's branch waits for your one-line confirmation.
- **Low-severity challenges do not block.** They are listed as outstanding at approval and in the overview. Anyone can raise a challenge's severity; only a configured confirmer for the stage can lower it, and both are recorded with the person's name.

What the helper does not establish, stated plainly:

- **Restated content (FR-014).** A block that cites a settled source is checked by hash. The check cannot prove that two wordings mean the same thing; you can mark any block inferred.
- **Evidence (FR-035).** An evidence row naming a test is confirmed only by finding that test in the named file. The helper does not run it, so a row confirmed this way shows the test exists, not that it passes.
- **Your reply (D-36).** A reply is mapped to the flags you meant, and the helper refuses only obvious mismatches (for example "ok" with an exception named). It cannot tell whether you read the list.
- **Correction wording (D-38).** The helper records the wording as given and cannot tell who wrote it.
- **The record file (R-21, R-25).** `eil-record.json` is plain project text, like the regions it replaced, and not part of any fingerprint. Editing it by hand can make a block look reviewed; deleting it, or breaking it, makes every approval it held unverifiable (never valid). Either is detectable in version control and is an attestation-level limit, like the gates.
- **The review cue is not in the documents (R-26).** A raw stage document no longer shows which paragraphs await review. The overview counts them per stage, and `eil show` marks them.
- **Summaries and "ok to the rest" (R-24).** A summary-mode answer accepts entries you may have read only as summaries, and "ok to the rest" accepts entries not shown in full. The record says which (`mode`, `unseen`); the helper cannot tell what you read.
- **`ai-decided` (R-23).** Whether a choice changes what a user observes is the AI's labelled judgement. Each such decision is put to you on the review list; it asks when unsure, but it can be wrong.
- **Re-signed without comparison (D-56).** An approval older than section-level records, on a changed document, is re-signed by one reply to a statement that the tool cannot compare it; the approval says so wherever it is shown.

**Diagrams** are Mermaid text inside the stage document (C4 context, container and component; sequence; ER), so a change to a diagram is a change to the document. The helper reads them line by line and checks them against each other (an external system must have the same name in the context and container views; a technical sequence's participants must be C4 elements; an ER diagram names its data store). **It never renders them**, and Mermaid's C4 support is experimental, so a construct outside the accepted subset is reported, not skipped. A diagram from another tool can be attached as an image and is then not structurally checked.

**The helper** is `python3 .specify/extensions/eil/scripts/python/eil <command> [--json]`. You rarely call it yourself, but `status`, `check --stage S`, `check --chain`, `trace --report` and `artifact list` are safe to run at any time and change nothing but the generated assessment and overview.

**Released archives.** `python3 tools/stage.py DIR --archives` writes `eil-extension-<version>.zip` and `engineer-in-the-loop-preset-<version>.zip`. Pushing a tag such as `v0.1.0` builds them in GitHub Actions and attaches both to a release (`.github/workflows/release.yml`); the build refuses if `preset.yml` and `extension.yml` do not carry the tag's version. Install them with `specify extension add eil --from <url>` (it asks you to confirm the source) and `specify preset add --from <url>`, extension first.

## Remove

Remove the **preset first, then the extension**:

```bash
specify preset remove engineer-in-the-loop
specify extension remove eil --force
```

What that does, and does not do:

- The wrapped commands (`specify`, `clarify`, `plan`, `tasks`, `analyze`, `checklist`, `implement`) resolve to Spec Kit's own again. Spec Kit regenerates each agent skill from the core template, so the skill is equivalent to the original (not necessarily byte-identical).
- The extension's commands, its helper and its four hooks are removed. No `eil` hook is left in `.specify/extensions.yml`.
- **Your stories stay.** Every stage document, `assets/` file, and the `spec.md`, `plan.md` and `tasks.md` aliases remain in the feature directories as ordinary readable files. A mirror (where your platform could not make a link) stays as a plain file: it is a copy of the real document, so from then on edit the `s0N` file and treat the copy as stale.
- A feature that was never governed (an ordinary `specs/NNN/spec.md` from before you installed) is never touched, at install or at removal, and is never gated.
- Removing does not delete approvals: they are in the stage documents and the story's `eil-record.json`, both left in place.

## Trials

The automated suite covers everything that code decides (over 2,000 tests: unit, contract against a real installed Spec Kit, and scenarios that drive the installed helper). It cannot show that an AI agent *follows* the prompts, or measure how long real stories take. Those are human trials, with protocols and blank recording sheets in [`docs/trials.md`](docs/trials.md), and **none has been run yet**. Until they are, treat the prompt behaviour as designed and unproven.

Known limits, stated plainly:

- The gates are **attestation-level, not tamper-proof**. They make a bypass detectable; they do not prevent one.
- No Mermaid diagram has been rendered, and no real Figma export has been registered.
- Whether `/speckit-checklist` stays meaningful over the AI Specification (OQ-001) is undecided.
- Only Linux has been tested.
- Spec Kit recomposes the agent skill for each wrapped command in place, so installing changes those generated files (removal restores them, equivalent in content but not byte-identical).
