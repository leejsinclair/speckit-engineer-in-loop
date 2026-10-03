---
description: Generate a checklist for the story. The core checklist over spec.md, with the Requirements and Functional Specification read as background.
strategy: wrap
---

## Guard (engineer-in-the-loop)

If `.specify/extensions/eil/scripts/python/eil` does not exist, STOP. Tell the user to run `specify extension add eil` and then `specify preset add engineer-in-the-loop`, and do nothing else: continuing without the helper would let a story bypass its gates.

## Reading a stage

Read a stage with `python3 .specify/extensions/eil/scripts/python/eil show <stage> --json` (add `--items <ids>` for just those items, or `--section "<heading>"` for one section), never by opening the whole document: `show` gives the content as a person reads it, with `[ai-draft]` after each block that still needs review and one readable line in place of each record. Open a stage document only to edit the part you are changing. **Never read `eil-record.json`**: it is the helper's record file, and `eil status` and `eil show` report what is in it.

## Before the core command

Run `python3 .specify/extensions/eil/scripts/python/eil enter checklist --json`.

- **Exit 3**: this feature is not a governed story. Skip everything in this wrapper and run the core command unchanged.
- **Any other non-zero exit**: STOP and show the helper's `refusals` (code, message, fix).

In a governed story `spec.md` is a link (or read-only mirror) to `s04-ai-spec.md`, the AI Specification. A checklist over it alone would test how well the AI Specification is written, which is not what a requirements-quality checklist is for. So **also read `s01-requirements.md` and `s02-functional-spec.md`, when they exist, as read-only context**: the requirements and behaviour that the AI Specification is derived from are what the checklist items should be about. Never edit `s01`, `s02` or `spec.md` from here, and never write a checklist file that replaces one of them.

{CORE_TEMPLATE}

## After the core command (governed stories only)

- Say which documents the checklist was generated from, and that `s01` and `s02` were read as background only.
- Finish with `python3 .specify/extensions/eil/scripts/python/eil sync --json`.
