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


def body(
    root: Path,
    key: str,
    disposition: str = "accept",
    comment: str | None = None,
    kind: str = "inferred",
    stage: str = "functional",
) -> dict[str, Any]:
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


@pytest.mark.parametrize(
    ("stage", "kind"), [("requirements", "inferred"), ("functional", "changes"), ("technical", "inferred")]
)
def test_an_answer_to_a_list_that_is_not_current_is_refused(
    page_server: Page, review_page_story: Any, stage: str, kind: str
) -> None:
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


def test_determinism_60_a_page_accept_from_a_non_confirmer_is_refused(
    page_server: Page, review_page_story: Any
) -> None:
    page_server.post("/name", {"name": "Mallory Guest"})
    status, payload = page_server.post("/answer", body(review_page_story.root, "FR-001"))
    assert refusals(payload) == ["not-a-confirmer"]


def test_the_same_persons_later_answer_replaces_the_earlier(
    page_server: Page, review_page_story: Any
) -> None:
    root = review_page_story.root
    page_server.post("/answer", body(root, "FR-001"))
    page_server.post("/answer", body(root, "FR-001", "except", comment="On reflection, no."))
    held = session(root)
    assert held["answers"]["FR-001"]["disposition"] == "except"
    assert "superseded" not in held


def test_a_different_persons_conflicting_answer_is_kept_as_in_003(
    page_server: Page, review_page_story: Any
) -> None:
    root = review_page_story.root
    page_server.post("/answer", body(root, "FR-001"))
    page_server.post("/name", {"name": "Priya QA"})
    page_server.post("/answer", body(root, "FR-001", "except", comment="Not this one."))
    held = session(root)
    assert held["answers"]["FR-001"]["by"] == "Priya QA"
    assert held["superseded"] == [
        {"key": "FR-001", **{k: v for k, v in held["superseded"][0].items() if k != "key"}}
    ]
    assert held["superseded"][0]["by"] == "Ada Dev" and held["superseded"][0]["disposition"] == "accept"
    page_server.post("/name", {"name": "Ada Dev"})
    for key in review_page_story.listed()[1:]:
        page_server.post("/answer", body(root, key))
    assert "FR-001" in reviews.conflicted_keys(Package(root), "functional")


def test_a_malformed_record_is_refused_as_on_the_command_line(
    page_server: Page, review_page_story: Any
) -> None:
    root = review_page_story.root
    recordfile.path(root).write_text('{"version": 1, "stages": {}, "nonsense": true}\n')
    before = files_snapshot(root)
    status, payload = page_server.post("/answer", body_without_lookup("FR-001"))
    code, cli = eil(
        root,
        "review",
        "answer",
        "--stage",
        "functional",
        "--kind",
        "inferred",
        "--entry",
        "FR-001",
        "--by",
        "Ada Dev",
        "--reply",
        "ok",
    )
    assert files_snapshot(root) == before
    assert code == 1
    assert payload["ok"] is False
    assert [(r["code"], r["message"]) for r in payload["refusals"]] == [
        (r["code"], r["message"]) for r in cli["refusals"]
    ]
    status, _, text = page_server.get("/")
    assert status == 200
    assert "disabled" in text and "malformed" in text.lower()
    assert 'class="notice' in text


def body_without_lookup(key: str) -> dict[str, Any]:
    return {
        "stage": "functional",
        "kind": "inferred",
        "entry": key,
        "disposition": "accept",
        "shown": None,
        "question": None,
        "comment": None,
    }


# ---- determinism 57


FIVE = [
    ("accept", None),
    ("accept", None),
    ("accept", None),
    ("except", "Name the pairs."),
    ("question", "Why this order?"),
]


def test_determinism_57_the_page_and_the_command_line_record_the_same(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
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
        argv = [
            "review",
            "answer",
            "--stage",
            "functional",
            "--kind",
            "inferred",
            "--entry",
            key,
            "--disposition",
            disposition,
            "--by",
            "Ada Dev",
        ]
        argv += ["--reply", comment or "ok"]
        code, payload = eil(in_chat, *argv)
        assert code == 0, payload

    def outcome(root: Path) -> Any:
        package = Package(root)
        statuses = {k: i.status for k, i in blockstatus.block_statuses(package)["functional"].items()}
        accs = package.record("functional", "provenance")["acceptances"]
        return (
            statuses,
            sorted(k for a in accs for k in a["except"]),
            sorted(k for a in accs for k in a["questioned"]),
            sorted(k for a in accs for k in a["accepted"]),
        )

    assert outcome(on_page) == outcome(in_chat)

    def scrub(root: Path) -> Any:
        data = json.loads(recordfile.path(root).read_text())
        prov = data["stages"]["functional"]["provenance"]
        for acc in prov["acceptances"]:
            for name in ("via", "questions", "comments", "reply", "id", "at"):
                acc.pop(name, None)
        for block in prov["blocks"].values():
            if "reviewed" in block:
                block["reviewed"] = {
                    k: v for k, v in block["reviewed"].items() if k not in ("reply", "list", "at")
                }
        prov["acceptances"] = sorted(prov["acceptances"], key=lambda a: json.dumps(a, sort_keys=True))
        return data

    assert scrub(on_page) == scrub(in_chat)


# ---- T035: a comment on a settled block (D-65)


def reopen_body(
    root: Path, key: str = "FR-003", comment: str | None = "Phone layout?", stage: str = "functional"
) -> dict[str, Any]:
    from eil.content import blocks_of

    block = next(b for b in blocks_of(Package(root).doc(stage)) if b.key == key)
    return {"stage": stage, "key": key, "shown": block.hash, "comment": comment}


def test_post_reopen_reopens_a_settled_block(page_server: Page, review_page_story: Any) -> None:
    root = review_page_story.root
    status, payload = page_server.post("/reopen", reopen_body(root))
    assert status == 200 and payload["ok"] is True, payload
    mark = Package(root).record("functional", "provenance")["blocks"]["FR-003"]["reopened"]
    assert mark["via"] == "page" and mark["comment"] == "Phone layout?" and mark["by"] == "Ada Dev"
    _, _, html = page_server.get("/")
    assert 'data-entry="FR-003"' in html
    assert "reopened by ada dev: phone layout?" in html.lower()


@pytest.mark.parametrize("comment", [None, "", "  "])
def test_post_reopen_needs_a_comment(page_server: Page, review_page_story: Any, comment: str | None) -> None:
    before = files_snapshot(review_page_story.root)
    status, payload = page_server.post("/reopen", reopen_body(review_page_story.root, comment=comment))
    assert refusals(payload) == ["comment-required"]
    assert files_snapshot(review_page_story.root) == before


def test_post_reopen_shown_an_older_version_is_refused(page_server: Page, review_page_story: Any) -> None:
    root = review_page_story.root
    body_ = reopen_body(root)
    text = review_page_story.story.read("functional")
    review_page_story.story.write(
        "functional",
        text.replace("shows both customers side by side.", "shows both customers, side by side."),
    )
    before = files_snapshot(root)
    status, payload = page_server.post("/reopen", body_)
    assert "entry-changed" in refusals(payload) or "unknown-item" in refusals(payload)
    assert files_snapshot(root) == before


def test_post_reopen_only_on_the_current_reviews_stage(page_server: Page, review_page_story: Any) -> None:
    root = review_page_story.root
    before = files_snapshot(root)
    status, payload = page_server.post("/reopen", reopen_body(root, "REQ-001", stage="requirements"))
    assert refusals(payload) == ["not-current"]
    assert files_snapshot(root) == before


def test_the_comment_button_is_on_settled_blocks_only(page_server: Page, review_page_story: Any) -> None:
    import re

    from eil import blockstatus

    _, _, html = page_server.get("/")
    settled = {
        k
        for k, i in blockstatus.block_statuses(Package(review_page_story.root))["functional"].items()
        if i.status == "settled"
    }
    with_button = {
        pagerender_unescape(m.group(1))
        for m in re.finditer(
            r'<div class="blk settled" data-key="([^"]+)"[^>]*>.*?data-act="comment"', html, re.S
        )
    }
    buttons = len(re.findall(r'data-act="comment"', html))
    assert buttons == len(settled) and with_button <= settled
    for key in review_page_story.listed():
        block = re.search(
            rf'<div class="blk[^"]*" data-key="{re.escape(key)}".*?</div><!--/control-->', html, re.S
        )
        if block:
            assert 'data-act="comment"' not in block.group(0)


def pagerender_unescape(text: str) -> str:
    import html as html_module

    return html_module.unescape(text)


# ---- T059: accept the rest of a section on the page (D-70)


def test_post_section_accepts_the_rest_of_one_section(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import tempfile

    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    built = review_page.build(tmp_path / "specs" / "001-story", entries=12)
    page = start_page(built.root)
    try:
        page.post("/answer", body(built.root, "FR-001"))
        listed = reviews.build_list(Package(built.root), "functional", "inferred", session_view=False)
        shown = {
            entry.key: entry.hash for entry in listed.entries if entry.section == "Functional Requirements"
        }
        status, payload = page.post(
            "/section",
            {
                "stage": "functional",
                "kind": "inferred",
                "section": "Functional Requirements",
                "shown": shown,
            },
        )
        assert payload["ok"] is True, payload
        answers = session(built.root)["answers"]
        assert set(answers) == {"FR-001", "FR-002", "FR-003", "FR-004"}
        assert (
            answers["FR-002"]["via"] == "page" and answers["FR-002"]["together"] == "Functional Requirements"
        )
        assert answers["FR-002"]["seen"] is True and answers["FR-002"]["reply"] == "Accept"
        status, payload = page.post(
            "/section", {"stage": "functional", "kind": "changes", "section": "Validation"}
        )
        assert refusals(payload) == ["not-current"]
    finally:
        page.stop()


def test_post_section_refuses_when_an_entry_changed_since_the_page_loaded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import tempfile

    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    built = review_page.build(tmp_path / "specs" / "001-story", entries=12)
    listed = reviews.build_list(Package(built.root), "functional", "inferred", session_view=False)
    shown = {entry.key: entry.hash for entry in listed.entries if entry.section == "Functional Requirements"}
    text = built.story.read("functional")
    built.story.write("functional", text.replace("handles case 2.", "handles case 2 safely."))
    before = files_snapshot(built.root)
    page = start_page(built.root)
    try:
        status, payload = page.post(
            "/section",
            {
                "stage": "functional",
                "kind": "inferred",
                "section": "Functional Requirements",
                "shown": shown,
            },
        )
        assert status == 200
        assert refusals(payload) == ["entry-changed"]
        assert payload["refusals"][0]["current"]["key"] == "FR-002"
        assert files_snapshot(built.root) == before
    finally:
        page.stop()


def test_the_section_button_only_on_headings_with_unanswered_entries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import re
    import tempfile

    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    built = review_page.build(tmp_path / "specs" / "001-story", entries=12)
    page = start_page(built.root)
    try:
        for key in ("FR-005", "FR-006", "FR-007", "FR-008"):
            page.post("/answer", body(built.root, key))
        _, _, html = page.get("/")
        buttons = re.findall(
            r'<button type="button" data-act="section" data-section="([^"]+)" data-count="(\d+)"[^>]*>Accept the rest of this section</button>',
            html,
        )
        assert buttons == [("Functional Requirements", "4"), ("Validation", "4")]
        from eil import pagerender

        assert (
            '"Accept the " + button.dataset.count + " unanswered blocks under " + button.dataset.section + "?"'
            in pagerender.SCRIPT
        )
        assert "button.dataset.armed" in pagerender.SCRIPT
    finally:
        page.stop()
