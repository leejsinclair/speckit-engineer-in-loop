"""Item grammar, clauses, tags, findings and item hashes (task T021)."""

from __future__ import annotations

import re

import pytest
from eil.blocks import Doc
from eil.trace import ParseResult, item_hash, parse_text, story_findings


def parse(text: str) -> ParseResult:
    return parse_text(text)


def only(text: str):
    result = parse(text)
    assert len(result.items) == 1, result
    return result.items[0]


# ---- what is an item


@pytest.mark.parametrize("kind", ["REQ", "UC", "FR", "NFR", "DEC", "AIS", "EVD", "OQ", "OVR", "CH", "ART"])
def test_every_item_kind_is_recognised(kind: str) -> None:
    item = only(f"**{kind}-042**: Something to say\n")
    assert (item.id, item.kind, item.number, item.title) == (f"{kind}-042", kind, 42, "Something to say")


@pytest.mark.parametrize(
    "line",
    [
        "**FR-001**: text",
        "- **FR-001**: text",
        "* **FR-001**: text",
        "  - **FR-001**: text",
        "**FR-001**. text",
        "**FR-001** : text",
    ],
)
def test_accepted_line_shapes(line: str) -> None:
    assert only(line + "\n").id == "FR-001"


def test_line_number_is_one_based() -> None:
    assert only("# Heading\n\n**FR-001**: text\n").line == 3


@pytest.mark.parametrize(
    "line",
    ["**FR-7**: text", "**FR-0007**: text", "**FR-001** text", "**FR-001**", "**FR-abc**: text"],
)
def test_malformed_item_lines_are_findings_never_silent(line: str) -> None:
    result = parse(line + "\n")
    assert result.items == []
    assert [f.code for f in result.findings] == ["malformed-item"]
    assert result.findings[0].where.endswith(":1")


def test_a_lowercase_prefix_is_not_an_item_prefix_at_all() -> None:
    result = parse("**fr-001**: text\n")
    assert result.items == [] and result.findings == []


def test_a_reference_in_the_middle_of_a_line_is_not_an_item() -> None:
    result = parse("This follows **FR-001** and **REQ-002**: not definitions.\n")
    assert result.items == [] and result.findings == []


def test_items_in_code_fences_are_ignored() -> None:
    assert parse("```text\n**FR-001**: shown as an example\n```\n").items == []


def test_items_in_html_comments_are_ignored() -> None:
    text = "<!--\n**ART-001**: example only\n-->\n**ART-002**: real\n"
    assert [i.id for i in parse(text).items] == ["ART-002"]


def test_a_malformed_line_in_a_comment_is_ignored_too() -> None:
    assert parse("<!-- **FR-7**: nope -->\n").findings == []


# ---- clauses


def test_traces_on_the_same_line() -> None:
    item = only("**FR-007**: Reject duplicate uploads (traces: REQ-003, UC-002)\n")
    assert item.traces == ["REQ-003", "UC-002"]
    assert item.title == "Reject duplicate uploads"


def test_traces_on_a_continuation_line() -> None:
    text = "**FR-007**: Reject duplicate uploads\n  (traces: REQ-003)\n\nnext paragraph\n"
    item = only(text)
    assert item.traces == ["REQ-003"]
    assert item.end_line == 2


def test_continuation_stops_at_blank_line_heading_item_task_and_fence() -> None:
    text = (
        "**FR-001**: one\nmore of one\n\nnot part\n"
        "**FR-002**: two\n## Heading\n"
        "**FR-003**: three\n- [ ] T001 a task\n"
        "**FR-004**: four\n```mermaid\nA\n```\n"
    )
    ends = {i.id: i.end_line for i in parse(text).items}
    assert ends == {"FR-001": 2, "FR-002": 5, "FR-003": 7, "FR-004": 9}


def test_code_clause_accepts_shas_and_pull_requests() -> None:
    item = only("**EVD-001**: Tested (code: 3fa9c21, PR#14) (traces: FR-001)\n")
    assert item.code == ["3fa9c21", "PR#14"]


def test_bad_code_reference_is_a_malformed_item() -> None:
    result = parse("**EVD-001**: Tested (code: not a ref)\n")
    assert [f.code for f in result.findings] == ["malformed-item"]


def test_bad_trace_id_is_a_malformed_item() -> None:
    result = parse("**FR-001**: Text (traces: REQ-3)\n")
    assert [f.code for f in result.findings] == ["malformed-item"]
    assert result.items[0].traces == []


def test_open_question_clauses() -> None:
    item = only("**OQ-004**: Is retention seven years? (status: open) (material: yes)\n")
    assert (item.status, item.material) == ("open", True)
    assert only("**OQ-005**: Naming? (status: resolved) (material: no)\n").material is False


def test_unknown_status_value_is_a_malformed_item() -> None:
    assert [f.code for f in parse("**OQ-004**: Q (status: maybe)\n").findings] == ["malformed-item"]


def test_accepted_by_clause_records_who_accepted_a_question() -> None:
    item = only("**OQ-004**: Retain? (status: accepted) (accepted-by: Ada Dev) (material: yes)\n")
    assert item.accepted_by == "Ada Dev" and item.status == "accepted"
    assert item.title == "Retain?"
    assert only("**OQ-005**: Retain? (status: open)\n").accepted_by is None


def test_store_clause_for_an_er_artifact() -> None:
    item = only("**ART-009**: Customer duplicate data (traces: DEC-004) (store: Customer DB)\n")
    assert item.store == "Customer DB"
    assert item.traces == ["DEC-004"]
    assert item.title == "Customer duplicate data"


def test_tags_are_collected_and_removed_from_the_title() -> None:
    item = only("**FR-001**: Do the thing [ai-draft] (traces: REQ-001)\n")
    assert item.tags == {"ai-draft"}
    assert item.title == "Do the thing"
    item = only("**AIS-002**: Answer [pending-clarification]\n")
    assert item.tags == {"pending-clarification"}


def test_an_item_with_no_clauses_has_empty_defaults() -> None:
    item = only("**REQ-001**: Plain\n")
    assert (item.traces, item.code, item.status, item.material, item.store, item.tags) == (
        [],
        [],
        None,
        None,
        None,
        set(),
    )


# ---- tasks


def test_task_lines_are_read_with_their_traces() -> None:
    result = parse(
        "- [ ] T012 [P] [US1] Build the parser in a.py (traces: AIS-001, DEC-002)\n- [x] T013 Done\n"
    )
    assert [(t.id, t.done, t.traces) for t in result.tasks] == [
        ("T012", False, ["AIS-001", "DEC-002"]),
        ("T013", True, []),
    ]
    assert result.tasks[0].line == 1


def test_a_task_id_needs_at_least_three_digits() -> None:
    assert parse("- [ ] T12 short\n").tasks == []


# ---- cross-document findings


def test_duplicate_ids_in_one_document_are_reported() -> None:
    result = parse("**FR-001**: a\n\n**FR-001**: b\n")
    assert [f.code for f in result.findings] == ["duplicate-id"]
    assert result.findings[0].where == "FR-001"


def test_duplicate_ids_across_documents_are_reported() -> None:
    found = story_findings(
        {"requirements": parse("**REQ-001**: a\n"), "functional": parse("**REQ-001**: b\n")}
    )
    assert [f.code for f in found] == ["duplicate-id"]


def test_a_trace_to_a_missing_id_is_a_dangling_trace() -> None:
    found = story_findings(
        {
            "requirements": parse("**REQ-001**: a\n"),
            "functional": parse("**FR-001**: b (traces: REQ-001, REQ-009)\n"),
        }
    )
    assert [(f.code, f.where) for f in found] == [("dangling-trace", "FR-001")]
    assert "REQ-009" in found[0].message


def test_a_task_trace_is_checked_too() -> None:
    found = story_findings(
        {
            "ai-spec": parse("**AIS-001**: a\n"),
            "tasks": parse("- [ ] T001 Do it (traces: AIS-001, AIS-050)\n"),
        }
    )
    assert [(f.code, f.where) for f in found] == [("dangling-trace", "T001")]


def test_a_clean_story_has_no_findings() -> None:
    found = story_findings(
        {"requirements": parse("**REQ-001**: a\n"), "functional": parse("**FR-001**: b (traces: REQ-001)\n")}
    )
    assert found == []


def test_parse_findings_carry_document_position() -> None:
    result = parse_text("x\n**FR-7**: nope\n", path="s02-functional-spec.md")
    assert result.findings[0].where == "s02-functional-spec.md:2"


# ---- item hash


def test_item_hash_has_the_sha256_shape() -> None:
    assert re.fullmatch(r"sha256:[0-9a-f]{64}", item_hash(only("**FR-001**: a\n")))


def test_item_hash_ignores_line_endings_trailing_space_and_blank_runs() -> None:
    a = item_hash(only("**FR-001**: text\n  more text\n"))
    b = item_hash(only("**FR-001**: text   \r\n  more text  \r\n"))
    assert a == b


def test_item_hash_changes_with_the_text() -> None:
    assert item_hash(only("**FR-001**: text\n")) != item_hash(only("**FR-001**: text!\n"))


def test_item_hash_includes_the_traces_clause() -> None:
    a = item_hash(only("**FR-001**: text (traces: REQ-001)\n"))
    b = item_hash(only("**FR-001**: text (traces: REQ-002)\n"))
    assert a != b


def test_item_hash_excludes_tags() -> None:
    plain = item_hash(only("**FR-001**: text (traces: REQ-001)\n"))
    tagged = item_hash(only("**FR-001**: text [ai-draft] (traces: REQ-001)\n"))
    pending = item_hash(only("**FR-001**: text (traces: REQ-001) [pending-clarification]\n"))
    assert plain == tagged == pending


def test_item_hash_includes_an_attachment() -> None:
    item = only("**ART-001**: view (traces: FR-001)\n")
    bare = item_hash(item)
    item.attachment = 'C4Container\n  Person(a, "A")'
    with_diagram = item_hash(item)
    item.attachment = 'C4Container\n  Person(a, "B")'
    assert len({bare, with_diagram, item_hash(item)}) == 3


def test_doc_object_can_be_parsed_directly() -> None:
    from eil.trace import parse_document

    assert [i.id for i in parse_document(Doc("**FR-001**: a\n")).items] == ["FR-001"]


# ---- technical decisions carry labelled fields (FR-032, FR-033)

from eil.trace import decision_fields  # noqa: E402


def test_a_decision_item_takes_its_labelled_lines_as_part_of_the_item() -> None:
    item = only(
        "**DEC-004**: Use a queue (traces: FR-001)\nDecision: Queue it.\nReason: Latency.\n\nprose after\n"
    )
    assert item.end_line == 3 and "Reason: Latency." in item.text and "prose after" not in item.text


def test_a_decision_item_continues_over_blank_lines_between_fields() -> None:
    item = only("**DEC-004**: Use a queue\n\nDecision:\nQueue it.\n\nReason:\n\nLatency.\n\n## Next\n")
    assert decision_fields(item) == {"decision": "Queue it.", "reason": "Latency."}
    assert item.end_line == 8


def test_only_a_decision_gets_the_blank_line_rule() -> None:
    result = parse("**FR-001**: Something (traces: REQ-001)\n\nDecision: not a field of an FR\n")
    assert result.items[0].end_line == 1


def test_decision_fields_accept_bold_bullets_and_plural_labels_and_join_continuation_lines() -> None:
    item = only(
        "**DEC-004**: Use a queue\n- **Decision:** Queue it,\n  behind the API.\n- **Rejected alternatives**: A, B\n"
        "- Trade-offs: slower\n**Owner**: Ada Dev\n"
    )
    assert decision_fields(item) == {
        "decision": "Queue it, behind the API.",
        "rejected alternative": "A, B",
        "trade-off": "slower",
        "owner": "Ada Dev",
    }


def test_a_label_with_no_text_is_an_empty_field() -> None:
    assert decision_fields(only("**DEC-004**: Use a queue\nReason:\n")) == {"reason": ""}
