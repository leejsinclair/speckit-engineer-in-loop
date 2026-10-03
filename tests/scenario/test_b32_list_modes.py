"""B-32 (US3, FR-014 to FR-018): lists are sized to the person.

Five entries are walked one at a time; three are answered, the conversation is "compacted" (a fresh
helper process), the list resumes at the fourth, and "ok to the rest" closes it. Thirty-odd entries
are a grouped summary with every scaffolding section as one entry, answered in one reply.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest

from tests.conftest import EilResult
from tests.helpers.package import Story, functional_doc, requirements_doc, with_record_sections
from tests.unit.test_list_modes import with_inferred

pytestmark = pytest.mark.scenario
FEATURE = "specs/001-lists"


def listing(eil: Callable[..., EilResult], stage: str) -> dict:
    result = eil(["review", "list", "--stage", stage, "--kind", "inferred", "--feature-dir", FEATURE, "--json"])
    assert result.code == 0, result.stderr
    return result.json


def test_b32_list_modes(project: Path, eil: Callable[..., EilResult]) -> None:
    story = Story(project / FEATURE)
    ids = with_inferred(story, 5)
    first = listing(eil, "requirements")
    assert first["mode"] == "one-at-a-time" and [e["key"] for e in first["entries"]] == ids
    for key in ids[:3]:
        answered = eil(["review", "answer", "--stage", "requirements", "--kind", "inferred", "--digest", first["digest"],
                        "--entry", key, "--by", "Test Developer", "--reply", "ok", "--feature-dir", FEATURE, "--json"])  # fmt: skip
        assert answered.code == 0, answered.stdout + answered.stderr
    resumed = listing(eil, "requirements")  # a new process: nothing is held in the conversation
    assert [e["key"] for e in resumed["entries"]] == ids[3:]
    assert resumed["mode"] == "one-at-a-time"
    rest = eil(["review", "answer", "--stage", "requirements", "--kind", "inferred", "--digest", resumed["digest"],
                "--rest", "--by", "Test Developer", "--reply", "ok to the rest", "--feature-dir", FEATURE, "--json"])  # fmt: skip
    assert rest.code == 0 and rest.json["closed"] is True
    assert listing(eil, "requirements")["entries"] == []

    people = "\n\n".join(f"- **Actor {n}**: does thing {n}" for n in range(1, 13))
    story.write("functional", with_record_sections(functional_doc({"Actors": people}), {"version": 1, "blocks": {}}))
    story.write("requirements", requirements_doc())
    big = listing(eil, "functional")
    keys = [e["key"] for e in big["entries"]]
    assert big["mode"] == "summary" and len(keys) > 8
    assert "§Actors" in keys and not any(k.startswith("Actors#") for k in keys)
    assert all(len(e["summary"]) <= 120 for e in big["entries"])
    assert [g["section"] for g in big["groups"]][:2] == ["Requirements Traceability", "Actors"]
    one = eil(["review", "answer", "--stage", "functional", "--kind", "inferred", "--digest", big["digest"], "--all",
               "--by", "Test Developer", "--reply", "ok", "--feature-dir", FEATURE, "--json"])  # fmt: skip
    assert one.code == 0, one.stdout
    record = json.loads((project / FEATURE / "eil-record.json").read_text())
    assert record["stages"]["functional"]["provenance"]["acceptances"][-1]["mode"] == "summary"
