"""Upgrade adoption and derived block status (T007; FR-047, D-42, determinism 32 and 33)."""

from __future__ import annotations

import io
from pathlib import Path

from eil import blockstatus, cli
from eil.blocks import Doc
from eil.package import STAGES, Package

from tests.helpers.package import (
    Story,
    block_entry,
    plan_doc,
    provenance_region,
    tasks_doc,
    with_ai_spec,
    with_approved_chain,
    with_record_sections,
)


def snapshot(root: Path) -> dict[str, bytes]:
    return {str(p.relative_to(root)): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


def run(argv: list[str], story: Story) -> tuple[int, str]:
    out = io.StringIO()
    code = cli.main([*argv, "--json", "--feature-dir", str(story.root)], cwd=story.root, env={}, stdout=out, stderr=io.StringIO())
    return code, out.getvalue()


def stage_states(story: Story) -> dict[str, tuple[str, str]]:
    package = Package(story.root)
    return {s: (package.state(s).state, package.state(s).reason) for s in STAGES}


def statuses(story: Story, stage: str) -> dict[str, str]:
    return {k: i.status for k, i in blockstatus.block_statuses(Package(story.root))[stage].items()}


def adopt_all(story: Story) -> None:
    cli._persist_adoption(Package(story.root))


# ---- approved and unchanged


def test_approved_and_unchanged_adopts_every_block_with_an_approval_basis(story_dir: Story) -> None:
    with_approved_chain(story_dir)
    record = blockstatus.adopt(Package(story_dir.root), "requirements")
    assert record is not None and record["currency"] == "known"
    assert record["blocks"]
    for entry in record["blocks"].values():
        assert entry["class"] == "adopted"
        assert entry["basis"] == "approval Ada Dev 2026-09-25T00:00:00Z"


def test_adoption_changes_neither_state_nor_fingerprint_nor_block_status(story_dir: Story) -> None:
    with_approved_chain(story_dir)
    package = Package(story_dir.root)
    states = stage_states(story_dir)
    prints = {s: package.fingerprint(s) for s in package.existing_stages()}
    before = {s: statuses(story_dir, s) for s in package.existing_stages()}
    adopt_all(story_dir)
    after_package = Package(story_dir.root)
    assert stage_states(story_dir) == states
    assert {s: after_package.fingerprint(s) for s in after_package.existing_stages()} == prints
    assert {s: statuses(story_dir, s) for s in after_package.existing_stages()} == before
    assert all(v == "settled" for v in before["requirements"].values())
    assert "provenance" in after_package.doc("requirements").regions


def test_adoption_writes_once_and_only_when_the_region_is_absent(story_dir: Story) -> None:
    with_approved_chain(story_dir)
    adopt_all(story_dir)
    once = snapshot(story_dir.root)
    adopt_all(story_dir)
    assert snapshot(story_dir.root) == once
    assert blockstatus.adopt(Package(story_dir.root), "requirements") is None


# ---- approved and changed


def test_approved_and_changed_adopts_only_covered_blocks(story_dir: Story) -> None:
    with_approved_chain(story_dir)
    text = story_dir.read("requirements")
    first = next(line for line in text.splitlines() if line.startswith("**REQ-001**"))
    story_dir.write("requirements", text.replace(first, first + " Also on export."))
    record = blockstatus.adopt(Package(story_dir.root), "requirements")
    assert record is not None
    assert "REQ-001" not in record["blocks"]
    assert any(k.startswith("REQ-") or k.startswith("UC-") for k in record["blocks"]) or record["blocks"] == {}
    assert statuses_from(story_dir, "requirements")["REQ-001"] == "needs-review"


def statuses_from(story: Story, stage: str) -> dict[str, str]:
    return statuses(story, stage)


# ---- never approved


def test_never_approved_untagged_is_adopted_and_tagged_is_inferred(story_dir: Story) -> None:
    with_approved_chain(story_dir)
    story_dir.write("plan", plan_doc({"Technical Context (traces: DEC-001)": "Python 3.11. [ai-draft]"}))
    record = blockstatus.adopt(Package(story_dir.root), "plan")
    assert record is not None
    classes = {e["class"] for e in record["blocks"].values()}
    assert classes == {"adopted", "inferred"}
    tagged = [k for k, e in record["blocks"].items() if e["class"] == "inferred"]
    assert len(tagged) == 1
    assert record["blocks"][tagged[0]].get("reviewed") is None
    assert statuses(story_dir, "plan")[tagged[0]] == "needs-review"
    assert {e.get("basis") for e in record["blocks"].values() if e["class"] == "adopted"} == {
        "untagged before upgrade"
    }


def test_derived_documents_have_unknown_currency(story_dir: Story) -> None:
    with_ai_spec(story_dir)
    story_dir.write("plan", plan_doc())
    story_dir.write("tasks", tasks_doc())
    for stage in ("ai-spec", "plan", "tasks"):
        record = blockstatus.adopt(Package(story_dir.root), stage)
        assert record is not None and record["currency"] == "unknown"
    traced = {k: s for k, s in statuses(story_dir, "tasks").items() if k.startswith("T")}
    assert traced and set(traced.values()) == {"unknown-currency"}


# ---- malformed


def test_a_malformed_region_is_never_auto_adopted(story_dir: Story) -> None:
    with_approved_chain(story_dir)
    bad = with_record_sections(story_dir.read("requirements"), {"version": 1, "bogus": 1})
    story_dir.write("requirements", bad)
    assert blockstatus.adopt(Package(story_dir.root), "requirements") is None
    adopt_all(story_dir)
    assert story_dir.read("requirements") == bad
    assert set(statuses(story_dir, "requirements").values()) == {"needs-review"}


# ---- derived status from a recorded region


def test_recorded_states_follow_the_data_model(story_dir: Story) -> None:
    with_approved_chain(story_dir)
    text = story_dir.read("requirements")
    package = Package(story_dir.root)
    hashes = package.current_item_hashes()
    stale = "sha256:" + "0" * 64
    second = "OQ-001"
    obj = {
        "version": 1,
        "blocks": {
            "REQ-001": block_entry(hashes["REQ-001"], "decided"),
            second: block_entry(hashes[second], "inferred"),
            "UC-001": block_entry(
                hashes["UC-001"], "inferred", reviewed={"by": "Ada", "at": "t", "list": "RVW-001", "reply": "ok"}
            ),
            "ART-001": block_entry(
                hashes["ART-001"], "inferred",
                reviewed={"by": "Ada", "at": "t", "list": "RVW-001", "reply": "ok"},
                sources={"REQ-001": stale},
            ),
        },
    }  # fmt: skip
    story_dir.write("requirements", with_record_sections(text, obj))
    got = statuses(story_dir, "requirements")
    assert got["REQ-001"] == "settled"
    assert got[second] == "needs-review"
    assert got["UC-001"] == "settled"
    assert got["ART-001"] == "source-changed"
    counts = blockstatus.counts(Package(story_dir.root), "requirements")
    assert counts["stale"] >= 1 and counts["settled"] >= 2


def test_a_restated_block_is_source_changed_when_a_cited_hash_moves(story_dir: Story) -> None:
    with_approved_chain(story_dir)
    hashes = Package(story_dir.root).current_item_hashes()
    text = story_dir.read("functional")
    fr = next(k for k in hashes if k.startswith("FR-"))
    obj = {
        "version": 1,
        "blocks": {fr: block_entry(hashes[fr], "restated", cites={"REQ-001": hashes["REQ-001"]})},
    }
    story_dir.write("functional", with_record_sections(text, obj))
    assert statuses(story_dir, "functional")[fr] == "settled"
    obj["blocks"][fr]["cites"]["REQ-001"] = "sha256:" + "1" * 64
    story_dir.write("functional", with_record_sections(text, obj))
    assert statuses(story_dir, "functional")[fr] == "source-changed"


# ---- read-only commands (determinism 32, 33)


def test_status_and_check_leave_the_regions_byte_identical(story_dir: Story) -> None:
    with_approved_chain(story_dir)

    def regions() -> dict[str, tuple[str, str]]:
        found = {}
        for stage in Package(story_dir.root).existing_stages():
            doc = Doc(story_dir.read(stage))
            found[stage] = tuple(
                "\n".join(x.raw for x in doc.lines[doc.regions[n].begin_no - 1 : doc.regions[n].end_no])
                if n in doc.regions
                else ""
                for n in ("provenance", "changelog")
            )
        return found

    before = regions()
    assert all(pair == ("", "") for pair in before.values())
    for argv in (["status"], ["check", "--stage", "requirements"], ["check", "--chain"]):
        run(argv, story_dir)
    assert regions() == before


def test_status_before_sync_equals_status_after(story_dir: Story) -> None:
    with_approved_chain(story_dir)
    code, before = run(["status"], story_dir)
    adopt_all(story_dir)
    code_after, after = run(["status"], story_dir)
    assert code == code_after
    assert before == after


def test_an_existing_record_is_left_alone(story_dir: Story) -> None:
    with_approved_chain(story_dir)
    text = with_record_sections(story_dir.read("requirements"), {"version": 1, "blocks": {}})
    story_dir.write("requirements", text)
    adopt_all(story_dir)
    assert story_dir.read("requirements") == text
    assert Doc(text).read_provenance().obj == {"version": 1, "blocks": {}}
    assert provenance_region({"version": 1, "blocks": {}}).strip() in text
