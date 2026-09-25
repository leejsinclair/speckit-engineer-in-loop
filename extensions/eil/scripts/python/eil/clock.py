"""The one place the helper reads the wall clock, so tests can replace it."""

from __future__ import annotations

from datetime import UTC, datetime


def utc_now() -> str:
    """RFC 3339 UTC to the second, for example ``2026-09-25T10:14:03Z``."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
