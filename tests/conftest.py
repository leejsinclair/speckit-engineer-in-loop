"""Shared pytest fixtures (task T008)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from tests.helpers import scratch
from tests.helpers.package import Story

REPO_ROOT = Path(__file__).resolve().parents[1]
HELPER_DIR = REPO_ROOT / "extensions" / "eil" / "scripts" / "python" / "eil"


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--update-baseline",
        action="store_true",
        default=False,
        help="recapture tests/fixtures/baseline-001-counts.json from the eil-001-baseline tag (SC-001)",
    )


@dataclass
class EilResult:
    """The outcome of one helper invocation."""

    code: int
    stdout: str
    stderr: str
    json: Any = field(default=None)

    @property
    def refusal_codes(self) -> list[str]:
        if isinstance(self.json, dict):
            return [r["code"] for r in self.json.get("refusals", [])]
        return []


def _run_eil(
    args: list[str], cwd: Path, env: dict[str, str] | None = None, helper: Path = HELPER_DIR
) -> EilResult:
    full_env = {**os.environ, **(env or {})}
    proc = subprocess.run(
        [sys.executable, str(helper), *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        env=full_env,
        check=False,
    )
    parsed = None
    if "--json" in args and proc.stdout.strip():
        parsed = json.loads(proc.stdout)
    return EilResult(proc.returncode, proc.stdout, proc.stderr, parsed)


@pytest.fixture
def run_eil() -> Callable[..., EilResult]:
    """``run_eil(args, cwd, env=None)`` runs the helper as ``python3 <dir> ...``."""

    def runner(args: list[str], cwd: Path, env: dict[str, str] | None = None) -> EilResult:
        return _run_eil(args, cwd, env)

    return runner


@pytest.fixture
def scratch_project(tmp_path: Path) -> Path:
    """A committed scratch Spec Kit project (skips when ``specify`` is unavailable)."""
    return scratch.make_scratch_project(tmp_path / "project")


@pytest.fixture
def story_dir(tmp_path: Path) -> Story:
    """An empty governed story package (only ``s00`` exists)."""
    return Story(tmp_path / "specs" / "001-story")


@pytest.fixture
def reference_story(tmp_path: Path) -> Story:
    """The reference story: approved through tasks, with a plan, tasks and evidence (B-27, SC-001)."""
    from tests.fixtures import reference_story as reference

    return reference.build(tmp_path / "specs" / "001-story")


@pytest.fixture
def eil_json(run_eil: Callable[..., EilResult]) -> Callable[..., tuple[int, Any]]:
    """``eil_json(args, cwd, env=None)`` runs the helper with ``--json``; returns ``(exit code, parsed JSON)``."""

    def runner(args: list[str], cwd: Path, env: dict[str, str] | None = None) -> tuple[int, Any]:
        result = run_eil([*args, "--json"] if "--json" not in args else args, cwd, env)
        return result.code, result.json

    return runner
