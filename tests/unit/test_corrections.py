"""Backwards corrections: ``correct propose|open``, ``(decided: CR-###)``, blocking and closing
(FR-021 to FR-025; research D-38; determinism requirements 34 to 36)."""

from __future__ import annotations

import pytest
from eil import chain, corrections, provenance, reviews, staleness
from eil.blockstatus import block_statuses
from eil.results import EilExit
from eil.trace import build_graph, parse_document

from tests.helpers.derived import CONFIG, edit, package_of, settle_derived
from tests.helpers.package import Story
from tests.unit.test_accept_changes import REQ1, confirm, prepared
from tests.unit.test_classify import classify

WORDING = "The system detects duplicate customers on import, in real time."
AIS1_WORDING = "Implement behaviour 1, within one second."


def codes(exc: pytest.ExceptionInfo[EilExit]) -> list[str]:
    return [r["code"] for r in exc.value.payload["refusals"]]


def open_cr(story: Story, item: str = "REQ-001", wording: str | None = WORDING, **kwargs: str) -> dict:
    return corrections.open_correction(
        package_of(story), item, "implementation", "too vague", "Ada Dev", wording=wording, **kwargs
    )


def found(story: Story, stage: str = "requirements") -> list[str]:
    pkg = package_of(story)
    return [f.code for f in provenance.decided_findings(pkg, stage, parse_document(pkg.doc(stage)))]


def reword(story: Story, cr: str = "CR-001", wording: str = WORDING) -> None:
    edit(story, "requirements", REQ1, f"**REQ-001**: {wording} (decided: {cr})")


# ---- propose


def test_propose_is_read_only_and_returns_candidates_ambiguity_and_impact(reference_story: Story) -> None:
    prepared(reference_story)
    before = {s: reference_story.read(s) for s in package_of(reference_story).existing_stages()}
    result = corrections.propose(package_of(reference_story), "REQ-001", "implementation", "vague")
    assert result["candidates"] == ["requirements"] and result["ambiguous"] is False
    assert "FR-001" in result["impact"] and "T001" in result["impact"]
    assert before == {s: reference_story.read(s) for s in before}


def test_a_restated_item_offers_its_own_stage_and_its_sources_stage(reference_story: Story) -> None:
    classify(reference_story, "ai-spec", ("AIS-001", None))
    result = corrections.propose(package_of(reference_story), "AIS-001", "plan", "wrong")
    assert result["candidates"][0] == "ai-spec" and "functional" in result["candidates"]
    assert result["ambiguous"] is True


def test_a_task_or_unknown_id_is_refused(reference_story: Story) -> None:
    with pytest.raises(EilExit) as exc:
        corrections.propose(package_of(reference_story), "T001", "implementation", "x")
    assert codes(exc) == ["unknown-item"]
    with pytest.raises(EilExit) as exc:
        corrections.propose(package_of(reference_story), "REQ-999", "implementation", "x")
    assert codes(exc) == ["unknown-item"]


# ---- open


def test_open_without_an_owner_when_ambiguous_is_refused_and_writes_nothing(reference_story: Story) -> None:
    classify(reference_story, "ai-spec", ("AIS-001", None))
    before = reference_story.read("ai-spec")
    with pytest.raises(EilExit) as exc:
        open_cr(reference_story, "AIS-001", None)
    assert codes(exc) == ["owner-ambiguous"] and reference_story.read("ai-spec") == before


def test_an_owner_that_is_not_a_candidate_is_refused(reference_story: Story) -> None:
    prepared(reference_story)
    with pytest.raises(EilExit) as exc:
        open_cr(reference_story, owner="plan")
    assert codes(exc) == ["owner-not-candidate"]


def test_the_ai_cannot_open_a_correction(reference_story: Story) -> None:
    prepared(reference_story)
    with pytest.raises(EilExit) as exc:
        corrections.open_correction(package_of(reference_story), "REQ-001", "code-review", "x", "claude")
    assert codes(exc) == ["ai-approval"]


def test_open_stores_the_wording_verbatim_and_allocates_story_wide_ids(reference_story: Story) -> None:
    prepared(reference_story)
    first = open_cr(reference_story)["correction"]
    second = open_cr(reference_story, "REQ-002", "  Analysts review   each pair.  ")["correction"]
    assert (first["id"], second["id"]) == ("CR-001", "CR-002")
    assert first["wording"] == WORDING and second["wording"] == "  Analysts review   each pair.  "
    assert first["status"] == "open" and first["owner"] == "requirements"
    assert [c["id"] for c in corrections.open_for(package_of(reference_story), "requirements")] == [
        "CR-001",
        "CR-002",
    ]


# ---- what an open correction blocks


def test_an_open_correction_blocks_only_its_item_and_what_traces_to_it(reference_story: Story) -> None:
    settle_derived(reference_story)
    open_cr(reference_story, "FR-003", None)
    pkg = package_of(reference_story)
    blocked = corrections.blocked_keys(pkg)
    assert set(blocked) == {
        "FR-003",
        *build_graph(__import__("eil.impact", fromlist=["x"]).parsed_story(pkg)).downstream(["FR-003"]),
    }
    assert "T003" in blocked and "T001" not in blocked
    hard, _ = staleness.scoped_work(pkg)
    assert "T003" in hard and "T001" not in hard
    assert any("CR-001" in str(cause) for cause in hard["T003"])


# ---- (decided: CR-###) eligibility


def test_the_persons_recorded_wording_carries_forward_on_a_short_ok(reference_story: Story) -> None:
    prepared(reference_story)
    open_cr(reference_story)
    reword(reference_story)
    listed = reviews.build_list(package_of(reference_story), "requirements", "changes")
    assert [(e.key, e.covered_by) for e in listed.entries] == [("REQ-001", "CR-001")]
    assert any("Correction wording is recorded as given" in limit for limit in listed.limits)
    result = confirm(reference_story)
    assert result["approval"]["reached"] == "carried-forward" and result["approval"]["rests_on"] == ["CR-001"]
    assert "comprehension" not in result["approval"]
    assert corrections.open_all(package_of(reference_story)) == []
    closed = corrections.find(package_of(reference_story), "CR-001")[1]
    assert closed["status"] == "closed" and closed["closed_by"] == "Ada Dev"


def test_text_that_differs_from_the_wording_is_not_covered_and_is_a_non_blocking_finding(
    reference_story: Story,
) -> None:
    prepared(reference_story)
    open_cr(reference_story)
    reword(reference_story, wording="The system detects duplicates on import, quickly.")
    pkg = package_of(reference_story)
    listed = reviews.build_list(pkg, "requirements", "changes")
    assert [(e.key, e.covered_by) for e in listed.entries] == [("REQ-001", None)]
    assert "correction-wording-mismatch" in found(reference_story)
    assert "decided-source-invalid" not in found(reference_story)


def test_a_correction_without_wording_never_covers(reference_story: Story) -> None:
    prepared(reference_story)
    open_cr(reference_story, wording=None)
    reword(reference_story)
    listed = reviews.build_list(package_of(reference_story), "requirements", "changes")
    assert [e.covered_by for e in listed.entries] == [None]


def test_a_correction_of_another_item_never_covers(reference_story: Story) -> None:
    prepared(reference_story)
    open_cr(reference_story, "REQ-002", "Analysts review flagged pairs.")
    reword(reference_story)
    listed = reviews.build_list(package_of(reference_story), "requirements", "changes")
    assert [e.covered_by for e in listed.entries] == [None]


def test_a_clause_naming_no_correction_stays_a_blocking_finding(reference_story: Story) -> None:
    prepared(reference_story)
    reword(reference_story, "CR-999")
    assert "decided-source-invalid" in found(reference_story)


# ---- a stage nobody approves


def test_confirm_on_a_never_approved_owner_closes_the_correction_and_writes_no_approval(
    reference_story: Story,
) -> None:
    classify(reference_story, "ai-spec", ("AIS-001", None))
    open_cr(reference_story, "AIS-001", AIS1_WORDING, owner="ai-spec")
    edit(reference_story, "ai-spec", "Implement behaviour 1.", AIS1_WORDING)
    pkg = package_of(reference_story)
    with pytest.raises(EilExit) as exc:
        reviews.confirm(
            pkg, CONFIG, "ai-spec", by="Ada Dev", confirmation="ok", summaries={"AIS-001": "Tighter."}
        )
    assert codes(exc) == ["not-amendable"]
    edit(
        reference_story,
        "ai-spec",
        f"{AIS1_WORDING} (traces: FR-001)",
        f"{AIS1_WORDING} (traces: FR-001) (decided: CR-001)",
    )
    classify(reference_story, "ai-spec", ("AIS-001", None))
    assert block_statuses(package_of(reference_story))["ai-spec"]["AIS-001"].status == "settled"
    result = reviews.confirm(
        package_of(reference_story),
        CONFIG,
        "ai-spec",
        by="Ada Dev",
        confirmation="ok",
        summaries={"AIS-001": "Tighter."},
    )
    assert result["closed"] == ["CR-001"] and result["still_open"] == []
    text = reference_story.read("ai-spec")
    assert (
        "eil:begin approval" not in text
        or '"by"' not in text.split("eil:begin approval")[1].split("eil:end approval")[0]
    )
    record = package_of(reference_story).record("ai-spec", "provenance")
    assert [c["item"] for c in record["changes"]] == ["AIS-001"] and record["changes"][0][
        "origin"
    ] == "CR-001"


# ---- the trace


def test_trace_shows_the_correction_with_its_origin(reference_story: Story) -> None:
    prepared(reference_story)
    open_cr(reference_story)
    result = (
        chain.trace(package_of(reference_story), to_ref="REQ-001")
        if False
        else chain.trace(package_of(reference_story), from_id="REQ-001")
    )
    assert [c["id"] for c in result["corrections"]] == ["CR-001"]
    assert "Correction CR-001 of REQ-001" in chain._render(result)
