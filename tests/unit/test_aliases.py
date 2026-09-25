"""Compatibility aliases (task T083; FR-049 to FR-053, research D-06 and D-07, determinism 6 and 7).

The three names Spec Kit expects (``spec.md``, ``plan.md``, ``tasks.md``) resolve to the one real
document. Every fault is reported before it is repaired, and the real document is never touched.
"""

from __future__ import annotations

import os
import stat

import pytest
from eil.aliases import AliasState, alias_mode, classify, refresh
from eil.package import ALIASES, Package

from tests.helpers.package import Story

TARGETS = {"spec.md": "s04-ai-spec.md", "plan.md": "s05-plan.md", "tasks.md": "s06-tasks.md"}
STAGE_OF = {"spec.md": "ai-spec", "plan.md": "plan", "tasks.md": "tasks"}
TEXT = "# Document\n\nSome content.\n"


def pkg(story: Story) -> Package:
    return Package(story.root)


def by_name(states: list[AliasState]) -> dict[str, AliasState]:
    return {s.name: s for s in states}


def ready(story: Story, *stages: str) -> None:
    for stage in stages:
        story.write(stage, f"{TEXT}{stage}\n")


# ---- the table and when an alias may exist (FR-049, FR-050, determinism 7)


def test_there_are_exactly_three_aliases_each_for_its_own_document() -> None:
    assert ALIASES == TARGETS


def test_no_alias_is_created_before_its_target_exists(story_dir: Story) -> None:
    ready(story_dir, "ai-spec")
    before, after = refresh(pkg(story_dir))
    assert before == [AliasState("spec.md", "s04-ai-spec.md", None, "missing")]
    assert [a.name for a in after] == ["spec.md"]
    assert not (story_dir.root / "plan.md").exists() and not (story_dir.root / "tasks.md").exists()


def test_no_target_means_no_alias_and_no_fault(story_dir: Story) -> None:
    before, after = refresh(pkg(story_dir))
    assert before == [] and after == []
    assert sorted(p.name for p in story_dir.root.iterdir()) == ["s00-README.md"]


def test_nothing_but_the_three_aliases_is_ever_created(story_dir: Story) -> None:
    ready(story_dir, "requirements", "functional", "technical", "ai-spec", "plan", "tasks")
    refresh(pkg(story_dir))
    names = {p.name for p in story_dir.root.iterdir()}
    assert names - {p.name for p in story_dir.root.glob("s0*")} == {"spec.md", "plan.md", "tasks.md"}


# ---- creating an alias (D-07)


def test_a_new_alias_is_a_relative_symlink_where_symlinks_work(story_dir: Story) -> None:
    ready(story_dir, "ai-spec")
    _, after = refresh(pkg(story_dir))
    alias = story_dir.root / "spec.md"
    assert alias.is_symlink() and os.readlink(alias) == "s04-ai-spec.md"
    assert after == [AliasState("spec.md", "s04-ai-spec.md", "symlink", None)]
    assert alias.read_text() == story_dir.read("ai-spec")


def test_mirror_mode_makes_a_read_only_copy_with_identical_bytes(story_dir: Story) -> None:
    ready(story_dir, "ai-spec")
    _, after = refresh(pkg(story_dir), mode="mirror")
    alias = story_dir.root / "spec.md"
    assert not alias.is_symlink() and alias.read_bytes() == story_dir.path("ai-spec").read_bytes()
    assert not alias.stat().st_mode & (stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH)
    assert after[0].form == "mirror" and after[0].fault is None


def test_a_platform_that_refuses_symlinks_falls_back_to_a_mirror(
    story_dir: Story, monkeypatch: pytest.MonkeyPatch
) -> None:
    def refused(*_args: object, **_kwargs: object) -> None:
        raise OSError("symlinks are not permitted")

    monkeypatch.setattr(os, "symlink", refused)
    ready(story_dir, "ai-spec")
    _, after = refresh(pkg(story_dir))
    assert after[0].form == "mirror" and not (story_dir.root / "spec.md").is_symlink()


def test_the_test_switch_reads_the_environment() -> None:
    assert alias_mode({"EIL_ALIAS_MODE": "mirror"}) == "mirror"
    assert alias_mode({"EIL_ALIAS_MODE": "MIRROR "}) == "mirror"
    assert alias_mode({}) == "symlink"
    assert alias_mode({"EIL_ALIAS_MODE": "anything else"}) == "symlink"


# ---- every fault class is reported before it is repaired (FR-051, FR-053, determinism 6)


def test_a_missing_alias_is_reported_then_created(story_dir: Story) -> None:
    ready(story_dir, "plan")
    assert by_name(classify(pkg(story_dir)))["plan.md"].fault == "missing"
    before, after = refresh(pkg(story_dir))
    assert by_name(before)["plan.md"].fault == "missing"
    assert by_name(after)["plan.md"].fault is None and (story_dir.root / "plan.md").exists()


def test_a_symlink_to_the_wrong_document_is_reported_then_repointed(story_dir: Story) -> None:
    ready(story_dir, "plan", "tasks")
    (story_dir.root / "plan.md").symlink_to("s06-tasks.md")
    before, after = refresh(pkg(story_dir))
    assert by_name(before)["plan.md"].fault == "wrong-target"
    assert os.readlink(story_dir.root / "plan.md") == "s05-plan.md"
    assert by_name(after)["plan.md"].fault is None
    assert story_dir.read("tasks") == f"{TEXT}tasks\n"


def test_a_dangling_symlink_is_a_wrong_target(story_dir: Story) -> None:
    ready(story_dir, "plan")
    (story_dir.root / "plan.md").symlink_to("nowhere.md")
    assert by_name(classify(pkg(story_dir)))["plan.md"].fault == "wrong-target"


def test_a_real_file_that_replaced_the_alias_is_diverged_and_the_target_prevails(story_dir: Story) -> None:
    ready(story_dir, "ai-spec")
    (story_dir.root / "spec.md").write_text("someone wrote a separate spec here\n")
    before, after = refresh(pkg(story_dir))
    assert by_name(before)["spec.md"].fault == "diverged"
    assert by_name(after)["spec.md"].fault is None
    assert (story_dir.root / "spec.md").read_bytes() == story_dir.path("ai-spec").read_bytes()
    assert story_dir.read("ai-spec") == f"{TEXT}ai-spec\n"


def test_a_mirror_that_differs_from_its_target_is_reported_then_refreshed(story_dir: Story) -> None:
    ready(story_dir, "ai-spec")
    refresh(pkg(story_dir), mode="mirror")
    story_dir.write("ai-spec", "# Changed\n")
    states = classify(pkg(story_dir))
    assert states[0].fault == "mirror-differs" and states[0].form == "mirror"
    before, after = refresh(pkg(story_dir), mode="mirror")
    assert before[0].fault == "mirror-differs" and after[0].fault is None
    assert (story_dir.root / "spec.md").read_text() == "# Changed\n"


def test_an_edited_mirror_is_reported_and_the_targets_content_prevails(story_dir: Story) -> None:
    ready(story_dir, "ai-spec")
    refresh(pkg(story_dir), mode="mirror")
    alias = story_dir.root / "spec.md"
    alias.chmod(0o644)
    alias.write_text("edited by hand\n")
    before, _ = refresh(pkg(story_dir), mode="mirror")
    assert before[0].fault == "diverged"
    assert alias.read_bytes() == story_dir.path("ai-spec").read_bytes()
    assert story_dir.read("ai-spec") == f"{TEXT}ai-spec\n"


def test_an_alias_whose_target_is_gone_is_reported_and_left_alone(story_dir: Story) -> None:
    ready(story_dir, "plan")
    refresh(pkg(story_dir))
    story_dir.path("plan").unlink()
    before, after = refresh(pkg(story_dir))
    assert before[0].fault == "target-missing" and after[0].fault == "target-missing"
    assert (story_dir.root / "plan.md").is_symlink()


def test_a_symlink_git_checked_out_as_a_text_file_is_a_fault_and_is_replaced(story_dir: Story) -> None:
    ready(story_dir, "tasks")
    (story_dir.root / "tasks.md").write_text("s06-tasks.md")
    before, after = refresh(pkg(story_dir))
    assert before[0].fault == "diverged" and after[0].fault is None
    assert (story_dir.root / "tasks.md").read_text() == f"{TEXT}tasks\n"


def test_a_valid_alias_is_left_exactly_as_it_is(story_dir: Story) -> None:
    ready(story_dir, "ai-spec")
    refresh(pkg(story_dir))
    before, after = refresh(pkg(story_dir))
    assert before[0].fault is None and after == before
    refresh(pkg(story_dir), mode="mirror")
    again = classify(pkg(story_dir))
    assert again[0].fault is None


def test_a_valid_mirror_is_kept_even_where_symlinks_would_work(story_dir: Story) -> None:
    ready(story_dir, "ai-spec")
    refresh(pkg(story_dir), mode="mirror")
    _, after = refresh(pkg(story_dir))
    assert after[0].form == "mirror" and not (story_dir.root / "spec.md").is_symlink()


def test_mirror_mode_replaces_a_valid_symlink_without_calling_it_a_fault(story_dir: Story) -> None:
    ready(story_dir, "ai-spec")
    refresh(pkg(story_dir))
    before, after = refresh(pkg(story_dir), mode="mirror")
    assert before[0].fault is None and after[0].form == "mirror"


def test_check_only_reports_and_changes_nothing(story_dir: Story) -> None:
    ready(story_dir, "ai-spec")
    before, after = refresh(pkg(story_dir), check_only=True)
    assert before[0].fault == "missing" and after == before
    assert not (story_dir.root / "spec.md").exists()


# ---- the target is never modified (FR-052)


@pytest.mark.parametrize("mode", ["symlink", "mirror"])
@pytest.mark.parametrize("setup", ["missing", "wrong", "diverged", "stale"])
def test_repairing_an_alias_never_changes_the_real_document(story_dir: Story, mode: str, setup: str) -> None:
    ready(story_dir, "ai-spec", "plan")
    original = story_dir.path("ai-spec").read_bytes()
    alias = story_dir.root / "spec.md"
    if setup == "wrong":
        alias.symlink_to("s05-plan.md")
    elif setup == "diverged":
        alias.write_text("something else")
    elif setup == "stale":
        refresh(pkg(story_dir), mode="mirror")
        story_dir.write("ai-spec", TEXT + "changed\n")
        original = story_dir.path("ai-spec").read_bytes()
    refresh(pkg(story_dir), mode=mode)
    assert story_dir.path("ai-spec").read_bytes() == original
    assert story_dir.read("plan") == f"{TEXT}plan\n"


def test_a_symlink_repaired_in_place_never_writes_through_to_the_target(story_dir: Story) -> None:
    ready(story_dir, "ai-spec")
    refresh(pkg(story_dir))  # a valid symlink
    story_dir.path("ai-spec").chmod(0o444)
    before = story_dir.path("ai-spec").read_bytes()
    refresh(pkg(story_dir), mode="mirror")  # replaces the symlink with a copy
    assert story_dir.path("ai-spec").read_bytes() == before
    assert story_dir.path("ai-spec").stat().st_mode & 0o777 == 0o444


def test_the_result_is_stable_when_run_twice(story_dir: Story) -> None:
    ready(story_dir, "ai-spec", "plan", "tasks")
    refresh(pkg(story_dir), mode="mirror")
    snapshot = {p.name: p.read_bytes() for p in story_dir.root.iterdir() if p.is_file()}
    refresh(pkg(story_dir), mode="mirror")
    assert {p.name: p.read_bytes() for p in story_dir.root.iterdir() if p.is_file()} == snapshot


def test_states_serialise_for_the_status_report() -> None:
    assert AliasState("spec.md", "s04-ai-spec.md", "mirror", None).to_json() == {
        "name": "spec.md",
        "target": "s04-ai-spec.md",
        "form": "mirror",
        "fault": None,
    }


def test_a_directory_in_the_place_of_an_alias_is_reported_and_not_removed(story_dir: Story) -> None:
    ready(story_dir, "ai-spec")
    (story_dir.root / "spec.md").mkdir()
    (story_dir.root / "spec.md" / "keep.txt").write_text("x")
    before, after = refresh(pkg(story_dir))
    assert before[0].fault == "diverged" and after[0].fault == "diverged"
    assert (story_dir.root / "spec.md" / "keep.txt").exists()
