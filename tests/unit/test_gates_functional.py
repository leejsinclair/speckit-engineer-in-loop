"""The Functional gate (task T058; FR-019, FR-020, FR-025, FR-028, FR-073, FR-075, FR-079 b, FR-081)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from eil.gates import CRITERIA_BY_STAGE, CriterionResult, GateResult, check_stage
from eil.package import Package

from tests.helpers.package import (
    SEQUENCE_DIAGRAM,
    Story,
    export_record,
    functional_doc,
    record_block,
    region,
    requirements_doc,
    with_functional,
    write_export,
)

JUDGED = ["FUN-G10", "FUN-G12", "FUN-G13"]
STRUCTURAL = [
    "FUN-G02",
    "FUN-G03",
    "FUN-G04",
    "FUN-G05",
    "FUN-G06",
    "FUN-G07",
    "FUN-G08",
    "FUN-G09",
    "FUN-G14",
    "FUN-G15",
    "FUN-G16",
]


def check(story: Story, judgments: Path | None = None) -> GateResult:
    return check_stage(Package(story.root), "functional", judgments_path=judgments)


def crit(result: GateResult, criterion_id: str) -> CriterionResult:
    return next(c for c in result.criteria if c.id == criterion_id)


def judged(tmp: Path, ids: list[str] | None = None) -> Path:
    body = {
        "stage": "functional",
        "judgments": [{"id": i, "status": "met", "reason": "ok"} for i in (ids or JUDGED)],
    }
    path = tmp / "functional-judgments.json"
    path.write_text(json.dumps(body))
    return path


def codes(result: GateResult) -> list[str]:
    return [f.code for f in result.findings]


# ---- the table


def test_the_table_has_sixteen_criteria_in_order_with_their_kinds() -> None:
    table = CRITERIA_BY_STAGE["functional"]
    assert [c.id for c in table] == [f"FUN-G{n:02d}" for n in range(1, 17)]
    kinds = {c.id: c.kind for c in table}
    assert [i for i, k in kinds.items() if k == "traceability"] == ["FUN-G01", "FUN-G11"]
    assert [i for i, k in kinds.items() if k == "judgment"] == JUDGED
    assert [i for i, k in kinds.items() if k == "structural"] == STRUCTURAL


# ---- a complete document


def test_a_complete_document_meets_every_code_decided_criterion_but_the_comprehension_check(
    story_dir: Story,
) -> None:
    with_functional(story_dir)
    result = check(story_dir)
    unmet = [c.id for c in result.criteria if c.status == "not-met" and c.kind != "judgment"]
    assert unmet == ["FUN-G16"], [(c.id, c.reason) for c in result.criteria if c.status == "not-met"]
    assert "comprehension-missing" in codes(result)
    assert (
        "no comprehension check" in crit(result, "FUN-G16").reason
        or "missing" in crit(result, "FUN-G16").reason
    )


def test_judgment_criteria_need_the_ais_verdicts(story_dir: Story, tmp_path: Path) -> None:
    with_functional(story_dir)
    result = check(story_dir, judged(tmp_path))
    assert all(crit(result, i).status == "met" for i in JUDGED)
    assert crit(result, "FUN-G12").reason == "AI assessment: ok"


# ---- traceability (FR-025, FR-028)


def test_a_functional_requirement_with_no_traces_is_untraceable(story_dir: Story) -> None:
    with_functional(
        story_dir,
        sections={
            "Functional Requirements": "**FR-001**: Flag duplicates. (traces: REQ-001)\n\n**FR-009**: Something untraced."
        },
    )
    result = check(story_dir)
    assert crit(result, "FUN-G01").status == "not-met"
    assert "FR-009 traces to no requirement or use case" in crit(result, "FUN-G01").reason


def test_a_trace_to_a_missing_id_is_a_dangling_trace_and_fails_the_gate(story_dir: Story) -> None:
    with_functional(
        story_dir,
        sections={"Functional Requirements": "**FR-001**: Flag duplicates. (traces: REQ-001, REQ-099)"},
    )
    result = check(story_dir)
    assert "dangling-trace" in codes(result)
    assert crit(result, "FUN-G01").status == "not-met" and "REQ-099" in crit(result, "FUN-G01").reason


def test_a_trace_to_another_functional_requirement_is_not_a_trace_to_a_requirement(story_dir: Story) -> None:
    with_functional(
        story_dir,
        sections={
            "Functional Requirements": "**FR-001**: Flag duplicates. (traces: REQ-001)\n\n**FR-002**: X (traces: FR-001)"
        },
    )
    result = check(story_dir)
    assert "FR-002 traces to no requirement or use case" in crit(result, "FUN-G01").reason


def test_an_approved_requirement_with_no_functional_requirement_is_reported_uncovered(
    story_dir: Story,
) -> None:
    with_functional(story_dir)
    story_dir.write(
        "requirements", requirements_doc({"Desired Outcome": "**REQ-001**: A.\n\n**REQ-002**: Also B."})
    )
    result = check(story_dir)
    assert crit(result, "FUN-G01").status == "not-met"
    assert "REQ-002 has no functional requirement" in crit(result, "FUN-G01").reason


def test_a_requirement_covered_through_an_nfr_is_covered(story_dir: Story) -> None:
    with_functional(story_dir)
    story_dir.write(
        "requirements", requirements_doc({"Desired Outcome": "**REQ-001**: A.\n\n**REQ-002**: B."})
    )
    story_dir.write(
        "functional",
        story_dir.read("functional").replace(
            "**NFR-001**: A 10 MB import completes within 60 seconds. (traces: REQ-001)",
            "**NFR-001**: A 10 MB import completes within 60 seconds. (traces: REQ-001, REQ-002)",
        ),
    )
    assert crit(check(story_dir), "FUN-G01").status == "met"


def test_a_missing_functional_requirements_section_is_reported(story_dir: Story) -> None:
    with_functional(story_dir, sections={"Functional Requirements": None})
    assert "missing section 'Functional Requirements'" in crit(check(story_dir), "FUN-G01").reason


# ---- headings (FR-015, FR-018)


@pytest.mark.parametrize(
    ("section", "criterion"),
    [
        ("Business Rules", "FUN-G03"),
        ("Inputs", "FUN-G04"),
        ("Outputs", "FUN-G04"),
        ("State and Workflow", "FUN-G05"),
        ("Validation", "FUN-G06"),
        ("Error and Exception Behaviour", "FUN-G07"),
        ("Security and Access Behaviour", "FUN-G08"),
        ("Audit and Compliance Behaviour", "FUN-G08"),
        ("Non-Functional Requirements", "FUN-G09"),
        ("Actors", "FUN-G02"),
        ("Use Cases and Scenarios", "FUN-G02"),
    ],
)
def test_a_missing_required_heading_fails_its_criterion(
    story_dir: Story, section: str, criterion: str
) -> None:
    with_functional(story_dir, sections={section: None})
    result = check(story_dir)
    assert crit(result, criterion).status == "not-met"
    assert f"missing section '{section}'" in crit(result, criterion).reason


def test_a_section_that_does_not_apply_can_be_listed_with_a_reason(story_dir: Story) -> None:
    with_functional(
        story_dir,
        sections={"Audit and Compliance Behaviour": None},
        not_applicable="- Audit and Compliance Behaviour: no audit duty here",
    )
    assert crit(check(story_dir), "FUN-G08").status == "met"


def test_the_ai_cannot_meet_acceptance_criteria_that_are_missing(story_dir: Story, tmp_path: Path) -> None:
    with_functional(story_dir, sections={"Acceptance Criteria": None})
    result = check(story_dir, judged(tmp_path))
    assert crit(result, "FUN-G10").status == "not-met"
    assert "missing section 'Acceptance Criteria'" in crit(result, "FUN-G10").reason


def test_use_cases_from_the_requirements_must_each_be_described(story_dir: Story) -> None:
    with_functional(story_dir)
    story_dir.write(
        "requirements",
        requirements_doc({"Use Cases": "**UC-001**: A (actor: x)\n\n**UC-002**: B (actor: y)"}),
    )
    result = check(story_dir)
    assert crit(result, "FUN-G02").status == "not-met" and "UC-002" in crit(result, "FUN-G02").reason
    assert "UC-001" not in crit(result, "FUN-G02").reason


def test_non_functional_requirements_need_an_nfr_item(story_dir: Story) -> None:
    with_functional(story_dir, sections={"Non-Functional Requirements": "Should be fast."})
    assert "no NFR item" in crit(check(story_dir), "FUN-G09").reason


def test_an_nfr_section_removed_with_a_reason_needs_no_nfr_item(story_dir: Story) -> None:
    with_functional(
        story_dir,
        sections={"Non-Functional Requirements": None},
        not_applicable="- Non-Functional Requirements: none for this spike",
    )
    assert crit(check(story_dir), "FUN-G09").status == "met"


# ---- ambiguities (FUN-G11)


def test_a_material_open_question_in_the_functional_spec_blocks(story_dir: Story) -> None:
    with_functional(
        story_dir,
        sections={
            "Business Rules": "Rule text.\n\n**OQ-010**: Is the match fuzzy? (status: open) (material: yes)"
        },
    )
    result = check(story_dir)
    assert crit(result, "FUN-G11").status == "not-met" and "OQ-010" in crit(result, "FUN-G11").reason


def test_a_resolved_or_accepted_question_does_not_block(story_dir: Story) -> None:
    with_functional(
        story_dir,
        sections={
            "Business Rules": "**OQ-010**: Fuzzy? (status: accepted) (accepted-by: Ada Dev) (material: yes)"
        },
    )
    assert crit(check(story_dir), "FUN-G11").status == "met"


# ---- sequence diagrams (FR-073 a, FR-079 b, FR-081)


def test_every_use_case_needs_a_sequence_diagram_or_a_recorded_reason(story_dir: Story) -> None:
    with_functional(story_dir, sequence=None)
    result = check(story_dir)
    assert crit(result, "FUN-G14").status == "not-met"
    assert "UC-001 has no sequence diagram and no recorded reason" in crit(result, "FUN-G14").reason


def test_a_recorded_reason_stands_in_for_the_diagram(story_dir: Story) -> None:
    with_functional(
        story_dir, sequence=None, not_applicable="- UC-001: a background job with no interaction to draw"
    )
    assert crit(check(story_dir), "FUN-G14").status == "met"


def test_a_reason_naming_the_use_case_must_give_a_reason(story_dir: Story) -> None:
    with_functional(story_dir, sequence=None, not_applicable="- UC-001:")
    assert "no reason" in crit(check(story_dir), "FUN-G14").reason


def test_a_diagram_must_trace_to_the_use_case_it_shows(story_dir: Story) -> None:
    with_functional(story_dir, sequence_traces="FR-001")
    assert "UC-001 has no sequence diagram" in crit(check(story_dir), "FUN-G14").reason


def test_participants_are_only_the_declared_actors_and_the_system(story_dir: Story) -> None:
    diagram = SEQUENCE_DIAGRAM.replace(
        "participant System", "participant System\n  participant API as Import API"
    )
    diagram += "\n  System->>API: forwards"
    with_functional(story_dir, sequence=diagram)
    result = check(story_dir)
    assert crit(result, "FUN-G14").status == "not-met"
    (finding,) = [f for f in result.findings if f.code == "artifact-wrong-level"]
    assert finding.where == "ART-002" and "Import API" in finding.message and "actor" in finding.message


def test_an_implied_participant_that_is_not_an_actor_is_caught_too(story_dir: Story) -> None:
    with_functional(story_dir, sequence=SEQUENCE_DIAGRAM + "\n  System->>Database: store")
    result = check(story_dir)
    assert crit(result, "FUN-G14").status == "not-met" and "Database" in crit(result, "FUN-G14").reason


def test_actor_names_compare_case_insensitively_and_by_label(story_dir: Story) -> None:
    diagram = "sequenceDiagram\n  actor A as data   ANALYST\n  participant S as system\n  A->>S: go"
    with_functional(story_dir, sequence=diagram)
    assert crit(check(story_dir), "FUN-G14").status == "met"


def test_an_er_diagram_in_the_functional_spec_is_wrong_level(story_dir: Story) -> None:
    er = "\n\n**ART-004**: Data (traces: FR-001)\n\n```mermaid\nerDiagram\n  CUSTOMER ||--o{ ORDER : has\n```\n"
    with_functional(story_dir)
    story_dir.write(
        "functional", story_dir.read("functional").replace("## Wireframes", er + "\n## Wireframes")
    )
    result = check(story_dir)
    assert "artifact-wrong-level" in codes(result)
    assert crit(result, "FUN-G14").status == "not-met"


def test_an_unparseable_sequence_diagram_fails_the_criterion(story_dir: Story) -> None:
    with_functional(story_dir, sequence=SEQUENCE_DIAGRAM + "\n  Analyst ~~> System: bad")
    result = check(story_dir)
    assert "diagram-unparseable" in codes(result) and crit(result, "FUN-G14").status == "not-met"


# ---- wireframes (FR-073 b, FR-075, FR-077, FR-078)


def test_a_story_with_no_wireframe_and_no_reason_is_not_met(story_dir: Story) -> None:
    with_functional(story_dir, wireframe=None)
    result = check(story_dir)
    assert crit(result, "FUN-G15").status == "not-met"
    assert "no wireframe" in crit(result, "FUN-G15").reason


def test_a_story_with_no_user_interface_records_why(story_dir: Story) -> None:
    with_functional(story_dir, wireframe=None, not_applicable="- Wireframes: batch import, no user interface")
    assert crit(check(story_dir), "FUN-G15").status == "met"


def test_a_registered_export_meets_the_criterion(story_dir: Story) -> None:
    with_functional(story_dir)
    assert crit(check(story_dir), "FUN-G15").status == "met"


def test_an_export_whose_file_is_missing_is_not_met(story_dir: Story) -> None:
    with_functional(story_dir, wireframe=export_record(sha256="sha256:" + "0" * 64))
    result = check(story_dir)
    assert "artifact-missing-file" in codes(result) and crit(result, "FUN-G15").status == "not-met"


def test_an_export_edited_after_registration_is_a_hash_mismatch(story_dir: Story) -> None:
    with_functional(story_dir)
    (story_dir.root / "assets" / "duplicate-review.png").write_bytes(
        (story_dir.root / "assets" / "duplicate-review.png").read_bytes() + b"x"
    )
    result = check(story_dir)
    assert "artifact-hash-mismatch" in codes(result) and crit(result, "FUN-G15").status == "not-met"


def test_a_hash_mismatch_changes_no_fingerprint(story_dir: Story) -> None:
    with_functional(story_dir)
    package = Package(story_dir.root)
    before = package.fingerprint("functional")
    (story_dir.root / "assets" / "duplicate-review.png").write_bytes(b"different")
    check(story_dir)
    assert package.fingerprint("functional") == before  # the document did not change (determinism 13)


@pytest.mark.parametrize(
    "source",
    [
        {
            "tool": "figma",
            "url": "https://www.figma.com/design/AbC/Name",
            "exported_at": "2026-09-25",
            "exported_by": "Ada",
        },
        {
            "tool": "figma",
            "url": "https://www.figma.com/design/AbC/Name?node-id=",
            "exported_at": "2026-09-25",
            "exported_by": "Ada",
        },
        {"tool": "figma", "exported_at": "2026-09-25", "exported_by": "Ada"},
        {"tool": "figma", "url": "https://www.figma.com/design/AbC/Name?node-id=1-2", "exported_by": "Ada"},
        {
            "tool": "figma",
            "url": "https://www.figma.com/design/AbC/Name?node-id=1-2",
            "exported_at": "2026-09-25",
        },
    ],
)
def test_an_export_without_provenance_is_not_met(story_dir: Story, source: dict) -> None:
    story_dir.write("requirements", requirements_doc())
    sha = write_export(story_dir.root)
    story_dir.write("functional", functional_doc(wireframe=export_record(sha256=sha, source=source)))
    result = check(story_dir)
    assert "artifact-no-provenance" in codes(result) and crit(result, "FUN-G15").status == "not-met"


def test_a_non_figma_source_needs_a_url_but_not_a_node_id(story_dir: Story) -> None:
    story_dir.write("requirements", requirements_doc())
    sha = write_export(story_dir.root)
    source = {
        "tool": "draw.io",
        "url": "https://example.test/diagram/1",
        "exported_at": "2026-09-25",
        "exported_by": "Ada",
    }
    story_dir.write("functional", functional_doc(wireframe=export_record(sha256=sha, source=source)))
    assert crit(check(story_dir), "FUN-G15").status == "met"


def test_a_format_that_is_not_allowed_is_not_met(story_dir: Story) -> None:
    story_dir.write("requirements", requirements_doc())
    sha = write_export(story_dir.root, "screen.gif", "wireframe.gif")
    story_dir.write("functional", functional_doc(wireframe=export_record("screen.gif", sha)))
    result = check(story_dir)
    assert "artifact-format-not-allowed" in codes(result) and crit(result, "FUN-G15").status == "not-met"


@pytest.mark.parametrize("name", ["wireframe.png", "wireframe.svg", "wireframe.pdf", "wireframe.jpg"])
def test_the_four_allowed_formats_are_accepted(story_dir: Story, name: str) -> None:
    story_dir.write("requirements", requirements_doc())
    sha = write_export(story_dir.root, name, name)
    story_dir.write("functional", functional_doc(wireframe=export_record(name, sha)))
    assert crit(check(story_dir), "FUN-G15").status == "met"


def test_a_listed_screen_with_no_export_yet_is_not_met(story_dir: Story) -> None:
    with_functional(story_dir, wireframe=None)
    story_dir.write(
        "functional",
        story_dir.read("functional").replace(
            "## Wireframes\n",
            "## Wireframes\n\n**ART-003**: Duplicate review screen (traces: FR-001, UC-001)\n",
        ),
    )
    result = check(story_dir)
    assert "artifact-unregistered" in codes(result) and crit(result, "FUN-G15").status == "not-met"


def test_a_record_pointing_outside_the_package_is_not_accepted(story_dir: Story) -> None:
    story_dir.write("requirements", requirements_doc())
    write_export(story_dir.root)
    story_dir.write(
        "functional",
        functional_doc(wireframe=export_record(file="../secret.png", sha256="sha256:" + "0" * 64)),
    )
    result = check(story_dir)
    assert "artifact-missing-file" in codes(result) and crit(result, "FUN-G15").status == "not-met"


# ---- the comprehension criterion (FUN-G16, FR-093)


def comprehension_record(story: Story, levels: int = 5, fingerprint: str | None = None) -> dict:
    names = ["recognise", "explain", "apply", "trace", "evaluate"][:levels]
    return {
        "stage": "functional",
        "fingerprint": fingerprint or Package(story.root).fingerprint("functional"),
        "taken_by": "Ada Dev",
        "levels": [{"level": n, "outcome": "understood", "attempts": 1, "items": ["FR-001"]} for n in names],
    }


def test_a_current_complete_record_meets_the_criterion(story_dir: Story) -> None:
    with_functional(story_dir)
    story_dir.write(
        "functional",
        story_dir.read("functional").replace(
            "<!-- eil:begin comprehension -->\n<!-- eil:end comprehension -->",
            region("comprehension", comprehension_record(story_dir)).rstrip("\n"),
        ),
    )
    result = check(story_dir)
    assert crit(result, "FUN-G16").status == "met"
    assert not [c for c in codes(result) if c.startswith("comprehension")]


def test_an_incomplete_record_is_reported(story_dir: Story) -> None:
    with_functional(story_dir)
    story_dir.write(
        "functional",
        story_dir.read("functional").replace(
            "<!-- eil:begin comprehension -->\n<!-- eil:end comprehension -->",
            region("comprehension", comprehension_record(story_dir, levels=3)).rstrip("\n"),
        ),
    )
    result = check(story_dir)
    assert crit(result, "FUN-G16").status == "not-met" and "comprehension-incomplete" in codes(result)


def test_a_record_for_an_older_version_is_stale(story_dir: Story) -> None:
    with_functional(story_dir)
    stale = comprehension_record(story_dir, fingerprint="sha256:" + "0" * 64)
    story_dir.write(
        "functional",
        story_dir.read("functional").replace(
            "<!-- eil:begin comprehension -->\n<!-- eil:end comprehension -->",
            region("comprehension", stale).rstrip("\n"),
        ),
    )
    assert "comprehension-stale" in codes(check(story_dir))


def test_a_content_change_after_the_check_makes_it_stale_but_a_formatting_change_does_not(
    story_dir: Story,
) -> None:
    with_functional(story_dir)
    record = comprehension_record(story_dir)
    story_dir.write(
        "functional",
        story_dir.read("functional").replace(
            "<!-- eil:begin comprehension -->\n<!-- eil:end comprehension -->",
            region("comprehension", record).rstrip("\n"),
        ),
    )
    path = story_dir.path("functional")
    path.write_bytes(path.read_bytes().replace(b"\n", b"  \r\n"))  # formatting only
    assert crit(check(story_dir), "FUN-G16").status == "met"
    story_dir.append("functional", "\nA new sentence.\n")
    assert "comprehension-stale" in codes(check(story_dir))


def test_a_record_with_a_key_outside_the_allowed_set_is_malformed_and_counts_as_no_record(
    story_dir: Story,
) -> None:
    with_functional(story_dir)
    record = comprehension_record(story_dir)
    record["levels"][0]["answer"] = "the analyst uploads a file"
    story_dir.write(
        "functional",
        story_dir.read("functional").replace(
            "<!-- eil:begin comprehension -->\n<!-- eil:end comprehension -->",
            region("comprehension", record).rstrip("\n"),
        ),
    )
    result = check(story_dir)
    assert "malformed-comprehension" in codes(result) and crit(result, "FUN-G16").status == "not-met"


def test_the_comprehension_criterion_can_be_overridden(story_dir: Story) -> None:
    with_functional(story_dir)
    override = record_block(
        "override",
        {
            "id": "OVR-001",
            "stage": "functional",
            "criterion": "FUN-G16",
            "by": "Ada Dev",
            "reason": "trial run",
        },
    )
    story_dir.write(
        "functional", story_dir.read("functional").replace("## Overrides\n", "## Overrides\n\n" + override)
    )
    assert crit(check(story_dir), "FUN-G16").status == "overridden"
