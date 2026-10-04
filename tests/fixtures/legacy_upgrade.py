"""A story shaped like the trial snapshot ``bd7a0d5`` (T003; research D-56, B-30).

The reference story, approved through Technical, with three things the trial had on upgrade:

* the Functional and Technical approvals carry ``items`` but no ``section_fingerprints`` (an
  approval from before section-level records);
* since that approval, one prose paragraph and one sequence diagram changed in each;
* the AI's judgments are recorded in each one's ``assessment`` record, as 001 wrote them (no per-criterion
  ``basis``, which 002 added);
* two plan blocks, never approved, still carry the old ``[ai-draft]`` tag.

Nothing here has a provenance region yet: the first writing call adopts.
"""

from __future__ import annotations

import json
from pathlib import Path

from tests.fixtures import reference_story
from tests.helpers.package import Story

# (stage, old text, new text): one prose paragraph and one sequence diagram per approved stage.
CHANGES = {
    "functional": (
        (
            "Two customers with the same tax id are duplicates.",
            "Two customers with the same tax id or email are duplicates.",
        ),
        ("Analyst->>System: Upload customer file", "Analyst->>System: Upload a customer file"),
    ),
    "technical": (
        (
            "Each analysis logs its duration and match count.",
            "Each analysis logs its duration, match count and file size.",
        ),
        ("API->>Worker: Queue analysis", "API->>Worker: Queue the analysis"),
    ),
}
# The sections and items those changes touch.
CHANGED_SECTIONS = {"functional": "Business Rules", "technical": "Observability"}
CHANGED_DIAGRAMS = {"functional": "ART-002", "technical": "ART-006"}
TAGGED_PLAN = ("Summary follows decision 1.", "Queue Design follows decision 4.")


def _record_judgments(story: Story, stage: str) -> None:
    from eil.gates import JUDGMENT, check_stage, criteria_for
    from eil.package import Package

    ids = [c.id for c in criteria_for(stage) if c.kind == JUDGMENT]
    path = story.root.parent / f"{story.root.name}-{stage}-judgments.json"
    body = {
        "stage": stage,
        "judgments": [{"id": i, "status": "met", "reason": f"assessed {i}"} for i in ids],
        "assessment": {"ambiguity": [f"{stage} wording reviewed"]},
    }
    path.write_text(json.dumps(body), encoding="utf-8")
    try:
        check_stage(Package(story.root), stage, judgments_path=path)
    finally:
        path.unlink()


def _as_001_era(story: Story, stage: str) -> None:
    """An assessment written before 002's per-criterion basis (D-29): verdicts carry no ``basis``."""
    from eil.package import Package

    package = Package(story.root)
    record = package.record(stage, "assessment") or {}
    for criterion in record.get("criteria", []):
        criterion.pop("basis", None)
    package.write_record(stage, "assessment", record)


def _drop_section_fingerprints(story: Story, stage: str) -> None:
    from eil.package import Package

    package = Package(story.root)
    approval = dict(package.record(stage, "approval") or {})
    approval.pop("section_fingerprints", None)
    package.write_record(stage, "approval", approval)


def build(root: Path) -> Story:
    """Write the legacy-upgrade story at ``root``."""
    story = reference_story.build(root)
    for stage in ("functional", "technical"):
        _record_judgments(story, stage)
        _as_001_era(story, stage)
        _drop_section_fingerprints(story, stage)
        text = story.read(stage)
        for old, new in CHANGES[stage]:
            assert old in text, f"{old!r} not in {stage}"
            text = text.replace(old, new, 1)
        story.write(stage, text)
    plan = story.read("plan")
    for line in TAGGED_PLAN:
        assert line in plan, f"{line!r} not in the plan"
        plan = plan.replace(line, line + " [ai-draft]", 1)
    story.write("plan", plan)
    return story
