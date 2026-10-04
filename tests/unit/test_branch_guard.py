"""T009: starting a story moves the pointer, and an unexpected branch waits for a person
(determinism 39 and 41; research D-47).

The helper reads the current branch with a read-only ``git symbolic-ref``; it never creates or
switches a branch.
"""

from __future__ import annotations

import io
import json
import subprocess
from pathlib import Path
from typing import Any

import pytest
from eil import cli, target
from eil.package import Package

from tests.fixtures.two_stories import TwoStories, on_branch
from tests.helpers.package import install_templates


def run(project: Path, *argv: str) -> tuple[int, Any]:
    out = io.StringIO()
    code = cli.main([*argv, "--json"], cwd=project, env={}, stdout=out, stderr=io.StringIO())
    return code, json.loads(out.getvalue()) if out.getvalue().strip() else None


def codes(payload: Any) -> list[str]:
    return [r["code"] for r in (payload or {}).get("refusals", [])]


def pointer(project: Path) -> str:
    return json.loads((project / ".specify" / "feature.json").read_text())["feature_directory"]


@pytest.fixture
def project(tmp_path: Path) -> Path:
    root = tmp_path / "project"
    install_templates(root)
    return root


def git(project: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=project, check=True, capture_output=True, text=True).stdout


# ---- the pointer (determinism 39)


def test_start_moves_the_pointer_and_reports_the_move(two_stories: TwoStories) -> None:
    code, payload = run(two_stories.project, "start", "--feature-dir", "specs/003-c", "--title", "Third")
    assert code == 0, payload
    assert pointer(two_stories.project) == "specs/003-c"
    assert payload["pointer"] == {"previous": "specs/001-a", "current": "specs/003-c"}
    assert payload["story"] == "003-c"
    assert "001-a" in payload["text"] and "003-c" in payload["text"]


def test_start_with_no_pointer_reports_none_before(project: Path) -> None:
    code, payload = run(project, "start", "--feature-dir", "specs/001-a", "--title", "First")
    assert code == 0, payload
    assert payload["pointer"] == {"previous": None, "current": "specs/001-a"}


# ---- the branch rule (D-47)


@pytest.mark.parametrize(
    ("branch", "expected"),
    [
        ("main", True),
        ("master", True),
        ("002-b", True),
        ("002-other", True),
        ("001-x", False),
        ("feature/x", False),
        ("trunk", False),
    ],
)
def test_the_branch_rule(branch: str, expected: bool) -> None:
    assert target.branch_expected(branch, "002-b", ["main", "master"]) is expected


def test_a_configured_main_branch_counts() -> None:
    assert target.branch_expected("trunk", "002-b", ["trunk"]) is True
    assert target.branch_expected("main", "002-b", ["trunk"]) is False


def test_a_story_without_a_number_prefix_matches_only_its_own_name() -> None:
    assert target.branch_expected("notes", "notes", ["main"]) is True
    assert target.branch_expected("notes-2", "notes", ["main"]) is False


@pytest.mark.parametrize("branch", ["main", "master", "002-b", "002-other"])
def test_start_proceeds_on_an_expected_branch(project: Path, branch: str) -> None:
    on_branch(project, branch)
    code, payload = run(project, "start", "--feature-dir", "specs/002-b", "--title", "B")
    assert code == 0, payload
    assert payload["branch"] == branch


def test_start_on_another_storys_branch_is_refused_and_writes_nothing(project: Path) -> None:
    on_branch(project, "001-x")
    code, payload = run(project, "start", "--feature-dir", "specs/002-b", "--title", "B")
    assert code == 1 and codes(payload) == ["unexpected-branch"]
    refusal = payload["refusals"][0]
    assert "001-x" in refusal["message"] and "--on-branch" in refusal["fix"]
    assert refusal["question"] == "Write story 002-b on branch 001-x?"
    assert not (project / "specs" / "002-b").exists()
    assert not (project / ".specify" / "feature.json").exists()


def test_a_configured_trunk_is_a_main_branch(project: Path) -> None:
    config = project / ".specify" / "extensions" / "eil"
    config.mkdir(parents=True)
    (config / "eil-config.yml").write_text("main_branches: [trunk]\n")
    on_branch(project, "trunk")
    code, payload = run(project, "start", "--feature-dir", "specs/002-b", "--title", "B")
    assert code == 0, payload


def test_a_persons_confirmation_lets_the_start_through_and_is_recorded(project: Path) -> None:
    on_branch(project, "001-x")
    code, payload = run(
        project, "start", "--feature-dir", "specs/002-b", "--title", "B",
        "--on-branch", "001-x", "--by", "Ada", "--reply", "yes",
    )  # fmt: skip
    assert code == 0, payload
    start = Package(project / "specs" / "002-b").story_record()["start"]
    assert start["branch"] == "001-x"
    assert start["branch_confirmed_by"] == "Ada"
    assert start["reply"] == "yes"
    assert start["question"] == "Write story 002-b on branch 001-x?"


def test_a_confirmation_for_another_branch_does_not_count(project: Path) -> None:
    on_branch(project, "001-x")
    code, payload = run(
        project,
        "start",
        "--feature-dir",
        "specs/002-b",
        "--title",
        "B",
        "--on-branch",
        "001-y",
        "--by",
        "Ada",
    )
    assert code == 1 and codes(payload) == ["unexpected-branch"]


def test_the_ai_cannot_confirm_the_branch(project: Path) -> None:
    on_branch(project, "001-x")
    code, payload = run(
        project,
        "start",
        "--feature-dir",
        "specs/002-b",
        "--title",
        "B",
        "--on-branch",
        "001-x",
        "--by",
        "Claude",
    )
    assert code == 1 and "ai-approval" in codes(payload)


def test_outside_a_repository_the_start_proceeds_with_no_branch(project: Path) -> None:
    code, payload = run(project, "start", "--feature-dir", "specs/002-b", "--title", "B")
    assert code == 0, payload
    assert payload["branch"] is None and "no git branch" in payload["note"]


def test_a_detached_head_proceeds_with_no_branch(project: Path) -> None:
    git(project, "init", "-q")
    git(
        project,
        "-c",
        "user.name=T",
        "-c",
        "user.email=t@example.test",
        "commit",
        "-q",
        "--allow-empty",
        "-m",
        "x",
    )
    git(project, "checkout", "-q", "--detach")
    code, payload = run(project, "start", "--feature-dir", "specs/002-b", "--title", "B")
    assert code == 0, payload
    assert payload["branch"] is None and "no git branch" in payload["note"]


def test_the_helper_never_switches_branch(project: Path) -> None:
    on_branch(project, "001-x")
    run(
        project,
        "start",
        "--feature-dir",
        "specs/002-b",
        "--title",
        "B",
        "--on-branch",
        "001-x",
        "--by",
        "Ada",
    )
    assert git(project, "symbolic-ref", "--short", "HEAD").strip() == "001-x"
