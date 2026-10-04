"""The browser review page's story (004 task T002).

``build(root)`` writes a story whose Requirements are approved and whose Functional draft lists five
blocks for review across its sections: two items, one prose paragraph, one table and the ``§Actors``
scaffolding entry. One block restates REQ-004 and is settled, one ``mermaid`` fence stands on its
own, and the Functional text cites ``REQ-004`` (defined once), ``REQ-099`` (defined nowhere) and
``DEC-002`` (defined twice, both times in the Requirements).

The options build the other lists the page's tests need:

* ``entries=12``: twelve items in three sections of four (determinism 59);
* ``entries=38``: a 38-entry Functional list (SC-003);
* ``entries=10``: a summary-mode list, more than ``one_at_a_time_max`` (determinism 69);
* ``changes=True``: the Functional stage approved, then two items changed, with the approval
  predating section-level records, so the ``legacy:functional`` entry is listed too (US6). A removed
  item of the stage under review is not put on its own ``changes`` list by the helper (003), so the
  removed panel is tested with a constructed list in ``test_page_render``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from tests.helpers.package import Story, approve_stages, functional_doc, install_templates, requirements_doc

BY = "Ada Dev"
FIVE = ("FR-001", "FR-002", "PROSE", "TABLE", "§Actors")
REQUIREMENT_ITEMS = "\n\n".join(
    [
        "**REQ-001**: The system detects duplicate customers on import.",
        "**REQ-002**: Analysts can dismiss a flagged pair.",
        "**REQ-003**: Every dismissal is logged.",
        "**REQ-004**: A flagged pair shows both customers side by side.",
    ]
)
DUPLICATE_DECISIONS = "\n\n".join(
    [
        "**DEC-002**: Keep the import synchronous for now.",
        "**DEC-002**: Keep the import asynchronous for now.",
    ]
)
PROSE = "Flagged pairs are shown in the order they were found, per REQ-004, REQ-099 and DEC-002."
TABLE = "| Rule | Effect |\n|---|---|\n| Same tax id | Duplicate |\n| Same email | Possible duplicate |"
RESTATED = "**FR-003**: A flagged pair shows both customers side by side. (traces: REQ-004)"
FENCE = "```mermaid\nflowchart LR\n  Import --> Flag --> Review\n```"
ACTORS = "- **Data Analyst**: reviews flagged duplicates\n\n- **Import Job**: flags duplicates"


@dataclass
class ReviewPageStory:
    story: Story
    keys: dict[str, str] = field(default_factory=dict)  # FIVE's names to their review keys

    @property
    def root(self) -> Path:
        return self.story.root

    def listed(self) -> list[str]:
        return [self.keys[name] for name in FIVE]


def _items(prefix: str, numbers: range) -> str:
    return "\n\n".join(
        f"**{prefix}-{n:03d}**: The system handles case {n}. It is stated in full. (traces: REQ-001)"
        for n in numbers
    )


def _functional_sections(entries: int | None) -> dict[str, str | None]:
    if entries is None:
        return {
            "Actors": ACTORS,
            "Functional Requirements": "\n\n".join(
                [
                    "**FR-001**: The system shall flag duplicate customers on import. (traces: REQ-001)",
                    "**FR-002**: The system shall let an analyst dismiss a flagged pair. (traces: REQ-002)",
                    RESTATED,
                    PROSE,
                ]
            ),
            "Business Rules": TABLE,
            "State and Workflow": f"A pair is flagged, then confirmed or dismissed.\n\n{FENCE}",
        }
    if entries == 12:
        return {
            "Functional Requirements": _items("FR", range(1, 5)),
            "Business Rules": _items("FR", range(5, 9)),
            "Validation": _items("FR", range(9, 13)),
        }
    return {"Functional Requirements": _items("FR", range(1, entries + 1))}


def _mark(
    story: Story, stage: str, inferred: list[str], restated: dict[str, list[str]] | None = None
) -> None:
    """Adopt every block of ``stage``, then mark ``inferred`` keys as inferred and ``restated`` keys
    as restating their cited items (as a classification would)."""
    from eil import blockstatus
    from eil.package import Package

    package = Package(story.root)
    record = blockstatus.adopt(package, stage)
    assert record is not None
    current = package.current_item_hashes()
    for key in inferred:
        record["blocks"][key] = {"hash": record["blocks"][key]["hash"], "class": "inferred"}
    for key, cites in (restated or {}).items():
        record["blocks"][key] = {
            "hash": record["blocks"][key]["hash"],
            "class": "restated",
            "cites": {i: current[i] for i in cites},
        }
    package.write_record(stage, "provenance", record)


def _keys(story: Story, stage: str) -> dict[str, str]:
    from eil.content import blocks_of
    from eil.package import Package

    out: dict[str, str] = {}
    for block in blocks_of(Package(story.root).doc(stage)):
        if block.kind == "prose" and block.text == PROSE:
            out["PROSE"] = block.key
        elif block.kind == "table":
            out["TABLE"] = block.key
        elif block.key in ("FR-001", "FR-002"):
            out[block.key] = block.key
        elif block.section == "Actors":
            out.setdefault("ACTORS_MEMBERS", "")
            out["ACTORS_MEMBERS"] = ",".join(filter(None, [out["ACTORS_MEMBERS"], block.key]))
    out["§Actors"] = "§Actors"
    return out


def _approve_requirements(story: Story) -> None:
    story.write(
        "requirements",
        requirements_doc({"Desired Outcome": REQUIREMENT_ITEMS, "Assumptions": DUPLICATE_DECISIONS}),
    )
    approve_stages(story, "requirements", by=BY)
    _mark(story, "requirements", [])


def build(
    root: Path, *, entries: int | None = None, changes: bool = False, templates: bool = True
) -> ReviewPageStory:
    """``root`` is the story directory; with ``templates`` its project (two levels up) gets the preset's
    templates, so a command-line write can regenerate the overview as in a real project."""
    if templates:
        install_templates(root.parents[1])
    story = Story(root)
    story.append("overview", f"\n- Title: {story.title}\n- Owner: {BY}\n")
    _approve_requirements(story)
    story.write("functional", functional_doc(_functional_sections(entries), wireframe=None))
    if changes:
        return _with_changes(story)
    if entries is not None:
        keys = [f"FR-{n:03d}" for n in range(1, entries + 1)]
        _mark(story, "functional", keys)
        return ReviewPageStory(story, {k: k for k in keys})
    keys = _keys(story, "functional")
    members = keys.pop("ACTORS_MEMBERS").split(",")
    _mark(
        story,
        "functional",
        ["FR-001", "FR-002", keys["PROSE"], keys["TABLE"], *members],
        {"FR-003": ["REQ-004"]},
    )
    return ReviewPageStory(story, keys)


def _with_changes(story: Story) -> ReviewPageStory:
    """Functional approved with every block settled; then FR-001 and FR-002 change, and the approval
    loses its section-level records so the legacy entry is listed."""
    import json

    from eil import recordfile
    from eil.package import Package

    _mark(story, "functional", [], {"FR-003": ["REQ-004"]})
    approve_stages(story, "functional", by=BY)
    Package(story.root).migrate("functional")
    text = story.read("functional")
    text = text.replace("flag duplicate customers on import.", "flag duplicate customers on every import.")
    text = text.replace("dismiss a flagged pair.", "dismiss or confirm a flagged pair.")
    story.write("functional", text)
    path = recordfile.path(story.root)
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    approval = data["stages"]["functional"]["approval"]
    approval.pop("section_fingerprints", None)
    path.write_text(recordfile.dumps(data), encoding="utf-8")
    return ReviewPageStory(story, {"FR-001": "FR-001", "FR-002": "FR-002", "legacy": "legacy:functional"})
