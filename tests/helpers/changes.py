"""Helpers for tests that confirm changes: the AI's one-line summary per change (D-39)."""

from __future__ import annotations

from eil import provenance
from eil.package import Package


def summaries_for(pkg: Package, stage: str) -> dict[str, str]:
    return {row.id: f"Summary of the change to {row.id}." for row in provenance.change_rows(pkg, stage)}
