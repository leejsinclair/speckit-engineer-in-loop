"""Touched artefacts, the diagram-currency and low-challenges lists, and completion's open-challenge
refusal (FR-033, FR-040, FR-045; determinism requirements 34 and 35)."""

from __future__ import annotations

import re
from typing import Any

import pytest
from eil import records, reviews, staleness
from eil.results import EilExit

from tests.helpers.derived import CONFIG, package_of, settle_derived
from tests.helpers.package import Story, completion_doc

YES = "Yes, I reviewed the evidence and the story is done."


@pytest.fixture
def story(reference_story: Story) -> Story:
    settle_derived(reference_story)
    return reference_story


def wire(story: Story, task: int, ais: int) -> None:
    text = story.read("tasks")
    story.write("tasks", re.sub(rf"(T{task:03d} .*?\(traces: )AIS-\d{{3}}\)", rf"\1AIS-{ais:03d})", text))


def codes(exc: Any) -> list[str]:
    return [r["code"] for r in exc.value.payload["refusals"]]


def keys(listed: Any) -> list[str]:
    return [e.key for e in listed.entries]


def test_no_task_reaching_an_artefact_means_nothing_is_touched(story: Story) -> None:
    assert staleness.touched_artifacts(package_of(story)) == {}


def test_a_task_with_code_touches_the_artefact_it_reaches(story: Story) -> None:
    wire(story, 3, 18)
    assert list(staleness.touched_artifacts(package_of(story))) == ["ART-004"]


def test_a_task_without_code_touches_nothing(story: Story) -> None:
    wire(story, 9, 19)
    assert staleness.touched_artifacts(package_of(story)) == {}


def test_an_artefact_whose_hash_moved_since_approval_is_touched(story: Story) -> None:
    package = package_of(story)
    approval = dict(package.record("technical", "approval") or {})
    approval["items"] = {**approval["items"], "ART-002": "sha256:" + "1" * 64}
    package.write_record("technical", "approval", approval)
    assert "ART-002" in staleness.touched_artifacts(package_of(story))


def test_diagram_currency_list_holds_only_touched_artefacts(story: Story) -> None:
    wire(story, 3, 18)
    wire(story, 4, 19)
    story.write("completion", completion_doc())
    listed = reviews.build_list(package_of(story), "completion", "diagram-currency")
    assert sorted(keys(listed)) == ["ART-004", "ART-007"]
    assert listed.purpose == "validation"


def test_answering_diagram_currency_settles_it_until_the_artefact_moves(story: Story) -> None:
    wire(story, 3, 18)
    story.write("completion", completion_doc())
    listed = reviews.build_list(package_of(story), "completion", "diagram-currency")
    reviews.answer(
        package_of(story), CONFIG, "completion", "diagram-currency",
        digest=listed.digest, by="Ada Dev", reply="all current", all_=True,
    )  # fmt: skip
    assert keys(reviews.build_list(package_of(story), "completion", "diagram-currency")) == []


def add_challenge(story: Story, stage: str, target: str, severity: str) -> str:
    out = records.add_challenge(
        package_of(story), stage, target, "Is this right?", "Priya", severity=severity
    )
    return out["id"]


def low_challenges(story: Story, n: int = 3) -> list[str]:
    story.write("completion", completion_doc())
    return [add_challenge(story, "requirements", f"REQ-00{i}", "low") for i in range(1, n + 1)]


def test_low_challenges_list_covers_every_stage_at_completion(story: Story) -> None:
    ids = low_challenges(story, 2)
    other = add_challenge(story, "functional", "FR-001", "low")
    listed = reviews.build_list(package_of(story), "completion", "low-challenges")
    assert sorted(keys(listed)) == sorted([*ids, other])
    assert all(e.severity == "low" for e in listed.entries)


def test_defer_all_closes_each_as_deferred_with_the_shared_reason_and_name(story: Story) -> None:
    ids = low_challenges(story)
    listed = reviews.build_list(package_of(story), "completion", "low-challenges")
    reviews.answer(
        package_of(story), CONFIG, "completion", "low-challenges",
        digest=listed.digest, by="Ada Dev", reply="defer all, accepted as minor", all_=True,
        defer_reason="accepted as minor",
    )  # fmt: skip
    for cid in ids:
        found = next(
            r for r in package_of(story).doc("requirements").records() if (r.obj or {}).get("id") == cid
        )
        assert found.obj["status"] == "closed" and found.obj["response"] == "deferred"
        assert found.obj["reason"] == "accepted as minor" and found.obj["responder"] == "Ada Dev"
    assert keys(reviews.build_list(package_of(story), "completion", "low-challenges")) == []


def test_defer_all_needs_a_reason(story: Story) -> None:
    low_challenges(story)
    listed = reviews.build_list(package_of(story), "completion", "low-challenges")
    with pytest.raises(EilExit) as exc:
        reviews.answer(
            package_of(story), CONFIG, "completion", "low-challenges",
            digest=listed.digest, by="Ada Dev", reply="defer all", all_=True,
        )  # fmt: skip
    assert "reason-required" in codes(exc)
    assert len(keys(reviews.build_list(package_of(story), "completion", "low-challenges"))) == 3


def test_all_except_leaves_the_named_challenges_open(story: Story) -> None:
    ids = low_challenges(story)
    listed = reviews.build_list(package_of(story), "completion", "low-challenges")
    reviews.answer(
        package_of(story), CONFIG, "completion", "low-challenges",
        digest=listed.digest, by="Ada Dev", reply=f"defer all except {ids[0]}", all_except=[ids[0]],
        defer_reason="minor",
    )  # fmt: skip
    assert keys(reviews.build_list(package_of(story), "completion", "low-challenges")) == [ids[0]]


def test_the_ai_cannot_defer_challenges(story: Story) -> None:
    low_challenges(story)
    listed = reviews.build_list(package_of(story), "completion", "low-challenges")
    with pytest.raises(EilExit) as exc:
        reviews.answer(
            package_of(story), CONFIG, "completion", "low-challenges",
            digest=listed.digest, by="Claude", reply="defer all", all_=True, defer_reason="minor",
        )  # fmt: skip
    assert "ai-approval" in codes(exc)
    assert len(keys(reviews.build_list(package_of(story), "completion", "low-challenges"))) == 3


def test_completion_is_refused_while_a_low_challenge_is_open_on_any_stage(story: Story) -> None:
    low_challenges(story, 1)
    with pytest.raises(EilExit) as exc:
        records.approve(package_of(story), CONFIG, "completion", "Ada Dev", YES)
    assert "open-challenge" in codes(exc)


def test_completion_refusal_names_the_low_challenges_list(story: Story) -> None:
    low_challenges(story, 1)
    with pytest.raises(EilExit) as exc:
        records.approve(package_of(story), CONFIG, "completion", "Ada Dev", YES)
    message = " ".join(str(r["fix"]) for r in exc.value.payload["refusals"] if r["code"] == "open-challenge")
    assert "low-challenges" in message
