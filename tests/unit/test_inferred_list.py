"""The ``inferred`` review list and what an unreviewed inferred block blocks (T035; FR-010, FR-014, FR-049)."""

from __future__ import annotations

from typing import Any

from eil import provenance, reviews, staleness
from eil.package import Package

from tests.helpers.derived import CONFIG, edit
from tests.helpers.package import Story

INFERRED = {"AIS-003": "a tie-break rule", "AIS-005": "a timeout", "AIS-007": "a retry policy of 3 attempts"}


def package_of(story: Story) -> Package:
    return Package(story.root)


def classify_ai_spec(story: Story) -> None:
    blocks = [b.key for b in provenance.blocks_of(package_of(story).doc("ai-spec")) if b.numbered]
    provenance.classify(
        package_of(story),
        "ai-spec",
        {"stage": "ai-spec", "blocks": [{"block": k, "adds": INFERRED.get(k)} for k in blocks]},
    )


def the_list(story: Story, stage: str = "ai-spec") -> reviews.ReviewList:
    return reviews.build_list(package_of(story), stage, "inferred")


def keys(listed: reviews.ReviewList) -> list[str]:
    return [e.key for e in listed.entries]


def answer(story: Story, **kwargs: Any) -> dict[str, Any]:
    listed = the_list(story)
    excepted = kwargs.get("all_except")
    reply = f"ok except {', '.join(excepted)}" if excepted else "ok"
    return reviews.answer(
        package_of(story), CONFIG, "ai-spec", "inferred", digest=listed.digest, by="Ada Dev", reply=reply, **kwargs
    )


def blocked(story: Story) -> dict[str, list[str]]:
    return {k: [str(c) for c in v] for k, v in staleness.blocked_work(package_of(story)).items()}


def test_the_list_shows_full_text_and_the_reason_for_each_entry(reference_story: Story) -> None:
    classify_ai_spec(reference_story)
    listed = the_list(reference_story)
    assert sorted(keys(listed)) == sorted(INFERRED)
    row = next(e for e in listed.entries if e.key == "AIS-007")
    assert row.what == "**AIS-007**: Implement behaviour 7. (traces: FR-007)"
    assert row.why == "adds a retry policy of 3 attempts"
    assert listed.purpose == "validation"


def test_a_reply_of_ok_except_settles_the_rest_and_the_excepted_block_reappears_alone(reference_story: Story) -> None:
    classify_ai_spec(reference_story)
    result = answer(reference_story, all_except=["AIS-003"])
    assert sorted(result["accepted"]) == ["AIS-005", "AIS-007"] and result["except"] == ["AIS-003"]
    assert keys(the_list(reference_story)) == ["AIS-003"]


def test_an_edited_reviewed_block_reappears_and_an_unchanged_one_never_does(reference_story: Story) -> None:
    classify_ai_spec(reference_story)
    answer(reference_story, all_=True)
    assert keys(the_list(reference_story)) == []
    edit(reference_story, "ai-spec", "Implement behaviour 5.", "Implement behaviour 5 with a limit.")
    assert keys(the_list(reference_story)) == ["AIS-005"]
    assert "changed since it was reviewed" in the_list(reference_story).entries[0].why


def test_a_hand_written_block_is_inferred_and_listed_once_the_stage_has_a_record(reference_story: Story) -> None:
    classify_ai_spec(reference_story)
    answer(reference_story, all_=True)
    old = "**AIS-008**: Implement behaviour 8. (traces: FR-008)"
    edit(reference_story, "ai-spec", old, old + "\n\n**AIS-020**: A block a person typed straight into the file. (traces: FR-001)")
    assert keys(the_list(reference_story)) == ["AIS-020"]


def test_every_list_shows_the_fidelity_limit(reference_story: Story) -> None:
    classify_ai_spec(reference_story)
    assert reviews.FIDELITY_LIMIT in the_list(reference_story).limits
    answer(reference_story, all_=True)
    assert reviews.FIDELITY_LIMIT in the_list(reference_story).limits


def test_an_unreviewed_inferred_ai_spec_item_blocks_only_the_work_that_traces_to_it(reference_story: Story) -> None:
    classify_ai_spec(reference_story)
    got = blocked(reference_story)
    assert {"T003", "T005", "T007"} <= set(got)
    assert any("AIS-007" in cause for cause in got["T007"])
    assert set(got) == {"T003", "T005", "T007"}


def test_review_lifts_the_block_and_an_exception_keeps_it(reference_story: Story) -> None:
    classify_ai_spec(reference_story)
    answer(reference_story, all_except=["AIS-003"])
    assert set(blocked(reference_story)) == {"T003"}
    answer(reference_story, all_=True)
    assert blocked(reference_story) == {}


def test_a_plan_section_tracing_an_unreviewed_item_is_blocked_and_so_is_what_traces_it(reference_story: Story) -> None:
    edit(reference_story, "plan", "Summary (traces: DEC-001)", "Summary (traces: AIS-007)")
    classify_ai_spec(reference_story)
    got = blocked(reference_story)
    assert "§Summary" in got and "T007" in got


def test_an_unreviewed_inferred_plan_section_or_task_blocks_nothing_else(reference_story: Story) -> None:
    classify_ai_spec(reference_story)
    answer(reference_story, all_=True)
    provenance.classify(
        package_of(reference_story), "plan", {"stage": "plan", "blocks": [{"block": "§Queue Design", "adds": "a new queue"}]}
    )
    provenance.classify(
        package_of(reference_story), "tasks", {"stage": "tasks", "blocks": [{"block": "T009", "adds": "extra work"}]}
    )
    assert "§Queue Design" in keys(the_list(reference_story, "plan"))
    assert "T009" in keys(the_list(reference_story, "tasks"))
    assert blocked(reference_story) == {}
