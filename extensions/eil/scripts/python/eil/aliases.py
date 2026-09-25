"""The three compatibility aliases (task T087; FR-049 to FR-053, research D-06 and D-07).

Spec Kit expects ``spec.md``, ``plan.md`` and ``tasks.md``. Each is a name for one real document
(``s04``, ``s05``, ``s06``), created only once its target exists and never edited on its own:
a relative symlink where the platform allows it, otherwise a read-only mirror with identical bytes.

``refresh`` classifies every alias, reports what it found, and only then repairs it, so a fault is
never silent (FR-051, FR-053). It never opens the real document for writing: an alias that is a
symlink is unlinked before anything is written in its place, so nothing can write through it.
"""

from __future__ import annotations

import os
import stat
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from .package import ALIASES, Package

SYMLINK, MIRROR = "symlink", "mirror"
_READ_ONLY = 0o444
_ANY_WRITE = stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH


@dataclass(frozen=True)
class AliasState:
    name: str
    target: str
    form: str | None  # symlink | mirror | None when there is no alias
    fault: str | None  # missing | wrong-target | diverged | mirror-differs | target-missing

    def to_json(self) -> dict[str, str | None]:
        return {"name": self.name, "target": self.target, "form": self.form, "fault": self.fault}


def alias_mode(env: Mapping[str, str]) -> str:
    """``mirror`` when the test switch forces it (quickstart B-08), else ``symlink``."""
    return MIRROR if env.get("EIL_ALIAS_MODE", "").strip().lower() == MIRROR else SYMLINK


def _classify_one(root: Path, name: str, target_name: str) -> AliasState | None:
    alias, target = root / name, root / target_name
    exists = os.path.lexists(alias)
    if not target.is_file():
        return AliasState(name, target_name, _form(alias), "target-missing") if exists else None
    if not exists:
        return AliasState(name, target_name, None, "missing")
    if alias.is_symlink():
        try:
            same = alias.resolve(strict=True) == target.resolve(strict=True)
        except OSError:
            same = False
        return AliasState(name, target_name, SYMLINK, None if same else "wrong-target")
    if not alias.is_file():
        return AliasState(name, target_name, None, "diverged")
    if alias.read_bytes() == target.read_bytes():
        return AliasState(name, target_name, MIRROR, None)
    read_only = not alias.stat().st_mode & _ANY_WRITE
    return AliasState(name, target_name, MIRROR, "mirror-differs" if read_only else "diverged")


def _form(alias: Path) -> str | None:
    if alias.is_symlink():
        return SYMLINK
    return MIRROR if alias.is_file() else None


def classify(pkg: Package) -> list[AliasState]:
    """The state of every alias that exists or should. An alias whose target does not exist yet is
    absent by design and is not listed."""
    found = (_classify_one(pkg.root, name, target) for name, target in ALIASES.items())
    return [state for state in found if state is not None]


def _remove(alias: Path) -> bool:
    if alias.is_dir() and not alias.is_symlink():
        return False  # never delete a directory someone put there
    try:
        alias.unlink()
    except PermissionError:
        alias.chmod(0o666)
        alias.unlink()
    return True


def _write_mirror(alias: Path, target: Path) -> None:
    alias.write_bytes(target.read_bytes())
    alias.chmod(_READ_ONLY)


def _create(root: Path, name: str, target_name: str, mode: str) -> None:
    alias, target = root / name, root / target_name
    if mode == SYMLINK:
        try:
            os.symlink(target_name, alias)
            return
        except (OSError, NotImplementedError):
            pass  # the platform or filesystem refuses links: use a mirror (D-07)
    _write_mirror(alias, target)


def refresh(
    pkg: Package, mode: str = SYMLINK, check_only: bool = False
) -> tuple[list[AliasState], list[AliasState]]:
    """Classify, then repair. Returns ``(before, after)``; ``before`` is what was found and is what to
    report. With ``check_only`` nothing is written."""
    before = classify(pkg)
    if check_only:
        return before, before
    for state in before:
        needs_convert = mode == MIRROR and state.form == SYMLINK and state.fault is None
        if state.fault in (None, "target-missing") and not needs_convert:
            continue
        alias = pkg.root / state.name
        if state.fault != "missing" or needs_convert:
            if not _remove(alias):
                continue
        keep_mirror = (
            state.fault in ("mirror-differs", "diverged") and state.form == MIRROR and mode != MIRROR
        )
        _create(pkg.root, state.name, state.target, MIRROR if (needs_convert or keep_mirror) else mode)
    return before, classify(pkg)
