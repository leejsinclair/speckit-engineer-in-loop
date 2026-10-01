"""Content blocks: FR-039 splitting, block hashes, keys and citations (T005; determinism 22, 23)."""

from __future__ import annotations

import pytest
from eil.blocks import Doc
from eil.content import blocks_of, cited_ids
from eil.trace import item_hash, parse_document

from tests.helpers.package import (
    changelog_region,
    provenance_region,
    record_block,
    with_record_sections,
)

HASH = "sha256:" + "b" * 64

DOC = """# Requirements

## Background

First paragraph
wraps over two lines.

Second paragraph. (traces: REQ-001, UC-001)

## Requirements

**REQ-001**: The system flags duplicates.
It does so on import. (traces: UC-001)

- **UC-001**: Analyst reviews a flagged pair.

| Col | Other |
|---|---|
| a | b |

```python
print("x")
```

**ART-001**: System context (traces: REQ-001)

```mermaid
C4Context
  Person(a, "A", "[existing] x")
```

<!-- a comment
that spans lines -->

Last paragraph.

## Challenges

Not a block, administrative.

## Approval

<!-- eil:begin approval -->
```json
{}
```
<!-- eil:end approval -->
"""


def _blocks(text: str = DOC) -> list:
    return blocks_of(Doc(text))


def _by_key(text: str = DOC) -> dict:
    return {b.key: b for b in _blocks(text)}


def test_splitting_follows_fr_039() -> None:
    kinds = [(b.kind, b.key.split("#")[0]) for b in _blocks()]
    assert kinds == [
        ("prose", "Background"),
        ("prose", "Background"),
        ("item", "REQ-001"),
        ("item", "UC-001"),
        ("table", "Requirements"),
        ("fence", "Requirements"),
        ("item", "ART-001"),
        ("prose", "Requirements"),
    ]


def test_headings_comments_regions_and_administrative_sections_are_not_blocks() -> None:
    text = "\n".join(b.text for b in _blocks())
    for absent in ("## ", "a comment", "Not a block", "eil:begin", '"json"'):
        assert absent not in text


def test_a_numbered_block_hash_equals_the_item_hash() -> None:
    doc = Doc(DOC)
    parsed = parse_document(doc)
    mine = {b.key: b.hash for b in blocks_of(doc)}
    for item in parsed.items:
        if item.kind != "ART":
            assert mine[item.id] == item_hash(item)


def test_an_art_block_includes_its_attachment_and_the_diagram_is_not_a_second_block() -> None:
    doc = Doc(DOC)
    parsed = parse_document(doc)
    art = next(i for i in parsed.items if i.id == "ART-001")
    blocks = blocks_of(doc)
    assert not any(b.kind == "fence" and "C4Context" in b.text for b in blocks)
    by_key = {b.key: b for b in blocks}
    assert by_key["ART-001"].hash == item_hash(art)
    edited = DOC.replace('"A", "[existing] x"', '"A", "[existing] y"')
    assert _by_key(edited)["ART-001"].hash != by_key["ART-001"].hash


def test_rewrapping_and_whitespace_leave_every_hash_unchanged() -> None:
    before = {b.key: b.hash for b in _blocks()}
    rewrapped = (
        DOC.replace("First paragraph\nwraps over two lines.", "First paragraph   \nwraps over two lines.  ")
        .replace("Last paragraph.", "Last paragraph.   ")
        .replace("\n\n## Requirements", "\n\n\n\n## Requirements")
    )
    assert {b.key: b.hash for b in _blocks(rewrapped)} == before


def test_ai_draft_and_pending_tags_do_not_change_a_hash() -> None:
    before = {b.key: b.hash for b in _blocks()}
    tagged = DOC.replace("Last paragraph.", "Last paragraph. [ai-draft]").replace(
        "The system flags duplicates.", "The system flags duplicates. [pending-clarification]"
    )
    assert {b.key: b.hash for b in _blocks(tagged)} == before


def test_inserting_a_paragraph_changes_only_that_paragraph() -> None:
    before = _by_key()
    after = _by_key(DOC.replace("Last paragraph.", "Last paragraph.\n\nBrand new paragraph."))
    new = set(after) - set(before)
    assert len(new) == 1 and after[new.pop()].text == "Brand new paragraph."
    assert all(after[k].hash == before[k].hash for k in before)


def test_editing_one_paragraph_changes_only_its_own_hash() -> None:
    before = _by_key()
    edited = _by_key(DOC.replace("Last paragraph.", "Last paragraph, edited."))
    changed = {k for k in before if k in edited and edited[k].hash != before[k].hash}
    assert changed == set()
    assert len(set(edited) - set(before)) == 1 and len(set(before) - set(edited)) == 1


def test_an_unnumbered_key_is_the_section_and_twelve_hex_digits() -> None:
    background = [b for b in _blocks() if b.key.startswith("Background#")]
    assert len(background) == 2
    for b in background:
        prefix, digits = b.key.split("#")
        assert prefix == "Background" and len(digits) == 12
        assert b.hash == "sha256:" + digits + b.hash[len("sha256:") + 12 :]


def test_a_prose_block_cites_through_its_last_line_only() -> None:
    cites = {b.text.split(".")[0]: b.traces for b in _blocks() if b.kind == "prose"}
    assert cites["Second paragraph"] == ["REQ-001", "UC-001"]
    assert cites["First paragraph\nwraps over two lines"] == []
    assert cited_ids("Claim. (traces: REQ-001)\nmore text") == []
    assert cited_ids("Claim.\nlast (traces: FR-002, T004)") == ["FR-002", "T004"]


def test_plan_headings_with_traces_are_numbered_blocks() -> None:
    plan = (
        "# Plan\n\n## Summary (traces: DEC-001)\n\nRuns async.\n\nMore words.\n\n"
        "## Structure\n\nA package.\n\n## Quality Assessment\n\nx\n"
    )
    by_key = _by_key(plan)
    assert set(by_key) == {"§Summary", by_key[next(k for k in by_key if k.startswith("Structure#"))].key}
    block = by_key["§Summary"]
    assert block.traces == ["DEC-001"] and "More words." in block.text
    edited = _by_key(plan.replace("Runs async.", "Runs sync."))
    assert edited["§Summary"].hash != block.hash


def test_task_lines_are_numbered_blocks_keyed_by_id() -> None:
    tasks = "# Tasks\n\n## Phase 1\n\n- [ ] T001 Do a thing (traces: AIS-001)\n- [x] T002 Other (traces: AIS-002) (code: abc1234)\n"
    by_key = _by_key(tasks)
    assert list(by_key) == ["T001", "T002"]
    assert by_key["T001"].traces == ["AIS-001"]
    ticked = _by_key(tasks.replace("- [ ] T001", "- [x] T001"))
    assert ticked["T001"].hash == by_key["T001"].hash, "ticking is not a change to what the task says"
    coded = _by_key(tasks.replace("Do a thing (traces: AIS-001)", "Do a thing (traces: AIS-001) (code: abc1234)"))
    assert coded["T001"].hash == by_key["T001"].hash
    reworded = _by_key(tasks.replace("Do a thing", "Do another thing"))
    assert reworded["T001"].hash != by_key["T001"].hash


def test_a_decision_with_field_lines_is_one_block() -> None:
    dec = (
        "# T\n\n## Technical Decisions\n\n**DEC-001**: Use a queue (traces: FR-001)\nDecision: Async.\n\n"
        "Reason: Latency.\nOwner: Ada\n\nA paragraph.\n"
    )
    keys = [b.key for b in _blocks(dec)]
    assert keys[0] == "DEC-001" and len(keys) == 2


def test_an_rf_item_is_a_numbered_block() -> None:
    text = "# V\n\n## Review Findings\n\n**RF-001**: Handler ignores tenant (status: open)\nRoot: implementation\n"
    (block,) = _blocks(text)
    assert block.key == "RF-001" and block.kind == "item"
    assert "Root: implementation" in block.text


def test_record_blocks_and_new_regions_are_not_content() -> None:
    text = with_record_sections(DOC, {"version": 1}, ["| a |"]) + "\n" + record_block("review", {"a": 1})
    assert [b.key for b in _blocks(text)] == [b.key for b in _blocks(DOC)]
    loose = DOC.replace("Last paragraph.", provenance_region({"version": 1}) + changelog_region(["| x |"]))
    assert [b.key for b in _blocks(loose)] == [b.key for b in _blocks(DOC)][:-1]


@pytest.mark.parametrize("heading", ["## Change Log", "## Record"])
def test_change_log_and_record_sections_are_administrative(heading: str) -> None:
    text = DOC + f"\n{heading}\n\nSome generated text.\n"
    assert not any("generated" in b.text for b in _blocks(text))
