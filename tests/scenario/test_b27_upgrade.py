"""B-27 (T082): upgrade of a story in progress. FR-047, FR-008, R-20.

The reference story is built by the 001-era writers, so it has no ``provenance`` or ``changelog`` region.
"""

from __future__ import annotations

import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from tests.helpers.derived import edit
from tests.helpers.package import Story

pytestmark = pytest.mark.scenario
REPO = Path(__file__).resolve().parents[2]
Eil = Callable[..., tuple[int, Any]]
UNCHANGED = ("requirements", "technical")
DERIVED = ("ai-spec", "plan", "tasks", "verification")


class Driver:
    def __init__(self, story: Story, eil_json: Eil) -> None:
        self.story, self.eil_json = story, eil_json

    def __call__(self, *args: str) -> tuple[int, Any]:
        return self.eil_json([*args, "--feature-dir", str(self.story.root)], self.story.root)


@pytest.fixture
def eil(reference_story: Story, eil_json: Eil) -> Driver:
    project = reference_story.root.parent.parent
    config = project / ".specify" / "extensions" / "eil" / "eil-config.yml"
    config.parent.mkdir(parents=True)
    config.write_text(
        "default_developer: Ada Dev\napprovers:\n  requirements: [Ada Dev]\n  functional: [Ada Dev]\n"
        "  technical: [Ada Dev]\n  completion: [Ada Dev]\nabbreviation_authorisers: [Ada Dev]\n",
        encoding="utf-8",
    )
    templates = project / ".specify" / "templates"
    templates.mkdir(parents=True)
    shutil.copy(REPO / "templates" / "s00-readme-template.md", templates)
    return Driver(reference_story, eil_json)


def has_region(story: Story, stage: str) -> bool:
    return "eil:begin provenance" in story.read(stage)


def snapshot(eil: Driver) -> dict[str, Any]:
    code, data = eil("status")
    assert code == 0, data
    return {
        "blocks": {stage: row["blocks"] for stage, row in data["stages"].items() if "blocks" in row},
        "blocked": sorted(row["id"] for row in data["blocked_work"]),
        "states": {stage: row["state"] for stage, row in data["stages"].items()},
    }


def test_b27_steps_1_and_2_sync_changes_nothing_that_was_settled(eil: Driver, reference_story: Story) -> None:
    edit(
        reference_story, "functional", "behaviour 1 of duplicate analysis", "behaviour 1 of duplicate review"
    )
    assert not any(has_region(reference_story, s) for s in (*UNCHANGED, "functional", *DERIVED))
    before = snapshot(eil)
    before_docs = {s: reference_story.read(s) for s in (*UNCHANGED, "functional", *DERIVED)}
    assert not any(has_region(reference_story, s) for s in before_docs), "status must not write"
    assert all(reference_story.read(s) == text for s, text in before_docs.items())

    code, data = eil("sync")
    assert code == 0, data
    assert snapshot(eil) == before

    assert all(has_region(reference_story, s) for s in UNCHANGED)
    code, blocks = eil("blocks", "list", "--stage", "requirements")
    assert code == 0 and {row["status"] for row in blocks["blocks"]} == {"settled"}
    assert {row["class"] for row in blocks["blocks"]} == {"adopted"}

    code, changes = eil("review", "list", "--stage", "functional", "--kind", "changes")
    assert code == 0 and [e["key"] for e in changes["entries"]] == ["FR-001"]

    for stage in DERIVED:
        code, listed = eil("review", "list", "--stage", stage, "--kind", "unknown-currency")
        assert code == 0 and listed["entries"], stage
        assert len({e["key"] for e in listed["entries"]}) == len(listed["entries"])


def test_b27_step_3_nothing_is_unblocked_except_by_the_answer(eil: Driver, reference_story: Story) -> None:
    eil("sync")
    before = snapshot(eil)["blocked"]
    changes_before = eil("review", "list", "--stage", "functional", "--kind", "changes")[1]["entries"]
    for stage in DERIVED:
        code, listed = eil("review", "list", "--stage", stage, "--kind", "unknown-currency")
        assert code == 0
        if not listed["entries"]:
            continue
        code, data = eil(
            "review", "answer", "--stage", stage, "--kind", "unknown-currency", "--digest", listed["digest"],
            "--reply", "ok to all", "--all", "--by", "Ada Dev",
        )  # fmt: skip
        assert code == 0, data
    after = snapshot(eil)["blocked"]
    assert set(after) <= set(before), "an answer must not block anything new"
    assert eil("review", "list", "--stage", "functional", "--kind", "changes")[1]["entries"] == changes_before
    for stage in DERIVED:
        assert not eil("review", "list", "--stage", stage, "--kind", "unknown-currency")[1]["entries"]


def test_b27_step_4_an_abbreviated_stage_is_unchanged_by_the_upgrade(eil: Driver) -> None:
    code, data = eil("abbreviate", "functional", "--by", "Ada Dev", "--reason", "a one-line fix")
    assert code == 0, data
    code, status = eil("status")
    assert status["stages"]["functional"]["abbreviated"] is True
    state = status["stages"]["functional"]["state"]

    assert eil("sync")[0] == 0
    code, status = eil("status")
    assert status["stages"]["functional"]["abbreviated"] is True
    assert status["stages"]["functional"]["state"] == state
    code, blocks = eil("blocks", "list", "--stage", "functional")
    assert code == 0 and blocks["blocks"], "the provenance rule applies to the shorter document"
