"""Challenges (task T117; FR-034 to FR-038, edge case "conflicting answers").

The AI raises them, a person answers them, and neither the code nor the AI can close one on the
person's behalf. A rejected or deferred challenge is a standing constraint.
"""

from __future__ import annotations

import re

import pytest
from eil import records
from eil.blocks import Doc
from eil.fingerprint import fingerprint_text
from eil.identity import Config
from eil.package import Package
from eil.results import EilExit

from tests.helpers.package import Story, with_technical

NOW = "2026-09-25T10:14:03Z"
CONFIG = Config(
    default_developer="Ada Dev",
    approvers={
        "requirements": ["Ada Dev", "Grace Lead"],
        "functional": ["Ada Dev", "Grace Lead"],
        "technical": ["Ada Dev"],
        "ai-spec": ["Ada Dev"],
    },
    abbreviation_authorisers=[],
)
TEXT = "What happens when two duplicate-detection requests arrive at the same time?"


@pytest.fixture(autouse=True)
def fixed_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(records, "utc_now", lambda: NOW)


@pytest.fixture
def package(story_dir: Story) -> Package:
    with_technical(story_dir)
    return Package(story_dir.root)


def add(
    package: Package,
    stage: str = "functional",
    target: str = "FR-001",
    text: str = TEXT,
    by: str | None = None,
) -> dict:
    return records.add_challenge(package, stage, target, text, by)


def answer(package: Package, cid: str, response: str, by: str = "Ada Dev", reason: str | None = None) -> dict:
    return records.answer_challenge(package, CONFIG, cid, response, by, reason)


def codes(exc: pytest.ExceptionInfo[EilExit]) -> list[str]:
    return [r["code"] for r in exc.value.payload["refusals"]]


def stored(package: Package, stage: str = "functional") -> list[dict]:
    return [r.obj for r in package.doc(stage).records() if r.kind == "challenge" and r.obj]


# ---- raising a challenge (FR-034, FR-035)


def test_a_challenge_is_recorded_open_with_its_target_and_text(package: Package) -> None:
    result = add(package)
    assert result["id"] == "CH-001"
    assert stored(package) == [
        {
            "id": "CH-001",
            "stage": "functional",
            "raised_by": "ai",
            "raised_at": NOW,
            "target": "FR-001",
            "text": TEXT,
            "status": "open",
        }
    ]


def test_the_challenge_sits_in_the_challenges_section_and_touches_nothing_else(
    story_dir: Story, package: Package
) -> None:
    before = story_dir.read("functional")
    add(package)
    after = story_dir.read("functional")
    assert after.index("## Challenges") < after.index("```eil:challenge") < after.index("## Overrides")
    without = re.sub(r"```eil:challenge\n.*?\n```\n", "", after, flags=re.DOTALL)
    assert fingerprint_text(without) == fingerprint_text(before)
    assert "eil:challenge" in after and "CH-001" not in before


def test_ids_are_unique_across_the_whole_story(package: Package) -> None:
    assert add(package, "functional")["id"] == "CH-001"
    assert add(package, "technical", "DEC-001", "Why not retry three times?")["id"] == "CH-002"
    assert add(package, "requirements", "REQ-001", "Is the scope complete?")["id"] == "CH-003"


def test_the_raiser_defaults_to_the_ai_and_may_be_a_person(package: Package) -> None:
    add(package)
    add(package, target="NFR-001", text="Is 60 seconds measured at the 95th percentile?", by="Grace Lead")
    assert [c["raised_by"] for c in stored(package)] == ["ai", "Grace Lead"]


def test_a_target_may_be_an_item_of_any_stage_or_a_section(package: Package) -> None:
    add(package, "technical", "FR-001", "Does the design serve this?")
    add(package, "functional", "Business Rules", "Which tax id counts?")
    assert [c["target"] for c in stored(package, "technical")] == ["FR-001"]


def test_a_target_that_exists_nowhere_is_refused(package: Package) -> None:
    with pytest.raises(EilExit) as exc:
        add(package, target="FR-099")
    assert codes(exc) == ["unknown-item"]
    with pytest.raises(EilExit) as exc:
        add(package, target="No Such Section")
    assert codes(exc) == ["unknown-item"]


@pytest.mark.parametrize("stage", ["verification", "nonsense"])
def test_only_definition_stages_with_a_document_take_challenges(package: Package, stage: str) -> None:
    with pytest.raises(EilExit) as exc:
        add(package, stage)
    assert codes(exc) in (["stage-not-eligible"], ["unknown-stage"])


def test_a_stage_without_a_document_is_refused(story_dir: Story) -> None:
    with_technical(story_dir)
    with pytest.raises(EilExit) as exc:
        add(Package(story_dir.root), "ai-spec")
    assert codes(exc) == ["unknown-stage"]


def test_an_empty_challenge_is_a_usage_error_not_a_record(package: Package) -> None:
    with pytest.raises(EilExit) as exc:
        add(package, text="   ")
    assert exc.value.code == 2


# ---- answering (FR-036)


def test_accepting_closes_the_challenge_with_who_when_and_the_response(package: Package) -> None:
    add(package)
    answer(package, "CH-001", "accepted")
    assert stored(package)[0] == {
        "id": "CH-001",
        "stage": "functional",
        "raised_by": "ai",
        "raised_at": NOW,
        "target": "FR-001",
        "text": TEXT,
        "status": "closed",
        "response": "accepted",
        "responder": "Ada Dev",
        "at": NOW,
    }


@pytest.mark.parametrize("response", ["rejected", "deferred"])
def test_rejecting_or_deferring_needs_a_reason(package: Package, response: str) -> None:
    add(package)
    with pytest.raises(EilExit) as exc:
        answer(package, "CH-001", response)
    assert codes(exc) == ["reason-required"]
    assert stored(package)[0]["status"] == "open"
    answer(package, "CH-001", response, reason="requests are idempotent on the customer id")
    assert stored(package)[0]["reason"] == "requests are idempotent on the customer id"


def test_a_reason_is_kept_when_an_answer_is_accepted_too(package: Package) -> None:
    add(package)
    answer(package, "CH-001", "accepted", reason="added FR-002")
    assert stored(package)[0]["reason"] == "added FR-002"


def test_only_a_person_configured_for_the_stage_may_answer(package: Package) -> None:
    add(package, "technical", "DEC-001", "Why not retry?")
    with pytest.raises(EilExit) as exc:
        answer(package, "CH-001", "accepted", by="Grace Lead")  # a confirmer of functional, not technical
    assert codes(exc) == ["not-a-confirmer"]
    with pytest.raises(EilExit) as exc:
        answer(package, "CH-001", "accepted", by="Mallory")
    assert codes(exc) == ["not-a-confirmer"]
    assert stored(package, "technical")[0]["status"] == "open"


def test_the_ai_cannot_answer_a_challenge(package: Package) -> None:
    add(package)
    with pytest.raises(EilExit) as exc:
        answer(package, "CH-001", "accepted", by="Claude")
    assert codes(exc) == ["ai-approval"]
    assert stored(package)[0]["status"] == "open"


def test_an_unknown_challenge_is_refused(package: Package) -> None:
    with pytest.raises(EilExit) as exc:
        answer(package, "CH-009", "accepted")
    assert codes(exc) == ["unknown-item"]


def test_all_refusals_are_reported_together_and_nothing_is_written(
    package: Package, story_dir: Story
) -> None:
    add(package)
    before = story_dir.read("functional")
    with pytest.raises(EilExit) as exc:
        answer(package, "CH-001", "rejected", by="Mallory")
    assert sorted(codes(exc)) == ["not-a-confirmer", "reason-required"]
    assert story_dir.read("functional") == before


def test_the_same_person_may_change_their_answer(package: Package) -> None:
    add(package)
    answer(package, "CH-001", "rejected", reason="no")
    answer(package, "CH-001", "accepted")
    challenge = stored(package)[0]
    assert (
        challenge["status"] == "closed" and challenge["response"] == "accepted" and "reason" not in challenge
    )


def test_answering_the_same_way_again_is_a_no_op(package: Package, story_dir: Story) -> None:
    add(package)
    answer(package, "CH-001", "accepted", reason="fine")
    before = story_dir.read("functional")
    answer(package, "CH-001", "accepted", by="Grace Lead", reason="fine")
    assert story_dir.read("functional") == before


# ---- conflicting answers (edge case)


def test_two_people_answering_differently_is_a_conflict_that_blocks_until_settled(package: Package) -> None:
    add(package)
    answer(package, "CH-001", "rejected", by="Ada Dev", reason="idempotent already")
    result = answer(package, "CH-001", "accepted", by="Grace Lead")
    challenge = stored(package)[0]
    assert result["conflict"] is True and challenge["status"] == "conflict"
    assert [(r["responder"], r["response"]) for r in challenge["responses"]] == [
        ("Ada Dev", "rejected"),
        ("Grace Lead", "accepted"),
    ]
    assert records.open_challenge_ids(package.doc("functional")) == ["CH-001"]


def test_a_configured_confirmer_settles_a_conflict_with_the_next_answer(package: Package) -> None:
    add(package)
    answer(package, "CH-001", "rejected", by="Ada Dev", reason="no")
    answer(package, "CH-001", "accepted", by="Grace Lead")
    settled = answer(package, "CH-001", "rejected", by="Ada Dev", reason="the owner decides: no")
    challenge = stored(package)[0]
    assert settled["conflict"] is False
    assert (
        challenge["status"] == "closed"
        and challenge["response"] == "rejected"
        and challenge["responder"] == "Ada Dev"
    )
    assert challenge["resolved_conflict"] is True and "responses" not in challenge
    assert records.open_challenge_ids(package.doc("functional")) == []


def test_a_person_who_is_not_a_confirmer_cannot_settle_a_conflict(package: Package) -> None:
    add(package)
    answer(package, "CH-001", "rejected", by="Ada Dev", reason="no")
    answer(package, "CH-001", "accepted", by="Grace Lead")
    with pytest.raises(EilExit) as exc:
        answer(package, "CH-001", "accepted", by="Mallory")
    assert codes(exc) == ["not-a-confirmer"]


# ---- standing constraints (FR-038)


@pytest.mark.parametrize("response", ["rejected", "deferred"])
def test_a_rejected_or_deferred_challenge_cannot_be_raised_again(package: Package, response: str) -> None:
    add(package)
    answer(package, "CH-001", response, reason="a decision")
    with pytest.raises(EilExit) as exc:
        add(package)
    assert codes(exc) == ["duplicate-of-closed"]
    assert "CH-001" in exc.value.payload["refusals"][0]["message"]


def test_equivalent_wording_is_the_same_challenge(package: Package) -> None:
    add(package)
    answer(package, "CH-001", "rejected", reason="a decision")
    with pytest.raises(EilExit) as exc:
        add(package, text="what happens when two duplicate detection requests arrive at the same time")
    assert codes(exc) == ["duplicate-of-closed"]


def test_a_different_point_on_the_same_target_is_a_new_challenge(package: Package) -> None:
    add(package)
    answer(package, "CH-001", "rejected", reason="a decision")
    assert (
        add(package, text="Which limit applies to files with more than one million rows?")["id"] == "CH-002"
    )


def test_the_same_words_about_another_target_are_a_new_challenge(package: Package) -> None:
    add(package)
    answer(package, "CH-001", "rejected", reason="a decision")
    assert add(package, target="NFR-001")["id"] == "CH-002"


def test_an_accepted_challenge_may_be_raised_again_if_the_text_still_has_the_gap(package: Package) -> None:
    add(package)
    answer(package, "CH-001", "accepted")
    assert add(package)["id"] == "CH-002"


def test_an_open_duplicate_is_not_added_twice(package: Package) -> None:
    add(package)
    with pytest.raises(EilExit) as exc:
        add(package)
    assert (
        codes(exc) == ["duplicate-of-closed"] and "still open" in exc.value.payload["refusals"][0]["message"]
    )


# ---- what reads them


def test_open_challenge_ids_lists_open_and_conflicting_ones_only(package: Package) -> None:
    add(package)
    add(package, target="NFR-001", text="Is the limit measured at p95?")
    answer(package, "CH-001", "accepted")
    assert records.open_challenge_ids(package.doc("functional")) == ["CH-002"]


def test_the_stage_documents_fingerprint_changes_with_a_challenge_but_not_with_a_status_read(
    package: Package, story_dir: Story
) -> None:
    before = package.fingerprint("functional")
    add(package)
    assert package.fingerprint("functional") != before
    assert isinstance(Doc(story_dir.read("functional")), Doc)
