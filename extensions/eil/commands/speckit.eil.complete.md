---
description: Close the story: summarise it, state that each approved diagram is current, and record the human's confirmation that the evidence was reviewed.
argument-hint: "Anything the developer wants recorded, such as deployment status"
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## Guard (engineer-in-the-loop)

If `.specify/extensions/eil/scripts/python/eil` does not exist, STOP. Tell the user to run `specify extension add eil` and then `specify preset add engineer-in-the-loop`, and do nothing else: continuing without the helper would let a story bypass its gates.

## What this stage is for

Completion answers **are we satisfied?** It is a person's decision: one recorded confirmation, made after reading the evidence. It is refused while the Verification document is missing, or while a requirement or an approved artefact is unverified without an exception, unless a configured confirmer records a named override. Every gate below is decided by the `eil` helper, not by you.

Every call below is `python3 .specify/extensions/eil/scripts/python/eil <subcommand> --json`. **Stop on any non-zero exit** and show the helper's `refusals` (code, message, fix). Exit 3 means there is no governed story.

## Steps

1. **Synchronise**: run `eil sync --json`.
2. **Start the stage**: run `eil stage-init completion --json`. It is refused until the Verification document exists (`verification-missing`) and Requirements, Functional and Technical are approved. If `s08-completion.md` already exists, continue from it.
3. **Fill the record from what the other stages hold**, and nothing new: completion status, implementation summary, requirements satisfied, outstanding issues (including open tasks and accepted risks), accepted deviations, relevant technical decisions, verification summary, deployment status, and documentation and support implications. Ask the human for anything you cannot see, such as the deployment status. Tag every passage you write with `[ai-draft]`.
4. **Diagram Currency**: for **every approved artefact** (`eil artifact list --json`) write one line under Diagram Currency: `- ART-004: current`, or, where what was built differs from the diagram, `- ART-007: deviation, accepted by <person>, because <reason>`, and list the deviation under Accepted Deviations too. **Ask the human** whether each diagram is still current; do not assume it, and never write yourself as the person accepting a deviation.
5. **Check**: run `eil check --stage completion --json` and show which criteria are met and which are not. If the gate is not met, say why and stop: do not ask for a confirmation that will be refused. If the human wants to waive one criterion, that is `/speckit-eil-override`.
6. **Ask the human directly** whether they have reviewed the evidence and confirm the story is complete, and for the name they are confirming as. Put the question to the person in the conversation and wait for their own answer.
7. **Record it** with their words passed **verbatim**:

   ```bash
   eil approve completion --by "<their name>" --attestation "<their words, verbatim>" --json
   ```

   On a refusal (`verification-missing`, `unverified-requirement`, `unverified-artifact`, an unmet criterion), show it and stop.
8. **Finish**: run `eil sync --json`, then report the approval or the refusal.

## Rules

- **Never supply the confirmation yourself.** Do not write, paraphrase or complete the human's answer, and do not treat silence or "just approve" as one.
- Do not edit the `approval` region by hand, and do not describe the story as complete before the helper has recorded the approval.
