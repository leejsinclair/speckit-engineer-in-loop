# Repository Guide for Coding Agents

## Start Here

- Read the binding [constitution](.specify/memory/constitution.md) before changing behavior. It governs enforcement, attestations, dependencies, tests, and human interactions.
- Use the active feature's `spec.md`, `plan.md`, `tasks.md`, and `contracts/` under [`specs/`](specs/) as the design record. Respect task checkpoints and run `/speckit-analyze` after changing `tasks.md` and before implementation.
- Use [README.md](README.md) for product behavior and installation. Link to existing documentation instead of restating it.

## Architecture and Ownership

- The repository ships two coupled products. The preset is rooted at [preset.yml](preset.yml), with `commands/` and `templates/`; the runtime extension is rooted at [extensions/eil/extension.yml](extensions/eil/extension.yml), with command prompts, configuration, and the Python helper.
- Put every gate, refusal, state transition, fingerprint, record, and other deterministic decision in `extensions/eil/scripts/python/eil/`, then cover it with a unit test. Prompts call the helper and obey its exit code; they do not enforce these rules themselves.
- Put behavior that cannot be mechanically checked in command prompts. Every new prompt-only rule needs a text assertion in [tests/contract/test_prompt_guidance.py](tests/contract/test_prompt_guidance.py) or a human probe in [docs/trials.md](docs/trials.md).
- Keep `preset.yml` and `extensions/eil/extension.yml` registrations aligned with their files. Keep both manifest versions aligned for releases.
- The helper supports Python 3.11+ and the standard library only. Do not add runtime dependencies without a constitution amendment.

## Change Discipline

- Follow test-first development: write and observe the focused test fail before implementing the behavior.
- Change a contract in `specs/**/contracts/*.md` together with the tests that pin it.
- Preserve honest limits: gates are attestation-level, not tamper-proof; AI judgments must be labelled; agents never supply, infer, or rewrite a person's confirmation.
- For a human interaction, state its purpose as awareness, understanding, decision, validation, or approval. Do not ask people to reconfirm unchanged decisions, and do not remove a decision, approval, or risk acceptance to reduce ceremony.
- Treat generated story overviews and aliases as helper-owned. In installed projects, edit staged `s0N-*` documents rather than generated `s00-README.md` or `spec.md`/`plan.md`/`tasks.md` mirrors.
- Never install the preset directly from the repository root: `specify preset add --dev .` copies the entire checkout. Stage it first with `python3 tools/stage.py <dir>`, then install the extension before the preset as documented in [README.md](README.md).

## Validation

- Fast CI-equivalent check: `ruff check . && ruff format --check . && python3 -m pytest -q tests/unit`
- Focused test: `python3 -m pytest -q path/to/test_file.py`
- Prompt changes: `python3 -m pytest -q tests/contract/test_prompt_guidance.py`
- Installation or composition changes: run the relevant tests under `tests/contract/`; these require the `specify` CLI and may skip when it is unavailable.
- End-to-end workflow changes: run the relevant tests under `tests/scenario/`.
- Full suite when the change crosses layers: `python3 -m pytest -q`
- Before release packaging, run `python3 tools/stage.py <dir> --archives`; do not inspect generated archives as source files.

## Pull Requests

Use [.github/pull_request_template.md](.github/pull_request_template.md). Name the constitution principles touched, tests or probes for prompt rules, contract/test pairing, and every added or removed human interaction with its purpose.
