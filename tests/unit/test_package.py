"""Feature-directory resolution, the governed test, document names and derived stage state
(task T023; FR-043, FR-044, FR-069, FR-070)."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from eil import package
from eil.fingerprint import fingerprint_file
from eil.package import Package, resolve_feature_dir

from tests.helpers.package import DOC_NAMES, Story, record_block, region

# ---- feature directory resolution


def project_with(tmp_path: Path, feature_json: str | None = None) -> Path:
    (tmp_path / ".specify").mkdir()
    if feature_json is not None:
        (tmp_path / ".specify" / "feature.json").write_text(json.dumps({"feature_directory": feature_json}))
    return tmp_path


def test_explicit_argument_wins(tmp_path: Path) -> None:
    project = project_with(tmp_path, "specs/from-json")
    env = {"SPECIFY_FEATURE_DIRECTORY": "specs/from-env"}
    assert resolve_feature_dir(project, "specs/from-arg", env) == project / "specs" / "from-arg"


def test_environment_beats_feature_json(tmp_path: Path) -> None:
    project = project_with(tmp_path, "specs/from-json")
    assert resolve_feature_dir(project, None, {"SPECIFY_FEATURE_DIRECTORY": "specs/from-env"}) == (
        project / "specs" / "from-env"
    )


def test_feature_json_is_the_last_resort(tmp_path: Path) -> None:
    project = project_with(tmp_path, "specs/from-json")
    assert resolve_feature_dir(project, None, {}) == project / "specs" / "from-json"


def test_absolute_paths_are_kept(tmp_path: Path) -> None:
    project = project_with(tmp_path)
    assert resolve_feature_dir(project, str(tmp_path / "elsewhere"), {}) == tmp_path / "elsewhere"


def test_nothing_resolves_to_none(tmp_path: Path) -> None:
    assert resolve_feature_dir(project_with(tmp_path), None, {}) is None


def test_an_unreadable_feature_json_resolves_to_none(tmp_path: Path) -> None:
    project = project_with(tmp_path)
    (project / ".specify" / "feature.json").write_text("{ nope")
    assert resolve_feature_dir(project, None, {}) is None


def test_an_empty_environment_value_is_ignored(tmp_path: Path) -> None:
    project = project_with(tmp_path, "specs/from-json")
    assert (
        resolve_feature_dir(project, None, {"SPECIFY_FEATURE_DIRECTORY": ""})
        == project / "specs" / "from-json"
    )


# ---- governed test (FR-069)


def test_a_directory_is_governed_iff_it_has_the_overview(tmp_path: Path) -> None:
    assert not Package(tmp_path).governed
    (tmp_path / "s00-README.md").write_text("x")
    assert Package(tmp_path).governed


def test_a_missing_directory_is_not_governed(tmp_path: Path) -> None:
    assert not Package(tmp_path / "nope").governed


def test_an_ordinary_spec_kit_feature_is_not_governed(tmp_path: Path) -> None:
    for name in ("spec.md", "plan.md", "tasks.md"):
        (tmp_path / name).write_text("x")
    assert not Package(tmp_path).governed


# ---- documents (FR-070)


def test_stage_document_names_match_the_s_prefix() -> None:
    assert list(package.STAGES) == [
        "requirements",
        "functional",
        "technical",
        "ai-spec",
        "plan",
        "tasks",
        "verification",
        "completion",
    ]
    for stage, name in package.DOC_FILES.items():
        assert re.fullmatch(r"s0[1-8]-[a-z-]+\.md", name), (stage, name)
    assert package.DOC_FILES == {k: v for k, v in DOC_NAMES.items() if k != "overview"}
    assert package.OVERVIEW == "s00-README.md"


def test_a_bare_number_is_never_a_stage_document(tmp_path: Path) -> None:
    (tmp_path / "s00-README.md").write_text("x")
    for name in ("01-requirements.md", "1-requirements.md", "requirements.md", "s1-requirements.md"):
        (tmp_path / name).write_text("x")
    (tmp_path / "s01-requirements.md").write_text("x")
    assert Package(tmp_path).existing_stages() == ["requirements"]


def test_stage_document_paths(tmp_path: Path) -> None:
    pkg = Package(tmp_path)
    assert pkg.doc_path("technical") == tmp_path / "s03-technical-spec.md"
    assert pkg.overview_path == tmp_path / "s00-README.md"


def test_unknown_stage_is_a_keyerror(tmp_path: Path) -> None:
    with pytest.raises(KeyError):
        Package(tmp_path).doc_path("design")


def test_the_alias_table_is_exactly_three() -> None:
    assert package.ALIASES == {
        "spec.md": "s04-ai-spec.md",
        "plan.md": "s05-plan.md",
        "tasks.md": "s06-tasks.md",
    }


def test_only_four_stages_are_approvable() -> None:
    assert package.APPROVABLE == ("requirements", "functional", "technical", "completion")


# ---- derived stage state


def approve(story: Story, stage: str, heading: bool = True, **extra: object) -> None:
    # The heading is content (real templates carry it), so add it before fingerprinting.
    if heading:
        story.append(stage, "\n## Approval\n")
    record = {
        "stage": stage,
        "by": "Ada",
        "at": "2026-09-25T10:00:00Z",
        "fingerprint": fingerprint_file(story.path(stage)),
        "attestation": "yes",
        "upstream": {},
        **extra,
    }
    story.append(stage, region("approval", record))


def assess(
    story: Story, stage: str, statuses: list[str], fingerprint: str | None = None, heading: bool = True
) -> None:
    if heading:
        story.append(stage, "\n## Quality Assessment\n")
    record = {
        "stage": stage,
        "fingerprint": fingerprint or fingerprint_file(story.path(stage)),
        "criteria": [
            {"id": f"X-G{i:02d}", "kind": "structural", "status": s, "reason": ""}
            for i, s in enumerate(statuses)
        ],
    }
    story.append(stage, region("assessment", record))


def test_no_document_is_not_started(story_dir: Story) -> None:
    assert Package(story_dir.root).state("functional").state == "not-started"


def test_a_document_with_no_approval_or_assessment_is_a_draft(story_dir: Story) -> None:
    story_dir.write("requirements", "# Requirements\n")
    assert Package(story_dir.root).state("requirements").state == "draft"


def test_a_met_current_assessment_is_in_review(story_dir: Story) -> None:
    story_dir.write("requirements", "# Requirements\n")
    assess(story_dir, "requirements", ["met", "overridden"])
    assert Package(story_dir.root).state("requirements").state == "in-review"


def test_an_unmet_criterion_keeps_it_a_draft(story_dir: Story) -> None:
    story_dir.write("requirements", "# Requirements\n")
    assess(story_dir, "requirements", ["met", "not-met"])
    assert Package(story_dir.root).state("requirements").state == "draft"


def test_a_stale_assessment_is_a_draft(story_dir: Story) -> None:
    story_dir.write("requirements", "# Requirements\n")
    assess(story_dir, "requirements", ["met"], fingerprint="sha256:" + "0" * 64)
    assert Package(story_dir.root).state("requirements").state == "draft"


def test_a_valid_approval_is_approved(story_dir: Story) -> None:
    story_dir.write("requirements", "# Requirements\n\n**REQ-001**: a\n")
    approve(story_dir, "requirements")
    state = Package(story_dir.root).state("requirements")
    assert state.state == "approved"
    assert state.approval and state.approval["by"] == "Ada"


def test_editing_the_content_after_approval_needs_re_review(story_dir: Story) -> None:
    story_dir.write("requirements", "# Requirements\n\n**REQ-001**: a\n")
    approve(story_dir, "requirements")
    path = story_dir.path("requirements")
    path.write_text(path.read_text().replace("**REQ-001**: a", "**REQ-001**: b"))
    state = Package(story_dir.root).state("requirements")
    assert state.state == "needs-re-review"
    assert "content" in state.reason


def test_a_formatting_only_edit_keeps_the_approval(story_dir: Story) -> None:
    story_dir.write("requirements", "# Requirements\n\n**REQ-001**: a\n")
    approve(story_dir, "requirements")
    path = story_dir.path("requirements")
    path.write_bytes(path.read_bytes().replace(b"\n", b"  \r\n"))
    assert Package(story_dir.root).state("requirements").state == "approved"


def test_rewriting_the_assessment_does_not_disturb_an_approval(story_dir: Story) -> None:
    story_dir.write("requirements", "# Requirements\n\n## Quality Assessment\n\n## Approval\n")
    approve(story_dir, "requirements", heading=False)
    assess(story_dir, "requirements", ["met"], heading=False)
    assert Package(story_dir.root).state("requirements").state == "approved"


def test_a_changed_upstream_document_needs_re_review(story_dir: Story) -> None:
    story_dir.write("requirements", "# Requirements\n\n**REQ-001**: a\n")
    story_dir.write("functional", "# Functional\n\n**FR-001**: b (traces: REQ-001)\n")
    approve(
        story_dir, "functional", upstream={"requirements": fingerprint_file(story_dir.path("requirements"))}
    )
    assert Package(story_dir.root).state("functional").state == "approved"
    path = story_dir.path("requirements")
    path.write_text(path.read_text().replace("REQ-001**: a", "REQ-001**: changed"))
    state = Package(story_dir.root).state("functional")
    assert state.state == "needs-re-review"
    assert "requirements" in state.reason


def test_a_missing_upstream_document_needs_re_review(story_dir: Story) -> None:
    story_dir.write("functional", "# Functional\n")
    approve(story_dir, "functional", upstream={"requirements": "sha256:" + "1" * 64})
    assert Package(story_dir.root).state("functional").state == "needs-re-review"


def test_malformed_approval_json_is_no_approval_and_is_reported(story_dir: Story) -> None:
    story_dir.write(
        "requirements",
        "# R\n\n<!-- eil:begin approval -->\n```json\n{ nope\n```\n<!-- eil:end approval -->\n",
    )
    state = Package(story_dir.root).state("requirements")
    assert state.state == "draft"
    assert [f.code for f in state.findings] == ["malformed-approval"]


def test_an_unmatched_region_marker_reads_as_no_approval(story_dir: Story) -> None:
    story_dir.write("requirements", "# R\n\n<!-- eil:begin approval -->\n```json\n{}\n```\n")
    state = Package(story_dir.root).state("requirements")
    assert state.state == "draft"
    assert "malformed-region" in [f.code for f in state.findings]


def test_the_abbreviation_flag_is_orthogonal(story_dir: Story) -> None:
    story_dir.write(
        "requirements",
        "# R\n\n" + record_block("abbreviation", {"stage": "requirements", "by": "Lead", "reason": "spike"}),
    )
    state = Package(story_dir.root).state("requirements")
    assert state.abbreviated and state.state == "draft"


def test_a_non_utf8_document_is_a_draft_with_a_finding(story_dir: Story) -> None:
    story_dir.path("requirements").write_bytes(b"\xff\xfe bad")
    state = Package(story_dir.root).state("requirements")
    assert state.state == "draft"
    assert [f.code for f in state.findings] == ["not-utf8"]


# ---- current stage rule


def test_current_stage_is_requirements_when_nothing_exists(story_dir: Story) -> None:
    assert Package(story_dir.root).current_stage() == "requirements"


def test_current_stage_is_the_first_unapproved_stage(story_dir: Story) -> None:
    story_dir.write("requirements", "# R\n")
    approve(story_dir, "requirements")
    story_dir.write("functional", "# F\n")
    assert Package(story_dir.root).current_stage() == "functional"


def test_a_stage_needing_re_review_becomes_current_again(story_dir: Story) -> None:
    story_dir.write("requirements", "# R\n\n**REQ-001**: a\n")
    approve(story_dir, "requirements")
    story_dir.write("functional", "# F\n")
    approve(
        story_dir, "functional", upstream={"requirements": fingerprint_file(story_dir.path("requirements"))}
    )
    story_dir.append("requirements", "\nA change.\n")
    assert Package(story_dir.root).current_stage() == "requirements"


def test_current_stage_moves_to_the_ai_spec_after_technical(story_dir: Story) -> None:
    for stage in ("requirements", "functional", "technical"):
        story_dir.write(stage, f"# {stage}\n")
        approve(story_dir, stage)
    assert Package(story_dir.root).current_stage() == "ai-spec"


def test_states_of_all_stages_are_listed_in_order(story_dir: Story) -> None:
    story_dir.write("requirements", "# R\n")
    states = Package(story_dir.root).states()
    assert list(states) == list(package.STAGES)
    assert states["requirements"].state == "draft" and states["completion"].state == "not-started"
