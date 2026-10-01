"""Helpers for the derived layers (s04 to s07) of the reference story: edit a source, settle the
derived documents so source versions are recorded, and answer review lists as a named confirmer."""

from __future__ import annotations

import re
from typing import Any

from eil import cli, reviews
from eil.identity import Config
from eil.package import Package

from tests.helpers.package import Story, approve_stages

CONFIG = Config(
    default_developer="Ada Dev",
    approvers={
        "requirements": ["Ada Dev"],
        "functional": ["Ada Dev"],
        "technical": ["Ada Dev"],
        "completion": ["Ada Dev"],
    },
)
DERIVED = ("ai-spec", "plan", "tasks", "verification")


def package_of(story: Story) -> Package:
    return Package(story.root)


def edit(story: Story, stage: str, old: str, new: str) -> None:
    text = story.read(stage)
    assert old in text, f"{old!r} not in {stage}"
    story.write(stage, text.replace(old, new, 1))


def change_dec3(story: Story) -> None:
    edit(story, "technical", "Reason for decision 3.", "A changed reason for decision 3.")


def revert_dec3(story: Story) -> None:
    edit(story, "technical", "A changed reason for decision 3.", "Reason for decision 3.")


def wire_tasks_to_dec3(story: Story) -> None:
    """T004 to T006 (ticked) and T009 trace AIS-014, which traces DEC-003."""
    text = story.read("tasks")
    for number in (4, 5, 6, 9):
        text = re.sub(rf"(T{number:03d} .*?\(traces: )AIS-\d{{3}}\)", r"\1AIS-014)", text)
    story.write("tasks", text)


def settle_derived(story: Story, stages: tuple[str, ...] = DERIVED) -> None:
    """Record the source versions of every derived block by answering the ``unknown-currency`` lists."""
    cli._persist_adoption(package_of(story))
    for stage in stages:
        for kind in ("inferred", "unknown-currency"):
            listed = reviews.build_list(package_of(story), stage, kind)
            if listed.entries:
                reviews.answer(
                    package_of(story), CONFIG, stage, kind,
                    digest=listed.digest, by="Ada Dev", reply="ok", all_=True,
                )  # fmt: skip


def reapprove_technical(story: Story) -> None:
    approve_stages(story, "technical")


def clear_approval(story: Story, stage: str) -> None:
    """Return ``stage`` to never approved."""
    text = story.read(stage)
    start = text.index("<!-- eil:begin approval -->")
    end = text.index("<!-- eil:end approval -->")
    story.write(stage, text[:start] + "<!-- eil:begin approval -->\n```json\n{}\n```\n" + text[end:])


def answer_all(story: Story, stage: str, kind: str, reply: str = "ok", **kwargs: Any) -> dict[str, Any]:
    listed = reviews.build_list(package_of(story), stage, kind)
    return reviews.answer(
        package_of(story), CONFIG, stage, kind, digest=kwargs.pop("digest", listed.digest),
        by="Ada Dev", reply=reply, all_=kwargs.pop("all_", True), **kwargs,
    )  # fmt: skip
