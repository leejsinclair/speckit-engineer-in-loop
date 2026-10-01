"""The AI Specification gate (task T084; FR-017, FR-027, FR-039, FR-067, FR-081, FR-082, determinism 16).

Nothing here needs the AI: every criterion is decided by code. The gate is what Plan and Tasks wait
on, and it is never approved by a person (spec Assumptions).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from eil.fingerprint import fingerprint_text
from eil.gates import CRITERIA_BY_STAGE, CriterionResult, GateResult, check_stage
from eil.package import Package

from tests.helpers.package import (
    AIS_SECTIONS,
    Story,
    approve_stages,
    mermaid,
    record_block,
    technical_doc,
    with_ai_spec,
)


def check(story: Story) -> GateResult:
    return check_stage(Package(story.root), "ai-spec")


def crit(result: GateResult, criterion_id: str) -> CriterionResult:
    return next(c for c in result.criteria if c.id == criterion_id)


def codes(result: GateResult) -> list[str]:
    return [f.code for f in result.findings]


def unmet(result: GateResult) -> list[str]:
    return [c.id for c in result.criteria if c.status == "not-met"]


# ---- the table


def test_the_table_has_five_criteria_all_decided_by_code() -> None:
    table = CRITERIA_BY_STAGE["ai-spec"]
    assert [c.id for c in table] == [f"AIS-G{n:02d}" for n in range(1, 6)]
    assert {c.id: c.kind for c in table} == {
        "AIS-G01": "structural",
        "AIS-G02": "traceability",
        "AIS-G03": "traceability",
        "AIS-G04": "traceability",
        "AIS-G05": "structural",
    }


def test_a_complete_traced_document_meets_the_gate(story_dir: Story) -> None:
    with_ai_spec(story_dir)
    result = check(story_dir)
    assert result.ok, [(c.id, c.reason) for c in result.criteria if c.status != "met"]
    assert not [f for f in result.findings if f.code.startswith(("ai-spec", "artifact", "pending"))]


def test_the_gate_writes_only_the_assessment_region(story_dir: Story) -> None:
    with_ai_spec(story_dir)
    before = story_dir.read("ai-spec")
    check(story_dir)
    after = story_dir.read("ai-spec")
    assert "eil:begin assessment -->\n```json" in after
    assert fingerprint_text(after) == fingerprint_text(before)


# ---- the sections of FR-017


@pytest.mark.parametrize("section", [s for s in AIS_SECTIONS])
def test_every_section_of_fr_017_and_the_artefact_list_must_be_present_and_not_empty(
    story_dir: Story, section: str
) -> None:
    with_ai_spec(story_dir, sections={section: None})
    assert f"missing section '{section}'" in crit(check(story_dir), "AIS-G01").reason
    with_ai_spec(story_dir, sections={section: ""})
    assert f"section '{section}' is empty" in crit(check(story_dir), "AIS-G01").reason


def test_a_section_that_does_not_apply_is_listed_with_a_reason(story_dir: Story) -> None:
    with_ai_spec(
        story_dir, sections={"Existing Code": None}, not_applicable="- Existing Code: a new component"
    )
    assert crit(check(story_dir), "AIS-G01").status == "met"
    with_ai_spec(story_dir, sections={"Existing Code": None}, not_applicable="- Existing Code:")
    assert "gives no reason" in crit(check(story_dir), "AIS-G01").reason


def test_optional_agent_guidance_is_allowed_and_not_required(story_dir: Story) -> None:
    with_ai_spec(story_dir, sections={"Agent Guidance": "Follow the patterns in src/importer.py."})
    assert check(story_dir).ok


# ---- source traceability (FR-027, FR-039)


def test_an_item_with_no_trace_has_no_source(story_dir: Story) -> None:
    with_ai_spec(story_dir, sections={"Business Rules": "**AIS-002**: Tax ids are unique."})
    result = check(story_dir)
    assert "AIS-002 traces to no approved source" in crit(result, "AIS-G02").reason
    assert any(f.code == "ai-spec-not-traceable" and f.where == "AIS-002" for f in result.findings)


@pytest.mark.parametrize("ref", ["REQ-001", "UC-001", "FR-001", "NFR-001", "DEC-001", "ART-004"])
def test_each_kind_of_approved_source_is_accepted(story_dir: Story, ref: str) -> None:
    with_ai_spec(story_dir, sections={"Business Rules": f"**AIS-002**: A rule. (traces: {ref})"})
    assert crit(check(story_dir), "AIS-G02").status == "met"


def test_a_trace_to_an_id_nothing_defines_is_a_dangling_trace_and_not_a_source(story_dir: Story) -> None:
    with_ai_spec(story_dir, sections={"Business Rules": "**AIS-002**: A rule. (traces: FR-099)"})
    result = check(story_dir)
    assert "dangling-trace" in codes(result)
    assert "AIS-002 traces to FR-099, which nothing defines" in crit(result, "AIS-G02").reason


def test_an_item_cannot_take_another_item_of_the_same_document_as_its_source(story_dir: Story) -> None:
    with_ai_spec(story_dir, sections={"Business Rules": "**AIS-002**: A rule. (traces: AIS-001)"})
    assert "AIS-001, an item of this document" in crit(check(story_dir), "AIS-G02").reason


def test_an_open_question_or_challenge_is_not_a_source(story_dir: Story) -> None:
    with_ai_spec(story_dir, sections={"Business Rules": "**AIS-002**: A rule. (traces: OQ-001)"})
    assert "not a requirement, decision or artefact" in crit(check(story_dir), "AIS-G02").reason


def test_a_source_in_a_stage_that_is_not_approved_is_not_a_source(story_dir: Story) -> None:
    with_ai_spec(story_dir)
    story_dir.write("technical", story_dir.read("technical").replace("10 MB", "20 MB"))
    result = check(story_dir)
    reason = crit(result, "AIS-G02").reason
    assert "AIS-003 traces to DEC-001, defined in technical, which is needs-re-review" in reason
    assert crit(check(story_dir), "AIS-G02").status == "not-met"


def test_re_approving_the_changed_stage_restores_the_source(story_dir: Story) -> None:
    with_ai_spec(story_dir)
    story_dir.write("technical", story_dir.read("technical").replace("10 MB", "20 MB"))
    assert not check(story_dir).ok
    approve_stages(story_dir, "technical")
    assert crit(check(story_dir), "AIS-G02").status == "met"


def test_text_that_is_not_an_item_has_no_source_and_is_flagged_with_its_line(story_dir: Story) -> None:
    with_ai_spec(
        story_dir,
        sections={
            "Business Rules": "**AIS-002**: A rule. (traces: FR-001)\n\nAlso cache every lookup for a day."
        },
    )
    result = check(story_dir)
    text = story_dir.read("ai-spec").splitlines()
    line = next(i for i, row in enumerate(text, 1) if "cache every lookup" in row)
    assert (
        f"line {line}" in crit(result, "AIS-G02").reason and "no AIS item" in crit(result, "AIS-G02").reason
    )
    assert any(f.code == "ai-spec-not-traceable" for f in result.findings)


def test_a_continuation_line_of_an_item_is_part_of_the_item(story_dir: Story) -> None:
    body = "**AIS-002**: A rule that runs\nover two lines. (traces: FR-001)"
    with_ai_spec(story_dir, sections={"Business Rules": body})
    assert crit(check(story_dir), "AIS-G02").status == "met"


def test_comments_and_the_example_in_a_template_are_not_text(story_dir: Story) -> None:
    body = "<!-- Advice for the author. **AIS-099**: Example (traces: FR-001) -->\n**AIS-002**: A rule. (traces: FR-001)"
    with_ai_spec(story_dir, sections={"Business Rules": body})
    assert crit(check(story_dir), "AIS-G02").status == "met"


def test_bulleted_items_are_items(story_dir: Story) -> None:
    with_ai_spec(story_dir, sections={"Business Rules": "- **AIS-002**: A rule. (traces: FR-001)"})
    assert crit(check(story_dir), "AIS-G02").status == "met"


# ---- pending clarifications (FR-067)


def test_a_pending_clarification_fails_the_gate_and_is_listed(story_dir: Story) -> None:
    body = "**AIS-002**: Retention is 90 days. [pending-clarification]"
    with_ai_spec(story_dir, sections={"Business Rules": body})
    result = check(story_dir)
    assert crit(result, "AIS-G03").status == "not-met"
    assert "AIS-002" in crit(result, "AIS-G03").reason
    assert any(f.code == "pending-clarification" and f.where == "AIS-002" for f in result.findings)
    assert "AIS-G02" not in unmet(result), "a pending answer is reported once, against its own criterion"
    assert not result.ok


def test_a_pending_clarification_can_be_overridden_by_name_and_stays_visible(story_dir: Story) -> None:
    override = {
        "id": "OVR-001",
        "stage": "ai-spec",
        "criterion": "AIS-G03",
        "by": "Ada Dev",
        "reason": "the answer is reviewed in the next stage",
        "at": "2026-09-25T00:00:00Z",
    }
    body = "**AIS-002**: Retention is 90 days. [pending-clarification]"
    with_ai_spec(story_dir, sections={"Business Rules": body}, extra=record_block("override", override))
    result = check(story_dir)
    assert crit(result, "AIS-G03").status == "overridden" and result.ok
    assert "pending-clarification" in codes(result)


# ---- referenced artefacts (FR-082, determinism 16)


def test_an_artefact_that_changed_since_its_stage_was_approved_is_named(story_dir: Story) -> None:
    with_ai_spec(story_dir)
    story_dir.write(
        "technical",
        story_dir.read("technical").replace(
            '"REST", "[existing] Accepts imports"', '"gRPC", "[existing] Accepts imports"'
        ),
    )
    result = check(story_dir)
    assert crit(result, "AIS-G04").status == "not-met"
    assert "ART-004 changed since technical was approved" in crit(result, "AIS-G04").reason
    assert any(f.code == "artifact-changed-since-approval" and f.where == "AIS-013" for f in result.findings)


def test_a_change_to_other_text_of_the_stage_leaves_the_artefact_and_the_sources_current(story_dir: Story) -> None:
    with_ai_spec(story_dir)
    story_dir.write("technical", story_dir.read("technical").replace("three times", "four times"))
    result = check(story_dir)
    assert crit(result, "AIS-G04").status == "met"
    assert crit(result, "AIS-G02").status == "met", "only an item's own change makes it an unapproved source (FR-002)"


def test_a_referenced_artefact_that_was_removed_is_a_dangling_trace_not_current(story_dir: Story) -> None:
    with_ai_spec(story_dir)
    story_dir.write("technical", technical_doc(er=None, not_applicable="- Data Model: none"))
    result = check(story_dir)
    assert "dangling-trace" in codes(result) and crit(result, "AIS-G02").status == "not-met"


def test_an_artefact_added_after_approval_was_never_approved(story_dir: Story) -> None:
    with_ai_spec(story_dir)
    extra = "**ART-020**: A new view (traces: FR-001, DEC-001)\n\n" + mermaid(
        'C4Container\n  Person(u, "Data Analyst", "[existing] x")'
    )
    story_dir.write(
        "technical",
        story_dir.read("technical").replace("## Not applicable\n", f"{extra}\n## Not applicable\n"),
    )
    story_dir.write(
        "ai-spec",
        story_dir.read("ai-spec").replace(
            "## Not applicable", "**AIS-020**: Read it. (traces: ART-020)\n\n## Not applicable", 1
        ),
    )
    result = check(story_dir)
    assert "ART-020 was not part of the approval of technical" in crit(result, "AIS-G04").reason


def test_an_artefact_reference_needs_no_check_when_the_stage_holds_no_approval_yet(story_dir: Story) -> None:
    with_ai_spec(story_dir)
    text = story_dir.read("technical")
    start = text.index("<!-- eil:begin approval -->")
    end = text.index("<!-- eil:end approval -->") + len("<!-- eil:end approval -->")
    story_dir.write(
        "technical", text[:start] + "<!-- eil:begin approval -->\n<!-- eil:end approval -->" + text[end:]
    )
    result = check(story_dir)
    assert crit(result, "AIS-G04").status == "met"  # the missing approval is reported by AIS-G02 instead
    assert (
        "which is draft" in crit(result, "AIS-G02").reason
        or "which is in-review" in crit(result, "AIS-G02").reason
    )


# ---- no diagram of its own (FR-082)


def test_an_art_item_in_the_ai_specification_is_the_wrong_level(story_dir: Story) -> None:
    body = "**ART-030**: My own view (traces: DEC-001)\n\n" + mermaid(
        'C4Container\n  Person(u, "Data Analyst", "x")'
    )
    with_ai_spec(story_dir, sections={"Interfaces": body})
    result = check(story_dir)
    assert (
        crit(result, "AIS-G05").status == "not-met"
        and "artifact-wrong-level" in crit(result, "AIS-G05").reason
    )


def test_a_bare_diagram_fence_is_reported_too(story_dir: Story) -> None:
    with_ai_spec(story_dir, sections={"Interfaces": mermaid("sequenceDiagram\n  A->>B: hi")})
    result = check(story_dir)
    assert crit(result, "AIS-G05").status == "not-met" and "artifact-unregistered" in codes(result)


# ---- overrides and the state of the stage


@pytest.mark.parametrize("criterion", ["AIS-G01", "AIS-G02", "AIS-G04", "AIS-G05"])
def test_any_criterion_can_be_overridden_by_a_named_confirmer(story_dir: Story, criterion: str) -> None:
    override = {
        "id": "OVR-001",
        "stage": "ai-spec",
        "criterion": criterion,
        "by": "Ada Dev",
        "reason": "accepted",
        "at": "2026-09-25T00:00:00Z",
    }
    sections: dict[str, str | None] = {"Business Rules": "**AIS-002**: A rule."}
    with_ai_spec(story_dir, sections=sections, extra=record_block("override", override))
    assert crit(check(story_dir), criterion).status in ("met", "overridden")


def test_a_met_gate_puts_the_stage_in_review_and_never_approved(story_dir: Story, tmp_path: Path) -> None:
    with_ai_spec(story_dir)
    check(story_dir)
    assert Package(story_dir.root).state("ai-spec").state == "in-review"
