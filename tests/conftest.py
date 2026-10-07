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
    parser.addoption(
        "--run-agent", action="store_true", default=False, help="run opt-in real-agent behavioural trials"
    )
    parser.addoption(
        "--agent-results", default="trial-results", help="directory for real-agent trial evidence"
    )
    parser.addoption("--agent-model", default=None, help="model passed to the real-agent adapter")
    parser.addoption(
        "--agent-max-turns", type=int, default=60, help="maximum turns in a real-agent conversation"
    )
    parser.addoption(
        "--keep-failed", action="store_true", default=False, help="retain failed agent workspaces"
    )
    parser.addoption(
        "--keep-workspace", action="store_true", default=False, help="retain every agent workspace"
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if config.getoption("--run-agent"):
        return
    skip = pytest.mark.skip(reason="real-agent trial; pass --run-agent to execute")
    for item in items:
        if "agent" in item.keywords:
            item.add_marker(skip)


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
def legacy_upgrade(tmp_path: Path) -> Story:
    """The ``bd7a0d5``-shaped story: legacy approvals, changed since, judgments recorded (T003, B-30)."""
    from tests.fixtures import legacy_upgrade as legacy

    return legacy.build(tmp_path / "specs" / "001-story")


@pytest.fixture
def two_stories(tmp_path: Path) -> Any:
    """Completed story A, in-progress story B, and the pointer on A (T004, B-29)."""
    from tests.fixtures import two_stories as fixture

    return fixture.build(tmp_path / "project")


def files_snapshot(root: Path) -> dict[str, bytes]:
    """``{relative path: bytes}`` of every file under ``root`` (``.git`` excluded), for byte-identity checks."""
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file() and ".git" not in path.relative_to(root).parts
    }


@pytest.fixture
def review_page_story(tmp_path: Path) -> Any:
    """The browser review page's story: Requirements approved, five Functional blocks listed (004 T002)."""
    from tests.fixtures import review_page

    built = review_page.build(tmp_path / "specs" / "001-story")
    yield built
    assert not (built.root / "eil-record.json.lock").exists(), "a record lock outlived its write"


@pytest.fixture
def page_server(review_page_story: Any, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Any:
    """The page for ``review_page_story``, served in a thread; stopped after the test (004 T004)."""
    import tempfile

    from tests.helpers.page import start_page

    runtime = tmp_path / "tmp"
    runtime.mkdir(exist_ok=True)
    monkeypatch.setattr(tempfile, "tempdir", str(runtime))
    page = start_page(review_page_story.root)
    yield page
    page.stop()
    assert not (review_page_story.root / "eil-record.json.lock").exists(), "a record lock outlived its write"


@pytest.fixture
def eil_json(run_eil: Callable[..., EilResult]) -> Callable[..., tuple[int, Any]]:
    """``eil_json(args, cwd, env=None)`` runs the helper with ``--json``; returns ``(exit code, parsed JSON)``."""

    def runner(args: list[str], cwd: Path, env: dict[str, str] | None = None) -> tuple[int, Any]:
        result = run_eil([*args, "--json"] if "--json" not in args else args, cwd, env)
        return result.code, result.json

    return runner
