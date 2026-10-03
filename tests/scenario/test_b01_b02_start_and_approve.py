"""B-01 and B-02 (task T035): start a story, gate Requirements, record one approval.

Drives the helper directly, as the stage commands would. FR-003, FR-008, FR-009 to FR-013, FR-047,
FR-048, FR-066.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest
from eil.blocks import Doc
from eil.package import Package
from eil.trace import parse_text

from tests.conftest import EilResult
from tests.helpers.package import requirements_doc
from tests.scenario.conftest import write_judgments

pytestmark = pytest.mark.scenario

FEATURE = "specs/001-detect-duplicates"
TITLE = "Detect duplicate customers on import"
REQUIRED_HEADINGS = [
    "Background",
    "Problem Statement",
    "Desired Outcome",
    "Users and Stakeholders",
    "Use Cases",
    "In Scope",
    "Out of Scope",
    "Constraints",
    "Dependencies",
    "Risks",
    "Assumptions",
    "Open Questions",
    "Success Criteria",
    "System Context",
]
JUDGED = ["REQ-G01", "REQ-G11", "REQ-G12", "REQ-G13"]
OPEN_QUESTION = "**OQ-004**: Keep customer history? (status: open) (material: yes)"
ACCEPTED_QUESTION = (
    "**OQ-004**: Keep customer history? (status: accepted) (accepted-by: Ada Dev) (material: yes)"
)


def start(eil: Callable[..., EilResult]) -> EilResult:
    return eil(["start", "--title", TITLE, "--owner", "Ada Dev", "--feature-dir", FEATURE, "--json"])


def listing(directory: Path) -> list[str]:
    return sorted(p.relative_to(directory).as_posix() for p in directory.rglob("*"))


# ---- B-01


def test_b01_starting_a_story_creates_only_the_overview_and_requirements(
    project: Path, eil: Callable
) -> None:
    result = start(eil)
    assert result.code == 0, result.stderr
    feature = project / FEATURE
    assert listing(feature) == ["eil-record.json", "s00-README.md", "s01-requirements.md"]  # 003: the record file
    for absent in ("spec.md", "plan.md", "tasks.md", "s02-functional-spec.md", "assets"):
        assert not (feature / absent).exists(), absent


def test_b01_the_requirements_template_has_every_required_heading(project: Path, eil: Callable) -> None:
    start(eil)
    text = (project / FEATURE / "s01-requirements.md").read_text(encoding="utf-8")
    for heading in REQUIRED_HEADINGS:
        assert f"{heading}\n" in text, heading
    assert "<!-- eil:begin assessment -->" in text and "<!-- eil:begin approval -->" in text
    parsed = parse_text(text)  # the commented example items must not count as items
    assert parsed.items == [] and parsed.findings == []
    assert Doc(text).findings == []


def test_b01_the_overview_shows_the_stage_and_its_status(project: Path, eil: Callable) -> None:
    start(eil)
    overview = (project / FEATURE / "s00-README.md").read_text(encoding="utf-8")
    assert overview.splitlines()[0].startswith("<!-- eil:generated")
    assert TITLE in overview and "Ada Dev" in overview
    assert "requirements" in overview and "draft" in overview


def test_b01_the_feature_directory_is_persisted_for_later_commands(project: Path, eil: Callable) -> None:
    start(eil)
    saved = json.loads((project / ".specify" / "feature.json").read_text(encoding="utf-8"))
    assert saved["feature_directory"] == FEATURE
    assert eil(["status", "--json"]).code != 3  # now resolvable without --feature-dir


def test_b01_a_started_story_cannot_be_started_again(project: Path, eil: Callable) -> None:
    start(eil)
    before = listing(project / FEATURE)
    again = start(eil)
    assert again.code == 1 and again.refusal_codes == ["already-governed"]
    assert listing(project / FEATURE) == before


def test_b01_an_ordinary_spec_kit_feature_is_not_taken_over(project: Path, eil: Callable) -> None:
    legacy = project / "specs" / "000-legacy"
    legacy.mkdir(parents=True)
    (legacy / "spec.md").write_text("an ordinary spec\n", encoding="utf-8")
    result = eil(["start", "--title", "Legacy", "--feature-dir", "specs/000-legacy", "--json"])
    assert result.code == 1 and result.refusal_codes == ["directory-has-spec-md"]
    assert listing(legacy) == ["spec.md"]


def test_b01_the_owner_defaults_to_the_git_identity(project: Path, eil: Callable) -> None:
    """Regression: git was asked from a directory that did not exist yet, so the owner was lost."""
    result = eil(["start", "--title", TITLE, "--feature-dir", FEATURE, "--json"])
    assert result.code == 0, result.stderr
    overview = (project / FEATURE / "s00-README.md").read_text(encoding="utf-8")
    assert "- Owner: Test Developer" in overview


def test_b01_start_needs_to_know_where_the_story_lives(project: Path, eil: Callable) -> None:
    result = eil(["start", "--title", TITLE, "--json"])
    assert result.code == 2 and result.json["ok"] is False


# ---- B-02


def fill(project: Path, question: str) -> Path:
    path = project / FEATURE / "s01-requirements.md"
    path.write_text(requirements_doc({"Open Questions": question}), encoding="utf-8", newline="\n")
    return path


def check(project: Path, eil: Callable[..., EilResult]) -> EilResult:
    judgments = write_judgments(project, "requirements", JUDGED)
    return eil(["check", "--stage", "requirements", "--judgments", str(judgments), "--json"])


def approve(eil: Callable[..., EilResult], by: str, **flags: str) -> EilResult:
    argv = [
        "approve",
        "requirements",
        "--by",
        by,
        "--attestation",
        "Yes, this is the problem we intend to solve.",
    ]
    for name, value in flags.items():
        argv += [f"--{name.replace('_', '-')}", value]
    return eil([*argv, "--json"])


def test_b02_an_open_material_question_blocks_approval(project: Path, eil: Callable) -> None:
    start(eil)
    fill(project, OPEN_QUESTION)
    assert check(project, eil).code == 0
    result = approve(eil, "Ada Dev")
    assert result.code == 1 and result.refusal_codes == ["open-question"]


def test_b02_someone_who_is_not_configured_cannot_approve(project: Path, eil: Callable) -> None:
    start(eil)
    fill(project, ACCEPTED_QUESTION)
    check(project, eil)
    result = approve(eil, "Mallory")
    assert result.code == 1 and result.refusal_codes == ["not-a-confirmer"]


def test_b02_the_next_stage_cannot_start_before_approval(project: Path, eil: Callable) -> None:
    start(eil)
    fill(project, ACCEPTED_QUESTION)
    result = eil(["stage-init", "functional", "--json"])
    assert result.code == 1 and result.refusal_codes == ["stage-not-approved"]
    assert not (project / FEATURE / "s02-functional-spec.md").exists()


def test_b02_an_accepted_question_lets_one_confirmation_approve(project: Path, eil: Callable) -> None:
    start(eil)
    path = fill(project, ACCEPTED_QUESTION)
    assert check(project, eil).json["ok"] is True
    result = approve(eil, "Ada Dev", played_back_to="Sam (business), Priya (QA)")
    assert result.code == 0, result.stdout + result.stderr
    saved = json.loads((path.parent / "eil-record.json").read_text(encoding="utf-8"))  # 003: the record file
    record = saved["stages"]["requirements"]["approval"]
    assert "Approved by Ada Dev" in path.read_text(encoding="utf-8")  # the document keeps one readable line
    assert record["by"] == "Ada Dev" and record["stage"] == "requirements"
    assert record["fingerprint"].startswith("sha256:") and record["at"].endswith("Z")
    assert record["attestation"].startswith("Yes, this is the problem")
    assert record["played_back_to"] == "Sam (business), Priya (QA)"


def test_b02_after_approval_the_stage_reads_as_approved(project: Path, eil: Callable) -> None:
    start(eil)
    fill(project, ACCEPTED_QUESTION)
    check(project, eil)
    assert Package(project / FEATURE).state("requirements").state == "in-review"
    assert approve(eil, "Ada Dev").code == 0
    assert Package(project / FEATURE).state("requirements").state == "approved"
    assert Package(project / FEATURE).current_stage() == "functional"


def test_b02_editing_after_approval_needs_a_new_confirmation(project: Path, eil: Callable) -> None:
    start(eil)
    path = fill(project, ACCEPTED_QUESTION)
    check(project, eil)
    approve(eil, "Ada Dev")
    path.write_text(path.read_text(encoding="utf-8") + "\nAn afterthought.\n", encoding="utf-8")
    result = eil(["stage-init", "functional", "--json"])
    assert result.code == 1 and result.refusal_codes == ["stage-not-approved"]


def test_b02_an_ai_cannot_record_an_approval(project: Path, eil: Callable) -> None:
    start(eil)
    fill(project, ACCEPTED_QUESTION)
    check(project, eil)
    result = approve(eil, "Claude")
    assert result.code == 1 and "ai-approval" in result.refusal_codes


def test_b02_an_approval_needs_the_humans_own_words(project: Path, eil: Callable) -> None:
    start(eil)
    fill(project, ACCEPTED_QUESTION)
    check(project, eil)
    result = eil(["approve", "requirements", "--by", "Ada Dev", "--attestation", "  ", "--json"])
    assert result.code == 1 and result.refusal_codes == ["attestation-required"]
