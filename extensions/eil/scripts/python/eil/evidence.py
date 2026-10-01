"""Confirming that the test or check an evidence row names exists (research D-41; FR-034, FR-035).

Reads files only: no test is run and nothing is fetched. A confirmed row means the named test exists in
the file it names; that its result was good stays the person's attestation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .package import Package

NOTE = "exists; result attested"
LIMIT = (
    "Evidence marked confirmed names a test the helper found in a file; it did not run it (exists; result "
    "attested). Manual evidence, and evidence naming no findable test, is shown to you."
)
_MAX_BYTES = 2_000_000
_PATH = re.compile(r"(?<![\w./-])(?P<path>[\w.-]+(?:/[\w.-]+)*\.\w+)(?P<rest>(?:::[^\s:()]+)*)")
_NODE = re.compile(r"::([^:]+)")
_QUOTED = re.compile(r"['\"`](?P<name>[^'\"`]+)['\"`]")
_IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_WORDS = frozenset(
    "in of at the a an for from file test tests check checks and or is are passes passed green ci see".split()
)


@dataclass(frozen=True)
class Confirmation:
    confirmed: bool
    reason: str = ""
    note: str = ""


def _no(reason: str) -> Confirmation:
    return Confirmation(False, reason)


def _names(text: str, found: re.Match[str]) -> list[str]:
    """The names asked for: those after ``::``, else quoted or identifier-like words around the path."""
    chained = _NODE.findall(found["rest"])
    if chained:
        return [c.strip() for c in chained]
    around = text[: found.start()] + " " + text[found.end() :]
    tail = around.lstrip()
    if tail.startswith("::"):
        tail = tail[2:]
    quoted = [m["name"].strip() for m in _QUOTED.finditer(around)]
    if quoted:
        return quoted
    return [w for w in _IDENT.findall(around) if w.lower() not in _WORDS and ("_" in w or w[:4] == "test")]


def _defines(source: str, name: str) -> bool:
    escaped = re.escape(name)
    pattern = (
        rf"(?m)^\s*(?:async\s+)?(?:def|class|function|func|fn|const|let|var)\s+{escaped}\b"
        rf"|\b(?:it|test|describe|context|specify)(?:\.\w+)?\s*\(\s*['\"`]{escaped}['\"`]"
    )
    return re.search(pattern, source) is not None


def confirm(root: Path, evidence: str) -> Confirmation:
    """Whether ``evidence`` names a test that the file it names, inside ``root``, defines."""
    found = _PATH.search(evidence or "")
    if not found:
        return _no("it names no file")
    base = root.resolve()
    target = (base / found["path"]).resolve()
    if not target.is_relative_to(base):
        return _no(f"{found['path']} is outside the project")
    if not target.is_file():
        return _no(f"{found['path']} does not exist in the project")
    names = _names(evidence, found)
    if not names:
        return _no(f"it names a file ({found['path']}) but no test in it")
    try:
        if target.stat().st_size > _MAX_BYTES:
            return _no(f"{found['path']} is too large to search")
        source = target.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return _no(f"{found['path']} cannot be read as text")
    for name in names:
        if not _defines(source, name):
            return _no(f"{found['path']} does not define {name}")
    return Confirmation(True, f"{found['path']} defines {', '.join(names)}", NOTE)


def confirmed_rows(package: Package) -> dict[str, Confirmation]:
    """``{EVD id: confirmation}`` for the automated rows whose named test the project's files define."""
    from . import verification
    from .trace import evidence_fields

    root = package.project_root or package.root
    out: dict[str, Confirmation] = {}
    for row in verification.evidence_rows(package):
        fields = evidence_fields(row)
        if fields.get("kind", "").strip().lower() != "automated":
            continue
        found = confirm(root, fields.get("evidence", ""))
        if found.confirmed:
            out[row.id] = found
    return out
