"""``enter`` and ``resolve`` and the plan and tasks gates (task T085; FR-004, FR-041, FR-042, FR-057,
FR-058, FR-067, FR-083).

``enter`` is the single gate call every wrapped Spec Kit command makes; ``resolve`` carries a pending
clarification answer to the earliest stage it affects.
"""

from __future__ import annotations

import pytest
from eil import aliases
from eil.blocks import Doc
from eil.gates import CRITERIA_BY_STAGE, GateResult, check_stage
from eil.handoff import ENTER_COMMANDS, enter, resolve
from eil.package import Package
from eil.results import EilExit
from eil.trace import parse_document

from tests.helpers.package import (
    Story,
    approve_stages,
    plan_doc,
    record_block,
    tasks_doc,
    with_ai_spec,
    with_approved_chain,
    with_plan_and_tasks,
)

PENDING_BODY = "**AIS-002**: Retention is 90 days. [pending-clarification]"


def refusals_of(exc: pytest.ExceptionInfo[EilExit]) -> list[str]:
    return [r["code"] for r in exc.value.payload["refusals"]]


def refused(story: Story, command: str, **kwargs: object) -> list[str]:
    with pytest.raises(EilExit) as exc:
        enter(Package(story.root), command, **kwargs)  # type: ignore[arg-type]
    assert exc.value.code == 1
    return refusals_of(exc)


def override(criterion: str, stage: str = "ai-spec") -> str:
    return record_block(
        "override",
        {
            "id": "OVR-001",
            "stage": stage,
            "criterion": criterion,
            "by": "Ada Dev",
            "reason": "accepted",
            "at": "2026-09-25T00:00:00Z",
        },
    )


def gate(story: Story, stage: str) -> GateResult:
    return check_stage(Package(story.root), stage)


def status_of(result: GateResult) -> dict[str, str]:
    return {c.id: c.status for c in result.criteria}


# ---- enter: the rules of each wrapped command


def test_the_wrapped_commands_are_the_seven_of_the_contract() -> None:
    assert ENTER_COMMANDS == ("specify", "clarify", "plan", "tasks", "analyze", "checklist", "implement")


def test_enter_plan_needs_an_ai_specification(story_dir: Story) -> None:
    with_approved_chain(story_dir)
    assert refused(story_dir, "plan") == ["ai-spec-missing"]
    assert not (story_dir.root / "spec.md").exists()


def test_enter_plan_passes_when_the_chain_is_approved_and_the_ai_specification_is_traceable(
    story_dir: Story,
) -> None:
    with_ai_spec(story_dir)
    result = enter(Package(story_dir.root), "plan")
    assert result["ok"] and result["command"] == "plan"
    assert (story_dir.root / "spec.md").exists(), "enter synchronises the aliases first"


def blocked_ids(story: Story, command: str) -> list[str]:
    return [row["id"] for row in enter(Package(story.root), command)["blocked"]]


def test_enter_plan_blocks_a_pending_clarification_and_names_it(story_dir: Story) -> None:
    with_ai_spec(story_dir, sections={"Business Rules": PENDING_BODY})
    result = enter(Package(story_dir.root), "plan")
    assert result["ok"]
    (row,) = [r for r in result["blocked"] if r["id"] == "AIS-002"]
    assert any("pending" in why for why in row["because"]) and "/speckit-eil-resolve AIS-002" in row["fix"]


def test_enter_plan_blocks_an_item_without_a_source(story_dir: Story) -> None:
    with_ai_spec(story_dir, sections={"Business Rules": "**AIS-002**: Tax ids are unique."})
    assert "AIS-002" in blocked_ids(story_dir, "plan")


def test_enter_plan_reports_a_pending_answer_and_an_unsourced_item_together(story_dir: Story) -> None:
    body = PENDING_BODY + "\n\n**AIS-016**: Unsourced."
    with_ai_spec(story_dir, sections={"Business Rules": body})
    assert {"AIS-002", "AIS-016"} <= set(blocked_ids(story_dir, "plan"))


def test_enter_plan_refuses_a_stage_that_was_never_approved(story_dir: Story) -> None:
    with_ai_spec(story_dir)
    text = story_dir.read("functional")
    start, end = text.index("<!-- eil:begin approval -->"), text.index("<!-- eil:end approval -->")
    story_dir.write(
        "functional", text[:start] + "<!-- eil:begin approval -->\n```json\n{}\n```\n" + text[end:]
    )
    assert "stage-not-approved" in refused(story_dir, "plan")


def test_a_stage_edited_after_approval_does_not_stop_plan_only_what_it_reaches(story_dir: Story) -> None:
    with_ai_spec(story_dir)
    story_dir.write("functional", story_dir.read("functional").replace("60 seconds", "90 seconds"))
    assert enter(Package(story_dir.root), "plan")["ok"]


def test_a_named_override_lets_plan_enter_over_a_pending_answer_and_stays_visible(story_dir: Story) -> None:
    with_ai_spec(story_dir, sections={"Business Rules": PENDING_BODY}, extra=override("AIS-G03"))
    result = enter(Package(story_dir.root), "plan")
    assert result["ok"]
    assert "OVR-001" in story_dir.read("ai-spec")


def test_enter_tasks_needs_a_plan_and_blocks_a_pending_item(story_dir: Story) -> None:
    with_ai_spec(story_dir)
    assert refused(story_dir, "tasks") == ["plan-missing"]
    story_dir.write("plan", plan_doc())
    assert enter(Package(story_dir.root), "tasks")["ok"]
    story_dir.write(
        "ai-spec",
        story_dir.read("ai-spec").replace("**AIS-002**: Two", "**AIS-002**: [pending-clarification] Two"),
    )
    assert "AIS-002" in blocked_ids(story_dir, "tasks")


def test_enter_implement_needs_plan_and_tasks_and_blocks_a_pending_answer(story_dir: Story) -> None:
    with_ai_spec(story_dir)
    story_dir.write("plan", plan_doc())
    assert refused(story_dir, "implement") == ["tasks-missing"]
    story_dir.write("tasks", tasks_doc())
    assert enter(Package(story_dir.root), "implement")["ok"]
    text = story_dir.read("ai-spec").replace("**AIS-002**: Two", "**AIS-002**: Two [pending-clarification]")
    story_dir.write("ai-spec", text)
    assert "AIS-002" in blocked_ids(story_dir, "implement")


def test_enter_implement_refuses_an_alias_it_cannot_repair(story_dir: Story) -> None:
    with_plan_and_tasks(story_dir)
    (story_dir.root / "plan.md").mkdir()
    assert "alias-fault-strict" in refused(story_dir, "implement")


def test_enter_clarify_needs_an_ai_specification_and_nothing_more(story_dir: Story) -> None:
    with_ai_spec(story_dir, sections={"Business Rules": PENDING_BODY})
    assert enter(Package(story_dir.root), "clarify")["ok"]


def test_enter_clarify_refuses_without_an_ai_specification(story_dir: Story) -> None:
    assert refused(story_dir, "clarify") == ["ai-spec-missing"]


@pytest.mark.parametrize("command", ["analyze", "checklist"])
def test_analyze_and_checklist_only_synchronise(story_dir: Story, command: str) -> None:
    with_ai_spec(story_dir)
    result = enter(Package(story_dir.root), command)
    assert result["ok"] and (story_dir.root / "spec.md").exists()


def test_enter_specify_refuses_a_governed_story(story_dir: Story) -> None:
    assert refused(story_dir, "specify") == ["already-governed"]


def test_enter_repairs_and_reports_an_alias_fault(story_dir: Story) -> None:
    with_ai_spec(story_dir)
    (story_dir.root / "spec.md").write_text("a separate file")
    result = enter(Package(story_dir.root), "plan")
    assert result["alias_faults"] == [
        {"name": "spec.md", "target": "s04-ai-spec.md", "form": "mirror", "fault": "diverged"}
    ]
    assert (story_dir.root / "spec.md").read_bytes() == story_dir.path("ai-spec").read_bytes()


def test_strict_makes_any_alias_fault_a_refusal_after_the_repair(story_dir: Story) -> None:
    with_ai_spec(story_dir)
    (story_dir.root / "spec.md").write_text("a separate file")
    assert refused(story_dir, "plan", strict=True) == ["alias-fault-strict"]
    assert (story_dir.root / "spec.md").read_bytes() == story_dir.path("ai-spec").read_bytes()


def test_enter_in_mirror_mode_leaves_read_only_mirrors(story_dir: Story) -> None:
    with_plan_and_tasks(story_dir)
    enter(Package(story_dir.root), "implement", mode=aliases.MIRROR)
    for name in ("spec.md", "plan.md", "tasks.md"):
        path = story_dir.root / name
        assert path.is_file() and not path.is_symlink() and path.stat().st_mode & 0o222 == 0


def test_enter_never_writes_a_stage_document(story_dir: Story) -> None:
    with_plan_and_tasks(story_dir)
    before = {s: story_dir.path(s).read_bytes() for s in Package(story_dir.root).existing_stages()}
    enter(Package(story_dir.root), "implement")
    assert {s: story_dir.path(s).read_bytes() for s in before} == before


# ---- the plan gate (FR-057)


def test_a_plan_whose_sections_all_name_an_approved_decision_meets_the_gate(story_dir: Story) -> None:
    with_ai_spec(story_dir)
    story_dir.write("plan", plan_doc())
    result = gate(story_dir, "plan")
    assert status_of(result)["PLN-G01"] == "met" and status_of(result)["PLN-G02"] == "not-met"


def test_the_plan_gate_is_judged_by_the_ai_and_the_table_says_so() -> None:
    kinds = {c.id: c.kind for c in CRITERIA_BY_STAGE["plan"]}
    assert kinds == {"PLN-G01": "traceability", "PLN-G02": "judgment"}


def test_plan_content_not_derivable_from_a_decision_is_flagged(story_dir: Story) -> None:
    with_ai_spec(story_dir)
    story_dir.write("plan", plan_doc({"Caching Layer": "Add a Redis cache in front of the API."}))
    result = gate(story_dir, "plan")
    reason = next(c.reason for c in result.criteria if c.id == "PLN-G01")
    assert "section 'Caching Layer' names no approved decision" in reason
    assert any(f.code == "plan-not-derivable" for f in result.findings)


def test_a_plan_section_may_not_cite_a_decision_that_is_not_approved_or_not_a_decision(
    story_dir: Story,
) -> None:
    with_ai_spec(story_dir)
    story_dir.write(
        "plan", plan_doc({"Summary (traces: DEC-009)": "x", "Technical Context (traces: FR-001)": "y"})
    )
    reason = next(c.reason for c in gate(story_dir, "plan").criteria if c.id == "PLN-G01")
    assert "DEC-009" in reason and "FR-001" in reason


def test_a_decision_of_an_unapproved_technical_stage_is_not_a_source_for_the_plan(story_dir: Story) -> None:
    with_ai_spec(story_dir)
    story_dir.write("technical", story_dir.read("technical").replace("three times", "four times"))
    story_dir.write("plan", plan_doc())
    assert status_of(gate(story_dir, "plan"))["PLN-G01"] == "not-met"
    approve_stages(story_dir, "technical")
    assert status_of(gate(story_dir, "plan"))["PLN-G01"] == "met"


def test_the_administrative_sections_of_a_plan_need_no_decision(story_dir: Story) -> None:
    with_ai_spec(story_dir)
    story_dir.write("plan", plan_doc(not_applicable="- Research: none needed"))
    assert status_of(gate(story_dir, "plan"))["PLN-G01"] == "met"


def test_an_empty_plan_has_nothing_derived(story_dir: Story) -> None:
    with_ai_spec(story_dir)
    story_dir.write(
        "plan",
        "# Plan\n\n## Challenges\n\n## Quality Assessment\n\n<!-- eil:begin assessment -->\n<!-- eil:end assessment -->\n",
    )
    assert "the plan has no sections" in next(
        c.reason for c in gate(story_dir, "plan").criteria if c.id == "PLN-G01"
    )


# ---- the tasks gate (FR-031, FR-058, FR-083)


def test_every_task_needs_a_source(story_dir: Story) -> None:
    with_ai_spec(story_dir)
    story_dir.write("plan", plan_doc())
    story_dir.write(
        "tasks",
        tasks_doc(["- [ ] T001 Add an admin console in src/admin.py", "- [ ] T002 Do it (traces: AIS-006)"]),
    )
    result = gate(story_dir, "tasks")
    reason = next(c.reason for c in result.criteria if c.id == "TSK-G01")
    assert "T001 traces to no AIS item" in reason and "T002" not in reason
    assert any(f.code == "task-untraced" and f.where == "T001" for f in result.findings)


def test_a_task_may_trace_to_an_approved_decision(story_dir: Story) -> None:
    with_ai_spec(story_dir)
    story_dir.write(
        "tasks",
        tasks_doc(
            [
                "- [ ] T001 Build the worker (traces: DEC-001)",
                "- [ ] T002 Add the schema (traces: AIS-014)",
                "- [ ] T003 Wire the queue (traces: AIS-015)",
            ]
        ),
    )
    assert status_of(gate(story_dir, "tasks"))["TSK-G01"] == "met"


def test_a_task_may_not_trace_to_something_that_is_not_a_source(story_dir: Story) -> None:
    with_ai_spec(story_dir)
    story_dir.write("tasks", tasks_doc(["- [ ] T001 Build the worker (traces: OQ-001)"]))
    assert "OQ-001" in next(c.reason for c in gate(story_dir, "tasks").criteria if c.id == "TSK-G01")


def test_an_empty_task_list_is_flagged(story_dir: Story) -> None:
    with_ai_spec(story_dir)
    story_dir.write("tasks", tasks_doc([]))
    assert "no tasks" in next(c.reason for c in gate(story_dir, "tasks").criteria if c.id == "TSK-G01")


def test_an_er_diagram_reached_by_no_task_is_uncovered(story_dir: Story) -> None:
    with_ai_spec(story_dir)
    story_dir.write("tasks", tasks_doc(TASKS_WITHOUT_SCHEMA))
    result = gate(story_dir, "tasks")
    assert status_of(result)["TSK-G02"] == "not-met"
    assert any(f.code == "artifact-uncovered" and f.where == "ART-007" for f in result.findings)
    assert "ART-007 (er, technical)" in next(c.reason for c in result.criteria if c.id == "TSK-G02")


TASKS_WITHOUT_SCHEMA = [
    "- [ ] T001 Create the worker package in src/worker/__init__.py (traces: AIS-003)",
    "- [ ] T004 Queue the analysis from the import handler in src/api/imports.py (traces: AIS-015)",
]


def test_a_technical_sequence_diagram_reached_by_no_task_is_uncovered(story_dir: Story) -> None:
    with_ai_spec(story_dir)
    story_dir.write("tasks", tasks_doc(["- [ ] T001 Add the schema in migrations/1.sql (traces: AIS-014)"]))
    assert "ART-006 (sequence, technical)" in next(
        c.reason for c in gate(story_dir, "tasks").criteria if c.id == "TSK-G02"
    )


def test_a_task_covers_an_artefact_directly_or_through_the_ais_item_that_cites_it(story_dir: Story) -> None:
    with_ai_spec(story_dir)
    story_dir.write(
        "tasks",
        tasks_doc(
            ["- [ ] T001 Add the schema (traces: ART-007)", "- [ ] T002 Wire the queue (traces: AIS-015)"]
        ),
    )
    assert status_of(gate(story_dir, "tasks"))["TSK-G02"] == "met"


def test_a_container_diagram_needs_no_task_of_its_own(story_dir: Story) -> None:
    with_plan_and_tasks(story_dir)
    assert status_of(gate(story_dir, "tasks"))["TSK-G02"] == "met"  # ART-004 is a container view


def test_an_artefact_the_ai_specification_does_not_list_is_not_in_scope(story_dir: Story) -> None:
    with_ai_spec(
        story_dir, sections={"Artefacts in Scope": "**AIS-013**: Read the container view. (traces: ART-004)"}
    )
    story_dir.write("tasks", tasks_doc(["- [ ] T001 Build the worker (traces: AIS-003)"]))
    assert status_of(gate(story_dir, "tasks"))["TSK-G02"] == "met"


def test_tasks_and_plan_are_never_approved_by_a_person(story_dir: Story) -> None:
    from eil.identity import Config
    from eil.records import approve
    from eil.results import EilExit

    with_plan_and_tasks(story_dir)
    for stage in ("plan", "tasks"):
        with pytest.raises(EilExit) as exc:
            approve(Package(story_dir.root), Config(), stage, "Ada Dev", "yes")
        assert exc.value.payload["refusals"][0]["code"] == "not-approvable"


# ---- resolve (FR-042, FR-067)


def carried(story: Story, stage: str, kind: str) -> list[str]:
    return [i.id for i in parse_document(Doc(story.read(stage))).items if i.kind == kind]


def test_resolve_carries_the_answer_to_the_earliest_stage_and_marks_it_for_re_review(
    story_dir: Story,
) -> None:
    with_ai_spec(story_dir, sections={"Business Rules": PENDING_BODY})
    result = resolve(Package(story_dir.root), "AIS-002", "functional")
    assert result["created"] and not result["cleared"] and result["carried_to"] == "FR-002"
    assert Package(story_dir.root).state("functional").state == "needs-re-review"
    # Nothing in the already-approved technical spec traces to the newly carried FR-002 (it could
    # not, since FR-002 did not exist when technical was approved), so per FR-043 ("depends on the
    # changed content") technical is not itself pulled into re-review — D-26.
    assert Package(story_dir.root).state("technical").state == "approved"
    assert Package(story_dir.root).state("requirements").state == "approved"
    functional = story_dir.read("functional")
    assert "**FR-002**: Carried from AIS-002: Retention is 90 days. [ai-draft]" in functional
    line = next(ln for ln in story_dir.read("ai-spec").splitlines() if ln.startswith("**AIS-002**"))
    assert "(traces: FR-002)" in line and "[pending-clarification]" in line


def test_the_new_item_goes_in_the_section_it_belongs_to_and_takes_the_next_free_number(
    story_dir: Story,
) -> None:
    with_ai_spec(story_dir, sections={"Business Rules": PENDING_BODY})
    resolve(Package(story_dir.root), "AIS-002", "functional")
    text = story_dir.read("functional")
    assert text.index("**FR-001**") < text.index("**FR-002**") < text.index("## Use Cases and Scenarios")
    assert carried(story_dir, "functional", "FR") == ["FR-001", "FR-002"]


@pytest.mark.parametrize(("stage", "expected"), [("requirements", "REQ-002"), ("technical", "DEC-002")])
def test_the_kind_of_item_follows_the_stage(story_dir: Story, stage: str, expected: str) -> None:
    with_ai_spec(story_dir, sections={"Business Rules": PENDING_BODY})
    assert resolve(Package(story_dir.root), "AIS-002", stage)["carried_to"] == expected


def test_the_pending_mark_stays_until_the_stage_is_approved_again(story_dir: Story) -> None:
    with_ai_spec(story_dir, sections={"Business Rules": PENDING_BODY})
    resolve(Package(story_dir.root), "AIS-002", "functional")
    again = resolve(Package(story_dir.root), "AIS-002", "functional")
    assert not again["created"] and not again["cleared"] and "approve functional" in again["text"]
    assert carried(story_dir, "functional", "FR") == ["FR-001", "FR-002"], "no second copy"
    functional = (
        story_dir.read("functional")
        .replace(" [ai-draft]", "")
        .replace(
            "Carried from AIS-002: Retention is 90 days.",
            "The system shall keep history for 90 days. (traces: REQ-001)",
        )
    )
    story_dir.write("functional", functional)
    approve_stages(story_dir, "functional")
    cleared = resolve(Package(story_dir.root), "AIS-002", "functional")
    assert cleared["cleared"]
    line = next(ln for ln in story_dir.read("ai-spec").splitlines() if ln.startswith("**AIS-002**"))
    assert "[pending-clarification]" not in line and "(traces: FR-002)" in line


def test_a_clearing_leaves_the_ai_specification_needing_the_technical_stage_re_approved(
    story_dir: Story,
) -> None:
    with_ai_spec(story_dir, sections={"Business Rules": PENDING_BODY})
    resolve(Package(story_dir.root), "AIS-002", "functional")
    functional = (
        story_dir.read("functional")
        .replace(" [ai-draft]", "")
        .replace("Carried from AIS-002: Retention is 90 days.", "Keep history. (traces: REQ-001)")
    )
    story_dir.write("functional", functional)
    approve_stages(story_dir, "functional")
    resolve(Package(story_dir.root), "AIS-002", "functional")
    result = gate(story_dir, "ai-spec")
    assert status_of(result)["AIS-G03"] == "met"
    # Technical was never pulled into re-review by this carry (D-26: nothing in it traces to the
    # newly carried FR-002), so its own AIS items still trace to an approved stage.
    assert status_of(result)["AIS-G02"] == "met"
    assert gate(story_dir, "ai-spec").ok


def test_resolve_into_a_stage_that_is_only_a_draft_leaves_it_a_draft(story_dir: Story) -> None:
    with_ai_spec(story_dir, sections={"Business Rules": PENDING_BODY})
    text = story_dir.read("requirements")
    start = text.index("<!-- eil:begin approval -->")
    end = text.index("<!-- eil:end approval -->")
    story_dir.write("requirements", text[:start] + "<!-- eil:begin approval -->\n" + text[end:])
    assert Package(story_dir.root).state("requirements").state == "draft"
    result = resolve(Package(story_dir.root), "AIS-002", "requirements")
    assert result["stage_state"] == "draft" and not result["cleared"]


@pytest.mark.parametrize(
    ("item", "stage", "code"),
    [
        ("AIS-001", "functional", "unknown-item"),  # not pending
        ("AIS-099", "functional", "unknown-item"),  # nothing by that id
        ("FR-001", "functional", "unknown-item"),  # not an AIS item
        ("AIS-002", "ai-spec", "stage-not-eligible"),
        ("AIS-002", "plan", "stage-not-eligible"),
        ("AIS-002", "nonsense", "stage-not-eligible"),
    ],
)
def test_resolve_refuses_what_it_cannot_carry(story_dir: Story, item: str, stage: str, code: str) -> None:
    with_ai_spec(story_dir, sections={"Business Rules": PENDING_BODY})
    with pytest.raises(EilExit) as exc:
        resolve(Package(story_dir.root), item, stage)
    assert exc.value.payload["refusals"][0]["code"] == code


def test_resolve_refuses_without_an_ai_specification_or_a_stage_document(story_dir: Story) -> None:
    with pytest.raises(EilExit) as exc:
        resolve(Package(story_dir.root), "AIS-002", "functional")
    assert exc.value.payload["refusals"][0]["code"] == "ai-spec-missing"
    with_ai_spec(story_dir, sections={"Business Rules": PENDING_BODY})
    story_dir.path("technical").unlink()
    with pytest.raises(EilExit) as exc:
        resolve(Package(story_dir.root), "AIS-002", "technical")
    assert exc.value.payload["refusals"][0]["code"] == "stage-not-eligible"


def test_resolve_refuses_a_stage_that_has_no_section_to_take_the_item(story_dir: Story) -> None:
    with_ai_spec(story_dir, sections={"Business Rules": PENDING_BODY})
    story_dir.write(
        "technical", story_dir.read("technical").replace("## Technical Decisions", "## Decisions")
    )
    with pytest.raises(EilExit) as exc:
        resolve(Package(story_dir.root), "AIS-002", "technical")
    assert "no 'Technical Decisions' section" in exc.value.payload["refusals"][0]["message"]


def test_a_pending_answer_with_traces_already_gets_the_new_id_added(story_dir: Story) -> None:
    body = "**AIS-002**: Retention is 90 days. (traces: NFR-001) [pending-clarification]"
    with_ai_spec(story_dir, sections={"Business Rules": body})
    resolve(Package(story_dir.root), "AIS-002", "functional")
    line = next(ln for ln in story_dir.read("ai-spec").splitlines() if ln.startswith("**AIS-002**"))
    assert "(traces: NFR-001, FR-002)" in line
