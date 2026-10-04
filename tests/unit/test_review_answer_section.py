"""004 T058: accept the rest of one section (research D-70; determinism 59; FR-011).

``review answer --rest --section NAME`` accepts only that section's unanswered entries, each recorded
``together`` with its section and ``seen: true`` (the page showed every one in full). ``--rest`` alone
keeps 003's meaning, ``seen: false``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from eil.package import Package

from tests.fixtures import review_page
from tests.helpers.page import eil

A = [f"FR-{n:03d}" for n in range(1, 5)]
B = [f"FR-{n:03d}" for n in range(5, 9)]


@pytest.fixture
def twelve(tmp_path: Path) -> Any:
    return review_page.build(tmp_path / "specs" / "001-story", entries=12)


def answer(root: Path, *argv: str) -> Any:
    code, payload = eil(
        root, "review", "answer", "--stage", "functional", "--kind", "inferred", "--by", "Ada Dev", *argv
    )
    assert code == 0, payload
    return payload


def session(root: Path) -> dict[str, Any]:
    (held,) = Package(root).story_record()["review_sessions"].values()
    return held


def test_determinism_59_the_rest_of_one_section(twelve: Any) -> None:
    root = twelve.root
    answer(root, "--entry", A[0], "--reply", "ok")
    answer(root, "--entry", A[1], "--reply", "not this", "--disposition", "except")
    earlier = {k: dict(v) for k, v in session(root)["answers"].items()}
    answer(
        root, "--rest", "--section", "Functional Requirements", "--reply", "ok to the rest of this section"
    )
    answers = session(root)["answers"]
    assert set(answers) == set(A), "B and C have no answers"
    for key in A[2:]:
        assert (
            answers[key]["disposition"] == "accept" and answers[key]["together"] == "Functional Requirements"
        )
        assert answers[key]["seen"] is True
    assert {k: answers[k] for k in A[:2]} == earlier, "the two earlier answers are unchanged"


def test_rest_without_a_section_keeps_seen_false(twelve: Any) -> None:
    answer(twelve.root, "--entry", A[0], "--reply", "ok")
    payload = answer(twelve.root, "--rest", "--reply", "ok to the rest")
    assert payload["closed"] is True
    accs = Package(twelve.root).record("functional", "provenance")["acceptances"]
    rest = next(a for a in accs if a["reply"] == "ok to the rest")
    assert sorted(rest["unseen"]) == sorted(
        k for k in A + B + [f"FR-{n:03d}" for n in range(9, 13)] if k != A[0]
    )
    assert "together" not in rest


def test_the_closing_acceptance_carries_together(twelve: Any) -> None:
    root = twelve.root
    answer(root, "--rest", "--section", "Functional Requirements", "--reply", "ok")
    answer(root, "--rest", "--section", "Business Rules", "--reply", "ok")
    payload = answer(root, "--rest", "--section", "Validation", "--reply", "ok")
    assert payload["closed"] is True
    accs = Package(root).record("functional", "provenance")["acceptances"]
    together = {k: v for a in accs for k, v in (a.get("together") or {}).items()}
    assert together == {**dict.fromkeys(A, "Functional Requirements"), **dict.fromkeys(B, "Business Rules"),
                        **dict.fromkeys([f"FR-{n:03d}" for n in range(9, 13)], "Validation")}  # fmt: skip
    assert all("unseen" not in a for a in accs)


def test_section_needs_rest_and_a_section_with_unanswered_entries(twelve: Any) -> None:
    code, _ = eil(
        twelve.root,
        "review",
        "answer",
        "--stage",
        "functional",
        "--kind",
        "inferred",
        "--by",
        "Ada Dev",
        "--reply",
        "ok",
        "--entry",
        "FR-001",
        "--section",
        "Validation",
    )
    assert code == 2
    code, payload = eil(
        twelve.root,
        "review",
        "answer",
        "--stage",
        "functional",
        "--kind",
        "inferred",
        "--by",
        "Ada Dev",
        "--reply",
        "ok",
        "--rest",
        "--section",
        "Nowhere",
    )
    assert code == 1 and [r["code"] for r in payload["refusals"]] == ["unknown-entry"]
