"""004 T016a and T033: ``review list`` returns the stored answers (research D-72; FR-014).

While a session is open the list carries ``answers`` beside the unanswered ``entries``, whichever
surface gave them. After it closes, ``last_answers`` holds the send-backs and questions of the latest
answers with their comments, so the agent acts on them without reading the record file.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from eil import reviews
from eil.identity import Config
from eil.package import Package

from tests.helpers.page import eil

CONFIG = Config(default_developer="Ada Dev", approvers={"functional": ["Ada Dev", "Priya QA"]})


def page_answer(root: Path, key: str, disposition: str = "accept", comment: str | None = None, by: str = "Ada Dev") -> dict[str, Any]:
    package = Package(root)
    listed = reviews.build_list(package, "functional", "inferred", session_view=False)
    entry = next(e for e in listed.entries if e.key == key)
    return reviews.answer(
        package, CONFIG, "functional", "inferred", digest=None, by=by, reply="", entry=key, disposition=disposition,
        shown=entry.hash, asked=reviews.entry_question("inferred", entry), comment=comment, via="page",
    )  # fmt: skip


def listing(root: Path) -> dict[str, Any]:
    code, payload = eil(root, "review", "list", "--stage", "functional", "--kind", "inferred")
    assert code == 0, payload
    return payload


# ---- the open-session half (T016a)


def test_answers_from_the_page_and_from_chat_are_returned(review_page_story: Any) -> None:
    root = review_page_story.root
    page_answer(root, "FR-001")
    page_answer(root, "FR-002", "except", comment="Say *which* pairs.")
    code, payload = eil(root, "review", "answer", "--stage", "functional", "--kind", "inferred", "--entry", "§Actors", "--by", "Ada Dev", "--reply", "fine")
    assert code == 0, payload
    found = listing(root)
    answers = {a["key"]: a for a in found["answers"]}
    assert set(answers) == {"FR-001", "FR-002", "§Actors"}
    assert answers["FR-002"] == {
        "key": "FR-002", "disposition": "except", "by": "Ada Dev", "at": answers["FR-002"]["at"], "via": "page",
        "comment": "Say *which* pairs.", "question": "Accept FR-002 as written?",
    }  # fmt: skip
    assert answers["FR-001"]["via"] == "page" and answers["FR-001"]["comment"] is None
    assert answers["§Actors"]["via"] is None and answers["§Actors"]["question"] is None
    assert sorted(e["key"] for e in found["entries"]) == sorted([review_page_story.keys["PROSE"], review_page_story.keys["TABLE"]])


def test_no_answers_field_without_a_session(review_page_story: Any) -> None:
    assert "answers" not in listing(review_page_story.root)


# ---- the closed-session half (T033)


def close_with_a_send_back_and_a_question(built: Any) -> None:
    root = built.root
    page_answer(root, "FR-001")
    page_answer(root, "FR-002", "except", comment="Name the pairs.")
    page_answer(root, built.keys["PROSE"], "question", comment="Why this order?")
    page_answer(root, built.keys["TABLE"])
    result = page_answer(root, "§Actors")
    assert result["closed"] is True


def test_after_the_session_closes_last_answers_hold_the_send_backs_and_questions(review_page_story: Any) -> None:
    close_with_a_send_back_and_a_question(review_page_story)
    found = listing(review_page_story.root)
    assert "answers" not in found
    last = {a["key"]: a for a in found["last_answers"]}
    prose = review_page_story.keys["PROSE"]
    assert set(last) == {"FR-002", prose}
    assert last["FR-002"]["disposition"] == "except" and last["FR-002"]["comment"] == "Name the pairs."
    assert last[prose]["disposition"] == "question" and last[prose]["comment"] == "Why this order?"
    assert last[prose]["by"] == "Ada Dev" and last[prose]["via"] == "page"
    assert last[prose]["question"] == f"Accept {prose} as written?"


def test_a_questioned_key_stays_listed_after_the_session_closes(review_page_story: Any) -> None:
    close_with_a_send_back_and_a_question(review_page_story)
    keys = [e["key"] for e in listing(review_page_story.root)["entries"]]
    assert review_page_story.keys["PROSE"] in keys and "FR-002" in keys
    assert "FR-001" not in keys


def test_a_send_back_leaves_last_answers_once_it_is_accepted(review_page_story: Any) -> None:
    close_with_a_send_back_and_a_question(review_page_story)
    page_answer(review_page_story.root, "FR-002")
    found = listing(review_page_story.root)
    if "last_answers" in found:
        assert "FR-002" not in {a["key"] for a in found["last_answers"]}
