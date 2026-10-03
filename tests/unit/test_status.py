"""``status``: derived state, outstanding items and the next action (task T052; FR-054, FR-056,
determinism 9, contracts/cli.md §status --json)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from eil import overview
from eil.fingerprint import fingerprint_file
from eil.package import STAGES, Package

from tests.helpers.package import Story, item_hashes, record_block, region, requirements_doc

TEMPLATE = (Path(__file__).resolve().parents[2] / "templates" / "s00-readme-template.md").read_text(
    encoding="utf-8"
)


def status(story: Story, template: str | None = TEMPLATE) -> dict[str, Any]:
    return overview.status(Package(story.root), template)


def snapshot(root: Path) -> dict[str, bytes]:
    return {str(p.relative_to(root)): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


def approve_requirements(story: Story) -> None:
    text = requirements_doc()
    story.write("requirements", text)
    record = {
        "stage": "requirements",
        "by": "Ada Dev",
        "at": "2026-09-25T10:14:03Z",
        "fingerprint": fingerprint_file(story.path("requirements")),
        "attestation": "yes",
        "upstream": {},
        "items": item_hashes(text),
        "overrides_used": [],
    }
    story.write(
        "requirements",
        text.replace(
            "<!-- eil:begin approval -->\n<!-- eil:end approval -->", region("approval", record).rstrip("\n")
        ),
    )


# ---- shape


def test_the_documented_top_level_keys(story_dir: Story) -> None:
    story_dir.write("requirements", requirements_doc())
    result = status(story_dir)
    assert {
        "governed",
        "feature_dir",
        "title",
        "owner",
        "current_stage",
        "stages",
        "outstanding",
        "comprehension",
        "artifacts",
        "aliases",
        "overview",
        "next",
    } <= set(result)
    assert result["governed"] is True
    assert result["current_stage"] == "requirements"


def test_every_stage_is_listed_in_order_with_its_state(story_dir: Story) -> None:
    story_dir.write("requirements", requirements_doc())
    stages = status(story_dir)["stages"]
    assert list(stages) == list(STAGES)
    assert stages["requirements"]["state"] == "draft" and stages["requirements"]["abbreviated"] is False
    assert stages["functional"] == {"state": "not-started", "abbreviated": False}


def test_an_approved_stage_carries_who_when_and_the_fingerprint(story_dir: Story) -> None:
    approve_requirements(story_dir)
    approval = status(story_dir)["stages"]["requirements"]["approval"]
    assert approval["by"] == "Ada Dev" and approval["at"] == "2026-09-25T10:14:03Z"
    assert approval["fingerprint"] == Package(story_dir.root).fingerprint("requirements")


def test_a_stage_needing_re_review_says_why(story_dir: Story) -> None:
    approve_requirements(story_dir)
    story_dir.append("requirements", "\nA later edit.\n")
    entry = status(story_dir)["stages"]["requirements"]
    assert entry["state"] == "needs-re-review" and "content" in entry["reason"]


def test_title_and_owner_come_from_the_overview(story_dir: Story) -> None:
    story_dir.write("requirements", requirements_doc())
    package = Package(story_dir.root)
    overview.write(package, TEMPLATE, "Detect duplicates", "Ada Dev")
    result = status(story_dir)
    assert (result["title"], result["owner"]) == ("Detect duplicates", "Ada Dev")


def test_the_feature_directory_is_reported(story_dir: Story) -> None:
    assert status(story_dir)["feature_dir"].endswith("001-story")


# ---- outstanding


def test_outstanding_items_are_listed_by_id(story_dir: Story) -> None:
    question = "**OQ-004**: Keep history? (status: open) (material: yes)"
    accepted = "**OQ-005**: Naming? (status: accepted) (accepted-by: Ada Dev) (material: no)"
    challenge = record_block(
        "challenge",
        {"id": "CH-002", "stage": "requirements", "status": "open", "target": "OQ-004", "text": "x"},
    )
    override = record_block(
        "override",
        {"id": "OVR-001", "stage": "requirements", "criterion": "REQ-G06", "by": "Ada Dev", "reason": "r"},
    )
    story_dir.write(
        "requirements",
        requirements_doc({"Open Questions": f"{question}\n\n{accepted}"}, extra=f"{challenge}\n{override}"),
    )
    outstanding = status(story_dir)["outstanding"]
    assert outstanding == {
        "open_questions": ["OQ-004"],
        "open_challenges": ["CH-002"],
        "low_challenges": [],
        "deferred_challenges": [],
        "pending_clarifications": [],
        "accepted_risks": ["OQ-005"],
        "overrides": ["OVR-001"],
    }


def test_pending_clarifications_are_listed(story_dir: Story) -> None:
    story_dir.write("ai-spec", "# AI\n\n**AIS-003**: An answer [pending-clarification]\n")
    assert status(story_dir)["outstanding"]["pending_clarifications"] == ["AIS-003"]


# ---- artifacts, comprehension, aliases


def test_artifacts_carry_their_kind_stage_form_and_state(story_dir: Story) -> None:
    story_dir.write("requirements", requirements_doc())
    assert status(story_dir)["artifacts"] == [
        {"id": "ART-001", "kind": "c4-context", "stage": "requirements", "form": "inline", "state": "ok"}
    ]


def test_comprehension_is_missing_until_a_record_exists(story_dir: Story) -> None:
    story_dir.write("functional", "# F\n")
    assert status(story_dir)["comprehension"]["functional"]["state"] == "missing"


def test_comprehension_counts_come_from_the_current_record(story_dir: Story) -> None:
    story_dir.write("functional", "# F\n\n## Comprehension Check\n")
    fp = fingerprint_file(story_dir.path("functional"))
    levels = [
        {"level": lv, "outcome": out, "attempts": 1, "items": []}
        for lv, out in [
            ("recognise", "understood"),
            ("explain", "coached"),
            ("apply", "skipped"),
            ("trace", "understood"),
            ("evaluate", "understood"),
        ]
    ]
    record = {"stage": "functional", "fingerprint": fp, "taken_by": "Ada Dev", "levels": levels}
    story_dir.append("functional", region("comprehension", record))
    result = status(story_dir)["comprehension"]["functional"]
    assert result["state"] == "complete"
    assert result["counts"] == {
        "understood": 3,
        "coached": 1,
        "revealed": 0,
        "skipped": 1,
        "not_applicable": 0,
        "own_decision": 0,  # 003 D-54
    }


def test_a_comprehension_record_for_an_older_version_is_stale(story_dir: Story) -> None:
    story_dir.write("functional", "# F\n\n## Comprehension Check\n")
    record = {"stage": "functional", "fingerprint": "sha256:" + "0" * 64, "taken_by": "A", "levels": []}
    story_dir.append("functional", region("comprehension", record))
    assert status(story_dir)["comprehension"]["functional"]["state"] == "stale"


def test_aliases_are_listed_even_when_there_are_none(story_dir: Story) -> None:
    assert status(story_dir)["aliases"] == []


# ---- the overview (FR-056)


def test_status_says_whether_the_overview_matches_the_records(story_dir: Story) -> None:
    story_dir.write("requirements", requirements_doc())
    package = Package(story_dir.root)
    overview.write(package, TEMPLATE, "Dup", "Ada Dev")
    assert status(story_dir)["overview"] == {"current": True}
    story_dir.write("overview", story_dir.read("overview").replace("| draft |", "| approved |"))
    result = status(story_dir)["overview"]
    assert result["current"] is False and "hand-edited" in result["message"]


def test_without_a_template_the_overview_check_is_skipped(story_dir: Story) -> None:
    assert status(story_dir, template=None)["overview"] == {"current": None}


# ---- read-only (determinism 9)


def test_status_writes_nothing_and_changes_no_fingerprint(story_dir: Story) -> None:
    approve_requirements(story_dir)
    package = Package(story_dir.root)
    overview.write(package, TEMPLATE, "Dup", "Ada Dev")
    before, fingerprints = snapshot(story_dir.root), {s: package.fingerprint(s) for s in STAGES}
    status(story_dir)
    status(story_dir)
    assert snapshot(story_dir.root) == before
    assert {s: package.fingerprint(s) for s in STAGES} == fingerprints


# ---- the single next action


def test_next_for_a_draft_says_how_many_criteria_are_unmet(story_dir: Story) -> None:
    story_dir.write("requirements", requirements_doc({"Constraints": None}))
    assert "requirements" in status(story_dir)["next"] and "REQ-G06" in status(story_dir)["next"]


def test_next_when_only_the_judgments_are_missing_says_to_run_the_check(story_dir: Story) -> None:
    story_dir.write("requirements", requirements_doc())
    text = status(story_dir)["next"]
    assert "judgment" in text and "eil check" in text


def test_next_for_a_stage_ready_for_approval(story_dir: Story) -> None:
    from eil.gates import check_stage

    story_dir.write("requirements", requirements_doc())
    import json

    judged = story_dir.root / "j.json"
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
    assert status(story_dir)["next"] == "Approve requirements with /speckit-eil-approve."


def test_next_names_an_open_challenge_first(story_dir: Story) -> None:
    challenge = record_block(
        "challenge",
        {"id": "CH-002", "stage": "requirements", "status": "open", "target": "REQ-001", "text": "x"},
    )
    story_dir.write("requirements", requirements_doc(extra=challenge))
    assert status(story_dir)["next"].startswith("Answer challenge CH-002")


def test_next_for_a_stage_that_has_not_started(story_dir: Story) -> None:
    approve_requirements(story_dir)
    assert status(story_dir)["next"] == "Start functional: run /speckit-eil-2-functional."


def test_next_for_a_stage_needing_re_review(story_dir: Story) -> None:
    approve_requirements(story_dir)
    story_dir.append("requirements", "\nedit\n")
    next_text = status(story_dir)["next"]
    assert next_text.startswith("Re-review requirements")
    assert "/speckit-eil-accept" in next_text and "/speckit-eil-approve" in next_text


def test_next_is_a_single_sentence(story_dir: Story) -> None:
    story_dir.write("requirements", requirements_doc())
    assert "\n" not in status(story_dir)["next"]


# ---- the structured next action (used by /speckit-eil-next)


def next_action(story: Story) -> dict[str, Any]:
    return status(story)["next_action"]


def test_next_action_carries_kind_stage_command_and_the_same_sentence(story_dir: Story) -> None:
    story_dir.write("requirements", requirements_doc())
    result = status(story_dir)
    assert set(result["next_action"]) == {"kind", "stage", "command", "message", "purpose"}
    assert result["next_action"]["message"] == result["next"]


def test_a_stage_not_started_is_drafting_with_the_numbered_command(story_dir: Story) -> None:
    approve_requirements(story_dir)
    assert next_action(story_dir) == {
        "kind": "draft",
        "stage": "functional",
        "command": "/speckit-eil-2-functional",
        "message": "Start functional: run /speckit-eil-2-functional.",
        "purpose": "awareness",
    }


def test_missing_judgments_are_a_check_the_ai_may_run(story_dir: Story) -> None:
    story_dir.write("requirements", requirements_doc())
    action = next_action(story_dir)
    assert (action["kind"], action["stage"]) == ("check", "requirements")


def test_an_unmet_gate_is_more_drafting(story_dir: Story) -> None:
    story_dir.write("requirements", requirements_doc({"Constraints": None}))
    assert next_action(story_dir)["kind"] == "draft"


def test_approval_is_always_a_human_step(story_dir: Story) -> None:
    import json

    from eil.gates import check_stage

    story_dir.write("requirements", requirements_doc())
    judged = story_dir.root / "j.json"
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
    action = next_action(story_dir)
    assert (action["kind"], action["command"]) == ("human", "/speckit-eil-approve")


def test_an_open_challenge_is_a_human_step_and_comes_first(story_dir: Story) -> None:
    challenge = record_block(
        "challenge",
        {"id": "CH-002", "stage": "requirements", "status": "open", "target": "REQ-001", "text": "x"},
    )
    story_dir.write("requirements", requirements_doc(extra=challenge))
    action = next_action(story_dir)
    assert (action["kind"], action["command"]) == ("human", "/speckit-eil-challenge")


def test_a_stage_needing_re_review_is_a_human_step(story_dir: Story) -> None:
    approve_requirements(story_dir)
    story_dir.append("requirements", "\nedit\n")
    assert next_action(story_dir)["kind"] == "human"


def test_open_tasks_send_the_story_to_implementation_before_verification(story_dir: Story) -> None:
    story_dir.write("tasks", "# Tasks\n\n- [x] T001 done\n- [ ] T002 not yet\n")
    package = Package(story_dir.root)
    model = overview.collect(package)
    model.current = "verification"
    action = overview.next_action(package, model)
    assert (action["stage"], action["kind"], action["command"]) == (
        "verification",
        "draft",
        "/speckit-implement",
    )
    story_dir.write("tasks", "# Tasks\n\n- [x] T001 done\n")
    assert overview.next_action(package, model)["command"] == "/speckit-eil-7-verify"


# ---- 003 D-58: the `reviewed` terminal state, and `done` after completion (FR-040)


def _reviewed_story(reference_story: Story) -> Package:
    from eil.gates import check_stage

    from tests.helpers.derived import settle_derived

    settle_derived(reference_story)
    for stage in ("ai-spec", "plan", "tasks", "verification"):
        check_stage(Package(reference_story.root), stage)
    return Package(reference_story.root)


def test_a_derived_stage_with_every_block_reviewed_and_its_code_criteria_met_is_reviewed(reference_story: Story) -> None:
    package = _reviewed_story(reference_story)
    assert package.state("plan").state == "reviewed"
    # The reference AI Specification misses sections its gate requires: not reviewed, whatever its blocks say.
    assert package.state("ai-spec").state != "reviewed"


def test_reviewed_falls_back_to_draft_when_a_block_needs_review_again(reference_story: Story) -> None:
    package = _reviewed_story(reference_story)
    assert package.state("plan").state == "reviewed"
    reference_story.write("plan", reference_story.read("plan").replace("Queue Design follows decision 4.", "Queue design follows decision four."))
    assert Package(reference_story.root).state("plan").state in ("draft", "in-review")


def test_the_current_stage_skips_a_reviewed_stage(reference_story: Story) -> None:
    package = _reviewed_story(reference_story)
    current = package.current_stage()
    assert current is None or package.state(current).state != "reviewed"


def test_after_completion_is_approved_the_story_is_done(two_stories: Any) -> None:
    package = Package(two_stories.a.root)
    assert package.current_stage() is None
    report = overview.status(package, TEMPLATE)
    action = report["next_action"]
    assert action["kind"] == "done"
    assert action["message"].startswith("Story complete; approved by Ada Dev on 2026-09-30")
    assert "Continue verification" not in str(report)
