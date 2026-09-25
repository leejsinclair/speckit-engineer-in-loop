"""Every wrap begins with the identical guard, contains ``{CORE_TEMPLATE}`` once, and the composed
skills carry the guard after install (task T099; C-05 against the real preset, research D-05, D-08).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.helpers import scratch

pytestmark = pytest.mark.contract

REPO = scratch.REPO_ROOT
WRAPS = ["clarify", "plan", "tasks", "analyze", "checklist", "implement"]
GUARD = (
    "If `.specify/extensions/eil/scripts/python/eil` does not exist, STOP. Tell the user to run "
    "`specify extension add eil` and then `specify preset add engineer-in-the-loop`, and do nothing else: "
    "continuing without the helper would let a story bypass its gates."
)


def wrap_path(name: str) -> Path:
    return REPO / "commands" / f"speckit.{name}.md"


def present() -> list[str]:
    return [n for n in WRAPS if wrap_path(n).is_file()]


@pytest.mark.parametrize("name", WRAPS)
def test_a_wrap_carries_the_guard_and_the_core_body_exactly_once(name: str) -> None:
    if not wrap_path(name).is_file():
        pytest.skip(f"speckit.{name}.md arrives with its task")
    text = wrap_path(name).read_text(encoding="utf-8")
    assert "strategy: wrap" in text.split("---")[1]
    assert text.count("{CORE_TEMPLATE}") == 1
    assert text.count(GUARD) == 1
    assert text.index(GUARD) < text.index("{CORE_TEMPLATE}")


@pytest.mark.parametrize("name", WRAPS)
def test_the_guard_comes_before_the_first_helper_call(name: str) -> None:
    if not wrap_path(name).is_file():
        pytest.skip(f"speckit.{name}.md arrives with its task")
    text = wrap_path(name).read_text(encoding="utf-8")
    first_call = text.index("eil enter")
    assert text.index(GUARD) < first_call


def test_the_composed_skills_contain_the_guard_before_the_core_body(scratch_project: Path) -> None:
    scratch.install_extension(scratch_project)
    scratch.install_preset(scratch_project)
    for name in present():
        skill = (scratch_project / ".claude" / "skills" / f"speckit-{name}" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        assert "source: preset:engineer-in-the-loop" in skill, name
        assert "{CORE_TEMPLATE}" not in skill, name
        guard = "If `.specify/extensions/eil/scripts/python/eil` does not exist, STOP"
        core = "## Pre-Execution Checks" if "## Pre-Execution Checks" in skill else "## Outline"
        assert guard in skill and skill.index(guard) < skill.index(core), name
        assert f"eil enter {name}" in skill, name
