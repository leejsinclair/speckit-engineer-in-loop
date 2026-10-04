"""The Completion gate and approval (task T109; FR-063 to FR-065, FR-084).

Completion is approved by a person who says they reviewed the evidence. It is refused while the
Verification document is missing, or while a requirement or an approved artefact is unverified
without an exception, unless a named override is recorded.
"""

from __future__ import annotations

import pytest
from eil.gates import CRITERIA_BY_STAGE, CriterionResult, GateResult, check_stage
from eil.identity import Config
from eil.package import Package
from eil.records import approve
from eil.results import EilExit

from tests.helpers.package import (
    VERIFY_TARGETS,
    Story,
    completion_doc,
    evidence_row,
    record_block,
    verification_doc,
    with_verification,
)

CONFIG = Config(
    default_developer="Ada Dev",
    approvers={
        "requirements": ["Ada Dev"],
        "functional": ["Ada Dev"],
        "technical": ["Ada Dev"],
        "completion": ["Ada Dev"],
    },
    abbreviation_authorisers=[],
)
YES = "Yes, I reviewed the evidence and the story is done."


def ready(story: Story, rows: list[str] | None = None, **sections: object) -> Package:
    with_verification(story, rows)
    story.write("completion", completion_doc(**sections))  # type: ignore[arg-type]
    return Package(story.root)


def gate(package: Package) -> GateResult:
    return check_stage(package, "completion")


def crit(result: GateResult, criterion_id: str) -> CriterionResult:
    return next(c for c in result.criteria if c.id == criterion_id)


def rows_with(*changes: tuple[str, dict]) -> list[str]:
    overrides = dict(changes)
    return [evidence_row(i, t, **overrides.get(t, {})) for i, t in enumerate(VERIFY_TARGETS, 1)]


def refused(package: Package, by: str = "Ada Dev", attestation: str = YES) -> list[str]:
    with pytest.raises(EilExit) as exc:
        approve(package, CONFIG, "completion", by, attestation)
    return [r["code"] for r in exc.value.payload["refusals"]]


def override(criterion: str) -> str:
    return record_block(
        "override",
        {
            "id": "OVR-001",
            "stage": "completion",
            "criterion": criterion,
            "by": "Ada Dev",
            "reason": "accepted",
            "at": "2026-09-25T00:00:00Z",
        },
    )


# ---- the table


def test_the_table_lists_the_sections_the_verification_the_two_statuses_and_the_currency() -> None:
    table = CRITERIA_BY_STAGE["completion"]
    assert [c.id for c in table] == [f"CMP-G{n:02d}" for n in range(1, 9)]
    assert all(c.kind in ("structural", "traceability") for c in table)


def test_a_complete_story_meets_the_gate_and_can_be_approved(story_dir: Story) -> None:
    package = ready(story_dir)
    result = gate(package)
    assert result.ok, [(c.id, c.reason) for c in result.criteria if c.status != "met"]
    approved = approve(package, CONFIG, "completion", "Ada Dev", YES)
    assert approved["approval"]["stage"] == "completion" and approved["approval"]["attestation"] == YES
    assert package.state("completion").state == "approved"


# ---- the sections (FR-063)


@pytest.mark.parametrize(
    "section",
    [
        "Completion Status",
        "Implementation Summary",
        "Requirements Satisfied",
        "Outstanding Issues",
        "Accepted Deviations",
        "Relevant Technical Decisions",
        "Verification Summary",
        "Deployment Status",
        "Documentation and Support Implications",
        "Diagram Currency",
    ],
)
def test_every_section_of_fr_063_and_the_diagram_currency_is_required(story_dir: Story, section: str) -> None:
    package = ready(story_dir, sections={section: None})
    assert f"missing section '{section}'" in crit(gate(package), "CMP-G01").reason


# ---- the verification must exist and be reviewed (FR-064)


def test_completion_is_refused_without_a_verification_document(story_dir: Story) -> None:
    package = ready(story_dir)
    story_dir.path("verification").unlink()
    assert "verification-missing" in refused(package)
    assert "verification document" in crit(gate(package), "CMP-G02").reason


def test_a_person_must_give_their_own_confirmation_that_the_evidence_was_reviewed(story_dir: Story) -> None:
    package = ready(story_dir)
    assert refused(package, attestation="   ") == ["attestation-required"]
    assert "ai-approval" in refused(package, by="Claude")
    assert "not-a-confirmer" in refused(package, by="Mallory")


def test_nothing_is_written_on_a_refusal(story_dir: Story) -> None:
    package = ready(story_dir, rows_with(("REQ-001", {"status": "unverified"})))
    before = story_dir.path("completion").read_bytes()
    refused(package)
    assert story_dir.path("completion").read_bytes() == before


# ---- unverified requirements and artefacts (FR-065)


def test_an_unverified_requirement_refuses_completion(story_dir: Story) -> None:
    package = ready(story_dir, rows_with(("REQ-001", {"status": "unverified"})))
    assert refused(package) == ["unverified-requirement"]
    assert "REQ-001 is unverified" in crit(gate(package), "CMP-G03").reason


def test_a_failed_requirement_refuses_completion_too(story_dir: Story) -> None:
    package = ready(story_dir, rows_with(("REQ-001", {"status": "failed"})))
    assert refused(package) == ["unverified-requirement"]
    assert "REQ-001 is failed" in crit(gate(package), "CMP-G03").reason


def test_a_requirement_with_no_row_at_all_is_unverified(story_dir: Story) -> None:
    package = ready(story_dir, [r for r in rows_with() if "(traces: REQ-001)" not in r])
    assert refused(package) == ["unverified-requirement"]


def test_an_excepted_requirement_with_a_named_exception_does_not_block(story_dir: Story) -> None:
    rows = rows_with(("REQ-001", {"status": "excepted", "accepted_by": "Ada Dev", "reason": "next release"}))
    package = ready(story_dir, rows)
    assert crit(gate(package), "CMP-G03").status == "met"
    assert approve(package, CONFIG, "completion", "Ada Dev", YES)["ok"]


def test_an_excepted_row_without_who_and_why_is_still_unverified(story_dir: Story) -> None:
    package = ready(story_dir, rows_with(("REQ-001", {"status": "excepted"})))
    assert refused(package) == ["unverified-requirement"]


def test_only_requirements_count_for_the_requirement_criterion(story_dir: Story) -> None:
    package = ready(story_dir, rows_with(("FR-001", {"status": "unverified"})))
    assert crit(gate(package), "CMP-G03").status == "met"


def test_an_unverified_artefact_refuses_completion(story_dir: Story) -> None:
    package = ready(story_dir, rows_with(("ART-007", {"status": "unverified"})))
    assert refused(package) == ["unverified-artifact"]
    assert "ART-007 is unverified" in crit(gate(package), "CMP-G04").reason


def test_a_requirement_and_an_artefact_both_unverified_report_both_together(story_dir: Story) -> None:
    rows = rows_with(("REQ-001", {"status": "unverified"}), ("ART-004", {"status": "unverified"}))
    assert sorted(refused(ready(story_dir, rows))) == ["unverified-artifact", "unverified-requirement"]


def test_a_named_override_lets_completion_proceed_and_stays_visible(story_dir: Story) -> None:
    rows = rows_with(("REQ-001", {"status": "unverified"}))
    with_verification(story_dir, rows)
    story_dir.write("completion", completion_doc(extra=override("CMP-G03")))
    package = Package(story_dir.root)
    assert crit(gate(package), "CMP-G03").status == "overridden"
    result = approve(package, CONFIG, "completion", "Ada Dev", YES)
    assert result["approval"]["overrides_used"] == ["OVR-001"]


# ---- the diagram currency (FR-084)


def test_every_approved_artefact_needs_a_currency_line(story_dir: Story) -> None:
    lines = "\n".join(
        f"- {a}: current" for a in ("ART-001", "ART-002", "ART-003", "ART-004", "ART-005", "ART-006")
    )
    package = ready(story_dir, sections={"Diagram Currency": lines})
    assert "ART-007 has no line under Diagram Currency" in crit(gate(package), "CMP-G05").reason


def test_a_deviation_names_who_accepted_it_and_why_and_is_listed_under_accepted_deviations(
    story_dir: Story,
) -> None:
    lines = "\n".join(
        f"- {a}: current" for a in ("ART-001", "ART-002", "ART-003", "ART-004", "ART-005", "ART-006")
    )
    deviation = "\n- ART-007: deviation"
    package = ready(story_dir, sections={"Diagram Currency": lines + deviation})
    reason = crit(gate(package), "CMP-G05").reason
    assert "ART-007 is a deviation but names no 'accepted by'" in reason and "no reason" in reason
    full = lines + "\n- ART-007: deviation, accepted by Ada Dev, because the index was renamed in review"
    accepted = ready(
        story_dir,
        sections={
            "Diagram Currency": full,
            "Accepted Deviations": "ART-007: the index was renamed in review.",
        },
    )
    assert crit(gate(accepted), "CMP-G05").status == "met"


def test_a_deviation_must_also_be_listed_under_accepted_deviations(story_dir: Story) -> None:
    lines = "\n".join(
        f"- {a}: current" for a in ("ART-001", "ART-002", "ART-003", "ART-004", "ART-005", "ART-006")
    )
    full = lines + "\n- ART-007: deviation, accepted by Ada Dev, because the index was renamed"
    package = ready(story_dir, sections={"Diagram Currency": full})
    assert "ART-007 is not listed under Accepted Deviations" in crit(gate(package), "CMP-G05").reason


def test_a_line_that_is_neither_current_nor_a_deviation_is_flagged(story_dir: Story) -> None:
    lines = "\n".join(
        f"- {a}: current" for a in ("ART-001", "ART-002", "ART-003", "ART-004", "ART-005", "ART-006")
    )
    package = ready(story_dir, sections={"Diagram Currency": lines + "\n- ART-007: probably fine"})
    assert "ART-007 is neither 'current' nor a 'deviation'" in crit(gate(package), "CMP-G05").reason


def test_the_ai_cannot_accept_a_deviation(story_dir: Story) -> None:
    lines = "\n".join(
        f"- {a}: current" for a in ("ART-001", "ART-002", "ART-003", "ART-004", "ART-005", "ART-006")
    )
    full = lines + "\n- ART-007: deviation, accepted by Claude, because it is fine"
    package = ready(story_dir, sections={"Diagram Currency": full, "Accepted Deviations": "ART-007"})
    assert "accepted by 'Claude'" in crit(gate(package), "CMP-G05").reason


# ---- earlier stages and the upstream chain


def test_completion_needs_the_three_definition_stages_approved(story_dir: Story) -> None:
    package = ready(story_dir)
    text = story_dir.read("technical").replace("three times", "four times")
    story_dir.write("technical", text)
    assert "stage-not-approved" in refused(package)


def test_the_verification_document_can_be_present_but_open_tasks_do_not_block_completion_here(
    story_dir: Story,
) -> None:
    package = ready(story_dir)
    assert crit(gate(package), "CMP-G02").status == "met"
    with_open = verification_doc(open_tasks=["T001"])
    story_dir.write("verification", with_open)
    assert approve(package, CONFIG, "completion", "Ada Dev", YES)["ok"]


# ---- untouched artefacts need no question (FR-033)

ALL_ARTS = ("ART-001", "ART-002", "ART-003", "ART-004", "ART-005", "ART-006", "ART-007")


def test_untouched_artefacts_are_covered_by_one_untouched_line(story_dir: Story) -> None:
    package = ready(story_dir, sections={"Diagram Currency": "- untouched: " + ", ".join(ALL_ARTS)})
    assert crit(gate(package), "CMP-G05").status == "met"


def test_an_untouched_line_beside_individual_lines(story_dir: Story) -> None:
    lines = "- ART-004: current\n- untouched: " + ", ".join(a for a in ALL_ARTS if a != "ART-004")
    assert crit(gate(ready(story_dir, sections={"Diagram Currency": lines})), "CMP-G05").status == "met"


def test_an_artefact_on_neither_an_untouched_line_nor_its_own_line_is_missing(story_dir: Story) -> None:
    package = ready(story_dir, sections={"Diagram Currency": "- untouched: " + ", ".join(ALL_ARTS[:6])})
    assert "ART-007 has no line under Diagram Currency" in crit(gate(package), "CMP-G05").reason


def test_a_touched_artefact_cannot_hide_on_the_untouched_line(
    story_dir: Story, monkeypatch: pytest.MonkeyPatch
) -> None:
    from eil import staleness

    monkeypatch.setattr(
        staleness, "touched_artifacts", lambda pkg: {"ART-004": "T001 carries code that reaches it"}
    )
    package = ready(story_dir, sections={"Diagram Currency": "- untouched: " + ", ".join(ALL_ARTS)})
    result = crit(gate(package), "CMP-G05")
    assert result.status == "not-met"
    assert "ART-004 is listed untouched but implementation touched it" in result.reason


def test_a_touched_artefact_needs_its_own_line(story_dir: Story, monkeypatch: pytest.MonkeyPatch) -> None:
    from eil import staleness

    monkeypatch.setattr(staleness, "touched_artifacts", lambda pkg: {"ART-004": "changed"})
    lines = "- untouched: " + ", ".join(a for a in ALL_ARTS if a != "ART-004")
    assert (
        "ART-004 has no line under Diagram Currency"
        in crit(gate(ready(story_dir, sections={"Diagram Currency": lines})), "CMP-G05").reason
    )
    assert (
        crit(
            gate(ready(story_dir, sections={"Diagram Currency": lines + "\n- ART-004: current"})), "CMP-G05"
        ).status
        == "met"
    )
