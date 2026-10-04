"""T032: answers are stored as they are given (determinism 47; research D-51; FR-015, FR-016).

A one-at-a-time list keeps each answer in a review session in the record file, so a compacted or
restarted conversation resumes at the first unanswered entry. "ok to the rest" closes the list and
marks what was not shown in full. A partial session settles nothing; when the last entry is
answered the session is applied through the ordinary answer path and removed.
"""

from __future__ import annotations

from typing import Any

import pytest
from eil import blockstatus, reviews
from eil.identity import Config
from eil.package import Package
from eil.results import EilExit

from tests.helpers.package import Story
from tests.unit.test_list_modes import with_inferred

CONFIG = Config(default_developer="Ada Dev", approvers={"requirements": ["Ada Dev", "Priya QA"]})


def pkg(story: Story) -> Package:
    return Package(story.root)


def entry(story: Story, key: str, reply: str = "ok", by: str = "Ada Dev", **kwargs: Any) -> dict[str, Any]:
    found = reviews.build_list(pkg(story), "requirements", "inferred")
    return reviews.answer(
        pkg(story),
        CONFIG,
        "requirements",
        "inferred",
        digest=found.digest,
        by=by,
        reply=reply,
        entry=key,
        **kwargs,
    )


def refused(call: Any) -> list[str]:
    with pytest.raises(EilExit) as caught:
        call()
    return [r["code"] for r in caught.value.payload["refusals"]]


def statuses(story: Story) -> dict[str, str]:
    return {
        k: i.status
        for k, i in blockstatus.block_statuses(pkg(story))["requirements"].items()
        if k.startswith("REQ-")
    }


def acceptances(story: Story) -> list[dict[str, Any]]:
    return (pkg(story).record("requirements", "provenance") or {}).get("acceptances", [])


@pytest.fixture
def five(story_dir: Story) -> list[str]:
    return with_inferred(story_dir, 5)


def test_answers_survive_a_fresh_package_and_the_list_resumes(story_dir: Story, five: list[str]) -> None:
    for key in five[:3]:
        assert entry(story_dir, key)["ok"]
    resumed = reviews.build_list(Package(story_dir.root), "requirements", "inferred")  # a compaction stand-in
    assert [e.key for e in resumed.entries] == five[3:]
    assert resumed.mode == "one-at-a-time"
    assert resumed.session == {"answered": 3, "remaining": 2}


def test_a_partial_session_settles_nothing(story_dir: Story, five: list[str]) -> None:
    for key in five[:4]:
        entry(story_dir, key)
    assert set(statuses(story_dir).values()) == {"needs-review"}
    assert acceptances(story_dir) == []


def test_the_last_answer_closes_the_session_through_the_answer_path(
    story_dir: Story, five: list[str]
) -> None:
    for key in five:
        result = entry(story_dir, key)
    assert result["closed"] is True
    assert set(statuses(story_dir).values()) == {"settled"}
    assert pkg(story_dir).story_record().get("review_sessions") in (None, {})
    accs = acceptances(story_dir)
    assert accs and all(a["mode"] == "one-at-a-time" for a in accs)
    assert sorted(k for a in accs for k in a["accepted"]) == five


def test_an_answer_lapses_when_its_entry_changes(story_dir: Story, five: list[str]) -> None:
    for key in five[:3]:
        entry(story_dir, key)
    story_dir.write(
        "requirements",
        story_dir.read("requirements").replace("Requirement number 2.", "Requirement number two."),
    )
    resumed = reviews.build_list(pkg(story_dir), "requirements", "inferred")
    assert [e.key for e in resumed.entries] == ["REQ-002", "REQ-004", "REQ-005"]


def test_ok_to_the_rest_accepts_what_remains_unseen(story_dir: Story, five: list[str]) -> None:
    entry(story_dir, five[0])
    entry(story_dir, five[1], reply="change this", disposition="except")
    found = reviews.build_list(pkg(story_dir), "requirements", "inferred")
    result = reviews.answer(
        pkg(story_dir),
        CONFIG,
        "requirements",
        "inferred",
        digest=found.digest,
        by="Ada Dev",
        reply="ok to the rest",
        rest=True,
    )
    assert result["closed"] is True
    accs = acceptances(story_dir)
    rest = next(a for a in accs if a["reply"] == "ok to the rest")
    assert sorted(rest["accepted"]) == five[2:] and sorted(rest["unseen"]) == five[2:]
    assert statuses(story_dir)["REQ-002"] == "needs-review"
    assert statuses(story_dir)["REQ-005"] == "settled"
    assert all("Requirement number" not in str(a) for a in accs), "no entry text is stored"


def test_the_rules_of_a_reply_hold_per_entry(story_dir: Story, five: list[str]) -> None:
    assert refused(lambda: entry(story_dir, five[0], by="Claude")) == ["ai-approval"]
    assert refused(lambda: entry(story_dir, five[0], reply="")) == ["reply-required"]
    assert refused(lambda: entry(story_dir, five[0], by="Mallory")) == ["not-a-confirmer"]
    assert refused(lambda: entry(story_dir, five[0], reply="ok", disposition="except")) == ["reply-mismatch"]
    assert refused(lambda: entry(story_dir, "REQ-099")) == ["unknown-entry"]
    assert pkg(story_dir).story_record().get("review_sessions") in (None, {})


def test_two_people_answering_one_entry_differently_is_a_conflict(story_dir: Story, five: list[str]) -> None:
    entry(story_dir, five[0], by="Ada Dev")
    entry(story_dir, five[0], by="Priya QA", reply="not this one", disposition="except")
    for key in five[1:]:
        entry(story_dir, key)
    assert "REQ-001" in reviews.conflicted_keys(pkg(story_dir), "requirements")


def test_a_whole_list_answer_records_its_mode(story_dir: Story) -> None:
    with_inferred(story_dir, 9)
    found = reviews.build_list(pkg(story_dir), "requirements", "inferred")
    reviews.answer(
        pkg(story_dir),
        CONFIG,
        "requirements",
        "inferred",
        digest=found.digest,
        by="Ada Dev",
        reply="ok",
        all_=True,
    )
    assert acceptances(story_dir)[-1]["mode"] == "summary"


def test_a_short_whole_list_answer_records_one_at_a_time(story_dir: Story, five: list[str]) -> None:
    found = reviews.build_list(pkg(story_dir), "requirements", "inferred")
    reviews.answer(
        pkg(story_dir),
        CONFIG,
        "requirements",
        "inferred",
        digest=found.digest,
        by="Ada Dev",
        reply="ok",
        all_=True,
    )
    assert acceptances(story_dir)[-1]["mode"] == "one-at-a-time"


def test_the_session_is_held_in_the_record_file_by_ids_and_hashes(story_dir: Story, five: list[str]) -> None:
    entry(story_dir, five[0])
    sessions = pkg(story_dir).story_record()["review_sessions"]
    (session,) = sessions.values()
    assert (
        session["stage"] == "requirements"
        and session["kind"] == "inferred"
        and session["mode"] == "one-at-a-time"
    )
    assert set(session["entries"]) == set(five)
    answer = session["answers"]["REQ-001"]
    assert set(answer) == {"by", "at", "disposition", "reply", "hash", "seen"}
    assert "Requirement number" not in str(session)
