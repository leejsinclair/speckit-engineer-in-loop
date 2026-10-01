"""Build scratch Spec Kit projects for contract and scenario tests (task T006).

Every helper shells out to the real ``specify`` CLI so the tests exercise the installed
Spec Kit, not a model of it. Tests skip when ``specify`` is not on PATH.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

from tests.helpers import release

REPO_ROOT = Path(__file__).resolve().parents[2]
EXTENSION_DIR = REPO_ROOT / "extensions" / "eil"

SPECIFY = shutil.which("specify")


def require_specify() -> None:
    """Skip the calling test when the Spec Kit CLI is unavailable."""
    if SPECIFY is None:
        pytest.skip("`specify` is not on PATH")


def run(args: list[str], cwd: Path, check: bool = True) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(args, cwd=cwd, capture_output=True, text=True, check=False)
    if check and proc.returncode != 0:
        raise AssertionError(
            f"{' '.join(args)} exited {proc.returncode}\nstdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
        )
    return proc


def git(project: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return run(["git", *args], project, check=check)


def specify(project: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    require_specify()
    return run([SPECIFY, *args], project, check=check)  # type: ignore[list-item]


def make_scratch_project(directory: Path) -> Path:
    """Create ``directory`` as a git repository initialised with ``specify init``, then commit it."""
    require_specify()
    directory.mkdir(parents=True, exist_ok=True)
    git(directory, "init", "-q")
    git(directory, "config", "user.name", "Test Developer")
    git(directory, "config", "user.email", "developer@example.test")
    git(directory, "config", "gc.auto", "0")
    specify(directory, "init", "--here", "--integration", "claude", "--force")
    git(directory, "add", "-A")
    git(directory, "commit", "-q", "-m", "baseline")
    return directory


def install_extension(project: Path, source: Path | None = None) -> subprocess.CompletedProcess[str]:
    """Install the extension from a staged copy (or from ``source`` when a test supplies a stub)."""
    if source is None:
        source = release.stage_extension(Path(tempfile.mkdtemp(prefix="eil-ext-")) / "eil")
    return specify(project, "extension", "add", "--dev", str(source))


def install_preset(project: Path, source: Path | None = None) -> subprocess.CompletedProcess[str]:
    """Install the preset from a staged copy: ``--dev .`` would copy the whole repository (F-16)."""
    if source is None:
        source = release.stage_preset(Path(tempfile.mkdtemp(prefix="eil-preset-")) / "preset")
    return specify(project, "preset", "add", "--dev", str(source))


def remove_preset(project: Path, preset_id: str = "engineer-in-the-loop") -> subprocess.CompletedProcess[str]:
    return specify(project, "preset", "remove", preset_id)


def remove_extension(project: Path, extension_id: str = "eil") -> subprocess.CompletedProcess[str]:
    return specify(project, "extension", "remove", extension_id, "--force")


def changed_paths(project: Path) -> list[str]:
    """Paths reported by ``git status --porcelain`` (untracked files listed individually)."""
    out = git(project, "status", "--porcelain", "--untracked-files=all").stdout
    return [line[3:] for line in out.splitlines() if line.strip()]
