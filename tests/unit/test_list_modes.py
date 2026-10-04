"""T031: a review list is presented by its size (determinism 46 and 48; research D-51; FR-014 to FR-018).

At most ``review.one_at_a_time_max`` entries (default 8) are walked one at a time; more are shown
as a grouped summary answered in one reply. Each scaffolding section (Actors, Dependencies, Not
applicable, Inputs, Outputs) is one entry. No list holds a restated or adopted block.
"""

from __future__ import annotations

from typing import Any

import pytest
from eil import blockstatus, reviews
from eil.identity import Config
from eil.package import Package

from tests.conftest import files_snapshot
from tests.helpers.package import Story, functional_doc, requirements_doc, with_record_sections

CONFIG = Config(
    default_developer="Ada Dev", approvers={"requirements": ["Ada Dev"], "functional": ["Ada Dev"]}
)


def with_inferred(story: Story, count: int) -> list[str]:
    """Requirements whose only unreviewed blocks are ``count`` REQ items; returns their ids."""
    items = "\n\n".join(
        f"**REQ-{n:03d}**: Requirement number {n}. It has a second sentence." for n in range(1, count + 1)
    )
    story.write("requirements", requirements_doc({"Desired Outcome": items}))
    package = Package(story.root)
    record = blockstatus.adopt(package, "requirements")
    assert record is not None
    ids = [f"REQ-{n:03d}" for n in range(1, count + 1)]
    for key in ids:
        record["blocks"][key] = {"hash": record["blocks"][key]["hash"], "class": "inferred"}
    package.write_record("requirements", "provenance", record)
    return ids


def listed(story: Story, stage: str = "requirements", threshold: int = 8) -> reviews.ReviewList:
    return reviews.build_list(Package(story.root), stage, "inferred", threshold=threshold)


@pytest.mark.parametrize(("count", "mode"), [(1, "one-at-a-time"), (8, "one-at-a-time"), (9, "summary")])
def test_the_mode_follows_the_size(story_dir: Story, count: int, mode: str) -> None:
    with_inferred(story_dir, count)
    found = listed(story_dir)
    assert len(found.entries) == count
    assert found.mode == mode and found.threshold == 8
    assert found.to_json()["mode"] == mode


def test_the_threshold_is_configurable(story_dir: Story) -> None:
    with_inferred(story_dir, 4)
    assert listed(story_dir, threshold=3).mode == "summary"
    assert listed(story_dir, threshold=4).mode == "one-at-a-time"


def test_the_configuration_key_is_read(tmp_path: Any) -> None:
    from eil.identity import load_config

    config = tmp_path / ".specify" / "extensions" / "eil"
    config.mkdir(parents=True)
    (config / "eil-config.yml").write_text("review:\n  one_at_a_time_max: 3\n")
    assert load_config(tmp_path).one_at_a_time_max == 3
    assert Config().one_at_a_time_max == 8


def test_entries_carry_a_short_deterministic_summary(story_dir: Story) -> None:
    with_inferred(story_dir, 2)
    entry = listed(story_dir).entries[0]
    assert entry.summary == "Requirement number 1."
    long = "word " * 60
    assert len(reviews.summarise(f"**REQ-009**: {long}")) <= 120
    assert reviews.summarise("A first sentence. A second.") == "A first sentence."
    assert (
        reviews.summarise("**FR-001**: The system shall flag duplicates. (traces: REQ-001)")
        == "The system shall flag duplicates."
    )


def test_entries_are_grouped_by_section(story_dir: Story) -> None:
    ids = with_inferred(story_dir, 3)
    groups = listed(story_dir).to_json()["groups"]
    assert groups == [{"section": "Desired Outcome", "entries": ids}]


@pytest.fixture
def actors(story_dir: Story) -> Story:
    """A Functional Specification with twelve Actors blocks, nothing reviewed."""
    from tests.helpers.package import export_record, write_export

    people = "\n\n".join(f"- **Actor {n}**: does thing {n}" for n in range(1, 13))
    story_dir.write("requirements", requirements_doc())
    text = functional_doc({"Actors": people}, wireframe=export_record(sha256=write_export(story_dir.root)))
    story_dir.write("functional", with_record_sections(text, {"version": 1, "blocks": {}}))
    return story_dir


def test_a_scaffolding_section_is_one_entry(actors: Story) -> None:
    found = listed(actors, "functional")
    keys = [e.key for e in found.entries]
    assert "§Actors" in keys
    entry = next(e for e in found.entries if e.key == "§Actors")
    assert len(entry.members) == 12
    assert not any(k.startswith("Actors#") for k in keys)
    for name in ("Inputs", "Outputs"):
        assert f"§{name}" in keys


def test_answering_the_section_entry_settles_every_member(actors: Story) -> None:
    found = listed(actors, "functional")
    members = set(next(e for e in found.entries if e.key == "§Actors").members)
    reviews.answer(
        Package(actors.root), CONFIG, "functional", "inferred",
        digest=found.digest, by="Ada Dev", reply="ok except §Inputs", all_except=["§Inputs"],
    )  # fmt: skip
    statuses = blockstatus.block_statuses(Package(actors.root))["functional"]
    assert all(statuses[k].status == "settled" for k in members)
    inputs = [k for k, i in statuses.items() if i.block.section == "Inputs"]
    assert inputs and all(statuses[k].status == "needs-review" for k in inputs)


def test_no_list_holds_a_settled_restated_or_adopted_block(legacy_upgrade: Story) -> None:
    """Determinism 48. The block-review lists hold only blocks that need review; the changes list holds
    only items changed since the approval (a changed item is listed even when its block is
    ``settled-pending``, determinism 50), never an unchanged restated or adopted block."""
    from eil import cli, provenance

    cli._persist_adoption(Package(legacy_upgrade.root))
    package = Package(legacy_upgrade.root)
    statuses = blockstatus.block_statuses(package)
    for stage in package.existing_stages():
        for kind in ("inferred", "unknown-currency"):
            for entry in reviews.build_list(package, stage, kind).entries:
                for key in entry.members or [entry.key]:
                    info = statuses[stage].get(key)
                    assert info is not None and info.status not in ("settled", "settled-pending"), (
                        stage,
                        kind,
                        key,
                    )
        changed = {r.id for r in provenance.change_rows(package, stage)}
        for entry in reviews.build_list(package, stage, "changes").entries:
            assert entry.key.startswith("legacy:") or entry.key in changed, (stage, entry.key)


def test_review_show_is_read_only_and_gives_full_text(actors: Story) -> None:
    before = files_snapshot(actors.root)
    package = Package(actors.root)
    entry = reviews.show_entries(package, "functional", "inferred", entry="§Actors")
    assert "Actor 12" in entry["text"]
    group = reviews.show_entries(package, "functional", "inferred", group="Actors")
    assert "Actor 1" in group["text"]
    everything = reviews.show_entries(package, "functional", "inferred", all_=True)
    assert "Actor 7" in everything["text"] and "Two customers with the same tax id" in everything["text"]
    assert files_snapshot(actors.root) == before
