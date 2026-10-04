"""004 T019, T035 and T059: the page's routes (research D-61, D-63; determinism 57 and 60).

``GET /`` renders the current review. ``POST /answer`` stores through ``reviews.answer`` under the
record lock and returns the helper's result or refusals unchanged; an answer to a list that is not
current is refused ``not-current``. ``POST /name`` changes who is answering, never to the AI.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pytest
from eil import blockstatus, recordfile, reviews
from eil.package import Package

from tests.conftest import files_snapshot
from tests.fixtures import review_page
from tests.helpers.page import Page, eil, start_page


def entry_of(root: Path, key: str, kind: str = "inferred", stage: str = "functional") -> reviews.ListEntry:
    listed = reviews.build_list(Package(root), stage, kind, session_view=False)
    return next(e for e in listed.entries if e.key == key)


def body(root: Path, key: str, disposition: str = "accept", comment: str | None = None, kind: str = "inferred", stage: str = "functional") -> dict[str, Any]:
    entry = entry_of(root, key, kind, stage)
    return {
        "stage": stage, "kind": kind, "entry": key, "disposition": disposition, "shown": entry.hash,
        "question": reviews.entry_question(kind, entry), "comment": comment,
    }  # fmt: skip


def refusals(payload: Any) -> list[str]:
    return [r["code"] for r in payload.get("refusals", [])]


def session(root: Path) -> dict[str, Any]:
    (held,) = Package(root).story_record()["review_sessions"].values()
    return held


def test_get_renders_the_current_review(page_server: Page, review_page_story: Any) -> None:
    status, headers, text = page_server.get("/")
    assert status == 200 and headers["Content-Type"].startswith("text/html")
    for key in review_page_story.listed():
        assert f'data-entry="{key}"' in text
    assert "Functional Specification: blocks that need review" in text


def test_post_answer_stores_through_the_answer_path(page_server: Page, review_page_story: Any) -> None:
    root = review_page_story.root
    status, payload = page_server.post("/answer", body(root, "FR-001"))
    assert status == 200 and payload["ok"] is True and payload["closed"] is False
    assert payload["remaining"] and "state" in payload
    stored = session(root)["answers"]["FR-001"]
    assert stored["via"] == "page" and stored["by"] == "Ada Dev" and stored["reply"] == "Accept"
    assert not (root / "eil-record.json.lock").exists()


def test_post_answer_returns_refusals_unchanged(page_server: Page, review_page_story: Any) -> None:
    root = review_page_story.root
    before = files_snapshot(root)
    status, payload = page_server.post("/answer", body(root, "FR-002", "except"))
    assert status == 200 and payload["ok"] is False and refusals(payload) == ["comment-required"]
    assert files_snapshot(root) == before


@pytest.mark.parametrize(("stage", "kind"), [("requirements", "inferred"), ("functional", "changes"), ("technical", "inferred")])
def test_an_answer_to_a_list_that_is_not_current_is_refused(page_server: Page, review_page_story: Any, stage: str, kind: str) -> None:
    root = review_page_story.root
    before = files_snapshot(root)
    status, payload = page_server.post("/answer", {**body(root, "FR-001"), "stage": stage, "kind": kind})
    assert status == 200 and refusals(payload) == ["not-current"]
    assert files_snapshot(root) == before


@pytest.mark.parametrize("name", ["Claude", "AI", "assistant", "  claude code "])
def test_determinism_60_the_name_cannot_become_the_ai(page_server: Page, name: str) -> None:
    status, payload = page_server.post("/name", {"name": name})
    assert status == 200 and refusals(payload) == ["ai-approval"]
    assert page_server.server.name == "Ada Dev"


def test_a_new_name_is_used_by_the_next_answer(page_server: Page, review_page_story: Any) -> None:
    status, payload = page_server.post("/name", {"name": "Priya QA"})
    assert status == 200 and payload["ok"] is True and payload["name"] == "Priya QA"
    page_server.post("/answer", body(review_page_story.root, "FR-002", "question", comment="Which pairs?"))
    assert session(review_page_story.root)["answers"]["FR-002"]["by"] == "Priya QA"


def test_determinism_60_a_page_accept_from_a_non_confirmer_is_refused(page_server: Page, review_page_story: Any) -> None:
    page_server.post("/name", {"name": "Mallory Guest"})
    status, payload = page_server.post("/answer", body(review_page_story.root, "FR-001"))
    assert refusals(payload) == ["not-a-confirmer"]


def test_the_same_persons_later_answer_replaces_the_earlier(page_server: Page, review_page_story: Any) -> None:
    root = review_page_story.root
    page_server.post("/answer", body(root, "FR-001"))
    page_server.post("/answer", body(root, "FR-001", "except", comment="On reflection, no."))
    held = session(root)
    assert held["answers"]["FR-001"]["disposition"] == "except"
    assert "superseded" not in held


def test_a_different_persons_conflicting_answer_is_kept_as_in_003(page_server: Page, review_page_story: Any) -> None:
    root = review_page_story.root
    page_server.post("/answer", body(root, "FR-001"))
    page_server.post("/name", {"name": "Priya QA"})
    page_server.post("/answer", body(root, "FR-001", "except", comment="Not this one."))
    held = session(root)
    assert held["answers"]["FR-001"]["by"] == "Priya QA"
    assert held["superseded"] == [{"key": "FR-001", **{k: v for k, v in held["superseded"][0].items() if k != "key"}}]
    assert held["superseded"][0]["by"] == "Ada Dev" and held["superseded"][0]["disposition"] == "accept"
    page_server.post("/name", {"name": "Ada Dev"})
    for key in review_page_story.listed()[1:]:
        page_server.post("/answer", body(root, key))
    assert "FR-001" in reviews.conflicted_keys(Package(root), "functional")


def test_a_malformed_record_is_refused_as_on_the_command_line(page_server: Page, review_page_story: Any) -> None:
    root = review_page_story.root
    recordfile.path(root).write_text('{"version": 1, "stages": {}, "nonsense": true}\n')
    before = files_snapshot(root)
    status, payload = page_server.post("/answer", body_without_lookup("FR-001"))
    code, cli = eil(root, "review", "answer", "--stage", "functional", "--kind", "inferred", "--entry", "FR-001", "--by", "Ada Dev", "--reply", "ok")
    assert files_snapshot(root) == before
    assert code == 1
    assert payload["ok"] is False
    assert [(r["code"], r["message"]) for r in payload["refusals"]] == [(r["code"], r["message"]) for r in cli["refusals"]]
    status, _, text = page_server.get("/")
    assert status == 200
    assert "disabled" in text and "malformed" in text.lower()
    assert 'class="notice' in text


def body_without_lookup(key: str) -> dict[str, Any]:
    return {"stage": "functional", "kind": "inferred", "entry": key, "disposition": "accept", "shown": None, "question": None, "comment": None}


# ---- determinism 57


FIVE = [("accept", None), ("accept", None), ("accept", None), ("except", "Name the pairs."), ("question", "Why this order?")]


def test_determinism_57_the_page_and_the_command_line_record_the_same(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import tempfile

    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    original = review_page.build(tmp_path / "a" / "specs" / "001-story")
    shutil.copytree(tmp_path / "a", tmp_path / "b")
    on_page, in_chat = original.root, tmp_path / "b" / "specs" / "001-story"
    keys = original.listed()
    page = start_page(on_page)
    try:
        for key, (disposition, comment) in zip(keys, FIVE, strict=True):
            status, payload = page.post("/answer", body(on_page, key, disposition, comment))
            assert payload["ok"] is True, payload
    finally:
        page.stop()
    for key, (disposition, comment) in zip(keys, FIVE, strict=True):
        argv = ["review", "answer", "--stage", "functional", "--kind", "inferred", "--entry", key, "--disposition", disposition, "--by", "Ada Dev"]
        argv += ["--reply", comment or "ok"]
        code, payload = eil(in_chat, *argv)
        assert code == 0, payload

    def outcome(root: Path) -> Any:
        package = Package(root)
        statuses = {k: i.status for k, i in blockstatus.block_statuses(package)["functional"].items()}
        accs = package.record("functional", "provenance")["acceptances"]
        return statuses, sorted(k for a in accs for k in a["except"]), sorted(k for a in accs for k in a["questioned"]), sorted(k for a in accs for k in a["accepted"])

    assert outcome(on_page) == outcome(in_chat)

    def scrub(root: Path) -> Any:
        data = json.loads(recordfile.path(root).read_text())
        prov = data["stages"]["functional"]["provenance"]
        for acc in prov["acceptances"]:
            for name in ("via", "questions", "comments", "reply", "id", "at"):
                acc.pop(name, None)
        for block in prov["blocks"].values():
            if "reviewed" in block:
                block["reviewed"] = {k: v for k, v in block["reviewed"].items() if k not in ("reply", "list", "at")}
        prov["acceptances"] = sorted(prov["acceptances"], key=lambda a: json.dumps(a, sort_keys=True))
        return data

    assert scrub(on_page) == scrub(in_chat)

