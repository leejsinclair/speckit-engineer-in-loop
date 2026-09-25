"""REQ to FR coverage in both directions (task T061; FR-025, FR-028)."""

from __future__ import annotations

from eil.trace import coverage_gaps, parse_text


def gaps(requirements: str, functional: str):
    return coverage_gaps(parse_text(requirements), parse_text(functional))


def test_a_fully_traced_pair_has_no_gaps() -> None:
    result = gaps(
        "**REQ-001**: A\n\n**UC-001**: B\n",
        "**FR-001**: X (traces: REQ-001)\n\n**FR-002**: Y (traces: UC-001)\n",
    )
    assert (result.untraceable, result.uncovered_requirements) == ([], [])


def test_every_requirement_needs_at_least_one_functional_requirement() -> None:
    result = gaps("**REQ-001**: A\n\n**REQ-002**: B\n", "**FR-001**: X (traces: REQ-001)\n")
    assert result.uncovered_requirements == ["REQ-002"] and result.untraceable == []


def test_every_functional_requirement_needs_a_requirement_or_use_case() -> None:
    result = gaps("**REQ-001**: A\n", "**FR-001**: X (traces: REQ-001)\n\n**FR-002**: Y\n")
    assert result.untraceable == ["FR-002"] and result.uncovered_requirements == []


def test_gaps_are_listed_in_both_directions_at_once() -> None:
    result = gaps("**REQ-001**: A\n\n**REQ-002**: B\n", "**FR-001**: X (traces: REQ-001)\n\n**FR-003**: Z\n")
    assert result.uncovered_requirements == ["REQ-002"] and result.untraceable == ["FR-003"]


def test_a_non_functional_requirement_can_cover_a_requirement() -> None:
    result = gaps(
        "**REQ-001**: A\n\n**REQ-002**: B\n",
        "**FR-001**: X (traces: REQ-001)\n\n**NFR-001**: Q (traces: REQ-002)\n",
    )
    assert result.uncovered_requirements == []


def test_a_trace_to_something_that_is_not_a_requirement_or_use_case_is_not_enough() -> None:
    result = gaps("**REQ-001**: A\n", "**FR-001**: X (traces: REQ-001)\n\n**FR-002**: Y (traces: FR-001)\n")
    assert result.untraceable == ["FR-002"]


def test_a_trace_to_an_id_the_requirements_do_not_define_is_not_enough() -> None:
    result = gaps("**REQ-001**: A\n", "**FR-001**: X (traces: REQ-001)\n\n**FR-002**: Y (traces: REQ-099)\n")
    assert result.untraceable == ["FR-002"]


def test_one_requirement_can_be_covered_by_several_and_one_can_cover_several() -> None:
    result = gaps(
        "**REQ-001**: A\n\n**REQ-002**: B\n",
        "**FR-001**: X (traces: REQ-001, REQ-002)\n\n**FR-002**: Y (traces: REQ-001)\n",
    )
    assert (result.untraceable, result.uncovered_requirements) == ([], [])


def test_use_cases_are_not_required_to_have_a_functional_requirement() -> None:
    result = gaps("**REQ-001**: A\n\n**UC-001**: B\n", "**FR-001**: X (traces: REQ-001)\n")
    assert result.uncovered_requirements == [] and result.uncovered_use_cases == ["UC-001"]


def test_no_requirements_and_no_functional_requirements_is_no_gap() -> None:
    result = gaps("", "")
    assert (result.untraceable, result.uncovered_requirements, result.uncovered_use_cases) == ([], [], [])
