"""Task snapshots and the ``tasks``, ``evidence`` and ``unknown-currency`` lists (T022; FR-005, FR-006,
FR-008, FR-049; determinism requirements 28 and 35)."""

from __future__ import annotations

from typing import Any

import pytest
from eil import blockstatus, reviews, staleness
from eil.gates import check_stage
from eil.records import approve
from eil.results import EilExit

from tests.helpers.derived import (
    CONFIG,
    answer_all,
    change_dec3,
    edit,
    package_of,
    settle_derived,
    wire_tasks_to_dec3,
)
from tests.helpers.package import Story, completion_doc, evidence_row, record_block

YES = "Yes, I reviewed the evidence and the story is done."
CLOSURE_T007 = {"AIS-007", "FR-007", "REQ-003"}


@pytest.fixture
def story(reference_story: Story) -> Story:
    wire_tasks_to_dec3(reference_story)
    settle_derived(reference_story)
    return reference_story


def record(story: Story, stage: str = "tasks") -> dict[str, Any]:
    obj = package_of(story).doc(stage).read_provenance().obj
    assert obj is not None
    return obj["blocks"]


def the_list(story: Story, stage: str, kind: str, **kwargs: Any) -> reviews.ReviewList:
    return reviews.build_list(package_of(story), stage, kind, **kwargs)


def keys(story: Story, stage: str, kind: str) -> list[str]:
    return [e.key for e in the_list(story, stage, kind).entries]


def approve_completion(story: Story) -> list[str]:
    story.write("completion", completion_doc())
    with pytest.raises(EilExit) as exc:
        approve(package_of(story), CONFIG, "completion", "Ada Dev", YES)
    return [r["code"] for r in exc.value.payload["refusals"]]


def tick(story: Story, task: str) -> None:
    edit(story, "tasks", f"- [ ] {task} ", f"- [x] {task} ")


# ---- snapshots


def test_sync_snapshots_a_newly_ticked_task_once(story: Story) -> None:
    tick(story, "T007")
    result = staleness.sync_task_snapshots(package_of(story))
    assert result["snapshotted"] == ["T007"] and result["completed_while_blocked"] == []
    entry = record(story)["T007"]
    assert set(entry["completed_against"]) == CLOSURE_T007 and entry["blocked_at_completion"] is False
    assert staleness.sync_task_snapshots(package_of(story))["snapshotted"] == []


def test_a_task_ticked_while_blocked_is_marked_and_listed(story: Story) -> None:
    change_dec3(story)
    tick(story, "T009")
    result = staleness.sync_task_snapshots(package_of(story))
    assert result["completed_while_blocked"] == ["T009"]
    assert record(story)["T009"]["blocked_at_completion"] is True
    assert "T009" in keys(story, "tasks", "tasks")


def test_unticking_a_task_clears_its_snapshot(story: Story) -> None:
    edit(story, "tasks", "- [x] T004 ", "- [ ] T004 ")
    staleness.sync_task_snapshots(package_of(story))
    assert "completed_against" not in record(story)["T004"]


def test_ticking_a_task_does_not_change_its_block(story: Story) -> None:
    tick(story, "T007")
    assert blockstatus.block_statuses(package_of(story))["tasks"]["T007"].status == "settled"


# ---- the tasks list


def test_nothing_is_listed_while_the_sources_are_unchanged(story: Story) -> None:
    assert keys(story, "tasks", "tasks") == []


def test_a_changed_source_puts_the_ticked_dependants_on_the_list(story: Story) -> None:
    change_dec3(story)
    listed = the_list(story, "tasks", "tasks")
    assert sorted(e.key for e in listed.entries) == ["T004", "T005", "T006"]
    assert listed.purpose == "revalidation"
    assert all("DEC-003" in e.why for e in listed.entries)


def test_the_list_puts_likely_rework_first_and_labels_the_ai_view(story: Story) -> None:
    change_dec3(story)
    views = {"T004": "still valid", "T005": "the queue code needs rework", "T006": "still valid"}
    listed = the_list(story, "tasks", "tasks", views=views)
    assert listed.entries[0].key == "T005"
    assert listed.entries[0].ai_view == "AI assessment: the queue code needs rework"


def test_ok_except_reconfirms_the_others_and_reopens_the_exception(story: Story) -> None:
    change_dec3(story)
    answer_all(story, "tasks", "tasks", reply="ok except T005", all_=False, all_except=["T005"])
    assert keys(story, "tasks", "tasks") == ["T005"]
    assert record(story)["T005"]["completed_against"] == {}
    assert record(story)["T004"]["completed_against"]["DEC-003"]


def test_a_reopened_task_stays_listed_until_it_is_unticked(story: Story) -> None:
    change_dec3(story)
    answer_all(story, "tasks", "tasks", reply="ok except T005", all_=False, all_except=["T005"])
    edit(story, "tasks", "- [x] T005 ", "- [ ] T005 ")
    staleness.sync_task_snapshots(package_of(story))
    assert keys(story, "tasks", "tasks") == []


def test_a_further_edit_after_the_list_was_shown_is_list_changed(story: Story) -> None:
    change_dec3(story)
    digest = the_list(story, "tasks", "tasks").digest
    edit(story, "technical", "A changed reason for decision 3.", "Yet another reason for decision 3.")
    with pytest.raises(EilExit) as exc:
        answer_all(story, "tasks", "tasks", digest=digest)
    assert [r["code"] for r in exc.value.payload["refusals"]] == ["list-changed"]


def test_a_reply_that_contradicts_the_flags_is_reply_mismatch(story: Story) -> None:
    change_dec3(story)
    with pytest.raises(EilExit) as exc:
        answer_all(story, "tasks", "tasks", reply="ok except T005")
    assert [r["code"] for r in exc.value.payload["refusals"]] == ["reply-mismatch"]


# ---- completion


def test_completion_refuses_while_the_tasks_list_is_unanswered(story: Story) -> None:
    assert "task-completed-against-earlier-version" not in approve_completion(story)
    change_dec3(story)
    assert "task-completed-against-earlier-version" in approve_completion(story)
    answer_all(story, "tasks", "tasks")
    assert "task-completed-against-earlier-version" not in approve_completion(story)


def test_the_task_refusal_can_be_overridden_like_other_completion_criteria(story: Story) -> None:
    change_dec3(story)
    override = record_block(
        "override",
        {
            "id": "OVR-001", "stage": "completion", "criterion": "CMP-G06", "by": "Ada Dev",
            "reason": "accepted", "at": "2026-09-25T00:00:00Z",
        },
    )  # fmt: skip
    story.write("completion", completion_doc(extra=override))
    codes = [c.id for c in check_stage(package_of(story), "completion", write=False).unmet()]
    assert "CMP-G06" not in codes


def test_completion_refuses_an_unreviewed_inferred_evidence_row(story: Story) -> None:
    assert "unreviewed-ai-content" not in approve_completion(story)
    text = story.read("verification")
    story.write("verification", text.replace("## Manual Evidence\n", "## Manual Evidence\n\n" + evidence_row(10, "REQ-003") + "\n", 1))
    assert "unreviewed-ai-content" in approve_completion(story)
    override = record_block(
        "override",
        {
            "id": "OVR-001", "stage": "completion", "criterion": "unreviewed-ai-content", "by": "Ada Dev",
            "reason": "accepted", "at": "2026-09-25T00:00:00Z",
        },
    )  # fmt: skip
    story.write("completion", completion_doc(extra=override))
    with pytest.raises(EilExit) as exc:
        approve(package_of(story), CONFIG, "completion", "Ada Dev", YES)
    assert "unreviewed-ai-content" not in [r["code"] for r in exc.value.payload["refusals"]]


# ---- the evidence list


def test_a_changed_source_puts_the_evidence_recorded_against_it_on_the_list(story: Story) -> None:
    assert keys(story, "verification", "evidence") == []
    edit(story, "functional", "behaviour 1 of duplicate analysis", "behaviour 1 of duplicate review")
    listed = the_list(story, "verification", "evidence")
    assert [e.key for e in listed.entries] == ["EVD-003"]
    assert listed.entries[0].extra["confirmed"] is False and "FR-001" in listed.entries[0].why


def test_answering_the_evidence_list_clears_the_completion_refusal(story: Story) -> None:
    edit(story, "functional", "behaviour 1 of duplicate analysis", "behaviour 1 of duplicate review")
    assert "evidence-for-earlier-version" in approve_completion(story)
    answer_all(story, "verification", "evidence")
    assert keys(story, "verification", "evidence") == []
    assert "evidence-for-earlier-version" not in approve_completion(story)


# ---- unknown currency


def test_derived_blocks_with_no_snapshot_appear_once_and_answering_records_it(reference_story: Story) -> None:
    listed = the_list(reference_story, "tasks", "unknown-currency")
    assert len(listed.entries) == 12 and listed.purpose == "awareness"
    answer_all(reference_story, "tasks", "unknown-currency")
    assert keys(reference_story, "tasks", "unknown-currency") == []
    blocks = record(reference_story)
    assert blocks["T001"]["sources"] and set(blocks["T001"]["completed_against"]) >= {"AIS-001", "FR-001"}
    assert blocks["T007"]["sources"] and "completed_against" not in blocks["T007"]
    assert blockstatus.counts(package_of(reference_story), "tasks")["unknown"] == 0
