"""Classification of content blocks (T033; determinism requirement 24; FR-009, FR-011, FR-013; research D-32)."""

from __future__ import annotations

import io
import json
from typing import Any

import pytest
from eil import blockstatus, cli, provenance
from eil.package import Package
from eil.results import EilExit

from tests.helpers.derived import edit
from tests.helpers.package import Story


def package_of(story: Story) -> Package:
    return Package(story.root)


def classify(story: Story, stage: str, *verdicts: tuple[str, str | None]) -> dict[str, Any]:
    data = {"stage": stage, "blocks": [{"block": key, "adds": adds} for key, adds in verdicts]}
    return provenance.classify(package_of(story), stage, data)


def entry(story: Story, stage: str, key: str) -> dict[str, Any]:
    return story_record(story, stage)["blocks"][key]


def story_record(story: Story, stage: str) -> dict[str, Any]:
    obj = package_of(story).doc(stage).read_provenance().obj
    assert obj is not None
    return obj


def status(story: Story, stage: str, key: str) -> str:
    return blockstatus.block_statuses(package_of(story))[stage][key].status


def every_ais(story: Story) -> list[tuple[str, str | None]]:
    return [(b.key, None) for b in blockstatus.blocks_of(package_of(story).doc("ai-spec")) if b.numbered]


def usage_code(story: Story, stage: str, data: Any) -> int:
    with pytest.raises(EilExit) as exc:
        provenance.classify(package_of(story), stage, data)
    return exc.value.code


# ---- class rules and precedence


def test_a_block_citing_a_settled_source_with_no_addition_is_restated(reference_story: Story) -> None:
    classify(reference_story, "ai-spec", ("AIS-001", None))
    got = entry(reference_story, "ai-spec", "AIS-001")
    assert got["class"] == "restated"
    assert list(got["cites"]) == ["FR-001"]
    assert got["cites"]["FR-001"] == package_of(reference_story).current_item_hashes()["FR-001"]
    assert status(reference_story, "ai-spec", "AIS-001") == "settled"


def test_an_adds_verdict_makes_the_block_inferred_with_its_reason(reference_story: Story) -> None:
    classify(reference_story, "ai-spec", ("AIS-007", "a retry policy of 3 attempts"))
    got = entry(reference_story, "ai-spec", "AIS-007")
    assert got["class"] == "inferred" and got["adds"] == "a retry policy of 3 attempts"
    assert "cites" not in got
    assert status(reference_story, "ai-spec", "AIS-007") == "needs-review"


def test_no_verdict_at_all_is_inferred(reference_story: Story) -> None:
    classify(reference_story, "ai-spec", ("AIS-001", None))
    assert entry(reference_story, "ai-spec", "AIS-002")["class"] == "inferred"
    assert entry(reference_story, "ai-spec", "AIS-002").get("adds") is None


def test_a_block_with_no_citation_is_inferred_whatever_the_verdict(reference_story: Story) -> None:
    edit(reference_story, "ai-spec", "Follow decision rule 13. (traces: DEC-002)", "Follow decision rule 13.")
    classify(reference_story, "ai-spec", ("AIS-013", None))
    assert entry(reference_story, "ai-spec", "AIS-013")["class"] == "inferred"


def test_decided_takes_precedence_over_restated_and_inferred(reference_story: Story) -> None:
    edit(reference_story, "ai-spec", "Implement behaviour 2. (traces: FR-002)", "Implement behaviour 2. (traces: FR-002) (decided: AIS-001)")
    classify(reference_story, "ai-spec", ("AIS-002", "something else"))
    assert entry(reference_story, "ai-spec", "AIS-002")["class"] == "decided"
    assert status(reference_story, "ai-spec", "AIS-002") == "settled"


def test_a_decided_clause_that_cannot_be_verified_is_not_decided(reference_story: Story) -> None:
    edit(reference_story, "ai-spec", "Implement behaviour 2. (traces: FR-002)", "Implement behaviour 2. (traces: FR-002) (decided: AIS-777)")
    classify(reference_story, "ai-spec", ("AIS-002", None))
    assert entry(reference_story, "ai-spec", "AIS-002")["class"] != "decided"


def test_a_citation_to_a_changed_source_is_inferred(reference_story: Story) -> None:
    edit(reference_story, "functional", "behaviour 3 of duplicate analysis", "behaviour 3 of duplicate analysis, reworded")
    classify(reference_story, "ai-spec", ("AIS-003", None), ("AIS-004", None))
    assert entry(reference_story, "ai-spec", "AIS-003")["class"] == "inferred"
    assert entry(reference_story, "ai-spec", "AIS-004")["class"] == "restated"


def test_a_citation_to_an_id_nothing_defines_is_inferred(reference_story: Story) -> None:
    edit(reference_story, "ai-spec", "Implement behaviour 5. (traces: FR-005)", "Implement behaviour 5. (traces: FR-999)")
    classify(reference_story, "ai-spec", ("AIS-005", None))
    assert entry(reference_story, "ai-spec", "AIS-005")["class"] == "inferred"


# ---- sources below the approved documents settle by block status (D-32)


def test_a_plan_section_and_task_follow_the_status_of_the_ai_spec_item_they_restate(reference_story: Story) -> None:
    edit(reference_story, "plan", "Summary (traces: DEC-001)", "Summary (traces: AIS-001)")
    edit(reference_story, "plan", "Technical Context (traces: DEC-002)", "Technical Context (traces: AIS-002)")
    classify(reference_story, "ai-spec", ("AIS-001", None), ("AIS-002", "extra behaviour"))
    classify(reference_story, "plan", ("§Summary", None), ("§Technical Context", None))
    assert entry(reference_story, "plan", "§Summary")["class"] == "restated"
    assert entry(reference_story, "plan", "§Technical Context")["class"] == "inferred"

    classify(reference_story, "tasks", ("T001", None), ("T002", None))
    assert entry(reference_story, "tasks", "T001")["class"] == "restated"
    assert entry(reference_story, "tasks", "T002")["class"] == "inferred"


def test_a_source_that_is_stale_makes_its_restating_block_inferred(reference_story: Story) -> None:
    classify(reference_story, "ai-spec", *every_ais(reference_story))
    edit(reference_story, "functional", "behaviour 1 of duplicate analysis", "behaviour 1 of duplicate analysis, reworded")
    classify(reference_story, "tasks", ("T001", None), ("T002", None))
    assert entry(reference_story, "tasks", "T001")["class"] == "inferred"
    assert entry(reference_story, "tasks", "T002")["class"] == "restated"


# ---- what classification leaves alone

def test_classifying_again_keeps_a_reviewed_block_reviewed(reference_story: Story) -> None:
    from tests.helpers.derived import answer_all

    classify(reference_story, "ai-spec", ("AIS-007", "extra"))
    answer_all(reference_story, "ai-spec", "inferred")
    before = entry(reference_story, "ai-spec", "AIS-007")
    assert before["reviewed"]
    classify(reference_story, "ai-spec", ("AIS-007", "extra"))
    assert entry(reference_story, "ai-spec", "AIS-007")["reviewed"] == before["reviewed"]
    assert status(reference_story, "ai-spec", "AIS-007") == "settled"


def test_an_edited_reviewed_block_loses_its_review(reference_story: Story) -> None:
    from tests.helpers.derived import answer_all

    classify(reference_story, "ai-spec", ("AIS-007", "extra"))
    answer_all(reference_story, "ai-spec", "inferred")
    edit(reference_story, "ai-spec", "Implement behaviour 7.", "Implement behaviour 7, differently.")
    classify(reference_story, "ai-spec", ("AIS-007", "extra"))
    assert "reviewed" not in entry(reference_story, "ai-spec", "AIS-007")
    assert status(reference_story, "ai-spec", "AIS-007") == "needs-review"


def test_classifying_an_approved_stage_keeps_its_adopted_blocks(reference_story: Story) -> None:
    classify(reference_story, "requirements", ("REQ-001", "unsupported claim"))
    assert entry(reference_story, "requirements", "REQ-001")["class"] == "adopted"


# ---- the classification file is validated (exit 2)


@pytest.mark.parametrize(
    "data",
    [
        {"stage": "ai-spec", "blocks": [{"block": "AIS-999", "adds": None}]},
        {"stage": "ai-spec", "blocks": [{"block": "AIS-001", "adds": None, "colour": "red"}]},
        {"stage": "ai-spec", "blocks": [{"adds": None}]},
        {"stage": "ai-spec", "blocks": [{"block": "AIS-001", "adds": 3}]},
        {"stage": "ai-spec", "blocks": [], "extra": 1},
        {"stage": "plan", "blocks": []},
        {"blocks": []},
        {"stage": "ai-spec", "blocks": "AIS-001"},
        ["AIS-001"],
    ],
)
def test_an_invalid_classification_is_a_usage_error_and_writes_nothing(reference_story: Story, data: Any) -> None:
    before = reference_story.read("ai-spec")
    assert usage_code(reference_story, "ai-spec", data) == 2
    assert reference_story.read("ai-spec") == before


def test_the_cli_reads_the_file_and_exits_2_on_bad_input(
    reference_story: Story, tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cli, "_regenerate_overview", lambda ctx, package: False)
    good, bad = tmp_path / "good.json", tmp_path / "bad.json"
    good.write_text(json.dumps({"stage": "ai-spec", "blocks": [{"block": "AIS-001", "adds": None}]}))
    bad.write_text("not json")

    def run(path: Any) -> int:
        return cli.main(
            ["blocks", "classify", "--stage", "ai-spec", "--file", str(path), "--json", "--feature-dir", str(reference_story.root)],
            cwd=reference_story.root, env={}, stdout=io.StringIO(), stderr=io.StringIO(),
        )  # fmt: skip

    assert run(bad) == 2
    assert run(tmp_path / "missing.json") == 2
    assert run(good) == 0
    assert entry(reference_story, "ai-spec", "AIS-001")["class"] == "restated"


# ---- reclassify: scrutiny can be added by anyone, never removed this way


def test_anyone_may_reclassify_a_restated_block_as_inferred_and_it_is_recorded(reference_story: Story) -> None:
    classify(reference_story, "ai-spec", ("AIS-001", None))
    provenance.reclassify(package_of(reference_story), "ai-spec", "AIS-001", by="Sam QA", reason="reads wider than FR-001")
    got = entry(reference_story, "ai-spec", "AIS-001")
    assert got["class"] == "inferred" and "cites" not in got
    assert "Sam QA" in got["adds"] and "reads wider than FR-001" in got["adds"]
    assert status(reference_story, "ai-spec", "AIS-001") == "needs-review"


def test_there_is_no_path_from_inferred_back_to_restated(reference_story: Story) -> None:
    classify(reference_story, "ai-spec", ("AIS-001", None))
    provenance.reclassify(package_of(reference_story), "ai-spec", "AIS-001", by="Sam QA")
    classify(reference_story, "ai-spec", ("AIS-001", None))
    assert entry(reference_story, "ai-spec", "AIS-001")["class"] == "inferred"
    with pytest.raises(EilExit) as exc:
        provenance.reclassify(package_of(reference_story), "ai-spec", "AIS-001", by="Sam QA")
    assert exc.value.payload["refusals"][0]["code"] == "not-restated"


def test_reclassify_refuses_an_unknown_block(reference_story: Story) -> None:
    classify(reference_story, "ai-spec", ("AIS-001", None))
    with pytest.raises(EilExit) as exc:
        provenance.reclassify(package_of(reference_story), "ai-spec", "AIS-404", by="Sam QA")
    assert exc.value.payload["refusals"][0]["code"] == "unknown-item"
