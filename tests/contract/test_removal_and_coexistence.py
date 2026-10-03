"""Installing next to existing work, and removing everything again (task T125; FR-005, FR-006, SC-009).

An ungoverned feature is never touched or gated, and after the preset and the extension are removed
Spec Kit behaves as before: the wrapped command resolves to the core, no hook is left, and every stage
document, alias and mirror the story produced is still an ordinary readable file.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from eil import aliases
from eil.package import Package

from tests.helpers import scratch
from tests.helpers.package import Story, with_plan_and_tasks

pytestmark = pytest.mark.contract

LEGACY = "Legacy spec, written by hand.\n"
SKILL = Path(".claude") / "skills" / "speckit-plan" / "SKILL.md"


def run_helper(project: Path, *args: str, feature: Path | None = None) -> subprocess.CompletedProcess[str]:
    helper = project / ".specify" / "extensions" / "eil" / "scripts" / "python" / "eil"
    extra = ["--feature-dir", str(feature)] if feature else []
    return subprocess.run(
        [sys.executable, str(helper), *args, *extra],
        cwd=project,
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.fixture
def project_with_legacy(scratch_project: Path) -> Path:
    legacy = scratch_project / "specs" / "000-legacy"
    legacy.mkdir(parents=True)
    (legacy / "spec.md").write_text(LEGACY, encoding="utf-8")
    scratch.git(scratch_project, "add", "-A")
    scratch.git(scratch_project, "commit", "-q", "-m", "legacy feature")
    return scratch_project


def test_an_existing_feature_is_untouched_and_never_gated(project_with_legacy: Path) -> None:
    project = project_with_legacy
    scratch.install_extension(project)
    scratch.install_preset(project)
    legacy = project / "specs" / "000-legacy"
    assert (legacy / "spec.md").read_text(encoding="utf-8") == LEGACY
    assert sorted(p.name for p in legacy.iterdir()) == ["spec.md"]
    for command in ("status", "check", "sync", "overview"):
        result = run_helper(project, command, "--json", feature=legacy)
        assert result.returncode == 3 and json.loads(result.stdout) == {"governed": False, "story": "000-legacy"}, command
    assert sorted(p.name for p in legacy.iterdir()) == ["spec.md"], "nothing was created there"
    started = run_helper(project, "start", "--title", "x", "--json", feature=legacy)
    assert started.returncode == 1 and "directory-has-spec-md" in started.stdout, (
        "an ordinary spec.md is never taken over"
    )


def test_removal_leaves_the_story_readable_and_standard_spec_kit_restored(project_with_legacy: Path) -> None:
    project = project_with_legacy
    scratch.install_extension(project)
    scratch.install_preset(project)
    feature = project / "specs" / "001-duplicates"
    story = Story(feature)
    with_plan_and_tasks(story)
    from eil import cli

    cli._persist_adoption(Package(feature))  # writes the story's record file (003 FR-013)
    assert (feature / "eil-record.json").is_file()
    aliases.refresh(Package(feature), aliases.MIRROR)
    scratch.git(project, "add", "-A")
    scratch.git(project, "commit", "-q", "-m", "a governed story")
    before = {p.name: p.read_bytes() for p in feature.iterdir() if p.is_file()}

    scratch.remove_preset(project)
    scratch.remove_extension(project)

    assert {p.name: p.read_bytes() for p in feature.iterdir() if p.is_file()} == before
    assert "eil-record.json" in before, "the record file is left in place, like every document"
    for name in ("spec.md", "plan.md", "tasks.md"):
        assert (feature / name).read_text(encoding="utf-8") == (
            feature
            / {"spec.md": "s04-ai-spec.md", "plan.md": "s05-plan.md", "tasks.md": "s06-tasks.md"}[name]
        ).read_text(encoding="utf-8")
    hooks = project / ".specify" / "extensions.yml"
    assert "speckit.eil" not in (hooks.read_text(encoding="utf-8") if hooks.exists() else "")
    assert not (project / ".specify" / "extensions" / "eil").exists()
    skill = (project / SKILL).read_text(encoding="utf-8")
    assert ".specify/extensions/eil/scripts/python/eil" not in skill and "preset:" not in skill
    assert "source: templates/commands/plan.md" in skill
    generated = (
        ".claude/skills/",
        ".specify/extensions",
        ".specify/presets",
        ".specify/integrations",
        ".specify/feature.json",
    )
    changed = [p for p in scratch.changed_paths(project) if not p.startswith(generated)]
    assert changed == [], f"non-generated files changed: {changed}"
    tracked = scratch.git(project, "diff", "--name-only", "HEAD").stdout.split()
    assert not [p for p in tracked if not p.startswith(generated)], tracked


def test_the_core_commands_resolve_to_the_core_again(project_with_legacy: Path) -> None:
    project = project_with_legacy
    scratch.install_extension(project)
    scratch.install_preset(project)
    assert "eil" in (project / SKILL).read_text(encoding="utf-8")
    scratch.remove_preset(project)
    scratch.remove_extension(project)
    resolved = scratch.run([".specify/scripts/bash/resolve-template.sh", "plan-template", "--json"], project)
    core = (project / ".specify" / "templates" / "plan-template.md").read_text(encoding="utf-8")
    assert json.loads(resolved.stdout)["TEMPLATE_CONTENT"] == core
    skills = sorted(p.parent.name for p in (project / ".claude" / "skills").glob("speckit-eil-*/SKILL.md"))
    assert skills == [], "no extension command is left"
