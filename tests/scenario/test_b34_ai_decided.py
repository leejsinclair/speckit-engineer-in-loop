"""B-34 (US5, FR-026 to FR-029): the developer is asked about behaviour, not mechanism.

A DEC owned by `ai-decided` with no reason is a finding; with one it is accepted, sits on the
technical review list in its own group, is settled by the person's one reply, and is named by the
approval. Turning it into the developer's decision surfaces it once more for review.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest
from eil.gates import JUDGMENT, criteria_for

from tests.conftest import EilResult
from tests.helpers.package import DECISION, Story, approve_stages, with_record_sections, with_technical
from tests.unit.test_ai_decided import AI_DECIDED

pytestmark = pytest.mark.scenario
FEATURE = "specs/001-decided"


def test_b34_ai_decided(project: Path, eil: Callable[..., EilResult], tmp_path: Path) -> None:
    story = Story(project / FEATURE)
    no_reason = AI_DECIDED.replace(
        "Reason: Rendering is the slowest step; this choice changes nothing a user sees.\n", ""
    )
    with_technical(
        story,
        sections={"Technical Decisions": DECISION.replace("Ada Dev", "Test Developer") + "\n\n" + no_reason},
    )
    story.write("technical", with_record_sections(story.read("technical")))
    approve_stages(story, "requirements", "functional", by="Test Developer")

    def run(*argv: str) -> EilResult:
        return eil([*argv, "--feature-dir", FEATURE, "--json"])

    checked = run("check", "--stage", "technical")
    assert "ai-decided-without-reason" in [f["code"] for f in checked.json["findings"]]

    story.write(
        "technical",
        story.read("technical").replace(
            "Owner: ai-decided",
            "Reason: Rendering is the slowest step; nothing a user sees changes.\nOwner: ai-decided",
        ),
    )
    judgments = tmp_path / "j.json"
    ids = [c.id for c in criteria_for("technical") if c.kind == JUDGMENT]
    judgments.write_text(
        json.dumps(
            {"stage": "technical", "judgments": [{"id": i, "status": "met", "reason": "ok"} for i in ids]}
        )
    )
    checked = run("check", "--stage", "technical", "--judgments", str(judgments))
    assert "ai-decided-without-reason" not in [f["code"] for f in checked.json["findings"]]

    listed = run("review", "list", "--stage", "technical", "--kind", "inferred").json
    assert {"section": "AI-decided decisions", "entries": ["DEC-002"]} in listed["groups"]
    answered = run("review", "answer", "--stage", "technical", "--kind", "inferred", "--digest", listed["digest"],
                   "--all", "--by", "Test Developer", "--reply", "ok")  # fmt: skip
    assert answered.code == 0, answered.stdout
    plan = run("comprehension", "plan", "--stage", "technical").json
    for row in plan["levels"]:
        extra = ["--items", row["target"]] if row.get("target") else []
        assert (
            run(
                "comprehension",
                "record",
                "--stage",
                "technical",
                "--level",
                row["level"],
                "--outcome",
                "skipped",
                "--by",
                "Test Developer",
                *extra,
            ).code
            == 0
        )
    run("check", "--stage", "technical", "--judgments", str(judgments))
    approved = run("approve", "technical", "--by", "Test Developer", "--attestation", "ok")
    assert approved.code == 0, approved.stdout
    assert approved.json["approval"]["ai_decided"] == ["DEC-002"]
    assert "AI-decided: DEC-002" in story.read("technical")

    story.write("technical", story.read("technical").replace("Owner: ai-decided", "Owner: Test Developer"))
    again = run("review", "list", "--stage", "technical", "--kind", "inferred").json
    assert [e["key"] for e in again["entries"]] == ["DEC-002"]
