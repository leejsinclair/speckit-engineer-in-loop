"""Work-scoped ``enter`` (T021; determinism requirement 27; FR-004, FR-025, FR-038, D-35)."""

from __future__ import annotations

from typing import Any

import pytest
from eil.handoff import enter
from eil.results import EilExit

from tests.helpers.derived import (
    change_dec3,
    clear_approval,
    edit,
    package_of,
    reapprove_technical,
    revert_dec3,
    settle_derived,
    wire_tasks_to_dec3,
)
from tests.helpers.package import Story


@pytest.fixture
def story(reference_story: Story) -> Story:
    wire_tasks_to_dec3(reference_story)
    settle_derived(reference_story)
    return reference_story


def entered(story: Story, command: str, **kwargs: Any) -> dict[str, Any]:
    return enter(package_of(story), command, **kwargs)


def refused(story: Story, command: str, **kwargs: Any) -> list[dict[str, Any]]:
    with pytest.raises(EilExit) as exc:
        entered(story, command, **kwargs)
    assert exc.value.code == 1
    return exc.value.payload["refusals"]


def blocked_ids(result: dict[str, Any]) -> set[str]:
    return {b["id"] for b in result["blocked"]}


def test_an_unaffected_task_may_proceed_when_another_is_blocked(story: Story) -> None:
    change_dec3(story)
    result = entered(story, "implement", task="T007")
    assert result["ok"] and result["command"] == "implement"
    assert "T007" not in blocked_ids(result)
    assert "T009" in blocked_ids(result)


def test_a_blocked_task_is_refused_naming_the_source_and_the_fix(story: Story) -> None:
    change_dec3(story)
    (refusal,) = refused(story, "implement", task="T009")
    assert refusal["code"] == "work-blocked"
    assert "DEC-003" in refusal["message"] and "T009" in refusal["message"]
    assert "/speckit-eil-accept technical" in refusal["fix"]


def test_without_a_task_implement_proceeds_except_for_the_blocked(story: Story) -> None:
    change_dec3(story)
    result = entered(story, "implement")
    (row,) = [b for b in result["blocked"] if b["id"] == "T009"]
    assert row["because"] and "DEC-003" in " ".join(row["because"])
    assert "/speckit-eil-accept technical" in row["fix"]
    assert "except T009" in result["text"]


def test_a_revert_lets_the_blocked_task_proceed(story: Story) -> None:
    change_dec3(story)
    assert refused(story, "implement", task="T009")
    revert_dec3(story)
    result = entered(story, "implement", task="T009")
    assert result["blocked"] == [] and result["rederive"] == []


def test_a_named_task_that_does_not_exist_is_refused(story: Story) -> None:
    assert [r["code"] for r in refused(story, "implement", task="T999")] == ["unknown-item"]


def test_nothing_may_proceed_is_work_blocked(story: Story) -> None:
    text = story.read("tasks")
    for n in range(7, 13):
        text = text.replace(f"(traces: AIS-{n:03d})", "(traces: AIS-014)")
    story.write("tasks", text)
    settle_derived(story)
    change_dec3(story)
    assert [r["code"] for r in refused(story, "implement")] == ["work-blocked"]


def test_a_stage_that_was_never_approved_still_refuses(story: Story) -> None:
    clear_approval(story, "technical")
    refusals = refused(story, "plan")
    assert "stage-not-approved" in [r["code"] for r in refusals]
    assert "technical" in next(r for r in refusals if r["code"] == "stage-not-approved")["message"]


def test_a_stage_needing_re_review_does_not_refuse_wholesale(story: Story) -> None:
    change_dec3(story)
    assert package_of(story).state("technical").state == "needs-re-review"
    result = entered(story, "plan")
    assert result["ok"]
    assert "§Project Structure" in blocked_ids(result)
    assert "§Queue Design" not in blocked_ids(result)
    assert result["rederive"] == []


def test_after_the_source_is_accepted_the_dependants_can_be_rederived(story: Story) -> None:
    change_dec3(story)
    reapprove_technical(story)
    plan = entered(story, "plan")
    assert set(plan["rederive"]) == {"AIS-014", "§Project Structure"}
    assert "§Project Structure" not in blocked_ids(plan)
    tasks = entered(story, "implement")
    assert "T009" in blocked_ids(tasks)
    row = next(b for b in tasks["blocked"] if b["id"] == "T009")
    assert "AIS-014" in " ".join(row["because"]) and "AIS-014" in row["fix"]
    assert "AIS-014" in tasks["rederive"]


def test_a_pending_clarification_blocks_only_the_tasks_tracing_to_it(story: Story) -> None:
    edit(story, "ai-spec", "**AIS-007**: Implement", "**AIS-007**: [pending-clarification] Implement")
    (refusal,) = refused(story, "implement", task="T007")
    assert refusal["code"] == "work-blocked" and "AIS-007" in refusal["message"]
    ok = entered(story, "implement", task="T008")
    assert blocked_ids(ok) == {"AIS-007", "T007"}
    entry = next(b for b in ok["blocked"] if b["id"] == "AIS-007")
    assert "pending" in " ".join(entry["because"]) and "/speckit-eil-resolve" in entry["fix"]


def test_an_ai_spec_item_without_a_source_is_a_per_item_entry(story: Story) -> None:
    edit(
        story,
        "ai-spec",
        "**AIS-008**: Implement behaviour 8. (traces: FR-008)",
        "**AIS-008**: Implement behaviour 8.",
    )
    result = entered(story, "plan")
    assert "AIS-008" in blocked_ids(result)
    assert "no approved source" in " ".join(
        next(b for b in result["blocked"] if b["id"] == "AIS-008")["because"]
    )


def test_enter_never_writes_a_stage_document(story: Story) -> None:
    change_dec3(story)
    before = {s: story.path(s).read_bytes() for s in package_of(story).existing_stages()}
    entered(story, "implement")
    assert {s: story.path(s).read_bytes() for s in before} == before
