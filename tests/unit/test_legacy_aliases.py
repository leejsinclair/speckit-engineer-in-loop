"""``amend`` and ``review start|accept|finish`` remain as aliases over the changes list (research D-36):
they keep their historical fields and refusals, and now also record ``reached`` and ``rests_on``."""

from __future__ import annotations

import pytest
from eil import provenance
from eil.package import Package, reached_of
from eil.results import EilExit

from tests.helpers.derived import CONFIG
from tests.helpers.package import Story
from tests.unit.test_accept_changes import decide_req1, prepared, reword_req2


def test_amend_still_writes_amended_and_now_reached_and_rests_on(reference_story: Story) -> None:
    prepared(reference_story)
    decide_req1(reference_story)
    result = provenance.amend(
        Package(reference_story.root), CONFIG, "requirements", ["CH-004"], "Ada Dev", "Yes."
    )
    approval = result["approval"]
    assert approval["amended"] is True and approval["amends"] == ["CH-004"]
    assert reached_of(approval) == "carried-forward"
    assert approval["rests_on"] == ["CH-004"] and approval["sign_off"] == "Yes."


def test_review_start_names_the_changes_list_digest(reference_story: Story) -> None:
    prepared(reference_story)
    decide_req1(reference_story)
    started = provenance.start(Package(reference_story.root), "requirements")
    assert started["kind"] == "changes" and started["digest"].startswith("sha256:")
    assert [row["id"] for row in started["items"]] == ["REQ-001"]


def test_review_accept_then_finish_records_reviewed_and_the_reviews(reference_story: Story) -> None:
    prepared(reference_story)
    reword_req2(reference_story)
    accepted = provenance.accept(
        Package(reference_story.root), CONFIG, "requirements", items=["REQ-002"], sections=[], by="Ada Dev"
    )
    result = provenance.finish(Package(reference_story.root), CONFIG, "requirements", "Ada Dev", "Yes.")
    approval = result["approval"]
    assert approval["reviewed_change_by_change"] is True
    assert approval["reviewed_ids"] == accepted["created"]
    assert reached_of(approval) == "reviewed"
    assert approval["rests_on"] == accepted["created"] and approval["attestation"] == "Yes."


def test_amend_from_a_subset_of_the_covering_decisions_succeeds(reference_story: Story) -> None:
    prepared(reference_story)
    decide_req1(reference_story)
    result = provenance.amend(
        Package(reference_story.root), CONFIG, "requirements", ["CH-004"], "Ada Dev", "Yes."
    )
    assert result["approval"]["amends"] == ["CH-004"]


def test_amend_from_an_id_outside_the_covering_set_is_refused(reference_story: Story) -> None:
    prepared(reference_story)
    decide_req1(reference_story)
    before = reference_story.read("requirements")
    with pytest.raises(EilExit) as info:
        provenance.amend(
            Package(reference_story.root), CONFIG, "requirements", ["CH-004", "OQ-001"], "Ada Dev", "Yes."
        )
    assert "amend-not-covering" in [r["code"] for r in info.value.payload["refusals"]]
    assert reference_story.read("requirements") == before


def test_review_aliases_record_legacy_reviews_not_acceptances(reference_story: Story) -> None:
    """Documented difference (contracts/cli.md): the aliases write eil:review records and
    ``(decided: RVW-###)``; ``review answer`` writes acceptances in the provenance region."""
    prepared(reference_story)
    reword_req2(reference_story)
    provenance.accept(
        Package(reference_story.root), CONFIG, "requirements", items=["REQ-002"], sections=[], by="Ada Dev"
    )
    assert "(decided: RVW-" in reference_story.read("requirements")
    assert "eil:review" in reference_story.read("requirements")
