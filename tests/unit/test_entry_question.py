"""004 T016: each entry's fixed question (research D-64; determinism 58; FR-003, FR-008).

``review list`` returns, on every entry, exactly the helper's question for that kind of entry, so a
page answer records what an "Accept" confirmed. ``review answer --question`` with any other wording is
refused ``question-mismatch`` and writes nothing.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from eil import reviews
from eil.package import Package

from tests.conftest import files_snapshot
from tests.fixtures import review_page
from tests.helpers.page import eil


def questions(root: Path, stage: str = "functional", kind: str = "inferred") -> dict[str, str]:
    code, payload = eil(root, "review", "list", "--stage", stage, "--kind", kind)
    assert code == 0, payload
    return {e["key"]: e["question"] for e in payload["entries"]}


def test_an_inferred_block_and_a_scaffolding_section(review_page_story: Any) -> None:
    found = questions(review_page_story.root)
    assert found["FR-001"] == "Accept FR-001 as written?"
    prose = review_page_story.keys["PROSE"]
    assert found[prose] == f"Accept {prose} as written?"
    assert found["§Actors"] == "Accept every block under Actors as written?"


def test_changed_and_added_change_entries(tmp_path: Path) -> None:
    built = review_page.build(tmp_path / "specs" / "001-story", changes=True)
    text = built.story.read("functional")
    built.story.write("functional", text.replace("## Business Rules", "**FR-009**: The system shall export flagged pairs. (traces: REQ-001)\n\n## Business Rules"))
    found = questions(built.root, kind="changes")
    assert found["FR-001"] == "Accept FR-001 as it now reads?"
    assert found["FR-009"] == "Accept the new FR-009 as written?"
    assert found["legacy:functional"] == reviews.LEGACY_STATEMENT + " Accept?"


def test_a_removed_change_entry() -> None:
    entry = reviews.ListEntry("REQ-003", "removed", "REQ-003 was removed", "removed since it was approved")
    assert reviews.entry_question("changes", entry) == "Accept the removal of REQ-003?"


def test_the_list_carries_the_question_on_every_entry(review_page_story: Any) -> None:
    listed = reviews.build_list(Package(review_page_story.root), "functional", "inferred")
    assert all(e.to_json()["question"] == reviews.entry_question("inferred", e) for e in listed.entries)


def answer_with_question(root: Path, text: str) -> tuple[int, Any]:
    return eil(
        root, "review", "answer", "--stage", "functional", "--kind", "inferred", "--entry", "FR-001",
        "--question", text, "--by", "Ada Dev", "--reply", "ok",
    )  # fmt: skip


@pytest.mark.parametrize("text", ["Accept FR-001?", "accept fr-001 as written?", "Accept FR-002 as written?", ""])
def test_any_other_wording_is_refused_question_mismatch(review_page_story: Any, text: str) -> None:
    before = files_snapshot(review_page_story.root)
    code, payload = answer_with_question(review_page_story.root, text)
    assert code == 1
    assert [r["code"] for r in payload["refusals"]] == ["question-mismatch"]
    assert files_snapshot(review_page_story.root) == before


def test_the_helpers_own_wording_is_stored(review_page_story: Any) -> None:
    code, payload = answer_with_question(review_page_story.root, "Accept FR-001 as written?")
    assert code == 0, payload
    (session,) = Package(review_page_story.root).story_record()["review_sessions"].values()
    assert session["answers"]["FR-001"]["question"] == "Accept FR-001 as written?"
