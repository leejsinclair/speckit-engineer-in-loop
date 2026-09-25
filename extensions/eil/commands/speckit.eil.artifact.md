---
description: Record an exported wireframe or diagram image, with the link to its source.
argument-hint: "The ART id and the path of the exported file"
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## Guard (engineer-in-the-loop)

If `.specify/extensions/eil/scripts/python/eil` does not exist, STOP. Tell the user to run `specify extension add eil` and then `specify preset add engineer-in-the-loop`, and do nothing else: continuing without the helper would let a story bypass its gates.

## What this command is for

A wireframe is designed in Figma and exported by a person as a static file. This command **records** that export: it hashes the file's raw bytes, keeps it under the story's `assets/` directory, and writes a record naming the exact Figma frame, so a later change to the file is detected. It proves the file exists, is the one recorded and links to a frame. Only a human can confirm it shows the right screen, and the helper cannot see whether the Figma design changed after the export.

Every call below is `python3 .specify/extensions/eil/scripts/python/eil <subcommand> --json`. **Stop on any non-zero exit** and show the helper's `refusals` (code, message, fix).

## Steps

1. **Synchronise**: run `eil sync --json`, then `eil artifact list --json` to see which `ART` items are still waiting for an export.
2. **Ask the human** for:
   - the `ART` id the export is for (it must already exist as an `ART` line, tracing to what it shows);
   - the exported file (`png`, `svg`, `pdf`, `jpg` or `jpeg`), placed **inside the story's directory** (for example in `assets/`); a path outside the story is refused;
   - the **link to the exact Figma frame, including `node-id=`** (right-click the frame in Figma and copy the link), or, for an image of a diagram made in another tool, a link to its source and what it depicts.
   Ask for the name of whoever exported it if it is not the developer.
3. **Do not create, convert or edit the file.** Do not draw a substitute, resize, re-export, screenshot or compress an image, and do not guess a frame link. If the human has no export yet, leave the `ART` line waiting and say so.
4. **Record it**: run

   ```bash
   eil artifact register --id ART-### --file <path> --kind wireframe --source-tool figma --source-url "<frame link>" [--exported-by "<name>"] --json
   ```

   Use `--kind image --depicts <diagram kind>` for an image of a diagram. Show the record. On a refusal (`artifact-no-provenance`, `artifact-format-not-allowed`, `path-outside-package`, `artifact-wrong-level`, ...), show it and stop.
5. **Say what changed.** If the stage was already approved, a new or changed export changes its document, so the stage now needs re-review and the human must approve it again.
6. **Finish**: run `eil sync --json`.

## Rules

- Never draw a wireframe or diagram, and never produce, alter or convert an exported file. You may only ask for one and record the one you are given.
