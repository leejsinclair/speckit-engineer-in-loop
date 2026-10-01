"""Focused gate output and the purpose of each request (task T067; FR-028, FR-032)."""

from __future__ import annotations

from eil import cli, overview
from eil.gates import CriterionResult, GateResult
from eil.package import Package

from tests.helpers.package import Story, requirements_doc

PURPOSES = {"awareness", "understanding", "decision", "validation", "approval"}


def crit(cid: str, kind: str, status: str, reason: str = "") -> CriterionResult:
    return CriterionResult(cid, f"text of {cid}", kind, status, reason)


def result() -> GateResult:
    criteria = [
        crit("S-01", "structural", "met"),
        crit("J-01", "judgment", "met", "assessed"),
        crit("S-02", "structural", "not-met", "missing"),
        crit("T-01", "traceability", "met"),
        crit("J-02", "judgment", "not-met", "no judgment supplied"),
        crit("S-03", "structural", "met"),
    ]
    return GateResult("functional", "f" * 64, criteria, [], {})


def test_json_orders_unmet_then_judgment_then_met() -> None:
    ids = [c["id"] for c in result().to_json()["criteria"]]
    assert ids == ["S-02", "J-02", "J-01", "S-01", "T-01", "S-03"]


def test_the_summary_counts_the_met_structural_criteria() -> None:
    summary = result().to_json()["summary"]
    assert summary["met_structural"] == 3 and summary["total"] == 6 and summary["unmet"] == 2


def test_text_collapses_met_structural_criteria_unless_full() -> None:
    focused = cli._render_check(result())
    assert "S-02" in focused and "J-02" in focused and "J-01" in focused
    assert "S-01" not in focused and "T-01" not in focused and "S-03" not in focused
    assert "3 structural criteria met" in focused
    full = cli._render_check(result(), full=True)
    assert all(i in full for i in ("S-01", "T-01", "S-03"))
    assert "structural criteria met" not in full


def test_every_next_action_states_one_of_the_five_purposes(story_dir: Story) -> None:
    assert overview.status(Package(story_dir.root))["next_action"]["purpose"] in PURPOSES
    story_dir.write("requirements", requirements_doc())
    assert overview.status(Package(story_dir.root))["next_action"]["purpose"] in PURPOSES


def test_a_challenge_to_answer_is_a_decision_and_the_action_is_named(story_dir: Story) -> None:
    from eil import records

    story_dir.write("requirements", requirements_doc())
    package = Package(story_dir.root)
    records.add_challenge(package, "requirements", "REQ-001", "A gap?", "Grace Lead", "medium")
    action = overview.status(Package(story_dir.root))["next_action"]
    assert action["kind"] == "human" and action["purpose"] == "decision"


def test_status_lists_open_low_challenges_per_stage_and_they_do_not_lead_the_next_action(
    story_dir: Story,
) -> None:
    from eil import records

    story_dir.write("requirements", requirements_doc())
    package = Package(story_dir.root)
    records.add_challenge(package, "requirements", "REQ-001", "A minor point?", "ai", "low")
    payload = overview.status(Package(story_dir.root))
    assert payload["stages"]["requirements"]["outstanding_low"] == ["CH-001"]
    assert payload["outstanding"]["open_challenges"] == []
    assert payload["outstanding"]["low_challenges"] == ["CH-001"]
    assert "CH-001" not in payload["next_action"]["message"]
