"""B-12 and the verification and completion half of B-17 (task T110): evidence, then a person's decision,
driving the installed helper as the commands do. FR-059 to FR-065, FR-084, FR-086, SC-014."""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path

import pytest
from eil.package import Package

from tests.helpers.package import (
    CURRENCY_TARGETS,
    ai_spec_doc,
    completion_doc,
    evidence_row,
    plan_doc,
    tasks_doc,
    verification_doc,
)
from tests.scenario.conftest import write_judgments
from tests.scenario.test_b04_b14_b16_functional import feature
from tests.scenario.test_b06_b08_b17_aispec_aliases import read, start_ai_spec, write

pytestmark = pytest.mark.scenario

TARGETS = ["REQ-001", "FR-001", "NFR-001", "ART-001", "ART-002", "ART-004", "ART-005", "ART-006", "ART-007"]
CURRENCY = "\n".join(f"- {a}: current" for a in CURRENCY_TARGETS if a != "ART-003")
YES = "Yes, I reviewed the evidence and the story is done."


def rows(**changes: dict) -> list[str]:
    return [evidence_row(i, t, **changes.get(t, {})) for i, t in enumerate(TARGETS, 1)]


def through_tasks(project: Path, eil: Callable) -> None:
    start_ai_spec(project, eil)
    write(project, "s04-ai-spec.md", ai_spec_doc())
    assert eil(["check", "--stage", "ai-spec", "--json"]).json["ok"]
    assert eil(["stage-init", "plan", "--json"]).code == 0
    write(project, "s05-plan.md", plan_doc())
    judged = write_judgments(project, "plan", ["PLN-G02"])
    assert eil(["check", "--stage", "plan", "--judgments", str(judged), "--json"]).json["ok"]
    assert eil(["stage-init", "tasks", "--json"]).code == 0
    write(project, "s06-tasks.md", tasks_doc())
    judged = write_judgments(project, "tasks", ["TSK-G03"])
    assert eil(["check", "--stage", "tasks", "--judgments", str(judged), "--json"]).json["ok"]


def start_verification(project: Path, eil: Callable, evidence: list[str] | None = None) -> None:
    through_tasks(project, eil)
    created = eil(["stage-init", "verification", "--json"])
    assert created.code == 0, created.stdout + created.stderr
    write(project, "s07-verification.md", verification_doc(evidence if evidence is not None else rows()))
    eil(["check", "--stage", "verification", "--json"])


def start_completion(project: Path, eil: Callable, **sections: object) -> None:
    created = eil(["stage-init", "completion", "--json"])
    assert created.code == 0, created.stdout + created.stderr
    write(project, "s08-completion.md", completion_doc({"Diagram Currency": CURRENCY, **sections}))  # type: ignore[arg-type]


def unmet(result) -> dict[str, str]:
    return {c["id"]: c["reason"] for c in result.json["criteria"] if c["status"] == "not-met"}


def test_b12_verification_cannot_start_before_tasks_exist(project: Path, eil: Callable) -> None:
    start_ai_spec(project, eil)
    result = eil(["stage-init", "verification", "--json"])
    assert result.code == 1 and result.refusal_codes == ["tasks-missing"]
    assert not (feature(project) / "s07-verification.md").exists()


def test_b12_the_verification_document_starts_from_the_template_and_is_never_approved(
    project: Path, eil: Callable
) -> None:
    through_tasks(project, eil)
    assert eil(["stage-init", "verification", "--json"]).code == 0
    text = read(project, "s07-verification.md")
    for heading in ("Automated Evidence", "Manual Evidence", "Exceptions", "Open Tasks"):
        assert f"## {heading}\n" in text
    assert not (feature(project) / "verification.md").exists(), "no alias for a stage Spec Kit does not read"
    assert not eil(["check", "--stage", "verification", "--json"]).json["ok"]
    approve = eil(["approve", "verification", "--by", "Ada Dev", "--attestation", "yes", "--json"])
    assert approve.refusal_codes == ["not-approvable"]


def test_b12_a_row_for_every_item_with_evidence_and_open_tasks_listed_meets_the_gate(
    project: Path, eil: Callable
) -> None:
    start_verification(project, eil)
    result = eil(["check", "--stage", "verification", "--json"])
    assert result.json["ok"], unmet(result)
    status = eil(["status", "--json"]).json
    assert status["stages"]["verification"]["state"] == "in-review"
    assert status["current_stage"] == "completion"


def test_b12_completion_is_refused_while_a_requirement_is_unverified(project: Path, eil: Callable) -> None:
    start_verification(project, eil, rows(**{"REQ-001": {"status": "unverified"}}))
    start_completion(project, eil)
    refused = eil(["approve", "completion", "--by", "Ada Dev", "--attestation", YES, "--json"])
    assert refused.code == 1 and refused.refusal_codes == ["unverified-requirement"]
    assert "REQ-001 is unverified" in refused.json["refusals"][0]["message"]
    assert Package(feature(project)).state("completion").state != "approved"


def test_b12_an_exception_naming_who_and_why_lets_completion_be_approved_by_the_persons_own_words(
    project: Path, eil: Callable
) -> None:
    exception = {"status": "excepted", "accepted_by": "Ada Dev", "reason": "verified in the next release"}
    start_verification(project, eil, rows(**{"REQ-001": exception}))
    start_completion(project, eil)
    assert eil(["check", "--stage", "completion", "--json"]).json["ok"]
    unattested = eil(["approve", "completion", "--by", "Ada Dev", "--attestation", " ", "--json"])
    assert unattested.refusal_codes == ["attestation-required"]
    approved = eil(["approve", "completion", "--by", "Ada Dev", "--attestation", YES, "--json"])
    assert approved.code == 0, approved.stdout
    status = eil(["status", "--json"]).json
    assert status["current_stage"] is None and status["stages"]["completion"]["approval"]["by"] == "Ada Dev"
    overview = read(project, "s00-README.md")
    assert "complete" in overview.lower() and "Ada Dev" in overview


def test_b12_an_unverified_artefact_is_refused_and_a_deviation_needs_who_and_why(
    project: Path, eil: Callable
) -> None:
    start_verification(project, eil, rows(**{"ART-007": {"status": "unverified"}}))
    start_completion(project, eil)
    refused = eil(["approve", "completion", "--by", "Ada Dev", "--attestation", YES, "--json"])
    assert refused.refusal_codes == ["unverified-artifact"]
    write(project, "s07-verification.md", verification_doc(rows()))
    write(
        project,
        "s08-completion.md",
        completion_doc({"Diagram Currency": CURRENCY.replace("ART-007: current", "ART-007: deviation")}),
    )
    gate = eil(["check", "--stage", "completion", "--json"])
    assert "ART-007 is a deviation but names no 'accepted by'" in unmet(gate)["CMP-G05"]
    full = CURRENCY.replace(
        "ART-007: current", "ART-007: deviation, accepted by Ada Dev, because the index was renamed"
    )
    write(
        project,
        "s08-completion.md",
        completion_doc({"Diagram Currency": full, "Accepted Deviations": "ART-007: the index was renamed."}),
    )
    assert eil(["check", "--stage", "completion", "--json"]).json["ok"]
    assert eil(["approve", "completion", "--by", "Ada Dev", "--attestation", YES, "--json"]).code == 0


def test_b12_completion_is_refused_without_the_verification_document(project: Path, eil: Callable) -> None:
    through_tasks(project, eil)
    refused = eil(["stage-init", "completion", "--json"])
    assert refused.code == 1 and refused.refusal_codes == ["verification-missing"]


def test_b12_a_named_override_lets_completion_proceed_over_an_unverified_requirement(
    project: Path, eil: Callable
) -> None:
    start_verification(project, eil, rows(**{"REQ-001": {"status": "unverified"}}))
    start_completion(project, eil)
    overridden = eil(
        ["override", "completion", "--criterion", "CMP-G03", "--by", "Ada Dev", "--reason", "spike", "--json"]
    )
    assert overridden.code == 0, overridden.stdout
    assert eil(["check", "--stage", "completion", "--json"]).json["ok"]
    approved = eil(["approve", "completion", "--by", "Ada Dev", "--attestation", YES, "--json"])
    assert approved.code == 0 and approved.json["approval"]["overrides_used"] == ["OVR-001"]
    assert "CMP-G03" in read(project, "s00-README.md")


def test_b12_the_ai_cannot_approve_completion(project: Path, eil: Callable) -> None:
    start_verification(project, eil)
    start_completion(project, eil)
    assert (
        "ai-approval"
        in eil(["approve", "completion", "--by", "Claude", "--attestation", YES, "--json"]).refusal_codes
    )


def test_b17_every_artefact_is_listed_with_kind_stage_and_state_and_the_overview_holds_links_only(
    project: Path, eil: Callable
) -> None:
    start_verification(project, eil)
    listed = eil(["artifact", "list", "--json"]).json["artifacts"]
    assert {a["id"] for a in listed} == {t for t in TARGETS if t.startswith("ART")}
    assert all(a["kind"] and a["stage"] and a["state"] for a in listed)
    overview = read(project, "s00-README.md")
    assert "ART-004" in overview and "C4Container" not in overview and "Person(" not in overview
    assert os.path.exists(feature(project) / "s07-verification.md")


def test_b12_trace_reports_a_requirement_without_evidence(project: Path, eil: Callable) -> None:
    start_verification(project, eil)
    report = eil(["trace", "--report", "--json"]).json["requirements"][0]
    assert report["evidence"] and "EVD-001" in report["evidence"]
