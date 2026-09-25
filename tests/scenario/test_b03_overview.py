"""B-03 (task T053): the overview stays in step with the records, with no manual edit and no
document prose (FR-054 to FR-056)."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from tests.helpers.package import requirements_doc
from tests.scenario.conftest import write_judgments

pytestmark = pytest.mark.scenario

FEATURE = "specs/001-detect-duplicates"
CANARY = "PROSE-CANARY-not-for-the-overview"
JUDGED = ["REQ-G01", "REQ-G11", "REQ-G12", "REQ-G13"]


def overview(project: Path) -> str:
    return (project / FEATURE / "s00-README.md").read_text(encoding="utf-8")


def started(project: Path, eil: Callable) -> None:
    result = eil(
        ["start", "--title", "Detect duplicates", "--owner", "Ada Dev", "--feature-dir", FEATURE, "--json"]
    )
    assert result.code == 0, result.stderr
    doc = requirements_doc(
        {
            "Background": CANARY,
            "Desired Outcome": f"**REQ-001**: {CANARY}",
            "Open Questions": "**OQ-004**: Keep history? (status: open) (material: yes)",
        }
    )
    (project / FEATURE / "s01-requirements.md").write_text(doc, encoding="utf-8", newline="\n")


def judge(project: Path, eil: Callable):
    path = write_judgments(project, "requirements", JUDGED)
    return eil(["check", "--stage", "requirements", "--judgments", str(path), "--json"])


def test_b03_the_overview_follows_each_action_without_manual_edits(project: Path, eil: Callable) -> None:
    started(project, eil)
    assert "| [s01-requirements.md](s01-requirements.md) | draft |" in overview(project)

    judge(project, eil)
    assert "- Open questions: OQ-004" in overview(project)  # check refreshed it

    eil(
        [
            "override",
            "requirements",
            "--criterion",
            "REQ-G10",
            "--by",
            "Ada Dev",
            "--reason",
            "accepting the risk for now",
            "--json",
        ]
    )
    assert "- Overrides: OVR-001 (requirements REQ-G10 by Ada Dev)" in overview(project)

    judge(project, eil)
    assert "| [s01-requirements.md](s01-requirements.md) | in-review |" in overview(project)

    # An override of one criterion is FR-010's way past a gate: approval now succeeds and records it.
    result = eil(["approve", "requirements", "--by", "Ada Dev", "--attestation", "Yes, I confirm.", "--json"])
    assert result.code == 0, result.stdout
    text = overview(project)
    assert "| [s01-requirements.md](s01-requirements.md) | approved |" in text
    assert "- Overrides: OVR-001 (requirements REQ-G10 by Ada Dev)" in text


def test_b03_approval_appears_in_the_overview(project: Path, eil: Callable) -> None:
    started(project, eil)
    path = project / FEATURE / "s01-requirements.md"
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            "(status: open)", "(status: accepted) (accepted-by: Ada Dev)"
        ),
        encoding="utf-8",
    )
    judge(project, eil)
    assert (
        eil(["approve", "requirements", "--by", "Ada Dev", "--attestation", "Yes, I confirm.", "--json"]).code
        == 0
    )
    text = overview(project)
    assert "| [s01-requirements.md](s01-requirements.md) | approved |" in text
    assert "| requirements | Ada Dev |" in text
    assert "- Current stage: functional" in text
    assert "- OQ-004 (accepted by Ada Dev, requirements)" in text


def test_b03_the_overview_never_contains_document_prose(project: Path, eil: Callable) -> None:
    started(project, eil)
    judge(project, eil)
    assert CANARY not in overview(project)


def test_b03_a_hand_edited_overview_loses_to_the_records_and_the_difference_is_reported(
    project: Path, eil: Callable
) -> None:
    started(project, eil)
    path = project / FEATURE / "s00-README.md"
    path.write_text(path.read_text(encoding="utf-8").replace("| draft |", "| approved |"), encoding="utf-8")
    report = eil(["status", "--json"])
    assert report.code == 0 and report.json["overview"]["current"] is False
    assert report.json["stages"]["requirements"]["state"] == "draft"  # derived, not what the file says
    eil(["sync", "--json"])
    assert "| [s01-requirements.md](s01-requirements.md) | draft |" in overview(project)
    assert eil(["status", "--json"]).json["overview"] == {"current": True}


def test_b03_status_changes_nothing(project: Path, eil: Callable) -> None:
    started(project, eil)
    eil(["sync", "--json"])
    before = {
        p.relative_to(project).as_posix(): p.read_bytes()
        for p in (project / FEATURE).rglob("*")
        if p.is_file()
    }
    eil(["status", "--json"])
    after = {
        p.relative_to(project).as_posix(): p.read_bytes()
        for p in (project / FEATURE).rglob("*")
        if p.is_file()
    }
    assert before == after
