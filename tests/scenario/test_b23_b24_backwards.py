"""B-23 and B-24 (T057): a problem found late is corrected in place with one report, one agreement and one
sign-off, and only what the change reaches is re-derived. Drives the helper as ``/speckit-eil-correct`` does.
SC-005, FR-021 to FR-027, FR-041, FR-042."""

from __future__ import annotations

import json
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from tests.helpers.derived import change_dec3, edit, package_of, wire_tasks_to_dec3
from tests.helpers.package import Story, record_block
from tests.unit.test_accept_changes import REQ2, prepared

pytestmark = pytest.mark.scenario
REPO = Path(__file__).resolve().parents[2]
Eil = Callable[..., tuple[int, Any]]
WORDING = "Analysts can review each flagged pair, and log every review."
REJECTED = {
    "id": "CH-003", "stage": "requirements", "raised_by": "ai", "raised_at": "2026-09-26T10:00:00Z",
    "target": "REQ-002", "text": "Should merges be logged?", "status": "closed",
    "responder": "Ada Dev", "response": "rejected", "reason": "Out of scope", "at": "2026-09-26T10:05:00Z",
}  # fmt: skip


@pytest.fixture
def eil(reference_story: Story, eil_json: Eil) -> Eil:
    project = reference_story.root.parent.parent
    config = project / ".specify" / "extensions" / "eil" / "eil-config.yml"
    config.parent.mkdir(parents=True)
    config.write_text(
        "default_developer: Ada Dev\napprovers:\n  requirements: [Ada Dev]\n  functional: [Ada Dev]\n"
        "  technical: [Ada Dev]\n  completion: [Ada Dev]\n",
        encoding="utf-8",
    )
    (project / ".specify" / "templates").mkdir(parents=True)
    shutil.copy(REPO / "templates" / "s00-readme-template.md", project / ".specify" / "templates")
    wire_tasks_to_dec3(reference_story)
    prepared(reference_story)

    def run(*args: str) -> tuple[int, Any]:
        return eil_json([*args, "--feature-dir", str(reference_story.root)], reference_story.root)

    for stage in ("ai-spec", "plan", "tasks", "verification"):
        code, listed = run("review", "list", "--stage", stage, "--kind", "unknown-currency")
        if listed["entries"]:
            code, data = run(
                "review", "answer", "--stage", stage, "--kind", "unknown-currency", "--digest", listed["digest"],
                "--reply", "ok", "--by", "Ada Dev", "--all",
            )  # fmt: skip
            assert code == 0, data
    return run


def summaries(story: Story, stage: str, *keys: str) -> tuple[str, str]:
    path = story.root.parent / f"summaries-{stage}.json"
    rows = [{"key": k, "summary": f"Summary of the change to {k}."} for k in keys]
    path.write_text(json.dumps({"stage": stage, "summaries": rows}), encoding="utf-8")
    return "--summaries", str(path)


def test_b23_a_correction_from_implementation_needs_three_interactions(reference_story: Story, eil: Eil) -> None:
    before = {s: reference_story.read(s) for s in package_of(reference_story).existing_stages()}
    code, proposal = eil("correct", "propose", "--item", "REQ-002", "--found-in", "implementation:T014", "--problem", "no log")
    assert code == 0 and proposal["candidates"] == ["requirements"] and proposal["ambiguous"] is False
    assert proposal["impact"] and before == {s: reference_story.read(s) for s in before}, "propose writes nothing"

    # interaction 1: the report with the person's wording; interaction 2: agreement to the preview
    code, opened = eil(
        "correct", "open", "--item", "REQ-002", "--found-in", "implementation:T014", "--problem", "no log",
        "--by", "Ada Dev", "--wording", WORDING,
    )  # fmt: skip
    assert code == 0 and opened["correction"]["id"] == "CR-001"
    edit(reference_story, "requirements", REQ2.split("**: ", 1)[1], WORDING)
    edit(reference_story, "requirements", WORDING, WORDING + " (decided: CR-001)")

    code, status = eil("status")
    blocked = {row["id"] for row in status["blocked_work"]}
    assert blocked and "T001" not in blocked
    assert eil("enter", "implement", "--task", "T001")[0] == 0

    # interaction 3: the sign-off. No changes list and no comprehension question in between.
    code, done = eil(
        "review", "confirm", "--stage", "requirements", "--by", "Ada Dev", "--confirmation", "ok",
        *summaries(reference_story, "requirements", "REQ-002"),
    )  # fmt: skip
    assert code == 0, done["refusals"][0]["message"]
    approval = done["approval"]
    assert approval["reached"] == "carried-forward" and approval["rests_on"] == ["CR-001"]
    record = package_of(reference_story).doc("requirements").read_provenance().obj
    assert [c["status"] for c in record["corrections"]] == ["closed"]
    assert record["changes"][0]["origin"] == "CR-001" and record["changes"][0]["summary_by"] == "ai"
    assert "implementation" in reference_story.read("requirements") and "CR-001" in reference_story.read("requirements")

    code, traced = eil("trace", "--to", "REQ-002")
    assert code == 0 and "CR-001" in json.dumps(traced)


def test_b23_step_2_an_ambiguous_owner_is_refused_without_an_owner(reference_story: Story, eil: Eil) -> None:
    from tests.unit.test_classify import classify

    classify(reference_story, "ai-spec", ("AIS-001", None))
    code, proposal = eil("correct", "propose", "--item", "AIS-001", "--found-in", "plan", "--problem", "x")
    assert code == 0 and proposal["ambiguous"] is True and proposal["candidates"][0] == "ai-spec"
    code, refusal = eil(
        "correct", "open", "--item", "AIS-001", "--found-in", "plan", "--problem", "x", "--by", "Ada Dev"
    )
    assert code == 1 and refusal["refusals"][0]["code"] == "owner-ambiguous"


def test_b23_step_5_and_6_a_rejected_challenge_is_listed_and_an_open_finding_blocks(reference_story: Story, eil: Eil) -> None:
    reference_story.append("requirements", "\n" + record_block("challenge", REJECTED).rstrip("\n") + "\n")
    eil("correct", "open", "--item", "REQ-002", "--found-in", "implementation", "--problem", "x", "--by", "Ada Dev", "--wording", WORDING)
    edit(reference_story, "requirements", REQ2.split("**: ", 1)[1], WORDING)
    edit(reference_story, "requirements", WORDING, WORDING + " (decided: CR-001)")
    code, done = eil(
        "review", "confirm", "--stage", "requirements", "--by", "Ada Dev", "--confirmation", "ok",
        *summaries(reference_story, "requirements", "REQ-002"),
    )  # fmt: skip
    assert code == 0, done
    code, listed = eil("review", "list", "--stage", "requirements", "--kind", "unsettled-challenges")
    assert code == 0 and [e["key"] for e in listed["entries"]] == ["CH-003"]

    reference_story.append(
        "verification",
        "\n**RF-001**: The review found the wrong retention period. (status: open)\nRoot: DEC-002\n",
    )
    code, checked = eil("check", "--stage", "verification")
    unmet = [c["id"] for c in checked["criteria"] if c["status"] != "met"]
    assert "VER-G07" in unmet


def test_b24_rederive_lists_exactly_what_the_change_reaches(reference_story: Story, eil: Eil) -> None:
    from tests.helpers.derived import reapprove_technical, settle_derived, wire_tasks_to_dec3

    wire_tasks_to_dec3(reference_story)
    settle_derived(reference_story)
    change_dec3(reference_story)
    reapprove_technical(reference_story)
    code, entered = eil("enter", "plan")
    assert code == 0
    assert set(entered["rederive"]) == {"AIS-014", "§Project Structure"}
