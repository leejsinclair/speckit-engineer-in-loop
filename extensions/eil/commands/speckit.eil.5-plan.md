---
description: The numbered entry point for the Plan stage (s05). It runs /speckit-plan, which enforces the stage's entry rule.
argument-hint: "Anything you would give /speckit-plan"
user-invocable: true
disable-model-invocation: false
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## Guard (engineer-in-the-loop)

If `.specify/extensions/eil/scripts/python/eil` does not exist, STOP. Tell the user to run `specify extension add eil` and then `specify preset add engineer-in-the-loop`, and do nothing else: continuing without the helper would let a story bypass its gates.

## What this command is for

A memorable, numbered name for the Plan stage, so the stages line up with the documents (`s05`). It adds no behaviour of its own.

## Steps

1. Run `/speckit-plan` with the user's input exactly as given, and follow it completely. Its entry rule refuses to start unless the AI Specification is approved; if it refuses, show the refusal and stop.
2. Do not skip, shorten or reorder anything `/speckit-plan` asks for, and do not decide anything it leaves to a person.
