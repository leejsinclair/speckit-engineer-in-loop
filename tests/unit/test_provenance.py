"""Human-decided provenance and ``eil amend`` (D-24, D-25)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from eil import provenance, records
from eil.gates import check_stage
from eil.identity import Config
from eil.package import Package
from eil.provenance import amend, decided_eligible
from eil.results import EilExit

from tests.helpers.package import Story, record_block, requirements_doc

JUDGED = ["REQ-G01", "REQ-G11", "REQ-G12", "REQ-G13"]
NOW = "2026-09-27T09:00:00Z"


@pytest.fixture(autouse=True)
def fixed_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(records, "utc_now", lambda: NOW)
    monkeypatch.setattr(provenance, "utc_now", lambda: NOW)


@pytest.fixture
def config() -> Config:
    return Config(
        default_developer="Ada Dev", approvers={"requirements": ["Ada Dev"]}, abbreviation_authorisers=[]
    )


def judgments(tmp: Path) -> Path:
    path = tmp / "judgments.json"
    body = {
        "stage": "requirements",
        "judgments": [{"id": c, "status": "met", "reason": "fine"} for c in JUDGED],
    }
    path.write_text(json.dumps(body))
    return path


def ready_and_approved(story: Story, tmp: Path, config: Config) -> Package:
    """A Requirements document, approved once, gate met, verdicts recorded."""
    story.write("requirements", requirements_doc())
    package = Package(story.root)
    check_stage(package, "requirements", judgments_path=judgments(tmp))
    records.approve(package, config, "requirements", by="Ada Dev", attestation="Yes, this is the problem.")
    return package


def refusals(exc: pytest.ExceptionInfo[EilExit]) -> list[str]:
    return [r["code"] for r in exc.value.payload["refusals"]]


CHALLENGE_ACCEPTED = {
    "id": "CH-004",
    "stage": "requirements",
    "raised_by": "ai",
    "raised_at": "2026-09-26T10:00:00Z",
    "target": "REQ-001",
    "text": "Should retention history be kept?",
    "status": "closed",
    "responder": "Ada Dev",
    "response": "accepted",
    "at": "2026-09-26T10:05:00Z",
}


# ---- decided_eligible


def test_a_challenge_id_that_does_not_exist_is_not_eligible(story_dir: Story) -> None:
    package = Package(story_dir.root)
    assert decided_eligible(package, "CH-999") == "CH-999 is not a challenge of this story"


def test_an_open_challenge_is_not_eligible(story_dir: Story) -> None:
    story_dir.write(
        "requirements",
        requirements_doc(
            extra=record_block("challenge", {**CHALLENGE_ACCEPTED, "status": "open", "response": None})
        ),
    )
    package = Package(story_dir.root)
    problem = decided_eligible(package, "CH-004")
    assert problem and "not accepted" in problem


def test_an_accepted_challenge_is_eligible(story_dir: Story) -> None:
    story_dir.write("requirements", requirements_doc(extra=record_block("challenge", CHALLENGE_ACCEPTED)))
    package = Package(story_dir.root)
    assert decided_eligible(package, "CH-004") is None


def test_an_open_question_not_yet_resolved_is_not_eligible(story_dir: Story) -> None:
    story_dir.write(
        "requirements", requirements_doc(sections={"Open Questions": "**OQ-001**: Keep? (status: open)"})
    )
    package = Package(story_dir.root)
    problem = decided_eligible(package, "OQ-001")
    assert problem and "not resolved or accepted" in problem


def test_a_resolved_open_question_is_eligible(story_dir: Story) -> None:
    story_dir.write("requirements", requirements_doc())  # OQ-001 is (status: resolved) by default
    package = Package(story_dir.root)
    assert decided_eligible(package, "OQ-001") is None


def test_an_ais_id_is_eligible_once_it_exists(story_dir: Story) -> None:
    story_dir.write("ai-spec", "**AIS-007**: carried answer (traces: FR-001)\n")
    package = Package(story_dir.root)
    assert decided_eligible(package, "AIS-007") is None


def test_an_id_shaped_wrong_is_never_eligible(story_dir: Story) -> None:
    package = Package(story_dir.root)
    assert decided_eligible(package, "FR-004") == "'FR-004' is not a CH-###, OQ-### or AIS-### id"


# ---- decided_findings, wired into the gate


def test_check_stage_reports_an_invalid_decided_citation(story_dir: Story, tmp_path: Path) -> None:
    story_dir.write(
        "requirements",
        requirements_doc(
            sections={
                "Desired Outcome": "**REQ-001**: detects duplicates (decided: CH-999)",
            }
        ),
    )
    package = Package(story_dir.root)
    result = check_stage(package, "requirements", judgments_path=judgments(tmp_path))
    codes = [f.code for f in result.findings]
    assert "decided-source-invalid" in codes


def test_check_stage_accepts_a_valid_decided_citation(story_dir: Story, tmp_path: Path) -> None:
    story_dir.write(
        "requirements",
        requirements_doc(
            sections={"Desired Outcome": "**REQ-001**: detects duplicates (decided: CH-004)"},
            extra=record_block("challenge", CHALLENGE_ACCEPTED),
        ),
    )
    package = Package(story_dir.root)
    result = check_stage(package, "requirements", judgments_path=judgments(tmp_path))
    codes = [f.code for f in result.findings]
    assert "decided-source-invalid" not in codes


# ---- eil amend


def test_amend_refuses_a_stage_that_was_never_approved(story_dir: Story) -> None:
    story_dir.write("requirements", requirements_doc())
    package = Package(story_dir.root)
    with pytest.raises(EilExit) as exc:
        amend(package, Config(), "requirements", ["CH-004"], "Ada Dev", "Yes.")
    assert refusals(exc) == ["not-amendable"]


def test_amend_refuses_a_stage_that_is_still_approved(
    story_dir: Story, tmp_path: Path, config: Config
) -> None:
    package = ready_and_approved(story_dir, tmp_path, config)
    with pytest.raises(EilExit) as exc:
        amend(package, config, "requirements", ["CH-004"], "Ada Dev", "Yes.")
    assert refusals(exc) == ["not-amendable"]


def test_amend_refuses_a_changed_item_with_no_decided_clause(
    story_dir: Story, tmp_path: Path, config: Config
) -> None:
    package = ready_and_approved(story_dir, tmp_path, config)
    text = package.read("requirements")
    edited = text.replace(
        "**REQ-001**: The system detects duplicate customers on import.",
        "**REQ-001**: The system detects duplicate customers on import, and keeps history.",
    )
    story_dir.write("requirements", edited)
    package2 = Package(story_dir.root)
    assert package2.state("requirements").state == "needs-re-review"
    with pytest.raises(EilExit) as exc:
        amend(package2, config, "requirements", ["CH-004"], "Ada Dev", "Yes.")
    assert "amend-not-covered" in refusals(exc)


def test_amend_refuses_a_change_outside_any_item(story_dir: Story, tmp_path: Path, config: Config) -> None:
    package = ready_and_approved(story_dir, tmp_path, config)
    text = package.read("requirements")
    edited = text.replace(
        "Imports create duplicate customers.", "Imports create many duplicate customers."
    ).replace("## Challenges\n", "## Challenges\n\n" + record_block("challenge", CHALLENGE_ACCEPTED))
    story_dir.write("requirements", edited)
    package2 = Package(story_dir.root)
    with pytest.raises(EilExit) as exc:
        amend(package2, config, "requirements", ["CH-004"], "Ada Dev", "Yes.")
    assert refusals(exc) == ["amend-not-covered"]


def test_amend_succeeds_when_every_change_is_covered(
    story_dir: Story, tmp_path: Path, config: Config
) -> None:
    package = ready_and_approved(story_dir, tmp_path, config)
    text = package.read("requirements")
    edited = text.replace(
        "**REQ-001**: The system detects duplicate customers on import.",
        "**REQ-001**: The system detects duplicate customers on import, and keeps history. (decided: CH-004)",
    ).replace("## Challenges\n", "## Challenges\n\n" + record_block("challenge", CHALLENGE_ACCEPTED))
    story_dir.write("requirements", edited)
    package2 = Package(story_dir.root)
    assert package2.state("requirements").state == "needs-re-review"

    result = amend(package2, config, "requirements", ["CH-004"], "Ada Dev", "Yes, that is right.")

    assert result["ok"] is True
    record = result["approval"]
    assert record["amended"] is True
    assert record["amends"] == ["CH-004"]
    assert record["by"] == "Ada Dev"
    assert record["at"] == NOW
    package3 = Package(story_dir.root)
    assert package3.state("requirements").state == "approved"


def test_amend_refuses_while_an_ai_draft_tag_remains(
    story_dir: Story, tmp_path: Path, config: Config
) -> None:
    package = ready_and_approved(story_dir, tmp_path, config)
    text = package.read("requirements")
    edited = text.replace(
        "**REQ-001**: The system detects duplicate customers on import.",
        "**REQ-001**: The system detects duplicate customers on import, and more. (decided: CH-004) [ai-draft]",
    ).replace("## Challenges\n", "## Challenges\n\n" + record_block("challenge", CHALLENGE_ACCEPTED))
    story_dir.write("requirements", edited)
    package2 = Package(story_dir.root)
    with pytest.raises(EilExit) as exc:
        amend(package2, config, "requirements", ["CH-004"], "Ada Dev", "Yes.")
    assert "unreviewed-ai-content" in refusals(exc)


def test_amend_refuses_an_unaccepted_from_id(story_dir: Story, tmp_path: Path, config: Config) -> None:
    package = ready_and_approved(story_dir, tmp_path, config)
    text = package.read("requirements")
    edited = text.replace(
        "**REQ-001**: The system detects duplicate customers on import.",
        "**REQ-001**: The system detects duplicate customers on import, and keeps history. (decided: CH-004)",
    ).replace(
        "## Challenges\n",
        "## Challenges\n\n"
        + record_block("challenge", {**CHALLENGE_ACCEPTED, "status": "open", "response": None}),
    )
    story_dir.write("requirements", edited)
    package2 = Package(story_dir.root)
    with pytest.raises(EilExit) as exc:
        amend(package2, config, "requirements", ["CH-004"], "Ada Dev", "Yes.")
    assert refusals(exc) == ["unknown-item"]


def test_amend_requires_at_least_one_from_id(story_dir: Story, tmp_path: Path, config: Config) -> None:
    package = ready_and_approved(story_dir, tmp_path, config)
    with pytest.raises(EilExit) as exc:
        amend(package, config, "requirements", [], "Ada Dev", "Yes.")
    assert exc.value.code == 2


def test_amend_never_accepts_the_ai_as_the_confirmer(
    story_dir: Story, tmp_path: Path, config: Config
) -> None:
    package = ready_and_approved(story_dir, tmp_path, config)
    text = package.read("requirements")
    edited = text.replace(
        "**REQ-001**: The system detects duplicate customers on import.",
        "**REQ-001**: The system detects duplicate customers on import, and keeps history. (decided: CH-004)",
    ).replace("## Challenges\n", "## Challenges\n\n" + record_block("challenge", CHALLENGE_ACCEPTED))
    story_dir.write("requirements", edited)
    package2 = Package(story_dir.root)
    with pytest.raises(EilExit) as exc:
        amend(package2, config, "requirements", ["CH-004"], "the AI", "Yes.")
    assert "ai-approval" in refusals(exc)
