"""The Technical gate (task T074; FR-016, FR-026, FR-032, FR-033, FR-074, FR-075, FR-079, FR-081)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from eil.blocks import Doc
from eil.fingerprint import fingerprint_text
from eil.gates import CRITERIA_BY_STAGE, CriterionResult, GateResult, JudgmentsError, check_stage
from eil.package import Package
from eil.trace import item_hash, parse_document

from tests.helpers.package import (
    CONTAINER_DIAGRAM,
    CONTEXT_DIAGRAM,
    DECISION,
    TECHNICAL_SECTIONS,
    Story,
    export_record,
    mermaid,
    record_block,
    technical_doc,
    with_technical,
    write_export,
)

JUDGED = ["TEC-G01", "TEC-G08", "TEC-G13", "TEC-G14"]
TRACEABILITY = ["TEC-G02", "TEC-G12"]


def check(story: Story, judgments: Path | None = None) -> GateResult:
    return check_stage(Package(story.root), "technical", judgments_path=judgments)


def crit(result: GateResult, criterion_id: str) -> CriterionResult:
    return next(c for c in result.criteria if c.id == criterion_id)


def judged(tmp: Path, ids: list[str] | None = None) -> Path:
    body = {
        "stage": "technical",
        "judgments": [{"id": i, "status": "met", "reason": "ok"} for i in (ids or JUDGED)],
    }
    path = tmp / "technical-judgments.json"
    path.write_text(json.dumps(body))
    return path


def codes(result: GateResult) -> list[str]:
    return [f.code for f in result.findings]


def unmet(result: GateResult) -> list[str]:
    return [c.id for c in result.criteria if c.status == "not-met" and c.kind != "judgment"]


# ---- the table


def test_the_table_has_nineteen_criteria_in_order_with_their_kinds() -> None:
    table = CRITERIA_BY_STAGE["technical"]
    assert [c.id for c in table] == [f"TEC-G{n:02d}" for n in range(1, 20)]
    kinds = {c.id: c.kind for c in table}
    assert [i for i, k in kinds.items() if k == "judgment"] == JUDGED
    assert [i for i, k in kinds.items() if k == "traceability"] == TRACEABILITY
    assert all(k == "structural" for i, k in kinds.items() if i not in [*JUDGED, *TRACEABILITY])


# ---- a complete document


def test_a_complete_document_meets_every_code_decided_criterion_but_the_comprehension_check(
    story_dir: Story,
) -> None:
    with_technical(story_dir)
    result = check(story_dir)
    assert unmet(result) == ["TEC-G19"], [(c.id, c.reason) for c in result.criteria if c.status == "not-met"]
    assert "comprehension-missing" in codes(result)


def test_judgment_criteria_need_the_ais_verdicts_and_the_ai_cannot_meet_the_rest(
    story_dir: Story, tmp_path: Path
) -> None:
    with_technical(story_dir)
    assert all(crit(check(story_dir), i).status == "not-met" for i in JUDGED)
    result = check(story_dir, judged(tmp_path))
    assert all(crit(result, i).status == "met" for i in JUDGED)
    assert crit(result, "TEC-G13").reason == "AI assessment: ok"
    with_technical(story_dir, sections={"Security Design": None})
    body = {"stage": "technical", "judgments": [{"id": "TEC-G03", "status": "met", "reason": "fine"}]}
    (tmp_path / "bad.json").write_text(json.dumps(body))
    with pytest.raises(JudgmentsError, match="not a judgment criterion"):
        check(story_dir, tmp_path / "bad.json")


def test_a_judgment_with_missing_structure_is_not_met_whatever_the_ai_says(
    story_dir: Story, tmp_path: Path
) -> None:
    with_technical(story_dir, sections={"Testing Strategy": None})
    result = check(story_dir, judged(tmp_path))
    assert crit(result, "TEC-G08").status == "not-met"
    assert "missing section 'Testing Strategy'" in crit(result, "TEC-G08").reason


# ---- sections named by the criteria (FR-016, FR-018)

SECTION_CRITERION = [
    ("Security Design", "TEC-G03"),
    ("Data Design", "TEC-G04"),
    ("API and Integration Design", "TEC-G05"),
    ("Existing System Impact", "TEC-G05"),
    ("Error Handling and Resilience", "TEC-G06"),
    ("Observability", "TEC-G07"),
    ("Performance", "TEC-G07"),
    ("Deployment and Migration", "TEC-G09"),
    ("Alternatives Considered", "TEC-G10"),
    ("Risks and Trade-offs", "TEC-G11"),
    ("Technical Decisions", "TEC-G02"),
]


@pytest.mark.parametrize(("section", "criterion"), SECTION_CRITERION)
def test_a_missing_or_empty_section_fails_its_criterion_by_name(
    story_dir: Story, section: str, criterion: str
) -> None:
    with_technical(story_dir, sections={section: None})
    assert f"missing section '{section}'" in crit(check(story_dir), criterion).reason
    with_technical(story_dir, sections={section: ""})
    assert f"section '{section}' is empty" in crit(check(story_dir), criterion).reason


@pytest.mark.parametrize(("section", "criterion"), SECTION_CRITERION[:-1])
def test_a_section_listed_as_not_applicable_with_a_reason_is_accepted_and_without_one_is_not(
    story_dir: Story, section: str, criterion: str
) -> None:
    with_technical(story_dir, sections={section: None}, not_applicable=f"- {section}: nothing changes here")
    assert crit(check(story_dir), criterion).status == "met"
    with_technical(story_dir, sections={section: None}, not_applicable=f"- {section}:")
    assert "gives no reason" in crit(check(story_dir), criterion).reason


def test_every_section_of_fr_016_has_a_criterion_that_names_it() -> None:
    named = {h for c in CRITERIA_BY_STAGE["technical"] for h in c.headings}
    wanted = set(TECHNICAL_SECTIONS) - {"Technical Requirements", "Architecture", "Component Design"}
    assert wanted <= named
    judged_headings = {h for c in CRITERIA_BY_STAGE["technical"] if c.id == "TEC-G01" for h in c.headings}
    assert {"Technical Requirements", "Architecture", "Component Design"} <= judged_headings


# ---- technical decisions (FR-026, FR-032, FR-033)

FIELDS = ["Decision", "Reason", "Rejected alternative", "Trade-off", "Owner"]


@pytest.mark.parametrize("field", FIELDS)
def test_a_decision_missing_a_field_fails_and_names_the_field(story_dir: Story, field: str) -> None:
    lines = [ln for ln in DECISION.splitlines() if not ln.startswith(f"{field}:")]
    with_technical(story_dir, sections={"Technical Decisions": "\n".join(lines)})
    result = check(story_dir)
    reason = crit(result, "TEC-G02").reason
    assert crit(result, "TEC-G02").status == "not-met"
    assert f"DEC-001 has no {field.lower()}" in reason


def test_a_field_with_a_label_but_no_text_counts_as_missing(story_dir: Story) -> None:
    text = DECISION.replace("Reason: A 10 MB import can exceed the synchronous latency limit.", "Reason:")
    with_technical(story_dir, sections={"Technical Decisions": text})
    assert "DEC-001 has no reason" in crit(check(story_dir), "TEC-G02").reason


def test_several_missing_fields_are_all_listed(story_dir: Story) -> None:
    text = "**DEC-001**: Use a queue (traces: FR-001)\nDecision: Use a queue."
    with_technical(story_dir, sections={"Technical Decisions": text})
    reason = crit(check(story_dir), "TEC-G02").reason
    for field in ("reason", "rejected alternative", "trade-off", "owner"):
        assert f"DEC-001 has no {field}" in reason


def test_fields_may_be_bold_bulleted_and_spread_over_blank_lines_like_the_standards_example(
    story_dir: Story,
) -> None:
    text = (
        "**DEC-001**: Use asynchronous processing (traces: FR-001)\n\n"
        "**Decision:**\nDuplicate analysis runs asynchronously.\n\n"
        "**Reason**:\nThe analysis may exceed the synchronous latency limit.\n\n"
        "- Rejected alternative: Analyse in the request.\n"
        "- Trade-off: Results are not immediate.\n"
        "- Owner: Ada Dev\n"
    )
    with_technical(story_dir, sections={"Technical Decisions": text})
    assert crit(check(story_dir), "TEC-G02").status == "met"


def test_a_decision_is_owned_by_a_person_not_the_ai(story_dir: Story) -> None:
    with_technical(
        story_dir, sections={"Technical Decisions": DECISION.replace("Owner: Ada Dev", "Owner: Claude")}
    )
    result = check(story_dir)
    assert crit(result, "TEC-G02").status == "not-met"
    assert "DEC-001 is owned by 'Claude'" in crit(result, "TEC-G02").reason


def test_a_decision_must_trace_to_a_functional_or_non_functional_requirement(story_dir: Story) -> None:
    for traces, expected in (
        ("", "traces to no FR or NFR"),
        (" (traces: REQ-001)", "traces to no FR or NFR"),
    ):
        text = DECISION.replace(" (traces: FR-001, NFR-001)", traces)
        with_technical(story_dir, sections={"Technical Decisions": text})
        assert expected in crit(check(story_dir), "TEC-G02").reason


def test_a_decision_that_traces_to_a_missing_id_is_a_dangling_trace(story_dir: Story) -> None:
    text = DECISION.replace("FR-001, NFR-001", "FR-001, FR-099")
    with_technical(story_dir, sections={"Technical Decisions": text})
    result = check(story_dir)
    assert "dangling-trace" in codes(result)
    assert "FR-099" in crit(result, "TEC-G02").reason


def test_no_decision_at_all_fails_the_criterion(story_dir: Story) -> None:
    with_technical(story_dir, sections={"Technical Decisions": "We will use a queue."})
    assert "no DEC item" in crit(check(story_dir), "TEC-G02").reason


def test_an_example_decision_inside_a_comment_is_not_a_decision(story_dir: Story) -> None:
    text = "<!--\n**DEC-009**: Example (traces: FR-001)\nDecision: an example\n-->\n" + DECISION
    with_technical(story_dir, sections={"Technical Decisions": text})
    result = check(story_dir)
    assert crit(result, "TEC-G02").status == "met"


def test_a_change_to_a_decision_field_changes_the_document_fingerprint_even_after_a_blank_line(
    story_dir: Story,
) -> None:
    text = "**DEC-001**: Queue it (traces: FR-001)\n\nDecision: Use a queue.\n\nReason: Latency.\n"
    other = text.replace("Latency", "Cost")
    first = {i.id: item_hash(i) for i in parse_document(Doc(text)).items}
    second = {i.id: item_hash(i) for i in parse_document(Doc(other)).items}
    assert first != second and fingerprint_text(text) != fingerprint_text(other)


# ---- unresolved technical questions (TEC-G12)


def test_an_open_material_question_is_listed_and_blocks_the_gate(story_dir: Story) -> None:
    with_technical(
        story_dir,
        sections={"Risks and Trade-offs": "**OQ-005**: Which queue product do we use? (material: yes)"},
    )
    result = check(story_dir)
    assert crit(result, "TEC-G12").status == "not-met"
    assert "OQ-005 is open and material" in crit(result, "TEC-G12").reason


def test_a_question_accepted_by_a_named_person_does_not_block(story_dir: Story) -> None:
    text = "**OQ-005**: Which queue? (status: accepted) (accepted-by: Ada Dev) (material: yes)"
    with_technical(story_dir, sections={"Risks and Trade-offs": text})
    assert crit(check(story_dir), "TEC-G12").status == "met"


def test_a_pending_clarification_is_an_unresolved_question(story_dir: Story) -> None:
    text = "The queue is undecided. [pending-clarification]"
    with_technical(
        story_dir, sections={"Risks and Trade-offs": f"**DEC-002**: Queue product (traces: FR-001) {text}"}
    )
    result = check(story_dir)
    assert (
        "DEC-002" in crit(result, "TEC-G12").reason
        and "pending clarification" in crit(result, "TEC-G12").reason
    )


# ---- the diagram criteria (FR-074, FR-075, FR-080)

DIAGRAM_CRITERIA = ["TEC-G15", "TEC-G16", "TEC-G17", "TEC-G18"]


def test_a_missing_container_diagram_fails_tec_g15(story_dir: Story) -> None:
    with_technical(story_dir, container=None)
    result = check(story_dir)
    assert (
        crit(result, "TEC-G15").status == "not-met"
        and "no c4-container diagram" in crit(result, "TEC-G15").reason
    )


def test_a_new_or_changed_container_needs_a_component_diagram_or_a_reason(story_dir: Story) -> None:
    with_technical(story_dir, components=None)
    reason = crit(check(story_dir), "TEC-G16").reason
    assert "Duplicate Worker" in reason and "no component diagram" in reason
    with_technical(
        story_dir, components=None, not_applicable="- Duplicate Worker: a single module, no parts to show"
    )
    assert crit(check(story_dir), "TEC-G16").status == "met"
    with_technical(story_dir, components=None, not_applicable="- Duplicate Worker:")
    assert "gives no reason" in crit(check(story_dir), "TEC-G16").reason


def test_an_existing_unchanged_container_needs_no_component_diagram(story_dir: Story) -> None:
    with_technical(story_dir)
    result = check(story_dir)
    assert "Import API" not in crit(result, "TEC-G16").reason and crit(result, "TEC-G16").status == "met"


def test_a_component_diagram_is_needed_for_a_changed_container_too(story_dir: Story) -> None:
    changed = CONTAINER_DIAGRAM.replace("[existing] Accepts imports", "[changed] Accepts imports")
    with_technical(story_dir, container=changed)
    assert "Import API" in crit(check(story_dir), "TEC-G16").reason


def test_each_use_case_needs_a_technical_sequence_diagram_or_a_reason(story_dir: Story) -> None:
    with_technical(story_dir, sequence=None)
    reason = crit(check(story_dir), "TEC-G17").reason
    assert "UC-001 has no technical sequence diagram" in reason
    with_technical(story_dir, sequence=None, not_applicable="- UC-001: stays inside the import API")
    assert crit(check(story_dir), "TEC-G17").status == "met"
    with_technical(story_dir, sequence=None, not_applicable="- UC-001:")
    assert "gives no reason" in crit(check(story_dir), "TEC-G17").reason


def test_a_sequence_diagram_covers_a_use_case_through_the_functional_requirement_it_traces(
    story_dir: Story,
) -> None:
    functional = {
        "sections": {
            "Functional Requirements": "**FR-001**: The system shall flag duplicate customers on import. (traces: REQ-001, UC-001)"
        }
    }
    with_technical(story_dir, functional=functional, sequence_traces="FR-001, DEC-001")
    assert crit(check(story_dir), "TEC-G17").status == "met"


def test_a_technical_sequence_diagram_must_cite_a_decision(story_dir: Story) -> None:
    with_technical(story_dir, sequence_traces="UC-001, FR-001")
    result = check(story_dir)
    assert crit(result, "TEC-G17").status == "not-met"
    assert "ART-006 cites no decision" in crit(result, "TEC-G17").reason


def test_persistent_data_needs_an_er_diagram_or_a_recorded_reason(story_dir: Story) -> None:
    with_technical(story_dir, er=None)
    assert "no er diagram" in crit(check(story_dir), "TEC-G18").reason
    with_technical(story_dir, er=None, not_applicable="- Data Model: no persistent data changes")
    assert crit(check(story_dir), "TEC-G18").status == "met"
    with_technical(story_dir, er=None, not_applicable="- Data Model:")
    assert "gives no reason" in crit(check(story_dir), "TEC-G18").reason


@pytest.mark.parametrize(
    ("argument", "criterion"),
    [
        ("container", "TEC-G15"),
        ("components", "TEC-G16"),
        ("sequence", "TEC-G17"),
        ("er", "TEC-G18"),
    ],
)
def test_a_diagram_that_does_not_parse_fails_its_own_criterion_and_is_named(
    story_dir: Story, argument: str, criterion: str
) -> None:
    header = {
        "container": "C4Container",
        "components": "C4Component",
        "sequence": "sequenceDiagram",
        "er": "erDiagram",
    }[argument]
    with_technical(story_dir, **{argument: f"{header}\n  this is not a statement ("})
    result = check(story_dir)
    assert crit(result, criterion).status == "not-met"
    assert "diagram-unparseable" in crit(result, criterion).reason
    assert "diagram-unparseable" in codes(result)
    others = [c for c in DIAGRAM_CRITERIA if c != criterion]
    assert all("diagram-unparseable" not in crit(result, c).reason for c in others)


def test_an_artifact_of_the_wrong_level_is_reported_against_its_criterion(story_dir: Story) -> None:
    with_technical(story_dir, container=CONTEXT_DIAGRAM)
    result = check(story_dir)
    assert "artifact-wrong-level" in codes(result)
    assert crit(result, "TEC-G15").status == "not-met"


def test_a_wireframe_in_the_technical_document_is_wrong_level(story_dir: Story) -> None:
    sha = write_export(story_dir.root)
    extra = "**ART-010**: Screen (traces: FR-001)\n\n" + record_block("artifact", export_record(sha256=sha))
    with_technical(story_dir, sections={"Risks and Trade-offs": "Some risk.\n\n" + extra})
    assert "artifact-wrong-level" in codes(check(story_dir))


def test_a_misplaced_attachment_is_reported_against_the_criterion_of_its_section(story_dir: Story) -> None:
    stray = mermaid("erDiagram\n  A ||--o{ B : has")
    with_technical(story_dir, sections={"Performance": "Ten imports at once.\n\n" + stray})
    result = check(story_dir)
    assert "artifact-unregistered" in codes(result)


# ---- comprehension (FR-093) and overrides (FR-045)


def test_the_comprehension_criterion_is_met_by_a_complete_current_record(story_dir: Story) -> None:
    with_technical(story_dir)
    text = story_dir.read("technical")
    # the record is outside the fingerprint, so it can be computed from the document as written
    record = {
        "stage": "technical",
        "fingerprint": fingerprint_text(text),
        "taken_by": "Ada Dev",
        "levels": [
            {"level": level, "outcome": "understood", "attempts": 1, "items": ["DEC-001"]}
            for level in ("recognise", "explain", "apply", "trace", "evaluate")
        ],
    }
    story_dir.write("technical", technical_doc(comprehension=record))
    result = check(story_dir)
    assert crit(result, "TEC-G19").status == "met", crit(result, "TEC-G19").reason


def test_a_record_for_an_earlier_version_is_stale(story_dir: Story) -> None:
    record = {
        "stage": "technical",
        "fingerprint": "sha256:" + "0" * 64,
        "taken_by": "Ada Dev",
        "levels": [
            {"level": level, "outcome": "understood", "attempts": 1, "items": ["DEC-001"]}
            for level in ("recognise", "explain", "apply", "trace", "evaluate")
        ],
    }
    with_technical(story_dir, comprehension=record)
    result = check(story_dir)
    assert "comprehension-stale" in codes(result) and crit(result, "TEC-G19").status == "not-met"


def test_an_override_by_a_confirmer_clears_a_criterion_and_stays_visible(story_dir: Story) -> None:
    override = {
        "id": "OVR-001",
        "stage": "technical",
        "criterion": "TEC-G19",
        "by": "Ada Dev",
        "reason": "trial run",
        "at": "2026-09-25T00:00:00Z",
    }
    with_technical(story_dir, extra=record_block("override", override))
    result = check(story_dir)
    assert crit(result, "TEC-G19").status == "overridden"
    assert "OVR-001" in crit(result, "TEC-G19").reason
