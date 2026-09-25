"""B-10 (task T119): AI challenges, human decides. FR-034 to FR-038."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from tests.scenario.conftest import write_judgments
from tests.scenario.test_b04_b14_b16_functional import FUN_JUDGED, feature, write_ready_functional
from tests.scenario.test_b05_b15_technical import take_the_check

pytestmark = pytest.mark.scenario

GAP = "The functional specification does not define what happens when two duplicate-detection requests arrive at the same time."
YES = "Yes, this is the behaviour we require."


def raise_gap(eil: Callable, text: str = GAP, target: str = "FR-001"):
    return eil(["challenge", "add", "functional", "--target", target, "--text", text, "--json"])


def answer(eil: Callable, cid: str, response: str, by: str = "Ada Dev", *extra: str):
    return eil(["challenge", "answer", cid, "--response", response, "--by", by, *extra, "--json"])


def approve(eil: Callable):
    return eil(["approve", "functional", "--by", "Ada Dev", "--attestation", YES, "--json"])


def test_b10_a_specific_challenge_is_recorded_open_and_blocks_approval(project: Path, eil: Callable) -> None:
    write_ready_functional(project, eil)
    take_the_check(eil, "functional")
    raised = raise_gap(eil)
    assert raised.code == 0 and raised.json["id"] == "CH-001"
    text = (feature(project) / "s02-functional-spec.md").read_text(encoding="utf-8")
    assert "```eil:challenge" in text and '"status": "open"' in text
    status = eil(["status", "--json"]).json
    assert status["outstanding"]["open_challenges"] == ["CH-001"]
    assert "CH-001" in (feature(project) / "s00-README.md").read_text(encoding="utf-8")
    refused = approve(eil)
    assert refused.code == 1 and "open-challenge" in refused.refusal_codes


def test_b10_the_check_cannot_start_while_a_challenge_is_open(project: Path, eil: Callable) -> None:
    write_ready_functional(project, eil)
    raise_gap(eil)
    plan = eil(["comprehension", "plan", "--stage", "functional", "--json"])
    assert plan.code == 1 and plan.refusal_codes == ["comprehension-prerequisites"]


def test_b10_a_rejection_needs_a_reason_and_closes_the_challenge(project: Path, eil: Callable) -> None:
    write_ready_functional(project, eil)
    raise_gap(eil)
    refused = answer(eil, "CH-001", "rejected")
    assert refused.code == 1 and refused.refusal_codes == ["reason-required"]
    closed = answer(
        eil,
        "CH-001",
        "rejected",
        "Ada Dev",
        "--reason",
        "requests are idempotent on customer id and analysis version",
    )
    assert closed.code == 0 and closed.json["challenge"]["status"] == "closed"
    assert eil(["status", "--json"]).json["outstanding"]["open_challenges"] == []
    # the record changed the document, so the AI's verdicts are for an earlier version: it judges again
    judged = write_judgments(project, "functional", FUN_JUDGED)
    assert eil(["check", "--stage", "functional", "--judgments", str(judged), "--json"]).json["ok"] is False
    take_the_check(eil, "functional")
    assert approve(eil).code == 0


def test_b10_the_rerun_pass_does_not_raise_a_rejected_point_again(project: Path, eil: Callable) -> None:
    write_ready_functional(project, eil)
    raise_gap(eil)
    answer(eil, "CH-001", "rejected", "Ada Dev", "--reason", "idempotent")
    again = raise_gap(eil, GAP.lower().replace("-", " ").rstrip("."))
    assert again.code == 1 and again.refusal_codes == ["duplicate-of-closed"]
    assert "Ada Dev" in again.json["refusals"][0]["message"]
    other = raise_gap(eil, "How is a file of over a million rows handled?")
    assert other.code == 0 and other.json["id"] == "CH-002"


def test_b10_the_ai_cannot_answer_and_a_stranger_cannot_either(project: Path, eil: Callable) -> None:
    write_ready_functional(project, eil)
    raise_gap(eil)
    assert "ai-approval" in answer(eil, "CH-001", "accepted", "Claude").refusal_codes
    assert "not-a-confirmer" in answer(eil, "CH-001", "accepted", "Mallory").refusal_codes
    assert eil(["status", "--json"]).json["outstanding"]["open_challenges"] == ["CH-001"]


def test_b10_two_people_answering_differently_is_a_conflict_a_configured_confirmer_settles(
    project: Path, eil: Callable
) -> None:
    config = project / ".specify" / "extensions" / "eil" / "eil-config.yml"
    config.write_text("approvers:\n  functional: [Ada Dev, Grace Lead]\n", encoding="utf-8")
    write_ready_functional(project, eil)
    raise_gap(eil)
    answer(eil, "CH-001", "rejected", "Ada Dev", "--reason", "no")
    conflict = answer(eil, "CH-001", "accepted", "Grace Lead")
    assert conflict.code == 0 and conflict.json["conflict"] is True
    assert eil(["status", "--json"]).json["outstanding"]["open_challenges"] == ["CH-001"]
    assert "open-challenge" in approve(eil).refusal_codes
    stranger = answer(eil, "CH-001", "accepted", "Mallory")
    assert stranger.refusal_codes == ["not-a-confirmer"]
    settled = answer(eil, "CH-001", "rejected", "Ada Dev", "--reason", "the owner decides: no")
    assert settled.json["conflict"] is False and settled.json["challenge"]["resolved_conflict"] is True
    assert eil(["status", "--json"]).json["outstanding"]["open_challenges"] == []


def test_b10_challenges_are_allowed_at_any_definition_stage_and_not_elsewhere(
    project: Path, eil: Callable
) -> None:
    write_ready_functional(project, eil)
    ok = eil(
        [
            "challenge",
            "add",
            "requirements",
            "--target",
            "REQ-001",
            "--text",
            "Is the success criterion measurable?",
            "--json",
        ]
    )
    assert ok.code == 0
    no = eil(
        ["challenge", "add", "verification", "--target", "REQ-001", "--text", "Is this verified?", "--json"]
    )
    assert no.code == 1
    unknown = eil(["challenge", "add", "functional", "--target", "FR-404", "--text", "About what?", "--json"])
    assert unknown.code == 1 and unknown.refusal_codes == ["unknown-item"]
