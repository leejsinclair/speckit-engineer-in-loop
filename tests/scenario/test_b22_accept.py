"""B-22 (T046): a small edit to approved work is brought back with one short confirmation. Drives the
helper as ``/speckit-eil-accept`` does. SC-004, FR-015 to FR-020."""

from __future__ import annotations

import json
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from tests.helpers.derived import edit, package_of
from tests.helpers.package import Story, record_block
from tests.unit.test_accept_changes import CHALLENGE, NEW_REQ, REQ1, REQ4, prepared

pytestmark = pytest.mark.scenario
REPO = Path(__file__).resolve().parents[2]
Eil = Callable[..., tuple[int, Any]]
CONFIRM = ("review", "confirm", "--stage", "requirements", "--by", "Ada Dev", "--confirmation")


def summaries(root: Path, *keys: str) -> tuple[str, str]:
    path = root / "summaries.json"
    rows = [{"key": k, "summary": f"Summary of the change to {k}."} for k in keys]
    path.write_text(json.dumps({"stage": "requirements", "summaries": rows}), encoding="utf-8")
    return "--summaries", str(path)


@pytest.fixture
def eil(reference_story: Story, eil_json: Eil) -> Eil:
    project = reference_story.root.parent.parent
    config = project / ".specify" / "extensions" / "eil" / "eil-config.yml"
    config.parent.mkdir(parents=True)
    config.write_text(
        "default_developer: Ada Dev\napprovers:\n  requirements: [Ada Dev]\n  functional: [Ada Dev]\n"
        "  technical: [Ada Dev]\n  completion: [Ada Dev]\n",
        encoding="utf-8",
    )
    (project / ".specify" / "templates").mkdir(parents=True)
    shutil.copy(REPO / "templates" / "s00-readme-template.md", project / ".specify" / "templates")
    prepared(reference_story)

    def run(*args: str) -> tuple[int, Any]:
        return eil_json([*args, "--feature-dir", str(reference_story.root)], reference_story.root)

    return run


def test_a_recorded_decision_is_carried_forward_with_one_ok(reference_story: Story, eil: Eil) -> None:
    reference_story.append("requirements", "\n" + record_block("challenge", CHALLENGE).rstrip("\n") + "\n")
    edit(reference_story, "requirements", REQ1, REQ1.replace("import.", "import, in real time.") + " (decided: CH-004)")
    code, listed = eil("review", "list", "--stage", "requirements", "--kind", "changes")
    assert code == 0 and [e["key"] for e in listed["entries"]] == ["REQ-001"]
    assert listed["entries"][0]["covered_by"] == "CH-004"
    code, done = eil(*CONFIRM, "ok", *summaries(reference_story.root.parent, "REQ-001"))
    assert code == 0, done
    assert done["approval"]["reached"] == "carried-forward" and done["approval"]["rests_on"] == ["CH-004"]
    assert package_of(reference_story).state("requirements").state == "approved"
    code, status = eil("status")
    approval = status["stages"]["requirements"]["approval"]
    assert code == 0 and approval["reached"] == "carried-forward" and approval["rests_on"] == ["CH-004"]
    assert "carried forward, resting on CH-004" in reference_story.path("overview").read_text(encoding="utf-8")


def test_an_uncovered_addition_is_answered_once_then_confirmed(reference_story: Story, eil: Eil) -> None:
    edit(reference_story, "requirements", REQ4, REQ4 + "\n\n" + NEW_REQ)
    code, refusal = eil(*CONFIRM, "ok")
    assert code != 0 and "changes-unanswered" in str(refusal)
    code, listed = eil("review", "list", "--stage", "requirements", "--kind", "changes")
    assert [e["key"] for e in listed["entries"]] == ["REQ-005"]
    code, data = eil(
        "review", "answer", "--stage", "requirements", "--kind", "changes", "--digest", listed["digest"],
        "--reply", "ok", "--by", "Ada Dev", "--all",
    )  # fmt: skip
    assert code == 0, data
    code, done = eil(*CONFIRM, "Yes, I reviewed the addition.", *summaries(reference_story.root.parent, "REQ-005"))
    assert code == 0, done
    assert done["approval"]["reached"] == "reviewed" and data["id"] in done["approval"]["rests_on"]
    assert package_of(reference_story).state("requirements").state == "approved"


def test_the_ai_cannot_confirm(reference_story: Story, eil: Eil) -> None:
    edit(reference_story, "requirements", REQ4, REQ4 + "\n\n" + NEW_REQ)
    code, refusal = eil("review", "confirm", "--stage", "requirements", "--by", "claude", "--confirmation", "ok")
    assert code != 0 and "ai-approval" in str(refusal)
