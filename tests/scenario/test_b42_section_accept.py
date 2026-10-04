"""B-42 (004 quickstart; US5): determinism 59 on the page, on a 12-entry list in three sections."""

from __future__ import annotations

from pathlib import Path

import pytest
from eil import reviews
from eil.package import Package

from tests.fixtures import review_page
from tests.helpers.page import start_page

pytestmark = pytest.mark.scenario


def test_b42_accept_the_rest_of_a_section_on_the_page(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import tempfile

    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    built = review_page.build(tmp_path / "specs" / "001-story", entries=12)
    root = built.root
    page = start_page(root)
    try:
        for key, disposition, comment in (("FR-001", "accept", None), ("FR-002", "except", "Not quite.")):
            entry = next(
                e for e in reviews.build_list(Package(root), "functional", "inferred").entries if e.key == key
            )
            page.post(
                "/answer",
                {
                    "stage": "functional",
                    "kind": "inferred",
                    "entry": key,
                    "disposition": disposition,
                    "shown": entry.hash,
                    "question": entry.question,
                    "comment": comment,
                },
            )
        listed = reviews.build_list(Package(root), "functional", "inferred")
        shown = {
            entry.key: entry.hash for entry in listed.entries if entry.section == "Functional Requirements"
        }
        status, payload = page.post(
            "/section",
            {"stage": "functional", "kind": "inferred", "section": "Functional Requirements", "shown": shown},
        )
        assert payload["ok"] is True
    finally:
        page.stop()
    (held,) = Package(root).story_record()["review_sessions"].values()
    answers = held["answers"]
    assert set(answers) == {"FR-001", "FR-002", "FR-003", "FR-004"}
    assert answers["FR-002"]["disposition"] == "except" and "together" not in answers["FR-002"]
    for key in ("FR-003", "FR-004"):
        assert answers[key]["together"] == "Functional Requirements" and answers[key]["seen"] is True
