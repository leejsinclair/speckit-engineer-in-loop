"""Scoped staleness (T020; determinism requirement 26; FR-002, FR-003, FR-007, D-34)."""

from __future__ import annotations

import pytest
from eil import blockstatus, staleness

from tests.helpers.derived import (
    change_dec3,
    edit,
    package_of,
    revert_dec3,
    settle_derived,
    wire_tasks_to_dec3,
)
from tests.helpers.package import Story

DEC3_DEPENDANTS = {"AIS-014", "T004", "T005", "T006", "T009", "§Project Structure"}


@pytest.fixture
def story(reference_story: Story) -> Story:
    wire_tasks_to_dec3(reference_story)
    settle_derived(reference_story)
    return reference_story


def stale_keys(story: Story) -> set[str]:
    return set(staleness.blocked_work(package_of(story)))


def status_of(story: Story, stage: str, key: str) -> blockstatus.BlockInfo:
    return blockstatus.block_statuses(package_of(story))[stage][key]


def test_nothing_is_stale_once_the_sources_are_recorded(story: Story) -> None:
    assert stale_keys(story) == set()
    assert blockstatus.counts(package_of(story), "tasks")["settled"] == 12


def test_changing_one_decision_marks_exactly_its_direct_and_transitive_dependants(story: Story) -> None:
    change_dec3(story)
    assert stale_keys(story) == DEC3_DEPENDANTS
    assert status_of(story, "ai-spec", "AIS-014").stale
    assert status_of(story, "tasks", "T004").stale
    assert not status_of(story, "ai-spec", "AIS-013").stale
    assert not status_of(story, "tasks", "T007").stale


def test_the_cause_names_the_changed_source(story: Story) -> None:
    change_dec3(story)
    work = staleness.blocked_work(package_of(story))
    assert any("DEC-003" in cause for cause in work["AIS-014"])
    assert any("DEC-003" in cause and "AIS-014" in cause for cause in work["T004"])


def test_reverting_the_change_clears_staleness_with_no_command(story: Story) -> None:
    change_dec3(story)
    assert stale_keys(story)
    revert_dec3(story)
    assert stale_keys(story) == set()
    assert not status_of(story, "tasks", "T004").stale


def test_a_multi_source_item_goes_stale_when_one_source_changes(story: Story) -> None:
    edit(story, "ai-spec", "(traces: DEC-004)", "(traces: DEC-004, DEC-003)")
    settle_derived(story)
    assert "AIS-015" not in stale_keys(story)
    change_dec3(story)
    assert "AIS-015" in stale_keys(story)


def test_a_whitespace_only_change_does_nothing(story: Story) -> None:
    edit(story, "technical", "Reason for decision 3.", "Reason for decision 3.   ")
    assert stale_keys(story) == set()


def test_a_change_outside_the_traced_chain_reaches_nobody(story: Story) -> None:
    edit(story, "technical", "Reason for decision 5.", "A different reason for decision 5.")
    assert stale_keys(story) == {"AIS-016", "§Audit Design"}


def test_a_stale_dependant_does_not_taint_a_sibling_source(story: Story) -> None:
    change_dec3(story)
    for key in ("AIS-001", "AIS-013", "T001", "T012"):
        assert key not in stale_keys(story)


def test_a_cycle_is_a_document_error_and_cannot_hang(story: Story) -> None:
    edit(story, "ai-spec", "(traces: FR-001)", "(traces: AIS-002)")
    edit(story, "ai-spec", "(traces: FR-002)", "(traces: AIS-001)")
    problems = staleness.problems(package_of(story))
    assert "trace-cycle" in {code for code, _ in problems}
    assert {"AIS-001", "AIS-002"} <= stale_keys(story)


def test_a_dangling_id_is_a_document_error_not_unaffected(story: Story) -> None:
    edit(story, "tasks", "(traces: AIS-008)", "(traces: AIS-999)")
    problems = staleness.problems(package_of(story))
    assert ("dangling-trace", "T008 traces to AIS-999, which nothing defines") in problems
    assert "T008" in stale_keys(story)


def test_a_derived_block_with_no_recorded_sources_is_unknown_not_stale(reference_story: Story) -> None:
    from tests.helpers.derived import package_of as pkg

    change_dec3(reference_story)
    assert staleness.blocked_work(pkg(reference_story)) == {}
    counts = blockstatus.counts(pkg(reference_story), "ai-spec")
    assert counts["unknown"] > 0 and counts["stale"] == 0


def test_a_pending_clarification_blocks_only_its_own_dependants(story: Story) -> None:
    edit(story, "ai-spec", "**AIS-007**: Implement", "**AIS-007**: [pending-clarification] Implement")
    work = staleness.blocked_work(package_of(story))
    assert set(work) == {"AIS-007", "T007"}
    assert any("pending" in cause for cause in work["AIS-007"])
