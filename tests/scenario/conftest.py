"""Scenario fixtures: a real Spec Kit project with the extension and preset installed.

Each test gets its own copy of one installed project (built once per session), and drives the
*installed* helper, as the slash commands do.
"""

from __future__ import annotations

import json
import shutil
from collections.abc import Callable
from pathlib import Path

import pytest

from tests.conftest import EilResult, _run_eil
from tests.helpers import scratch

INSTALLED_HELPER = Path(".specify") / "extensions" / "eil" / "scripts" / "python" / "eil"


@pytest.fixture(scope="session")
def installed_template(tmp_path_factory: pytest.TempPathFactory) -> Path:
    scratch.require_specify()
    root = tmp_path_factory.mktemp("installed") / "project"
    scratch.make_scratch_project(root)
    scratch.install_extension(root)
    scratch.install_preset(root)
    scratch.git(root, "add", "-A")
    scratch.git(root, "commit", "-q", "-m", "installed")
    return root


@pytest.fixture
def project(installed_template: Path, tmp_path: Path) -> Path:
    target = tmp_path / "project"
    shutil.copytree(installed_template, target, symlinks=True)
    return target


@pytest.fixture
def eil(project: Path) -> Callable[..., EilResult]:
    """``eil(args, env=None)`` runs the installed helper in the project."""

    def run(args: list[str], env: dict[str, str] | None = None) -> EilResult:
        return _run_eil(args, project, env, helper=project / INSTALLED_HELPER)

    return run


def write_judgments(directory: Path, stage: str, ids: list[str]) -> Path:
    path = directory / f"{stage}-judgments.json"
    body = {"stage": stage, "judgments": [{"id": i, "status": "met", "reason": "assessed"} for i in ids]}
    path.write_text(json.dumps(body), encoding="utf-8")
    return path
