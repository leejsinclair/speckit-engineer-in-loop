"""B-26 (T076): completion asks only what implementation touched. FR-033 to FR-035, FR-040, FR-045."""
# ruff: noqa: F811

from __future__ import annotations

import re
import subprocess
from collections.abc import Callable
from typing import Any

import pytest
from eil import reviews

from tests.helpers.derived import edit, package_of
from tests.helpers.package import Story, completion_doc
from tests.scenario.test_b19_b20_scoped_staleness import Driver
from tests.scenario.test_b19_b20_scoped_staleness import eil as driver  # noqa: F401

pytestmark = pytest.mark.scenario
Eil = Callable[..., tuple[int, Any]]


def test_b26_step_1_only_touched_artefacts_are_asked(driver: Driver, reference_story: Story) -> None:
    text = reference_story.read("tasks")
    for task, art in ((1, "ART-001"), (2, "ART-004"), (3, "ART-007")):
        text = re.sub(rf"(T{task:03d} .*?\(traces: AIS-\d{{3}})\)", rf"\1, {art})", text)
    reference_story.write("tasks", text)
    reference_story.write("completion", completion_doc())

    code, listed = driver("review", "list", "--stage", "completion", "--kind", "diagram-currency")
    assert code == 0 and listed["purpose"] == "validation"
    assert sorted(e["key"] for e in listed["entries"]) == ["ART-001", "ART-004", "ART-007"]

    code, status = driver("status")
    currency = status["diagram_currency"]
    assert sorted(currency["touched"]) == ["ART-001", "ART-004", "ART-007"]
    assert currency["untouched"] == ["ART-002", "ART-003", "ART-005", "ART-006", "ART-008"]


def test_b26_step_2_evidence_the_files_confirm_is_not_asked(
    driver: Driver, reference_story: Story, monkeypatch: pytest.MonkeyPatch
) -> None:
    reference_story.write(
        "verification",
        reference_story.read("verification").replace(
            "tests/test_import.py::test_flags_duplicates", "tests/unit/test_dupes.py::test_threshold"
        ),
    )
    edit(reference_story, "functional", "behaviour 1 of duplicate", "behaviour 1 of the duplicate")

    def listed() -> list[str]:
        return [e.key for e in reviews.build_list(package_of(reference_story), "verification", "evidence").entries]

    assert "EVD-003" in listed()
    project = reference_story.root.parent.parent
    (project / "tests" / "unit").mkdir(parents=True)
    (project / "tests" / "unit" / "test_dupes.py").write_text("def test_threshold():\n    assert True\n")

    def fail(*args: object, **kwargs: object) -> None:
        raise AssertionError("a process was started")

    monkeypatch.setattr(subprocess, "run", fail)
    monkeypatch.setattr(subprocess, "Popen", fail)
    assert "EVD-003" not in listed()


def test_b26_step_3_low_challenges_are_deferred_in_one_reply(driver: Driver, reference_story: Story) -> None:
    reference_story.write("completion", completion_doc())
    for n in range(1, 6):
        code, added = driver(
            "challenge", "add", "requirements", "--target", ["REQ-001", "REQ-002", "REQ-003", "REQ-004", "UC-001"][n - 1], "--text", f"Minor point {n}?",
            "--by", "Priya", "--severity", "low",
        )  # fmt: skip
        assert code == 0, added
    code, listed = driver("review", "list", "--stage", "completion", "--kind", "low-challenges")
    assert code == 0 and len(listed["entries"]) == 5 and {e["severity"] for e in listed["entries"]} == {"low"}

    code, refused = driver("review", "answer", "--stage", "completion", "--kind", "low-challenges",
                           "--digest", listed["digest"], "--reply", "defer all", "--by", "Ada Dev", "--all")  # fmt: skip
    assert code == 1 and refused["refusals"][0]["code"] == "reason-required"

    code, done = driver(
        "review", "answer", "--stage", "completion", "--kind", "low-challenges", "--digest", listed["digest"],
        "--reply", "defer all, accepted as minor", "--by", "Ada Dev", "--all", "--defer-reason", "accepted as minor",
    )  # fmt: skip
    assert code == 0, done
    assert len(done["deferred"]) == 5
    challenges = [r for r in package_of(reference_story).doc("requirements").records() if r.kind == "challenge"]
    assert len(challenges) == 5
    assert {(c.obj["status"], c.obj["response"], c.obj["reason"], c.obj["responder"]) for c in challenges} == {
        ("closed", "deferred", "accepted as minor", "Ada Dev")
    }
    code, status = driver("status")
    assert len(status["outstanding"]["deferred_challenges"]) == 5
    assert status["outstanding"]["low_challenges"] == []


def test_b26_step_4_an_accepted_design_difference_is_a_correction_with_origin_completion(driver: Driver) -> None:
    code, opened = driver(
        "correct", "open", "--item", "ART-006", "--found-in", "completion", "--problem", "built as a queue, not a call",
        "--by", "Ada Dev",
    )  # fmt: skip
    assert code == 0, opened
    assert opened["correction"]["found_in"] == {"stage": "completion"}
    code, status = driver("status")
    assert [c["id"] for c in status["corrections"]] == ["CR-001"]
