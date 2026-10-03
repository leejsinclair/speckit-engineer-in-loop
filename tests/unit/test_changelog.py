"""The Change Log: one AI-drafted, person-accepted entry per accepted change (FR-043, FR-044; research D-39)."""

from __future__ import annotations

import pytest
from eil import changelog, corrections, overview, reviews
from eil.fingerprint import fingerprint_text
from eil.results import EilExit

from tests.helpers.derived import CONFIG, edit, package_of
from tests.helpers.package import Story
from tests.unit.test_accept_changes import (
    NEW_REQ,
    add_req5,
    answer,
    decide_req1,
    prepared,
    reword_req2,
)
from tests.unit.test_classify import classify


def record(story: Story, stage: str = "requirements") -> dict:
    return package_of(story).record(stage, "provenance")


def confirm_with(story: Story, summaries: dict[str, str] | None, stage: str = "requirements"):
    return reviews.confirm(
        package_of(story), CONFIG, stage, by="Ada Dev", confirmation="ok", summaries=summaries
    )


def test_a_covered_change_needs_a_summary_and_is_recorded_as_ai_drafted(reference_story: Story) -> None:
    prepared(reference_story)
    decide_req1(reference_story)
    result = confirm_with(reference_story, {"REQ-001": "Made the import detection real-time."})
    (entry,) = record(reference_story)["changes"]
    assert entry["item"] == "REQ-001" and entry["summary_by"] == "ai" and entry["accepted_by"] == "Ada Dev"
    assert entry["summary"] == "Made the import detection real-time." and entry["origin"] == "CH-004"
    assert result["approval"]["reached"] == "carried-forward"


@pytest.mark.parametrize("covered", [True, False])
def test_a_change_without_a_summary_is_refused_and_nothing_is_written(reference_story: Story, covered: bool) -> None:
    prepared(reference_story)
    if covered:
        decide_req1(reference_story)
    else:
        reword_req2(reference_story)
        answer(reference_story)
    before = reference_story.read("requirements")
    with pytest.raises(EilExit) as exc:
        confirm_with(reference_story, None)
    assert [r["code"] for r in exc.value.payload["refusals"]] == ["summary-missing"]
    assert reference_story.read("requirements") == before


def test_summaries_given_with_the_answer_are_used_by_confirm(reference_story: Story) -> None:
    prepared(reference_story)
    add_req5(reference_story)
    answer(reference_story, summaries={"REQ-005": "Added an export of the decision history."})
    acceptance = record(reference_story)["acceptances"][-1]
    assert acceptance["summaries"] == {"REQ-005": "Added an export of the decision history."}
    confirm_with(reference_story, None)
    (entry,) = record(reference_story)["changes"]
    assert entry["item"] == "REQ-005" and entry["origin"] == "edit"
    assert entry["summary"] == "Added an export of the decision history."


def test_the_confirm_summary_wins_over_the_stored_one(reference_story: Story) -> None:
    prepared(reference_story)
    add_req5(reference_story)
    answer(reference_story, summaries={"REQ-005": "Old."})
    confirm_with(reference_story, {"REQ-005": "New."})
    assert record(reference_story)["changes"][0]["summary"] == "New."


def test_the_changelog_region_is_a_labelled_table_with_escaped_cells(reference_story: Story) -> None:
    prepared(reference_story)
    add_req5(reference_story)
    answer(reference_story)
    confirm_with(reference_story, {"REQ-005": "Split a | b\nacross lines."})
    text = reference_story.read("requirements")
    region = text.split("<!-- eil:begin changelog -->")[1].split("<!-- eil:end changelog -->")[0]
    assert "AI-drafted, accepted as shown" in region and "Split a \\| b across lines." in region
    assert "\n## Change Log" in text and text.index("## Change Log") < text.index("## Record")


def test_rendering_the_log_changes_no_fingerprint(reference_story: Story) -> None:
    prepared(reference_story)
    add_req5(reference_story)
    answer(reference_story)
    confirm_with(reference_story, {"REQ-005": "First."})
    text = reference_story.read("requirements")
    changed = text.replace("First.", "Something else entirely.")
    assert changed != text and fingerprint_text(changed) == fingerprint_text(text)


def test_a_closed_correction_in_a_never_approved_stage_writes_one_entry_and_a_rederivation_none(
    reference_story: Story,
) -> None:
    classify(reference_story, "ai-spec", ("AIS-001", None))
    corrections.open_correction(
        package_of(reference_story), "AIS-001", "plan", "slow", "Ada Dev", owner="ai-spec",
        wording="Implement behaviour 1, quickly.",
    )
    edit(reference_story, "ai-spec", "Implement behaviour 1.", "Implement behaviour 1, quickly. (decided: CR-001)")
    classify(reference_story, "ai-spec", ("AIS-001", None))
    confirm_with(reference_story, {"AIS-001": "Made it quick."}, "ai-spec")
    assert [c["item"] for c in record(reference_story, "ai-spec")["changes"]] == ["AIS-001"]
    edit(reference_story, "ai-spec", "Implement behaviour 2.", "Implement behaviour 2 differently.")
    classify(reference_story, "ai-spec", ("AIS-002", None))
    assert len(record(reference_story, "ai-spec")["changes"]) == 1


def test_the_overview_shows_the_latest_five_changes_story_wide_newest_first(reference_story: Story) -> None:
    prepared(reference_story)
    pkg = package_of(reference_story)
    rows = [
        changelog.entry(f"2026-09-2{n}T10:00:00Z", f"REQ-00{n}", f"Change {n}.", "edit", "Ada Dev") for n in range(1, 8)
    ]
    from eil.provenance import _load_record, _save_record

    stored = _load_record(pkg, "requirements")
    stored["changes"] = rows
    _save_record(pkg, "requirements", stored)
    recent = changelog.recent(package_of(reference_story))
    assert [r["summary"] for r in recent] == [f"Change {n}." for n in (7, 6, 5, 4, 3)]
    status = overview.status(package_of(reference_story))
    assert [r["summary"] for r in status["recent_changes"]] == [r["summary"] for r in recent]


def test_no_change_log_bookkeeping_appears_in_the_prose(reference_story: Story) -> None:
    prepared(reference_story)
    add_req5(reference_story)
    answer(reference_story)
    confirm_with(reference_story, {"REQ-005": "Added export."})
    text = reference_story.read("requirements")
    assert NEW_REQ in text and "summary_by" not in text.split("<!-- eil:begin provenance -->")[0]
