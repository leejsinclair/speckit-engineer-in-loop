"""B-18, functional half (task T062): the comprehension check before approval.

The parts that depend on an AI phrasing and judging questions are judged by the trial probes
(docs/trials.md), not here. This drives everything the helper decides. FR-087 to FR-094, SC-016.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest
from eil.package import Package

from tests.helpers.package import record_block
from tests.scenario.conftest import write_judgments
from tests.scenario.test_b04_b14_b16_functional import FEATURE, FUN_JUDGED, feature, write_ready_functional

pytestmark = pytest.mark.scenario

LEVELS = ["recognise", "explain", "apply", "trace", "evaluate"]


def record(eil: Callable, level: str, outcome: str, **flags: str) -> object:
    argv = [
        "comprehension",
        "record",
        "--stage",
        "functional",
        "--level",
        level,
        "--outcome",
        outcome,
        "--by",
        "Ada Dev",
    ]
    for name, value in flags.items():
        argv += [f"--{name.replace('_', '-')}", value]
    return eil([*argv, "--json"])


def doc_path(project: Path) -> Path:
    return feature(project) / "s02-functional-spec.md"


def test_b18_an_open_challenge_blocks_the_check_until_it_is_closed(project: Path, eil: Callable) -> None:
    write_ready_functional(project, eil)
    challenge = record_block(
        "challenge",
        {
            "id": "CH-001",
            "stage": "functional",
            "status": "open",
            "target": "FR-001",
            "text": "What about duplicates?",
        },
    )
    path = doc_path(project)
    path.write_text(
        path.read_text(encoding="utf-8").replace("## Challenges\n", "## Challenges\n\n" + challenge),
        encoding="utf-8",
    )
    result = eil(["comprehension", "plan", "--stage", "functional", "--json"])
    assert result.code == 1 and result.refusal_codes == ["comprehension-prerequisites"]
    path.write_text(
        path.read_text(encoding="utf-8").replace('"status": "open"', '"status": "closed"'), encoding="utf-8"
    )
    eil(
        [
            "check",
            "--stage",
            "functional",
            "--judgments",
            str(write_judgments(project, "functional", FUN_JUDGED)),
            "--json",
        ]
    )
    assert eil(["comprehension", "plan", "--stage", "functional", "--json"]).code == 0


def test_b18_a_level_recorded_as_not_applicable_needs_a_reason(project: Path, eil: Callable) -> None:
    write_ready_functional(project, eil)
    refused = record(eil, "evaluate", "not-applicable")
    assert refused.code == 1 and refused.refusal_codes == ["reason-required"]
    accepted = record(eil, "evaluate", "not-applicable", reason="one screen, no trade-off", attempts="0")
    assert accepted.code == 0, accepted.stdout


def test_b18_only_a_configured_person_can_take_the_check(project: Path, eil: Callable) -> None:
    write_ready_functional(project, eil)
    result = eil(
        [
            "comprehension",
            "record",
            "--stage",
            "functional",
            "--level",
            "recognise",
            "--outcome",
            "understood",
            "--by",
            "Mallory",
            "--json",
        ]
    )
    assert result.code == 1 and result.refusal_codes == ["not-a-confirmer"]


def test_b18_an_extra_key_added_by_hand_makes_the_record_malformed(project: Path, eil: Callable) -> None:
    write_ready_functional(project, eil)
    for level in LEVELS:
        assert record(eil, level, "understood").code == 0
    path = doc_path(project)
    text = path.read_text(encoding="utf-8")
    path.write_text(
        text.replace(
            '"taken_by": "Ada Dev",', '"taken_by": "Ada Dev",\n  "answer": "the analyst uploads a file",'
        ),
        encoding="utf-8",
    )
    result = eil(["check", "--stage", "functional", "--json"])
    assert "malformed-comprehension" in [f["code"] for f in result.json["findings"]]
    assert {c["id"]: c["status"] for c in result.json["criteria"]}["FUN-G16"] == "not-met"
    approve = eil(["approve", "functional", "--by", "Ada Dev", "--attestation", "Yes.", "--json"])
    assert approve.code == 1 and "FUN-G16" in approve.json["refusals"][0]["message"]


def test_b18_the_counts_reach_the_approval_and_the_overview(project: Path, eil: Callable) -> None:
    write_ready_functional(project, eil)
    outcomes = ["understood", "coached", "skipped", "revealed", "understood"]
    for level, outcome in zip(LEVELS, outcomes, strict=True):
        assert record(eil, level, outcome).code == 0
    approved = eil(
        [
            "approve",
            "functional",
            "--by",
            "Ada Dev",
            "--attestation",
            "Yes, this is the behaviour we require.",
            "--json",
        ]
    )
    assert approved.code == 0, approved.stdout
    overview = (feature(project) / "s00-README.md").read_text(encoding="utf-8")
    assert "understood 2 · coached 1 · revealed 1 · skipped 1" in overview


def test_b18_a_configured_confirmer_can_override_the_criterion_and_it_stays_visible(
    project: Path, eil: Callable
) -> None:
    write_ready_functional(project, eil)
    overridden = eil(
        [
            "override",
            "functional",
            "--criterion",
            "FUN-G16",
            "--by",
            "Ada Dev",
            "--reason",
            "trial run without the check",
            "--json",
        ]
    )
    assert overridden.code == 0, overridden.stdout
    eil(
        [
            "check",
            "--stage",
            "functional",
            "--judgments",
            str(write_judgments(project, "functional", FUN_JUDGED)),
            "--json",
        ]
    )
    approved = eil(["approve", "functional", "--by", "Ada Dev", "--attestation", "Yes, I confirm.", "--json"])
    assert approved.code == 0, approved.stdout
    assert Package(feature(project)).state("functional").state == "approved"
    overview = (feature(project) / "s00-README.md").read_text(encoding="utf-8")
    assert "OVR-" in overview and "FUN-G16" in overview


def test_b18_the_record_survives_regeneration_of_the_overview_without_changing_the_document(
    project: Path, eil: Callable
) -> None:
    write_ready_functional(project, eil)
    record(eil, "recognise", "understood")
    before = eil(["fingerprint", f"{FEATURE}/s02-functional-spec.md"]).stdout
    eil(["sync", "--json"])
    eil(["status", "--json"])
    assert eil(["fingerprint", f"{FEATURE}/s02-functional-spec.md"]).stdout == before
    assert (
        json.loads(json.dumps(eil(["status", "--json"]).json["comprehension"]))["functional"]["state"]
        == "incomplete"
    )
