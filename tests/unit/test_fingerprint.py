"""Fingerprint tests (task T017): the normative vectors of contracts/document-format.md and
determinism requirements 1 and 2 of contracts/cli.md."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

import pytest
from eil.fingerprint import NotUtf8, fingerprint_file, fingerprint_text, normalise


def region(name: str, body: str = "x") -> str:
    return f"<!-- eil:begin {name} -->\n{body}\n<!-- eil:end {name} -->\n"


def test_format_is_sha256_prefix_and_64_hex() -> None:
    assert re.fullmatch(r"sha256:[0-9a-f]{64}", fingerprint_text("A\n"))


def test_value_is_sha256_of_the_normalised_text() -> None:
    expected = "sha256:" + hashlib.sha256(b"A\n\nB\n").hexdigest()
    assert fingerprint_text("A\n\nB\n") == expected


@pytest.mark.parametrize("text", ["A\n\nB\n", "A\r\n\r\nB", "A  \n\n\n\nB\n\n"])
def test_normative_vectors_that_must_match(text: str) -> None:
    assert fingerprint_text(text) == fingerprint_text("A\n\nB\n")


@pytest.mark.parametrize("text", ["A\nB\n", "A \n\nB2\n"])
def test_normative_vectors_that_must_differ(text: str) -> None:
    assert fingerprint_text(text) != fingerprint_text("A\n\nB\n")


def test_lone_carriage_returns_are_newlines() -> None:
    assert fingerprint_text("A\r\rB\r") == fingerprint_text("A\n\nB\n")


def test_trailing_spaces_and_tabs_are_ignored() -> None:
    assert fingerprint_text("A \t \nB\t\n") == fingerprint_text("A\nB\n")


def test_leading_and_trailing_blank_lines_are_ignored() -> None:
    assert fingerprint_text("\n\n\nA\nB\n\n\n") == fingerprint_text("A\nB\n")


def test_runs_of_blank_lines_collapse_to_one_but_not_to_none() -> None:
    assert fingerprint_text("A\n\n\n\n\nB") == fingerprint_text("A\n\nB")
    assert fingerprint_text("A\nB") != fingerprint_text("A\n\nB")


def test_leading_spaces_are_content() -> None:
    assert fingerprint_text("A\n B\n") != fingerprint_text("A\nB\n")


def test_case_and_word_changes_are_content() -> None:
    assert fingerprint_text("Hello\n") != fingerprint_text("hello\n")


def test_normalise_returns_the_text_that_is_hashed() -> None:
    assert normalise("A  \r\n\r\n\r\nB\r\n\r\n") == "A\n\nB\n"


# ---- regions (determinism 2)


@pytest.mark.parametrize("name", ["approval", "assessment", "comprehension"])
def test_a_document_differing_only_inside_a_region_matches(name: str) -> None:
    one = f"# T\n\n{region(name, 'one')}\nbody\n"
    two = f"# T\n\n{region(name, 'two and more')}\nbody\n"
    assert fingerprint_text(one) == fingerprint_text(two)


@pytest.mark.parametrize("name", ["approval", "assessment", "comprehension"])
def test_a_document_matches_the_same_document_without_the_region(name: str) -> None:
    with_region = f"A\n\n{region(name)}\nB\n"
    assert fingerprint_text(with_region) == fingerprint_text("A\n\nB\n")


def test_a_region_at_the_end_of_the_file_is_removed_cleanly() -> None:
    assert fingerprint_text(f"## Approval\n{region('approval')}") == fingerprint_text("## Approval\n")


def test_region_directly_followed_by_text_leaves_no_gap() -> None:
    assert fingerprint_text(f"A\n{region('approval')}B\n") == fingerprint_text("A\nB\n")


def test_headings_around_a_region_remain_content() -> None:
    a = f"## Approval\n{region('approval', 'x')}"
    b = f"## Sign-off\n{region('approval', 'x')}"
    assert fingerprint_text(a) != fingerprint_text(b)


def test_all_three_regions_can_coexist() -> None:
    text = "A\n\n" + region("comprehension") + "\n" + region("assessment") + "\n" + region("approval")
    assert fingerprint_text(text) == fingerprint_text("A\n")


def test_content_between_regions_still_counts() -> None:
    a = f"{region('assessment')}\nmiddle\n{region('approval')}"
    b = f"{region('assessment')}\nchanged\n{region('approval')}"
    assert fingerprint_text(a) != fingerprint_text(b)


def test_a_record_block_is_content_not_a_region() -> None:
    a = 'A\n\n```eil:challenge\n{"id": "CH-001"}\n```\n'
    b = 'A\n\n```eil:challenge\n{"id": "CH-002"}\n```\n'
    assert fingerprint_text(a) != fingerprint_text(b)


def test_an_unmatched_begin_marker_is_not_stripped_so_the_document_reads_as_changed() -> None:
    open_region = "A\n<!-- eil:begin approval -->\nsecret one\n"
    other = "A\n<!-- eil:begin approval -->\nsecret two\n"
    assert fingerprint_text(open_region) != fingerprint_text(other)


def test_a_region_marker_indented_or_with_trailing_space_still_counts() -> None:
    text = "A\n  <!-- eil:begin approval -->  \nx\n<!-- eil:end approval -->\n"
    assert fingerprint_text(text) == fingerprint_text("A\n")


def test_a_marker_for_another_name_is_ordinary_content() -> None:
    text = "A\n<!-- eil:begin other -->\nx\n<!-- eil:end other -->\n"
    assert fingerprint_text(text) != fingerprint_text("A\n")


# ---- files


def test_file_fingerprint_matches_text_fingerprint(tmp_path: Path) -> None:
    path = tmp_path / "doc.md"
    path.write_bytes(b"A\r\n\r\nB")
    assert fingerprint_file(path) == fingerprint_text("A\n\nB\n")


def test_non_utf8_file_is_reported_not_fingerprinted(tmp_path: Path) -> None:
    path = tmp_path / "bad.md"
    path.write_bytes(b"\xff\xfe\x00bad")
    with pytest.raises(NotUtf8):
        fingerprint_file(path)


def test_a_utf8_bom_is_not_silently_ignored(tmp_path: Path) -> None:
    """The algorithm says decode UTF-8 and nothing else, so a BOM is content."""
    path = tmp_path / "bom.md"
    path.write_bytes(b"\xef\xbb\xbfA\n")
    assert fingerprint_file(path) != fingerprint_text("A\n")
