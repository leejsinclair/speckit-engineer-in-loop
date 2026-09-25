"""Spec Kit's own prerequisite check accepts the aliases (task T086; research D-06).

The core scripts insist on ``spec.md``, ``plan.md`` and ``tasks.md``. This runs the real
``check-prerequisites.sh`` in a governed package whose three aliases exist, first as symlinks and
then as read-only mirrors, and asserts it accepts them and reports the alias paths.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest
from eil import aliases
from eil.package import Package

from tests.helpers.package import Story, with_plan_and_tasks

pytestmark = pytest.mark.contract

SCRIPT = ".specify/scripts/bash/check-prerequisites.sh"


def governed_project(project: Path, mode: str) -> Path:
    feature = project / "specs" / "001-duplicates"
    story = Story(feature)
    with_plan_and_tasks(story)
    aliases.refresh(Package(feature), mode)
    (project / ".specify" / "feature.json").write_text(
        json.dumps({"feature_directory": "specs/001-duplicates"}), encoding="utf-8"
    )
    return feature


@pytest.mark.parametrize("mode", [aliases.SYMLINK, aliases.MIRROR])
def test_check_prerequisites_accepts_and_reports_the_aliases(scratch_project: Path, mode: str) -> None:
    feature = governed_project(scratch_project, mode)
    env = {**os.environ, "SPECIFY_FEATURE_DIRECTORY": str(feature)}
    proc = subprocess.run(
        [SCRIPT, "--json", "--require-tasks", "--include-tasks"],
        cwd=scratch_project,
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    payload = json.loads(proc.stdout)
    assert Path(payload["FEATURE_DIR"]).resolve() == feature.resolve()
    assert (
        (feature / "tasks.md").exists() and (feature / "plan.md").exists() and (feature / "spec.md").exists()
    )
    assert (feature / "tasks.md").read_bytes() == (feature / "s06-tasks.md").read_bytes()
