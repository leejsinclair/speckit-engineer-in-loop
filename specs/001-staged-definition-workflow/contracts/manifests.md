# Contract: preset and extension manifests

Shapes are the ones the installed Spec Kit validates (research F-1..F-4, F-9). Values are the intended ones; a contract test (C-01, C-02) installs both and asserts them.

## `preset.yml`

```yaml
schema_version: "1.0"

preset:
  id: "engineer-in-the-loop"
  name: "Engineer in the Loop"
  version: "0.1.0"
  description: "Rigorous, hard-gated staged definition workflow: Requirements, Functional, Technical and AI Specification, each closed by developer approval."
  author: "leejsinclair"
  repository: "https://github.com/leejsinclair/speckit-engineer-in-loop"
  license: "MIT"

requires:
  speckit_version: ">=1.0.2.dev0"

provides:
  templates:
    # ---- new document skeletons (D-02, risk R-1)
    - {type: template, name: s00-readme-template,          file: templates/s00-readme-template.md}
    - {type: template, name: s01-requirements-template,    file: templates/s01-requirements-template.md}
    - {type: template, name: s02-functional-spec-template, file: templates/s02-functional-spec-template.md}
    - {type: template, name: s03-technical-spec-template,  file: templates/s03-technical-spec-template.md}
    - {type: template, name: s07-verification-template,    file: templates/s07-verification-template.md}
    - {type: template, name: s08-completion-template,      file: templates/s08-completion-template.md}
    # ---- overrides of core templates (the three aliased documents)
    - {type: template, name: spec-template,  file: templates/spec-template.md,  replaces: spec-template}
    - {type: template, name: plan-template,  file: templates/plan-template.md,  replaces: plan-template}
    - {type: template, name: tasks-template, file: templates/tasks-template.md, replaces: tasks-template}
    # ---- command overrides (D-13)
    - {type: command, name: speckit.specify,   file: commands/speckit.specify.md,   strategy: replace, replaces: speckit.specify}
    - {type: command, name: speckit.clarify,   file: commands/speckit.clarify.md,   strategy: wrap}
    - {type: command, name: speckit.plan,      file: commands/speckit.plan.md,      strategy: wrap}
    - {type: command, name: speckit.tasks,     file: commands/speckit.tasks.md,     strategy: wrap}
    - {type: command, name: speckit.analyze,   file: commands/speckit.analyze.md,   strategy: wrap}
    - {type: command, name: speckit.checklist, file: commands/speckit.checklist.md, strategy: wrap}
    - {type: command, name: speckit.implement, file: commands/speckit.implement.md, strategy: wrap}

tags: ["governance", "process", "traceability", "human-in-the-loop"]
```

Rules verified against validation: `requires.speckit_version` is the only dependency field (F-3); command entries follow the `lean` and `constitution-sync` shape (F-1, F-2); `wrap` bodies contain `{CORE_TEMPLATE}` exactly once.

**Not provided**: no hooks (presets cannot), no scripts (the helper lives in the extension, D-08), no `constitution`, `converge` or `taskstoissues` override.

## `extensions/eil/extension.yml`

```yaml
schema_version: "1.0"

extension:
  id: eil
  name: "Engineer in the Loop"
  version: "0.1.0"
  description: "Stage, approval, challenge, override and traceability commands, and the deterministic helper behind them."
  author: "leejsinclair"
  repository: "https://github.com/leejsinclair/speckit-engineer-in-loop"
  license: "MIT"

requires:
  speckit_version: ">=1.0.2.dev0"
  tools:
    - {name: python3, required: true}
    - {name: git, required: false}          # identity default only

provides:
  commands:
    - {name: speckit.eil.requirements, file: commands/speckit.eil.requirements.md, description: "Start a story and draft, challenge and gate Requirements"}
    - {name: speckit.eil.functional,   file: commands/speckit.eil.functional.md,   description: "Functional Specification stage"}
    - {name: speckit.eil.technical,    file: commands/speckit.eil.technical.md,    description: "Technical Specification stage (developer-owned)"}
    - {name: speckit.eil.ai-spec,      file: commands/speckit.eil.ai-spec.md,      description: "Assemble the AI Specification from approved stages"}
    - {name: speckit.eil.verify,       file: commands/speckit.eil.verify.md,       description: "Record verification evidence"}
    - {name: speckit.eil.complete,     file: commands/speckit.eil.complete.md,     description: "Completion stage"}
    - {name: speckit.eil.comprehend,   file: commands/speckit.eil.comprehend.md,   description: "Comprehension check before approving Functional or Technical"}
    - {name: speckit.eil.artifact,     file: commands/speckit.eil.artifact.md,     description: "Record an exported wireframe or diagram image with its source"}
    - {name: speckit.eil.challenge,    file: commands/speckit.eil.challenge.md,    description: "Raise or answer a challenge"}
    - {name: speckit.eil.approve,      file: commands/speckit.eil.approve.md,      description: "Record a stage approval (human confirmation)"}
    - {name: speckit.eil.override,     file: commands/speckit.eil.override.md,     description: "Record a named, reasoned override"}
    - {name: speckit.eil.amend,        file: commands/speckit.eil.amend.md,        description: "Re-sign an approval covered entirely by cited human decisions"}
    - {name: speckit.eil.abbreviate,   file: commands/speckit.eil.abbreviate.md,   description: "Record an abbreviated stage"}
    - {name: speckit.eil.resolve,      file: commands/speckit.eil.resolve.md,      description: "Carry a pending clarification upstream"}
    - {name: speckit.eil.trace,        file: commands/speckit.eil.trace.md,        description: "Traceability chain and gaps"}
    - {name: speckit.eil.status,       file: commands/speckit.eil.status.md,       description: "Where the story is, who approved what, what is outstanding"}

  scripts:
    - {name: eil, file: scripts/python/eil, description: "Deterministic helper (fingerprints, aliases, gates, records, artefact, diagram and comprehension checks)"}

  config:
    - {name: eil-config.yml, template: config-template.yml, description: "Approvers per stage", required: false}

hooks:
  after_clarify:
    command: speckit.eil.status
    optional: false
    description: "Refresh mirrors and overview after clarification"
  after_plan:
    command: speckit.eil.status
    optional: false
    description: "Refresh mirrors and overview after planning"
  after_tasks:
    command: speckit.eil.status
    optional: false
    description: "Refresh mirrors and overview after task generation"
  after_implement:
    command: speckit.eil.status
    optional: false
    description: "Refresh overview after implementation"

tags: ["governance", "process", "traceability"]

config:
  defaults:
    default_developer: null
    approvers: {requirements: [], functional: [], technical: [], completion: []}
    abbreviation_authorisers: []
```

Templates carry the artefact sections and example `ART` items (document-format.md, Templates). The exported files live in the story's `assets/` directory, which is created by `eil artifact register` at story time, so neither manifest lists it and install adds nothing outside `.specify/` and the agent's command directory (FR-001).

Rules: command names match `speckit.<ext>.<command>` (F-4). Hooks carry **no refusal** (D-05): `status` only syncs and regenerates the overview. `provides.scripts` is a directory-of-record for the helper; if the installed Spec Kit does not copy a directory tree for a script entry, the fallback is to list each file under `provides.scripts` (contract test C-04 checks the helper runs from `.specify/extensions/eil/`).

## Install and removal contract

| Action | Command | Expected result |
|---|---|---|
| Install extension | `specify extension add --dev ./extensions/eil` (or `--from <archive>`) | `.specify/extensions/eil/` populated; 15 commands registered as skills `speckit-eil-*`; 4 hooks in `.specify/extensions.yml`; no file the project's authors wrote is changed |
| Install preset | `specify preset add --dev <staged dir>` or `--from <archive>`; never `--dev .` from the repository root, which copies the whole repository (research F-16) | 9 templates resolvable; 7 core commands composed; the only tracked files that change are the agent's generated skills for those 7 commands, recomposed in place (research F-14); no file the project's authors wrote is changed |
| Order | extension first, then preset | The preset's guard (D-08) fails closed if the extension is absent |
| Remove | `specify preset remove engineer-in-the-loop`, `specify extension remove eil` | Core commands and templates resolve as before install; stage documents, aliases and mirrors remain as ordinary files (FR-005); the generated skills are regenerated equivalent in content, not byte-identical (F-14); `.specify/extensions.yml` has no `eil` hooks |
