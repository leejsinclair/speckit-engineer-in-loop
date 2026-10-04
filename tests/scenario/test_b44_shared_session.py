"""B-44 (004 quickstart; FR-013): one session, two surfaces.

On a 6-entry list, three entries are answered on the page; the command line's ``review list`` then
returns only the other three, and ``review answer --entry`` answers them. No entry is asked twice, and
the session closes once, with the page's answers and the chat answers recorded as separate acceptances.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from eil import reviews
from eil.package import Package

from tests.fixtures import review_page
from tests.helpers.page import eil, start_page

pytestmark = pytest.mark.scenario


def test_b44_answers_on_the_page_and_in_chat_share_one_session(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import tempfile

    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    built = review_page.build(tmp_path / "specs" / "001-story", entries=6)
    root = built.root
    keys = [f"FR-{n:03d}" for n in range(1, 7)]
    page = start_page(root, "Ada Dev")
    try:
        for key in keys[:3]:
            entry = next(
                e
                for e in reviews.build_list(
                    Package(root), "functional", "inferred", session_view=False
                ).entries
                if e.key == key
            )
            status, payload = page.post(
                "/answer",
                {"stage": "functional", "kind": "inferred", "entry": key, "disposition": "accept", "shown": entry.hash,
                 "question": entry.question, "comment": None},
            )  # fmt: skip
            assert payload["ok"] is True and payload["closed"] is False
    finally:
        page.stop()

    code, listed = eil(root, "review", "list", "--stage", "functional", "--kind", "inferred")
    assert code == 0
    assert [e["key"] for e in listed["entries"]] == keys[3:], "no entry is asked twice"
    assert [a["key"] for a in listed["answers"]] == keys[:3]
    closed = []
    for key in keys[3:]:
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
        closed.append(payload["closed"])
    assert closed == [False, False, True], "the session closes once"
    accs = Package(root).record("functional", "provenance")["acceptances"]
    assert len(accs) == 2
    page_acc = next(a for a in accs if a.get("via") == "page")
    chat_acc = next(a for a in accs if "via" not in a)
    assert sorted(page_acc["accepted"]) == keys[:3] and sorted(chat_acc["accepted"]) == keys[3:]
    assert Package(root).story_record().get("review_sessions") in (None, {})
