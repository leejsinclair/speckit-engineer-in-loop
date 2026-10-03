---
description: Implement the tasks. Ambiguities are surfaced for a human decision, never assumed.
strategy: wrap
---

## Guard (engineer-in-the-loop)

If `.specify/extensions/eil/scripts/python/eil` does not exist, STOP. Tell the user to run `specify extension add eil` and then `specify preset add engineer-in-the-loop`, and do nothing else: continuing without the helper would let a story bypass its gates.

## Reading a stage

Read a stage with `python3 .specify/extensions/eil/scripts/python/eil show <stage> --json` (add `--items <ids>` for just those items, or `--section "<heading>"` for one section), never by opening the whole document: `show` gives the content as a person reads it, with `[ai-draft]` after each block that still needs review and one readable line in place of each record. Open a stage document only to edit the part you are changing. **Never read `eil-record.json`**: it is the helper's record file, and `eil status` and `eil show` report what is in it.

## Before the core command

Run `python3 .specify/extensions/eil/scripts/python/eil enter implement --json`.

- **Exit 3**: this feature is not a governed story. Skip everything in this wrapper and run the core command unchanged.
- **Any other non-zero exit**: STOP and show the helper's `refusals` (code, message, fix): a missing plan or task list, an artefact or diagram check that fails, a stage never approved, every open task blocked (`work-blocked`), or an alias the helper could not repair. Do not work around a refusal.
- **Exit 0**: read `blocked[]` (`{id, because[], fix}`) and `rederive[]`. Work on the tasks that are not listed; a blocked task is skipped, not the whole run. Say which tasks you are skipping and why, using each row's `because` and `fix`.

The files `spec.md`, `plan.md` and `tasks.md` are links (or read-only mirrors) to `s04`, `s05` and `s06`. Read them as usual; when the core command marks a task done, edit `tasks.md` only, and never replace any of the three with a separate file.

{CORE_TEMPLATE}

## While implementing (governed stories only)

- **Before each task**, run `python3 .specify/extensions/eil/scripts/python/eil enter implement --task T### --json`. If it is refused with `work-blocked`, skip that task, tell the human which item blocks it and the `fix` shown, and go on to the next task. Never implement a task that is blocked or listed in `rederive`; those need their plan or task line derived again first.
- **After ticking a task**, run `python3 .specify/extensions/eil/scripts/python/eil sync --json`. It records the versions of the sources the task was completed against; do not write that record yourself.
- When completed tasks are affected by a later change, offer the human the one-reply list: `eil review list --stage tasks --kind tasks --json`. Give your view of each task in a views file, labelled `AI assessment:` by the helper. The human answers; you never record the answer for them.

- **Surface ambiguities; never assume.** If the AI Specification, the plan or a task is silent, unclear or contradictory on something that changes what you would build, **stop that piece of work**, put the question to the human, and record the answer through `/speckit-clarify` (or `/speckit-eil-resolve` when it belongs in an earlier stage). Do not proceed on an assumption nobody recorded (FR-041).
- Implement only what the approved design contains. If a task seems to need architecture the design does not contain, stop and raise it as a challenge.
- After each change to code that carries a task, note the commit or pull request against the task's item with a `(code: <sha>)` or `(code: PR#n)` clause, so the chain from requirement to code can be traced.
- Finish with `python3 .specify/extensions/eil/scripts/python/eil sync --json`.
