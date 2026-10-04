"""B-35 (US6, FR-030 to FR-034): the comprehension check respects what the developer already knows.

Ada's own settled decision is not asked of Ada: where nothing else is eligible the level is planned and
recorded `own-decision`. One waiver records every remaining level as skipped with her reason. The
approval and the overview show both.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest
from eil.gates import JUDGMENT, criteria_for

from tests.conftest import EilResult
from tests.helpers.package import DECISION, Story, approve_stages, with_record_sections, with_technical

pytestmark = pytest.mark.scenario
FEATURE = "specs/001-own"
ME = "Test Developer"


def test_b35_comprehension(project: Path, eil: Callable[..., EilResult], tmp_path: Path) -> None:
    story = Story(project / FEATURE)
    with_technical(story, sections={"Technical Decisions": DECISION.replace("Ada Dev", ME)})
    story.write("technical", with_record_sections(story.read("technical")))
    approve_stages(story, "requirements", "functional", by=ME)

    def run(*argv: str) -> EilResult:
        return eil([*argv, "--feature-dir", FEATURE, "--json"])

    keys = [b["key"] for b in run("blocks", "list", "--stage", "technical").json["blocks"]]
    classes = tmp_path / "c.json"
    classes.write_text(
        json.dumps({"stage": "technical", "blocks": [{"block": k, "adds": None} for k in keys]})
    )
    assert run("blocks", "classify", "--stage", "technical", "--file", str(classes)).code == 0
    judgments = tmp_path / "j.json"
    ids = [c.id for c in criteria_for("technical") if c.kind == JUDGMENT]
    judgments.write_text(
        json.dumps(
            {"stage": "technical", "judgments": [{"id": i, "status": "met", "reason": "ok"} for i in ids]}
        )
    )
    assert run("check", "--stage", "technical", "--judgments", str(judgments)).code == 0
    listed = run("review", "list", "--stage", "technical", "--kind", "inferred").json
    if listed["entries"]:
        assert (
            run(
                "review",
                "answer",
                "--stage",
                "technical",
                "--kind",
                "inferred",
                "--digest",
                listed["digest"],
                "--all",
                "--by",
                ME,
                "--reply",
                "ok",
            ).code
            == 0
        )

    rows = {
        r["level"]: r for r in run("comprehension", "plan", "--stage", "technical", "--by", ME).json["levels"]
    }
    assert all(r.get("target") != "DEC-001" for r in rows.values())
    assert rows["explain"]["status"] == "own-decision" and rows["explain"]["items"] == ["DEC-001"]
    recognise = rows["recognise"]["target"]
    assert (
        run(
            "comprehension",
            "record",
            "--stage",
            "technical",
            "--level",
            "recognise",
            "--outcome",
            "understood",
            "--by",
            ME,
            "--items",
            recognise,
        ).code
        == 0
    )
    assert (
        run(
            "comprehension",
            "record",
            "--stage",
            "technical",
            "--level",
            "explain",
            "--outcome",
            "own-decision",
            "--by",
            ME,
            "--items",
            "DEC-001",
        ).code
        == 0
    )
    waived = run(
        "comprehension",
        "waive",
        "--stage",
        "technical",
        "--by",
        ME,
        "--reason",
        "I made these decisions this morning",
    )
    assert waived.code == 0, waived.stdout
    assert waived.json["state"] == "complete"

    run("check", "--stage", "technical", "--judgments", str(judgments))
    approved = run("approve", "technical", "--by", ME, "--attestation", "ok")
    assert approved.code == 0, approved.stdout
    counts = approved.json["approval"]["comprehension"]
    assert counts["own_decision"] == 1 and counts["skipped"] == 3 and counts["understood"] == 1
    overview = (project / FEATURE / "s00-README.md").read_text()
    assert "own-decision 1" in overview and "skipped 3" in overview
