"""B-05, B-15 and the technical half of B-18 (task T076): the Technical stage end to end, driving the
installed helper as the commands would. FR-032, FR-033, FR-045, FR-074, FR-079, FR-080, FR-087 to FR-094."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
from eil.package import Package

from tests.helpers.package import (
    CONTAINER_DIAGRAM,
    DECISION,
    TECHNICAL_SEQUENCE,
    technical_doc,
)
from tests.scenario.conftest import write_judgments
from tests.scenario.test_b04_b14_b16_functional import feature, write_ready_functional

pytestmark = pytest.mark.scenario

TEC_JUDGED = ["TEC-G01", "TEC-G08", "TEC-G13", "TEC-G14"]
LEVELS = ["recognise", "explain", "apply", "trace", "evaluate"]
YES = "Yes, this is the engineering solution we intend to build."


def take_the_check(eil: Callable, stage: str, outcome: str = "understood") -> None:
    plan = eil(["comprehension", "plan", "--stage", stage, "--json"])
    assert plan.code == 0, plan.stdout
    for row in plan.json["levels"]:
        recorded = eil(
            [
                "comprehension",
                "record",
                "--stage",
                stage,
                "--level",
                row["level"],
                "--outcome",
                outcome,
                "--by",
                "Ada Dev",
                "--items",
                row["target"],
                "--json",
            ]
        )
        assert recorded.code == 0, recorded.stdout


def approved_functional(project: Path, eil: Callable) -> None:
    write_ready_functional(project, eil)
    take_the_check(eil, "functional")
    approved = eil(
        ["approve", "functional", "--by", "Ada Dev", "--attestation", "Yes, the behaviour.", "--json"]
    )
    assert approved.code == 0, approved.stdout


def start_technical(project: Path, eil: Callable) -> None:
    approved_functional(project, eil)
    result = eil(["stage-init", "technical", "--json"])
    assert result.code == 0, result.stdout + result.stderr


def write_technical(project: Path, **kwargs: object) -> None:
    (feature(project) / "s03-technical-spec.md").write_text(
        technical_doc(**kwargs), encoding="utf-8", newline="\n"
    )


def check(project: Path, eil: Callable, judged: bool = True):
    argv = ["check", "--stage", "technical", "--json"]
    if judged:
        argv[3:3] = ["--judgments", str(write_judgments(project, "technical", TEC_JUDGED))]
    return eil(argv)


def unmet(result) -> dict[str, str]:
    return {c["id"]: c["reason"] for c in result.json["criteria"] if c["status"] == "not-met"}


# ---- B-05: decisions are the developer's, in full


def test_b05_the_technical_stage_cannot_start_before_the_functional_stage_is_approved(
    project: Path, eil: Callable
) -> None:
    write_ready_functional(project, eil)
    result = eil(["stage-init", "technical", "--json"])
    assert result.code == 1 and result.refusal_codes == ["stage-not-approved"]
    assert not (feature(project) / "s03-technical-spec.md").exists()


def test_b05_the_stage_starts_from_the_template_with_every_section_and_diagram_place(
    project: Path, eil: Callable
) -> None:
    start_technical(project, eil)
    text = (feature(project) / "s03-technical-spec.md").read_text(encoding="utf-8")
    for heading in (
        "Technical Requirements",
        "Architecture",
        "Component Design",
        "Data Design",
        "API and Integration Design",
        "Security Design",
        "Error Handling and Resilience",
        "Observability",
        "Performance",
        "Testing Strategy",
        "Deployment and Migration",
        "Existing System Impact",
        "Alternatives Considered",
        "Risks and Trade-offs",
        "Technical Decisions",
        "Container View",
        "Component Views",
        "Sequence Diagrams",
        "Data Model",
        "Comprehension Check",
    ):
        assert f"## {heading}\n" in text, heading
    assert "<!-- eil:begin comprehension -->" in text
    assert "{{" not in text
    result = eil(["check", "--stage", "technical", "--json"])
    assert not result.json["ok"]  # an empty template never passes


def test_b05_a_decision_missing_its_rejected_alternative_names_the_field_and_blocks_the_gate(
    project: Path, eil: Callable
) -> None:
    start_technical(project, eil)
    incomplete = "\n".join(ln for ln in DECISION.splitlines() if not ln.startswith("Rejected alternative"))
    write_technical(project, sections={"Technical Decisions": incomplete})
    result = check(project, eil)
    assert "DEC-001 has no rejected alternative" in unmet(result)["TEC-G02"]
    write_technical(project)
    fixed = check(project, eil)
    assert "TEC-G02" not in unmet(fixed)


def test_b05_the_owner_of_a_decision_is_the_developer_even_when_the_ai_proposed_it(
    project: Path, eil: Callable
) -> None:
    start_technical(project, eil)
    write_technical(
        project, sections={"Technical Decisions": DECISION.replace("Owner: Ada Dev", "Owner: AI")}
    )
    assert "owned by 'AI'" in unmet(check(project, eil))["TEC-G02"]
    write_technical(project)
    assert "TEC-G02" not in unmet(check(project, eil))


def test_b05_a_decision_that_serves_no_requirement_is_flagged(project: Path, eil: Callable) -> None:
    start_technical(project, eil)
    write_technical(
        project, sections={"Technical Decisions": DECISION.replace(" (traces: FR-001, NFR-001)", "")}
    )
    assert "DEC-001 traces to no FR or NFR" in unmet(check(project, eil))["TEC-G02"]


# ---- B-15: diagrams and their consistency


def test_b15_a_complete_technical_document_meets_every_criterion_but_the_comprehension_check(
    project: Path, eil: Callable
) -> None:
    start_technical(project, eil)
    write_technical(project)
    result = check(project, eil)
    assert list(unmet(result)) == ["TEC-G19"], unmet(result)


def test_b15_renaming_an_external_system_in_the_container_diagram_names_both_sides(
    project: Path, eil: Callable
) -> None:
    start_technical(project, eil)
    write_technical(project, container=CONTAINER_DIAGRAM.replace('"CRM"', '"Salesforce"'))
    result = check(project, eil)
    messages = [f["message"] for f in result.json["findings"] if f["code"] == "diagram-inconsistent"]
    assert any("'Salesforce'" in m for m in messages) and any("'CRM'" in m for m in messages)
    assert "TEC-G15" in unmet(result)
    write_technical(project)
    assert "TEC-G15" not in unmet(check(project, eil))


def test_b15_a_participant_in_no_c4_diagram_and_a_store_that_is_not_a_database_are_reported(
    project: Path, eil: Callable
) -> None:
    start_technical(project, eil)
    write_technical(
        project,
        sequence=TECHNICAL_SEQUENCE.replace("Duplicate Worker", "Rabbit Queue"),
        er_store="Import API",
    )
    result = check(project, eil)
    joined = " ".join(f["message"] for f in result.json["findings"])
    assert "rule c" in joined and "'Rabbit Queue'" in joined
    assert "rule d" in joined and "not a data store" in joined
    assert {"TEC-G17", "TEC-G18"} <= set(unmet(result))


def test_b15_a_line_the_parser_cannot_read_is_reported_with_its_line_and_never_skipped(
    project: Path, eil: Callable
) -> None:
    start_technical(project, eil)
    write_technical(project, sequence=TECHNICAL_SEQUENCE + "\n  Foo bar baz")
    result = check(project, eil)
    finding = next(f for f in result.json["findings"] if f["code"] == "diagram-unparseable")
    text = (feature(project) / "s03-technical-spec.md").read_text(encoding="utf-8").splitlines()
    line = next(i for i, row in enumerate(text, 1) if row.strip() == "Foo bar baz")
    assert f":{line}" in finding["where"] or f"line {line}" in finding["message"]
    assert "TEC-G17" in unmet(result)


def test_b15_a_functional_only_sequence_diagram_is_wrong_for_this_stage(project: Path, eil: Callable) -> None:
    start_technical(project, eil)
    write_technical(
        project,
        sequence="sequenceDiagram\n  actor Analyst as Data Analyst\n  participant System\n  Analyst->>System: upload",
    )
    result = check(project, eil)
    assert "TEC-G17" in unmet(result)


def test_b15_an_er_diagram_or_a_component_diagram_can_be_replaced_by_a_recorded_reason(
    project: Path, eil: Callable
) -> None:
    start_technical(project, eil)
    write_technical(
        project,
        er=None,
        components=None,
        not_applicable="- Data Model: no persistent data changes\n- Duplicate Worker: a single module",
    )
    result = check(project, eil)
    assert not {"TEC-G16", "TEC-G18"} & set(unmet(result)), unmet(result)


def test_b15_a_confirmer_can_override_a_rule_and_the_override_stays_in_the_overview(
    project: Path, eil: Callable
) -> None:
    start_technical(project, eil)
    write_technical(project, sequence=TECHNICAL_SEQUENCE.replace("Duplicate Worker", "Rabbit Queue"))
    assert "TEC-G17" in unmet(check(project, eil))
    overridden = eil(
        [
            "override",
            "technical",
            "--criterion",
            "TEC-G17",
            "--by",
            "Ada Dev",
            "--reason",
            "the queue is drawn in the platform team's diagram",
            "--json",
        ]
    )
    assert overridden.code == 0, overridden.stdout
    result = check(project, eil)
    assert {c["id"]: c["status"] for c in result.json["criteria"]}["TEC-G17"] == "overridden"
    overview = (feature(project) / "s00-README.md").read_text(encoding="utf-8")
    assert "TEC-G17" in overview and "OVR-" in overview


# ---- B-18, technical half: the check, the record and the approval


def ready_for_the_check(project: Path, eil: Callable) -> None:
    start_technical(project, eil)
    write_technical(project)
    assert list(unmet(check(project, eil))) == ["TEC-G19"]


def test_b18_the_plan_targets_decisions_and_artefacts_and_is_repeatable(project: Path, eil: Callable) -> None:
    ready_for_the_check(project, eil)
    first = eil(["comprehension", "plan", "--stage", "technical", "--json"])
    assert first.code == 0, first.stdout
    targets = {row["level"]: row["target"] for row in first.json["levels"]}
    assert list(targets) == LEVELS
    assert targets["explain"] == "DEC-001" and targets["evaluate"] == "DEC-001"
    assert targets["recognise"] in {"DEC-001", "ART-004", "ART-005", "ART-006", "ART-007"}
    assert targets["apply"] in {"DEC-001", "ART-004", "ART-006"}
    assert eil(["comprehension", "plan", "--stage", "technical", "--json"]).json == first.json


def test_b18_the_plan_is_refused_while_another_criterion_is_unmet(project: Path, eil: Callable) -> None:
    start_technical(project, eil)
    write_technical(project, sections={"Security Design": None})
    check(project, eil)
    result = eil(["comprehension", "plan", "--stage", "technical", "--json"])
    assert result.code == 1 and result.refusal_codes == ["comprehension-prerequisites"]
    assert "TEC-G03" in result.json["refusals"][0]["message"]


def test_b18_approval_is_refused_until_the_check_has_been_taken_and_then_records_the_counts(
    project: Path, eil: Callable
) -> None:
    ready_for_the_check(project, eil)
    refused = eil(["approve", "technical", "--by", "Ada Dev", "--attestation", YES, "--json"])
    assert refused.code == 1 and refused.refusal_codes == ["unmet-criteria"]
    assert "TEC-G19" in refused.json["refusals"][0]["message"]
    plan = eil(["comprehension", "plan", "--stage", "technical", "--json"])
    outcomes = ["understood", "coached", "revealed", "skipped", "understood"]
    for row, outcome in zip(plan.json["levels"], outcomes, strict=True):
        recorded = eil(
            [
                "comprehension",
                "record",
                "--stage",
                "technical",
                "--level",
                row["level"],
                "--outcome",
                outcome,
                "--by",
                "Ada Dev",
                "--items",
                row["target"],
                "--json",
            ]
        )
        assert recorded.code == 0, recorded.stdout
    approved = eil(["approve", "technical", "--by", "Ada Dev", "--attestation", YES, "--json"])
    assert approved.code == 0, approved.stdout
    counts = approved.json["approval"]["comprehension"]
    assert (counts["understood"], counts["coached"], counts["revealed"], counts["skipped"]) == (2, 1, 1, 1)
    assert Package(feature(project)).state("technical").state == "approved"
    overview = (feature(project) / "s00-README.md").read_text(encoding="utf-8")
    assert "understood 2 · coached 1 · revealed 1 · skipped 1" in overview


def test_b18_a_content_change_after_the_check_makes_it_stale_and_a_re_check_restores_the_gate(
    project: Path, eil: Callable
) -> None:
    ready_for_the_check(project, eil)
    take_the_check(eil, "technical")
    assert not unmet(check(project, eil))
    path = feature(project) / "s03-technical-spec.md"
    path.write_text(path.read_text(encoding="utf-8").replace("three times", "five times"), encoding="utf-8")
    stale = check(project, eil)
    assert "comprehension-stale" in [f["code"] for f in stale.json["findings"]]
    assert list(unmet(stale)) == ["TEC-G19"]
    take_the_check(eil, "technical")
    assert not unmet(check(project, eil))


def test_b18_a_changed_functional_specification_makes_the_technical_stage_need_re_review(
    project: Path, eil: Callable
) -> None:
    ready_for_the_check(project, eil)
    take_the_check(eil, "technical")
    eil(["approve", "technical", "--by", "Ada Dev", "--attestation", YES, "--json"])
    path = feature(project) / "s02-functional-spec.md"
    path.write_text(
        path.read_text(encoding="utf-8").replace("within 60 seconds", "within 90 seconds"), encoding="utf-8"
    )
    assert Package(feature(project)).state("technical").state == "needs-re-review"
