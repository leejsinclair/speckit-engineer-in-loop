"""B-09 and B-11 (task T102): detecting hand edits, and analyze over the whole chain. FR-043, FR-044,
FR-068. The judgment half of B-11 (is the checklist still meaningful?) is a human reading, recorded in
docs/trials.md."""

from __future__ import annotations

import shutil
from collections.abc import Callable
from pathlib import Path

import pytest
from eil.package import Package

from tests.scenario.test_b04_b14_b16_functional import feature, write_ready_functional
from tests.scenario.test_b05_b15_technical import approved_functional, start_technical, write_technical

pytestmark = pytest.mark.scenario


def states(project: Path, eil: Callable) -> dict[str, dict]:
    return eil(["status", "--json"]).json["stages"]


def test_b09_formatting_changes_keep_the_approval_and_a_changed_word_does_not(
    project: Path, eil: Callable
) -> None:
    approved_functional(project, eil)
    path = feature(project) / "s01-requirements.md"
    text = path.read_text(encoding="utf-8")
    path.write_bytes(text.replace("\n", "  \r\n").encode("utf-8"))
    assert states(project, eil)["requirements"]["state"] == "approved"
    path.write_text(text.replace("detects", "spots"), encoding="utf-8")
    after = states(project, eil)
    assert after["requirements"]["state"] == "needs-re-review"
    assert after["requirements"]["affected_items"][0] == "REQ-001"
    assert after["functional"]["state"] == "needs-re-review"
    assert "FR-001" in after["functional"]["affected_items"]


def test_b09_the_affected_items_are_the_ones_that_depend_on_the_change(project: Path, eil: Callable) -> None:
    approved_functional(project, eil)
    path = feature(project) / "s02-functional-spec.md"
    path.write_text(
        path.read_text(encoding="utf-8").replace("within 60 seconds", "within 90 seconds"), encoding="utf-8"
    )
    after = states(project, eil)
    assert after["functional"]["affected_items"] == ["NFR-001"]
    assert after["requirements"]["state"] == "approved"


def test_b09_a_clone_elsewhere_keeps_every_approval(project: Path, eil: Callable, tmp_path: Path) -> None:
    approved_functional(project, eil)
    clone = tmp_path / "clone"
    shutil.copytree(project, clone, symlinks=True)
    package = Package(clone / "specs" / "001-detect-duplicates")
    assert (
        package.state("requirements").state == "approved" and package.state("functional").state == "approved"
    )


def test_b11_the_chain_check_names_the_gaps_analyze_appends(project: Path, eil: Callable) -> None:
    start_technical(project, eil)
    write_technical(project)
    path = feature(project) / "s02-functional-spec.md"
    text = path.read_text(encoding="utf-8")
    path.write_text(
        text.replace("**NFR-001**", "**FR-099**: Something nobody asked for.\n\n**NFR-001**", 1),
        encoding="utf-8",
    )
    result = eil(["check", "--chain", "--json"])
    assert result.code == 0 and result.json["ok"] is False
    gaps = {g["where"]: g for g in result.json["gaps"]}
    assert (
        gaps["FR-099"]["id"].startswith("T-")
        and "traces to no requirement or use case" in gaps["FR-099"]["message"]
    )


def test_b11_a_complete_chain_reports_no_gaps_and_strict_refuses_only_when_there_are_some(
    project: Path, eil: Callable
) -> None:
    write_ready_functional(project, eil)
    clean = eil(["check", "--chain", "--strict", "--json"])
    assert clean.code == 0 and clean.json["gaps"] == []
    path = feature(project) / "s02-functional-spec.md"
    path.write_text(path.read_text(encoding="utf-8").replace("(traces: REQ-001)", "", 1), encoding="utf-8")
    assert eil(["check", "--chain", "--strict", "--json"]).code == 1


def test_b11_trace_reads_the_story_in_both_directions_and_reports_gaps(project: Path, eil: Callable) -> None:
    write_ready_functional(project, eil)
    forward = eil(["trace", "--from", "REQ-001", "--json"])
    assert forward.code == 0 and "FR-001" in [r["id"] for r in forward.json["chain"]]
    assert "no technical decision traces to a functional requirement of REQ-001" in forward.json["gaps"]
    reverse = eil(["trace", "--to", "NFR-001", "--json"])
    assert [r["id"] for r in reverse.json["chain"]] == ["REQ-001"]
    unknown = eil(["trace", "--to", "PR#404", "--json"])
    assert unknown.code == 2
    both = eil(["trace", "--from", "REQ-001", "--to", "FR-001", "--json"])
    assert both.code == 2
    report = eil(["trace", "--report", "--json"])
    assert (
        report.json["requirements"][0]["id"] == "REQ-001"
        and report.json["requirements"][0]["complete"] is False
    )
