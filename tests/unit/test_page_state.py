"""004 T046: change notices and the idle stop (research D-66, D-68; determinism 65 and 66).

``GET /state`` returns the current review, the document's fingerprint, each listed entry's hash and
each stored answer, read fresh on every call. The page compares it with what it embedded and shows a
notice; it never changes what it shows. The page stops after a period with no request but ``/state``,
and stopping loses nothing.
"""

from __future__ import annotations

import html
import json
import re
import time
from pathlib import Path
from typing import Any

import pytest
from eil import pagerender, reviews
from eil.package import Package

from tests.helpers.package import Story
from tests.helpers.page import Page, eil, start_page


def embedded(page_html: str) -> Any:
    found = re.search(r'<meta name="eil-state" content="([^"]*)">', page_html)
    assert found
    return json.loads(html.unescape(found.group(1)))


def test_determinism_66_state_has_the_four_parts(page_server: Page, review_page_story: Any) -> None:
    state = page_server.state()
    assert set(state) == {"current", "doc", "entries", "answers"}
    assert state["current"]["stage"] == "functional" and state["current"]["kind"] == "inferred"
    assert state["doc"] == Package(review_page_story.root).fingerprint("functional")
    assert set(state["entries"]) == set(review_page_story.listed())
    assert state["answers"] == {}


def test_determinism_66_the_page_embeds_the_state_it_was_rendered_from(page_server: Page) -> None:
    _, _, text = page_server.get("/")
    assert embedded(text) == page_server.state()


def test_determinism_66_a_block_edit_and_a_cli_answer_show_on_the_next_call(
    page_server: Page, review_page_story: Any
) -> None:
    first = page_server.state()
    text = review_page_story.story.read("functional")
    review_page_story.story.write(
        "functional",
        text.replace("flag duplicate customers on import.", "flag duplicate customers on each import."),
    )
    second = page_server.state()
    assert second["entries"]["FR-001"] != first["entries"]["FR-001"]
    assert second["doc"] != first["doc"]
    code, payload = eil(
        review_page_story.root,
        "review",
        "answer",
        "--stage",
        "functional",
        "--kind",
        "inferred",
        "--entry",
        "FR-002",
        "--by",
        "Ada Dev",
        "--reply",
        "ok",
    )
    assert code == 0, payload
    third = page_server.state()
    assert third["answers"]["FR-002"][0:2] == ["accept", "Ada Dev"], (
        "no cached package: a CLI write between two calls shows"
    )


def test_determinism_66_the_poll_interval_is_at_most_5_seconds() -> None:
    assert 0 < pagerender.POLL_MS <= 5000
    assert f"setTimeout(poll, {pagerender.POLL_MS})" in pagerender.SCRIPT


def test_the_script_never_changes_rendered_content_on_a_notice() -> None:
    poll = pagerender.SCRIPT[
        pagerender.SCRIPT.index("function differences") : pagerender.SCRIPT.index("const diagrams")
    ]
    assert "innerHTML" not in poll and "#doc" not in poll and "showNotice" in poll
    for message in (
        "changed",
        "was answered elsewhere",
        "A new review is current: ",
        "The document changed outside the review blocks",
    ):
        assert message in poll
    assert json.dumps(pagerender.STOPPED) in pagerender.SCRIPT
    assert json.dumps(pagerender.CHANGED) in pagerender.SCRIPT


def test_successful_writes_do_not_hide_unrelated_changes() -> None:
    script = pagerender.SCRIPT
    assert "function adopt(result, keys)" in script
    assert "differences(result.state, new Set(keys))" in script
    assert "adopt(result, [control.dataset.entry])" in script
    assert "adopt(result, Object.keys(shown))" in script
    assert "adopt(result, [block.dataset.key])" in script


def test_state_after_an_answer_on_the_page(page_server: Page, review_page_story: Any) -> None:
    root = review_page_story.root
    entry = next(
        e for e in reviews.build_list(Package(root), "functional", "inferred").entries if e.key == "FR-001"
    )
    status, result = page_server.post(
        "/answer", {"stage": "functional", "kind": "inferred", "entry": "FR-001", "disposition": "accept", "shown": entry.hash, "question": entry.question},
    )  # fmt: skip
    assert result["state"] == page_server.state()
    assert result["state"]["answers"]["FR-001"][:2] == ["accept", "Ada Dev"]


# ---- determinism 65


def wait_until(condition: Any, seconds: float = 5.0) -> bool:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if condition():
            return True
        time.sleep(0.02)
    return condition()


def test_determinism_65_a_page_polled_only_for_state_stops(review_page_story: Any) -> None:
    page = start_page(review_page_story.root, idle_minutes=0.01)  # 0.6 seconds
    try:
        page.get("/state")
        assert wait_until(page.server.stopped.is_set, 5)
        with pytest.raises(OSError):
            for _ in range(20):
                page.get("/state")
                time.sleep(0.05)
    finally:
        page.stop()


def test_determinism_65_a_page_in_use_does_not_stop(review_page_story: Any) -> None:
    page = start_page(review_page_story.root, idle_minutes=0.02)  # 1.2 seconds
    try:
        for _ in range(8):
            assert page.get("/")[0] == 200
            time.sleep(0.25)
        assert not page.server.stopped.is_set()
    finally:
        page.stop()


def test_determinism_65_stopping_loses_no_answer(review_page_story: Any) -> None:
    root = review_page_story.root
    page = start_page(root, idle_minutes=0.01)
    try:
        entry = next(
            e
            for e in reviews.build_list(Package(root), "functional", "inferred").entries
            if e.key == "FR-001"
        )
        page.post(
            "/answer",
            {
                "stage": "functional",
                "kind": "inferred",
                "entry": "FR-001",
                "disposition": "accept",
                "shown": entry.hash,
                "question": entry.question,
            },
        )
        assert wait_until(page.server.stopped.is_set, 5)
    finally:
        page.stop()
    code, listed = eil(root, "review", "list", "--stage", "functional", "--kind", "inferred")
    assert [a["key"] for a in listed["answers"]] == ["FR-001"]
    assert "FR-001" not in [e["key"] for e in listed["entries"]]


def test_state_answers_in_under_200ms_on_a_large_stage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import tempfile

    from tests.fixtures import review_page

    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    built = review_page.build(tmp_path / "specs" / "001-story")
    story: Story = built.story
    padding = "Background narrative line with several ordinary words, but no item.\n" * 1500  # about 100 KB
    story.write(
        "functional",
        story.read("functional").replace(
            "## Not applicable", f"## Background notes\n\n{padding}\n## Not applicable", 1
        ),
    )
    page = start_page(built.root)
    try:
        page.state()
        started = time.perf_counter()
        page.state()
        assert time.perf_counter() - started < 0.2
    finally:
        page.stop()


# ---- T049: the configuration key


def config_with(tmp_path: Path, body: str) -> Any:
    from eil.identity import load_config

    where = tmp_path / ".specify" / "extensions" / "eil"
    where.mkdir(parents=True, exist_ok=True)
    (where / "eil-config.yml").write_text(f"review:\n{body}")
    return load_config(tmp_path)


def test_page_idle_minutes_defaults_to_60_and_is_read(tmp_path: Path) -> None:
    from eil.identity import Config, ConfigError

    assert Config().page_idle_minutes == 60
    assert config_with(tmp_path, "  page_idle_minutes: 5\n").page_idle_minutes == 5
    for bad in ("0", "-3", "soon", "true"):
        with pytest.raises(ConfigError):
            config_with(tmp_path, f"  page_idle_minutes: {bad}\n")
    with pytest.raises(ConfigError):
        config_with(tmp_path, "  page_colour: blue\n")
