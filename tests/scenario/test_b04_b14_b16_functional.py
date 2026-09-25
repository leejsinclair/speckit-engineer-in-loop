"""B-04, B-14 and B-16 (task T062): the Functional stage end to end, driving the helper as the
commands would. FR-025, FR-073 to FR-085."""

from __future__ import annotations

import json
import shutil
from collections.abc import Callable
from pathlib import Path

import pytest
from eil.package import Package

from tests.helpers.package import ASSETS_FIXTURES, FIGMA_URL, functional_doc, requirements_doc
from tests.scenario.conftest import write_judgments

pytestmark = pytest.mark.scenario

FEATURE = "specs/001-detect-duplicates"
ACCEPTED = "**OQ-004**: Keep history? (status: accepted) (accepted-by: Ada Dev) (material: yes)"
REQ_JUDGED = ["REQ-G01", "REQ-G11", "REQ-G12", "REQ-G13"]
FUN_JUDGED = ["FUN-G10", "FUN-G12", "FUN-G13"]


def feature(project: Path) -> Path:
    return project / FEATURE


def approved_requirements(project: Path, eil: Callable) -> None:
    assert (
        eil(
            [
                "start",
                "--title",
                "Detect duplicates",
                "--owner",
                "Ada Dev",
                "--feature-dir",
                FEATURE,
                "--json",
            ]
        ).code
        == 0
    )
    (feature(project) / "s01-requirements.md").write_text(
        requirements_doc({"Open Questions": ACCEPTED}), encoding="utf-8", newline="\n"
    )
    judged = write_judgments(project, "requirements", REQ_JUDGED)
    eil(["check", "--stage", "requirements", "--judgments", str(judged), "--json"])
    result = eil(
        ["approve", "requirements", "--by", "Ada Dev", "--attestation", "Yes, this is the problem.", "--json"]
    )
    assert result.code == 0, result.stdout


def start_functional(project: Path, eil: Callable) -> None:
    approved_requirements(project, eil)
    result = eil(["stage-init", "functional", "--json"])
    assert result.code == 0, result.stdout + result.stderr


# ---- B-04


def test_b04_the_functional_stage_starts_from_the_template_once_requirements_are_approved(
    project: Path, eil: Callable
) -> None:
    start_functional(project, eil)
    text = (feature(project) / "s02-functional-spec.md").read_text(encoding="utf-8")
    for heading in (
        "Actors",
        "Functional Requirements",
        "Business Rules",
        "Acceptance Criteria",
        "Sequence Diagrams",
        "Wireframes",
        "Comprehension Check",
    ):
        assert f"{heading}\n" in text, heading
    assert "<!-- eil:begin comprehension -->" in text
    assert not (feature(project) / "assets").exists()  # FR-047: only the first export creates it


def test_b04_a_requirement_with_no_functional_requirement_is_reported(project: Path, eil: Callable) -> None:
    start_functional(project, eil)
    (feature(project) / "s02-functional-spec.md").write_text(
        functional_doc(wireframe=None), encoding="utf-8", newline="\n"
    )
    judged = write_judgments(project, "functional", FUN_JUDGED)
    result = eil(["check", "--stage", "functional", "--judgments", str(judged), "--json"])
    assert result.code == 0
    rows = {c["id"]: c for c in result.json["criteria"]}
    assert rows["FUN-G15"]["status"] == "not-met" and "no wireframe" in rows["FUN-G15"]["reason"]
    assert rows["FUN-G16"]["status"] == "not-met"


# ---- B-14: the export flow


def test_b14_a_wireframe_is_registered_and_then_meets_the_gate(project: Path, eil: Callable) -> None:
    start_functional(project, eil)
    story = feature(project)
    text = functional_doc(wireframe=None).replace(
        "## Wireframes\n", "## Wireframes\n\n**ART-003**: Duplicate review screen (traces: FR-001, UC-001)\n"
    )
    (story / "s02-functional-spec.md").write_text(text, encoding="utf-8", newline="\n")
    export = story / "exports" / "screen.png"
    export.parent.mkdir()
    shutil.copy(ASSETS_FIXTURES / "wireframe.png", export)
    result = eil(
        [
            "artifact",
            "register",
            "--id",
            "ART-003",
            "--file",
            f"{FEATURE}/exports/screen.png",
            "--kind",
            "wireframe",
            "--source-tool",
            "figma",
            "--source-url",
            FIGMA_URL,
            "--exported-on",
            "2026-09-25",
            "--exported-by",
            "Ada Dev",
            "--json",
        ]
    )
    assert result.code == 0, result.stdout + result.stderr
    assert (story / "assets" / "screen.png").is_file()
    listing = eil(["artifact", "list", "--stage", "functional", "--json"])
    assert listing.code == 0
    row = next(r for r in listing.json["artifacts"] if r["id"] == "ART-003")
    assert (row["kind"], row["form"], row["state"]) == ("wireframe", "file", "ok")


def test_b14_editing_the_export_after_registration_is_caught_without_changing_the_document(
    project: Path, eil: Callable
) -> None:
    start_functional(project, eil)
    story = feature(project)
    (story / "s02-functional-spec.md").write_text(
        functional_doc(wireframe=None).replace(
            "## Wireframes\n", "## Wireframes\n\n**ART-003**: Screen (traces: FR-001)\n"
        ),
        encoding="utf-8",
        newline="\n",
    )
    export = story / "assets" / "screen.png"
    export.parent.mkdir()
    shutil.copy(ASSETS_FIXTURES / "wireframe.png", export)
    eil(
        [
            "artifact",
            "register",
            "--id",
            "ART-003",
            "--file",
            f"{FEATURE}/assets/screen.png",
            "--kind",
            "wireframe",
            "--source-tool",
            "figma",
            "--source-url",
            FIGMA_URL,
            "--exported-on",
            "2026-09-25",
            "--exported-by",
            "Ada Dev",
            "--json",
        ]
    )
    fingerprint = eil(["fingerprint", f"{FEATURE}/s02-functional-spec.md"]).stdout
    export.write_bytes(export.read_bytes() + b"tampered")
    assert eil(["fingerprint", f"{FEATURE}/s02-functional-spec.md"]).stdout == fingerprint
    listing = eil(["artifact", "list", "--json"])
    assert next(r for r in listing.json["artifacts"] if r["id"] == "ART-003")["state"] == "hash-mismatch"


def test_b14_registration_without_a_frame_link_is_refused(project: Path, eil: Callable) -> None:
    start_functional(project, eil)
    story = feature(project)
    (story / "s02-functional-spec.md").write_text(
        functional_doc(wireframe=None).replace(
            "## Wireframes\n", "## Wireframes\n\n**ART-003**: Screen (traces: FR-001)\n"
        ),
        encoding="utf-8",
        newline="\n",
    )
    (story / "assets").mkdir()
    shutil.copy(ASSETS_FIXTURES / "wireframe.png", story / "assets" / "screen.png")
    result = eil(
        [
            "artifact",
            "register",
            "--id",
            "ART-003",
            "--file",
            f"{FEATURE}/assets/screen.png",
            "--kind",
            "wireframe",
            "--source-tool",
            "figma",
            "--source-url",
            "https://www.figma.com/design/AbC/Name",
            "--json",
        ]
    )
    assert result.code == 1 and result.refusal_codes == ["artifact-no-provenance"]


# ---- B-16 and the check: approval needs the comprehension record, not a pass


def write_ready_functional(project: Path, eil: Callable) -> None:
    start_functional(project, eil)
    story = feature(project)
    (story / "s02-functional-spec.md").write_text(
        functional_doc(wireframe=None, not_applicable="- Wireframes: batch import, no user interface"),
        encoding="utf-8",
        newline="\n",
    )
    judged = write_judgments(project, "functional", FUN_JUDGED)
    assert eil(["check", "--stage", "functional", "--judgments", str(judged), "--json"]).code == 0


def test_b16_approval_is_refused_until_the_comprehension_check_has_been_taken(
    project: Path, eil: Callable
) -> None:
    write_ready_functional(project, eil)
    result = eil(
        ["approve", "functional", "--by", "Ada Dev", "--attestation", "Yes, this is the behaviour.", "--json"]
    )
    assert result.code == 1 and result.refusal_codes == ["unmet-criteria"]
    assert "FUN-G16" in result.json["refusals"][0]["message"]


def test_b16_a_complete_record_is_enough_even_when_every_level_was_skipped(
    project: Path, eil: Callable
) -> None:
    write_ready_functional(project, eil)
    plan = eil(["comprehension", "plan", "--stage", "functional", "--json"])
    assert plan.code == 0
    for row in plan.json["levels"]:
        recorded = eil(
            [
                "comprehension",
                "record",
                "--stage",
                "functional",
                "--level",
                row["level"],
                "--outcome",
                "skipped",
                "--by",
                "Ada Dev",
                "--items",
                row["target"],
                "--json",
            ]
        )
        assert recorded.code == 0, recorded.stdout
    approved = eil(
        ["approve", "functional", "--by", "Ada Dev", "--attestation", "Yes, this is the behaviour.", "--json"]
    )
    assert approved.code == 0, approved.stdout
    assert approved.json["approval"]["comprehension"]["skipped"] == 5
    assert Package(feature(project)).state("functional").state == "approved"


def test_b16_the_plan_is_deterministic_across_runs(project: Path, eil: Callable) -> None:
    write_ready_functional(project, eil)
    first = eil(["comprehension", "plan", "--stage", "functional", "--json"])
    second = eil(["comprehension", "plan", "--stage", "functional", "--json"])
    assert first.json == second.json
    retry = eil(
        ["comprehension", "plan", "--stage", "functional", "--level", "explain", "--attempt", "2", "--json"]
    )
    assert retry.json["attempt"] == 2 and retry.json["levels"][0]["level"] == "explain"


def test_b16_editing_the_document_after_the_check_makes_it_stale(project: Path, eil: Callable) -> None:
    write_ready_functional(project, eil)
    plan = eil(["comprehension", "plan", "--stage", "functional", "--json"])
    for row in plan.json["levels"]:
        eil(
            [
                "comprehension",
                "record",
                "--stage",
                "functional",
                "--level",
                row["level"],
                "--outcome",
                "understood",
                "--by",
                "Ada Dev",
                "--json",
            ]
        )
    path = feature(project) / "s02-functional-spec.md"
    path.write_text(
        path.read_text(encoding="utf-8").replace("within 60 seconds", "within 90 seconds"), encoding="utf-8"
    )
    judged = write_judgments(project, "functional", FUN_JUDGED)
    result = eil(["check", "--stage", "functional", "--judgments", str(judged), "--json"])
    assert "comprehension-stale" in [f["code"] for f in result.json["findings"]]


def test_b16_the_record_holds_no_question_answer_or_score(project: Path, eil: Callable) -> None:
    write_ready_functional(project, eil)
    plan = eil(["comprehension", "plan", "--stage", "functional", "--json"])
    for row in plan.json["levels"]:
        eil(
            [
                "comprehension",
                "record",
                "--stage",
                "functional",
                "--level",
                row["level"],
                "--outcome",
                "coached",
                "--attempts",
                "2",
                "--by",
                "Ada Dev",
                "--items",
                row["target"],
                "--json",
            ]
        )
    text = (feature(project) / "s02-functional-spec.md").read_text(encoding="utf-8")
    start = text.index("<!-- eil:begin comprehension -->")
    body = text[start : text.index("<!-- eil:end comprehension -->")]
    record = json.loads(body[body.index("```json") + 7 : body.rindex("```")])
    assert set(record) == {"stage", "fingerprint", "taken_by", "started_at", "updated_at", "levels"}
    assert all(
        set(level) <= {"level", "outcome", "attempts", "items", "reason"} for level in record["levels"]
    )
