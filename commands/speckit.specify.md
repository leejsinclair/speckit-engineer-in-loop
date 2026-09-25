---
description: Start a story at the Requirements stage. Replaces the standard specify command, which would write spec.md.
argument-hint: "Describe the story you want to define"
strategy: replace
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## Guard (engineer-in-the-loop)

If `.specify/extensions/eil/scripts/python/eil` does not exist, STOP. Tell the user to run `specify extension add eil` and then `specify preset add engineer-in-the-loop`, and do nothing else: continuing without the helper would let a story bypass its gates.

## Pre-Execution Checks

**Check for extension hooks (before specification)**:
- Check if `.specify/extensions.yml` exists in the project root.
- If it exists, read it and look for entries under the `hooks.before_specify` key
- If the YAML cannot be parsed or is invalid, skip hook checking silently and continue normally
- Filter out hooks where `enabled` is explicitly `false`. Treat hooks without an `enabled` field as enabled by default.
- For each remaining hook, do **not** attempt to interpret or evaluate hook `condition` expressions:
  - If the hook has no `condition` field, or it is null/empty, treat the hook as executable
  - If the hook defines a non-empty `condition`, skip the hook and leave condition evaluation to the HookExecutor implementation
- When constructing command invocations from hook command names, replace dots (`.`) with hyphens (`-`). For example, `speckit.git.commit` → `/speckit-git-commit`.
- For each executable hook, output the following based on its `optional` flag:
  - **Optional hook** (`optional: true`):
    ```
    ## Extension Hooks

    **Optional Pre-Hook**: {extension}
    Command: `/{command}`
    Description: {description}

    Prompt: {prompt}
    To execute: `/{command}`
    ```
  - **Mandatory hook** (`optional: false`):
    ```
    ## Extension Hooks

    **Automatic Pre-Hook**: {extension}
    Executing: `/{command}`
    EXECUTE_COMMAND: {command}

    Wait for the result of the hook command before proceeding to the Outline.
    ```
    After emitting the block above you MUST actually invoke the hook and wait for it to finish before continuing. Run it the same way you would run the command yourself in this agent/session (the invocation may differ from the literal `{command}` id shown above, e.g. a skills-mode agent runs it as `/skill:speckit-...` or `$speckit-...`). Emitting the block alone does not run the hook.
- If no hooks are registered or `.specify/extensions.yml` does not exist, skip silently

## Outline

This command starts a *governed story* (engineer-in-the-loop). A story begins at the **Requirements** stage, never with a `spec.md`: the file named `spec.md` is created later, as an alias of the AI Specification, and nothing may write through it. So this command never creates or writes `spec.md`, `plan.md` or `tasks.md`.

The text the user typed after `/speckit-specify` **is** the story description. If it is empty, ask for one and stop.

1. **Name the story.** Choose a concise short name (2-4 words, action-noun form, for example `duplicate-customer-detection`) and a plain-language title from the description.
2. **Branch creation** (optional, via hook): if a `before_specify` hook ran and printed `BRANCH_NAME` and `FEATURE_NUM`, note them. The branch name does not dictate the directory name.
3. **Choose the feature directory** exactly as the standard command does: use `SPECIFY_FEATURE_DIRECTORY` if the user gave one; otherwise `specs/<prefix>-<short-name>`, where the prefix follows `feature_numbering` in `.specify/init-options.json` (`timestamp`: `YYYYMMDD-HHMMSS`; otherwise the next free three-digit number after scanning `specs/`).
4. **Start the story.** Run:

   ```bash
   python3 .specify/extensions/eil/scripts/python/eil start --title "<title>" --feature-dir "<feature directory>" --json
   ```

   - It creates the feature directory, `s00-README.md` (the generated overview) and `s01-requirements.md`, and records `.specify/feature.json` if there is none.
   - On a non-zero exit, stop and show the refusals (code, message, fix). `already-governed` means the story exists: point the user to the command for its current stage instead. `directory-has-spec-md` means an ordinary Spec Kit feature is there: never take it over; choose a new directory.
5. **Continue as the Requirements stage**: run `/speckit-eil-requirements` with the user's description as its input. That command drafts the document, runs the gate and reports.

## Mandatory Post-Execution Hooks

**You MUST complete this section before reporting completion to the user.**

Check if `.specify/extensions.yml` exists in the project root.
- If it does not exist, or no hooks are registered under `hooks.after_specify`, skip to the Completion Report.
- If it exists, read it and look for entries under the `hooks.after_specify` key.
- If the YAML cannot be parsed or is invalid, skip hook checking silently and continue to the Completion Report.
- Filter out hooks where `enabled` is explicitly `false`. Treat hooks without an `enabled` field as enabled by default.
- For each remaining hook, do **not** attempt to interpret or evaluate hook `condition` expressions:
  - If the hook has no `condition` field, or it is null/empty, treat the hook as executable
  - If the hook defines a non-empty `condition`, skip the hook and leave condition evaluation to the HookExecutor implementation
- When constructing command invocations from hook command names, replace dots (`.`) with hyphens (`-`). For example, `speckit.git.commit` → `/speckit-git-commit`.
- For each executable hook, output the following based on its `optional` flag:
  - **Mandatory hook** (`optional: false`) — **You MUST emit `EXECUTE_COMMAND:` for each mandatory hook**:
    ```
    ## Extension Hooks

    **Automatic Hook**: {extension}
    Executing: `/{command}`
    EXECUTE_COMMAND: {command}
    ```
    After emitting the block above you MUST actually invoke the hook and wait for it to finish before continuing. Run it the same way you would run the command yourself in this agent/session (the invocation may differ from the literal `{command}` id shown above, e.g. a skills-mode agent runs it as `/skill:speckit-...` or `$speckit-...`). Emitting the block alone does not run the hook.
  - **Optional hook** (`optional: true`):
    ```
    ## Extension Hooks

    **Optional Hook**: {extension}
    Command: `/{command}`
    Description: {description}

    Prompt: {prompt}
    To execute: `/{command}`
    ```

## Completion Report

Report the feature directory, the two documents created, that no `spec.md` exists yet, and the next step (finish and gate the Requirements, then approve them with `/speckit-eil-approve`).

## Done When

- [ ] The story exists with `s00-README.md` and `s01-requirements.md` and no `spec.md`, `plan.md` or `tasks.md`
- [ ] Extension hooks dispatched or skipped according to the rules above
- [ ] The Requirements stage command was run (or the user was told how to run it)
