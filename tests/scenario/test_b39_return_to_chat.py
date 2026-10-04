"""B-39 (004 quickstart; US2, FR-014 to FR-016): back to the chat after "done".

After the B-38 answers, ``review list --current`` returns the send-back and the question with their
comments and the name, so the agent acts on them without the record file. Once the sent-back block is
edited it is listed again and highlighted; the questioned block stays listed. A comment on a settled
block reopens it, listed with its ``reopened`` mark.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from eil import reviews
from eil.content import blocks_of
from eil.package import Package

from tests.fixtures import review_page
from tests.helpers.page import eil, start_page

pytestmark = pytest.mark.scenario

ANSWERS = [
    ("accept", None),
    ("accept", None),
    ("except", "Name the pairs this applies to."),
    ("question", "Why this order?"),
    ("accept", None),
]


def body(root: Path, key: str, disposition: str, comment: str | None) -> dict[str, Any]:
    listed = reviews.build_list(Package(root), "functional", "inferred", session_view=False)
    entry = next(e for e in listed.entries if e.key == key)
    return {
        "stage": "functional", "kind": "inferred", "entry": key, "disposition": disposition, "shown": entry.hash,
        "question": reviews.entry_question("inferred", entry), "comment": comment,
    }  # fmt: skip


def test_b39_return_to_chat_and_act_on_the_answers(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import tempfile

    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    built = review_page.build(tmp_path / "specs" / "001-story")
    root, keys = built.root, built.listed()
    page = start_page(root, "Ada Dev")
    try:
        for key, (disposition, comment) in zip(keys, ANSWERS, strict=True):
            assert page.post("/answer", body(root, key, disposition, comment))[1]["ok"]

        code, current = eil(root, "review", "list", "--current")
        assert code == 0 and current["current"]["stage"] == "functional"
        last = {a["key"]: a for a in current["last_answers"]}
        assert (
            last[keys[2]]["disposition"] == "except"
            and last[keys[2]]["comment"] == "Name the pairs this applies to."
        )
        assert last[keys[3]]["disposition"] == "question" and last[keys[3]]["comment"] == "Why this order?"
        assert {a["by"] for a in last.values()} == {"Ada Dev"}

        prose = next(b for b in blocks_of(Package(root).doc("functional")) if b.key == keys[2])
        text = built.story.read("functional")
        built.story.write(
            "functional",
            text.replace(prose.text, prose.text.replace("in the order they were found", "newest first")),
        )
        _, _, html = page.get("/")
        listed = [e["key"] for e in eil(root, "review", "list", "--current")[1]["entries"]]
        reworked = next(k for k in listed if k.startswith("Functional Requirements#"))
        assert reworked != keys[2], "the edited prose block has a new key"
        assert f'data-entry="{reworked}"' in html and f"Needs review: {reworked}" in html
        assert keys[3] in listed and f'data-entry="{keys[3]}"' in html

        status, payload = page.post(
            "/reopen",
            {
                "stage": "functional",
                "key": "FR-003",
                "shown": _hash(root, "FR-003"),
                "comment": "Phone layout?",
            },
        )
        assert payload["ok"] is True, payload
        _, current = eil(root, "review", "list", "--current")
        assert "FR-003" in [e["key"] for e in current["entries"]]
        mark = Package(root).record("functional", "provenance")["blocks"]["FR-003"]["reopened"]
        assert mark["comment"] == "Phone layout?" and mark["via"] == "page"
    finally:
        page.stop()


def _hash(root: Path, key: str) -> str:
    return next(b.hash for b in blocks_of(Package(root).doc("functional")) if b.key == key)
