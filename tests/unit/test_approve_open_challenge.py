"""``approve`` refuses while a challenge is open, at every approvable stage (task T118; FR-037)."""

from __future__ import annotations

import pytest
from eil.identity import Config
from eil.package import Package
from eil.records import approve
from eil.results import EilExit

from tests.helpers.package import Story, completion_doc, record_block, with_technical

CONFIG = Config(
    default_developer="Ada Dev",
    approvers={s: ["Ada Dev"] for s in ("requirements", "functional", "technical", "completion")},
    abbreviation_authorisers=[],
)


def challenge(status: str = "open") -> str:
    return record_block(
        "challenge",
        {
            "id": "CH-001",
            "stage": "x",
            "raised_by": "ai",
            "target": "REQ-001",
            "text": "A gap?",
            "status": status,
        },
    )


def put(story: Story, stage: str, block: str) -> None:
    story.write(stage, story.read(stage).replace("## Challenges\n", f"## Challenges\n\n{block}", 1))


def refusals(package: Package, stage: str) -> list[dict]:
    with pytest.raises(EilExit) as exc:
        approve(package, CONFIG, stage, "Ada Dev", "Yes.")
    return exc.value.payload["refusals"]


@pytest.mark.parametrize("stage", ["requirements", "functional", "technical", "completion"])
def test_an_open_challenge_refuses_approval_at_every_approvable_stage(story_dir: Story, stage: str) -> None:
    with_technical(story_dir)
    story_dir.write("completion", completion_doc())
    put(story_dir, stage, challenge("open"))
    found = refusals(Package(story_dir.root), stage)
    assert "open-challenge" in [r["code"] for r in found]
    message = next(r["message"] for r in found if r["code"] == "open-challenge")
    assert "CH-001" in message


def test_a_conflicting_challenge_also_refuses(story_dir: Story) -> None:
    with_technical(story_dir)
    put(story_dir, "requirements", challenge("conflict"))
    found = refusals(Package(story_dir.root), "requirements")
    assert "conflict" in next(r["message"] for r in found if r["code"] == "open-challenge")


def test_a_closed_challenge_does_not_refuse(story_dir: Story) -> None:
    with_technical(story_dir)
    put(story_dir, "requirements", challenge("closed"))
    assert "open-challenge" not in [r["code"] for r in refusals(Package(story_dir.root), "requirements")]


def test_an_open_challenge_in_another_stage_does_not_refuse_this_one(story_dir: Story) -> None:
    with_technical(story_dir)
    put(story_dir, "functional", challenge("open"))
    assert "open-challenge" not in [r["code"] for r in refusals(Package(story_dir.root), "requirements")]


def test_the_refusal_cannot_be_overridden_by_naming_it(story_dir: Story) -> None:
    from eil.records import override

    with_technical(story_dir)
    with pytest.raises(EilExit) as exc:
        override(Package(story_dir.root), CONFIG, "requirements", "open-challenge", "Ada Dev", "please")
    assert exc.value.payload["refusals"][0]["code"] == "unknown-criterion"
