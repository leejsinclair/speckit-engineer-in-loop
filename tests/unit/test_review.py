"""``eil review``: walk a stage's changes since its last approval one at a time (D-28), and the
judgment-scoping fix (D-29) it depends on so an unrelated criterion is never re-recorded.

Reproduces the dogfooding acceptance scenario: a new item, a diagram rename and a prose edit,
reviewed item by item, bring the stage back to approved with no comprehension question asked and
no other judgment criterion voided.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from eil import provenance
from eil.gates import check_stage
from eil.identity import Config
from eil.package import Package
from eil.results import EilExit

from tests.helpers.package import Story, approve_stages, with_functional

JUDGED = ["FUN-G10", "FUN-G12", "FUN-G13"]
NOW = "2026-09-29T09:00:00Z"


def judgments(tmp: Path) -> Path:
    path = tmp / "j.json"
    path.write_text(
        json.dumps(
            {"stage": "functional", "judgments": [{"id": i, "status": "met", "reason": "ok"} for i in JUDGED]}
        )
    )
    return path


@pytest.fixture
def config() -> Config:
    return Config(default_developer="Ada Dev", approvers={"functional": ["Ada Dev"]})


def approved(story_dir: Story, tmp_path: Path) -> Package:
    with_functional(story_dir)
    package = Package(story_dir.root)
    check_stage(package, "functional", judgments_path=judgments(tmp_path))
    approve_stages(story_dir, "requirements", "functional")
    return Package(story_dir.root)


def refusals(exc: pytest.ExceptionInfo[EilExit]) -> list[str]:
    return [r["code"] for r in exc.value.payload["refusals"]]


def test_start_refuses_a_stage_that_still_needs_no_review(story_dir: Story, tmp_path: Path) -> None:
    package = approved(story_dir, tmp_path)
    with pytest.raises(EilExit) as exc:
        provenance.start(package, "functional")
    assert refusals(exc) == ["not-amendable"]


def test_the_full_acceptance_scenario(story_dir: Story, tmp_path: Path) -> None:
    """New item, diagram rename, prose edit — reviewed one at a time, zero comprehension
    questions, unrelated judgments untouched, a visible reviewed_change_by_change mark."""
    package = approved(story_dir, tmp_path)
    before = Package(story_dir.root).state("functional").approval
    assert before is not None

    text = story_dir.read("functional")
    text = text.replace(
        "**FR-001**: The system shall flag duplicate customers on import. (traces: REQ-001)",
        "**FR-001**: The system shall flag duplicate customers on import. (traces: REQ-001)\n\n"
        "**FR-002**: A heading that expands an item is not a second definition. (traces: REQ-001)",
    )
    text = text.replace(
        "Two customers with the same tax id are duplicates.",
        "Two customers with the same tax id, or the same email, are duplicates.",
    )
    text = text.replace(
        "Analyst->>System: Upload customer file", "Analyst->>System: Upload customer file for review"
    )
    story_dir.write("functional", text)

    package = Package(story_dir.root)
    assert package.state("functional").state == "needs-re-review"

    started = provenance.start(package, "functional")
    item_ids = {row["id"] for row in started["items"]}
    assert "FR-002" in item_ids and "ART-002" in item_ids
    assert any(row["title"] == "Business Rules" for row in started["sections"])

    config = Config(default_developer="Ada Dev", approvers={"functional": ["Ada Dev"]})
    accepted = provenance.accept(
        package,
        config,
        "functional",
        items=["FR-002", "ART-002"],
        sections=["Business Rules"],
        by="Ada Dev",
        note="agreed in conversation",
    )
    assert len(accepted["created"]) == 3
    assert "**FR-002**" in story_dir.read("functional")
    assert "(decided: RVW-001)" in story_dir.read("functional") or "(decided: RVW-002)" in story_dir.read(
        "functional"
    )

    package = Package(story_dir.root)
    # FUN-G12/FUN-G13 are whole-document judgment criteria (no named headings, D-29): any edit
    # voids them and the AI re-submits its verdict, same as ever — this is not new friction, and
    # is independent of the item/section-level review above.
    check_stage(package, "functional", judgments_path=judgments(tmp_path))
    result = provenance.finish(package, config, "functional", "Ada Dev", "Yes, I reviewed each change.")

    assert result["ok"] is True
    record = result["approval"]
    assert record["reviewed_change_by_change"] is True
    assert len(record["reviewed_ids"]) == 3

    # No comprehension question was asked: the region is complete, every level not-applicable,
    # naming the review as the reason.
    comp = json.dumps(Package(story_dir.root).record("functional", "comprehension"))
    assert '"outcome": "not-applicable"' in comp
    assert "each change reviewed individually" in comp or "recorded human decision" in comp

    # The other judgment criteria were never re-recorded: their reason is exactly what step 1 gave.
    after_check = check_stage(Package(story_dir.root), "functional", write=False)
    fun_g10 = next(c for c in after_check.criteria if c.id == "FUN-G10")
    assert fun_g10.reason == "AI assessment: ok"

    assert Package(story_dir.root).state("functional").state == "approved"


def test_finish_refuses_when_nothing_has_been_reviewed_yet(story_dir: Story, tmp_path: Path) -> None:
    package = approved(story_dir, tmp_path)
    text = story_dir.read("functional").replace(
        "Two customers with the same tax id are duplicates.",
        "Two customers with the same tax id, or the same email, are duplicates.",
    )
    story_dir.write("functional", text)
    package = Package(story_dir.root)
    config = Config(default_developer="Ada Dev", approvers={"functional": ["Ada Dev"]})
    with pytest.raises(EilExit) as exc:
        provenance.finish(package, config, "functional", "Ada Dev", "Yes.")
    assert refusals(exc) == ["amend-not-covered"]


def test_accept_refuses_an_item_that_did_not_actually_change(story_dir: Story, tmp_path: Path) -> None:
    package = approved(story_dir, tmp_path)
    text = story_dir.read("functional").replace(
        "Two customers with the same tax id are duplicates.",
        "Two customers with the same tax id, or the same email, are duplicates.",
    )
    story_dir.write("functional", text)
    package = Package(story_dir.root)
    config = Config(default_developer="Ada Dev", approvers={"functional": ["Ada Dev"]})
    with pytest.raises(EilExit) as exc:
        provenance.accept(package, config, "functional", items=["FR-001"], sections=[], by="Ada Dev")
    assert refusals(exc) == ["unknown-item"]


def test_accept_refuses_a_section_that_did_not_actually_change(story_dir: Story, tmp_path: Path) -> None:
    package = approved(story_dir, tmp_path)
    config = Config(default_developer="Ada Dev", approvers={"functional": ["Ada Dev"]})
    # nothing changed at all yet, so functional is still approved, not needs-re-review
    with pytest.raises(EilExit) as exc:
        provenance.accept(package, config, "functional", items=[], sections=["Business Rules"], by="Ada Dev")
    assert refusals(exc) == ["not-amendable"]


def test_the_ai_cannot_accept_a_change(story_dir: Story, tmp_path: Path) -> None:
    package = approved(story_dir, tmp_path)
    text = story_dir.read("functional").replace(
        "Two customers with the same tax id are duplicates.",
        "Two customers with the same tax id, or the same email, are duplicates.",
    )
    story_dir.write("functional", text)
    package = Package(story_dir.root)
    config = Config(default_developer="Ada Dev", approvers={"functional": ["Ada Dev"]})
    with pytest.raises(EilExit) as exc:
        provenance.accept(package, config, "functional", items=[], sections=["Business Rules"], by="the AI")
    assert "ai-approval" in refusals(exc)
