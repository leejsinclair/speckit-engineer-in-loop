"""004 T006: which review is current (research D-61; determinism 62; data-model "Current review").

The page shows whatever ``reviews.current_review`` names: the current stage if it is Requirements,
Functional or Technical, on its ``changes`` list once it has an approval and on its ``inferred`` list
before. ``review list --current`` exposes the same answer read-only, and returns ``current: null``
with exit 0 when there is none.
"""

from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any

from eil import cli, reviews
from eil.package import Package

from tests.conftest import files_snapshot
from tests.fixtures import review_page
from tests.helpers.package import Story, requirements_doc, with_approved_chain


def current(root: Path) -> dict[str, Any]:
    return reviews.current_review(Package(root))


def list_current(root: Path) -> tuple[int, Any]:
    out = io.StringIO()
    code = cli.main(["review", "list", "--current", "--json", "--feature-dir", str(root)], cwd=root, stdout=out, stderr=io.StringIO())
    return code, json.loads(out.getvalue())


def test_a_fresh_story_reviews_its_requirements(story_dir: Story) -> None:
    story_dir.write("requirements", requirements_doc())
    found = current(story_dir.root)
    assert (found["stage"], found["kind"], found["document"]) == ("requirements", "inferred", "requirements")


def test_after_requirements_approval_the_functional_draft_is_current(tmp_path: Path) -> None:
    built = review_page.build(tmp_path / "specs" / "001-story")
    found = current(built.root)
    assert (found["stage"], found["kind"]) == ("functional", "inferred")
    assert sorted(e.key for e in found["entries"]) == sorted(built.listed())


def test_an_edited_approved_requirement_makes_its_changes_list_current(tmp_path: Path) -> None:
    built = review_page.build(tmp_path / "specs" / "001-story")
    text = built.story.read("requirements")
    built.story.write("requirements", text.replace("Every dismissal is logged.", "Every dismissal is logged with a reason."))
    found = current(built.root)
    assert (found["stage"], found["kind"]) == ("requirements", "changes")
    assert "REQ-003" in [e.key for e in found["entries"]]


def test_nothing_is_current_once_technical_is_approved(story_dir: Story) -> None:
    with_approved_chain(story_dir)
    assert Package(story_dir.root).current_stage() == "ai-spec"
    found = current(story_dir.root)
    assert found["stage"] is None and found["kind"] is None and found["entries"] == []
    assert found["document"] == "technical", "the latest of the three stages that exists is shown"


def test_review_list_current_returns_the_list(tmp_path: Path) -> None:
    built = review_page.build(tmp_path / "specs" / "001-story")
    code, payload = list_current(built.root)
    assert code == 0
    assert payload["current"] == {"stage": "functional", "kind": "inferred", "document": "functional"}
    assert payload["stage"] == "functional" and payload["kind"] == "inferred"
    assert sorted(e["key"] for e in payload["entries"]) == sorted(built.listed())


def test_review_list_current_with_none_is_null_and_exits_0(story_dir: Story) -> None:
    with_approved_chain(story_dir)
    before = files_snapshot(story_dir.root)
    code, payload = list_current(story_dir.root)
    assert code == 0
    assert payload["current"] is None and payload["entries"] == []
    assert files_snapshot(story_dir.root) == before


def test_current_replaces_stage_and_kind(tmp_path: Path) -> None:
    built = review_page.build(tmp_path / "specs" / "001-story")
    out, err = io.StringIO(), io.StringIO()
    code = cli.main(
        ["review", "list", "--current", "--stage", "requirements", "--kind", "inferred", "--json", "--feature-dir", str(built.root)],
        cwd=built.root, stdout=out, stderr=err,
    )  # fmt: skip
    assert code == 2
