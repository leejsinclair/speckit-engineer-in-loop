"""Two stories in one project (T004; research D-46, D-47, B-29).

* story A (``specs/001-a``): the reference story with its completion approved;
* story B (``specs/002-b``): Requirements approved, Functional in progress;
* ``.specify/feature.json`` still points at A, as it did in the trial.

``build`` can also put the project in a git repository on a named branch (local ``git init`` and
``git checkout -b`` only; nothing touches a network).
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

from tests.fixtures import reference_story
from tests.helpers.package import (
    Story,
    approve_stages,
    completion_doc,
    install_templates,
    with_functional,
    with_record_sections,
)

A_NAME = "001-a"
B_NAME = "002-b"


@dataclass
class TwoStories:
    project: Path
    a: Story
    b: Story

    def point_at(self, story: Story | None) -> None:
        """Set ``.specify/feature.json`` to ``story`` (``None`` removes it)."""
        saved = self.project / ".specify" / "feature.json"
        if story is None:
            saved.unlink(missing_ok=True)
            return
        relative = story.root.relative_to(self.project).as_posix()
        saved.write_text(json.dumps({"feature_directory": relative}) + "\n", encoding="utf-8")


def approve_completion(story: Story, by: str = "Ada Dev") -> None:
    """Write a completion document and its approval as ``records.approve`` shapes it."""
    from eil import verification
    from eil.blocks import write_region
    from eil.fingerprint import fingerprint_text
    from eil.package import Package

    text = completion_doc()
    story.write("completion", text)
    package = Package(story.root)
    record = {
        "stage": "completion",
        "by": by,
        "at": "2026-09-30T00:00:00Z",
        "fingerprint": fingerprint_text(text),
        "reached": "first",
        "attestation": "Yes.",
        "upstream": {s: fp for s in ("requirements", "functional", "technical") if (fp := package.fingerprint(s))},
        "items": {},
        "overrides_used": [],
        "review_findings": verification.finding_hashes(package),
    }
    story.write("completion", write_region(text, "approval", record))


def git(project: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=project, check=True, capture_output=True, text=True)


def on_branch(project: Path, branch: str) -> None:
    """Make ``project`` a git repository (if it is not one) and check out a new ``branch``."""
    if not (project / ".git").exists():
        git(project, "init", "-q")
    git(project, "checkout", "-q", "-B", branch)


def build(project: Path, branch: str | None = None) -> TwoStories:
    """Write both stories into ``project`` (created if absent) and point the project at A."""
    (project / ".specify").mkdir(parents=True, exist_ok=True)
    if not (project / ".specify" / "templates").is_dir():
        install_templates(project)
    a = reference_story.build(project / "specs" / A_NAME)
    approve_completion(a)
    b = Story(project / "specs" / B_NAME, title="Second story")
    with_functional(b)
    b.write("functional", with_record_sections(b.read("functional")))  # drafted from the template
    approve_stages(b, "requirements")
    stories = TwoStories(project, a, b)
    stories.point_at(a)
    if branch is not None:
        on_branch(project, branch)
    return stories
