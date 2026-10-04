"""T074: the small-story profile (determinism 52; research D-52; FR-019 to FR-022).

Authorised once by a person allowed to authorise abbreviations, with a reason. While it is active:
the Functional wireframe criterion is met by it, the AI Specification, plan and tasks are reviewed as
one ``derived`` list before implementation, plan and task entry proceed under a recorded override of
``unreviewed-ai-content``, and comprehension asks two levels. Every approval is still required.
Withdrawing it restores everything for stages not yet approved.
"""

from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any

import pytest
from eil import cli, comprehension, handoff, overview, profile, records, reviews
from eil.gates import check_stage
from eil.identity import Config
from eil.package import Package
from eil.results import EilExit

from tests.helpers.package import Story, with_functional

CONFIG = Config(
    default_developer="Ada Dev",
    approvers={s: ["Ada Dev"] for s in ("requirements", "functional", "technical", "completion")},
    abbreviation_authorisers=["Ada Dev"],
)


def codes(call: Any) -> list[str]:
    with pytest.raises(EilExit) as caught:
        call()
    return [r["code"] for r in caught.value.payload["refusals"]]


def set_profile(
    story: Story, by: str = "Ada Dev", reason: str = "One screen, detailed request"
) -> dict[str, Any]:
    return profile.set_profile(Package(story.root), CONFIG, "small", by=by, reason=reason)


def test_only_an_authoriser_with_a_reason_sets_it_once(story_dir: Story) -> None:
    with_functional(story_dir)
    assert codes(lambda: set_profile(story_dir, by="Mallory")) == ["not-an-authoriser"]
    assert codes(lambda: set_profile(story_dir, reason=" ")) == ["reason-required"]
    assert "ai-approval" in codes(lambda: set_profile(story_dir, by="Claude"))
    result = set_profile(story_dir)
    assert (
        result["profile"]["by"] == "Ada Dev" and result["profile"]["reason"] == "One screen, detailed request"
    )
    assert codes(lambda: set_profile(story_dir)) == ["profile-active"]


def test_withdraw_needs_an_active_profile(story_dir: Story) -> None:
    with_functional(story_dir)
    assert codes(
        lambda: profile.withdraw(Package(story_dir.root), CONFIG, by="Ada Dev", reason="bigger")
    ) == ["no-profile"]
    set_profile(story_dir)
    profile.withdraw(Package(story_dir.root), CONFIG, by="Ada Dev", reason="it grew")
    assert profile.active(Package(story_dir.root)) is None
    assert codes(lambda: profile.withdraw(Package(story_dir.root), CONFIG, by="Ada Dev", reason="again")) == [
        "no-profile"
    ]


def wireframe(story: Story) -> Any:
    result = check_stage(Package(story.root), "functional", write=False)
    return next(c for c in result.criteria if c.id == "FUN-G15")


def test_the_wireframe_criterion_is_met_by_the_profile_and_says_so(story_dir: Story) -> None:
    with_functional(story_dir, wireframe=None)
    assert wireframe(story_dir).status == "not-met"
    set_profile(story_dir)
    met = wireframe(story_dir)
    assert met.status == "met" and met.reason.startswith("small-story profile (Ada Dev, ")
    profile.withdraw(Package(story_dir.root), CONFIG, by="Ada Dev", reason="it grew")
    assert wireframe(story_dir).status == "not-met"


def test_comprehension_asks_explain_and_apply_only(story_dir: Story, tmp_path: Path) -> None:
    from tests.unit.test_comprehension import technical_ready

    technical_ready(story_dir, tmp_path)
    set_profile(story_dir)
    rows = {r["level"]: r for r in comprehension.plan(Package(story_dir.root), "technical")["levels"]}
    assert rows["explain"]["status"] == "ok" and rows["apply"]["status"] == "ok"
    for name in ("recognise", "trace", "evaluate"):
        assert rows[name]["status"] == "not-applicable"
        assert rows[name]["reason"].startswith("small-story profile (authorised by Ada Dev")
    result = comprehension.record(
        Package(story_dir.root), CONFIG, "technical", "explain", "understood", by="Ada Dev", items=["DEC-001"]
    )
    assert result["counts"]["not_applicable"] == 3 and result["state"] == "incomplete"
    result = comprehension.record(
        Package(story_dir.root),
        CONFIG,
        "technical",
        "apply",
        "understood",
        by="Ada Dev",
        items=[rows["apply"]["target"]],
    )
    assert result["state"] == "complete", "two answers complete the check under the profile"


@pytest.fixture
def drafted(reference_story: Story) -> Story:
    """The reference story with its AI Specification, plan and tasks drafted from the templates: nothing
    in them reviewed yet."""
    from tests.helpers.package import with_record_sections

    for stage in ("ai-spec", "plan", "tasks"):
        reference_story.write(stage, with_record_sections(reference_story.read(stage)))
    return reference_story


def test_the_derived_list_needs_the_profile_and_is_the_union(drafted: Story) -> None:
    reference_story = drafted
    package = Package(reference_story.root)
    assert codes(lambda: reviews.build_list(package, "derived", "inferred")) == ["no-profile"]
    set_profile(reference_story)
    combined = reviews.build_list(Package(reference_story.root), "derived", "inferred")
    union = [
        e.key
        for stage in ("ai-spec", "plan", "tasks")
        for e in reviews.build_list(
            Package(reference_story.root), stage, "inferred", session_view=False
        ).entries
    ]
    assert union and sorted(e.key for e in combined.entries) == sorted(union)
    assert {e.extra["stage"] for e in combined.entries} <= {"ai-spec", "plan", "tasks"}


def enter(story: Story, command: str) -> tuple[int, Any]:
    out = io.StringIO()
    code = cli.main(
        ["enter", command, "--json", "--feature-dir", str(story.root)],
        cwd=story.root,
        env={},
        stdout=out,
        stderr=io.StringIO(),
    )
    return code, json.loads(out.getvalue())


def test_plan_and_task_entry_proceed_under_the_recorded_override(reference_story: Story) -> None:
    result = set_profile(reference_story)
    override = result["override"]
    assert override["criterion"] == "unreviewed-ai-content" and override["scope"] == [
        "enter plan",
        "enter tasks",
    ]
    assert override["by"] == "Ada Dev" and override["basis"] == "small-story profile"
    for command in ("plan", "tasks"):
        result = handoff.enter(Package(reference_story.root), command)
        assert result["overrides_used"] == [override["id"]]


def test_implementation_waits_for_the_derived_list(drafted: Story) -> None:
    reference_story = drafted
    set_profile(reference_story)
    assert "unreviewed-ai-content" in codes(lambda: handoff.enter(Package(reference_story.root), "implement"))
    listed = reviews.build_list(Package(reference_story.root), "derived", "inferred")
    assert listed.entries
    reviews.answer(
        Package(reference_story.root),
        CONFIG,
        "derived",
        "inferred",
        digest=listed.digest,
        by="Ada Dev",
        reply="ok",
        all_=True,
    )
    assert reviews.build_list(Package(reference_story.root), "derived", "inferred").entries == []
    try:
        handoff.enter(Package(reference_story.root), "implement")
    except EilExit as exc:
        assert "unreviewed-ai-content" not in [r["code"] for r in exc.payload["refusals"]]


def test_status_shows_the_override_and_withdrawal_shows_it_withdrawn(reference_story: Story) -> None:
    template = (Path(__file__).resolve().parents[2] / "templates" / "s00-readme-template.md").read_text()
    override = set_profile(reference_story)["override"]
    report = overview.status(Package(reference_story.root), template)
    assert override["id"] in report["outstanding"]["overrides"]
    assert (
        report["profile"]["by"] == "Ada Dev" and report["profile"]["reason"] == "One screen, detailed request"
    )
    rendered = overview.render(Package(reference_story.root), template, "T", "Ada Dev")
    assert "Small-story profile" in rendered and "unreviewed-ai-content" in rendered
    profile.withdraw(Package(reference_story.root), CONFIG, by="Ada Dev", reason="it grew")
    report = overview.status(Package(reference_story.root), template)
    assert override["id"] not in report["outstanding"]["overrides"]
    assert report["profile"]["withdrawn"]["reason"] == "it grew"
    assert "withdrawn" in overview.render(Package(reference_story.root), template, "T", "Ada Dev")
    assert codes(lambda: reviews.build_list(Package(reference_story.root), "derived", "inferred")) == [
        "no-profile"
    ]


def test_an_approval_under_the_profile_keeps_it_after_withdrawal(story_dir: Story, tmp_path: Path) -> None:
    from eil import blockstatus

    from tests.helpers.package import requirements_doc, with_record_sections

    story_dir.write("requirements", with_record_sections(requirements_doc()))
    set_profile(story_dir)
    judged = tmp_path / "j.json"
    judged.write_text(
        json.dumps(
            {
                "stage": "requirements",
                "judgments": [
                    {"id": i, "status": "met", "reason": "ok"}
                    for i in ("REQ-G01", "REQ-G11", "REQ-G12", "REQ-G13")
                ],
            }
        )
    )
    check_stage(Package(story_dir.root), "requirements", judgments_path=judged)
    listed = reviews.build_list(Package(story_dir.root), "requirements", "inferred")
    reviews.answer(
        Package(story_dir.root),
        CONFIG,
        "requirements",
        "inferred",
        digest=listed.digest,
        by="Ada Dev",
        reply="ok",
        all_=True,
    )
    assert not blockstatus.unreviewed(Package(story_dir.root), "requirements")
    approval = records.approve(Package(story_dir.root), CONFIG, "requirements", "Ada Dev", "ok")["approval"]
    assert approval["profile"] == "small"
    profile.withdraw(Package(story_dir.root), CONFIG, by="Ada Dev", reason="it grew")
    after = Package(story_dir.root)
    assert after.state("requirements").state == "approved"
    assert after.record("requirements", "approval")["profile"] == "small"
