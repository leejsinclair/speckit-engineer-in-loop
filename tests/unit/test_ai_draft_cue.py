"""Status comes from hashes, never from an ``[ai-draft]`` tag (002 D-33), and the helper writes no tag into
a document at all: the cue is shown by ``eil show`` and the review lists (003 T019, D-50, FR-037)."""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest
from eil import blockstatus, cli, provenance, records, reviews
from eil.blocks import write_provenance
from eil.gates import check_stage
from eil.identity import Config
from eil.package import Package
from eil.records import approve, override
from eil.results import EilExit

from tests.helpers.package import Story, block_entry, requirements_doc

JUDGED = ["REQ-G01", "REQ-G11", "REQ-G12", "REQ-G13"]
CONFIG = Config(
    default_developer="Ada Dev", approvers={"requirements": ["Ada Dev"]}, abbreviation_authorisers=[]
)
UNREVIEWED = ("Background", "Risks")


@pytest.fixture(autouse=True)
def fixed_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(records, "utc_now", lambda: "2026-09-25T10:14:03Z")
    monkeypatch.setattr(cli, "_regenerate_overview", lambda ctx, package: False)


def judgments(tmp: Path) -> Path:
    path = tmp / "judgments.json"
    path.write_text(
        json.dumps(
            {
                "stage": "requirements",
                "judgments": [{"id": c, "status": "met", "reason": "fine"} for c in JUDGED],
            }
        )
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
    by_section = {
        b.section: b for b in blockstatus.blocks_of(package.doc("requirements")) if b.kind == "prose"
    }
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
        approve(
            package_of(story),
            CONFIG,
            "requirements",
            "Ada Dev",
            "Yes, this is the problem we intend to solve.",
        )
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
    return {
        b.section for b in blockstatus.blocks_of(package.doc("requirements")) if "[ai-draft]" in b.text
    } | {
        b.section
        for b in blockstatus.blocks_of(package.doc("requirements"))
        if any(
            "[ai-draft]" in line.raw
            for line in package.doc("requirements").lines[b.first_line - 1 : b.last_line]
        )
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
    story.write(
        "requirements",
        story.read("requirements").replace(
            "Imports create duplicate customers.", "Imports create duplicate customers. [ai-draft]"
        ),
    )
    assert try_approve(story) == []
    assert package_of(story).state("requirements").state == "approved"


def test_sync_writes_no_tag_into_the_document(story: Story) -> None:
    """003 D-50: the cue is shown by `eil show` and the review lists, never written into a document."""
    assert sync(story) == 0
    assert "[ai-draft]" not in story.read("requirements")
    assert tagged_sections(story) == set()


def test_sync_strips_existing_tags_and_keeps_every_fingerprint_and_status(story: Story) -> None:
    text = story.read("requirements")
    for old in ("Imports create duplicate customers.", "Customer IDs are stable."):
        text = text.replace(old, old + " [ai-draft]")
    story.write("requirements", text)
    fingerprint = package_of(story).fingerprint("requirements")
    before = {k: i.status for k, i in blockstatus.block_statuses(package_of(story))["requirements"].items()}
    sync(story)
    assert "[ai-draft]" not in story.read("requirements")
    assert package_of(story).fingerprint("requirements") == fingerprint
    assert {
        k: i.status for k, i in blockstatus.block_statuses(package_of(story))["requirements"].items()
    } == before


def test_a_tag_in_an_html_comment_is_left_alone() -> None:
    from eil.blocks import strip_ai_draft

    text = "# T\n\n<!-- write [ai-draft] by hand? never -->\nBody [ai-draft]\n\n```text\nliteral [ai-draft]\n```\n"
    assert (
        strip_ai_draft(text)
        == "# T\n\n<!-- write [ai-draft] by hand? never -->\nBody\n\n```text\nliteral\n```\n"
    )


def test_classify_and_answer_write_no_tag(story: Story, tmp_path: Path) -> None:
    package = package_of(story)
    keys = [b.key for b in blockstatus.blocks_of(package.doc("requirements")) if b.section in UNREVIEWED]
    path = tmp_path / "classes.json"
    path.write_text(
        json.dumps({"stage": "requirements", "blocks": [{"block": k, "adds": "an inference"} for k in keys]})
    )
    provenance.classify(package, "requirements", json.loads(path.read_text()))
    assert "[ai-draft]" not in story.read("requirements")
    review_all(story)
    assert "[ai-draft]" not in story.read("requirements")


def test_an_agent_edit_by_matching_its_own_text_applies_after_classification(
    story: Story, tmp_path: Path
) -> None:
    """FR-037: the text the agent wrote is still in the document, byte for byte, after the helper ran."""
    written = "Imports create duplicate customers.\n"  # an edit whose match spans the end of the line
    package = package_of(story)
    keys = [b.key for b in blockstatus.blocks_of(package.doc("requirements")) if b.section == "Background"]
    provenance.classify(
        package,
        "requirements",
        {"stage": "requirements", "blocks": [{"block": k, "adds": "x"} for k in keys]},
    )
    sync(story)
    text = story.read("requirements")
    assert text.count(written) == 1
    story.write("requirements", text.replace(written, "Imports create duplicate customer records.\n"))
    assert "duplicate customer records." in story.read("requirements")


def test_reviewing_settles_the_blocks_without_touching_the_prose(story: Story) -> None:
    def texts() -> list[str]:
        return [b.text for b in blockstatus.blocks_of(package_of(story).doc("requirements"))]

    before = texts()
    review_all(story)
    assert try_approve(story) == []
    assert texts() == before


def test_the_override_of_unreviewed_ai_content_still_works(story: Story, tmp_path: Path) -> None:
    assert try_approve(story) == ["unreviewed-ai-content"]
    override(
        package_of(story),
        CONFIG,
        "requirements",
        "unreviewed-ai-content",
        by="Ada Dev",
        reason="reviewed in pairing",
    )
    check_stage(package_of(story), "requirements", judgments_path=judgments(tmp_path))
    assert try_approve(story) == []
