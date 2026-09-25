"""The chain, forward and reverse (task T100; FR-024, FR-028 to FR-030, FR-040, FR-045, FR-068).

REQ/UC -> FR -> DEC -> AIS -> task -> code -> EVD, with ART as a side branch, readable both ways and
with the gaps named.
"""

from __future__ import annotations

import pytest
from eil import chain
from eil.blocks import Doc
from eil.package import Package
from eil.trace import Task, build_graph, code_matches, parse_document, parse_text

from tests.helpers.package import Story, record_block, tasks_doc, with_ai_spec

EVIDENCE = (
    "# Verification\n\n"
    "**EVD-001**: The import test flags the duplicate (traces: FR-001, T001)\n\n"
    "**EVD-002**: Screenshot review of the container view (traces: ART-004)\n"
)
TASKS = [
    "- [ ] T001 Create the worker package in src/worker/__init__.py (traces: AIS-003) (code: abc1234)",
    "- [x] T002 Add the status endpoint in src/api/status.py (traces: AIS-006) (code: PR#12)",
    "- [ ] T003 Add the DUPLICATE_MATCH migration in migrations/001.sql (traces: AIS-014)",
    "- [ ] T004 Queue the analysis in src/api/imports.py (traces: AIS-015)",
]


def full_story(story: Story) -> Package:
    with_ai_spec(story)
    story.write("plan", "# Plan\n")
    story.write("tasks", tasks_doc(TASKS))
    story.write("verification", EVIDENCE)
    return Package(story.root)


def ids(rows: list[dict]) -> list[str]:
    return [r["id"] for r in rows]


# ---- the graph and code references


def test_a_task_line_carries_its_code_references() -> None:
    result = parse_text(tasks_doc(TASKS))
    by_id = {t.id: t for t in result.tasks}
    assert by_id["T001"].code == ["abc1234"] and by_id["T002"].code == ["PR#12"] and by_id["T003"].code == []


def test_a_task_with_a_bad_code_reference_is_a_malformed_item() -> None:
    result = parse_text("- [ ] T001 Do it (traces: AIS-003) (code: not a ref)\n")
    assert [f.code for f in result.findings] == ["malformed-item"]
    assert isinstance(result.tasks[0], Task)


@pytest.mark.parametrize(
    ("ref", "wanted", "expected"),
    [
        ("abc1234", "abc1234", True),
        ("abc1234def", "abc1234", True),
        ("abc1234", "abc1234def", True),
        ("abc1234", "abd1234", False),
        ("PR#12", "PR#12", True),
        ("PR#12", "PR#123", False),
        ("PR#12", "abc1234", False),
    ],
)
def test_a_commit_matches_by_prefix_and_a_pull_request_only_exactly(
    ref: str, wanted: str, expected: bool
) -> None:
    assert code_matches(ref, wanted) is expected


def test_the_graph_knows_which_stage_defined_each_id_and_who_traces_to_it(story_dir: Story) -> None:
    package = full_story(story_dir)
    graph = build_graph({s: parse_document(package.doc(s)) for s in package.existing_stages()})
    assert graph.nodes["FR-001"].stage == "functional" and graph.nodes["T001"].stage == "tasks"
    assert "DEC-001" in graph.children["FR-001"] and "AIS-003" in graph.children["DEC-001"]


# ---- forward: from a requirement to its evidence


def test_the_forward_chain_from_a_requirement_reaches_every_link_to_the_evidence(story_dir: Story) -> None:
    package = full_story(story_dir)
    result = chain.trace(package, from_id="REQ-001")
    reached = ids(result["chain"])
    for expected in ("FR-001", "DEC-001", "ART-004", "AIS-003", "T001", "EVD-001", "EVD-002"):
        assert expected in reached, expected
    assert result["direction"] == "forward" and result["chain"][0]["id"] == "ART-001"
    stages = {r["id"]: r["stage"] for r in result["chain"]}
    assert stages["DEC-001"] == "technical" and stages["EVD-001"] == "verification"


def test_the_artefact_side_branch_is_part_of_the_chain(story_dir: Story) -> None:
    package = full_story(story_dir)
    reached = ids(chain.trace(package, from_id="FR-001")["chain"])
    assert "ART-004" in reached and "AIS-013" in reached and "EVD-002" in reached


def test_a_forward_chain_names_the_links_that_are_missing(story_dir: Story) -> None:
    package = full_story(story_dir)
    story_dir.write("verification", "# Verification\n")
    story_dir.write("tasks", tasks_doc(["- [ ] T001 Create it in src/a.py (traces: AIS-003)"]))
    gaps = chain.trace(package, from_id="REQ-001")["gaps"]
    assert "no code change is linked (code: <sha or PR#n>)" in gaps
    assert "no verification evidence (FR-030)" in gaps


def test_a_requirement_with_no_functional_requirement_is_a_gap_at_the_first_link(story_dir: Story) -> None:
    package = full_story(story_dir)
    story_dir.write(
        "requirements",
        story_dir.read("requirements").replace(
            "**REQ-001**:", "**REQ-002**: A second outcome.\n\n**REQ-001**:", 1
        ),
    )
    result = chain.trace(package, from_id="REQ-002")
    assert result["chain"] == [] and "no functional requirement traces to REQ-002" in result["gaps"]


def test_forward_from_an_unknown_id_is_a_clear_error(story_dir: Story) -> None:
    package = full_story(story_dir)
    with pytest.raises(chain.UnknownReference):
        chain.trace(package, from_id="REQ-099")


# ---- reverse: from a task or a change to its reason


def test_the_reverse_chain_from_a_task_reaches_the_requirement(story_dir: Story) -> None:
    package = full_story(story_dir)
    result = chain.trace(package, to_ref="T001")
    assert result["direction"] == "reverse"
    reached = ids(result["chain"])
    assert reached[:2] == ["AIS-003", "DEC-001"] and "FR-001" in reached and "REQ-001" in reached
    assert result["gaps"] == []


def test_the_reverse_chain_from_a_pull_request_starts_at_the_tasks_that_carry_it(story_dir: Story) -> None:
    package = full_story(story_dir)
    result = chain.trace(package, to_ref="PR#12")
    assert result["start"] == ["T002"]
    reached = ids(result["chain"])
    assert "AIS-006" in reached and "DEC-001" in reached and "REQ-001" in reached


def test_the_reverse_chain_from_a_commit_matches_by_prefix(story_dir: Story) -> None:
    package = full_story(story_dir)
    assert chain.trace(package, to_ref="abc1234def0")["start"] == ["T001"]


def test_a_change_that_no_task_carries_is_an_error(story_dir: Story) -> None:
    package = full_story(story_dir)
    with pytest.raises(chain.UnknownReference):
        chain.trace(package, to_ref="PR#999")


def test_a_reverse_chain_that_ends_before_a_requirement_is_a_gap(story_dir: Story) -> None:
    package = full_story(story_dir)
    story_dir.write(
        "tasks",
        tasks_doc(["- [ ] T001 Do it (traces: AIS-003) (code: abc1234)", "- [ ] T009 Stray (code: PR#7)"]),
    )
    result = chain.trace(package, to_ref="PR#7")
    assert result["chain"] == [] and "T009 traces to nothing, so no requirement is reached" in result["gaps"]


def test_from_may_also_take_a_commit(story_dir: Story) -> None:
    package = full_story(story_dir)
    result = chain.trace(package, from_id="abc1234")
    assert result["start"] == ["T001"] and "EVD-001" in ids(result["chain"])


# ---- what every report carries: overrides, abbreviations, accepted risks


def test_the_report_lists_overrides_abbreviations_and_accepted_risks(story_dir: Story) -> None:
    override = {
        "id": "OVR-001",
        "stage": "functional",
        "criterion": "FUN-G16",
        "by": "Ada Dev",
        "reason": "x",
        "at": "2026-09-25T00:00:00Z",
    }
    package = full_story(story_dir)
    story_dir.write(
        "functional",
        story_dir.read("functional").replace(
            "## Overrides\n", "## Overrides\n\n" + record_block("override", override)
        ),
    )
    story_dir.write(
        "requirements",
        story_dir.read("requirements").replace(
            "## Not applicable\n",
            "**OQ-004**: Keep history? (status: accepted) (accepted-by: Ada Dev) (material: yes)\n\n## Not applicable\n",
            1,
        ),
    )
    story_dir.write(
        "plan",
        "# Plan\n\n## Abbreviation\n\n"
        + record_block("abbreviation", {"stage": "plan", "by": "Ada Dev", "reason": "trivial"}),
    )
    result = chain.trace(package, from_id="REQ-001")
    assert [o["id"] for o in result["overrides"]] == ["OVR-001"]
    assert result["abbreviated"] == [{"stage": "plan", "by": "Ada Dev"}]
    assert [r["id"] for r in result["accepted_risks"]] == ["OQ-004"]
    assert (
        "OVR-001" in result["text"]
        and "OQ-004" in result["text"]
        and "plan (authorised by Ada Dev)" in result["text"]
    )


# ---- the whole-story report and the chain check (FR-068)


def test_the_report_gives_one_row_per_requirement_and_where_its_chain_ends(story_dir: Story) -> None:
    package = full_story(story_dir)
    rows = chain.report(package)["requirements"]
    assert [r["id"] for r in rows] == ["REQ-001"]
    row = rows[0]
    assert row["functional"] == ["FR-001", "NFR-001"] and "DEC-001" in row["decisions"]
    assert "AIS-003" in row["ai_spec"] and "T001" in row["tasks"] and row["code"] == ["PR#12", "abc1234"]
    assert row["evidence"] == ["EVD-001", "EVD-002"] and row["complete"] is True


def test_a_requirement_without_evidence_is_incomplete_at_verification(story_dir: Story) -> None:
    package = full_story(story_dir)
    story_dir.write("verification", "# Verification\n")
    row = chain.report(package)["requirements"][0]
    assert row["complete"] is False and row["ends_at"] == "verification"


def test_the_chain_check_reports_gaps_in_both_directions_with_t_ids(story_dir: Story) -> None:
    package = full_story(story_dir)
    story_dir.write(
        "functional",
        story_dir.read("functional").replace(
            "**NFR-001**", "**FR-009**: Untraced behaviour.\n\n**NFR-001**", 1
        ),
    )
    story_dir.write(
        "requirements",
        story_dir.read("requirements").replace("**REQ-001**:", "**REQ-005**: Uncovered.\n\n**REQ-001**:", 1),
    )
    story_dir.write("tasks", tasks_doc([*TASKS, "- [ ] T009 Add a console"]))
    result = chain.check(package)
    messages = {g["message"] for g in result["gaps"]}
    assert "FR-009 traces to no requirement or use case" in messages
    assert "REQ-005 has no functional requirement" in messages
    assert "T009 traces to no AIS item or approved decision" in messages
    assert [g["id"] for g in result["gaps"]] == [f"T-{n:03d}" for n in range(1, len(result["gaps"]) + 1)]
    assert result["ok"] is False


def test_the_chain_check_covers_decisions_and_the_ai_specification(story_dir: Story) -> None:
    package = full_story(story_dir)
    story_dir.write("technical", story_dir.read("technical").replace(" (traces: FR-001, NFR-001)", "", 1))
    story_dir.write(
        "ai-spec",
        story_dir.read("ai-spec").replace(
            "**AIS-002**: Two customers with the same tax id are duplicates. (traces: FR-001)",
            "**AIS-002**: Unsourced.",
        ),
    )
    messages = {g["message"] for g in chain.check(package)["gaps"]}
    assert "DEC-001 traces to no FR or NFR" in messages
    assert "AIS-002 traces to no approved source" in messages


def test_a_clean_chain_has_no_gaps(story_dir: Story) -> None:
    package = full_story(story_dir)
    result = chain.check(package)
    assert result["gaps"] == [] and result["ok"] is True


def test_an_artefact_that_traces_to_nothing_is_a_gap(story_dir: Story) -> None:
    package = full_story(story_dir)
    story_dir.write(
        "technical",
        story_dir.read("technical").replace(
            "**ART-004**: Containers of the platform (traces: FR-001, DEC-001)",
            "**ART-004**: Containers of the platform",
        ),
    )
    assert any("ART-004" in g["message"] for g in chain.check(package)["gaps"])


def test_tracing_writes_nothing(story_dir: Story) -> None:
    package = full_story(story_dir)
    before = {p.name: p.read_bytes() for p in story_dir.root.iterdir() if p.is_file()}
    chain.trace(package, from_id="REQ-001")
    chain.report(package)
    chain.check(package)
    assert {p.name: p.read_bytes() for p in story_dir.root.iterdir() if p.is_file()} == before
    assert isinstance(Doc(story_dir.read("plan")), Doc)
