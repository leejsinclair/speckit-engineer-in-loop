"""T058: decisions with no observable effect are the AI's, labelled, and validated by a person
(research D-53; FR-026 to FR-029).

``Owner: ai-decided`` is accepted only with a ``Reason:``. Such a DEC is always inferred, so it is on
the stage's review list in its own group, settled only by a person's reply; the approval names it.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from eil import blockstatus, comprehension, provenance, records, reviews
from eil.gates import JUDGMENT, check_stage, criteria_for
from eil.identity import Config
from eil.package import Package

from tests.helpers.package import DECISION, Story, approve_stages, with_record_sections, with_technical

CONFIG = Config(
    default_developer="Ada Dev",
    approvers={s: ["Ada Dev"] for s in ("requirements", "functional", "technical", "completion")},
)
AI_DECIDED = """**DEC-002**: Cache rendered pages by document modification time (traces: FR-001)
Decision: Cache each rendered page, keyed by the document's modification time.
Reason: Rendering is the slowest step; this choice changes nothing a user sees.
Rejected alternative: Render on every request.
Trade-off: A little memory.
Owner: ai-decided"""


def write(story: Story, decision: str = AI_DECIDED) -> None:
    """A Technical Specification drafted from the template, so with an empty Record (nothing adopted)."""
    with_technical(story, sections={"Technical Decisions": DECISION + "\n\n" + decision})
    story.write("technical", with_record_sections(story.read("technical")))
    approve_stages(story, "requirements", "functional")


def judgments(tmp: Path) -> Path:
    path = tmp / "technical-judgments.json"
    ids = [c.id for c in criteria_for("technical") if c.kind == JUDGMENT]
    path.write_text(json.dumps({"stage": "technical", "judgments": [{"id": i, "status": "met", "reason": "ok"} for i in ids]}))
    return path


def reasons(story: Story) -> list[str]:
    result = check_stage(Package(story.root), "technical", write=False)
    return [c.reason for c in result.criteria if c.status == "not-met"] + [f.code for f in result.findings]


def test_ai_decided_without_a_reason_is_a_finding_and_unmet(story_dir: Story) -> None:
    write(story_dir, AI_DECIDED.replace("Reason: Rendering is the slowest step; this choice changes nothing a user sees.\n", ""))
    found = reasons(story_dir)
    assert "ai-decided-without-reason" in found
    assert any("DEC-002" in r and "ai-decided" in r for r in found)


def test_ai_decided_with_a_reason_is_accepted(story_dir: Story) -> None:
    write(story_dir)
    assert not any("DEC-002" in r for r in reasons(story_dir))


def test_any_other_owner_must_still_be_a_person(story_dir: Story) -> None:
    write(story_dir, AI_DECIDED.replace("Owner: ai-decided", "Owner: Claude"))
    assert any("DEC-002" in r and "not the AI" in r for r in reasons(story_dir))


def test_an_ai_decided_decision_is_always_inferred(story_dir: Story) -> None:
    write(story_dir)
    provenance.classify(Package(story_dir.root), "technical", {"stage": "technical", "blocks": [{"block": "DEC-002", "adds": None}, {"block": "DEC-001", "adds": None}]})
    record = Package(story_dir.root).record("technical", "provenance")
    assert record["blocks"]["DEC-002"]["class"] == "inferred"
    assert "AI-decided" in record["blocks"]["DEC-002"]["adds"]
    assert record["blocks"]["DEC-001"]["class"] == "restated"


def test_it_is_listed_in_its_own_group(story_dir: Story) -> None:
    write(story_dir)
    listed = reviews.build_list(Package(story_dir.root), "technical", "inferred")
    entry = next(e for e in listed.entries if e.key == "DEC-002")
    assert entry.section == "AI-decided decisions"
    assert {"section": "AI-decided decisions", "entries": ["DEC-002"]} in listed.groups()


def test_show_marks_it(story_dir: Story) -> None:
    from eil.show import view

    write(story_dir)
    text = view(Package(story_dir.root), "technical")["text"]
    assert any(line.startswith("**DEC-002**") and "[ai-decided]" in line for line in text.splitlines())


def approve_technical(story: Story, tmp: Path) -> dict[str, Any]:
    package = Package(story.root)
    check_stage(package, "technical", judgments_path=judgments(tmp))
    listed = reviews.build_list(Package(story.root), "technical", "inferred")
    if listed.entries:
        reviews.answer(Package(story.root), CONFIG, "technical", "inferred", digest=listed.digest, by="Ada Dev", reply="ok", all_=True)
    plan = comprehension.plan(Package(story.root), "technical")
    for row in plan["levels"]:
        comprehension.record(Package(story.root), CONFIG, "technical", row["level"], "skipped", by="Ada Dev", items=[row["target"]] if row.get("target") else [])
    check_stage(Package(story.root), "technical", judgments_path=judgments(tmp))
    return records.approve(Package(story.root), CONFIG, "technical", "Ada Dev", "ok")


def test_the_approval_lists_ai_decided_decisions(story_dir: Story, tmp_path: Path) -> None:
    write(story_dir)
    result = approve_technical(story_dir, tmp_path)
    assert result["approval"]["ai_decided"] == ["DEC-002"]
    assert "AI-decided: DEC-002" in story_dir.read("technical")


def test_turning_it_into_the_developers_decision_surfaces_it_once(story_dir: Story, tmp_path: Path) -> None:
    write(story_dir)
    approve_technical(story_dir, tmp_path)
    story_dir.write("technical", story_dir.read("technical").replace("Owner: ai-decided", "Owner: Ada Dev"))
    statuses = blockstatus.block_statuses(Package(story_dir.root))["technical"]
    assert statuses["DEC-002"].status == "needs-review"
    assert [k for k, i in statuses.items() if i.status == "needs-review"] == ["DEC-002"]


@pytest.mark.parametrize("owner", ["ai-decided", "AI-decided", " ai-decided "])
def test_the_label_is_matched_whatever_its_case(owner: str) -> None:
    from eil.trace import is_ai_decided

    assert is_ai_decided(owner)
