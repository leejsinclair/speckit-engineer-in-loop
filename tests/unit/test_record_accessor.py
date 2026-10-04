"""T006: the single seam for record reads and writes (``Package.record`` / ``Package.write_record``).

Every JSON record (``approval``, ``assessment``, ``comprehension``, ``provenance``) is read and written
through the package, never by reaching into a region directly, so where the records live can change
without touching a caller.
"""

from __future__ import annotations

from typing import Any

import pytest
from eil import blockstatus
from eil.blocks import Doc, write_provenance, write_region
from eil.package import Package

from tests.helpers.package import Story

NAMES = ("approval", "assessment", "comprehension", "provenance")

COMPREHENSION = {
    "stage": "functional",
    "fingerprint": "sha256:" + "0" * 64,
    "taken_by": "Ada Dev",
    "levels": [{"level": "recognise", "outcome": "understood", "attempts": 1, "items": ["FR-001"]}],
}


@pytest.fixture
def recorded(legacy_upgrade: Story) -> Story:
    """The legacy story with all four Functional records held inline (as 002 wrote them), no record file."""
    package = Package(legacy_upgrade.root)
    held = {name: package.record("functional", name) for name in NAMES}
    held["provenance"] = blockstatus.adopt(package, "functional")
    held["comprehension"] = COMPREHENSION
    (legacy_upgrade.root / "eil-record.json").unlink()
    text = legacy_upgrade.read("functional")
    for name in NAMES:
        text = (
            write_provenance(text, held[name])
            if name == "provenance"
            else write_region(text, name, held[name])
        )
    legacy_upgrade.write("functional", text)
    return legacy_upgrade


def _region_obj(story: Story, stage: str, name: str) -> Any:
    return Doc(story.read(stage)).read_region(name).obj


@pytest.mark.parametrize("name", NAMES)
def test_record_reads_what_the_region_holds(recorded: Story, name: str) -> None:
    expected = _region_obj(recorded, "functional", name)
    assert expected, f"the fixture has no {name} record"
    assert Package(recorded.root).record("functional", name) == expected


def test_record_absent_is_none(story_dir: Story) -> None:
    from tests.helpers.package import with_functional

    with_functional(story_dir)
    package = Package(story_dir.root)
    assert package.record("functional", "approval") is None
    assert package.record("functional", "provenance") is None


def test_write_then_read_round_trips(recorded: Story) -> None:
    package = Package(recorded.root)
    record = dict(package.record("functional", "assessment") or {})
    record["evaluated_at"] = "2026-10-02T00:00:00Z"
    package.write_record("functional", "assessment", record)
    assert Package(recorded.root).record("functional", "assessment") == record


def test_write_creates_a_missing_region(story_dir: Story) -> None:
    from tests.helpers.package import with_functional

    with_functional(story_dir)
    text = story_dir.read("functional")
    story_dir.write(
        "functional", text.replace("<!-- eil:begin approval -->\n<!-- eil:end approval -->\n", "")
    )
    package = Package(story_dir.root)
    package.write_record("functional", "approval", {"stage": "functional", "fingerprint": "sha256:x"})
    assert Package(story_dir.root).record("functional", "approval") == {
        "stage": "functional",
        "fingerprint": "sha256:x",
    }
    assert "## Approval" in story_dir.read("functional")


def test_record_read_reports_a_malformed_provenance(story_dir: Story) -> None:
    from tests.helpers.package import with_functional, with_record_sections

    with_functional(story_dir)
    story_dir.write(
        "functional", with_record_sections(story_dir.read("functional"), {"version": 1, "bogus": 1})
    )
    read = Package(story_dir.root).record_read("functional", "provenance")
    assert read.obj is None and read.error and "bogus" in read.error


def test_unchanged_write_keeps_every_record_and_fingerprint(recorded: Story) -> None:
    """With the record file (D-48) a write migrates the stage, so the document changes, but no record
    and no fingerprint does."""
    package = Package(recorded.root)
    before = {s: package.fingerprint(s) for s in package.existing_stages()}
    for stage in package.existing_stages():
        for name in NAMES:
            obj = Package(recorded.root).record(stage, name)
            if obj:
                Package(recorded.root).write_record(stage, name, obj)
                assert Package(recorded.root).record(stage, name) == obj
    after = Package(recorded.root)
    assert {s: after.fingerprint(s) for s in after.existing_stages()} == before
