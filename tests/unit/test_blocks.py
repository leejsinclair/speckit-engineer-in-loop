"""Marked regions, record blocks and fences (task T019)."""

from __future__ import annotations

import json

import pytest
from eil.blocks import Doc, RegionError, dumps, replace_record, write_region

from tests.helpers.package import record_block, region


def codes(doc: Doc) -> list[str]:
    return [f.code for f in doc.findings]


# ---- regions: read


def test_reads_a_region_as_json() -> None:
    doc = Doc("# T\n\n" + region("approval", {"by": "Ada", "n": 1}))
    read = doc.read_region("approval")
    assert read.obj == {"by": "Ada", "n": 1}
    assert read.error is None
    assert doc.findings == []


def test_absent_region_reads_as_none() -> None:
    read = Doc("# T\n").read_region("approval")
    assert read.obj is None and read.error is None


def test_empty_region_reads_as_none() -> None:
    text = "<!-- eil:begin approval -->\n<!-- eil:end approval -->\n"
    read = Doc(text).read_region("approval")
    assert read.obj is None and read.error is None


def test_unparseable_json_in_a_region_is_an_error_not_silence() -> None:
    text = "<!-- eil:begin approval -->\n```json\n{ nope\n```\n<!-- eil:end approval -->\n"
    read = Doc(text).read_region("approval")
    assert read.obj is None
    assert read.error and "JSON" in read.error


def test_a_region_holding_a_json_array_is_an_error() -> None:
    text = "<!-- eil:begin approval -->\n```json\n[1, 2]\n```\n<!-- eil:end approval -->\n"
    assert Doc(text).read_region("approval").error


def test_each_region_name_is_read_independently() -> None:
    text = region("assessment", {"a": 1}) + "\n" + region("approval", {"b": 2})
    doc = Doc(text)
    assert doc.read_region("assessment").obj == {"a": 1}
    assert doc.read_region("approval").obj == {"b": 2}


# ---- regions: malformed


def test_unmatched_begin_marker_is_malformed_region() -> None:
    assert codes(Doc("<!-- eil:begin approval -->\nx\n")) == ["malformed-region"]


def test_unmatched_end_marker_is_malformed_region() -> None:
    assert codes(Doc("x\n<!-- eil:end approval -->\n")) == ["malformed-region"]


def test_end_marker_of_a_different_name_is_malformed_region() -> None:
    text = "<!-- eil:begin approval -->\nx\n<!-- eil:end assessment -->\n"
    assert "malformed-region" in codes(Doc(text))


def test_nested_regions_are_malformed_region() -> None:
    text = (
        "<!-- eil:begin approval -->\n<!-- eil:begin assessment -->\n"
        "<!-- eil:end assessment -->\n<!-- eil:end approval -->\n"
    )
    assert "malformed-region" in codes(Doc(text))


def test_a_region_defined_twice_is_malformed_region() -> None:
    text = region("approval", {"a": 1}) + region("approval", {"a": 2})
    assert "malformed-region" in codes(Doc(text))


def test_reading_a_malformed_region_reports_an_error() -> None:
    read = Doc("<!-- eil:begin approval -->\n```json\n{}\n```\n").read_region("approval")
    assert read.obj is None and read.error


# ---- regions: write


def test_write_replaces_the_body_and_preserves_every_other_byte() -> None:
    before = (
        "# T\r\n\r\nSome  text \r\n\r\n"
        + region("approval", {"old": True}).replace("\n", "\r\n")
        + "tail  \r\n"
    )
    after = write_region(before, "approval", {"new": 1})
    assert after.startswith("# T\r\n\r\nSome  text \r\n\r\n<!-- eil:begin approval -->\r\n")
    assert after.endswith("<!-- eil:end approval -->\r\ntail  \r\n")
    assert Doc(after).read_region("approval").obj == {"new": 1}


def test_write_is_idempotent() -> None:
    text = "# T\n\n" + region("approval", {"a": 1})
    once = write_region(text, "approval", {"z": 1, "a": [1, 2]})
    assert write_region(once, "approval", {"z": 1, "a": [1, 2]}) == once


def test_write_appends_a_missing_region_at_the_end() -> None:
    text = "# T\n\nbody\n"
    after = write_region(text, "assessment", {"ok": True})
    assert after.startswith(text)
    assert Doc(after).read_region("assessment").obj == {"ok": True}
    assert Doc(after).findings == []


def test_write_can_add_a_heading_with_a_new_region() -> None:
    after = write_region("# T\n", "approval", {"a": 1}, heading="## Approval")
    assert "\n## Approval\n<!-- eil:begin approval -->" in after


def test_write_refuses_a_document_with_a_malformed_region() -> None:
    with pytest.raises(RegionError):
        write_region("<!-- eil:begin approval -->\nx\n", "approval", {"a": 1})


def test_write_keeps_non_ascii_text_readable() -> None:
    after = write_region("# T\n", "approval", {"by": "José — ✓"})
    assert "José — ✓" in after


def test_dumps_is_stable_two_space_json() -> None:
    assert dumps({"a": 1, "b": [1]}) == json.dumps({"a": 1, "b": [1]}, indent=2, ensure_ascii=False)


# ---- record blocks


def test_reads_record_blocks_with_their_kind_and_object() -> None:
    text = (
        "## Challenges\n\n"
        + record_block("challenge", {"id": "CH-001", "status": "open"})
        + "\n"
        + record_block("override", {"id": "OVR-001"})
    )
    records = Doc(text).records()
    assert [(r.kind, r.obj["id"]) for r in records] == [("challenge", "CH-001"), ("override", "OVR-001")]


def test_only_eil_info_strings_are_records() -> None:
    text = '```json\n{"id": "X"}\n```\n\n```eil:artifact\n{"file": "a.png"}\n```\n'
    assert [r.kind for r in Doc(text).records()] == ["artifact"]


def test_malformed_record_json_is_a_finding_naming_the_line() -> None:
    doc = Doc("a\n\n```eil:challenge\n{ nope\n```\n")
    assert codes(doc) == ["malformed-record"]
    assert ":3" in doc.findings[0].where
    assert doc.records()[0].obj is None


def test_a_record_holding_a_json_list_is_malformed() -> None:
    assert codes(Doc("```eil:challenge\n[1]\n```\n")) == ["malformed-record"]


def test_rewriting_a_record_preserves_every_other_byte() -> None:
    text = "Intro  \n\n" + record_block("challenge", {"id": "CH-001", "status": "open"}) + "\nAfter  \n"
    doc = Doc(text)
    (record,) = doc.records()
    after = replace_record(text, record, {"id": "CH-001", "status": "closed"})
    assert after.startswith("Intro  \n\n```eil:challenge\n")
    assert after.endswith("```\n\nAfter  \n")
    assert Doc(after).records()[0].obj == {"id": "CH-001", "status": "closed"}


def test_rewriting_one_record_leaves_its_neighbours_untouched() -> None:
    first = record_block("challenge", {"id": "CH-001"})
    second = record_block("challenge", {"id": "CH-002"})
    text = first + "\n" + second
    doc = Doc(text)
    after = replace_record(text, doc.records()[1], {"id": "CH-002", "status": "closed"})
    assert after.startswith(first + "\n```eil:challenge\n")
    assert Doc(after).records()[0].obj == {"id": "CH-001"}


def test_rewriting_a_record_is_idempotent() -> None:
    text = record_block("artifact", {"file": "assets/a.png", "sha256": "sha256:00"})
    (record,) = Doc(text).records()
    once = replace_record(text, record, {"file": "assets/a.png", "sha256": "sha256:11"})
    (record2,) = Doc(once).records()
    assert replace_record(once, record2, {"file": "assets/a.png", "sha256": "sha256:11"}) == once


# ---- fences


def test_mermaid_fences_carry_line_numbers_and_body() -> None:
    text = "# T\n\ntext\n\n```mermaid\nC4Context\n  title X\n```\n"
    (fence,) = Doc(text).fences_with_info("mermaid")
    assert fence.open_no == 5 and fence.close_no == 8
    assert fence.body == ["C4Context", "  title X"]
    assert fence.body_start == 6


def test_tilde_fences_and_longer_fences_are_understood() -> None:
    text = "~~~mermaid\nA\n~~~\n\n````mermaid\nB\n```\nstill B\n````\n"
    bodies = [f.body for f in Doc(text).fences_with_info("mermaid")]
    assert bodies == [["A"], ["B", "```", "still B"]]


def test_an_unclosed_fence_is_reported() -> None:
    doc = Doc("```mermaid\nA\n")
    assert codes(doc) == ["malformed-fence"]
    assert doc.fences[0].close_no is None


def test_fences_inside_html_comments_are_ignored() -> None:
    text = "<!--\n```mermaid\nC4Context\n```\n-->\n\n```mermaid\nsequenceDiagram\n```\n"
    fences = Doc(text).fences_with_info("mermaid")
    assert [f.body for f in fences] == [["sequenceDiagram"]]


def test_a_one_line_comment_hides_nothing_around_it() -> None:
    doc = Doc("before <!-- note --> after\n\n```mermaid\nA\n```\n")
    assert len(doc.fences_with_info("mermaid")) == 1


def test_comment_markers_inside_a_fence_are_literal_text() -> None:
    text = "```text\n<!-- not a comment\n```\n\n```mermaid\nA\n```\n"
    assert len(Doc(text).fences_with_info("mermaid")) == 1


def test_region_markers_are_not_hidden_by_comment_masking() -> None:
    text = "<!-- an ordinary comment -->\n" + region("approval", {"a": 1})
    assert Doc(text).read_region("approval").obj == {"a": 1}


def test_live_lines_blank_out_comments_but_keep_line_numbers() -> None:
    text = "a\n<!-- hidden\nstill hidden -->\nb\n"
    live = {ln.no: ln.live for ln in Doc(text).lines}
    assert live[1] == "a" and live[2].strip() == "" and live[3].strip() == "" and live[4] == "b"


def test_fence_body_lines_are_not_live_text() -> None:
    text = "```json\n**FR-001**: inside a fence\n```\n**FR-002**: outside\n"
    kinds = {ln.no: ln.kind for ln in Doc(text).lines}
    assert kinds[2] == "fence-body" and kinds[4] == "text"
