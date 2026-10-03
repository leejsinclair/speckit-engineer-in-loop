"""Approvals and overrides (task T033; FR-010 to FR-013, FR-045, FR-066, determinism 3, 4, 5)."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from eil import records
from eil.artifacts import scan_document
from eil.gates import check_stage
from eil.identity import Config
from eil.package import Package
from eil.records import approve, override
from eil.results import EilExit
from eil.trace import item_hash, parse_document

from tests.helpers.package import Story, record_block, requirements_doc

JUDGED = ["REQ-G01", "REQ-G11", "REQ-G12", "REQ-G13"]
NOW = "2026-09-25T10:14:03Z"


@pytest.fixture(autouse=True)
def fixed_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(records, "utc_now", lambda: NOW)


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


def ready(story: Story, tmp: Path, text: str | None = None) -> Package:
    """A Requirements document whose gate is met, with the AI's verdicts recorded."""
    story.write("requirements", text if text is not None else requirements_doc())
    package = Package(story.root)
    check_stage(package, "requirements", judgments_path=judgments(tmp))
    return package


def approve_ok(package: Package, config: Config, **overrides: object) -> dict:
    args = {"by": "Ada Dev", "attestation": "Yes, this is the problem we intend to solve."}
    return approve(package, config, "requirements", **{**args, **overrides})  # type: ignore[arg-type]


def refusals(exc: pytest.ExceptionInfo[EilExit]) -> list[str]:
    return [r["code"] for r in exc.value.payload["refusals"]]


# ---- a successful approval


def test_a_met_gate_and_a_configured_confirmer_records_the_approval(
    story_dir: Story, tmp_path: Path, config: Config
) -> None:
    package = ready(story_dir, tmp_path)
    fingerprint = package.fingerprint("requirements")
    result = approve_ok(package, config)
    assert result["ok"] is True
    record = package.record("requirements", "approval")
    assert record["stage"] == "requirements"
    assert record["by"] == "Ada Dev"
    assert record["at"] == NOW
    assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", record["at"])
    assert record["fingerprint"] == fingerprint
    assert record["attestation"] == "Yes, this is the problem we intend to solve."
    assert record["reached"] == "first"
    assert record["upstream"] == {}
    assert record["overrides_used"] == []
    assert "played_back_to" not in record and "comprehension" not in record


def test_the_approval_covers_the_current_content_and_the_stage_becomes_approved(
    story_dir: Story, tmp_path: Path, config: Config
) -> None:
    package = ready(story_dir, tmp_path)
    approve_ok(package, config)
    assert package.state("requirements").state == "approved"
    assert (
        package.fingerprint("requirements")
        == package.record("requirements", "approval")["fingerprint"]
    )


def test_the_record_carries_each_items_hash_for_impact_analysis(
    story_dir: Story, tmp_path: Path, config: Config
) -> None:
    package = ready(story_dir, tmp_path)
    approve_ok(package, config)
    record = package.record("requirements", "approval")
    doc = package.doc("requirements")
    parsed = parse_document(doc)
    scan_document(doc, "requirements", parsed)  # attaches the diagram, which is part of an artifact's hash
    assert set(record["items"]) == {"REQ-001", "UC-001", "OQ-001", "ART-001"}
    for item in parsed.items:
        assert record["items"][item.id] == item_hash(item)


def test_a_played_back_note_is_recorded_when_given(story_dir: Story, tmp_path: Path, config: Config) -> None:
    package = ready(story_dir, tmp_path)
    approve_ok(package, config, played_back_to="Sam (business), Priya (QA)")
    assert (
        package.record("requirements", "approval")["played_back_to"]
        == "Sam (business), Priya (QA)"
    )


def test_one_confirmation_is_enough(story_dir: Story, tmp_path: Path) -> None:
    both = Config(
        default_developer=None,
        approvers={"requirements": ["Ada Dev", "Sam Lee"]},
        abbreviation_authorisers=[],
    )
    package = ready(story_dir, tmp_path)
    approve_ok(package, both, by="Sam Lee")
    assert package.state("requirements").state == "approved"


def test_the_developer_may_approve_when_no_approvers_are_configured(story_dir: Story, tmp_path: Path) -> None:
    open_config = Config(default_developer="Ada Dev", approvers={}, abbreviation_authorisers=[])
    package = ready(story_dir, tmp_path)
    approve_ok(package, open_config)
    assert package.state("requirements").state == "approved"


def test_approval_writes_only_the_approval_region(story_dir: Story, tmp_path: Path, config: Config) -> None:
    package = ready(story_dir, tmp_path)
    before = story_dir.read("requirements")
    approve_ok(package, config)
    after = story_dir.read("requirements")
    strip = re.compile(r"<!-- eil:begin approval -->.*?<!-- eil:end approval -->", re.S)
    assert strip.sub("", before) == strip.sub("", after)


def test_a_second_approval_replaces_the_first_rather_than_appending(
    story_dir: Story, tmp_path: Path, config: Config
) -> None:
    package = ready(story_dir, tmp_path)
    approve_ok(package, config)
    story_dir.append("requirements", "\nA later edit.\n")
    check_stage(package, "requirements", judgments_path=judgments(tmp_path))
    assert package.state("requirements").state == "needs-re-review"
    approve_ok(package, config, attestation="Re-confirmed after the edit.")
    text = story_dir.read("requirements")
    assert text.count("<!-- eil:begin approval -->") == 1
    record = package.record("requirements", "approval")
    assert record["attestation"] == "Re-confirmed after the edit."
    assert package.state("requirements").state == "approved"


# ---- refusals write nothing (determinism 3)


def test_an_unmet_criterion_refuses_and_writes_nothing(
    story_dir: Story, tmp_path: Path, config: Config
) -> None:
    package = ready(story_dir, tmp_path, requirements_doc({"Constraints": None}))
    before = story_dir.path("requirements").read_bytes()
    with pytest.raises(EilExit) as exc:
        approve_ok(package, config)
    assert exc.value.code == 1
    assert refusals(exc) == ["unmet-criteria"]
    assert "REQ-G06" in exc.value.payload["refusals"][0]["message"]
    assert exc.value.payload["refusals"][0]["fix"]
    assert story_dir.path("requirements").read_bytes() == before


def test_missing_ai_verdicts_leave_the_judgment_criteria_unmet(story_dir: Story, config: Config) -> None:
    story_dir.write("requirements", requirements_doc())
    package = Package(story_dir.root)
    with pytest.raises(EilExit) as exc:
        approve_ok(package, config)
    assert refusals(exc) == ["unmet-criteria"]
    message = exc.value.payload["refusals"][0]["message"]
    assert all(criterion in message for criterion in JUDGED)


def test_verdicts_that_predate_an_edit_no_longer_count(
    story_dir: Story, tmp_path: Path, config: Config
) -> None:
    package = ready(story_dir, tmp_path)
    story_dir.append("requirements", "\nAn edit after the AI's assessment.\n")
    with pytest.raises(EilExit) as exc:
        approve_ok(package, config)
    assert refusals(exc) == ["unmet-criteria"]


def test_an_open_material_question_is_its_own_refusal(
    story_dir: Story, tmp_path: Path, config: Config
) -> None:
    text = requirements_doc({"Open Questions": "**OQ-004**: Retention? (status: open) (material: yes)"})
    package = ready(story_dir, tmp_path, text)
    with pytest.raises(EilExit) as exc:
        approve_ok(package, config)
    assert refusals(exc) == ["open-question"]
    assert "OQ-004" in exc.value.payload["refusals"][0]["message"]


def test_an_empty_open_questions_section_is_not_reported_as_an_open_question(
    story_dir: Story, tmp_path: Path, config: Config
) -> None:
    """The dedicated refusal is for questions that are actually open, not for an empty section."""
    package = ready(story_dir, tmp_path, requirements_doc({"Open Questions": ""}))
    with pytest.raises(EilExit) as exc:
        approve_ok(package, config)
    assert refusals(exc) == ["unmet-criteria"]
    assert "Open Questions" in exc.value.payload["refusals"][0]["message"]


def test_the_unmet_criteria_are_listed_one_per_line(story_dir: Story, tmp_path: Path, config: Config) -> None:
    package = ready(story_dir, tmp_path, requirements_doc({"Constraints": None, "Risks": None}))
    with pytest.raises(EilExit) as exc:
        approve_ok(package, config)
    lines = exc.value.payload["refusals"][0]["message"].splitlines()
    assert lines[0] == "unmet criteria:"
    assert [line.strip().split(":")[0] for line in lines[1:]] == ["REQ-G06", "REQ-G08"]


def test_an_accepted_question_lets_approval_through(story_dir: Story, tmp_path: Path, config: Config) -> None:
    text = requirements_doc(
        {"Open Questions": "**OQ-004**: Retention? (status: accepted) (accepted-by: Ada Dev) (material: yes)"}
    )
    package = ready(story_dir, tmp_path, text)
    approve_ok(package, config)
    assert package.state("requirements").state == "approved"


def test_unreviewed_ai_content_refuses(story_dir: Story, tmp_path: Path, config: Config) -> None:
    text = requirements_doc({"Background": "AI wrote this. [ai-draft]"})
    package = ready(story_dir, tmp_path, text)
    with pytest.raises(EilExit) as exc:
        approve_ok(package, config)
    assert refusals(exc) == ["unreviewed-ai-content"]
    assert "line" in exc.value.payload["refusals"][0]["message"]


def test_unreviewed_ai_content_can_be_overridden_by_a_confirmer(
    story_dir: Story, tmp_path: Path, config: Config
) -> None:
    text = requirements_doc({"Background": "AI wrote this. [ai-draft]"})
    ready(story_dir, tmp_path, text)
    package = Package(story_dir.root)
    override(
        package,
        config,
        "requirements",
        "unreviewed-ai-content",
        by="Ada Dev",
        reason="reviewed in the pairing session",
    )
    check_stage(package, "requirements", judgments_path=judgments(tmp_path))
    approve_ok(package, config)
    assert package.record("requirements", "approval")["overrides_used"] == ["OVR-001"]


def test_a_blank_attestation_is_refused(story_dir: Story, tmp_path: Path, config: Config) -> None:
    package = ready(story_dir, tmp_path)
    for attestation in ("", "   ", "\n"):
        with pytest.raises(EilExit) as exc:
            approve_ok(package, config, attestation=attestation)
        assert refusals(exc) == ["attestation-required"]
    assert package.state("requirements").state != "approved"


@pytest.mark.parametrize("name", ["Claude", "AI", "ai agent", "Copilot"])
def test_an_approval_by_the_ai_is_refused(story_dir: Story, tmp_path: Path, name: str) -> None:
    permissive = Config(
        default_developer=name, approvers={"requirements": [name]}, abbreviation_authorisers=[]
    )
    package = ready(story_dir, tmp_path)
    with pytest.raises(EilExit) as exc:
        approve_ok(package, permissive, by=name)
    assert "ai-approval" in refusals(exc)
    assert package.state("requirements").state != "approved"


def test_someone_not_configured_is_refused(story_dir: Story, tmp_path: Path, config: Config) -> None:
    package = ready(story_dir, tmp_path)
    before = story_dir.path("requirements").read_bytes()
    with pytest.raises(EilExit) as exc:
        approve_ok(package, config, by="Mallory")
    assert refusals(exc) == ["not-a-confirmer"]
    assert story_dir.path("requirements").read_bytes() == before


def test_every_applicable_refusal_is_reported_together(
    story_dir: Story, tmp_path: Path, config: Config
) -> None:
    package = ready(story_dir, tmp_path, requirements_doc({"Constraints": None}))
    with pytest.raises(EilExit) as exc:
        approve_ok(package, config, by="Mallory", attestation="")
    assert set(refusals(exc)) == {"not-a-confirmer", "attestation-required", "unmet-criteria"}


@pytest.mark.parametrize("stage", ["ai-spec", "plan", "tasks", "verification"])
def test_stages_that_are_never_approved_are_refused(story_dir: Story, config: Config, stage: str) -> None:
    story_dir.write(stage, "# x\n")
    with pytest.raises(EilExit) as exc:
        approve(Package(story_dir.root), config, stage, by="Ada Dev", attestation="yes")
    assert exc.value.code == 1 and refusals(exc) == ["not-approvable"]


def test_an_unknown_stage_is_refused(story_dir: Story, config: Config) -> None:
    with pytest.raises(EilExit) as exc:
        approve(Package(story_dir.root), config, "design", by="Ada Dev", attestation="yes")
    assert refusals(exc) == ["unknown-stage"]


def test_a_stage_whose_document_does_not_exist_cannot_be_approved(story_dir: Story, config: Config) -> None:
    with pytest.raises(EilExit) as exc:
        approve(Package(story_dir.root), config, "requirements", by="Ada Dev", attestation="yes")
    assert refusals(exc) == ["unknown-stage"]
    assert "no document" in exc.value.payload["refusals"][0]["message"]
    assert not story_dir.exists("requirements")


def test_a_later_stage_cannot_be_approved_before_the_earlier_one(
    story_dir: Story, tmp_path: Path, config: Config
) -> None:
    story_dir.write("functional", "# Functional\n")
    package = Package(story_dir.root)
    with pytest.raises(EilExit) as exc:
        approve(package, config, "functional", by="Ada Dev", attestation="yes")
    assert "stage-not-approved" in refusals(exc)
    assert "requirements" in exc.value.payload["refusals"][0]["message"]


# ---- overrides (FR-010, FR-045)


def test_an_override_is_recorded_under_overrides_with_who_what_and_why(
    story_dir: Story, config: Config
) -> None:
    story_dir.write("requirements", requirements_doc({"Constraints": None}))
    package = Package(story_dir.root)
    result = override(
        package, config, "requirements", "REQ-G06", by="Ada Dev", reason="a spike: constraints unknown yet"
    )
    assert result["ok"] is True and result["id"] == "OVR-001"
    (record,) = [r for r in package.doc("requirements").records() if r.kind == "override"]
    assert record.obj == {
        "id": "OVR-001",
        "stage": "requirements",
        "criterion": "REQ-G06",
        "by": "Ada Dev",
        "at": NOW,
        "reason": "a spike: constraints unknown yet",
    }
    text = story_dir.read("requirements")
    assert text.index("## Overrides") < text.index("```eil:override") < text.index("## Quality Assessment")


def test_overrides_are_numbered_across_the_story(story_dir: Story, config: Config) -> None:
    story_dir.write(
        "requirements", requirements_doc({"Constraints": None, "Risks": None, "Assumptions": None})
    )
    package = Package(story_dir.root)
    first = override(package, config, "requirements", "REQ-G06", by="Ada Dev", reason="r1")
    second = override(package, config, "requirements", "REQ-G08", by="Ada Dev", reason="r2")
    assert (first["id"], second["id"]) == ("OVR-001", "OVR-002")
    earlier = {"id": "OVR-005", "stage": "functional", "criterion": "FUN-G01", "by": "A", "reason": "r"}
    story_dir.write("functional", "# F\n\n## Overrides\n\n" + record_block("override", earlier))
    third = override(package, config, "requirements", "REQ-G09", by="Ada Dev", reason="r3")
    assert third["id"] == "OVR-006"


def test_an_override_changes_the_document_fingerprint(story_dir: Story, config: Config) -> None:
    story_dir.write("requirements", requirements_doc())
    package = Package(story_dir.root)
    before = package.fingerprint("requirements")
    override(package, config, "requirements", "REQ-G06", by="Ada Dev", reason="r")
    assert package.fingerprint("requirements") != before


def test_an_override_makes_that_criterion_overridden_in_the_next_check(
    story_dir: Story, config: Config
) -> None:
    story_dir.write("requirements", requirements_doc({"Constraints": None}))
    package = Package(story_dir.root)
    override(package, config, "requirements", "REQ-G06", by="Ada Dev", reason="r")
    result = check_stage(package, "requirements", write=False)
    assert next(c for c in result.criteria if c.id == "REQ-G06").status == "overridden"


def test_an_override_without_a_reason_is_refused(story_dir: Story, config: Config) -> None:
    story_dir.write("requirements", requirements_doc())
    before = story_dir.path("requirements").read_bytes()
    for reason in ("", "   "):
        with pytest.raises(EilExit) as exc:
            override(Package(story_dir.root), config, "requirements", "REQ-G06", by="Ada Dev", reason=reason)
        assert refusals(exc) == ["reason-required"]
    assert story_dir.path("requirements").read_bytes() == before


def test_an_override_by_someone_not_configured_is_refused(story_dir: Story, config: Config) -> None:
    story_dir.write("requirements", requirements_doc())
    before = story_dir.path("requirements").read_bytes()
    with pytest.raises(EilExit) as exc:
        override(Package(story_dir.root), config, "requirements", "REQ-G06", by="Mallory", reason="r")
    assert refusals(exc) == ["not-a-confirmer"]
    assert story_dir.path("requirements").read_bytes() == before


def test_an_override_of_an_unknown_criterion_is_refused(story_dir: Story, config: Config) -> None:
    story_dir.write("requirements", requirements_doc())
    for criterion in ("REQ-G99", "FUN-G01", "everything", ""):
        with pytest.raises(EilExit) as exc:
            override(Package(story_dir.root), config, "requirements", criterion, by="Ada Dev", reason="r")
        assert refusals(exc) == ["unknown-criterion"]


def test_an_override_for_a_stage_with_no_document_is_refused(story_dir: Story, config: Config) -> None:
    with pytest.raises(EilExit) as exc:
        override(Package(story_dir.root), config, "requirements", "REQ-G06", by="Ada Dev", reason="r")
    assert refusals(exc) == ["unknown-stage"]


def test_an_override_is_visible_in_the_document_for_review(story_dir: Story, config: Config) -> None:
    story_dir.write(
        "requirements",
        requirements_doc(extra=record_block("challenge", {"id": "CH-001", "status": "closed"})),
    )
    override(Package(story_dir.root), config, "requirements", "REQ-G06", by="Ada Dev", reason="visible")
    assert "visible" in story_dir.read("requirements") and '"CH-001"' in story_dir.read("requirements")


# ---- 003 D-59: approving takes one word, recorded with the helper's question (determinism 53)



def test_an_empty_reply_is_still_refused(story_dir: Story, tmp_path: Path, config: Config) -> None:
    package = ready(story_dir, tmp_path)
    with pytest.raises(EilExit) as exc:
        approve_ok(package, config, attestation="  ")
    assert "attestation-required" in refusals(exc)


