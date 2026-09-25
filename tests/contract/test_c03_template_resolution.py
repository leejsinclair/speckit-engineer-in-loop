"""C-03 (risk R-1, task T010): custom template names install and resolve.

The design gives the nine story documents template names beyond Spec Kit's core five
(research D-02). This proves, against the installed Spec Kit, that a preset can provide a
new template name and can override a core one, and that both resolve to the preset's file.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.helpers import scratch

pytestmark = pytest.mark.contract

STUBS = Path(__file__).parent / "stubs"


@pytest.fixture
def stubbed_project(scratch_project: Path) -> Path:
    scratch.install_extension(scratch_project, STUBS / "eil-stub")
    scratch.install_preset(scratch_project, STUBS / "preset-stub")
    return scratch_project


def resolve(project: Path, name: str) -> dict[str, str]:
    proc = scratch.run([".specify/scripts/bash/resolve-template.sh", name, "--json"], project)
    return json.loads(proc.stdout)


def test_new_template_name_resolves_to_the_preset_file(stubbed_project: Path) -> None:
    resolved = resolve(stubbed_project, "s01-requirements-template")
    assert resolved["TEMPLATE_NAME"] == "s01-requirements-template"
    assert resolved["TEMPLATE_CONTENT"] == "# STUB s01 requirements template\n"


def test_core_template_name_resolves_to_the_preset_override(stubbed_project: Path) -> None:
    resolved = resolve(stubbed_project, "spec-template")
    assert resolved["TEMPLATE_CONTENT"] == "# STUB spec-template override\n"


def test_cli_reports_the_preset_as_the_top_layer(stubbed_project: Path) -> None:
    out = scratch.specify(stubbed_project, "preset", "resolve", "s01-requirements-template").stdout
    flat = "".join(out.split())
    assert "presets/eil-preset-stub/templates/s01-requirements-template.md" in flat
    assert "toplayerfrom:eil-preset-stub" in flat


def test_an_unrelated_core_template_is_unchanged(stubbed_project: Path) -> None:
    resolved = resolve(stubbed_project, "plan-template")
    core = (stubbed_project / ".specify" / "templates" / "plan-template.md").read_text(encoding="utf-8")
    assert resolved["TEMPLATE_CONTENT"] == core


def test_removing_the_preset_restores_the_core_template(stubbed_project: Path) -> None:
    scratch.specify(stubbed_project, "preset", "remove", "eil-preset-stub")
    core = (stubbed_project / ".specify" / "templates" / "spec-template.md").read_text(encoding="utf-8")
    assert resolve(stubbed_project, "spec-template")["TEMPLATE_CONTENT"] == core
