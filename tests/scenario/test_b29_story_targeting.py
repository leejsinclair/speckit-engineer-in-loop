"""B-29 (US1, FR-001 to FR-006): every change lands on the intended story.

With the pointer on completed story A and story B in progress, a writing call with no story named is
refused ``ambiguous-story`` and both stories stay byte-identical; a read-only call proceeds and names
A. Starting story C moves the pointer and says so. A start on another story's branch waits for a
person's confirmation, which is recorded with their name.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest

from tests.conftest import EilResult, files_snapshot
from tests.fixtures import two_stories
from tests.scenario.conftest import write_judgments

pytestmark = pytest.mark.scenario


def test_b29_story_targeting(project: Path, eil: Callable[..., EilResult]) -> None:
    stories = two_stories.build(project)
    judgments = write_judgments(project, "functional", ["FUN-G10", "FUN-G12", "FUN-G13"])
    specs = project / "specs"
    before = files_snapshot(specs)

    # A write with no story named: refused, nothing touched (A's approved records included).
    refused = eil(["check", "--stage", "functional", "--judgments", str(judgments), "--json"])
    assert refused.code == 1, refused.stderr
    assert refused.refusal_codes == ["ambiguous-story"]
    message = refused.json["refusals"][0]["message"]
    assert "001-a" in message and "002-b" in message
    assert files_snapshot(specs) == before

    # A read-only call proceeds and names the story it read.
    status = eil(["status", "--json"])
    assert status.code == 0 and status.json["story"] == "001-a"

    # Naming the story lets the write through, and only that story changes.
    a_before = files_snapshot(stories.a.root)
    named = eil(
        [
            "check",
            "--stage",
            "functional",
            "--judgments",
            str(judgments),
            "--feature-dir",
            "specs/002-b",
            "--json",
        ]
    )
    assert named.code == 0, named.stderr
    assert named.json["story"] == "002-b"
    assert files_snapshot(stories.a.root) == a_before

    # Starting a new story moves the pointer and reports the move.
    started = eil(["start", "--feature-dir", "specs/003-c", "--title", "Third story", "--json"])
    assert started.code == 0, started.stderr
    assert started.json["pointer"] == {"previous": "specs/001-a", "current": "specs/003-c"}
    saved = json.loads((project / ".specify" / "feature.json").read_text())
    assert saved["feature_directory"] == "specs/003-c"
    follow = eil(["overview", "--json"])
    assert follow.code == 0 and follow.json["story"] == "003-c"

    # A start on another story's branch waits for a person.
    subprocess.run(["git", "checkout", "-q", "-b", "001-x"], cwd=project, check=True)
    waiting = eil(["start", "--feature-dir", "specs/004-d", "--title", "Fourth story", "--json"])
    assert waiting.code == 1 and waiting.refusal_codes == ["unexpected-branch"]
    assert "001-x" in waiting.json["refusals"][0]["message"]
    assert not (specs / "004-d").exists()
    confirmed = eil(
        ["start", "--feature-dir", "specs/004-d", "--title", "Fourth story", "--on-branch", "001-x",
         "--by", "Test Developer", "--reply", "yes", "--json"]
    )  # fmt: skip
    assert confirmed.code == 0, confirmed.stderr
    record = json.loads((specs / "004-d" / "eil-record.json").read_text())
    assert record["story"]["start"]["branch_confirmed_by"] == "Test Developer"
    assert record["story"]["start"]["reply"] == "yes"
