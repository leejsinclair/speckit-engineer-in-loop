"""B-25 (task T068): focused presentation and challenge severity. FR-028 to FR-030, FR-048."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from tests.scenario.conftest import write_judgments
from tests.scenario.test_b04_b14_b16_functional import FUN_JUDGED, feature, write_ready_functional
from tests.scenario.test_b05_b15_technical import take_the_check

pytestmark = pytest.mark.scenario

YES = "Yes, this is the behaviour we require."


def raise_gap(eil: Callable, text: str, severity: str | None, target: str = "FR-001"):
    args = ["challenge", "add", "functional", "--target", target, "--text", text, "--json"]
    return eil([*args, "--severity", severity] if severity else args)


def severity(eil: Callable, cid: str, to: str, by: str):
    return eil(["challenge", "severity", cid, "--to", to, "--by", by, "--json"])


def test_b25_focused_check_output_and_full(project: Path, eil: Callable) -> None:
    write_ready_functional(project, eil)
    focused = eil(["check", "--stage", "functional"])
    assert "structural criteria met" in focused.stdout
    full = eil(["check", "--stage", "functional", "--full"])
    assert "structural criteria met" not in full.stdout
    assert len(full.stdout.splitlines()) > len(focused.stdout.splitlines())
    data = eil(["check", "--stage", "functional", "--json"]).json
    assert data["summary"]["met_structural"] > 0
    assert data["criteria"][0]["status"] in ("not-met", "met")


def test_b25_severity_lifecycle(project: Path, eil: Callable) -> None:
    write_ready_functional(project, eil)
    assert raise_gap(eil, "A minor wording point on the summary line?", "low").json["id"] == "CH-001"
    assert raise_gap(eil, "What if two requests arrive together?", "medium").json["id"] == "CH-002"
    assert raise_gap(eil, "Is the limit per file or per customer?", "high", "NFR-001").json["id"] == "CH-003"
    outstanding = eil(["status", "--json"]).json["outstanding"]
    assert outstanding["open_challenges"] == ["CH-003", "CH-002"]
    assert outstanding["low_challenges"] == ["CH-001"]

    for cid in ("CH-002", "CH-003"):
        assert eil(["challenge", "answer", cid, "--response", "accepted", "--by", "Ada Dev", "--json"]).code == 0
    judged = write_judgments(project, "functional", FUN_JUDGED)
    assert eil(["check", "--stage", "functional", "--judgments", str(judged), "--json"]).code == 0
    take_the_check(eil, "functional")
    approved = eil(["approve", "functional", "--by", "Ada Dev", "--attestation", YES, "--json"])
    assert approved.code == 0, approved.stdout
    assert approved.json["approval"]["outstanding"] == ["CH-001"]
    assert "CH-001" in (feature(project) / "s00-README.md").read_text(encoding="utf-8")

    raised = severity(eil, "CH-001", "high", "Sam QA")
    assert raised.code == 0 and raised.json["challenge"]["severity"] == "high"
    lowered = severity(eil, "CH-001", "low", "Sam QA")
    assert lowered.code == 1 and lowered.refusal_codes == ["not-a-confirmer"]
    assert eil(["status", "--json"]).json["outstanding"]["open_challenges"] == ["CH-001"]


def test_b25_the_ai_must_rate_and_a_duplicate_names_the_first(project: Path, eil: Callable) -> None:
    write_ready_functional(project, eil)
    unrated = eil(
        ["challenge", "add", "functional", "--target", "FR-001", "--text", "A gap?", "--by", "ai", "--json"]
    )
    assert unrated.code == 2
    first = raise_gap(eil, "Is the scope complete for batches?", "medium")
    again = raise_gap(eil, "is the scope complete for batches", "high")
    assert again.code == 1 and again.json["refusals"][0]["existing"] == first.json["id"]
