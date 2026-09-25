"""B-13 (task T126): governance boundaries. Who may approve, who may abbreviate, and what an
abbreviation does and does not change. FR-013, FR-040, FR-045; removal is in
tests/contract/test_removal_and_coexistence.py."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from tests.helpers.package import requirements_doc
from tests.scenario.conftest import write_judgments
from tests.scenario.test_b04_b14_b16_functional import ACCEPTED, FEATURE, REQ_JUDGED, feature

pytestmark = pytest.mark.scenario

YES = "Yes, this is the problem we intend to solve."


def config(project: Path, name: str, body: str) -> None:
    (project / ".specify" / "extensions" / "eil" / name).write_text(body, encoding="utf-8")


def ready_requirements(project: Path, eil: Callable) -> None:
    started = eil(
        ["start", "--title", "Detect duplicates", "--owner", "Ada Dev", "--feature-dir", FEATURE, "--json"]
    )
    assert started.code == 0, started.stdout
    (feature(project) / "s01-requirements.md").write_text(
        requirements_doc({"Open Questions": ACCEPTED}), encoding="utf-8", newline="\n"
    )
    judged = write_judgments(project, "requirements", REQ_JUDGED)
    assert eil(["check", "--stage", "requirements", "--judgments", str(judged), "--json"]).json["ok"]


def test_b13_a_configured_approver_is_enforced_per_stage(project: Path, eil: Callable) -> None:
    config(project, "eil-config.yml", "approvers:\n  requirements: [Grace Lead]\n")
    ready_requirements(project, eil)
    refused = eil(["approve", "requirements", "--by", "Ada Dev", "--attestation", YES, "--json"])
    assert refused.code == 1 and refused.refusal_codes == ["not-a-confirmer"]
    assert "Grace Lead" in refused.json["refusals"][0]["fix"]
    approved = eil(["approve", "requirements", "--by", "Grace Lead", "--attestation", YES, "--json"])
    assert approved.code == 0, approved.stdout


def test_b13_the_override_authority_is_the_same_list(project: Path, eil: Callable) -> None:
    config(project, "eil-config.yml", "approvers:\n  requirements: [Grace Lead]\n")
    ready_requirements(project, eil)
    args = ["override", "requirements", "--criterion", "REQ-G01", "--reason", "spike", "--json"]
    assert eil([*args[:4], "--by", "Ada Dev", *args[4:]]).refusal_codes == ["not-a-confirmer"]
    assert eil([*args[:4], "--by", "Grace Lead", *args[4:]]).code == 0


def test_b13_a_local_file_overrides_the_shared_one_on_this_machine(project: Path, eil: Callable) -> None:
    config(project, "eil-config.yml", "approvers:\n  requirements: [Grace Lead]\n")
    config(project, "local-config.yml", "approvers:\n  requirements: [Ada Dev]\n")
    ready_requirements(project, eil)
    assert eil(["approve", "requirements", "--by", "Ada Dev", "--attestation", YES, "--json"]).code == 0


def test_b13_a_malformed_configuration_is_a_usage_error_never_a_silent_default(
    project: Path, eil: Callable
) -> None:
    config(project, "eil-config.yml", "approvers: [broken\n")
    ready_requirements_started = eil(
        ["start", "--title", "x", "--owner", "Ada Dev", "--feature-dir", FEATURE, "--json"]
    )
    assert ready_requirements_started.code == 2


def test_b13_an_abbreviation_is_recorded_shown_and_never_a_skip(project: Path, eil: Callable) -> None:
    ready_requirements(project, eil)
    skipped = eil(["abbreviate", "technical", "--by", "Ada Dev", "--reason", "trivial", "--json"])
    assert skipped.code == 1 and skipped.refusal_codes == ["cannot-skip"]
    no_reason = eil(["abbreviate", "requirements", "--by", "Ada Dev", "--reason", " ", "--json"])
    assert no_reason.refusal_codes == ["reason-required"]
    stranger = eil(["abbreviate", "requirements", "--by", "Mallory", "--reason", "trivial", "--json"])
    assert stranger.refusal_codes == ["not-an-authoriser"]
    done = eil(["abbreviate", "requirements", "--by", "Ada Dev", "--reason", "a one-line fix", "--json"])
    assert done.code == 0, done.stdout
    status = eil(["status", "--json"]).json
    assert status["stages"]["requirements"]["abbreviated"] is True
    overview = (feature(project) / "s00-README.md").read_text(encoding="utf-8")
    assert "requirements (authorised by Ada Dev)" in overview
    trace = eil(["trace", "--report", "--json"]).json
    assert trace["abbreviated"] == [{"stage": "requirements", "by": "Ada Dev"}]


def test_b13_an_abbreviated_stage_still_has_to_pass_its_gate_and_be_approved(
    project: Path, eil: Callable
) -> None:
    ready_requirements(project, eil)
    eil(["abbreviate", "requirements", "--by", "Ada Dev", "--reason", "a one-line fix", "--json"])
    judged = write_judgments(project, "requirements", REQ_JUDGED)
    checked = eil(["check", "--stage", "requirements", "--judgments", str(judged), "--json"])
    assert checked.json["ok"] is True
    text = (feature(project) / "s01-requirements.md").read_text(encoding="utf-8")
    (feature(project) / "s01-requirements.md").write_text(
        text.replace("## Success Criteria\n", "## Success Criteria\n\n"), encoding="utf-8"
    )
    assert eil(["approve", "requirements", "--by", "Ada Dev", "--attestation", YES, "--json"]).code == 0
    assert eil(["status", "--json"]).json["stages"]["requirements"]["abbreviated"] is True
