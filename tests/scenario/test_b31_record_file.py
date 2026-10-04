"""B-31 (US2, FR-007 to FR-012, SC-002): the records move out of the documents.

On the reference story, `sync` moves every record into `eil-record.json`: every fingerprint and
approval is unchanged, no JSON is left in a stage document, and what remains of the record in each
document is under 10% of its bytes. Deleting the file makes the approvals unverifiable. `show` is clean.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest
from eil.blocks import Doc
from eil.package import RECORD_NAMES

from tests.conftest import EilResult
from tests.fixtures import reference_story
from tests.helpers import derived

pytestmark = pytest.mark.scenario
FEATURE = "specs/001-story"
STAGES = ("requirements", "functional", "technical", "ai-spec", "plan", "tasks", "verification")


def region_bytes(text: str) -> int:
    """The bytes of record left in a document: the bodies of its record regions (the Change Log is content)."""
    doc = Doc(text)
    return sum(len("\n".join(doc.region_lines(name)).encode()) for name in RECORD_NAMES)


def test_b31_record_file(project: Path, eil: Callable[..., EilResult]) -> None:
    story = reference_story.build(project / FEATURE)
    derived.settle_derived(story)  # records for every derived block, as a run through tasks leaves them
    for stage in ("requirements", "functional", "technical"):
        assert eil(["check", "--stage", stage, "--feature-dir", FEATURE, "--json"]).code == 0

    before = eil(["status", "--feature-dir", FEATURE, "--json"]).json
    fingerprints = {
        s: eil(["fingerprint", f"{FEATURE}/{story.path(s).name}", "--json"]).json["fingerprint"]
        for s in STAGES
    }

    synced = eil(["sync", "--feature-dir", FEATURE, "--json"])
    assert synced.code == 0, synced.stderr
    after = eil(["status", "--feature-dir", FEATURE, "--json"]).json
    assert {s: e["state"] for s, e in after["stages"].items()} == {
        s: e["state"] for s, e in before["stages"].items()
    }
    assert {s: e.get("approval") for s, e in after["stages"].items()} == {
        s: e.get("approval") for s, e in before["stages"].items()
    }
    for stage in STAGES:
        text = story.read(stage)
        assert (
            eil(["fingerprint", f"{FEATURE}/{story.path(stage).name}", "--json"]).json["fingerprint"]
            == fingerprints[stage]
        )
        assert "```json" not in text and '"hash": "sha256:' not in text, stage
        assert region_bytes(text) < 0.10 * len(text.encode()), stage
    record = json.loads((project / FEATURE / "eil-record.json").read_text())
    assert set(record["stages"]) >= {"requirements", "functional", "technical", "tasks"}

    shown = eil(["show", "tasks", "--feature-dir", FEATURE, "--json"])
    assert shown.code == 0 and "sha256:" not in shown.json["text"] and "<!--" not in shown.json["text"]

    (project / FEATURE / "eil-record.json").unlink()
    gone = eil(["status", "--feature-dir", FEATURE, "--json"]).json
    for stage in ("requirements", "functional", "technical"):
        assert gone["stages"][stage]["state"] == "needs-re-review"
        assert gone["stages"][stage]["reason"] == "approval record missing or unreadable"
