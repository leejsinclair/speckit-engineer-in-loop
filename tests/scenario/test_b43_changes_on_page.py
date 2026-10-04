"""B-43 (004 quickstart; US6): re-approving a changed stage with the page.

An approved Functional stage with two changed items (and the legacy entry its old approval brings) is
current as ``functional/changes``. One change is accepted and one sent back on the page; ``review
confirm`` then refuses the re-sign exactly as it does after the same answers in chat. After the rework
and an accept on the page, it proceeds.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

import pytest
from eil import reviews
from eil.package import Package

from tests.fixtures import review_page
from tests.helpers.page import Page, eil, start_page

pytestmark = pytest.mark.scenario
REWORK = ("dismiss or confirm a flagged pair.", "dismiss or confirm a flagged pair, with a reason.")


def answer(page: Page, root: Path, key: str, disposition: str = "accept", comment: str | None = None) -> Any:
    entry = next(
        e
        for e in reviews.build_list(Package(root), "functional", "changes", session_view=False).entries
        if e.key == key
    )
    status, payload = page.post(
        "/answer",
        {"stage": "functional", "kind": "changes", "entry": key, "disposition": disposition, "shown": entry.hash, "question": entry.question, "comment": comment},
    )  # fmt: skip
    assert payload["ok"] is True, payload
    return payload


def confirm(root: Path) -> tuple[int, Any]:
    return eil(root, "review", "confirm", "--stage", "functional", "--by", "Ada Dev", "--confirmation", "yes")


def test_b43_a_changed_stage_re_approved_on_the_page(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import tempfile

    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    built = review_page.build(tmp_path / "page" / "specs" / "001-story", changes=True)
    shutil.copytree(tmp_path / "page", tmp_path / "chat")
    root, chat = built.root, tmp_path / "chat" / "specs" / "001-story"
    assert eil(root, "review", "list", "--current")[1]["current"] == {
        "stage": "functional",
        "kind": "changes",
        "document": "functional",
    }

    page = start_page(root)
    try:
        _, _, html = page.get("/")
        assert (
            "Functional Specification: changes since approval" in html
            and '<section class="panel legacy"' in html
        )
        answer(page, root, "FR-001")
        answer(page, root, "FR-002", "except", "Say what confirming does.")
        answer(page, root, "legacy:functional")
        for key, disposition, reply in (
            ("FR-001", "accept", "ok"),
            ("FR-002", "except", "Say what confirming does."),
            ("legacy:functional", "accept", "ok"),
        ):
            code, payload = eil(
                chat,
                "review",
                "answer",
                "--stage",
                "functional",
                "--kind",
                "changes",
                "--entry",
                key,
                "--disposition",
                disposition,
                "--by",
                "Ada Dev",
                "--reply",
                reply,
            )
            assert code == 0, payload
        on_page, in_chat = confirm(root), confirm(chat)
        assert on_page[0] == in_chat[0] == 1
        assert (
            [r["code"] for r in on_page[1]["refusals"]]
            == [r["code"] for r in in_chat[1]["refusals"]]
            == ["changes-unanswered"]
        )

        text = built.story.read("functional")
        built.story.write("functional", text.replace(*REWORK))
        listed = [e["key"] for e in eil(root, "review", "list", "--current")[1]["entries"]]
        assert "FR-002" in listed
        for key in listed:
            answer(page, root, key)
    finally:
        page.stop()
    import json

    summaries = tmp_path / "summaries.json"
    summaries.write_text(json.dumps({"stage": "functional", "summaries": [
        {"key": "FR-001", "summary": "Flags duplicates on every import."},
        {"key": "FR-002", "summary": "Analysts may also confirm a pair, with a reason."},
    ]}))  # fmt: skip
    code, payload = eil(
        root,
        "review",
        "confirm",
        "--stage",
        "functional",
        "--by",
        "Ada Dev",
        "--confirmation",
        "yes",
        "--summaries",
        str(summaries),
    )
    assert code == 0, payload
    assert Package(root).state("functional").state == "approved"
