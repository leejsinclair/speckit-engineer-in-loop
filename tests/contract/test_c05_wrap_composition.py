"""C-05 (risk R-2, task T011) and C-04: a wrap composes into the agent skill, and the helper
installed with the extension runs from ``.specify/extensions/eil/``.

If the guard were not in the composed skill, a story could bypass every gate without anyone
noticing (research D-05, D-08), so this is the test that decides whether enforcement by wrap
is viable.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from tests.helpers import scratch

pytestmark = pytest.mark.contract

STUBS = Path(__file__).parent / "stubs"
SKILL = Path(".claude") / "skills" / "speckit-plan" / "SKILL.md"
GUARD = "If `.specify/extensions/eil/scripts/python/eil` does not exist, STOP"
HELPER_CALL = "python3 .specify/extensions/eil/scripts/python/eil enter plan --json"


@pytest.fixture
def stubbed_project(scratch_project: Path) -> Path:
    scratch.install_extension(scratch_project, STUBS / "eil-stub")
    scratch.install_preset(scratch_project, STUBS / "preset-stub")
    return scratch_project


def test_composed_skill_has_guard_and_helper_call_before_the_core_body(stubbed_project: Path) -> None:
    skill = (stubbed_project / SKILL).read_text(encoding="utf-8")
    core_marker = "## User Input"  # first heading of the core plan body
    assert GUARD in skill
    assert HELPER_CALL in skill
    assert core_marker in skill
    assert skill.index(GUARD) < skill.index(HELPER_CALL) < skill.index(core_marker)


def test_core_body_is_substituted_exactly_once_and_placeholder_is_gone(stubbed_project: Path) -> None:
    skill = (stubbed_project / SKILL).read_text(encoding="utf-8")
    assert "{CORE_TEMPLATE}" not in skill
    assert skill.count("## Pre-Execution Checks") == 1
    assert "setup-plan.sh" in skill  # the core plan workflow is really there


def test_skill_is_attributed_to_the_preset(stubbed_project: Path) -> None:
    skill = (stubbed_project / SKILL).read_text(encoding="utf-8")
    assert "source: preset:eil-preset-stub" in skill


def _body(skill: str) -> list[str]:
    """The skill text after the frontmatter, as whitespace-separated words, minus the title
    heading Spec Kit adds when it regenerates a skill."""
    _, _, body = skill.split("---\n", 2)
    return body.replace("# Speckit Plan Skill", "").split()


def test_removing_the_preset_restores_the_core_skill_in_content(scratch_project: Path) -> None:
    """SC-009 is about behaviour. Spec Kit regenerates the skill on removal, so the file is
    equivalent but not byte-identical (YAML quoting and a title heading differ); this pins
    that the guard and the preset attribution are gone and the core body is back in full."""
    before = (scratch_project / SKILL).read_text(encoding="utf-8")
    scratch.install_extension(scratch_project, STUBS / "eil-stub")
    scratch.install_preset(scratch_project, STUBS / "preset-stub")
    assert (scratch_project / SKILL).read_text(encoding="utf-8") != before
    scratch.specify(scratch_project, "preset", "remove", "eil-preset-stub")
    after = (scratch_project / SKILL).read_text(encoding="utf-8")
    assert GUARD not in after
    assert "preset:" not in after
    assert "source: templates/commands/plan.md" in after
    assert _body(after) == _body(before)


def test_c04_helper_directory_is_installed_and_runs_from_the_installed_location(
    stubbed_project: Path,
) -> None:
    helper = stubbed_project / ".specify" / "extensions" / "eil" / "scripts" / "python" / "eil"
    assert (helper / "__main__.py").is_file()
    proc = subprocess.run(
        [sys.executable, str(helper), "ping", "--json"],
        cwd=stubbed_project,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    assert '"stub": true' in proc.stdout


def test_extension_command_is_registered_as_a_skill(stubbed_project: Path) -> None:
    assert (stubbed_project / ".claude" / "skills" / "speckit-eil-ping" / "SKILL.md").is_file()


def test_install_changes_only_managed_files(scratch_project: Path) -> None:
    """FR-001, as observed: nothing the project's authors wrote is edited.

    The single tracked file that changes is the agent's generated skill for the wrapped
    command; Spec Kit composes it in place and restores it on removal (checked above).
    """
    scratch.install_extension(scratch_project, STUBS / "eil-stub")
    scratch.install_preset(scratch_project, STUBS / "preset-stub")
    tracked_changes = [
        line[3:]
        for line in scratch.git(
            scratch_project, "status", "--porcelain", "--untracked-files=no"
        ).stdout.splitlines()
    ]
    assert tracked_changes == [".claude/skills/speckit-plan/SKILL.md"]
