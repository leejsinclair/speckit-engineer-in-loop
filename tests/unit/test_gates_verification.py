"""The Verification gate (task T108; FR-059 to FR-062, edge case "open tasks at verification start").

The document records evidence and never declares completion. Every requirement, functional
requirement and approved artefact has a row with a status, and every exception names who and why.
"""

from __future__ import annotations

import pytest
from eil import verification
from eil.gates import CRITERIA_BY_STAGE, CriterionResult, GateResult, check_stage
from eil.package import Package

from tests.helpers.package import (
    VERIFY_TARGETS,
    Story,
    evidence_row,
    verification_doc,
    with_verification,
)


def check(story: Story) -> GateResult:
    return check_stage(Package(story.root), "verification")


def crit(result: GateResult, criterion_id: str) -> CriterionResult:
    return next(c for c in result.criteria if c.id == criterion_id)


def rows_for(*overrides: tuple[str, dict]) -> list[str]:
    """One row per default target, with keyword overrides for named targets."""
    changes = dict(overrides)
    return [evidence_row(i, t, **changes.get(t, {})) for i, t in enumerate(VERIFY_TARGETS, 1)]


# ---- the table


def test_the_table_has_seven_criteria_all_decided_by_code() -> None:
    table = CRITERIA_BY_STAGE["verification"]
    assert [c.id for c in table] == [f"VER-G{n:02d}" for n in range(1, 8)]
    assert {c.kind for c in table} <= {"structural", "traceability"}


def test_a_complete_document_meets_the_gate_and_the_stage_is_in_review_never_approved(
    story_dir: Story,
) -> None:
    with_verification(story_dir)
    result = check(story_dir)
    assert result.ok, [(c.id, c.reason) for c in result.criteria if c.status != "met"]
    assert Package(story_dir.root).state("verification").state in ("in-review", "reviewed")  # 003 D-58: reviewed when every block is settled


# ---- the sections (FR-060)


@pytest.mark.parametrize("section", ["Automated Evidence", "Manual Evidence", "Exceptions", "Open Tasks"])
def test_the_document_separates_automated_manual_exceptions_and_open_tasks(
    story_dir: Story, section: str
) -> None:
    with_verification(story_dir, sections={section: None})
    assert f"missing section '{section}'" in crit(check(story_dir), "VER-G01").reason


# ---- every item has a row and a status (FR-059)


@pytest.mark.parametrize("target", VERIFY_TARGETS)
def test_every_requirement_functional_requirement_and_approved_artefact_needs_a_row(
    story_dir: Story, target: str
) -> None:
    rows = [r for r in rows_for() if f"(traces: {target})" not in r]
    with_verification(story_dir, rows)
    result = check(story_dir)
    assert crit(result, "VER-G02").status == "not-met"
    assert f"{target} has no verification row" in crit(result, "VER-G02").reason


def test_an_artefact_is_required_only_once_its_stage_is_approved(story_dir: Story) -> None:
    with_verification(story_dir)
    text = story_dir.read("technical")
    start = text.index("<!-- eil:begin approval -->")
    end = text.index("<!-- eil:end approval -->")
    story_dir.write("technical", text[:start] + "<!-- eil:begin approval -->\n" + text[end:])
    rows = [r for r in rows_for() if "(traces: ART-004)" not in r]
    story_dir.write("verification", verification_doc(rows))
    assert crit(check(story_dir), "VER-G02").status == "met"


def test_a_row_may_cover_several_targets(story_dir: Story) -> None:
    rows = [r for r in rows_for() if "(traces: FR-001)" not in r and "(traces: NFR-001)" not in r] + [
        "**EVD-020**: Both by one test (traces: FR-001, NFR-001) (status: verified)\nKind: automated\nEvidence: tests/x.py"
    ]
    with_verification(story_dir, rows)
    assert crit(check(story_dir), "VER-G02").status == "met"


def test_a_row_with_no_status_is_flagged(story_dir: Story) -> None:
    rows = rows_for()
    rows[1] = "**EVD-002**: Evidence for FR-001 (traces: FR-001)\nKind: automated\nEvidence: tests/x.py"
    with_verification(story_dir, rows)
    assert "EVD-002 has no status" in crit(check(story_dir), "VER-G03").reason


def test_a_status_must_be_one_of_the_four() -> None:
    from eil.trace import parse_text

    result = parse_text("**EVD-001**: X (traces: FR-001) (status: done)\n")
    assert [f.code for f in result.findings] == ["malformed-item"]


@pytest.mark.parametrize("status", ["verified", "failed"])
def test_a_verified_or_failed_row_names_its_kind_and_its_evidence(story_dir: Story, status: str) -> None:
    rows = rows_for()
    rows[1] = f"**EVD-002**: Evidence for FR-001 (traces: FR-001) (status: {status})"
    with_verification(story_dir, rows)
    reason = crit(check(story_dir), "VER-G03").reason
    assert "EVD-002 has no kind (automated or manual)" in reason and "EVD-002 has no evidence" in reason


def test_the_kind_is_automated_or_manual(story_dir: Story) -> None:
    rows = rows_for(("FR-001", {"kind": "guesswork"}))
    with_verification(story_dir, rows)
    assert "EVD-002 has kind 'guesswork'" in crit(check(story_dir), "VER-G03").reason


def test_an_unverified_row_needs_no_evidence_but_still_counts_as_a_status(story_dir: Story) -> None:
    rows = rows_for(("FR-001", {"status": "unverified"}))
    with_verification(story_dir, rows)
    result = check(story_dir)
    assert crit(result, "VER-G03").status == "met" and crit(result, "VER-G02").status == "met"


# ---- exceptions record who and why (FR-061)


def test_an_exception_names_who_accepted_it_and_why(story_dir: Story) -> None:
    rows = rows_for(("NFR-001", {"status": "excepted"}))
    with_verification(story_dir, rows)
    reason = crit(check(story_dir), "VER-G04").reason
    assert "EVD-003 is excepted and names no 'Accepted by'" in reason and "no 'Reason'" in reason


def test_an_exception_with_both_is_accepted(story_dir: Story) -> None:
    rows = rows_for(
        ("NFR-001", {"status": "excepted", "accepted_by": "Ada Dev", "reason": "load test is next sprint"})
    )
    with_verification(story_dir, rows)
    assert crit(check(story_dir), "VER-G04").status == "met"


def test_the_ai_cannot_accept_an_exception(story_dir: Story) -> None:
    rows = rows_for(("NFR-001", {"status": "excepted", "accepted_by": "Claude", "reason": "fine"}))
    with_verification(story_dir, rows)
    assert "accepted by 'Claude'" in crit(check(story_dir), "VER-G04").reason


# ---- open tasks are listed, not hidden


def test_every_open_task_of_the_task_list_is_named_under_open_tasks(story_dir: Story) -> None:
    with_verification(story_dir, open_tasks=["T001", "T003"])
    reason = crit(check(story_dir), "VER-G05").reason
    assert "T002" in reason and "T004" in reason and "T001" not in reason


def test_a_finished_task_needs_no_listing(story_dir: Story) -> None:
    with_verification(story_dir, open_tasks=["T001", "T003", "T004"])
    tasks = story_dir.read("tasks").replace("- [ ] T002", "- [x] T002")
    story_dir.write("tasks", tasks)
    assert crit(check(story_dir), "VER-G05").status == "met"


def test_no_open_task_may_be_hidden_by_saying_none(story_dir: Story) -> None:
    with_verification(story_dir, open_tasks=[])
    assert crit(check(story_dir), "VER-G05").status == "not-met"


# ---- it never declares completion (FR-062)


@pytest.mark.parametrize(
    "claim",
    ["The story is complete.", "The feature is now done.", "This work is completed."],
)
def test_a_declaration_of_completion_is_flagged(story_dir: Story, claim: str) -> None:
    with_verification(story_dir, sections={"Exceptions": claim})
    assert "declares completion" in crit(check(story_dir), "VER-G06").reason


def test_a_completion_heading_or_an_approval_record_is_flagged(story_dir: Story) -> None:
    with_verification(story_dir, sections={"Completion": "All done."})
    assert "declares completion" in crit(check(story_dir), "VER-G06").reason


def test_the_word_complete_in_an_ordinary_sentence_is_not_a_declaration(story_dir: Story) -> None:
    with_verification(story_dir, sections={"Exceptions": "Coverage of the migration is not complete yet."})
    assert crit(check(story_dir), "VER-G06").status == "met"


# ---- the derived statuses (used by completion)


def statuses(story: Story) -> dict[str, str]:
    return verification.statuses(Package(story.root))


def test_a_target_with_no_row_is_unverified(story_dir: Story) -> None:
    rows = [r for r in rows_for() if "(traces: FR-001)" not in r]
    with_verification(story_dir, rows)
    assert statuses(story_dir)["FR-001"] == "unverified" and statuses(story_dir)["REQ-001"] == "verified"


@pytest.mark.parametrize(
    ("row_statuses", "expected"),
    [
        (["verified"], "verified"),
        (["verified", "verified"], "verified"),
        (["verified", "failed"], "failed"),
        (["verified", "unverified"], "unverified"),
        (["verified", "excepted"], "excepted"),
        (["excepted"], "excepted"),
        (["failed", "unverified"], "failed"),
    ],
)
def test_a_target_takes_the_worst_status_of_its_rows(
    story_dir: Story, row_statuses: list[str], expected: str
) -> None:
    rows = [r for r in rows_for() if "(traces: FR-001)" not in r]
    for n, status in enumerate(row_statuses, 20):
        rows.append(evidence_row(n, "FR-001", status, accepted_by="Ada Dev", reason="later"))
    with_verification(story_dir, rows)
    assert statuses(story_dir)["FR-001"] == expected


def test_a_code_link_on_a_row_is_parsed(story_dir: Story) -> None:
    rows = rows_for()
    rows[1] = evidence_row(2, "FR-001", code=" (code: abc1234, PR#12)")
    with_verification(story_dir, rows)
    from eil.trace import parse_document

    item = next(
        i for i in parse_document(Package(story_dir.root).doc("verification")).items if i.id == "EVD-002"
    )
    assert item.code == ["abc1234", "PR#12"]
