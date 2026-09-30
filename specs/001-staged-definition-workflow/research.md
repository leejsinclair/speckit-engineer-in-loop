# Research: Staged Definition Workflow

Resolves every unknown in the plan's Technical Context. Facts marked **[verified]** were read from the installed Spec Kit (`specify-cli 1.0.2.dev0`: `presets/__init__.py`, `extensions/__init__.py`, the bundled `lean` and `constitution-sync` presets, the bundled `git` extension, `core_pack/commands/*.md` and `.specify/scripts/bash/*`) or from the reference preset's README. Nothing here is guessed about Spec Kit's behaviour; where a fact could not be verified it is called out as a risk with a test.

---

## Verified platform facts

| # | Fact | Source |
|---|------|--------|
| F-1 | A preset manifest has `preset`, `requires.speckit_version`, `provides.templates[]`, `tags`. A template entry has `type` (`template`, `command` or `script`), `name`, `file`, optional `description`, `replaces`, `strategy`. | `presets/__init__.py` (validation), bundled presets |
| F-2 | Strategies are `replace` (default), `prepend`, `append`, `wrap`. Scripts support only `replace` and `wrap`. `wrap` places the core command where `{CORE_TEMPLATE}` appears. A strategy may also be declared in the command file's frontmatter. | `VALID_PRESET_STRATEGIES`, `VALID_SCRIPT_STRATEGIES`, `constitution-sync` |
| F-3 | A preset's `requires` carries only `speckit_version`; there is no field to depend on an extension. | manifest validation |
| F-4 | An extension manifest has `extension`, `requires`, `provides.commands[]`, `provides.scripts[]`, `provides.templates[]`, `provides.config[]`, `hooks`, `config.defaults`. Command names must match `speckit.<ext>.<command>` (lowercase, digits, hyphens). | `EXTENSION_COMMAND_NAME_PATTERN`, `git` extension |
| F-5 | Hook names are `before_<cmd>` / `after_<cmd>`; each carries `command`, `optional`, `description`, `prompt`. Installing registers them in `.specify/extensions.yml`. A hook is **rendered as an instruction to the AI agent** (`EXECUTE_COMMAND: …`); Spec Kit does not run it as code. `settings.auto_execute_hooks` exists and can be turned off. | `HookExecutor`, core command text |
| F-6 | Core scripts reference `spec.md`, `plan.md`, `tasks.md` by fixed name (`setup-tasks.sh` errors if either of the first two is missing; `check-prerequisites.sh` errors if `plan.md` is missing). | `.specify/scripts/bash/*` |
| F-7 | `setup-plan.sh` copies the plan template to `plan.md` **only if it does not already exist**. `create-new-feature.sh` and the core `specify` command write `spec.md` from the resolved `spec-template`. | `setup-plan.sh`, `create-new-feature.sh`, `specify.md` |
| F-8 | The active feature directory comes from `SPECIFY_FEATURE_DIRECTORY` or `.specify/feature.json`. | `common.sh` |
| F-9 | `specify preset add --dev <dir>` and `specify extension add --dev <dir>` install from a local directory; `--from <url>` installs from an archive. Both have `remove`, `enable`, `disable`, `set-priority`. | CLI help |
| F-10 | The install target for an extension is `.specify/extensions/<id>/`; its config may be overridden per machine in `extensions/*/local-config.yml` (git-ignored). | `HookExecutor`, `.specify/.gitignore` |
| F-11 | The project's install uses the Claude integration with `ai_skills: true`, so commands are invoked as `/speckit-<name>`. | `.specify/init-options.json` |
| F-12 | `python3` 3.11+ is guaranteed wherever `specify` runs (`Requires-Python >=3.11`); `jq` is optional in core scripts, `yq` is absent. | package metadata; `which` |
| F-13 | `requires.speckit_version` is checked with PEP 440 and prereleases allowed, so the installed `1.0.2.dev0` (which sorts *before* `1.0.2`) fails `>=1.0.2`. The floor that admits the verified build is `>=1.0.2.dev0`. | `_utils.version_satisfies`; risk spike 2026-09-25 (found when `specify extension add` refused the stub) |
| F-14 | Installing a preset that wraps or replaces a command recomposes the agent's generated skill in place (`.claude/skills/speckit-<cmd>/SKILL.md`); that is the only tracked file install changes. Removing the preset regenerates it equivalent in content (same frontmatter values and body) but not byte-identical (YAML quoting and a title heading differ). | risk spike, contract tests C-05 |
| F-15 | A `provides.scripts` entry whose `file` is a directory is copied as a whole tree to `.specify/extensions/<id>/<file>/`, and `python3 <that dir>` runs its `__main__.py`. No per-file listing is needed. | contract test C-04 (stub) |
| F-16 | `specify preset add --dev <dir>` copies the whole source directory into `.specify/presets/<id>/` with no ignore mechanism (installing from the repository root copied 82 MB, including `.venv`, `specs/` and `tests/`). `specify extension add` honours `.extensionignore`, but read from the *extension's own directory*, not the repository root. So installs (and release archives) are made from a staged copy of the shipped files only. | risk spike follow-up, contract test C-01 |

---

## Decisions

### D-01 Repository and package layout
**Decision**: One repository. Preset at the root (`preset.yml`, `templates/`, `commands/`); extension in `extensions/eil/`; tests in `tests/`.
**Rationale**: It matches the reference preset (F-1, reference README), keeps the two halves versioned together, and each installs with its own `--dev` or `--from` command (F-9).
**Alternatives**: Two repositories (double release burden, easy to install mismatched versions); extension-only with no preset (cannot override the core `specify` and `plan` commands, so fails FR-003/004).

### D-02 Template names beyond the core five
**Decision**: The preset provides `template`-type entries named `s00-readme-template` … `s08-completion-template`, alongside overrides of the core `spec-template`, `plan-template` and `tasks-template`.
**Rationale**: Templates are resolved by name through the resolver stack (F-1, `resolve-template.sh`); nothing in validation limits names to the core five.
**Risk R-1**: Unproven that arbitrary names install and resolve. Contract test C-03 covers it first.
**Fallback**: Ship the non-core skeletons as `provides.templates` of the **extension** (a resolver layer that exists for extension templates), or read them from `.specify/extensions/eil/templates/` directly in the helper.
**Alternatives**: Inline the skeletons in the command prompts (bloats prompts, no override point for teams).

### D-03 Where state lives
**Decision**: Each stage document carries its own approval, challenge, override and abbreviation records as fenced JSON blocks inside `<!-- eil:begin … -->` / `<!-- eil:end -->` markers. Approver configuration lives in the extension config file. There are no other state files.
**Rationale**: FR-046 and the "nine documents, three aliases" constraint rule out a hidden state store; FR-069 defines a stage's status by "which documents exist and which carry a recorded approval", which presumes approvals sit in the documents; ordinary `git diff` then shows every approval and override (SC-002, spec Constraints).
**Alternatives**: A sidecar `.eil/state.json` (a tenth file, invisible to a reader of the package, drifts from the documents); YAML front matter (PyYAML is not in the stdlib, and front matter would be fingerprinted with the body, making the approval self-invalidating).
**Consequence**: Fingerprinting must exclude the approval block (D-09).

### D-04 Implementation language for the deterministic helper
**Decision**: Python 3.11+ standard library only, run as `python3 <ext>/scripts/python/eil …`.
**Rationale**: One implementation for Linux, macOS and Windows (F-12). Fingerprinting, alias handling and JSON parsing are awkward and platform-divergent in shell (`sha256sum` vs `shasum`, no JSON). Zero third-party runtime dependencies keeps SC-001's ten-minute install honest.
**Alternatives**: Bash plus PowerShell pairs like the core scripts (two implementations to keep behaviourally identical, weak JSON); Node (adds a runtime Spec Kit users do not necessarily have); AI-only enforcement with no code (fails FR-011/044/051, which need reproducible fingerprints and fault detection).

### D-05 Three enforcement layers
**Decision**:
1. **Helper (code)**: everything deterministic, meaning fingerprints, alias faults, mirror refresh, gate results, traceability checks, record writing, overview generation. It returns non-zero on refusal.
2. **Preset wraps (prompt at command entry)**: each intercepted command begins by running the helper's `enter` step and **stops on a non-zero exit**. This is the refusal mechanism for FR-004, FR-008, FR-053.
3. **Extension hooks**: `after_*` only, to refresh the overview and mirrors after a command finishes. No hook carries a refusal.
**Rationale**: Hooks are instructions to the agent and can be disabled with `auto_execute_hooks` (F-5), so refusal must not depend on them. Wraps are part of the command prompt itself and cannot be skipped by a setting. Code beats prose wherever a result must be reproducible.
**Honest limit**: all three run through the AI agent; a human editing files directly bypasses them. That is the spec's stated attestation-level assumption, made detectable by fingerprints (FR-044).

### D-06 `spec.md`, `plan.md`, `tasks.md` as aliases
**Decision**: `spec.md → s04-ai-spec.md`, `plan.md → s05-plan.md`, `tasks.md → s06-tasks.md`, created when the target is created.
**Rationale**: Core scripts require those exact names (F-6). Because `setup-plan.sh` skips its copy when `plan.md` exists (F-7), the wrapped `plan` command first has the helper create `s05-plan.md` from the plan template and its alias; core then finds the alias and proceeds and writes through it. The replaced `specify` command never calls the core steps that write `spec.md` (D-13).
**Alternatives**: Rename the core scripts' constants (edits Spec Kit files, forbidden by FR-001); wrap the scripts to take file names (script wraps are supported, F-2, but would need bash + PowerShell variants and re-wrapping on every core script change).

### D-07 Alias mechanism: symlink, falling back to mirror
**Decision**: The helper first tries a **relative symlink** (`spec.md -> s04-ai-spec.md`). If the platform or filesystem refuses (or Git checked a link out as a text file), it writes a **read-only mirror** with identical bytes and lists it in the overview's "Mirrors" section. `sync` runs at the start of every wrapped or extension command; it compares each alias to its target, **reports any difference as an alias fault first**, then refreshes the mirror from the target.
**Rationale**: Directly implements FR-049, FR-051, FR-053 and clarification 9. Detection rule: alias absent → fault; symlink to the wrong target → fault; regular file whose bytes differ → fault (edited mirror, or replaced real file); regular file whose bytes match → valid mirror.
**Edge**: A symlink that Git materialised as a one-line text file containing the target path differs from the target, so it is reported as a fault and then replaced by a mirror. Correct behaviour, and it surfaces the platform limitation.
**Alternatives**: Hard links (break on editors that replace files, and Git does not preserve them); always mirror (loses the single-document guarantee on platforms that could have had it).

### D-08 Preset-to-extension coupling
**Decision**: Every preset wrap starts with a guard step: if `.specify/extensions/eil/scripts/python/eil` is missing, stop and print the two install commands. The README documents installing both, extension first.
**Rationale**: F-3 gives the preset no way to declare the dependency, and a wrap that silently degrades to the core behaviour would let a story bypass the gates without anyone knowing, which is the opposite of the feature's purpose.
**Alternatives**: Bundle the helper inside the preset (a script `provides` type exists, but then the preset alone carries logic and the "companion extension" split is meaningless); fail open (rejected above).

### D-09 Content fingerprint
**Decision**: SHA-256 of the **normalised** document text, hex-encoded, recorded as `sha256:<hex>`. Normalisation, in order: decode UTF-8; convert CRLF and CR to LF; strip trailing whitespace from every line; collapse runs of blank lines to a single blank line; strip leading and trailing blank lines; **remove every `eil:begin approval` … `eil:end approval`, `eil:begin assessment` … `eil:end assessment` and `eil:begin comprehension` … `eil:end comprehension` region** (the `## Approval`, `## Quality Assessment` and `## Comprehension Check` headings stay and are fingerprinted); re-encode UTF-8.
**Rationale**: FR-011 needs a version identifier that is stable across clone, checkout and merge (a timestamp is not; the user reverted it), and FR-044 declares line endings, trailing spaces and repeated blank lines to be non-changes. Excluding the approval region avoids the circularity of a document fingerprinting its own approval; excluding the assessment region means re-running a check never changes a document's identity, since the assessment is derived output; the comprehension region is excluded for the same reason it must record the fingerprint it was taken on. Full formal spec in [contracts/document-format.md](contracts/document-format.md).
**Known limit**: whitespace *inside* a fenced code block is normalised like any other (the rule is line-based, not Markdown-aware). Accepted: code blocks in definition documents are illustrative, and a Markdown-aware rule would be heavier and easier to get wrong.
**Alternatives**: Git blob hash (depends on line-ending config and includes formatting); per-file mtime (rejected by the user).

### D-10 Identifiers and traceability syntax
**Decision**: Item identifiers per story, zero-padded to three digits, never reused: `REQ-###`, `UC-###`, `FR-###`, `NFR-###`, `DEC-###`, `AIS-###` (AI Specification items), `EVD-###` (evidence), `ART-###` (diagrams and wireframes, D-18). Tasks keep Spec Kit's `T###`. An item is defined on a line starting `**ID**:` (optionally after a list marker) and states its sources in a trailing clause `(traces: REQ-003, UC-002)`. Code changes are linked from the task or evidence line as `(code: <commit-sha>|PR#<n>)`.
**Rationale**: Plain text a human can read and a regex can extract; one syntax for every stage; forward and reverse chains are computed by the helper (no hand-maintained reverse index to drift). The per-story `FR-###` deliberately reuses the spec-writing convention Spec Kit users already know.
**Note on collision**: story-level `FR-###` and this feature's own `FR-###` are in different documents of different features; the helper never mixes documents from different feature directories.
**Alternatives**: YAML link tables (heavy to author, drift-prone); Markdown links between headings (hard to validate, no direction).

### D-11 Approver identity and "AI cannot approve"
**Decision**: `approve` requires `--by <name>` matching an entry in the stage's configured approvers (default: the story's developer, resolved from `git config user.name` / `user.email`, else the config's `default_developer`), and `--attestation "<verbatim text>"`. The `speckit.eil.approve` command prompt instructs the agent to ask the human directly, wait for an explicit answer, and pass that answer's text through. The record stores name, UTC time, fingerprint, the attestation text and an optional `played_back_to` note (FR-066). `approve` re-runs the gate and refuses on any unmet criterion, open challenge or unaccepted open question.
**Rationale**: FR-012 cannot be made cryptographically true (Out of Scope: no signing). What can be done is to make an approval require a named, configured person plus a recorded verbatim confirmation, so an approval fabricated by the agent is *visible as such* in the record and in review. The pull request's two-approver rule is the out-of-band backstop (clarification 2).
**Alternatives**: OS-level prompts or TTY detection (defeated trivially, and breaks non-interactive CI use); signatures (out of scope).

### D-12 Stage derivation and re-review
**Decision**: A feature is **governed** iff `s00-README.md` exists (FR-069). Current stage = the first stage in order whose document is missing or not validly approved. A stage is *approved* iff it has an approval record whose fingerprint equals the document's current fingerprint. An approval also records, for each **upstream** document, that document's fingerprint and the per-item hashes of the IDs it depends on. A stage whose upstream fingerprints no longer match is reported **needs re-review**, and the helper lists exactly the downstream items whose `traces` reference an upstream ID with a changed hash (FR-043).
**Rationale**: Statuses are derived from documents, never stored separately, so the overview cannot disagree with them for long (FR-056: documents win). Item-level hashes give the "which items are affected" answer without a second store.
**Alternatives**: Stored status field (can be edited independently of content, contradicting FR-044); whole-document staleness only (fails the "identify which items are affected" clause of FR-043).

### D-13 Behaviour of the intercepted core commands
| Core command | Strategy | What the preset adds |
|---|---|---|
| `specify` | replace | Never writes `spec.md`. Creates the feature directory as core does, persists `.specify/feature.json`, then runs the Requirements stage (`speckit.eil.requirements`). Satisfies FR-003 and the "writing through an alias" edge case. |
| `clarify` | wrap | Writes each accepted answer into `s04-ai-spec.md` as a marked pending item (`[pending-clarification]`), refuses if `s04` does not yet exist (nothing to write into), and points the human to `speckit.eil.resolve` to carry it upstream (FR-067). |
| `plan` | wrap | Guard, `sync`, gate (AI Spec complete, traceable, no pending items), create `s05-plan.md` and alias, then core plan body (FR-004, FR-057). |
| `tasks` | wrap | Same, then creates `s06-tasks.md` and alias (FR-004, FR-058). |
| `analyze` | wrap | Core behaviour over the three aliases is untouched, followed by `eil check --chain` (FR-025..029) reported in the same table style (FR-068). |
| `checklist` | wrap | Adds `s01`/`s02` as **read-only** extra context so checklist items about requirement quality have their real source; still reads the `spec.md` alias as core does. Resolves OQ-001 in design; proven by scenario B-11. |
| `implement` | wrap | Guard, `sync`, gate (plan and tasks exist and are traceable). |
| `constitution`, `taskstoissues`, `converge` | none | Untouched. |
**Rationale**: `replace` only where core behaviour would violate the model (`specify`); `wrap` everywhere else so core improvements still flow through and removal restores stock behaviour (FR-005, SC-009).

### D-14 The overview is generated
**Decision**: `s00-README.md` is written entirely by `eil overview` from the documents' records. The file carries a "generated; edit the stage documents" notice. It holds title, owner, stage, status, document index with per-document status, an artefact index (id, kind, stage, state; links only, FR-086), approvals, outstanding questions/challenges/overrides/issues, and a Mirrors list. It contains no requirement, behaviour or design text (FR-055); a structural check enforces that by only emitting from records and fixed labels.
**Rationale**: Manual edits are exactly how overview and documents diverge (FR-056). Regenerating is cheap and idempotent. Stage documents remain authoritative if the two disagree.
**Alternatives**: Hand-maintained (drifts); partially generated with a free-text region (invites specification content, violating FR-055).

### D-15 Test strategy
**Decision**: Three tiers. (1) `pytest` unit tests for every helper module, with fingerprint and alias-fault tables driven from fixtures. (2) Contract tests that install preset and extension into a scratch project created by `specify init --here` in a temp directory and assert registration, template and command resolution, uninstall cleanliness and that no pre-existing file changed (SC-001, SC-009, FR-001, FR-005). (3) Scenario tests replaying [quickstart.md](quickstart.md). The unit tier also carries the Mermaid subset fixtures (each accepted construct, each consistency rule passing and failing, unparseable input) and sample exports for the hash, format and provenance checks (D-20). Prompt-quality outcomes (SC-007, SC-008, SC-010) and the wireframe content review (D-21) are **human trials**, not automated.
**Rationale**: Deterministic behaviour is testable in code; AI-following-instructions behaviour is not, and pretending otherwise would overstate what is verified.

### D-16 Abbreviation, and telling AI-drafted from human-reviewed content
**Decision**: *Abbreviation* is a record in the stage document (`who`, `why`, `sections_condensed`) and a status shown in the overview; the stage is never skipped and still passes a gate (FR-040). *Not-applicable sections* are removed only with a recorded reason line (FR-018). AI-authored text that a human has not reviewed is tagged `[ai-draft]` at item or section level; the gate lists any remaining `[ai-draft]` tag as an unreviewed item, and approval refuses while any remains unless overridden (spec edge case "AI-added content not reviewed").
**Rationale**: Uses the same visible, greppable, diffable mechanism as everything else; no new file or store.

### D-17 Which artefact belongs to which stage (FR-071..074)
**Decision**: The stage that owns a level of abstraction owns its diagram, and each stage may only *see* what its level allows.

| Stage | Owns | Sees |
|---|---|---|
| s01 | C4 Level 1 system context | the system as one box, its people and neighbouring systems |
| s02 | system-level sequence diagram per use case (or N/A with reason); wireframes per screen state (or N/A with reason) | actors and the system as one participant; screens. No containers, components, technology, or data structures |
| s03 | C4 Level 2 container; C4 Level 3 component per new or changed container (or N/A with reason); technical sequence diagram per use case that crosses containers (or N/A with reason); ER diagram | everything |
| s04 | nothing; references approved artefacts as `AIS` items tracing to `ART` | |
| s05, s06 | nothing; s06 tasks are covered against artefacts through `AIS` | |
| s07 | evidence about artefacts (`EVD` tracing to `ART`) | |
| s08 | a currency statement per artefact | |

**Rationale**: This makes FR-019 and FR-020 checkable: "the functional sequence diagram names a component" is a structural finding, where "prescribes implementation" alone is a judgement. The AI Specification must not decide (FR-039), so it may point at approved diagrams (Mermaid text is what an agent reads best) but not draw its own.
**Alternatives**: A conceptual ER diagram in s02 (rejected: it invites schema thinking before Technical, and the process standard puts data design in s03); wireframes as an optional s01 artefact (rejected: a screen is a behaviour decision, so an existing design is only a linked reference in s01, binding once s02 adopts an export); C4 Level 4, deployment, dynamic and UML state diagrams (rejected for now: not asked for; the artefact kinds are a closed list that can grow, see D-18).

### D-18 Artefact identity and storage (FR-071, FR-076, FR-077)
**Decision**: Every artefact is an item `ART-###` (D-10 grammar, `traces:` clause, in both directions). Two storage forms, one item line:
- **Inline diagram**: the item line is followed by a fenced ` ```mermaid ` block. The kind is **derived** from the diagram's first keyword (`C4Context` → context, `C4Container`, `C4Component`, `sequenceDiagram` → sequence, `erDiagram` → er) and the owning stage (a `sequenceDiagram` in s02 is functional, in s03 technical). No separate record. The block is ordinary document text, so it is fingerprinted and its item hash covers it.
- **Exported file** (wireframe, or an image of a diagram made elsewhere): the item line is followed by an ` ```eil:artifact ` record block (file, file fingerprint, format, source). The file lives in `assets/` in the feature directory.
A fence or record with no preceding `ART` item line is `artifact-unregistered`. The `assets/` directory is created when the first export is registered (FR-047).
**Rationale**: Reuses the item, trace and fingerprint machinery instead of a parallel registry. Inline text means a diagram edit *is* a document edit, so FR-044 and FR-043 apply with no new code. Only real binary files need a record, because they are the one thing the document fingerprint cannot see.
**Alternatives**: A separate artefact registry file (a second store, contradicting D-03); referencing exports by relative Markdown image link only (no fingerprint, so a swapped file goes unnoticed); a record block for every diagram (duplicates what the diagram itself already says).

### D-19 Figma wireframes: export, provenance, drift (FR-077, FR-078)
**Decision**: The human designs in Figma and exports frames as static files (Figma offers PNG, SVG, PDF and JPG, confirmed in the first trial; PNG at 2x is the recommended default, SVG accepted). The AI cannot do this and asks for it (FR-085). `eil artifact register` copies the file into `assets/`, computes the SHA-256 of the **raw bytes** (not normalised, since these are binary), and writes the record: `file`, `sha256`, `format`, `source: {tool: "figma", url, exported_at, exported_by}`. For `tool: figma` the URL must carry a `node-id` so a reviewer can open the exact frame. Re-registering rewrites the record, which changes the document and so triggers re-review. A file that no longer matches its record is `artifact-hash-mismatch`.
**Rationale**: A link alone rots and cannot be fingerprinted; a file alone loses where it came from. Both together give a reviewer the approved picture and a path to the source. Figma is read by nobody in code (out of scope), so drift after export is invisible and recorded as attestation-level in the spec assumptions.
**Alternatives**: Link-only (no evidence of what was approved); the Figma REST API (an external integration, out of scope and needs a token); storing exports outside the repository (breaks FR-046).

### D-20 Diagram parsing and consistency rules (FR-079, FR-080, FR-081)
**Decision**: `diagrams.py` extracts elements from the five Mermaid diagram types with line-oriented regexes, not a full parser:
- C4: the `Person`/`System`/`Container`/`Component` families (with `Db`, `Queue` and `_Ext` variants), boundary macros, and the `Rel` family. The list was widened from the first draft after the Mermaid documentation examples were read (2026-09-25): queues, `*Db_Ext`, `Component_Ext`, the generic `Boundary`, unquoted labels and `$name=` arguments all appear there. The element **name** is its display label (second argument), compared case-insensitively with whitespace collapsed, since aliases differ between diagrams.
- sequence: `participant`/`actor X as Label`, plus participants implied by messages.
- ER: entity blocks and relationship lines.
Rules, each a finding with a stable code and overridable (FR-045): (a) L2 external people and systems equal L1's; a component diagram has a `Container_Boundary` whose label is a container in L2. (b) functional sequence participants ⊆ declared actors ∪ {`System`}. (c) technical sequence participants ⊆ C4 element labels. (d) an ER `ART` item carries `(store: <label>)`, naming a `ContainerDb` or `SystemDb` in L2. (e) each s01 user, stakeholder and dependency appears in L1. (f) L1 elements carry a `[existing]`, `[new]` or `[changed]` marker in their description (FR-072).
**Named lists the rules read**: bullets under the `Users and Stakeholders`, `Dependencies` and `Actors` headings; the name is the first bold span, else the text before `:` or ` — `.
**Rationale**: The team asked for cross-diagram consistency. Regex extraction over a small closed vocabulary is testable with fixtures and never silent: a diagram that yields nothing recognisable is `diagram-unparseable` (FR-080, risk R-5).
**Alternatives**: A full Mermaid parser (a dependency and a moving target); presence-only checks (rejected by the team); Structurizr or PlantUML (rejected by the team in favour of one notation).

### D-21 The helper never renders
**Decision**: The helper parses text and hashes files; it does not render diagrams or read images. Whether a diagram *displays* is the team's tooling (an optional CI step with Mermaid's own CLI can catch it). The AI challenge pass reviews a wireframe's content only if the agent can view the image, and that review is a `judgment` criterion, never a structural pass.
**Rationale**: Keeps the helper stdlib-only (D-04) and offline. Consistent with the attestation-level stance: the code proves the artefact exists, parses and is the one that was approved, and a human confirms it says the right thing.

### D-22 Comprehension check before approving Functional and Technical (FR-087..094)
**Decision**: Before `functional` or `technical` can be approved, the developer takes a five-level comprehension check (`speckit.eil.comprehend`): recognise, explain, apply, trace, evaluate, one question at a time, judged on meaning, with hints that point at the document and unlimited retries, skip and reveal. The helper chooses the target items deterministically (`comprehension plan`); the agent only phrases the question and judges the answer; the helper records outcomes (`comprehension record`). The record lives in a `comprehension` region of the stage document, excluded from the fingerprint like `approval` and `assessment`, and binds to the fingerprint it was taken on. Approval requires a **current, complete** record (all five levels resolved, any outcome), not a pass. Skipped and revealed counts are copied into the approval record and the overview.

| Know Your Spec (README) | This workflow |
|---|---|
| Five levels Recognise, Explain, Apply, Trace, Evaluate | Adopted unchanged |
| Judged on semantic understanding; hints point to spec sections, never reveal | Adopted; a wrong answer caused by a defective document raises a challenge instead of coaching (FR-091) |
| Unlimited retries; skip; reveal | Adopted; a skipped or revealed level can be re-asked with a new item (attempt *k*+1) |
| Fires after `specify`, on `spec.md` | Fires before approval, on `s02` and `s03` |
| Advisory; never blocks | Approval blocked until the check has been **taken** on the current version; **not** until passed (user decision) |
| Writes nothing, ever | Writes outcome, attempts and item ids per level, plus taker and fingerprint; never questions, answers, hints or scores |
| Retries: newly worded at the same level, never identical phrasing; expected answer kept private until asked | Adopted (FR-090) |
| Levels 1 and 2 multiple choice when plausible distractors exist; 3 to 5 free text | Adopted (FR-087) |
| An answer drifting into implementation is coached back to spec level and re-asked without using a retry | Adopted for Functional only; on Technical implementation is in scope (FR-090) |
| Derives all five questions privately first; proposes a batch of repairs to `spec.md` before question 1 | Adapted: pre-scan of the five target items, one batch of challenges, the check stops until they are answered (FR-091). Challenges, not silent repairs, because the human decides |
| Model picks what to ask | Helper picks targets from the document's own items, so the same version gives the same choices and the Trace level uses a real chain |

**Rationale**: The last criterion of the Functional and Technical gates asks that a developer "can explain" the document. That was a bare `judgment` criterion. The check turns it into evidence a pull request reviewer can see (five levels, how many skipped), without making the AI the judge of whether the human may proceed ("AI challenges. Humans decide."). Requiring it to be taken but not passed was the user's decision; the visible counts are the safeguard. Recording no answers keeps the record small, leaves no answer key in the repository and avoids storing what someone said under test.
**Limits**: Judgement of understanding is AI's fallible assessment and is labelled so; that the taker is the confirmer is attestation-level, like approval (D-11). Compared against the Know Your Spec README and, on 2026-09-25, its command text and tests. Its tests (a check that the prompt forbids persistence, plus behavioural probes for coaching, skip and reveal, out-of-scope answers and repair) are adapted into a contract test and the human trial protocol. **Coexistence**: both can be installed. Its mandatory `after_specify` hook also fires after this preset's replaced `specify`, finds no `spec.md` in a governed story and says so and stops: harmless but noisy, and the two checks are independent (this one gates approval of `s02`/`s03`; that one is advisory on `spec.md`, which here is the AI Specification alias).
**Alternatives**: Pass required (rejected by the user: makes AI the gatekeeper of the human's competence); advisory and unrecorded (no evidence, cannot support a gate criterion); a comprehension check on every stage (not asked for; Requirements and AI Specification can be added later).
---

### D-23 Fingerprint neutrality for `[ai-draft]` (FR-095)
**Decision**: The document fingerprint (contracts/document-format.md §Fingerprint algorithm) removes every `[ai-draft]` tag before hashing, **except inside an HTML comment**, the same way the item hash already treats it as neutral. Reviewing and untagging a human's own text is not a content change, so it no longer invalidates an existing `assessment`, `comprehension` record or approval-fingerprint comparison.
**Rationale**: A dogfooding session found untagging alone (no wording changed) forcing a fresh comprehension check and re-judgment, because the whole-document fingerprint moved on the tag alone even though `trace.item_hash` already treated it as neutral. `[pending-clarification]` stays content: clearing it is a human decision made through `eil resolve` (FR-067), not a formatting no-op, and must still trigger re-review.
**Migration**: the first cut of this decision stripped the substring unconditionally and turned out to need one after all: every shipped template's own header comment says the word ("Tag any text the AI wrote with `[ai-draft]` until a human has reviewed it") without it ever being a tag, so every already-created stage document's fingerprint moved on upgrade with nothing actually edited — found via dogfooding on the fix itself. Scoping the removal to outside a comment restores the original argument: `eil approve` already refuses while a *real* (live-text) tag remains, so an already-approved document's hashed text never contained one, and its recorded fingerprint is unaffected retroactively. Only a live `assessment`/`comprehension` record taken while a real tag still remained can go stale across the upgrade — cheap to retake, never blocking.
**Alternatives**: A fingerprint format-version field (rejected: unnecessary once the comment carve-out closes the actual gap, and it would require every caller to carry a version); leaving item hash and document fingerprint inconsistent (rejected: it was exactly the inconsistency causing the churn); stripping only a tag at the true end of a line (rejected: a real tag is routinely followed by a `(traces: ...)` clause or the `[pending-clarification]` tag on the same line, per the item grammar, so "end of line" would miss the common case).

### D-24 Human-decided provenance: the `(decided: ID)` clause (FR-096)
**Decision**: Text copied verbatim from a recorded human decision — an accepted challenge (`CH-###`), a resolved open question (`OQ-###`), or a clarify answer (`AIS-###`) — is written **untagged**, carrying `(decided: ID)` instead of `[ai-draft]`. The helper checks the cited id exists and is in an eligible state (challenge accepted; question resolved or accepted; an `AIS` item); it cannot check that the marked text is a faithful transcription, which stays attestation-level like every other gate (Principle II).
**Rationale**: The `[ai-draft]` tag exists to flag *AI judgement calls* for review. Text that is the human's own words, already reviewed once when they said it, does not need a second review cycle just because the AI is the one typing it into the document.
**Alternatives**: Trusting any untagged text near a `traces:` reference to a human item (rejected: too weak a check, no explicit marker to point review at); requiring the human to type the text themselves (rejected: reintroduces the exact friction being removed).

### D-25 `eil amend`: re-signing an approval covered by cited decisions (FR-097)
**Decision**: `eil amend <stage> --from <ids> --by <name> --attestation <text>` re-signs an approval that is `needs-re-review`, in place of a full `/speckit-eil-approve`, but only when every item that changed since the last approval carries a `(decided: ID)` clause naming one of the cited ids, and no `[ai-draft]` tag remains. It writes a new approval record marked `"amended": true` with the cited ids, visible in the overview exactly as an override is.
**Rationale**: A stage needing re-review after nothing but a carried, human-decided change should not need the full first-approval ceremony (gate walk-through, playback, fresh attestation) repeated; the human already decided, and amend simply re-confirms that stage's approval covers it.
**Alternatives**: Silently keeping the stage approved when the changes are all decided (rejected: an approval is a recorded confirmation event, and no new confirmation would exist at all); re-running the full approval unconditionally (the status quo, and the friction being fixed).

### D-26 Downstream re-review is item-level, not document-level (FR-043, FR-098, FR-099)
**Decision**: `package.state()` marks a stage `needs-re-review` because of an upstream change only when `impact.affected()` shows one of the stage's own items actually traces to something that changed upstream — not whenever any upstream document's whole fingerprint differs from what its approval recorded. When upstream moved but nothing traced is affected, the stage stays `approved` with a visible, non-blocking note.
**Rationale**: `impact.py` already computed the finer answer for `eil trace`/review; `state()` was not using it, so an edit to an unrelated part of an upstream document (a different requirement, a typo in Background) forced re-review of everything downstream regardless of relevance.
**Alternatives**: Leaving the document-level rule (the status quo, and one of the two biggest contributors to the reported churn); re-reviewing downstream stages automatically without a note (rejected: silently loses the visibility a reviewer needs to know something moved at all).

### D-27 Delta comprehension on re-approval (FR-100)
**Decision**: The comprehension check taken for a stage's *first* approval keeps all five levels. On re-approval (the stage was previously approved and is now `needs-re-review`), `comprehension plan` restricts each level's eligible items to what actually changed and returns at most two levels. If every changed item carries a valid `(decided: ID)` clause, the plan reports so and the check is recorded `not-applicable` for those levels with that reason, with no question asked at all.
**Rationale**: The check exists so a person demonstrates they understood what they are approving; on a delta approval that is a much smaller document (what changed), and nothing left to demonstrate at all when every change was the human's own prior decision.
**Alternatives**: Always running the full five levels on every re-approval (the status quo, and the largest single contributor to the reported churn — 8 runs to finish 3); dropping the comprehension requirement on re-approval entirely (rejected: a re-approval can still contain new AI-authored content that deserves the same check).

### D-28 `eil review`: a guided change-by-change review as a first-class action (FR-101)
**Decision**: `eil review start` lists every item and non-item section changed since a stage's last approval (ids and titles only); `eil review accept` records the person's acceptance of one or more, right now, in their own words — writing `(decided: RVW-###)` onto an item's own line (replacing `[ai-draft]` if present) and the `eil:review` record together, as one helper action; `eil review finish` gathers every acceptance recorded since the last approval and re-signs it, sharing its coverage core with `eil amend` (D-25) but auto-collecting `--from` from the review session instead of asking the human to name ids that already exist elsewhere. A non-item section (prose, a reworded paragraph) has no line to carry a clause, so its acceptance is the record alone; coverage for it is a matching-`target` `eil:review` record, never a `(decided: ...)` clause.
**Rationale**: Real dogfooding after implementation found four changes — a new item, a resolved question, a diagram fixed because it would not draw, a reworded paragraph — all reviewed item by item in conversation, with `amend` unusable for any of them: a new item and a diagram edit have no earlier decision to cite, and a prose edit has no item to carry one at all. The review *itself*, done once, is the missing citation; recording it through the helper (not an AI hand-edit of the tag, trusted after the fact) keeps the same attestation-level honesty as everything else here.
**Mechanism reuse**: `trace.section_fingerprints` (D-29) generalises the single `prose_fingerprint` (D-25) to one fingerprint per `##` section, so *which* section changed is known without ever storing the document's old text — the prompt still reads the actual diff with `git diff`, exactly as `/speckit-eil-approve` already does. A section that holds nothing but record blocks and marked regions (`Reviews`, `Challenges`, `Overrides`, `Quality Assessment`, `Comprehension Check`, `Approval`) is excluded from `section_fingerprints` entirely, so recording a review (or a challenge, or checking a gate) is never itself a "changed section" needing its own review — the alternative (an infinite regress of reviewing the review) was found and fixed in the same session, not designed around in advance.
**Also fixed while building this**: `eil amend`'s item-coverage was self-stage-only (`impact.changed_items` filtered to the stage's own items); it could not amend a stage whose own text never changed, only an upstream item it traces to (exactly the shape D-26 exists for). Coverage is now the union of the stage's own edits and any upstream id in its recorded `upstream_items` whose current hash no longer matches — the same set `state()` uses to decide `needs-re-review` in the first place.
**Alternatives**: A separate "Implementation amendments" section shadowing the changed item (considered from the user's own proposal; rejected: two sources of truth for the same content will drift); a second, AI-classified "mechanical vs substantive" tier with lighter rules for the former (rejected: a human's own diligence per item already scales the rigor; a second, weaker path to the same state is exactly the inconsistency this project avoids elsewhere).

### D-29 A judgment verdict is scoped to its own criterion, not the whole document (FR-102)
**Decision**: `gates.evaluate` computes each judgment criterion's own **basis** — the fingerprint of just the sections `Criterion.headings` names (via `trace.section_fingerprints`), or the whole-document fingerprint for the handful with no named sections (REQ-G12/G13, FUN-G12/G13, TEC-G13/G14, which genuinely read everything). A verdict is kept only while its own basis still matches; the assessment record's `criteria[].basis` field carries it forward. The five free-text assessment lists (ambiguity, missing, …) still gate on the whole-document fingerprint, since a free-text note can reference anything in the document.
**Rationale**: `_prior_judgments` voided **every** judgment verdict on **any** edit anywhere in the document, even though `Criterion.headings` already named exactly what each one reads — a bug, not a missing convenience, found from the same dogfooding session: an edit to one section forced re-judging four criteria that never read it. It also blocked `eil amend`/`eil review finish` from ever completing silently, since those paths never re-ran the full judgment pass; making judgments hold their own scope was the fix that let a reviewed change actually finish without a full re-approval.
**Alternatives**: Leaving the whole-document rule (the status quo, and one of the two remaining large contributors to the reported churn); scoping to the whole item/heading tree instead of exact section content (rejected: `Criterion.headings` already names sections precisely; no coarser unit was needed).
---

## Risks and tests

| ID | Risk | Effect | Mitigation / test |
|----|------|--------|-------------------|
| R-1 | Custom template names may not install or resolve | Nine-document scaffold breaks | Contract test C-03 first; fallback in D-02. **Resolved 2026-09-25: C-03 passes.** A new template name and a core-name override both resolve to the preset file through `resolve-template.sh` and `specify preset resolve`; removal restores core. The D-02 fallback is not needed |
| R-2 | Preset wraps may not fire for skill-invoked commands the way they do for slash commands | Gates silently absent | Contract test C-05 checks the composed `speckit-plan` skill contains the guard; scenario B-06 step 4. **Resolved 2026-09-25: C-05 passes.** The composed `speckit-plan` skill has the guard and the helper call ahead of the core body, and `{CORE_TEMPLATE}` is substituted (F-14). Whether the AI then obeys it is still R-3 |
| R-3 | AI agent ignores the guard instruction | Refusal not applied | Guard is the **first** step and the helper's exit code is the only signal; residual risk documented as attestation-level (D-05) |
| R-4 | Symlinks unavailable (Windows without privilege) | Mirror fallback is the common path there | Mirror logic is first-class and tested (unit U-Alias-*), not an afterthought |
| R-5 | Regex-based ID extraction misses a malformed item | False "no coverage" or missed gap | `check` reports unparsable item lines as findings rather than ignoring them; fixtures include malformed cases |
| R-6 | Two people edit different stage documents in parallel branches | Merge conflict inside a record block | Records are small, append-mostly JSON; conflicts surface in ordinary review. Documented, not automated. |
| R-7 | Fingerprint excludes approval block only; a block edited by hand can forge an approval | Forged approval | Detectable in review (attestation text, name, time in the diff); not preventable (spec assumption) |
| R-8 | `checklist` reading an AI Spec produces poor items (OQ-001) | Lower-value checklist | Wrap adds s01/s02 context (D-13); scenario B-11 evaluates it on a real story |
| R-9 | Constitution is unratified | No principles to check | Reported in the plan; `/speckit-constitution` recommended |
| R-10 | Mermaid's C4 support is marked experimental; syntax may change | Parser rejects valid diagrams | The accepted macro set is a small stated subset, isolated in `diagrams.py`; fixtures pin it; an unrecognised construct is `diagram-unparseable`, and the fallback is a registered image with no structural checks |
| R-11 | Consistency rules are stricter than real diagrams | Legitimate diagram blocks a gate | Every rule is a finding that an authorised person can override with a reason (FR-045); unit fixtures include borderline diagrams |
| R-12 | Figma source changes after export | Approved picture differs from the design | Invisible to the workflow by design (D-19); the record links the exact frame; a fresh export triggers re-review |
| R-13 | AI cannot see an image, or judges a wireframe wrongly | False assurance | Wireframe content review is a `judgment` criterion and a human confirms it (D-21) |
| R-14 | AI misjudges an answer, or the agent records outcomes without asking the human | Comprehension record overstates understanding | Outcomes are only labels; counts of skipped and revealed levels reach the approval record and the overview for the reviewer; the record cannot hold text or a score; attestation-level like D-11 |
| R-15 | Developer skips or reveals every level to get past the criterion | Empty comprehension | Allowed by design (user decision); visible as `skipped 5` in the overview and pull request diff |

## Outcome

All Technical Context fields are resolved. No `NEEDS CLARIFICATION` markers remain.
