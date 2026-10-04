"""B-38 (004 quickstart; SC-001): a Functional draft reviewed on the page.

Five listed blocks are answered through ``POST /answer``: three accepted, one sent back with a comment
and one questioned with a comment. Each answer is stored at once with ``via: page``, the fixed
question, the name, the time and the comment. The fifth closes the session into acceptances that say
they were answered on the page, and the blocks end exactly as the same answers given in chat leave them.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

import pytest
from eil import blockstatus, reviews
from eil.package import Package

from tests.fixtures import review_page
from tests.helpers.page import eil, start_page

pytestmark = pytest.mark.scenario

ANSWERS = [("accept", None), ("accept", None), ("except", "Name the pairs this applies to."), ("question", "Why this order?"), ("accept", None)]


def body(root: Path, key: str, disposition: str, comment: str | None) -> dict[str, Any]:
    listed = reviews.build_list(Package(root), "functional", "inferred", session_view=False)
    entry = next(e for e in listed.entries if e.key == key)
    return {
        "stage": "functional", "kind": "inferred", "entry": key, "disposition": disposition, "shown": entry.hash,
        "question": reviews.entry_question("inferred", entry), "comment": comment,
    }  # fmt: skip


def statuses(root: Path) -> dict[str, str]:
    return {k: i.status for k, i in blockstatus.block_statuses(Package(root))["functional"].items()}


def test_b38_a_functional_draft_reviewed_on_the_page(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import tempfile

    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    built = review_page.build(tmp_path / "page" / "specs" / "001-story")
    shutil.copytree(tmp_path / "page", tmp_path / "chat")
    chat_root = tmp_path / "chat" / "specs" / "001-story"
    root, keys = built.root, built.listed()

    page = start_page(root, "Ada Dev")
    try:
        status, _, html = page.get("/")
        assert status == 200 and "0 of 5 answered" in html
        for index, (key, (disposition, comment)) in enumerate(zip(keys, ANSWERS, strict=True)):
            status, result = page.post("/answer", body(root, key, disposition, comment))
            assert status == 200 and result["ok"] is True, result
            if index < 4:
                (session,) = Package(root).story_record()["review_sessions"].values()
                stored = session["answers"][key]
                assert stored["via"] == "page" and stored["by"] == "Ada Dev" and stored["at"]
                assert stored["question"] == body(root, key, disposition, comment)["question"]
                assert stored.get("comment") == comment
                assert stored["disposition"] == disposition
        assert result["closed"] is True
    finally:
        page.stop()

    assert Package(root).story_record().get("review_sessions") in (None, {})
    accs = Package(root).record("functional", "provenance")["acceptances"]
    assert accs and all(a["via"] == "page" for a in accs)
    assert all(set(a["questions"]) for a in accs)
    send_back = next(a for a in accs if a["except"])
    question = next(a for a in accs if a["questioned"])
    assert send_back["comments"] == {keys[2]: "Name the pairs this applies to."}
    assert question["comments"] == {keys[3]: "Why this order?"}

    for key, (disposition, comment) in zip(keys, ANSWERS, strict=True):
        code, payload = eil(
            chat_root, "review", "answer", "--stage", "functional", "--kind", "inferred", "--entry", key,
            "--disposition", disposition, "--by", "Ada Dev", "--reply", comment or "ok",
        )  # fmt: skip
        assert code == 0, payload
    assert statuses(root) == statuses(chat_root), "SC-001: the page records what chat records"
    assert statuses(root)[keys[2]] == "needs-review" and statuses(root)[keys[3]] == "needs-review"
    assert statuses(root)["FR-001"] == "settled"
