"""The provenance and changelog regions, allowed keys, placement and fingerprint vectors (T006)."""

from __future__ import annotations

import json
from typing import Any

import pytest
from eil.blocks import (
    Doc,
    RegionError,
    ensure_record_sections,
    provenance_problems,
    render_changelog,
    write_changelog,
    write_provenance,
)
from eil.fingerprint import fingerprint_text

from tests.helpers.package import (
    block_entry,
    changelog_region,
    provenance_region,
    with_record_sections,
)

BASE = "# Title\n\n## Background\n\nSome prose.\n\n## Quality Assessment\n\n<!-- eil:begin assessment -->\n<!-- eil:end assessment -->\n"
HASH = "sha256:" + "a" * 64

VALID: dict[str, Any] = {
    "version": 1,
    "currency": "known",
    "blocks": {
        "AIS-007": block_entry(
            HASH,
            "inferred",
            adds="retry policy",
            reviewed={"by": "Ada", "at": "t", "list": "RVW-001", "reply": "ok"},
            sources={"DEC-002": HASH},
        ),
        "Background#3f2a91c0d4e1": block_entry(HASH, "restated", cites={"REQ-001": HASH}),
        "T014": block_entry(HASH, "adopted", basis="untagged before upgrade", blocked_at_completion=False),
    },
    "acceptances": [
        {"id": "RVW-001", "stage": "ai-spec", "kind": "inferred", "digest": HASH, "by": "Ada", "at": "t",
         "reply": "ok", "accepted": [], "except": [], "questioned": [], "reopened": [], "deferred": [],
         "reason": None, "resolved_conflict": False}
    ],
    "corrections": [
        {"id": "CR-001", "item": "FR-004", "owner": "functional",
         "found_in": {"stage": "implementation", "item": "T014"}, "problem": "p", "wording": "w",
         "impact": [], "opened_by": "Ada", "at": "t", "status": "open", "closed_by_approval": None}
    ],
    "changes": [
        {"at": "2026-10-02T09:00:00Z", "item": "FR-004", "summary": "s", "summary_by": "ai",
         "origin": "CR-001", "accepted_by": "Ada"}
    ],
    "conflicts": [{"key": "FR-013", "hash": HASH, "answers": ["RVW-001"]}],
}  # fmt: skip


def _doc_with(obj: Any) -> Doc:
    return Doc(with_record_sections(BASE, obj))


def test_a_valid_record_round_trips() -> None:
    read = _doc_with(VALID).read_provenance()
    assert read.error is None
    assert read.obj == VALID


def test_regions_are_recognised_by_name() -> None:
    doc = Doc(with_record_sections(BASE, VALID, ["| a |"]))
    assert {"provenance", "changelog", "assessment"} <= set(doc.regions)


def test_an_absent_region_reads_as_absent_without_error() -> None:
    read = Doc(BASE).read_provenance()
    assert read.obj is None and read.error is None


@pytest.mark.parametrize(
    "mutate",
    [
        lambda o: o.update(extra=1),
        lambda o: o["blocks"]["AIS-007"].update(colour="red"),
        lambda o: o["blocks"]["AIS-007"]["reviewed"].update(when="t"),
        lambda o: o["blocks"]["AIS-007"].update({"class": "guessed"}),
        lambda o: o["acceptances"][0].update(approved=True),
        lambda o: o["corrections"][0].update(severity="high"),
        lambda o: o["corrections"][0]["found_in"].update(line=3),
        lambda o: o["changes"][0].update(who="x"),
        lambda o: o["conflicts"][0].update(winner="x"),
        lambda o: o.update(blocks=[]),
    ],
)
def test_any_other_key_is_malformed_provenance(mutate: Any) -> None:
    obj = json.loads(json.dumps(VALID))
    mutate(obj)
    assert provenance_problems(obj)
    doc = _doc_with(obj)
    assert doc.read_provenance().obj is None
    assert doc.read_provenance().error
    assert [f.code for f in doc.findings if f.code == "malformed-provenance"] == ["malformed-provenance"]


def test_unparseable_json_is_malformed_provenance() -> None:
    text = with_record_sections(BASE, {"version": 1}).replace('"version": 1', '"version": ')
    doc = Doc(text)
    assert doc.read_provenance().error
    assert any(f.code == "malformed-provenance" for f in doc.findings)


def test_a_malformed_region_is_not_rewritten() -> None:
    text = with_record_sections(BASE, {"version": 1, "bogus": 1})
    with pytest.raises(RegionError):
        write_provenance(text, {"version": 1, "bogus": 1})


def test_write_refuses_a_record_that_would_be_malformed() -> None:
    with pytest.raises(RegionError):
        write_provenance(BASE, {"version": 1, "bogus": 1})


def test_first_write_places_change_log_before_record_before_quality_assessment() -> None:
    text = write_provenance(BASE, {"version": 1})
    order = [text.index(h) for h in ("## Background", "## Change Log", "## Record", "## Quality Assessment")]
    assert order == sorted(order)
    assert "<!-- eil:begin changelog -->\n<!-- eil:end changelog -->" in text


def test_record_goes_before_comprehension_check_when_that_comes_first() -> None:
    base = BASE.replace("## Quality Assessment", "## Comprehension Check\n\n## Quality Assessment")
    text = ensure_record_sections(base)
    assert text.index("## Record") < text.index("## Comprehension Check")


def test_a_document_with_neither_gets_the_sections_at_the_end() -> None:
    text = ensure_record_sections("# T\n\n## A\n\nx\n")
    assert text.rstrip().endswith("<!-- eil:end provenance -->")
    assert text.index("## Change Log") < text.index("## Record")


def test_a_second_write_changes_only_the_record() -> None:
    once = write_provenance(BASE, {"version": 1})
    twice = write_provenance(once, {"version": 1, "currency": "unknown"})
    assert twice.count("## Record") == 1 and twice.count("## Change Log") == 1
    assert Doc(twice).read_provenance().obj == {"version": 1, "currency": "unknown"}
    assert twice.replace('"currency": "unknown"', "").count("Some prose.") == 1


def test_the_changelog_is_rendered_from_changes_and_escaped() -> None:
    rows = render_changelog(
        [
            {"at": "2026-10-02T09:00:00Z", "item": "FR-004", "summary": "a | b\nc", "origin": "CR-001",
             "accepted_by": "Ada"}
        ],
        [{"id": "CR-001", "found_in": {"stage": "implementation", "item": "T014"}}],
    )  # fmt: skip
    assert rows[0].startswith("| Date | Item | Change (AI-drafted, accepted as shown)")
    assert rows[2] == "| 2026-10-02 | FR-004 | a \\| b c | implementation (T014), CR-001 | Ada |"
    assert render_changelog([]) == []


def test_write_changelog_fills_only_its_region() -> None:
    base = write_provenance(BASE, {"version": 1})
    filled = write_changelog(base, [{"at": "2026-10-02", "item": "FR-1", "summary": "s", "origin": "edit"}])
    assert "| 2026-10-02 | FR-1 | s | edit |" in filled
    assert Doc(filled).read_provenance().obj == {"version": 1}
    assert write_changelog(filled, []) == base


# ---- fingerprint vectors (contracts/document-format.md §Fingerprint test vectors)


def test_a_document_differing_only_in_provenance_or_changelog_matches() -> None:
    plain = fingerprint_text(BASE)
    assert fingerprint_text(with_record_sections(BASE)) == plain
    assert fingerprint_text(with_record_sections(BASE, VALID, ["| x | y |"])) == plain
    assert fingerprint_text(with_record_sections(BASE, {"version": 1})) == plain


def test_the_two_regions_alone_are_excluded() -> None:
    body = BASE + "\n" + provenance_region({"version": 1}) + "\n" + changelog_region(["| a |"])
    assert fingerprint_text(body) == fingerprint_text(BASE)


def test_an_ordinary_change_beside_the_regions_still_changes_the_fingerprint() -> None:
    edited = with_record_sections(BASE.replace("Some prose.", "Other prose."), VALID)
    assert fingerprint_text(edited) != fingerprint_text(BASE)


def test_ai_draft_on_a_prose_block_changes_nothing() -> None:
    assert fingerprint_text(BASE.replace("Some prose.", "Some prose. [ai-draft]")) == fingerprint_text(BASE)
