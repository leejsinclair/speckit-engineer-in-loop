"""The reference story fixture is the shape the 002 scenarios rely on (T002, T003)."""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from typing import Any

from eil.package import Package
from eil.trace import parse_document

from tests.helpers.package import Story


def kinds(package: Package) -> Counter[str]:
    return Counter(
        i.kind for stage in package.existing_stages() for i in parse_document(package.doc(stage)).items
    )


def test_counts_and_states(reference_story: Story) -> None:
    package = Package(reference_story.root)
    count = kinds(package)
    assert (count["REQ"], count["UC"], count["FR"], count["DEC"], count["ART"]) == (4, 3, 12, 5, 8)
    assert count["AIS"] == 19 and count["EVD"] == 9
    assert [package.state(s).state for s in ("requirements", "functional", "technical")] == ["approved"] * 3
    tasks = parse_document(package.doc("tasks")).tasks
    assert [t.id for t in tasks] == [f"T{n:03d}" for n in range(1, 13)]
    assert [t.done for t in tasks] == [True] * 6 + [False] * 6
    assert all(t.code for t in tasks[:6])


def test_eil_json_reports_the_status(
    reference_story: Story, eil_json: Callable[..., tuple[int, Any]]
) -> None:
    code, data = eil_json(["status", "--feature-dir", str(reference_story.root)], reference_story.root)
    assert code == 0 and data["governed"] is True
