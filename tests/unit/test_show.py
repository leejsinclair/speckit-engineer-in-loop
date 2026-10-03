"""T018: ``eil show``, the clean view of a stage (determinism 45; research D-49; FR-012).

The document with every region replaced by its rendered line, no HTML comment, and the review cue
after the first line of each block that needs review. It reads; it never writes.
"""

from __future__ import annotations

import io
import json
from typing import Any

import pytest
from eil import blockstatus, cli
from eil.package import Package

from tests.conftest import files_snapshot
from tests.helpers.package import Story


def show(story: Story, *argv: str, json_mode: bool = True) -> tuple[int, Any]:
    out = io.StringIO()
    args = ["show", *argv, "--feature-dir", str(story.root)] + (["--json"] if json_mode else [])
    code = cli.main(args, cwd=story.root, env={}, stdout=out, stderr=io.StringIO())
    text = out.getvalue()
    return code, (json.loads(text) if json_mode and text.strip() else text)


def needs_review(story: Story, stage: str) -> dict[str, Any]:
    return {k: i for k, i in blockstatus.block_statuses(Package(story.root))[stage].items() if i.status == "needs-review"}


@pytest.mark.parametrize("migrated", [False, True], ids=["inline", "migrated"])
def test_no_region_body_and_no_comment(legacy_upgrade: Story, migrated: bool) -> None:
    if migrated:
        cli._persist_adoption(Package(legacy_upgrade.root))
    code, payload = show(legacy_upgrade, "functional")
    assert code == 0
    text = payload["text"]
    assert "<!--" not in text
    assert "```json" not in text and "sha256:" not in text and '"fingerprint"' not in text
    assert "Approved by Ada Dev on 2026-09-25" in text
    assert payload["story"] == "001-story" and payload["stage"] == "functional"


def test_the_cue_follows_exactly_the_blocks_that_need_review(legacy_upgrade: Story) -> None:
    pending = needs_review(legacy_upgrade, "plan")
    assert pending
    code, payload = show(legacy_upgrade, "plan")
    lines = payload["text"].split("\n")
    cued = [line for line in lines if "[ai-draft]" in line]
    assert len(cued) == len(pending)
    rows = {row["key"]: row for row in payload["blocks"]}
    assert {k for k, r in rows.items() if r["status"] == "needs-review"} == set(pending)
    settled = [i for i in blockstatus.block_statuses(Package(legacy_upgrade.root))["plan"].values() if i.status != "needs-review"]
    for info in settled:
        first = info.block.text.split("\n")[0].strip()
        assert not any(line.startswith(first) and "[ai-draft]" in line for line in lines if first), info.key


def test_blocks_carry_key_status_and_document_lines(legacy_upgrade: Story) -> None:
    code, payload = show(legacy_upgrade, "functional")
    document = legacy_upgrade.read("functional").split("\n")
    fr = next(r for r in payload["blocks"] if r["key"] == "FR-001")
    assert set(fr) == {"key", "status", "first_line", "last_line"}
    assert document[fr["first_line"] - 1].startswith("**FR-001**")


def test_items_shows_only_those_items_under_their_headings(legacy_upgrade: Story) -> None:
    code, payload = show(legacy_upgrade, "functional", "--items", "FR-002,NFR-001")
    text = payload["text"]
    assert "**FR-002**" in text and "**NFR-001**" in text
    assert "**FR-001**" not in text and "**FR-003**" not in text
    assert "## Functional Requirements" in text and "## Non-Functional Requirements" in text
    assert [r["key"] for r in payload["blocks"]] == ["FR-002", "NFR-001"]


def test_an_item_from_an_upstream_stage_is_found_there(legacy_upgrade: Story) -> None:
    code, payload = show(legacy_upgrade, "functional", "--items", "REQ-001")
    assert code == 0 and "**REQ-001**" in payload["text"]


def test_section_shows_one_section(legacy_upgrade: Story) -> None:
    code, payload = show(legacy_upgrade, "functional", "--section", "Business Rules")
    assert code == 0
    assert payload["text"].startswith("## Business Rules")
    assert "tax id or email" in payload["text"] and "## Inputs" not in payload["text"]


def test_an_unknown_item_is_refused(legacy_upgrade: Story) -> None:
    code, payload = show(legacy_upgrade, "functional", "--items", "FR-999")
    assert code == 1 and [r["code"] for r in payload["refusals"]] == ["unknown-item"]


def test_an_unknown_section_is_refused(legacy_upgrade: Story) -> None:
    code, payload = show(legacy_upgrade, "functional", "--section", "Nowhere")
    assert code == 1 and [r["code"] for r in payload["refusals"]] == ["unknown-item"]


def test_show_writes_nothing(legacy_upgrade: Story) -> None:
    before = files_snapshot(legacy_upgrade.root)
    show(legacy_upgrade, "functional")
    show(legacy_upgrade, "technical", "--items", "DEC-001")
    show(legacy_upgrade, "plan", json_mode=False)
    assert files_snapshot(legacy_upgrade.root) == before


def test_the_text_form_is_the_view(legacy_upgrade: Story) -> None:
    code, text = show(legacy_upgrade, "plan", json_mode=False)
    assert code == 0 and text.startswith("Story 001-story: # Implementation Plan")

