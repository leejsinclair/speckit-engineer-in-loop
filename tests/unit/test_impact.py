"""Impact of an upstream change (task T101; FR-043, FR-044, determinism 1).

A changed item marks the stages that depend on it for re-review and names exactly the affected items.
Formatting never counts, and nothing depends on a clock or a path, so a clone keeps its approvals.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from eil import impact, overview
from eil.package import Package

from tests.helpers.package import Story, approve_stages, tasks_doc, with_ai_spec


def package_of(story: Story) -> Package:
    return Package(story.root)


def approved_story(story: Story) -> Package:
    with_ai_spec(story)
    story.write("plan", "# Plan\n")
    story.write("tasks", tasks_doc())
    return package_of(story)


def edit(story: Story, stage: str, old: str, new: str) -> None:
    text = story.read(stage)
    assert old in text, old
    story.write(stage, text.replace(old, new, 1))


def test_an_untouched_story_has_nothing_affected(story_dir: Story) -> None:
    assert impact.affected(approved_story(story_dir)) == {}


def test_a_changed_functional_requirement_affects_what_traces_to_it_and_nothing_else(
    story_dir: Story,
) -> None:
    package = approved_story(story_dir)
    edit(
        story_dir,
        "functional",
        "flag duplicate customers on import",
        "flag likely duplicate customers on import",
    )
    affected = impact.affected(package)
    assert set(affected["functional"]) == {"FR-001", "ART-002", "ART-003"}, "the diagrams that trace to it"
    assert set(affected["technical"]) == {"DEC-001", "ART-004", "ART-005", "ART-006", "ART-007"}
    assert "NFR-001" not in affected["functional"], "an item nothing changed is not affected"
    assert "AIS-001" in affected["ai-spec"] and "AIS-003" in affected["ai-spec"], "through DEC-001 and FR-001"
    assert "AIS-011" not in affected["ai-spec"], "AIS-011 traces only to REQ-001, which did not change"
    assert "T001" in affected["tasks"]
    assert "requirements" not in affected


def test_the_downstream_stages_are_marked_and_the_affected_items_are_listed_in_status(
    story_dir: Story,
) -> None:
    package = approved_story(story_dir)
    edit(
        story_dir,
        "functional",
        "flag duplicate customers on import",
        "flag likely duplicate customers on import",
    )
    report = overview.status(package)
    assert report["stages"]["functional"]["state"] == "needs-re-review"
    assert report["stages"]["functional"]["affected_items"] == ["FR-001", "ART-002", "ART-003"]
    assert report["stages"]["technical"]["state"] == "needs-re-review"
    assert set(report["stages"]["technical"]["affected_items"]) >= {"DEC-001", "ART-004"}
    assert report["stages"]["requirements"]["state"] == "approved"
    assert "affected_items" not in report["stages"]["requirements"]


def test_only_the_stages_that_hold_an_affected_item_get_a_list_but_all_downstream_approvals_wait(
    story_dir: Story,
) -> None:
    package = approved_story(story_dir)
    edit(
        story_dir,
        "requirements",
        "**REQ-001**: The system detects duplicate customers on import.",
        "**REQ-001**: The system detects duplicate customers at import time.",
    )
    report = overview.status(package)
    for stage in ("requirements", "functional", "technical"):
        assert report["stages"][stage]["state"] == "needs-re-review"
    assert report["stages"]["requirements"]["affected_items"] == ["REQ-001", "ART-001"]
    assert "FR-001" in report["stages"]["functional"]["affected_items"]
    assert "AIS-011" in impact.affected(package)["ai-spec"]


def test_a_removed_item_still_affects_what_traced_to_it(story_dir: Story) -> None:
    package = approved_story(story_dir)
    edit(
        story_dir, "technical", "**ART-007**: Duplicate match data (traces: DEC-001) (store: Customer DB)", ""
    )
    affected = impact.affected(package)
    assert "AIS-014" in affected["ai-spec"] and "T003" in affected["tasks"]


def test_a_new_item_in_an_approved_stage_is_a_change_to_that_stage(story_dir: Story) -> None:
    package = approved_story(story_dir)
    edit(
        story_dir,
        "functional",
        "**NFR-001**",
        "**FR-002**: The system shall log each match. (traces: REQ-001)\n\n**NFR-001**",
    )
    assert impact.affected(package)["functional"] == ["FR-002"]


def test_a_changed_diagram_affects_the_items_that_cite_it(story_dir: Story) -> None:
    package = approved_story(story_dir)
    edit(
        story_dir, "technical", '"REST", "[existing] Accepts imports"', '"gRPC", "[existing] Accepts imports"'
    )
    affected = impact.affected(package)
    assert affected["technical"] == ["ART-004"]
    assert "AIS-013" in affected["ai-spec"] and "AIS-003" not in affected["ai-spec"]


def test_formatting_only_changes_affect_nothing_and_keep_every_approval(story_dir: Story) -> None:
    package = approved_story(story_dir)
    text = story_dir.read("functional")
    story_dir.path("functional").write_bytes(text.replace("\n", "  \r\n").encode())
    assert impact.affected(package) == {}
    assert package.state("functional").state == "approved" and package.state("technical").state == "approved"


def test_a_tag_change_is_not_a_change_to_an_item(story_dir: Story) -> None:
    package = approved_story(story_dir)
    edit(story_dir, "functional", "on import. (traces: REQ-001)", "on import. (traces: REQ-001) [ai-draft]")
    assert impact.affected(package) == {}


def test_a_clone_elsewhere_keeps_its_approvals_and_reports_the_same_impact(
    story_dir: Story, tmp_path: Path
) -> None:
    package = approved_story(story_dir)
    copy = tmp_path / "elsewhere" / "specs" / "001-story"
    shutil.copytree(story_dir.root, copy, symlinks=True)
    clone = Package(copy)
    assert {s: clone.state(s).state for s in ("requirements", "functional", "technical")} == {
        "requirements": "approved",
        "functional": "approved",
        "technical": "approved",
    }
    assert impact.affected(clone) == impact.affected(package) == {}


def test_approving_the_changed_stage_again_clears_its_own_list_and_leaves_the_rest(story_dir: Story) -> None:
    package = approved_story(story_dir)
    edit(
        story_dir,
        "functional",
        "flag duplicate customers on import",
        "flag likely duplicate customers on import",
    )
    approve_stages(story_dir, "functional")
    affected = impact.affected(package)
    assert "functional" not in affected, "the new approval records the new hash"
    assert package.state("technical").state == "needs-re-review", (
        "technical still has to be reviewed against it"
    )


def test_an_unapproved_upstream_stage_has_no_baseline_to_compare_with(story_dir: Story) -> None:
    with_ai_spec(story_dir)
    text = story_dir.read("technical")
    start = text.index("<!-- eil:begin approval -->")
    end = text.index("<!-- eil:end approval -->")
    story_dir.write("technical", text[:start] + "<!-- eil:begin approval -->\n" + text[end:])
    assert impact.affected(package_of(story_dir)) == {}
