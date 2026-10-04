"""T017: the record file ``eil-record.json`` (determinism 42 to 44; research D-48; FR-007 to FR-011).

Every JSON record moves out of the stage documents into one file per story; each region keeps one
rendered line. Fingerprints are untouched, so no approval moves. A missing or malformed file makes
the approvals it held unverifiable, never valid.
"""

from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any

import pytest
from eil import cli, recordfile
from eil.blocks import Doc
from eil.package import RECORD_NAMES, Package

from tests.conftest import files_snapshot
from tests.helpers.package import Story


def run(story: Story, *argv: str) -> tuple[int, Any]:
    out = io.StringIO()
    code = cli.main(
        [*argv, "--json", "--feature-dir", str(story.root)],
        cwd=story.root,
        env={},
        stdout=out,
        stderr=io.StringIO(),
    )
    return code, json.loads(out.getvalue()) if out.getvalue().strip() else None


def json_regions(story: Story) -> dict[str, list[str]]:
    """``{stage: [region names whose body is JSON]}``."""
    package = Package(story.root)
    found: dict[str, list[str]] = {}
    for stage in package.existing_stages():
        doc = Doc(story.read(stage))
        names = [n for n in RECORD_NAMES if doc.read_region(n).obj is not None or doc.read_region(n).error]
        if names:
            found[stage] = names
    return found


def inline_story(root: Path) -> Story:
    """The reference story exactly as 002 left it: every record inline (no record file)."""
    from tests.fixtures import reference_story
    from tests.helpers.package import install_templates

    install_templates(root.parents[1])
    return reference_story.build(root)


# ---- the file itself


def test_the_layout_is_sorted_two_space_json_with_a_final_newline() -> None:
    data = {
        "version": 1,
        "story": {"start": {"branch": "main", "at": "t"}},
        "stages": {"plan": {}, "functional": {"assessment": {"b": 1, "a": 2}}},
    }
    text = recordfile.dumps(data)
    assert text.endswith("}\n")
    assert json.loads(text) == {
        "stages": {"functional": {"assessment": {"a": 2, "b": 1}}},
        "story": {"start": {"at": "t", "branch": "main"}},
        "version": 1,
    }
    assert text == json.dumps(json.loads(text), indent=2, sort_keys=True) + "\n"
    assert '"plan"' not in text, "a stage with no records has no key"


@pytest.mark.parametrize(
    ("data", "problem"),
    [
        ({"version": 1, "extra": 1}, "unknown key 'extra'"),
        ({"version": 2}, "version must be 1"),
        ({"version": 1, "story": {"mood": "x"}}, "story has unknown key 'mood'"),
        ({"version": 1, "stages": {"sprint": {}}}, "unknown stage 'sprint'"),
        ({"version": 1, "stages": {"functional": {"notes": {}}}}, "unknown record 'notes'"),
        ({"version": 1, "stages": {"functional": {"provenance": {"version": 1, "bogus": 1}}}}, "bogus"),
        ({"version": 1, "stages": {"functional": {"approval": {"by": "Ada"}}}}, "no fingerprint"),
    ],
)
def test_only_the_allowed_keys_pass(data: dict[str, Any], problem: str) -> None:
    assert any(problem in p for p in recordfile.problems(data)), recordfile.problems(data)


def test_a_conforming_file_has_no_problems() -> None:
    assert recordfile.problems(recordfile.empty()) == []


def test_a_malformed_file_is_reported_and_never_written_over(story_dir: Story) -> None:
    from tests.helpers.package import with_functional

    with_functional(story_dir)
    (story_dir.root / "eil-record.json").write_text("{not json")
    code, status = run(story_dir, "status")
    assert code == 0
    assert "malformed-record-file" in [i["code"] for i in status["issues"]]
    code, payload = run(story_dir, "check", "--stage", "functional")
    assert (story_dir.root / "eil-record.json").read_text() == "{not json"


# ---- migration (determinism 42)


def test_sync_moves_every_record_out_of_the_documents_and_keeps_every_fingerprint(tmp_path: Path) -> None:
    story = inline_story(tmp_path / "specs" / "001-story")
    from tests.fixtures.legacy_upgrade import _record_judgments

    _record_judgments(story, "functional")
    package = Package(story.root)
    before = {s: package.fingerprint(s) for s in package.existing_stages()}
    states = {s: package.state(s).state for s in package.existing_stages()}
    records = {(s, n): package.record(s, n) for s in package.existing_stages() for n in RECORD_NAMES}
    assert json_regions(story), "the fixture starts with inline records"

    code, _ = run(story, "sync")
    assert code == 0
    assert json_regions(story) == {}
    after = Package(story.root)
    assert {s: after.fingerprint(s) for s in after.existing_stages()} == before
    assert {s: after.state(s).state for s in after.existing_stages()} == states
    for (stage, name), obj in records.items():
        if obj and name != "provenance":  # provenance is adopted on this first write
            assert after.record(stage, name) == obj, (stage, name)
    saved = json.loads((story.root / "eil-record.json").read_text())
    assert set(saved["stages"]["functional"]) >= {"approval", "assessment"}


def test_each_region_keeps_one_readable_line(tmp_path: Path) -> None:
    story = inline_story(tmp_path / "specs" / "001-story")
    run(story, "sync")
    text = story.read("functional")
    doc = Doc(text)
    approval = doc.region_lines("approval")
    assert len(approval) == 1 and approval[0].startswith("Approved by Ada Dev on 2026-09-25 (first approval)")
    for name in ("approval", "provenance"):
        lines = doc.region_lines(name)
        assert lines and not any("sha256:" in line or line.startswith("```") for line in lines), (name, lines)


def test_migration_is_idempotent(tmp_path: Path) -> None:
    story = inline_story(tmp_path / "specs" / "001-story")
    run(story, "sync")
    once = files_snapshot(story.root)
    run(story, "sync")
    assert files_snapshot(story.root) == once


# ---- half-migrated (determinism 43)


def test_status_reads_both_forms_and_writes_nothing(tmp_path: Path) -> None:
    story = inline_story(tmp_path / "specs" / "001-story")
    package = Package(story.root)
    approval = package.record("functional", "approval")
    package.write_record("functional", "approval", approval)  # functional migrates; the rest stays inline
    assert "functional" not in json_regions(story) and "requirements" in json_regions(story)
    before = files_snapshot(story.root)
    code, status = run(story, "status")
    assert code == 0
    assert status["stages"]["requirements"]["state"] == "approved"
    assert status["stages"]["functional"]["state"] == "approved"
    assert files_snapshot(story.root) == before


def test_the_next_write_on_a_stage_completes_its_migration(tmp_path: Path) -> None:
    story = inline_story(tmp_path / "specs" / "001-story")
    from tests.fixtures.legacy_upgrade import _record_judgments

    _record_judgments(story, "technical")  # an assessment, written through the seam
    assert "technical" not in json_regions(story)
    assert Package(story.root).state("technical").state == "approved"


# ---- integrity (determinism 44)


def test_deleting_the_file_makes_every_approval_unverifiable(tmp_path: Path) -> None:
    story = inline_story(tmp_path / "specs" / "001-story")
    run(story, "sync")
    (story.root / "eil-record.json").unlink()
    package = Package(story.root)
    for stage in ("requirements", "functional", "technical"):
        state = package.state(stage)
        assert state.state == "needs-re-review", stage
        assert state.reason == "approval record missing or unreadable"
        assert "approval-record-missing" in [f.code for f in state.findings]
    code, status = run(story, "status")
    assert "approval-record-missing" in [i["code"] for i in status["issues"]]


def test_a_malformed_file_makes_every_approval_unverifiable(tmp_path: Path) -> None:
    story = inline_story(tmp_path / "specs" / "001-story")
    run(story, "sync")
    (story.root / "eil-record.json").write_text('{"version": 1, "stages": {"functional": {"approval": 3}}}')
    package = Package(story.root)
    assert package.state("functional").state == "needs-re-review"
    assert package.state("functional").reason == "approval record missing or unreadable"
    assert "malformed-record-file" in [f.code for f in package.state("functional").findings]


def test_removing_one_approval_from_the_file_unverifies_only_that_stage(tmp_path: Path) -> None:
    story = inline_story(tmp_path / "specs" / "001-story")
    run(story, "sync")
    path = story.root / "eil-record.json"
    data = json.loads(path.read_text())
    del data["stages"]["technical"]["approval"]
    path.write_text(json.dumps(data))
    package = Package(story.root)
    assert package.state("technical").state == "needs-re-review"
    assert package.state("functional").state == "approved"
