"""C-01, C-02 and C-04 against the real preset and extension (task T034).

The counts follow the manifests, so this file does not change as commands are added. Two tests that
need the finished command set (19 commands, 4 hooks) switch themselves on once the manifest lists
them (task T129).
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from tests.helpers import scratch

pytestmark = pytest.mark.contract

REPO = scratch.REPO_ROOT
EXTENSION_MANIFEST = (REPO / "extensions" / "eil" / "extension.yml").read_text(encoding="utf-8")
PRESET_MANIFEST = (REPO / "preset.yml").read_text(encoding="utf-8")

EXTENSION_COMMANDS = re.findall(r"name:\s*(speckit\.eil\.[a-z0-9-]+)", EXTENSION_MANIFEST)
EXTENSION_ALIASES = re.findall(r'"(speckit\.eil-[a-z0-9-]+)"', EXTENSION_MANIFEST)
PRESET_TEMPLATES = re.findall(r"type:\s*template,\s*name:\s*([a-z0-9-]+)", PRESET_MANIFEST)
PRESET_COMMANDS = re.findall(r"type:\s*command,\s*name:\s*(speckit\.[a-z]+)", PRESET_MANIFEST)


@pytest.fixture
def installed(scratch_project: Path) -> Path:
    scratch.install_extension(scratch_project)
    scratch.install_preset(scratch_project)
    return scratch_project


def test_manifests_declare_what_this_phase_builds() -> None:
    assert "speckit.eil.requirements" in EXTENSION_COMMANDS
    assert "s01-requirements-template" in PRESET_TEMPLATES and "s00-readme-template" in PRESET_TEMPLATES
    assert "speckit.specify" in PRESET_COMMANDS


def test_c01_extension_commands_are_registered_as_skills(installed: Path) -> None:
    skills = {p.parent.name for p in (installed / ".claude" / "skills").glob("speckit-eil-*/SKILL.md")}
    assert skills == {name.replace(".", "-") for name in EXTENSION_COMMANDS + EXTENSION_ALIASES}


def test_the_numbered_names_cover_the_stages_in_order() -> None:
    """Every stage has a numbered name that matches its document number, and only those."""
    assert sorted(EXTENSION_ALIASES + [c for c in EXTENSION_COMMANDS if re.search(r"\.\d-", c)]) == [
        "speckit.eil-0-status",
        "speckit.eil-1-requirements",
        "speckit.eil-2-functional",
        "speckit.eil-3-technical",
        "speckit.eil-4-ai-spec",
        "speckit.eil-7-verify",
        "speckit.eil-8-complete",
        "speckit.eil.5-plan",
        "speckit.eil.6-tasks",
    ]


def test_each_alias_targets_a_command_that_exists() -> None:
    """An alias sits on the command it is named for (1-requirements on ...requirements)."""
    for command, alias in re.findall(
        r'name:\s*(speckit\.eil\.[a-z0-9-]+),\s*aliases:\s*\["(speckit\.eil-[a-z0-9-]+)"\]',
        EXTENSION_MANIFEST,
    ):
        assert alias.removeprefix("speckit.eil-").split("-", 1)[1] == command.split(".")[2], (command, alias)
        assert (REPO / "extensions" / "eil" / "commands" / f"{command}.md").is_file()


def test_c01_the_preset_replaces_specify_with_a_composed_skill(installed: Path) -> None:
    skill = (installed / ".claude" / "skills" / "speckit-specify" / "SKILL.md").read_text(encoding="utf-8")
    assert "source: preset:engineer-in-the-loop" in skill
    assert ".specify/extensions/eil/scripts/python/eil" in skill  # the guard


def test_c01_install_changes_nothing_the_project_authored(scratch_project: Path) -> None:
    """FR-001: only additions under .specify/ and the agent's command directory, plus the agent's
    generated skills recomposed in place for commands the preset wraps or replaces (research F-14)."""
    scratch.install_extension(scratch_project)
    scratch.install_preset(scratch_project)
    changed = scratch.git(
        scratch_project, "status", "--porcelain", "--untracked-files=no"
    ).stdout.splitlines()
    for line in changed:
        assert re.fullmatch(r" M \.claude/skills/speckit-[a-z-]+/SKILL\.md", line), line
    for path in scratch.changed_paths(scratch_project):
        assert path.startswith((".specify/", ".claude/")), path


def test_c01_the_installed_extension_carries_no_tests_or_specs(installed: Path) -> None:
    root = installed / ".specify" / "extensions" / "eil"
    assert root.is_dir()
    for excluded in ("specs", "tests", "docs", ".github"):
        assert not (root / excluded).exists(), excluded
    assert not list(root.rglob("__pycache__"))


def test_c01_the_extension_ignore_file_keeps_caches_out_of_a_direct_dev_install(
    scratch_project: Path, tmp_path: Path
) -> None:
    """`specify extension add --dev extensions/eil` reads .extensionignore from that directory."""
    source = tmp_path / "eil"
    shutil.copytree(
        scratch.REPO_ROOT / "extensions" / "eil", source, ignore=shutil.ignore_patterns("__pycache__")
    )
    cache = source / "scripts" / "python" / "eil" / "__pycache__"
    cache.mkdir()
    (cache / "junk.pyc").write_bytes(b"x")
    scratch.install_extension(scratch_project, source)
    installed = scratch_project / ".specify" / "extensions" / "eil"
    assert not list(installed.rglob("__pycache__"))
    assert not (installed / ".extensionignore").exists()


def test_c01_the_preset_carries_only_its_shipped_files(installed: Path) -> None:
    """Research F-16: a preset install copies its whole source directory, so it is staged first."""
    root = installed / ".specify" / "presets" / "engineer-in-the-loop"
    top = {p.name for p in root.iterdir()}
    assert top <= {"preset.yml", "LICENSE", "README.md", "templates", "commands", ".composed"}, top
    assert {"preset.yml", "templates", "commands"} <= top


def test_c02_every_preset_template_resolves_to_the_presets_file(installed: Path) -> None:
    assert PRESET_TEMPLATES
    for name in PRESET_TEMPLATES:
        proc = scratch.run([".specify/scripts/bash/resolve-template.sh", name, "--json"], installed)
        content = json.loads(proc.stdout)["TEMPLATE_CONTENT"]
        source = (REPO / "templates" / f"{name}.md").read_text(encoding="utf-8")
        assert content == source, name


def test_c02_the_core_template_override_wins_where_the_preset_replaces_one(installed: Path) -> None:
    for name in ("spec-template", "plan-template", "tasks-template"):
        if name not in PRESET_TEMPLATES:
            continue
        resolved = json.loads(
            scratch.run([".specify/scripts/bash/resolve-template.sh", name, "--json"], installed).stdout
        )
        assert resolved["TEMPLATE_CONTENT"] == (REPO / "templates" / f"{name}.md").read_text(encoding="utf-8")


def test_c04_the_helper_runs_from_the_installed_location(installed: Path) -> None:
    (installed / "README.md").write_text("Hello\n", encoding="utf-8")
    helper = installed / ".specify" / "extensions" / "eil" / "scripts" / "python" / "eil"
    assert (helper / "__main__.py").is_file()
    proc = subprocess.run(
        [sys.executable, str(helper), "fingerprint", "README.md"],
        cwd=installed,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert re.fullmatch(r"sha256:[0-9a-f]{64}", proc.stdout.strip())


def test_c04_an_ungoverned_project_is_left_alone_by_every_other_command(installed: Path) -> None:
    helper = installed / ".specify" / "extensions" / "eil" / "scripts" / "python" / "eil"
    proc = subprocess.run(
        [sys.executable, str(helper), "status", "--json"],
        cwd=installed,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 3 and json.loads(proc.stdout) == {"governed": False}


def test_c01_removal_restores_a_project_without_the_preset_or_extension(scratch_project: Path) -> None:
    scratch.install_extension(scratch_project)
    scratch.install_preset(scratch_project)
    scratch.remove_preset(scratch_project)
    scratch.remove_extension(scratch_project)
    remaining = [p for p in scratch.changed_paths(scratch_project) if p.startswith(".specify/extensions/eil")]
    assert remaining == []
    resolved = scratch.run(
        [".specify/scripts/bash/resolve-template.sh", "spec-template", "--json"], scratch_project
    )
    core = (scratch_project / ".specify" / "templates" / "spec-template.md").read_text(encoding="utf-8")
    assert json.loads(resolved.stdout)["TEMPLATE_CONTENT"] == core


@pytest.mark.skipif(len(EXTENSION_COMMANDS) < 19, reason="the last command arrives in task T129")
def test_the_finished_extension_registers_nineteen_commands_and_four_hooks(installed: Path) -> None:
    assert len(EXTENSION_COMMANDS) == 19
    hooks = (installed / ".specify" / "extensions.yml").read_text(encoding="utf-8")
    for name in ("after_clarify", "after_plan", "after_tasks", "after_implement"):
        assert name in hooks
    assert len(re.findall(r"command:\s*speckit\.eil\.status", hooks)) == 4


@pytest.mark.skipif(
    len(PRESET_COMMANDS) < 7 or len(PRESET_TEMPLATES) < 9,
    reason="the last wrap arrives in task T107 and the last template in task T116",
)
def test_the_finished_preset_composes_seven_core_commands(installed: Path) -> None:
    assert sorted(PRESET_COMMANDS) == sorted(
        f"speckit.{n}" for n in ("specify", "clarify", "plan", "tasks", "analyze", "checklist", "implement")
    )
    assert len(PRESET_TEMPLATES) == 9
