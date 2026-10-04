"""Challenge severity (task T066; FR-029, FR-030, FR-048, determinism 31, contracts/cli.md)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from eil import records
from eil.gates import check_stage
from eil.identity import Config
from eil.package import Package
from eil.results import EilExit

from tests.helpers.package import Story, requirements_doc

NOW = "2026-09-25T10:14:03Z"
JUDGED = ["REQ-G01", "REQ-G11", "REQ-G12", "REQ-G13"]
CONFIG = Config(
    default_developer="Ada Dev",
    approvers={"requirements": ["Ada Dev", "Grace Lead"]},
    abbreviation_authorisers=[],
)
YES = "Yes, this is the problem we intend to solve."


@pytest.fixture(autouse=True)
def fixed_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(records, "utc_now", lambda: NOW)


@pytest.fixture
def package(story_dir: Story) -> Package:
    story_dir.write("requirements", requirements_doc())
    return Package(story_dir.root)


def add(package: Package, text: str, severity: str | None = "medium", by: str | None = None) -> dict:
    return records.add_challenge(package, "requirements", "REQ-001", text, by, severity)


def codes(exc: pytest.ExceptionInfo[EilExit]) -> list[str]:
    return [r["code"] for r in exc.value.payload["refusals"]]


def stored(package: Package) -> dict[str, dict]:
    found = [r.obj for r in package.doc("requirements").records() if r.kind == "challenge" and r.obj]
    return {c["id"]: c for c in found}


def approve_after_checking(package: Package, tmp: Path) -> dict:
    path = tmp / "judgments.json"
    body = {
        "stage": "requirements",
        "judgments": [{"id": c, "status": "met", "reason": "ok"} for c in JUDGED],
    }
    path.write_text(json.dumps(body))
    check_stage(package, "requirements", judgments_path=path)
    return records.approve(package, CONFIG, "requirements", "Ada Dev", YES)


def severity(package: Package, cid: str, to: str, by: str) -> dict:
    return records.set_challenge_severity(package, CONFIG, cid, to, by)


# ---- raising: the --severity rule


def test_the_ai_must_rate_a_challenge_it_raises(package: Package) -> None:
    with pytest.raises(EilExit) as exc:
        records.add_challenge(package, "requirements", "REQ-001", "A gap?", None, None)
    assert exc.value.code == 2
    with pytest.raises(EilExit) as named:
        records.add_challenge(package, "requirements", "REQ-001", "A gap?", "ai", None)
    assert named.value.code == 2
    assert stored(package) == {}


def test_a_person_may_omit_severity_and_it_reads_as_medium(package: Package) -> None:
    result = records.add_challenge(package, "requirements", "REQ-001", "A gap?", "Grace Lead", None)
    assert "severity" not in result["challenge"]
    assert records.challenge_severity(result["challenge"]) == "medium"


def test_a_given_severity_is_recorded_and_an_unknown_one_is_a_usage_error(package: Package) -> None:
    assert add(package, "A gap?", "low")["challenge"]["severity"] == "low"
    with pytest.raises(EilExit) as exc:
        add(package, "Another gap?", "urgent")
    assert exc.value.code == 2


def test_a_legacy_record_without_severity_counts_as_medium() -> None:
    assert records.challenge_severity({"id": "CH-001", "status": "open"}) == "medium"
    assert records.challenge_severity({"severity": "low"}) == "low"


# ---- approval: only high and medium block


def test_low_challenges_do_not_block_and_are_recorded_as_outstanding(
    package: Package, tmp_path: Path
) -> None:
    add(package, "First minor point?", "low")
    add(package, "Second minor point on wording?", "low")
    result = approve_after_checking(package, tmp_path)
    assert result["approval"]["outstanding"] == ["CH-001", "CH-002"]
    assert package.record("requirements", "approval")["outstanding"] == ["CH-001", "CH-002"]


def test_no_outstanding_key_when_there_are_none(package: Package, tmp_path: Path) -> None:
    assert "outstanding" not in approve_after_checking(package, tmp_path)["approval"]


@pytest.mark.parametrize("level", ["medium", "high"])
def test_a_medium_or_high_challenge_refuses_and_a_low_one_beside_it_is_not_named(
    package: Package, tmp_path: Path, level: str
) -> None:
    add(package, "A low point?", "low")
    add(package, "A weightier point?", level)
    with pytest.raises(EilExit) as exc:
        approve_after_checking(package, tmp_path)
    found = [r for r in exc.value.payload["refusals"] if r["code"] == "open-challenge"]
    assert found and "CH-002" in found[0]["message"] and "CH-001" not in found[0]["message"]


def test_an_unrated_challenge_blocks_like_medium(package: Package, tmp_path: Path) -> None:
    records.add_challenge(package, "requirements", "REQ-001", "A gap?", "Grace Lead", None)
    with pytest.raises(EilExit) as exc:
        approve_after_checking(package, tmp_path)
    assert "open-challenge" in codes(exc)


# ---- changing severity: anyone raises, only a confirmer lowers (FR-048)


def test_anyone_may_raise_and_it_is_recorded_with_their_name(package: Package) -> None:
    add(package, "A minor point?", "low")
    result = severity(package, "CH-001", "high", "Sam QA")
    assert result["challenge"]["severity"] == "high"
    assert stored(package)["CH-001"]["severity_history"] == [
        {"from": "low", "to": "high", "by": "Sam QA", "at": NOW}
    ]


def test_a_non_confirmer_cannot_lower(package: Package) -> None:
    add(package, "A point?", "high")
    with pytest.raises(EilExit) as exc:
        severity(package, "CH-001", "low", "Sam QA")
    assert codes(exc) == ["not-a-confirmer"]
    assert stored(package)["CH-001"]["severity"] == "high"


def test_a_confirmer_may_lower_and_history_accumulates(package: Package) -> None:
    add(package, "A point?", "high")
    severity(package, "CH-001", "low", "Grace Lead")
    severity(package, "CH-001", "medium", "Sam QA")
    history = stored(package)["CH-001"]["severity_history"]
    assert [(h["from"], h["to"], h["by"]) for h in history] == [
        ("high", "low", "Grace Lead"),
        ("low", "medium", "Sam QA"),
    ]


def test_the_ai_cannot_lower(package: Package) -> None:
    add(package, "A point?", "high")
    with pytest.raises(EilExit) as exc:
        severity(package, "CH-001", "low", "ai")
    assert codes(exc) == ["ai-approval"]


def test_an_unknown_challenge_and_an_unchanged_severity(package: Package) -> None:
    add(package, "A point?", "high")
    with pytest.raises(EilExit) as exc:
        severity(package, "CH-009", "low", "Grace Lead")
    assert codes(exc) == ["unknown-item"]
    result = severity(package, "CH-001", "high", "Sam QA")
    assert "severity_history" not in result["challenge"]


def test_a_legacy_challenge_raised_reads_from_medium(package: Package) -> None:
    records.add_challenge(package, "requirements", "REQ-001", "A gap?", "Grace Lead", None)
    severity(package, "CH-001", "high", "Sam QA")
    assert stored(package)["CH-001"]["severity_history"][0]["from"] == "medium"


# ---- duplicates


def test_a_duplicate_of_an_open_challenge_names_the_existing_one(package: Package) -> None:
    add(package, "Is the scope complete?", "low")
    with pytest.raises(EilExit) as exc:
        add(package, "is the scope complete", "high")
    refusal = exc.value.payload["refusals"][0]
    assert refusal["existing"] == "CH-001" and "still open" in refusal["message"]
    assert len(stored(package)) == 1
