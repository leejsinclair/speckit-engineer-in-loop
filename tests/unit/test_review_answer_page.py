"""004 T017: one answer path, extended (research D-63, D-70; determinism 56, 60 and 69).

``reviews.answer`` gains ``shown`` (the version the person saw), ``via``, ``asked`` (the fixed question)
and ``comment``. A page answer is the same call a chat answer is, with those fields; the refusals, the
session, superseding and closing are shared. A session answered partly on the page and partly in chat
closes into one acceptance per surface, and only the page one says so.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from eil import recordfile, reviews
from eil.blocks import provenance_problems
from eil.identity import Config
from eil.package import Package
from eil.results import EilExit

from tests.conftest import files_snapshot
from tests.fixtures import review_page
from tests.helpers.page import eil

CONFIG = Config(default_developer="Ada Dev", approvers={"functional": ["Ada Dev"]})


def entry_of(root: Path, key: str, kind: str = "inferred") -> reviews.ListEntry:
    listed = reviews.build_list(Package(root), "functional", kind, session_view=False)
    return next(e for e in listed.entries if e.key == key)


def page(
    root: Path,
    key: str,
    disposition: str = "accept",
    comment: str | None = None,
    by: str = "Ada Dev",
    **extra: Any,
) -> dict[str, Any]:
    entry = entry_of(root, key)
    kwargs: dict[str, Any] = {
        "shown": entry.hash,
        "asked": reviews.entry_question("inferred", entry),
        **extra,
    }
    return reviews.answer(
        Package(root), CONFIG, "functional", "inferred", digest=None, by=by, reply="", entry=key,
        disposition=disposition, comment=comment, via="page", **kwargs,
    )  # fmt: skip


def codes(call: Any) -> list[str]:
    with pytest.raises(EilExit) as caught:
        call()
    return [r["code"] for r in caught.value.payload["refusals"]]


def session(root: Path) -> dict[str, Any]:
    (held,) = Package(root).story_record()["review_sessions"].values()
    return held


def acceptances(root: Path) -> list[dict[str, Any]]:
    return (Package(root).record("functional", "provenance") or {}).get("acceptances", [])


# ---- determinism 56, CLI half


def test_a_stale_shown_hash_is_refused_entry_changed(review_page_story: Any) -> None:
    root = review_page_story.root
    shown = entry_of(root, "FR-001").hash
    text = review_page_story.story.read("functional")
    review_page_story.story.write(
        "functional",
        text.replace("flag duplicate customers on import.", "flag duplicate customers on each import."),
    )
    before = files_snapshot(root)
    code, payload = eil(
        root, "review", "answer", "--stage", "functional", "--kind", "inferred", "--entry", "FR-001",
        "--shown", shown, "--by", "Ada Dev", "--reply", "ok",
    )  # fmt: skip
    assert code == 1
    (refusal,) = payload["refusals"]
    assert refusal["code"] == "entry-changed"
    now = entry_of(root, "FR-001")
    assert refusal["current"] == {"key": "FR-001", "hash": now.hash, "what": now.what}
    assert now.hash != shown
    assert files_snapshot(root) == before


def test_the_current_shown_hash_is_accepted(review_page_story: Any) -> None:
    root = review_page_story.root
    code, payload = eil(
        root, "review", "answer", "--stage", "functional", "--kind", "inferred", "--entry", "FR-001",
        "--shown", entry_of(root, "FR-001").hash, "--by", "Ada Dev", "--reply", "ok",
    )  # fmt: skip
    assert code == 0, payload


# ---- comments, replies and via


@pytest.mark.parametrize(
    "comment",
    [
        "Plain words.",
        "**Bold** and `code` and [a link](https://example.org)",
        '<img src=x onerror="alert(1)"> & <b>',
        "x" * 10_240,
    ],
)
def test_a_comment_is_stored_verbatim(review_page_story: Any, comment: str) -> None:
    page(review_page_story.root, "FR-002", "except", comment=comment)
    stored = session(review_page_story.root)["answers"]["FR-002"]
    assert stored["comment"] == comment and stored["reply"] == comment


def test_a_cli_comment_is_stored_verbatim_too(review_page_story: Any) -> None:
    code, payload = eil(
        review_page_story.root, "review", "answer", "--stage", "functional", "--kind", "inferred", "--entry", "FR-002",
        "--disposition", "except", "--comment", "Say *which* pairs.", "--by", "Ada Dev", "--reply", "not quite",
    )  # fmt: skip
    assert code == 0, payload
    stored = session(review_page_story.root)["answers"]["FR-002"]
    assert stored["comment"] == "Say *which* pairs." and stored["reply"] == "not quite"
    assert "via" not in stored, "a command-line call is never recorded as a page answer"


@pytest.mark.parametrize("disposition", ["except", "question"])
@pytest.mark.parametrize("comment", [None, "", "   "])
def test_a_page_send_back_or_question_needs_a_comment(
    review_page_story: Any, disposition: str, comment: str | None
) -> None:
    before = files_snapshot(review_page_story.root)
    assert codes(lambda: page(review_page_story.root, "FR-002", disposition, comment=comment)) == [
        "comment-required"
    ]
    assert files_snapshot(review_page_story.root) == before


def test_a_page_accept_replies_accept_or_its_comment(review_page_story: Any) -> None:
    page(review_page_story.root, "FR-001")
    page(review_page_story.root, "FR-002", comment="Fine, but tidy the wording later.")
    answers = session(review_page_story.root)["answers"]
    assert answers["FR-001"]["reply"] == "Accept" and "comment" not in answers["FR-001"]
    assert answers["FR-002"]["reply"] == "Fine, but tidy the wording later."
    assert answers["FR-001"]["via"] == "page" and answers["FR-001"]["question"] == "Accept FR-001 as written?"


def test_the_question_must_be_the_helpers(review_page_story: Any) -> None:
    assert codes(lambda: page(review_page_story.root, "FR-001", asked="Is FR-001 fine?")) == [
        "question-mismatch"
    ]


def test_the_cli_has_no_via_flag(review_page_story: Any) -> None:
    code, _ = eil(
        review_page_story.root, "review", "answer", "--stage", "functional", "--kind", "inferred", "--entry", "FR-001",
        "--via", "page", "--by", "Ada Dev", "--reply", "ok",
    )  # fmt: skip
    assert code == 2


# ---- closing groups by surface


def test_a_session_closes_into_one_acceptance_per_surface(review_page_story: Any) -> None:
    root = review_page_story.root
    keys = review_page_story.listed()
    page(root, keys[0])
    page(root, keys[1], "except", comment="Name the pairs.")
    for key in keys[2:]:
        code, payload = eil(
            root,
            "review",
            "answer",
            "--stage",
            "functional",
            "--kind",
            "inferred",
            "--entry",
            key,
            "--by",
            "Ada Dev",
            "--reply",
            "ok",
        )
        assert code == 0, payload
    assert payload["closed"] is True
    accs = acceptances(root)
    on_page = [a for a in accs if a.get("via") == "page"]
    in_chat = [a for a in accs if "via" not in a]
    assert len(on_page) == 2 and len(in_chat) == 1, (
        "accept and send-back on the page differ in reply, so two groups"
    )
    for acc in on_page:
        assert set(acc["questions"]) <= {keys[0], keys[1]}
    send_back = next(a for a in on_page if a["except"])
    assert send_back["comments"] == {keys[1]: "Name the pairs."}
    assert send_back["questions"] == {keys[1]: f"Accept {keys[1]} as written?"}
    assert "questions" not in in_chat[0] and "comments" not in in_chat[0]
    assert sorted(in_chat[0]["accepted"]) == sorted(_expand(root, keys[2:]))


def _expand(root: Path, keys: list[str]) -> list[str]:
    out: list[str] = []
    for key in keys:
        out += entry_of_any(root, key)
    return out


def entry_of_any(root: Path, key: str) -> list[str]:
    from eil.content import blocks_of

    if not key.startswith("§"):
        return [key]
    return [b.key for b in blocks_of(Package(root).doc("functional")) if b.section == key[1:]]


# ---- the record file's grammar


def test_problems_accepts_the_new_fields_and_rejects_unknown_ones(review_page_story: Any) -> None:
    acceptance = {
        "id": "RVW-001", "stage": "functional", "kind": "inferred", "digest": "sha256:x", "by": "Ada Dev",
        "at": "2026-10-04T00:00:00Z", "reply": "Accept", "accepted": ["FR-001"], "except": [], "questioned": [],
        "reopened": [], "hashes": {"FR-001": "sha256:y"}, "mode": "one-at-a-time", "via": "page",
        "questions": {"FR-001": "Accept FR-001 as written?"}, "comments": {"FR-001": "fine"}, "together": {"FR-001": "Functional Requirements"},
    }  # fmt: skip
    assert provenance_problems({"version": 1, "blocks": {}, "acceptances": [acceptance]}) == []
    assert (
        provenance_problems({"version": 1, "blocks": {}, "acceptances": [{**acceptance, "shown": "x"}]}) != []
    )
    answer = {"by": "Ada Dev", "at": "t", "disposition": "accept", "reply": "Accept", "hash": "h", "seen": True,
              "via": "page", "question": "q", "comment": "c", "together": "S"}  # fmt: skip
    data = {
        "version": 1,
        "story": {
            "review_sessions": {
                "k": {"stage": "functional", "kind": "inferred", "answers": {"FR-001": answer}}
            }
        },
        "stages": {},
    }
    assert recordfile.problems(data) == []
    data["story"]["review_sessions"]["k"]["answers"]["FR-001"]["shown"] = "x"
    assert recordfile.problems(data) != []


# ---- determinism 60


def test_a_page_accept_from_someone_not_a_confirmer_is_refused(review_page_story: Any) -> None:
    assert codes(lambda: page(review_page_story.root, "FR-001", by="Mallory Guest")) == ["not-a-confirmer"]


def test_a_page_answer_from_the_ai_is_refused(review_page_story: Any) -> None:
    assert "ai-approval" in codes(lambda: page(review_page_story.root, "FR-001", by="Claude"))


# ---- determinism 69


def test_a_summary_mode_list_answered_on_the_page_then_whole_in_chat(tmp_path: Path) -> None:
    built = review_page.build(tmp_path / "specs" / "001-story", entries=10)
    root = built.root
    page(root, "FR-001")
    assert session(root)["mode"] == "summary"
    code, listed = eil(root, "review", "list", "--stage", "functional", "--kind", "inferred")
    assert code == 0 and [e["key"] for e in listed["entries"]] == [f"FR-{n:03d}" for n in range(2, 11)]
    code, payload = eil(
        root, "review", "answer", "--stage", "functional", "--kind", "inferred", "--all", "--digest", listed["digest"],
        "--by", "Ada Dev", "--reply", "ok",
    )  # fmt: skip
    assert code == 0, payload
    assert payload["closed"] is True
    assert Package(root).story_record().get("review_sessions") in (None, {})
    assert sorted(k for a in acceptances(root) for k in a["accepted"]) == [
        f"FR-{n:03d}" for n in range(1, 11)
    ]
    assert json.loads(recordfile.path(root).read_text())  # valid JSON
