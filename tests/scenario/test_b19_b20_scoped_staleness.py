"""B-19 and B-20 (T023): an upstream edit blocks only what it reaches, and completed tasks and evidence
are revalidated in one reply. Drives the helper as the wrapped commands do. SC-002, SC-003, FR-005, FR-006."""

from __future__ import annotations

import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from eil import cli

from tests.helpers.derived import change_dec3, edit, package_of, revert_dec3, wire_tasks_to_dec3
from tests.helpers.package import Story

pytestmark = pytest.mark.scenario
REPO = Path(__file__).resolve().parents[2]

Eil = Callable[..., tuple[int, Any]]
DEC3_DEPENDANTS = {"AIS-014", "T004", "T005", "T006", "T009", "§Project Structure"}


class Driver:
    def __init__(self, story: Story, eil_json: Eil) -> None:
        self.story, self.eil_json = story, eil_json

    def __call__(self, *args: str) -> tuple[int, Any]:
        return self.eil_json([*args, "--feature-dir", str(self.story.root)], self.story.root)

    def answer(self, stage: str, kind: str, reply: str, *flags: str, digest: str | None = None) -> tuple[int, Any]:
        digest = digest or self("review", "list", "--stage", stage, "--kind", kind)[1]["digest"]
        return self(
            "review", "answer", "--stage", stage, "--kind", kind, "--digest", digest,
            "--reply", reply, "--by", "Ada Dev", *flags,
        )  # fmt: skip


@pytest.fixture
def eil(reference_story: Story, eil_json: Eil) -> Driver:
    wire_tasks_to_dec3(reference_story)
    driver = Driver(reference_story, eil_json)
    config = reference_story.root.parent.parent / ".specify" / "extensions" / "eil" / "eil-config.yml"
    config.parent.mkdir(parents=True)
    config.write_text(
        "default_developer: Ada Dev\napprovers:\n  requirements: [Ada Dev]\n  functional: [Ada Dev]\n"
        "  technical: [Ada Dev]\n  completion: [Ada Dev]\n",
        encoding="utf-8",
    )
    templates = reference_story.root.parent.parent / ".specify" / "templates"
    templates.mkdir(parents=True)
    shutil.copy(REPO / "templates" / "s00-readme-template.md", templates)
    cli._persist_adoption(package_of(reference_story))
    for stage in ("ai-spec", "plan", "tasks", "verification"):
        code, data = driver.answer(stage, "unknown-currency", "ok", "--all")
        assert code == 0, data
    return driver


def blocked(eil: Driver) -> set[str]:
    code, data = eil("status")
    assert code == 0
    return {row["id"] for row in data["blocked_work"]}


def test_b19_an_upstream_edit_blocks_only_what_it_reaches(eil: Driver) -> None:
    assert blocked(eil) == set()
    change_dec3(eil.story)
    assert blocked(eil) == DEC3_DEPENDANTS
    assert eil("enter", "implement", "--task", "T002")[0] == 0
    code, data = eil("enter", "implement", "--task", "T009")
    assert code == 1 and data["refusals"][0]["code"] == "work-blocked"
    assert "DEC-003" in data["refusals"][0]["message"]
    assert "/speckit-eil-accept technical" in data["refusals"][0]["fix"]
    revert_dec3(eil.story)
    assert blocked(eil) == set()
    edit(eil.story, "technical", "Retry failed analyses three times.", "Retry failed analyses three times.   ")
    assert blocked(eil) == set()


def test_b20_completed_tasks_are_revalidated_in_one_reply(eil: Driver) -> None:
    change_dec3(eil.story)
    code, listed = eil("review", "list", "--stage", "tasks", "--kind", "tasks")
    assert code == 0 and sorted(e["key"] for e in listed["entries"]) == ["T004", "T005", "T006"]
    assert all("DEC-003" in e["why"] for e in listed["entries"])
    code, data = eil.answer("tasks", "tasks", "ok, except T005", "--all-except", "T005", digest=listed["digest"])
    assert code == 0, data
    assert [e["key"] for e in eil("review", "list", "--stage", "tasks", "--kind", "tasks")[1]["entries"]] == ["T005"]
    edit(eil.story, "technical", "A changed reason for decision 3.", "Another reason for decision 3.")
    code, data = eil.answer("tasks", "tasks", "ok", "--all", digest=listed["digest"])
    assert code == 1 and data["refusals"][0]["code"] == "list-changed"


def test_b20_evidence_for_an_earlier_version_blocks_completion(eil: Driver) -> None:
    edit(eil.story, "functional", "behaviour 1 of duplicate analysis", "behaviour 1 of duplicate review")
    code, listed = eil("review", "list", "--stage", "verification", "--kind", "evidence")
    assert code == 0 and [e["key"] for e in listed["entries"]] == ["EVD-003"]
