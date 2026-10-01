"""Build story-package fixtures for unit and scenario tests (task T007).

A ``Story`` writes a governed feature directory (``s00`` to ``s08`` documents) into a temp
directory. Documents are plain text so tests state exactly what they mean; the helpers only
add the machine-readable pieces (regions and record blocks) in the documented format.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DOC_NAMES = {
    "overview": "s00-README.md",
    "requirements": "s01-requirements.md",
    "functional": "s02-functional-spec.md",
    "technical": "s03-technical-spec.md",
    "ai-spec": "s04-ai-spec.md",
    "plan": "s05-plan.md",
    "tasks": "s06-tasks.md",
    "verification": "s07-verification.md",
    "completion": "s08-completion.md",
}


def item_hashes(text: str, stage: str = "requirements") -> dict[str, str]:
    """``{item.id: item_hash(item)}`` for every item in ``text``, attachments included — the same
    shape ``records.approve`` records, for fixtures that hand-build an approval record."""
    from eil.artifacts import scan_document
    from eil.blocks import Doc
    from eil.trace import item_hash, parse_document

    doc = Doc(text)
    parsed = parse_document(doc)
    scan_document(doc, stage, parsed)
    return {item.id: item_hash(item) for item in parsed.items}


def region(name: str, obj: Any) -> str:
    """A marked region (``approval``, ``assessment``, ``comprehension`` or ``provenance``) holding JSON."""
    body = json.dumps(obj, indent=2, ensure_ascii=False)
    return f"<!-- eil:begin {name} -->\n```json\n{body}\n```\n<!-- eil:end {name} -->\n"


def record_block(kind: str, obj: Any) -> str:
    """A fenced ``eil:<kind>`` record block holding one JSON object."""
    return f"```eil:{kind}\n{json.dumps(obj, ensure_ascii=False)}\n```\n"


def mermaid(text: str) -> str:
    return f"```mermaid\n{text.strip()}\n```\n"


def item(item_id: str, text: str, traces: list[str] | None = None, extra: str = "") -> str:
    """An item line in the documented grammar."""
    clause = f" (traces: {', '.join(traces)})" if traces else ""
    return f"**{item_id}**: {text}{clause}{extra}\n"


class Story:
    """A governed story directory under ``root``."""

    def __init__(self, root: Path, title: str = "Duplicate customer analysis") -> None:
        self.root = root
        self.title = title
        root.mkdir(parents=True, exist_ok=True)
        notice = "<!-- eil:generated — edit the stage documents, not this file -->"
        self.write("overview", f"{notice}\n# {title}\n")

    def path(self, stage: str) -> Path:
        return self.root / DOC_NAMES[stage]

    def write(self, stage: str, text: str) -> Path:
        path = self.path(stage)
        path.write_text(text, encoding="utf-8", newline="\n")
        return path

    def read(self, stage: str) -> str:
        return self.path(stage).read_text(encoding="utf-8")

    def append(self, stage: str, text: str) -> None:
        with self.path(stage).open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(text)

    def exists(self, stage: str) -> bool:
        return self.path(stage).exists()


# ---- a complete, valid Requirements document (task T031 and later)

CONTEXT_DIAGRAM = """C4Context
  Person(analyst, "Data Analyst", "[existing] Reviews duplicates")
  System(platform, "Customer Platform", "[changed] Detects duplicates on import")
  System_Ext(crm, "CRM", "[existing] Customer store")
  Rel(analyst, platform, "Reviews duplicates")
  Rel(platform, crm, "Reads customers")"""

REQUIREMENTS_SECTIONS: dict[str, str] = {
    "Background": "Imports create duplicate customers.",
    "Problem Statement": "Analysts merge duplicates by hand, which is slow.",
    "Desired Outcome": "**REQ-001**: The system detects duplicate customers on import.",
    "Users and Stakeholders": "- **Data Analyst**: reviews flagged duplicates",
    "Use Cases": "**UC-001**: Analyst reviews a flagged duplicate (actor: Data Analyst; goal: merge or dismiss).",
    "In Scope": "Detection on import.",
    "Out of Scope": "Merging rules.",
    "Constraints": "Must run inside the nightly import window.",
    "Dependencies": "- **CRM**: the existing customer store",
    "Risks": "False positives annoy analysts.",
    "Assumptions": "Customer IDs are stable.",
    "Open Questions": "**OQ-001**: Keep history? (status: resolved) (material: yes)",
    "Success Criteria": "Duplicates are flagged within one import run.",
}

_HEADING_LEVELS = {"In Scope": 3, "Out of Scope": 3}


def requirements_doc(
    sections: dict[str, str | None] | None = None,
    *,
    diagram: str | None = CONTEXT_DIAGRAM,
    not_applicable: str = "",
    extra: str = "",
    approval: dict[str, Any] | None = None,
) -> str:
    """A complete Requirements document. ``sections`` overrides a section's body; ``None`` drops
    the section entirely and ``""`` leaves it present but empty."""
    merged = {**REQUIREMENTS_SECTIONS, **(sections or {})}
    lines = ["# Requirements: Duplicate customer analysis", ""]
    order = [
        "Background",
        "Problem Statement",
        "Desired Outcome",
        "Users and Stakeholders",
        "Use Cases",
        "Scope",
        "In Scope",
        "Out of Scope",
        "Constraints",
        "Dependencies",
        "Risks",
        "Assumptions",
        "Open Questions",
        "Success Criteria",
    ]
    for name in order:
        if name == "Scope":
            lines += ["## Scope", ""]
            continue
        body = merged.get(name)
        if body is None:
            continue
        hashes = "#" * _HEADING_LEVELS.get(name, 2)
        lines += [f"{hashes} {name}", "", body, ""] if body else [f"{hashes} {name}", ""]
    if diagram is not None:
        lines += [
            "## System Context",
            "",
            "**ART-001**: System context (traces: REQ-001)",
            "",
            mermaid(diagram).rstrip("\n"),
            "",
        ]
    lines += ["## Not applicable", ""]
    if not_applicable:
        lines += [not_applicable, ""]
    lines += ["## Challenges", "", "## Overrides", ""]
    if extra:
        lines += [extra, ""]
    lines += ["## Quality Assessment", "", "<!-- eil:begin assessment -->", "<!-- eil:end assessment -->", ""]
    lines += ["## Approval", "", "<!-- eil:begin approval -->", "<!-- eil:end approval -->", ""]
    text = "\n".join(lines)
    if approval is not None:
        text = text.replace(
            "<!-- eil:begin approval -->\n<!-- eil:end approval -->",
            region("approval", approval).rstrip("\n"),
        )
    return text


# ---- a complete, valid Functional Specification (task T058 and later)

ASSETS_FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "assets"
FIGMA_URL = "https://www.figma.com/design/AbC123/Duplicates?node-id=12-345"

SEQUENCE_DIAGRAM = """sequenceDiagram
  actor Analyst as Data Analyst
  participant System
  Analyst->>System: Upload customer file
  System-->>Analyst: Flag duplicate matches
  alt no duplicates found
    System-->>Analyst: Report a clean import
  end"""

FUNCTIONAL_SECTIONS: dict[str, str] = {
    "Requirements Traceability": "REQ-001 is satisfied by FR-001 and NFR-001.",
    "Actors": "- **Data Analyst**: reviews flagged duplicates",
    "Functional Requirements": "**FR-001**: The system shall flag duplicate customers on import. (traces: REQ-001)",
    "Use Cases and Scenarios": "Scenario for UC-001: the analyst uploads a file and reviews the flagged matches.",
    "Business Rules": "Two customers with the same tax id are duplicates.",
    "Inputs": "A CSV file of customers.",
    "Outputs": "A list of flagged pairs.",
    "State and Workflow": "A pair is flagged, then confirmed or dismissed.",
    "Validation": "Files over 10 MB are rejected.",
    "Error and Exception Behaviour": "A malformed row is skipped and reported.",
    "Security and Access Behaviour": "Only analysts can review matches.",
    "Audit and Compliance Behaviour": "Every dismissal is logged.",
    "Non-Functional Requirements": "**NFR-001**: A 10 MB import completes within 60 seconds. (traces: REQ-001)",
    "Acceptance Criteria": "Given a file with a known duplicate, the pair is flagged.",
}
_FUNCTIONAL_ORDER = list(FUNCTIONAL_SECTIONS)


def export_bytes(name: str = "wireframe.png") -> bytes:
    return (ASSETS_FIXTURES / name).read_bytes()


def write_export(root: Path, name: str = "duplicate-review.png", source: str = "wireframe.png") -> str:
    """Put a sample export into ``<root>/assets`` and return its ``sha256:`` (raw bytes)."""
    import hashlib

    data = export_bytes(source)
    (root / "assets").mkdir(exist_ok=True)
    (root / "assets" / name).write_bytes(data)
    return "sha256:" + hashlib.sha256(data).hexdigest()


def export_record(name: str = "duplicate-review.png", sha256: str = "", **overrides: Any) -> dict[str, Any]:
    record: dict[str, Any] = {
        "file": f"assets/{name}",
        "sha256": sha256,
        "kind": "wireframe",
        "source": {"tool": "figma", "url": FIGMA_URL, "exported_at": "2026-09-25", "exported_by": "Ada Dev"},
    }
    record.update(overrides)
    return record


def functional_doc(
    sections: dict[str, str | None] | None = None,
    *,
    sequence: str | None = SEQUENCE_DIAGRAM,
    sequence_traces: str = "UC-001, FR-001",
    wireframe: dict[str, Any] | None = None,
    not_applicable: str = "",
    extra: str = "",
    comprehension: dict[str, Any] | None = None,
) -> str:
    """A complete Functional Specification. ``wireframe`` is an export record (see ``export_record``);
    ``None`` leaves the Wireframes section without one."""
    merged = {**FUNCTIONAL_SECTIONS, **(sections or {})}
    lines = ["# Functional Specification: Duplicate customer analysis", ""]
    for name in _FUNCTIONAL_ORDER:
        body = merged.get(name)
        if body is None:
            continue
        lines += [f"## {name}", "", body, ""] if body else [f"## {name}", ""]
    lines += ["## Sequence Diagrams", ""]
    if sequence is not None:
        lines += [
            f"**ART-002**: Analyst reviews duplicates (traces: {sequence_traces})",
            "",
            mermaid(sequence).rstrip("\n"),
            "",
        ]
    lines += ["## Wireframes", ""]
    if wireframe is not None:
        lines += [
            "**ART-003**: Duplicate review screen (traces: FR-001, UC-001)",
            "",
            record_block("artifact", wireframe).rstrip("\n"),
            "",
        ]
    lines += ["## Not applicable", ""]
    if not_applicable:
        lines += [not_applicable, ""]
    lines += ["## Challenges", "", "## Overrides", ""]
    if extra:
        lines += [extra, ""]
    lines += [
        "## Comprehension Check",
        "",
        "<!-- eil:begin comprehension -->",
        "<!-- eil:end comprehension -->",
        "",
    ]
    lines += ["## Quality Assessment", "", "<!-- eil:begin assessment -->", "<!-- eil:end assessment -->", ""]
    lines += ["## Approval", "", "<!-- eil:begin approval -->", "<!-- eil:end approval -->", ""]
    text = "\n".join(lines)
    if comprehension is not None:
        text = text.replace(
            "<!-- eil:begin comprehension -->\n<!-- eil:end comprehension -->",
            region("comprehension", comprehension).rstrip("\n"),
        )
    return text


def with_functional(story: Story, **kwargs: Any) -> str:
    """Write a valid ``s01`` and a Functional document (with a real export unless ``wireframe`` is given)."""
    story.write("requirements", requirements_doc())
    if "wireframe" not in kwargs:
        kwargs["wireframe"] = export_record(sha256=write_export(story.root))
    text = functional_doc(**kwargs)
    story.write("functional", text)
    return text


# ---- a complete, valid Technical Specification (task T074 and later)

CONTAINER_DIAGRAM = """C4Container
  Person(analyst, "Data Analyst", "[existing] Reviews duplicates")
  System_Ext(crm, "CRM", "[existing] Customer store")
  System_Boundary(platform, "Customer Platform") {
    Container(api, "Import API", "REST", "[existing] Accepts imports")
    Container(worker, "Duplicate Worker", "Python", "[new] Analyses duplicates")
    ContainerDb(db, "Customer DB", "PostgreSQL", "[existing] Customer records")
  }
  Rel(analyst, api, "Uploads files")
  Rel(api, worker, "Queues analysis")
  Rel(worker, db, "Reads and writes")
  Rel(api, crm, "Reads customers")"""

COMPONENT_DIAGRAM = """C4Component
  ContainerDb(db, "Customer DB", "PostgreSQL", "[existing] Customer records")
  Container_Boundary(worker, "Duplicate Worker") {
    Component(matcher, "Matcher", "Python", "[new] Compares customers")
    Component(results, "Result Store", "Python", "[new] Saves matches")
    Rel(matcher, results, "Hands matches to")
    Rel(results, db, "Writes")
  }"""

TECHNICAL_SEQUENCE = """sequenceDiagram
  actor Analyst as Data Analyst
  participant API as Import API
  participant Worker as Duplicate Worker
  participant DB as Customer DB
  Analyst->>API: Upload file
  API->>Worker: Queue analysis
  Worker->>DB: Store matches"""

ER_DIAGRAM = """erDiagram
  CUSTOMER ||--o{ DUPLICATE_MATCH : "has\""""

DECISION = """**DEC-001**: Use asynchronous processing (traces: FR-001, NFR-001)
Decision: Duplicate analysis runs asynchronously in a worker.
Reason: A 10 MB import can exceed the synchronous latency limit.
Rejected alternative: Analyse inside the import request.
Trade-off: Results are not available to the caller straight away.
Owner: Ada Dev"""

TECHNICAL_SECTIONS: dict[str, str] = {
    "Technical Requirements": "Analysis of a 10 MB file finishes within 60 seconds (NFR-001).",
    "Architecture": "The import API queues work for a worker that analyses it.",
    "Component Design": "The worker has a matcher and a result store.",
    "Data Design": "A DUPLICATE_MATCH table is added to the customer database.",
    "API and Integration Design": "The import API adds a status endpoint; the CRM is read only.",
    "Security Design": "Workers use a service account with read access to customers.",
    "Error Handling and Resilience": "Failed analyses retry three times; the job is idempotent on file id.",
    "Observability": "Each analysis logs its duration and match count.",
    "Performance": "Ten concurrent imports are expected at month end.",
    "Testing Strategy": "Unit tests for the matcher, an integration test through the queue.",
    "Deployment and Migration": "Deploy the worker first, then the API; the migration is additive.",
    "Existing System Impact": "The customer database gains one table.",
    "Alternatives Considered": "Synchronous analysis was rejected (DEC-001).",
    "Risks and Trade-offs": "Analysts wait for results; the queue is a new failure point.",
    "Technical Decisions": DECISION,
}
_TECHNICAL_ORDER = list(TECHNICAL_SECTIONS)


def technical_doc(
    sections: dict[str, str | None] | None = None,
    *,
    container: str | None = CONTAINER_DIAGRAM,
    components: str | None = COMPONENT_DIAGRAM,
    sequence: str | None = TECHNICAL_SEQUENCE,
    sequence_traces: str = "UC-001, DEC-001",
    er: str | None = ER_DIAGRAM,
    er_store: str | None = "Customer DB",
    not_applicable: str = "",
    extra: str = "",
    comprehension: dict[str, Any] | None = None,
) -> str:
    """A complete Technical Specification. A diagram argument of ``None`` leaves that section without one."""
    merged = {**TECHNICAL_SECTIONS, **(sections or {})}
    lines = ["# Technical Specification: Duplicate customer analysis", ""]
    for name in _TECHNICAL_ORDER:
        body = merged.get(name)
        if body is None:
            continue
        lines += [f"## {name}", "", body, ""] if body else [f"## {name}", ""]
    lines += ["## Container View", ""]
    if container is not None:
        lines += [
            "**ART-004**: Containers of the platform (traces: FR-001, DEC-001)",
            "",
            mermaid(container).rstrip("\n"),
            "",
        ]
    lines += ["## Component Views", ""]
    if components is not None:
        lines += [
            "**ART-005**: Inside the duplicate worker (traces: FR-001, DEC-001)",
            "",
            mermaid(components).rstrip("\n"),
            "",
        ]
    lines += ["## Sequence Diagrams", ""]
    if sequence is not None:
        lines += [
            f"**ART-006**: Asynchronous analysis (traces: {sequence_traces})",
            "",
            mermaid(sequence).rstrip("\n"),
            "",
        ]
    lines += ["## Data Model", ""]
    if er is not None:
        store = f" (store: {er_store})" if er_store else ""
        lines += [
            f"**ART-007**: Duplicate match data (traces: DEC-001){store}",
            "",
            mermaid(er).rstrip("\n"),
            "",
        ]
    lines += ["## Not applicable", ""]
    if not_applicable:
        lines += [not_applicable, ""]
    lines += ["## Challenges", "", "## Overrides", ""]
    if extra:
        lines += [extra, ""]
    lines += [
        "## Comprehension Check",
        "",
        "<!-- eil:begin comprehension -->",
        "<!-- eil:end comprehension -->",
        "",
    ]
    lines += ["## Quality Assessment", "", "<!-- eil:begin assessment -->", "<!-- eil:end assessment -->", ""]
    lines += ["## Approval", "", "<!-- eil:begin approval -->", "<!-- eil:end approval -->", ""]
    text = "\n".join(lines)
    if comprehension is not None:
        text = text.replace(
            "<!-- eil:begin comprehension -->\n<!-- eil:end comprehension -->",
            region("comprehension", comprehension).rstrip("\n"),
        )
    return text


def with_technical(story: Story, functional: dict[str, Any] | None = None, **kwargs: Any) -> str:
    """Write valid ``s01`` and ``s02`` documents (``functional`` overrides how ``s02`` is built) and a
    Technical document."""
    with_functional(story, **(functional or {}))
    text = technical_doc(**kwargs)
    story.write("technical", text)
    return text


# ---- approvals written the way ``eil approve`` writes them, without running the gates

DEFINITION_STAGE_ORDER = ("requirements", "functional", "technical")


def approve_stages(story: Story, *stages: str, by: str = "Ada Dev") -> None:
    """Record an approval in each stage document (in the order given), as ``records.approve`` shapes it:
    the fingerprint, the fingerprints of the earlier stages, the hash of every item, its section
    fingerprints, and the current hash of everything it traces to upstream."""
    from eil import impact
    from eil.artifacts import scan_document
    from eil.blocks import Doc, write_region
    from eil.fingerprint import fingerprint_text
    from eil.package import Package
    from eil.trace import item_hash, parse_document, section_fingerprints

    package = Package(story.root)
    for stage in stages:
        text = story.read(stage)
        if "approval" not in Doc(text).regions:
            text = write_region(text, "approval", {}, heading="## Approval")
        doc = Doc(text, path=DOC_NAMES[stage])
        parsed = parse_document(doc)
        scan_document(doc, stage, parsed)
        all_parsed = impact.parsed_story(package)
        all_parsed[stage] = parsed
        record = {
            "stage": stage,
            "by": by,
            "at": "2026-09-25T00:00:00Z",
            "fingerprint": fingerprint_text(text),
            "attestation": "Yes.",
            "upstream": {
                earlier: fp
                for earlier in DEFINITION_STAGE_ORDER
                if DEFINITION_STAGE_ORDER.index(earlier) < DEFINITION_STAGE_ORDER.index(stage)
                and (fp := package.fingerprint(earlier))
            },
            "items": {item.id: item_hash(item) for item in parsed.items},
            "section_fingerprints": section_fingerprints(doc, parsed.items),
            "upstream_items": impact.upstream_item_hashes(package, stage, all_parsed),
            "overrides_used": [],
        }
        story.write(stage, write_region(text, "approval", record))


# ---- a complete, valid AI Specification (task T084 and later)

AIS_SECTIONS: dict[str, str] = {
    "Functional Requirements": "**AIS-001**: Flag duplicate customers on import. (traces: FR-001)",
    "Business Rules": "**AIS-002**: Two customers with the same tax id are duplicates. (traces: FR-001)",
    "Technical Decisions": "**AIS-003**: Analysis runs asynchronously in a worker. (traces: DEC-001)",
    "Architectural Constraints": "**AIS-004**: The import API only queues work. (traces: DEC-001)",
    "Existing Code": "**AIS-005**: Reuse the CSV importer in the API. (traces: FR-001)",
    "Interfaces": "**AIS-006**: The API adds a status endpoint. (traces: DEC-001)",
    "Data Structures": "**AIS-007**: A DUPLICATE_MATCH table holds the matches. (traces: DEC-001)",
    "Testing Requirements": "**AIS-008**: Integration test through the queue. (traces: NFR-001)",
    "Security Requirements": "**AIS-009**: Workers read customers only. (traces: DEC-001)",
    "Edge Cases": "**AIS-010**: A malformed row is skipped and reported. (traces: FR-001)",
    "Explicit Exclusions": "**AIS-011**: No merge rules are implemented. (traces: REQ-001)",
    "Implementation Constraints": "**AIS-012**: A 10 MB import finishes in 60 seconds. (traces: NFR-001)",
    "Artefacts in Scope": (
        "**AIS-013**: Read the container view before changing the API. (traces: ART-004)\n\n"
        "**AIS-014**: Follow the duplicate match schema. (traces: ART-007)\n\n"
        "**AIS-015**: Follow the asynchronous analysis sequence. (traces: ART-006)"
    ),
}
_AIS_ORDER = list(AIS_SECTIONS)


def ai_spec_doc(
    sections: dict[str, str | None] | None = None, *, extra: str = "", not_applicable: str = ""
) -> str:
    """A complete AI Specification. ``sections`` overrides a section's body; ``None`` drops it."""
    merged = {**AIS_SECTIONS, **(sections or {})}
    lines = ["# AI Specification: Duplicate customer analysis", ""]
    for name in _AIS_ORDER:
        body = merged.get(name)
        if body is None:
            continue
        lines += [f"## {name}", "", body, ""] if body else [f"## {name}", ""]
    for name, body in merged.items():
        if name not in AIS_SECTIONS and body is not None:
            lines += [f"## {name}", "", body, ""]
    lines += ["## Not applicable", ""]
    if not_applicable:
        lines += [not_applicable, ""]
    lines += ["## Challenges", "", "## Overrides", ""]
    if extra:
        lines += [extra, ""]
    lines += ["## Quality Assessment", "", "<!-- eil:begin assessment -->", "<!-- eil:end assessment -->", ""]
    lines += ["## Approval", "", "<!-- eil:begin approval -->", "<!-- eil:end approval -->", ""]
    return "\n".join(lines)


def with_approved_chain(story: Story) -> None:
    """A story whose Requirements, Functional and Technical documents are all approved."""
    with_technical(story)
    approve_stages(story, *DEFINITION_STAGE_ORDER)


def with_ai_spec(story: Story, **kwargs: Any) -> str:
    with_approved_chain(story)
    text = ai_spec_doc(**kwargs)
    story.write("ai-spec", text)
    return text


# ---- a plan and a task list (task T085 and later)

PLAN_SECTIONS: dict[str, str] = {
    "Summary (traces: DEC-001)": "Analysis runs asynchronously in a worker behind the import API.",
    "Technical Context (traces: DEC-001)": "Python 3.11, PostgreSQL, a queue.",
    "Project Structure (traces: DEC-001)": "A worker package beside the API.",
}


def plan_doc(
    sections: dict[str, str | None] | None = None, *, extra: str = "", not_applicable: str = ""
) -> str:
    merged = {**PLAN_SECTIONS, **(sections or {})}
    lines = ["# Implementation Plan: Duplicate customer analysis", "", "**Branch**: `001-duplicates`", ""]
    for name, body in merged.items():
        if body is not None:
            lines += [f"## {name}", "", body, ""]
    lines += ["## Not applicable", ""]
    if not_applicable:
        lines += [not_applicable, ""]
    lines += ["## Challenges", "", "## Overrides", ""]
    if extra:
        lines += [extra, ""]
    lines += ["## Quality Assessment", "", "<!-- eil:begin assessment -->", "<!-- eil:end assessment -->", ""]
    return "\n".join(lines)


TASK_LINES: list[str] = [
    "- [ ] T001 Create the worker package in src/worker/__init__.py (traces: AIS-003)",
    "- [ ] T002 Add the status endpoint in src/api/status.py (traces: AIS-006)",
    "- [ ] T003 Add the DUPLICATE_MATCH migration in migrations/001.sql (traces: AIS-014)",
    "- [ ] T004 Queue the analysis from the import handler in src/api/imports.py (traces: AIS-015)",
]


def tasks_doc(tasks: list[str] | None = None, *, extra: str = "", not_applicable: str = "") -> str:
    lines = ["# Tasks: Duplicate customer analysis", "", "## Phase 1: Build", ""]
    lines += TASK_LINES if tasks is None else tasks
    lines += ["", "## Not applicable", ""]
    if not_applicable:
        lines += [not_applicable, ""]
    lines += ["## Challenges", "", "## Overrides", ""]
    if extra:
        lines += [extra, ""]
    lines += ["## Quality Assessment", "", "<!-- eil:begin assessment -->", "<!-- eil:end assessment -->", ""]
    return "\n".join(lines)


def with_plan_and_tasks(story: Story, **kwargs: Any) -> None:
    with_ai_spec(story, **kwargs)
    story.write("plan", plan_doc())
    story.write("tasks", tasks_doc())


# ---- verification and completion documents (task T108 and later)

VERIFY_TARGETS = [
    "REQ-001",
    "FR-001",
    "NFR-001",
    "ART-001",
    "ART-002",
    "ART-003",
    "ART-004",
    "ART-005",
    "ART-006",
    "ART-007",
]
DEFAULT_OPEN_TASKS = ["T001", "T002", "T003", "T004"]


def evidence_row(
    number: int,
    target: str,
    status: str = "verified",
    kind: str | None = None,
    evidence: str | None = None,
    accepted_by: str | None = None,
    reason: str | None = None,
    code: str = "",
) -> str:
    """One ``EVD`` row: its status clause and labelled fields."""
    kind = kind or ("manual" if target.startswith("ART") else "automated")
    lines = [f"**EVD-{number:03d}**: Evidence for {target} (traces: {target}) (status: {status}){code}"]
    if status in ("verified", "failed"):
        lines += [f"Kind: {kind}", f"Evidence: {evidence or 'tests/test_import.py::test_flags_duplicates'}"]
    if accepted_by is not None:
        lines.append(f"Accepted by: {accepted_by}")
    if reason is not None:
        lines.append(f"Reason: {reason}")
    return "\n".join(lines)


def verification_doc(
    rows: list[str] | None = None,
    *,
    open_tasks: list[str] | None = None,
    sections: dict[str, str | None] | None = None,
    extra: str = "",
) -> str:
    """A complete Verification document: a verified row for every default target unless ``rows`` is given."""
    rows = rows if rows is not None else [evidence_row(i, t) for i, t in enumerate(VERIFY_TARGETS, 1)]

    def is_exception(row: str) -> bool:
        return "(status: excepted)" in row or "(status: unverified)" in row

    def is_failed(row: str) -> bool:
        return "(status: failed)" in row

    manual = [r for r in rows if "Kind: manual" in r and not is_exception(r) and not is_failed(r)]
    exceptions = [r for r in rows if is_exception(r)]
    failed = [r for r in rows if is_failed(r)]
    automated = [r for r in rows if r not in manual and r not in exceptions and r not in failed]
    merged: dict[str, str | None] = {
        "Automated Evidence": "\n\n".join(automated) or "None recorded.",
        "Manual Evidence": "\n\n".join(manual) or "None recorded.",
        "Exceptions": "\n\n".join(exceptions) or "None.",
        "Failed Evidence": "\n\n".join(failed) or "None.",
        "Open Tasks": ", ".join(open_tasks if open_tasks is not None else DEFAULT_OPEN_TASKS) or "None.",
        **(sections or {}),
    }
    lines = ["# Verification: Duplicate customer analysis", ""]
    for name, body in merged.items():
        if body is not None:
            lines += [f"## {name}", "", body, ""]
    lines += ["## Not applicable", ""]
    lines += ["## Challenges", "", "## Overrides", ""]
    if extra:
        lines += [extra, ""]
    lines += ["## Quality Assessment", "", "<!-- eil:begin assessment -->", "<!-- eil:end assessment -->", ""]
    return "\n".join(lines)


CURRENCY_TARGETS = ["ART-001", "ART-002", "ART-003", "ART-004", "ART-005", "ART-006", "ART-007"]

COMPLETION_SECTIONS: dict[str, str] = {
    "Completion Status": "Complete: every requirement is verified.",
    "Implementation Summary": "The import queues analysis for a worker.",
    "Requirements Satisfied": "REQ-001 is satisfied by FR-001 and NFR-001.",
    "Outstanding Issues": "None.",
    "Accepted Deviations": "None.",
    "Relevant Technical Decisions": "DEC-001: asynchronous processing.",
    "Verification Summary": "Every item is verified; see the verification document.",
    "Deployment Status": "Deployed to staging.",
    "Documentation and Support Implications": "The runbook gains a queue section.",
    "Diagram Currency": "\n".join(f"- {art}: current" for art in CURRENCY_TARGETS),
}


def completion_doc(
    sections: dict[str, str | None] | None = None, *, extra: str = "", not_applicable: str = ""
) -> str:
    merged = {**COMPLETION_SECTIONS, **(sections or {})}
    lines = ["# Completion: Duplicate customer analysis", ""]
    for name, body in merged.items():
        if body is not None:
            lines += [f"## {name}", "", body, ""] if body else [f"## {name}", ""]
    lines += ["## Not applicable", ""]
    if not_applicable:
        lines += [not_applicable, ""]
    lines += ["## Challenges", "", "## Overrides", ""]
    if extra:
        lines += [extra, ""]
    lines += ["## Quality Assessment", "", "<!-- eil:begin assessment -->", "<!-- eil:end assessment -->", ""]
    lines += ["## Approval", "", "<!-- eil:begin approval -->", "<!-- eil:end approval -->", ""]
    return "\n".join(lines)


def with_verification(story: Story, rows: list[str] | None = None, **kwargs: Any) -> None:
    with_plan_and_tasks(story)
    story.write("verification", verification_doc(rows, **kwargs))


# ---- 002: provenance and change-log regions, review findings (T004)

RECORD_HEADINGS = ("## Change Log", "## Record")


def provenance_region(obj: dict[str, Any]) -> str:
    """A ``provenance`` region holding ``obj`` as JSON."""
    return region("provenance", obj)


def changelog_region(rows: list[str] | None = None) -> str:
    """A ``changelog`` region: a generated Markdown table (never parsed), or markers only."""
    body = ""
    if rows:
        header = "| Date | Item | Change (AI-drafted, accepted as shown) | Found in | Accepted by |\n|---|---|---|---|---|\n"
        body = header + "\n".join(rows) + "\n"
    return f"<!-- eil:begin changelog -->\n{body}<!-- eil:end changelog -->\n"


def with_record_sections(text: str, provenance: dict[str, Any] | None = None, changelog: list[str] | None = None) -> str:
    """Insert ``## Change Log`` and ``## Record`` (with their regions) before the first
    ``## Comprehension Check`` or ``## Quality Assessment``, or at the end."""
    block = (
        "## Change Log\n\n"
        + changelog_region(changelog)
        + "\n## Record\n\n"
        + (provenance_region(provenance) if provenance is not None else "<!-- eil:begin provenance -->\n<!-- eil:end provenance -->\n")
        + "\n"
    )
    positions = [p for p in (text.find("## Comprehension Check"), text.find("## Quality Assessment")) if p >= 0]
    if not positions:
        return text.rstrip("\n") + "\n\n" + block
    at = min(positions)
    return text[:at] + block + text[at:]


def block_entry(text_hash: str, klass: str = "inferred", **fields: Any) -> dict[str, Any]:
    """One ``blocks.<key>`` entry of a provenance record."""
    return {"hash": text_hash, "class": klass, **fields}


def rf_row(
    number: int,
    text: str = "Handler ignores the tenant filter",
    status: str = "open",
    root: str = "implementation",
    accepted_by: str | None = None,
    reason: str | None = None,
    traces: list[str] | None = None,
) -> str:
    """One ``RF`` (review finding) item with its labelled lines."""
    clause = f" (traces: {', '.join(traces)})" if traces else ""
    lines = [f"**RF-{number:03d}**: {text}{clause} (status: {status})", f"Root: {root}"]
    if accepted_by is not None:
        lines.append(f"Accepted by: {accepted_by}")
    if reason is not None:
        lines.append(f"Reason: {reason}")
    return "\n".join(lines)
