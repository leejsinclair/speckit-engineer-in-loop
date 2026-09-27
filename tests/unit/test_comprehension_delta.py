"""Delta comprehension on re-approval (D-27): the check asks only about what changed, capped at
two levels, and is skipped entirely when every change is a recorded human decision."""

from __future__ import annotations

import json
from pathlib import Path

from eil import comprehension
from eil.gates import check_stage
from eil.package import Package

from tests.helpers.package import Story, approve_stages, record_block, with_functional

JUDGED = ["FUN-G10", "FUN-G12", "FUN-G13"]


def judgments(tmp: Path) -> Path:
    path = tmp / "j.json"
    path.write_text(
        json.dumps(
            {"stage": "functional", "judgments": [{"id": i, "status": "met", "reason": "ok"} for i in JUDGED]}
        )
    )
    return path


CHALLENGE_ACCEPTED = {
    "id": "CH-004",
    "stage": "requirements",
    "raised_by": "ai",
    "raised_at": "2026-09-26T10:00:00Z",
    "target": "REQ-001",
    "text": "Should the wording be more specific?",
    "status": "closed",
    "responder": "Ada Dev",
    "response": "accepted",
    "at": "2026-09-26T10:05:00Z",
}


def edit(story: Story, stage: str, old: str, new: str) -> None:
    text = story.read(stage)
    assert old in text, old
    story.write(stage, text.replace(old, new, 1))


def approved(story_dir: Story, tmp_path: Path) -> Package:
    with_functional(story_dir)
    package = Package(story_dir.root)
    check_stage(package, "functional", judgments_path=judgments(tmp_path))
    approve_stages(story_dir, "requirements", "functional")
    return Package(story_dir.root)


def test_a_first_approval_is_not_a_delta_check(story_dir: Story, tmp_path: Path) -> None:
    with_functional(story_dir)
    package = Package(story_dir.root)
    check_stage(package, "functional", judgments_path=judgments(tmp_path))
    plan = comprehension.plan(Package(story_dir.root), "functional")
    assert "delta" not in plan
    assert {row["level"] for row in plan["levels"]} == set(comprehension.LEVELS)


def test_a_re_approval_restricts_the_pool_to_what_changed(story_dir: Story, tmp_path: Path) -> None:
    package = approved(story_dir, tmp_path)
    edit(
        story_dir,
        "requirements",
        "**REQ-001**: The system detects duplicate customers on import.",
        "**REQ-001**: The system detects duplicate customers on import, in real time.",
    )
    package = Package(story_dir.root)
    assert package.state("functional").state == "needs-re-review"

    plan = comprehension.plan(package, "functional")

    assert "delta" in plan and plan["delta"]["human_decided"] is False
    assert "FR-001" in plan["delta"]["changed"]
    asked = [row for row in plan["levels"] if row["status"] == "ok"]
    assert 0 < len(asked) <= comprehension.DELTA_LEVEL_CAP
    for row in asked:
        assert row["target"] in plan["delta"]["changed"]
    skipped = [row for row in plan["levels"] if row["status"] == "no-material" and "reason" in row]
    assert skipped and all("delta check" in row["reason"] or "changed" in row["reason"] for row in skipped)


def test_when_every_change_is_a_recorded_human_decision_nothing_is_asked(story_dir: Story, tmp_path) -> None:
    package = approved(story_dir, tmp_path)
    edit(
        story_dir,
        "requirements",
        "**REQ-001**: The system detects duplicate customers on import.",
        "**REQ-001**: The system detects duplicate customers on import, in real time. (decided: CH-004)",
    )
    story_dir.append("requirements", "\n" + record_block("challenge", CHALLENGE_ACCEPTED).rstrip("\n") + "\n")
    package = Package(story_dir.root)
    assert package.state("functional").state == "needs-re-review"

    plan = comprehension.plan(package, "functional")

    assert plan["delta"]["human_decided"] is True
    assert "CH-004" in plan["delta"]["reason"]
    assert all(row["status"] == "no-material" for row in plan["levels"])
    assert {row["level"] for row in plan["levels"]} == set(comprehension.LEVELS)


def test_recording_every_no_material_level_completes_the_check(story_dir: Story, tmp_path: Path) -> None:
    package = approved(story_dir, tmp_path)
    edit(
        story_dir,
        "requirements",
        "**REQ-001**: The system detects duplicate customers on import.",
        "**REQ-001**: The system detects duplicate customers on import, in real time. (decided: CH-004)",
    )
    story_dir.append("requirements", "\n" + record_block("challenge", CHALLENGE_ACCEPTED).rstrip("\n") + "\n")
    package = Package(story_dir.root)
    plan = comprehension.plan(package, "functional")
    from eil.identity import Config

    config = Config(default_developer="Ada Dev", approvers={"functional": ["Ada Dev"]})
    for row in plan["levels"]:
        result = comprehension.record(
            package,
            config,
            "functional",
            row["level"],
            "not-applicable",
            by="Ada Dev",
            reason=row["reason"],
        )
    assert result["state"] == "complete"


def test_an_unrelated_prose_change_leaves_the_pool_empty(story_dir: Story, tmp_path: Path) -> None:
    package = approved(story_dir, tmp_path)
    edit(story_dir, "requirements", "Imports create duplicate customers.", "Imports create many duplicates.")
    package = Package(story_dir.root)
    # Prose outside any item is not a change to any REQ/FR item's hash, so nothing is affected and
    # there is nothing for the delta check to ask about.
    plan = comprehension.plan(package, "functional")
    assert plan["delta"]["changed"] == []
    assert plan["delta"]["human_decided"] is True
