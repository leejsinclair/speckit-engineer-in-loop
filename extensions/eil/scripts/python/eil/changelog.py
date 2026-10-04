"""The Change Log: one entry per accepted change, drafted by the AI and accepted as shown (D-39).

Entries live in the stage's provenance region (``changes[]``); the ``changelog`` region is a table
generated from them, excluded from the fingerprint, and never parsed back. A re-derivation writes none.
"""

from __future__ import annotations

from typing import Any

from .blocks import RegionError, write_changelog
from .package import Package

RECENT = 5


def entry(at: str, item: str, summary: str, origin: str, accepted_by: str) -> dict[str, Any]:
    return {
        "at": at, "item": item, "summary": summary.strip(), "summary_by": "ai",
        "origin": origin, "accepted_by": accepted_by,
    }  # fmt: skip


def stored_summary(record: dict[str, Any], key: str, digest: str) -> str | None:
    """The latest summary given with an acceptance of ``key`` at ``digest``."""
    found = None
    for acc in record.get("acceptances") or []:
        summary = (acc.get("summaries") or {}).get(key)
        if summary and (acc.get("hashes") or {}).get(key) == digest:
            found = summary
    return found


def refresh(pkg: Package, stage: str) -> bool:
    """Rewrite the ``changelog`` region of ``stage`` from its record. Returns whether the file changed."""
    try:
        record = pkg.record(stage, "provenance")
    except (OSError, UnicodeDecodeError):
        return False
    changes = [c for c in (record or {}).get("changes") or [] if isinstance(c, dict)]
    if not changes:
        return False
    text = pkg.read(stage)
    try:
        updated = write_changelog(text, changes, (record or {}).get("corrections"))
    except RegionError:
        return False
    if updated == text:
        return False
    pkg.doc_path(stage).write_bytes(updated.encode("utf-8"))
    return True


def refresh_all(pkg: Package) -> list[str]:
    return [s for s in pkg.existing_stages() if refresh(pkg, s)]


def recent(pkg: Package, limit: int = RECENT) -> list[dict[str, Any]]:
    """The latest ``limit`` entries story-wide, newest first."""
    rows = []
    for order, stage in enumerate(pkg.existing_stages()):
        try:
            record = pkg.record(stage, "provenance")
        except (OSError, UnicodeDecodeError):
            continue
        for index, change in enumerate((record or {}).get("changes") or []):
            if isinstance(change, dict):
                rows.append((str(change.get("at", "")), order, index, {"stage": stage, **change}))
    rows.sort(key=lambda r: r[:3], reverse=True)
    return [r[3] for r in rows[:limit]]
