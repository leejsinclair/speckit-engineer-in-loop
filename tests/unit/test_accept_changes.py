"""Accepting changes to an approved stage: the ``changes`` list and ``review confirm``
(determinism requirement 30; FR-015 to FR-020, FR-038, FR-048, FR-050; research D-36, D-37)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
from eil import cli, reviews
from eil.package import Package, reached_of
from eil.results import EilExit

from tests.helpers.changes import summaries_for
from tests.helpers.derived import CONFIG, edit
from tests.helpers.package import Story, record_block
from tests.unit.test_comprehension_delta import approved as approved_functional

FR3 = "**FR-003**: The system shall support behaviour 3 of duplicate analysis. (traces: REQ-001)"
FR4 = "**FR-004**: The system shall support behaviour 4 of duplicate analysis. (traces: REQ-002)"
NEW_FR = "**FR-013**: The system shall keep a history of merges. (traces: REQ-004)"
REQ1 = "**REQ-001**: The system detects duplicate customers on import."
REQ2 = "**REQ-002**: Analysts can review each flagged pair."
REQ4 = "**REQ-004**: Every decision on a pair is auditable."
NEW_REQ = "**REQ-005**: Analysts can export the decision history."


def package_of(story: Story) -> Package:
    return Package(story.root)


def prepared(story: Story) -> Story:
    """The reference story with provenance recorded, so a hand-written block counts as inferred."""
    cli._persist_adoption(package_of(story))
    return story


CHALLENGE = {
    "id": "CH-004", "stage": "requirements", "raised_by": "ai", "raised_at": "2026-09-26T10:00:00Z",
    "target": "REQ-001", "text": "Should the wording be more specific?", "status": "closed",
    "responder": "Ada Dev", "response": "accepted", "at": "2026-09-26T10:05:00Z",
}  # fmt: skip


def decide_req1(story: Story) -> None:
    """REQ-001 reworded and carried in as the person's already-recorded decision CH-004."""
    story.append("requirements", "\n" + record_block("challenge", CHALLENGE).rstrip("\n") + "\n")
    edit(story, "requirements", REQ1, REQ1.replace("import.", "import, in real time.") + " (decided: CH-004)")


def reword_req2(story: Story) -> None:
    edit(story, "requirements", REQ2, REQ2.replace("pair.", "pair, with a note."))


def add_req5(story: Story) -> None:
    edit(story, "requirements", REQ4, REQ4 + "\n\n" + NEW_REQ)


STAGE = "requirements"


def the_list(story: Story, stage: str = STAGE) -> reviews.ReviewList:
    return reviews.build_list(package_of(story), stage, "changes")


def entry(listed: reviews.ReviewList, key: str) -> reviews.ListEntry:
    return next(e for e in listed.entries if e.key == key)


def answer(story: Story, by: str = "Ada Dev", reply: str = "ok", **kwargs: Any) -> dict[str, Any]:
    listed = the_list(story)
    if not kwargs.get("reopen"):
        kwargs.setdefault("all_", True)
    return reviews.answer(
        package_of(story), CONFIG, STAGE, "changes", digest=listed.digest, by=by, reply=reply, **kwargs
    )


def confirm(
    story: Story, confirmation: str = "ok", by: str = "Ada Dev", stage: str = STAGE
) -> dict[str, Any]:
    pkg = package_of(story)
    return reviews.confirm(
        pkg, CONFIG, stage, by=by, confirmation=confirmation, summaries=summaries_for(pkg, stage)
    )


def codes(exc: pytest.ExceptionInfo[EilExit]) -> list[str]:
    return [r["code"] for r in exc.value.payload["refusals"]]


def refused(story: Story, **kwargs: Any) -> list[str]:
    stage = kwargs.get("stage", STAGE)
    before = story.read(stage)
    with pytest.raises(EilExit) as exc:
        confirm(story, **kwargs)
    assert story.read(stage) == before, "a refusal must write nothing"
    return codes(exc)


def _hash(story: Story, item_id: str) -> str:
    return package_of(story).current_item_hashes()[item_id]


# ---- the list: covered versus uncovered, with no ids supplied


def test_the_list_splits_covered_changes_from_uncovered_ones(reference_story: Story) -> None:
    prepared(reference_story)
    decide_req1(reference_story)
    add_req5(reference_story)
    listed = the_list(reference_story)
    assert entry(listed, "REQ-001").covered_by == "CH-004"
    assert entry(listed, "REQ-005").covered_by is None
    assert entry(listed, "REQ-005").extra.get("inferred") is True
    assert "inferred" not in entry(listed, "REQ-001").extra


def test_a_change_in_an_upstream_item_reaches_the_stage_that_traces_it(reference_story: Story) -> None:
    prepared(reference_story)
    decide_req1(reference_story)
    functional = the_list(reference_story, "functional")
    assert [e.key for e in functional.entries] == ["REQ-001"]
    assert functional.entries[0].covered_by == "CH-004"


def test_an_unchanged_stage_has_an_empty_list(reference_story: Story) -> None:
    assert the_list(reference_story).entries == []


# ---- confirm with everything covered: carried forward on "ok" (Constitution II)


def test_confirm_carries_forward_when_every_change_is_a_recorded_decision(reference_story: Story) -> None:
    prepared(reference_story)
    decide_req1(reference_story)
    approval = confirm(reference_story, "ok")["approval"]
    assert approval["reached"] == "carried-forward"
    assert approval["rests_on"] == ["CH-004"]
    assert approval["sign_off"] == "ok" and "attestation" not in approval
    assert approval["by"] == "Ada Dev"
    assert package_of(reference_story).state(STAGE).state == "approved"
    assert reached_of(package_of(reference_story).state(STAGE).approval) == "carried-forward"


def test_confirm_writes_only_the_records_to_the_document(reference_story: Story) -> None:
    prepared(reference_story)
    decide_req1(reference_story)
    before = reference_story.read(STAGE)
    confirm(reference_story, "ok")
    strip = re.compile(r"<!-- eil:begin (approval|provenance|changelog) -->.*?<!-- eil:end \1 -->", re.DOTALL)
    assert strip.sub("", reference_story.read(STAGE)) == strip.sub("", before)


def test_a_downstream_stage_with_only_an_upstream_change_shows_it_as_a_covered_change(
    reference_story: Story,
) -> None:
    prepared(reference_story)
    decide_req1(reference_story)
    assert entry(the_list(reference_story, "functional"), "REQ-001").covered_by == "CH-004"


# ---- uncovered changes need the list answered, then a confirmation


def test_uncovered_and_unanswered_refuses_changes_unanswered(reference_story: Story) -> None:
    prepared(reference_story)
    decide_req1(reference_story)
    reword_req2(reference_story)
    assert refused(reference_story) == ["changes-unanswered"]


def test_answered_changes_give_reached_reviewed_with_the_attestation(reference_story: Story) -> None:
    prepared(reference_story)
    decide_req1(reference_story)
    add_req5(reference_story)
    accepted = answer(reference_story)
    approval = confirm(reference_story, "Yes, I reviewed the changes.")["approval"]
    assert approval["reached"] == "reviewed"
    assert approval["attestation"] == "Yes, I reviewed the changes." and "sign_off" not in approval
    assert accepted["id"] in approval["rests_on"] and "CH-004" in approval["rests_on"]
    assert package_of(reference_story).state(STAGE).state == "approved"


def test_answering_the_list_settles_an_inferred_addition(reference_story: Story) -> None:
    prepared(reference_story)
    add_req5(reference_story)
    answer(reference_story)
    assert reviews.build_list(package_of(reference_story), STAGE, "inferred").entries == []


def test_answered_changes_leave_the_list_and_a_changed_one_returns(reference_story: Story) -> None:
    prepared(reference_story)
    add_req5(reference_story)
    answer(reference_story)
    assert "REQ-005" not in [e.key for e in the_list(reference_story).entries]
    edit(reference_story, STAGE, NEW_REQ, NEW_REQ.replace("history.", "history as a file."))
    assert "REQ-005" in [e.key for e in the_list(reference_story).entries]


# ---- an inferred-list acceptance also answers the matching change (A1, D-45)


def answer_inferred(story: Story, by: str = "Ada Dev", reply: str = "ok", **kwargs: Any) -> dict[str, Any]:
    pkg = package_of(story)
    listed = reviews.build_list(pkg, STAGE, "inferred")
    return reviews.answer(pkg, CONFIG, STAGE, "inferred", digest=listed.digest, by=by, reply=reply, **kwargs)


def test_an_inferred_acceptance_also_answers_the_matching_change(reference_story: Story) -> None:
    prepared(reference_story)
    add_req5(reference_story)
    assert "REQ-005" in [e.key for e in the_list(reference_story).entries]
    answer_inferred(reference_story, all_=True)
    assert "REQ-005" not in [e.key for e in the_list(reference_story).entries]
    assert confirm(reference_story, "yes")["approval"]["reached"] == "reviewed"


def test_an_inferred_acceptance_at_another_hash_does_not_answer_the_change(reference_story: Story) -> None:
    prepared(reference_story)
    add_req5(reference_story)
    answer_inferred(reference_story, all_=True)
    edit(reference_story, STAGE, NEW_REQ, NEW_REQ.replace("history.", "history as a file."))
    assert "REQ-005" in [e.key for e in the_list(reference_story).entries]


def test_an_inferred_exception_does_not_answer_the_change(reference_story: Story) -> None:
    prepared(reference_story)
    add_req5(reference_story)
    answer_inferred(reference_story, reply="ok except REQ-005", all_except=["REQ-005"])
    assert "REQ-005" in [e.key for e in the_list(reference_story).entries]


def test_a_non_confirmers_inferred_acceptance_does_not_answer_the_change(reference_story: Story) -> None:
    prepared(reference_story)
    add_req5(reference_story)
    with pytest.raises(EilExit):
        answer_inferred(reference_story, by="Priya QA", all_=True)
    assert "REQ-005" in [e.key for e in the_list(reference_story).entries]


def test_an_opposing_answer_after_an_inferred_acceptance_keeps_the_change_open(
    reference_story: Story,
) -> None:
    prepared(reference_story)
    add_req5(reference_story)
    answer_inferred(reference_story, all_=True)
    reviews.answer(
        package_of(reference_story), CONFIG, STAGE, "changes", digest=None, by="Priya QA",
        reply="I don't agree with REQ-005", reopen=["REQ-005"],
    )  # fmt: skip
    assert "REQ-005" in [e.key for e in the_list(reference_story).entries]


# ---- who may confirm


def test_an_empty_confirmation_is_refused(reference_story: Story) -> None:
    prepared(reference_story)
    decide_req1(reference_story)
    assert refused(reference_story, confirmation="  ") == ["confirmation-required"]


def test_someone_not_configured_to_confirm_is_refused(reference_story: Story) -> None:
    prepared(reference_story)
    decide_req1(reference_story)
    assert "not-a-confirmer" in refused(reference_story, by="Priya QA")


def test_the_ai_can_never_supply_the_sign_off(reference_story: Story) -> None:
    prepared(reference_story)
    decide_req1(reference_story)
    assert "ai-approval" in refused(reference_story, by="claude")


def test_a_stage_that_was_never_approved_is_not_amendable(reference_story: Story) -> None:
    with pytest.raises(EilExit) as exc:
        confirm(reference_story, stage="ai-spec")
    assert codes(exc) == ["not-amendable"]


# ---- conflicting answers (FR-050)


def test_a_conflicting_answer_blocks_confirm_until_a_confirmer_answers_again(reference_story: Story) -> None:
    prepared(reference_story)
    add_req5(reference_story)
    answer(reference_story)
    reviews.answer(
        package_of(reference_story), CONFIG, STAGE, "changes", digest=None, by="Priya QA",
        reply="I don't agree with REQ-005", reopen=["REQ-005"],
    )  # fmt: skip
    conflicted = reviews.conflicted_keys(
        package_of(reference_story), STAGE, {"REQ-005": _hash(reference_story, "REQ-005")}
    )
    assert conflicted == {"REQ-005"}
    assert "acceptance-conflict" in refused(reference_story)
    assert entry(the_list(reference_story), "REQ-005").conflict is True
    result = answer(reference_story, reply="ok, agreed after discussion")
    assert result["resolved_conflict"] is True
    assert confirm(reference_story, "yes")["approval"]["reached"] == "reviewed"


# ---- the comprehension check on a stage that takes one (D-27)


def test_a_covered_change_to_a_checked_stage_carries_forward_without_a_question(
    story_dir: Story, tmp_path: Path
) -> None:
    approved_functional(story_dir, tmp_path)
    cli._persist_adoption(package_of(story_dir))
    edit(
        story_dir,
        "requirements",
        "The system detects duplicate customers on import.",
        "The system detects duplicate customers on import, in real time. (decided: CH-004)",
    )
    story_dir.append("requirements", "\n" + record_block("challenge", CHALLENGE).rstrip("\n") + "\n")
    approval = confirm(story_dir, "ok", stage="functional")["approval"]
    assert approval["reached"] == "carried-forward" and approval["rests_on"] == ["CH-004"]
    comp = package_of(story_dir).record("functional", "comprehension")
    assert comp and {row["outcome"] for row in comp["levels"]} == {"not-applicable"}


def test_an_answered_change_to_a_checked_stage_still_needs_the_delta_check(
    story_dir: Story, tmp_path: Path
) -> None:
    approved_functional(story_dir, tmp_path)
    cli._persist_adoption(package_of(story_dir))
    edit(
        story_dir,
        "functional",
        "**FR-001**: The system shall flag duplicate customers on import.",
        "**FR-001**: The system shall flag duplicate customers on import, in real time.",
    )
    reviews.answer(
        package_of(story_dir), CONFIG, "functional", "changes",
        digest=the_list(story_dir, "functional").digest, by="Ada Dev", reply="ok", all_=True,
    )  # fmt: skip
    assert refused(story_dir, stage="functional") == ["comprehension-prerequisites"]


# ---- records from before this feature, and the first approval (FR-020, FR-038)


def test_an_approval_without_reached_reads_as_first() -> None:
    assert reached_of({"by": "Ada Dev", "attestation": "Yes."}) == "first"
    assert reached_of({"reached": "carried-forward"}) == "carried-forward"
    assert reached_of(None) is None
