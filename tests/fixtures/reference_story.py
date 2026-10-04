"""The reference story (T002; B-27, SC-001): a package approved through tasks.

4 REQ, 3 UC, 12 FR (and NFR-001), 5 DEC, 8 ART, AIS items that trace to them, plan sections that trace
to the decisions, tasks T001 to T012 (T001 to T006 ticked with a code reference) and the s07 evidence rows.
"""

from __future__ import annotations

from pathlib import Path

from tests.helpers.package import (
    TECHNICAL_SEQUENCE,
    Story,
    ai_spec_doc,
    approve_stages,
    evidence_row,
    export_record,
    functional_doc,
    mermaid,
    plan_doc,
    requirements_doc,
    tasks_doc,
    technical_doc,
    verification_doc,
    write_export,
)

REQUIREMENTS = {
    "Desired Outcome": "\n\n".join(
        f"**REQ-{n:03d}**: {text}"
        for n, text in enumerate(
            [
                "The system detects duplicate customers on import.",
                "Analysts can review each flagged pair.",
                "Analysts can merge or dismiss a flagged pair.",
                "Every decision on a pair is auditable.",
            ],
            1,
        )
    ),
    "Use Cases": "\n\n".join(
        f"**UC-{n:03d}**: {text} (actor: Data Analyst; goal: {goal})"
        for n, (text, goal) in enumerate(
            [
                ("Analyst reviews a flagged duplicate", "merge or dismiss"),
                ("Analyst dismisses a false positive", "clear the flag"),
                ("Auditor reads the decision history", "verify decisions"),
            ],
            1,
        )
    ),
}

_FR_TRACES = ["REQ-001", "REQ-001", "REQ-001", "REQ-002", "REQ-002", "REQ-002", "REQ-003", "REQ-003", "REQ-003", "REQ-004", "REQ-004", "REQ-004"]  # fmt: skip
FUNCTIONAL = {
    "Functional Requirements": "\n\n".join(
        f"**FR-{n:03d}**: The system shall support behaviour {n} of duplicate analysis. (traces: {req})"
        for n, req in enumerate(_FR_TRACES, 1)
    ),
    "Requirements Traceability": "Every REQ is satisfied by the FR items that trace to it.",
}

DECISIONS = "\n\n".join(
    f"**DEC-{n:03d}**: {title} (traces: FR-{n:03d}, NFR-001)\n"
    f"Decision: {title}.\nReason: Reason for decision {n}.\nRejected alternative: Alternative {n}.\n"
    f"Trade-off: Trade-off {n}.\nOwner: Ada Dev"
    for n, title in enumerate(
        [
            "Use asynchronous processing",
            "Store matches in the customer database",
            "Queue work per import file",
            "Retry failed analyses three times",
            "Log every decision to an audit table",
        ],
        1,
    )
)

_AIS_TRACES = [f"FR-{n:03d}" for n in range(1, 13)] + [f"DEC-{n:03d}" for n in range(2, 6)] + ["NFR-001", "ART-004", "ART-007"]  # fmt: skip
AI_SPEC = {
    "Functional Requirements": "\n\n".join(
        f"**AIS-{n:03d}**: Implement behaviour {n}. (traces: {t})" for n, t in enumerate(_AIS_TRACES[:12], 1)
    ),
    "Business Rules": "\n\n".join(
        f"**AIS-{n:03d}**: Follow decision rule {n}. (traces: {t})"
        for n, t in enumerate(_AIS_TRACES[12:16], 13)
    ),
    "Testing Requirements": "**AIS-017**: Integration test through the queue. (traces: NFR-001)",
    "Artefacts in Scope": (
        "**AIS-018**: Read the container view before changing the API. (traces: ART-004)\n\n"
        "**AIS-019**: Follow the duplicate match schema. (traces: ART-007)"
    ),
    **dict.fromkeys(
        [
            "Technical Decisions", "Architectural Constraints", "Existing Code", "Interfaces",
            "Data Structures", "Security Requirements", "Edge Cases", "Explicit Exclusions",
            "Implementation Constraints",
        ]
    ),
}  # fmt: skip

PLAN = {
    f"{title} (traces: DEC-{n:03d})": f"{title} follows decision {n}."
    for n, title in enumerate(
        ["Summary", "Technical Context", "Project Structure", "Queue Design", "Audit Design"], 1
    )
}

TASKS = [
    f"- [{'x' if n <= 6 else ' '}] T{n:03d} Build part {n} in src/part{n}.py (traces: AIS-{n:03d})"
    + (f" (code: {n:07x}a)" if n <= 6 else "")
    for n in range(1, 13)
]

EVIDENCE_TARGETS = [
    "REQ-001",
    "REQ-002",
    "FR-001",
    "FR-002",
    "FR-003",
    "NFR-001",
    "ART-001",
    "ART-004",
    "ART-007",
]


def build(root: Path) -> Story:
    """Write and approve the reference story at ``root`` (created if absent)."""
    story = Story(root)
    story.write("requirements", requirements_doc(REQUIREMENTS))
    story.write(
        "functional",
        functional_doc(FUNCTIONAL, wireframe=export_record(sha256=write_export(story.root))),
    )
    technical = technical_doc({"Technical Decisions": DECISIONS})
    art8 = (
        "**ART-008**: Audit trail (traces: DEC-005)\n\n" + mermaid(TECHNICAL_SEQUENCE).rstrip("\n") + "\n\n"
    )
    technical = technical.replace("## Data Model", "## Audit Flow\n\n" + art8 + "## Data Model", 1)
    story.write("technical", technical)
    approve_stages(story, "requirements", "functional", "technical")
    story.write("ai-spec", ai_spec_doc(AI_SPEC))
    story.write("plan", plan_doc(PLAN))
    story.write("tasks", tasks_doc(TASKS))
    rows = [evidence_row(n, t) for n, t in enumerate(EVIDENCE_TARGETS, 1)]
    story.write("verification", verification_doc(rows, open_tasks=[f"T{n:03d}" for n in range(7, 13)]))
    return story
