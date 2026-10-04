"""B-40 (004 quickstart; US3, SC-002): the page is safe to leave open.

Every attack of determinism 54 and 55 is refused, a stale answer is refused (56), and a page started
without ``--host`` listens on loopback only. The record file is byte-identical after all of them.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from eil import reviews
from eil.package import Package

from tests.conftest import files_snapshot
from tests.fixtures import review_page
from tests.helpers.page import same_origin, start_page

pytestmark = pytest.mark.scenario


def test_b40_attacks_are_refused_and_nothing_changes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import tempfile

    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    built = review_page.build(tmp_path / "specs" / "001-story")
    root = built.root
    entry = next(e for e in reviews.build_list(Package(root), "functional", "inferred").entries if e.key == "FR-001")
    answer = {"stage": "functional", "kind": "inferred", "entry": "FR-001", "disposition": "accept", "shown": entry.hash, "question": entry.question}
    page = start_page(root)
    try:
        assert page.server.server_address[0] == "127.0.0.1"
        port = page.origin.rsplit(":", 1)[1]
        before = files_snapshot(root)
        good = same_origin(page.origin, page.token)
        forged = [
            {k: v for k, v in good.items() if k != "X-EIL-Token"},
            {**good, "X-EIL-Token": "guess"},
            {**good, "Origin": "http://evil.example"},
            {k: v for k, v in good.items() if k != "Origin"},
            {**good, "Host": f"attacker.example:{port}"},
            {**good, "Content-Type": "text/plain"},
        ]
        for headers in forged:
            assert page.call("POST", "/answer", answer, headers)[0] == 403
        for path in ("/doc/../../etc/passwd", "/doc/notastage", "/eil-record.json", "/static/x.js"):
            assert page.get(path)[0] in (403, 404)
        text = built.story.read("functional")
        built.story.write("functional", text.replace("flag duplicate customers on import.", "flag duplicate customers on each import."))
        stale_before = files_snapshot(root)
        status, payload = page.post("/answer", answer)
        assert [r["code"] for r in payload["refusals"]] == ["entry-changed"]
        assert files_snapshot(root) == stale_before
        assert {k: v for k, v in before.items() if k != "s02-functional-spec.md"} == {
            k: v for k, v in files_snapshot(root).items() if k != "s02-functional-spec.md"
        }
        assert not (root / "eil-record.json.lock").exists()
    finally:
        page.stop()
