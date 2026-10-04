"""004 T034: a comment reopens any settled block (research D-65; determinism 61; FR-016).

``--reopen`` now reaches every settled block of the stage on the ``inferred`` list, restated and
decided ones included. It writes a ``reopened`` mark with the comment; the block's text, fingerprint
and class do not change, but it needs review again until a person accepts it, which removes the mark.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from eil import blockstatus, reviews
from eil.identity import Config
from eil.package import Package
from eil.results import EilExit

from tests.conftest import files_snapshot
from tests.helpers.page import eil

CONFIG = Config(default_developer="Ada Dev", approvers={"functional": ["Ada Dev"]})
COMMENT = "Is *side by side* right on a phone? <b>check</b>"


def provenance(root: Path) -> dict[str, Any]:
    return Package(root).record("functional", "provenance") or {}


def status_of(root: Path, key: str) -> str:
    return blockstatus.block_statuses(Package(root))["functional"][key].status


def reopen(root: Path, key: str = "FR-003", comment: str = COMMENT, via: str | None = "page", by: str = "Ada Dev") -> dict[str, Any]:
    return reviews.answer(
        Package(root), CONFIG, "functional", "inferred", digest=None, by=by, reply="" if via else comment,
        reopen=[key], comment=comment, via=via,
    )  # fmt: skip


def settle_everything(built: Any) -> None:
    for key in built.listed():
        code, payload = eil(built.root, "review", "answer", "--stage", "functional", "--kind", "inferred", "--entry", key, "--by", "Ada Dev", "--reply", "ok")
        assert code == 0, payload


def test_determinism_61_a_comment_on_a_restated_settled_block_reopens_it(review_page_story: Any) -> None:
    root = review_page_story.root
    assert status_of(root, "FR-003") == "settled"
    before = provenance(root)["blocks"]["FR-003"]
    text_before = review_page_story.story.read("functional")
    reopen(root)
    entry = provenance(root)["blocks"]["FR-003"]
    mark = entry["reopened"]
    assert set(mark) == {"by", "at", "list", "comment", "via"}
    assert mark["by"] == "Ada Dev" and mark["comment"] == COMMENT and mark["via"] == "page" and mark["list"].startswith("RVW-")
    assert entry["hash"] == before["hash"] and entry["class"] == before["class"] == "restated"
    assert entry["cites"] == before["cites"]
    assert review_page_story.story.read("functional") == text_before, "the document's text and fingerprint are unchanged"
    assert status_of(root, "FR-003") == "needs-review"
    listed = reviews.build_list(Package(root), "functional", "inferred")
    assert "FR-003" in [e.key for e in listed.entries]


def test_accepting_it_removes_the_mark(review_page_story: Any) -> None:
    root = review_page_story.root
    settle_everything(review_page_story)
    reopen(root)
    code, payload = eil(root, "review", "answer", "--stage", "functional", "--kind", "inferred", "--entry", "FR-003", "--by", "Ada Dev", "--reply", "ok")
    assert code == 0 and payload["closed"] is True, payload
    entry = provenance(root)["blocks"]["FR-003"]
    assert "reopened" not in entry
    assert entry["class"] == "restated"
    assert status_of(root, "FR-003") == "settled"


def test_editing_a_reopened_block_keeps_the_mark_until_it_is_settled(review_page_story: Any) -> None:
    root = review_page_story.root
    reopen(root)
    text = review_page_story.story.read("functional")
    review_page_story.story.write("functional", text.replace("shows both customers side by side.", "shows both customers one above the other."))
    assert provenance(root)["blocks"]["FR-003"]["reopened"]["comment"] == COMMENT
    assert status_of(root, "FR-003") == "needs-review"


def test_show_says_why_the_block_is_back(review_page_story: Any) -> None:
    reopen(review_page_story.root, comment="Phone layout?")
    code, payload = eil(review_page_story.root, "show", "functional")
    assert code == 0
    line = next(ln for ln in payload["text"].splitlines() if ln.startswith("**FR-003**"))
    assert line.endswith("[ai-draft] (reopened by Ada Dev: Phone layout?)")


def test_the_cli_reopens_with_a_comment(review_page_story: Any) -> None:
    code, payload = eil(
        review_page_story.root, "review", "answer", "--stage", "functional", "--kind", "inferred", "--reopen", "FR-003",
        "--comment", "Phone layout?", "--by", "Ada Dev", "--reply", "Reopen FR-003: phone layout?",
    )  # fmt: skip
    assert code == 0, payload
    mark = provenance(review_page_story.root)["blocks"]["FR-003"]["reopened"]
    assert mark["comment"] == "Phone layout?" and "via" not in mark


def test_an_adopted_settled_block_can_be_reopened_too(review_page_story: Any) -> None:
    from eil.content import blocks_of

    root = review_page_story.root
    key = next(b.key for b in blocks_of(Package(root).doc("functional")) if b.section == "Validation")
    assert status_of(root, key) == "settled"
    reopen(root, key)
    assert status_of(root, key) == "needs-review"
    assert provenance(root)["blocks"][key]["class"] == "adopted"


def test_a_block_that_is_not_settled_is_refused_as_in_003(review_page_story: Any) -> None:
    before = files_snapshot(review_page_story.root)
    with pytest.raises(EilExit) as caught:
        reopen(review_page_story.root, "FR-099")
    assert [r["code"] for r in caught.value.payload["refusals"]] == ["unknown-item"]
    assert files_snapshot(review_page_story.root) == before


def test_a_page_reopen_needs_a_comment(review_page_story: Any) -> None:
    with pytest.raises(EilExit) as caught:
        reopen(review_page_story.root, comment="  ")
    assert [r["code"] for r in caught.value.payload["refusals"]] == ["comment-required"]


def test_a_reopen_shown_an_older_version_is_refused(review_page_story: Any) -> None:
    root = review_page_story.root
    with pytest.raises(EilExit) as caught:
        reviews.answer(
            Package(root), CONFIG, "functional", "inferred", digest=None, by="Ada Dev", reply="", reopen=["FR-003"],
            comment="Phone?", via="page", shown="sha256:" + "0" * 64,
        )  # fmt: skip
    assert [r["code"] for r in caught.value.payload["refusals"]] == ["entry-changed"]
