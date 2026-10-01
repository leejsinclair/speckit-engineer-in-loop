"""``[ai-draft]`` is a cue the helper renders from block status, never the source of it (T034; determinism
requirement 25; FR-046; research D-33)."""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest
from eil import blockstatus, cli, provenance, records, reviews
from eil.blocks import Doc, write_provenance
from eil.gates import check_stage
from eil.identity import Config
from eil.package import Package
from eil.records import approve, override
from eil.results import EilExit

from tests.helpers.package import Story, block_entry, requirements_doc

JUDGED = ["REQ-G01", "REQ-G11", "REQ-G12", "REQ-G13"]
CONFIG = Config(default_developer="Ada Dev", approvers={"requirements": ["Ada Dev"]}, abbreviation_authorisers=[])
UNREVIEWED = ("Background", "Risks")


@pytest.fixture(autouse=True)
def fixed_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(records, "utc_now", lambda: "2026-09-25T10:14:03Z")
    monkeypatch.setattr(cli, "_regenerate_overview", lambda ctx, package: False)


def judgments(tmp: Path) -> Path:
    path = tmp / "judgments.json"
    path.write_text(
        json.dumps({"stage": "requirements", "judgments": [{"id": c, "status": "met", "reason": "fine"} for c in JUDGED]})
    )
    return path


@pytest.fixture
def story(story_dir: Story, tmp_path: Path) -> Story:
    """Requirements with a met gate; the Background and Risks paragraphs are recorded inferred and
    unreviewed, and carry no tag."""
    story_dir.write("requirements", requirements_doc())
    package = Package(story_dir.root)
    record = blockstatus.adopt(package, "requirements")
    assert record is not None
    by_section = {b.section: b for b in blockstatus.blocks_of(package.doc("requirements")) if b.kind == "prose"}
    for section in UNREVIEWED:
        block = by_section[section]
        record["blocks"][block.key] = block_entry(block.hash, "inferred")
    story_dir.write("requirements", write_provenance(story_dir.read("requirements"), record))
    check_stage(Package(story_dir.root), "requirements", judgments_path=judgments(tmp_path))
    return story_dir


def package_of(story: Story) -> Package:
    return Package(story.root)


def try_approve(story: Story) -> list[str]:
    try:
        approve(package_of(story), CONFIG, "requirements", "Ada Dev", "Yes, this is the problem we intend to solve.")
    except EilExit as exc:
        return [r["code"] for r in exc.payload["refusals"]]
    return []


def sync(story: Story) -> int:
    return cli.main(
        ["sync", "--json", "--feature-dir", str(story.root)],
        cwd=story.root, env={}, stdout=io.StringIO(), stderr=io.StringIO(),
    )  # fmt: skip


def tagged_sections(story: Story) -> set[str]:
    package = package_of(story)
    return {b.section for b in blockstatus.blocks_of(package.doc("requirements")) if "[ai-draft]" in b.text} | {
        b.section
        for b in blockstatus.blocks_of(package.doc("requirements"))
        if any("[ai-draft]" in line.raw for line in package.doc("requirements").lines[b.first_line - 1 : b.last_line])
    }


def review_all(story: Story) -> None:
    listed = reviews.build_list(package_of(story), "requirements", "inferred")
    reviews.answer(
        package_of(story), CONFIG, "requirements", "inferred",
        digest=listed.digest, by="Ada Dev", reply="ok", all_=True,
    )  # fmt: skip


def test_approve_refuses_while_an_inferred_block_is_unreviewed_even_with_no_tag_present(story: Story) -> None:
    assert "[ai-draft]" not in story.read("requirements")
    assert try_approve(story) == ["unreviewed-ai-content"]


def test_approve_passes_once_the_blocks_are_reviewed_even_if_a_tag_was_hand_added(story: Story) -> None:
    review_all(story)
    story.write("requirements", story.read("requirements").replace("Imports create duplicate customers.", "Imports create duplicate customers. [ai-draft]"))
    assert try_approve(story) == []
    assert package_of(story).state("requirements").state == "approved"


def test_sync_renders_the_tag_on_exactly_the_unreviewed_inferred_blocks(story: Story) -> None:
    assert sync(story) == 0
    assert tagged_sections(story) == set(UNREVIEWED)


def test_sync_removes_a_tag_from_a_block_that_is_not_unreviewed_inferred(story: Story) -> None:
    story.write("requirements", story.read("requirements").replace("Customer IDs are stable.", "Customer IDs are stable. [ai-draft]"))
    sync(story)
    assert tagged_sections(story) == set(UNREVIEWED)


def test_removing_a_tag_by_hand_changes_nothing_and_sync_puts_it_back(story: Story) -> None:
    sync(story)
    before = {k: i.status for k, i in blockstatus.block_statuses(package_of(story))["requirements"].items()}
    story.write("requirements", story.read("requirements").replace(" [ai-draft]", ""))
    assert {k: i.status for k, i in blockstatus.block_statuses(package_of(story))["requirements"].items()} == before
    assert try_approve(story) == ["unreviewed-ai-content"]
    sync(story)
    assert tagged_sections(story) == set(UNREVIEWED)


def test_re_rendering_leaves_the_fingerprint_unchanged(story: Story) -> None:
    fingerprint = package_of(story).fingerprint("requirements")
    sync(story)
    assert story.read("requirements").count("[ai-draft]") == len(UNREVIEWED)
    assert package_of(story).fingerprint("requirements") == fingerprint


def test_rendering_touches_only_the_first_line_of_a_block_and_is_idempotent(story: Story) -> None:
    sync(story)
    once = story.read("requirements")
    sync(story)
    assert story.read("requirements") == once
    plain = once.replace(" [ai-draft]", "")
    assert plain == story.read("requirements").replace(" [ai-draft]", "")


def test_reviewing_removes_the_tags(story: Story) -> None:
    sync(story)
    review_all(story)
    assert "[ai-draft]" not in story.read("requirements")


def test_render_cues_adds_and_removes_a_tag_on_the_first_line_only() -> None:
    text = "# T\n\n## S\n\nFirst line\nsecond line [ai-draft]\n\n```text\ncode [ai-draft]\n```\n"
    blocks = blockstatus.blocks_of(Doc(text))
    out = provenance.render_cues(text, blocks, set())
    assert out == "# T\n\n## S\n\nFirst line\nsecond line\n\n```text\ncode [ai-draft]\n```\n"
    key = blockstatus.blocks_of(Doc(out))[0].key
    again = provenance.render_cues(out, blockstatus.blocks_of(Doc(out)), {key})
    assert again == "# T\n\n## S\n\nFirst line [ai-draft]\nsecond line\n\n```text\ncode [ai-draft]\n```\n"


def test_the_override_of_unreviewed_ai_content_still_works(story: Story, tmp_path: Path) -> None:
    assert try_approve(story) == ["unreviewed-ai-content"]
    override(package_of(story), CONFIG, "requirements", "unreviewed-ai-content", by="Ada Dev", reason="reviewed in pairing")
    check_stage(package_of(story), "requirements", judgments_path=judgments(tmp_path))
    assert try_approve(story) == []
