"""The story a call acts on, and the branch a story is started on (research D-46, D-47; FR-001 to FR-006).

Resolution returns the directory together with where it came from: an ``argument``, the
``environment``, the active-story ``pointer`` (``.specify/feature.json``) or ``none``. A call that
writes is refused when its target came from the pointer or from nothing and cannot be told for
certain; one that names its story is never refused for that.

The branch is read with ``git symbolic-ref``, a local, read-only query (``identity`` already asks
git for ``user.name`` the same way). The helper never creates or switches a branch.
"""

from __future__ import annotations

import json
import re
import subprocess
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

POINTER = Path(".specify") / "feature.json"
ENVIRONMENT = "SPECIFY_FEATURE_DIRECTORY"
DEFAULT_MAIN_BRANCHES = ("main", "master")
BRANCH_QUESTION = "Write story {story} on branch {branch}?"
_NUMBER = re.compile(r"^(?P<number>\d+)-")


@dataclass
class Target:
    """Where a call's story came from. ``directory`` is ``None`` only when nothing names one."""

    directory: Path | None
    source: str  # argument | environment | pointer | none
    candidates: list[Path] = field(default_factory=list)

    @property
    def name(self) -> str | None:
        return self.directory.name if self.directory is not None else None


def _absolute(cwd: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else cwd / path


def read_pointer(cwd: Path) -> str | None:
    """The directory ``.specify/feature.json`` names, as written, or ``None``."""
    try:
        data = json.loads((cwd / POINTER).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    value = data.get("feature_directory") if isinstance(data, dict) else None
    return value.strip() if isinstance(value, str) and value.strip() else None


def stories(project: Path) -> list[Path]:
    """Every governed story of the project (a directory under ``specs/`` holding ``s00-README.md``)."""
    from .package import OVERVIEW

    specs = project / "specs"
    if not specs.is_dir():
        return []
    return sorted(p for p in specs.iterdir() if p.is_dir() and (p / OVERVIEW).is_file())


def resolve_target(cwd: Path, argument: str | None, env: Mapping[str, str]) -> Target:
    """The target story, as Spec Kit resolves it (argument, environment, pointer), with its source.
    With no pointer, a project holding exactly one story targets that story."""
    if argument:
        return Target(_absolute(cwd, argument), "argument")
    from_env = (env.get(ENVIRONMENT) or "").strip()
    if from_env:
        return Target(_absolute(cwd, from_env), "environment")
    found = stories(cwd)
    pointer = read_pointer(cwd)
    if pointer is not None:
        return Target(_absolute(cwd, pointer), "pointer", found)
    return Target(found[0] if len(found) == 1 else None, "none", found)


def completion_approved(directory: Path) -> bool:
    from .package import Package

    package = Package(directory)
    return package.governed and package.state("completion").state == "approved"


def _shown(cwd: Path, directory: Path) -> str:
    try:
        return directory.relative_to(cwd).as_posix()
    except ValueError:
        return str(directory)


def ambiguity(target: Target, cwd: Path) -> str | None:
    """Why a write to ``target`` cannot be trusted to land on the intended story, or ``None``
    (data-model §Story target). A story named on the call is never ambiguous."""
    if target.source in ("argument", "environment"):
        return None
    found = target.candidates
    names = ", ".join(_shown(cwd, s) for s in found) or "none"
    if target.source == "none":
        if target.directory is None and len(found) > 1:
            return f"no story is named and the project has more than one story ({names})"
        return None
    assert target.directory is not None
    if not target.directory.is_dir():
        return (
            f"the active-story pointer names {_shown(cwd, target.directory)}, which does not exist "
            f"(stories: {names})"
        )
    if completion_approved(target.directory):
        open_ = [s for s in found if s.resolve() != target.directory.resolve() and not completion_approved(s)]
        if open_:
            return (
                f"the active-story pointer names {_shown(cwd, target.directory)}, whose completion is approved, "
                f"while {', '.join(_shown(cwd, s) for s in open_)} is not complete"
            )
    return None


# ---- the branch a story is started on (D-47)


def current_branch(where: Path) -> str | None:
    """The checked-out branch, or ``None`` outside a repository or on a detached HEAD."""
    while not where.exists() and where != where.parent:
        where = where.parent
    try:
        proc = subprocess.run(
            ["git", "symbolic-ref", "--short", "-q", "HEAD"],
            cwd=where,
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    value = proc.stdout.strip()
    return value if proc.returncode == 0 and value else None


def branch_expected(branch: str, story: str, main_branches: list[str] | tuple[str, ...]) -> bool:
    """Whether a story named ``story`` may be started on ``branch`` without asking: the branch is a
    main branch, or is named for the story (its name, or its number prefix such as ``003-``)."""
    if branch in main_branches or branch == story:
        return True
    number = _NUMBER.match(story)
    return bool(number) and branch.startswith(f"{number['number']}-")


def branch_question(story: str, branch: str) -> str:
    return BRANCH_QUESTION.format(story=story, branch=branch)


__all__ = [
    "Target",
    "ambiguity",
    "branch_expected",
    "branch_question",
    "completion_approved",
    "current_branch",
    "read_pointer",
    "resolve_target",
    "stories",
]
