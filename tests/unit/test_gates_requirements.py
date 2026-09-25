"""The Requirements gate (task T031; FR-009, FR-014, FR-018, FR-022, FR-023, FR-072, FR-079 e and f,
determinism 9 and 21)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from eil.gates import (
    CRITERIA_BY_STAGE,
    CriterionResult,
    GateResult,
    JudgmentsError,
    ai_draft_lines,
    check_stage,
)
from eil.package import Package

from tests.helpers.package import (
    CONTEXT_DIAGRAM,
    REQUIREMENTS_SECTIONS,
    Story,
    record_block,
    requirements_doc,
)

STRUCTURAL = [
    "REQ-G02",
    "REQ-G03",
    "REQ-G04",
    "REQ-G05",
    "REQ-G06",
    "REQ-G07",
    "REQ-G08",
    "REQ-G09",
    "REQ-G14",
]
TRACEABILITY = ["REQ-G10"]
JUDGMENT = ["REQ-G01", "REQ-G11", "REQ-G12", "REQ-G13"]


def run(story: Story, text: str | None = None, judgments: Path | None = None) -> GateResult:
    if text is not None:
        story.write("requirements", text)
    return check_stage(Package(story.root), "requirements", judgments_path=judgments)


def crit(result: GateResult, criterion_id: str) -> CriterionResult:
    return next(c for c in result.criteria if c.id == criterion_id)


def judgments_file(tmp: Path, verdicts: dict[str, str] | None = None, **extra: object) -> Path:
    verdicts = verdicts if verdicts is not None else {cid: "met" for cid in JUDGMENT}
    body = {
        "stage": "requirements",
        "judgments": [
            {"id": cid, "status": status, "reason": f"reason for {cid}"} for cid, status in verdicts.items()
        ],
        **extra,
    }
    path = tmp / "judgments.json"
    path.write_text(json.dumps(body))
    return path


# ---- the criteria table


def test_the_table_has_fourteen_criteria_in_order_with_their_kinds() -> None:
    table = CRITERIA_BY_STAGE["requirements"]
    assert [c.id for c in table] == [f"REQ-G{n:02d}" for n in range(1, 15)]
    kinds = {c.id: c.kind for c in table}
    assert [i for i, k in kinds.items() if k == "structural"] == STRUCTURAL
    assert [i for i, k in kinds.items() if k == "traceability"] == TRACEABILITY
    assert [i for i, k in kinds.items() if k == "judgment"] == JUDGMENT
    assert all(c.text.strip() for c in table)


# ---- a complete document


def test_a_complete_document_meets_every_code_decided_criterion(story_dir: Story) -> None:
    result = run(story_dir, requirements_doc())
    for cid in STRUCTURAL + TRACEABILITY:
        assert crit(result, cid).status == "met", (cid, crit(result, cid).reason)
    assert result.findings == []


def test_judgment_criteria_stay_not_met_until_the_ai_supplies_a_verdict(story_dir: Story) -> None:
    result = run(story_dir, requirements_doc())
    for cid in JUDGMENT:
        assert (crit(result, cid).status, crit(result, cid).reason) == ("not-met", "no judgment supplied")
    assert result.ok is False


def test_with_every_verdict_supplied_the_gate_is_met(story_dir: Story, tmp_path: Path) -> None:
    result = run(story_dir, requirements_doc(), judgments_file(tmp_path))
    assert result.ok is True
    assert all(c.status == "met" for c in result.criteria)


def test_ai_verdicts_are_labelled_as_the_ais(story_dir: Story, tmp_path: Path) -> None:
    result = run(
        story_dir, requirements_doc(), judgments_file(tmp_path, {"REQ-G01": "not-met", "REQ-G11": "met"})
    )
    assert crit(result, "REQ-G01").reason == "AI assessment: reason for REQ-G01"
    assert crit(result, "REQ-G01").status == "not-met"
    assert crit(result, "REQ-G11").reason == "AI assessment: reason for REQ-G11"
    assert crit(result, "REQ-G12").reason == "no judgment supplied"


# ---- required headings (FR-014, FR-018)


def test_an_empty_template_meets_nothing(story_dir: Story) -> None:
    empty = {name: "" for name in REQUIREMENTS_SECTIONS}
    result = run(story_dir, requirements_doc(empty, diagram=None))
    for cid in [
        "REQ-G02",
        "REQ-G03",
        "REQ-G04",
        "REQ-G05",
        "REQ-G06",
        "REQ-G07",
        "REQ-G08",
        "REQ-G09",
        "REQ-G14",
    ]:
        assert crit(result, cid).status == "not-met", cid
    assert "empty" in crit(result, "REQ-G06").reason


@pytest.mark.parametrize(
    ("section", "criterion"),
    [
        ("Desired Outcome", "REQ-G02"),
        ("Users and Stakeholders", "REQ-G03"),
        ("Use Cases", "REQ-G04"),
        ("In Scope", "REQ-G05"),
        ("Out of Scope", "REQ-G05"),
        ("Constraints", "REQ-G06"),
        ("Dependencies", "REQ-G07"),
        ("Risks", "REQ-G08"),
        ("Assumptions", "REQ-G09"),
    ],
)
def test_a_missing_required_heading_makes_its_criterion_not_met(
    story_dir: Story, section: str, criterion: str
) -> None:
    result = run(story_dir, requirements_doc({section: None}))
    assert crit(result, criterion).status == "not-met"
    assert f"missing section '{section}'" in crit(result, criterion).reason


def test_a_removed_section_with_a_recorded_reason_is_met(story_dir: Story) -> None:
    text = requirements_doc(
        {"Constraints": None}, not_applicable="- **Constraints**: a spike, no constraints yet"
    )
    assert crit(run(story_dir, text), "REQ-G06").status == "met"


def test_a_not_applicable_entry_without_a_reason_is_not_enough(story_dir: Story) -> None:
    text = requirements_doc({"Constraints": None}, not_applicable="- Constraints:")
    result = run(story_dir, text)
    assert crit(result, "REQ-G06").status == "not-met"
    assert "no reason" in crit(result, "REQ-G06").reason


def test_a_present_but_empty_section_can_also_be_listed_as_not_applicable(story_dir: Story) -> None:
    text = requirements_doc({"Risks": ""}, not_applicable="- Risks — none identified for this spike")
    assert crit(run(story_dir, text), "REQ-G08").status == "met"


def test_scope_needs_both_in_scope_and_out_of_scope(story_dir: Story) -> None:
    result = run(story_dir, requirements_doc({"Out of Scope": None}))
    assert crit(result, "REQ-G05").status == "not-met"
    assert "Out of Scope" in crit(result, "REQ-G05").reason
    assert "In Scope" not in crit(result, "REQ-G05").reason


def test_use_cases_need_at_least_one_uc_item(story_dir: Story) -> None:
    result = run(story_dir, requirements_doc({"Use Cases": "Some prose but no item."}))
    assert crit(result, "REQ-G04").status == "not-met"
    assert "UC" in crit(result, "REQ-G04").reason


def test_html_comment_guidance_does_not_count_as_content(story_dir: Story) -> None:
    result = run(story_dir, requirements_doc({"Constraints": "<!-- Describe known constraints here -->"}))
    assert crit(result, "REQ-G06").status == "not-met"


def test_section_names_match_case_insensitively(story_dir: Story) -> None:
    text = requirements_doc().replace("## Constraints", "## CONSTRAINTS")
    assert crit(run(story_dir, text), "REQ-G06").status == "met"


def test_the_ai_cannot_meet_a_judgment_criterion_whose_section_is_missing(
    story_dir: Story, tmp_path: Path
) -> None:
    text = requirements_doc({"Problem Statement": None})
    result = run(story_dir, text, judgments_file(tmp_path))
    assert crit(result, "REQ-G01").status == "not-met"
    assert "missing section 'Problem Statement'" in crit(result, "REQ-G01").reason


# ---- open questions (FR-022, FR-023)


@pytest.mark.parametrize(
    ("question", "met"),
    [
        ("**OQ-001**: Retain history? (status: open) (material: yes)", False),
        ("**OQ-001**: Retain history? (material: yes)", False),
        ("**OQ-001**: Retain history? (status: open)", False),  # materiality unstated counts as material
        ("**OQ-001**: Retain history? (status: open) (material: no)", True),
        ("**OQ-001**: Retain history? (status: resolved) (material: yes)", True),
        ("**OQ-001**: Retain history? (status: accepted) (accepted-by: Ada Dev) (material: yes)", True),
        ("**OQ-001**: Retain history? (status: accepted) (material: yes)", False),
    ],
)
def test_material_open_questions_block(story_dir: Story, question: str, met: bool) -> None:
    result = run(story_dir, requirements_doc({"Open Questions": question}))
    assert (crit(result, "REQ-G10").status == "met") is met, crit(result, "REQ-G10").reason
    if not met:
        assert "OQ-001" in crit(result, "REQ-G10").reason


def test_an_accepted_question_without_a_name_says_who_is_missing(story_dir: Story) -> None:
    result = run(
        story_dir, requirements_doc({"Open Questions": "**OQ-001**: Q? (status: accepted) (material: yes)"})
    )
    assert "accepted-by" in crit(result, "REQ-G10").reason


def test_a_missing_open_questions_section_is_reported(story_dir: Story) -> None:
    result = run(story_dir, requirements_doc({"Open Questions": None}))
    assert "missing section 'Open Questions'" in crit(result, "REQ-G10").reason


# ---- the context diagram (FR-072, FR-079 e and f)


def test_a_missing_context_diagram_is_not_met(story_dir: Story) -> None:
    result = run(story_dir, requirements_doc(diagram=None))
    assert crit(result, "REQ-G14").status == "not-met"
    assert "c4-context" in crit(result, "REQ-G14").reason


def test_every_listed_user_must_appear_in_the_diagram(story_dir: Story) -> None:
    sections = {"Users and Stakeholders": "- **Data Analyst**: reviews\n- **Compliance Officer**: audits"}
    result = run(story_dir, requirements_doc(sections))
    assert crit(result, "REQ-G14").status == "not-met"
    (finding,) = [f for f in result.findings if f.code == "diagram-inconsistent"]
    assert "rule e" in finding.message and "Compliance Officer" in finding.message


def test_every_listed_dependency_must_appear_in_the_diagram(story_dir: Story) -> None:
    result = run(story_dir, requirements_doc({"Dependencies": "- **CRM**: store\n- **Billing**: invoices"}))
    (finding,) = [f for f in result.findings if f.code == "diagram-inconsistent"]
    assert "rule e" in finding.message and "Billing" in finding.message


def test_names_are_compared_case_insensitively_and_with_collapsed_whitespace(story_dir: Story) -> None:
    result = run(story_dir, requirements_doc({"Users and Stakeholders": "- **data   ANALYST**: reviews"}))
    assert crit(result, "REQ-G14").status == "met"


def test_the_name_may_come_from_text_before_a_colon_or_a_dash(story_dir: Story) -> None:
    sections = {"Users and Stakeholders": "- Data Analyst: reviews\n- CRM — the customer store"}
    assert crit(run(story_dir, requirements_doc(sections)), "REQ-G14").status == "met"


def test_every_element_needs_an_existing_new_or_changed_marker(story_dir: Story) -> None:
    diagram = CONTEXT_DIAGRAM.replace('"[existing] Customer store"', '"Customer store"')
    result = run(story_dir, requirements_doc(diagram=diagram))
    assert crit(result, "REQ-G14").status == "not-met"
    (finding,) = [f for f in result.findings if f.code == "diagram-inconsistent"]
    assert "rule f" in finding.message and "CRM" in finding.message


def test_an_unparseable_diagram_fails_the_criterion(story_dir: Story) -> None:
    result = run(story_dir, requirements_doc(diagram=CONTEXT_DIAGRAM + "\n  Bogus(x)"))
    assert crit(result, "REQ-G14").status == "not-met"
    assert [f.code for f in result.findings] == ["diagram-unparseable"]


def test_a_wireframe_in_requirements_is_wrong_level(story_dir: Story) -> None:
    extra_art = "**ART-002**: A screen (traces: REQ-001)\n\n" + record_block(
        "artifact", {"file": "assets/a.png", "kind": "wireframe"}
    )
    text = requirements_doc().replace("## Not applicable", extra_art + "\n## Not applicable")
    result = run(story_dir, text)
    assert "artifact-wrong-level" in [f.code for f in result.findings]
    assert crit(result, "REQ-G14").status == "not-met"


def test_an_artifact_without_traces_is_reported_and_fails_the_criterion(story_dir: Story) -> None:
    text = requirements_doc().replace("(traces: REQ-001)\n\n```mermaid", "\n\n```mermaid")
    result = run(story_dir, text)
    assert "artifact-untraced" in [f.code for f in result.findings]
    assert crit(result, "REQ-G14").status == "not-met"


def test_a_diagram_that_is_not_a_context_diagram_does_not_satisfy_the_criterion(story_dir: Story) -> None:
    container = (
        'C4Container\n  Person(a, "Data Analyst", "[existing] x")\n  System(b, "CRM", "[existing] y")\n'
    )
    result = run(story_dir, requirements_doc(diagram=container))
    assert crit(result, "REQ-G14").status == "not-met"
    assert "artifact-wrong-level" in [f.code for f in result.findings]


# ---- overrides (FR-010, FR-045)


def test_an_override_record_makes_that_one_criterion_overridden(story_dir: Story) -> None:
    override = record_block(
        "override",
        {
            "id": "OVR-001",
            "stage": "requirements",
            "criterion": "REQ-G06",
            "by": "Ada Dev",
            "at": "t",
            "reason": "spike",
        },
    )
    result = run(story_dir, requirements_doc({"Constraints": None}, extra=override))
    assert crit(result, "REQ-G06").status == "overridden"
    assert "Ada Dev" in crit(result, "REQ-G06").reason and "spike" in crit(result, "REQ-G06").reason
    assert crit(result, "REQ-G07").status == "met"  # never blanket


def test_an_override_for_another_criterion_does_not_help(story_dir: Story) -> None:
    override = record_block(
        "override",
        {"id": "OVR-001", "stage": "requirements", "criterion": "REQ-G07", "by": "A", "reason": "r"},
    )
    assert (
        crit(run(story_dir, requirements_doc({"Constraints": None}, extra=override)), "REQ-G06").status
        == "not-met"
    )


def test_overridden_criteria_let_the_gate_pass(story_dir: Story, tmp_path: Path) -> None:
    override = record_block(
        "override",
        {"id": "OVR-001", "stage": "requirements", "criterion": "REQ-G06", "by": "A", "reason": "r"},
    )
    result = run(story_dir, requirements_doc({"Constraints": None}, extra=override), judgments_file(tmp_path))
    assert result.ok is True


# ---- --judgments (determinism 21)


def test_a_verdict_for_a_non_judgment_criterion_is_rejected_and_nothing_is_written(
    story_dir: Story, tmp_path: Path
) -> None:
    story_dir.write("requirements", requirements_doc())
    before = story_dir.path("requirements").read_bytes()
    with pytest.raises(JudgmentsError, match="REQ-G03"):
        run(story_dir, None, judgments_file(tmp_path, {"REQ-G03": "met"}))
    assert story_dir.path("requirements").read_bytes() == before


@pytest.mark.parametrize(
    "body",
    [
        {"stage": "requirements", "judgments": [{"id": "REQ-G99", "status": "met", "reason": "r"}]},
        {"stage": "functional", "judgments": [{"id": "REQ-G01", "status": "met", "reason": "r"}]},
        {"stage": "requirements", "judgments": [{"id": "REQ-G01", "status": "met", "reason": ""}]},
        {"stage": "requirements", "judgments": [{"id": "REQ-G01", "status": "overridden", "reason": "r"}]},
        {"stage": "requirements", "judgments": [{"id": "REQ-G01", "status": "met"}]},
        {
            "stage": "requirements",
            "judgments": [{"id": "REQ-G01", "status": "met", "reason": "r", "extra": 1}],
        },
        {"stage": "requirements", "judgments": [{"id": "REQ-G01", "status": "met", "reason": "r"}] * 2},
        {"stage": "requirements", "judgments": "nope"},
        {"stage": "requirements"},
        {"judgments": []},
        {"stage": "requirements", "judgments": [], "surprise": True},
        ["not", "an", "object"],
    ],
)
def test_bad_judgment_files_are_rejected_without_writing(
    story_dir: Story, tmp_path: Path, body: object
) -> None:
    story_dir.write("requirements", requirements_doc())
    before = story_dir.path("requirements").read_bytes()
    path = tmp_path / "j.json"
    path.write_text(json.dumps(body))
    with pytest.raises(JudgmentsError):
        run(story_dir, None, path)
    assert story_dir.path("requirements").read_bytes() == before


def test_a_judgment_file_that_is_not_json_is_rejected(story_dir: Story, tmp_path: Path) -> None:
    story_dir.write("requirements", requirements_doc())
    path = tmp_path / "j.json"
    path.write_text("{ nope")
    with pytest.raises(JudgmentsError):
        run(story_dir, None, path)
    with pytest.raises(JudgmentsError):
        run(story_dir, None, tmp_path / "missing.json")


def test_running_twice_with_the_same_file_is_byte_identical(story_dir: Story, tmp_path: Path) -> None:
    path = judgments_file(tmp_path)
    story_dir.write("requirements", requirements_doc())
    run(story_dir, None, path)
    first = story_dir.path("requirements").read_bytes()
    run(story_dir, None, path)
    assert story_dir.path("requirements").read_bytes() == first


def test_the_optional_assessment_lists_are_written_as_the_ais(story_dir: Story, tmp_path: Path) -> None:
    lists = {"ambiguity": ["'fast' is unquantified"], "untestable": ["SC-2"]}
    run(story_dir, requirements_doc(), judgments_file(tmp_path, assessment=lists))
    region = Package(story_dir.root).doc("requirements").read_region("assessment").obj
    assert region["assessment"]["ambiguity"] == ["'fast' is unquantified"]
    assert region["assessment"]["untestable"] == ["SC-2"]
    assert set(region["assessment"]) == {
        "ambiguity",
        "missing",
        "contradictions",
        "unsupported_assumptions",
        "untestable",
    }


def test_the_missing_list_reports_missing_sections_without_the_ai(story_dir: Story) -> None:
    run(story_dir, requirements_doc({"Constraints": None}))
    region = Package(story_dir.root).doc("requirements").read_region("assessment").obj
    assert any("Constraints" in entry for entry in region["assessment"]["missing"])


def test_unknown_assessment_list_names_are_rejected(story_dir: Story, tmp_path: Path) -> None:
    story_dir.write("requirements", requirements_doc())
    with pytest.raises(JudgmentsError):
        run(story_dir, None, judgments_file(tmp_path, assessment={"vibes": ["x"]}))


# ---- the assessment region (FR-009, determinism 9)


def test_check_writes_the_assessment_region_and_leaves_the_fingerprint_alone(story_dir: Story) -> None:
    story_dir.write("requirements", requirements_doc())
    package = Package(story_dir.root)
    before = package.fingerprint("requirements")
    result = check_stage(package, "requirements")
    assert package.fingerprint("requirements") == before == result.fingerprint
    region = package.doc("requirements").read_region("assessment").obj
    assert region["stage"] == "requirements" and region["fingerprint"] == before
    assert [c["id"] for c in region["criteria"]][:2] == ["REQ-G01", "REQ-G02"]
    assert {"id", "kind", "status", "reason"} <= set(region["criteria"][0])


def test_check_without_writing_changes_nothing(story_dir: Story) -> None:
    story_dir.write("requirements", requirements_doc())
    before = story_dir.path("requirements").read_bytes()
    check_stage(Package(story_dir.root), "requirements", write=False)
    assert story_dir.path("requirements").read_bytes() == before


def test_running_check_twice_is_byte_identical(story_dir: Story) -> None:
    story_dir.write("requirements", requirements_doc())
    package = Package(story_dir.root)
    check_stage(package, "requirements")
    first = story_dir.path("requirements").read_bytes()
    check_stage(package, "requirements")
    assert story_dir.path("requirements").read_bytes() == first


def test_a_met_gate_makes_the_stage_in_review(story_dir: Story, tmp_path: Path) -> None:
    run(story_dir, requirements_doc(), judgments_file(tmp_path))
    assert Package(story_dir.root).state("requirements").state == "in-review"


def test_verdicts_are_kept_while_the_document_is_unchanged(story_dir: Story, tmp_path: Path) -> None:
    run(story_dir, requirements_doc(), judgments_file(tmp_path))
    again = check_stage(Package(story_dir.root), "requirements")  # no judgments file this time
    assert again.ok is True
    assert crit(again, "REQ-G01").reason == "AI assessment: reason for REQ-G01"


def test_verdicts_go_stale_when_the_document_changes(story_dir: Story, tmp_path: Path) -> None:
    run(story_dir, requirements_doc(), judgments_file(tmp_path))
    story_dir.append("requirements", "\nA new sentence.\n")
    again = check_stage(Package(story_dir.root), "requirements")
    assert crit(again, "REQ-G01").reason == "no judgment supplied"
    assert again.ok is False


def test_a_new_judgments_file_replaces_earlier_verdicts_wholly(story_dir: Story, tmp_path: Path) -> None:
    run(story_dir, requirements_doc(), judgments_file(tmp_path))
    result = check_stage(
        Package(story_dir.root), "requirements", judgments_path=judgments_file(tmp_path, {"REQ-G01": "met"})
    )
    assert crit(result, "REQ-G01").status == "met"
    assert crit(result, "REQ-G11").reason == "no judgment supplied"


def test_check_never_changes_human_content(story_dir: Story) -> None:
    text = requirements_doc()
    story_dir.write("requirements", text)
    check_stage(Package(story_dir.root), "requirements")
    written = story_dir.read("requirements")
    start = written.index("<!-- eil:begin assessment -->")
    end = written.index("<!-- eil:end assessment -->") + len("<!-- eil:end assessment -->")
    assert (
        written[:start] + written[end:]
        == text[: text.index("<!-- eil:begin assessment -->")]
        + text[text.index("<!-- eil:end assessment -->") + len("<!-- eil:end assessment -->") :]
    )


# ---- unreviewed AI content (D-16)


def test_ai_draft_tags_are_found_with_their_line_numbers() -> None:
    text = "# T\n\n**FR-001**: Do it [ai-draft]\n\nprose [ai-draft] more\n\n```text\n[ai-draft] in a fence\n```\n"
    assert ai_draft_lines(text) == [3, 5]


def test_ai_draft_tags_in_comments_do_not_count() -> None:
    assert ai_draft_lines("<!-- tag AI text with [ai-draft] -->\ntext\n") == []
