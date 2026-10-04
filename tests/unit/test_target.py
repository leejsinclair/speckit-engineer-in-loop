"""T008: the target story of every call (determinism 38 and 40; research D-46).

Resolution names the directory together with where it came from. A call that writes is refused
``ambiguous-story`` before anything is touched when its target came from the pointer (or from
nothing) and cannot be told for certain; a read-only call is never refused for that and names the
story it read. Every result carries ``story``.
"""

from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any

import pytest
from eil import cli, target

from tests.conftest import files_snapshot
from tests.fixtures.two_stories import TwoStories
from tests.helpers.package import Story, install_templates, with_functional


def run(project: Path, *argv: str, env: dict[str, str] | None = None) -> tuple[int, Any, str]:
    out, err = io.StringIO(), io.StringIO()
    code = cli.main([*argv, "--json"], cwd=project, env=env or {}, stdout=out, stderr=err)
    return code, (json.loads(out.getvalue()) if out.getvalue().strip() else None), err.getvalue()


def codes(payload: Any) -> list[str]:
    return [r["code"] for r in (payload or {}).get("refusals", [])]


# ---- resolution


def test_an_argument_wins_and_is_never_ambiguous(two_stories: TwoStories) -> None:
    found = target.resolve_target(two_stories.project, "specs/002-b", {})
    assert (found.directory, found.source) == (two_stories.b.root, "argument")
    assert target.ambiguity(found, two_stories.project) is None


def test_the_environment_comes_next(two_stories: TwoStories) -> None:
    found = target.resolve_target(two_stories.project, None, {"SPECIFY_FEATURE_DIRECTORY": "specs/002-b"})
    assert (found.directory, found.source) == (two_stories.b.root, "environment")
    assert target.ambiguity(found, two_stories.project) is None


def test_the_pointer_then_names_a_story(two_stories: TwoStories) -> None:
    found = target.resolve_target(two_stories.project, None, {})
    assert (found.directory, found.source) == (two_stories.a.root, "pointer")


def test_no_pointer_and_one_story_is_that_story(tmp_path: Path) -> None:
    (tmp_path / ".specify").mkdir()
    only = Story(tmp_path / "specs" / "001-only")
    found = target.resolve_target(tmp_path, None, {})
    assert (found.directory, found.source) == (only.root, "none")
    assert target.ambiguity(found, tmp_path) is None


def test_no_pointer_and_two_stories_is_ambiguous(two_stories: TwoStories) -> None:
    two_stories.point_at(None)
    found = target.resolve_target(two_stories.project, None, {})
    assert found.source == "none" and found.directory is None
    assert sorted(p.name for p in found.candidates) == ["001-a", "002-b"]
    assert "more than one story" in (target.ambiguity(found, two_stories.project) or "")


def test_a_pointer_to_a_missing_directory_is_ambiguous(two_stories: TwoStories) -> None:
    (two_stories.project / ".specify" / "feature.json").write_text('{"feature_directory": "specs/009-gone"}')
    found = target.resolve_target(two_stories.project, None, {})
    assert found.source == "pointer"
    assert "does not exist" in (target.ambiguity(found, two_stories.project) or "")


def test_a_pointer_to_a_complete_story_with_another_in_progress_is_ambiguous(two_stories: TwoStories) -> None:
    found = target.resolve_target(two_stories.project, None, {})
    reason = target.ambiguity(found, two_stories.project) or ""
    assert "completion is approved" in reason and "002-b" in reason


def test_a_pointer_to_a_complete_story_alone_is_not_ambiguous(two_stories: TwoStories) -> None:
    import shutil

    shutil.rmtree(two_stories.b.root)
    found = target.resolve_target(two_stories.project, None, {})
    assert target.ambiguity(found, two_stories.project) is None


def test_a_pointer_to_an_in_progress_story_is_not_ambiguous(two_stories: TwoStories) -> None:
    two_stories.point_at(two_stories.b)
    assert target.ambiguity(target.resolve_target(two_stories.project, None, {}), two_stories.project) is None


# ---- the writes / read-only table, walked (determinism 38 and 40)

# One concrete call per entry of ``cli.COMMAND_KINDS``. A read-only call may still refuse for its own
# reasons (``None``), but never ``ambiguous-story``.
EXAMPLES: dict[str, tuple[list[str], int | None]] = {
    "status": (["status"], 0),
    "show": (["show", "functional"], 0),
    "trace": (["trace"], 0),
    "fingerprint": (["fingerprint", "specs/001-a/s01-requirements.md"], 0),
    "blocks list": (["blocks", "list", "--stage", "functional"], 0),
    "review list": (["review", "list", "--stage", "functional", "--kind", "inferred"], 0),
    "review start": (["review", "start", "--stage", "functional"], None),
    "review show": (["review", "show", "--stage", "functional", "--kind", "inferred", "--all"], 0),
    "comprehension plan": (["comprehension", "plan", "--stage", "functional"], None),
    "check": (["check", "--stage", "requirements"], 0),
    "enter": (["enter", "analyze"], 0),
    "artifact list": (["artifact", "list"], 0),
    "correct propose": (
        ["correct", "propose", "--item", "FR-001", "--found-in", "technical", "--problem", "x"],
        None,
    ),
    "start": (["start", "--title", "New"], 1),
    "sync": (["sync"], 1),
    "check --judgments": (["check", "--stage", "functional", "--judgments", "judgments.json"], 1),
    "stage-init": (["stage-init", "completion"], 1),
    "challenge add": (
        ["challenge", "add", "functional", "--target", "FR-001", "--text", "x", "--severity", "low"],
        1,
    ),
    "challenge severity": (["challenge", "severity", "CH-001", "--to", "low", "--by", "Ada Dev"], 1),
    "challenge answer": (["challenge", "answer", "CH-001", "--response", "accepted", "--by", "Ada Dev"], 1),
    "approve": (["approve", "functional", "--by", "Ada Dev", "--attestation", "ok"], 1),
    "override": (["override", "functional", "--criterion", "FUN-G10", "--by", "Ada Dev", "--reason", "x"], 1),
    "amend": (["amend", "functional", "--from", "CH-001", "--by", "Ada Dev", "--attestation", "ok"], 1),
    "review accept": (
        ["review", "accept", "--stage", "functional", "--items", "FR-001", "--by", "Ada Dev"],
        1,
    ),
    "review finish": (
        ["review", "finish", "--stage", "functional", "--by", "Ada Dev", "--attestation", "ok"],
        1,
    ),
    "review confirm": (
        ["review", "confirm", "--stage", "functional", "--by", "Ada Dev", "--confirmation", "ok"],
        1,
    ),
    "review answer": (
        [
            "review",
            "answer",
            "--stage",
            "functional",
            "--kind",
            "inferred",
            "--by",
            "Ada Dev",
            "--reply",
            "ok",
            "--all",
        ],
        1,
    ),
    "correct open": (
        [
            "correct",
            "open",
            "--item",
            "FR-001",
            "--found-in",
            "technical",
            "--problem",
            "x",
            "--by",
            "Ada Dev",
        ],
        1,
    ),
    "blocks classify": (["blocks", "classify", "--stage", "functional", "--file", "c.json"], 1),
    "blocks reclassify": (
        [
            "blocks",
            "reclassify",
            "--stage",
            "functional",
            "--block",
            "FR-001",
            "--to",
            "inferred",
            "--by",
            "Ada Dev",
        ],
        1,
    ),
    "abbreviate": (["abbreviate", "functional", "--by", "Ada Dev", "--reason", "x"], 1),
    "resolve": (["resolve", "--id", "AIS-001", "--stage", "functional"], 1),
    "artifact register": (
        [
            "artifact",
            "register",
            "--id",
            "ART-009",
            "--file",
            "x.png",
            "--kind",
            "image",
            "--source-tool",
            "figma",
            "--source-url",
            "https://x",
        ],
        1,
    ),
    "comprehension record": (
        [
            "comprehension",
            "record",
            "--stage",
            "functional",
            "--level",
            "recognise",
            "--outcome",
            "understood",
            "--by",
            "Ada Dev",
        ],
        1,
    ),
    "comprehension waive": (
        ["comprehension", "waive", "--stage", "functional", "--by", "Ada Dev", "--reason", "x"],
        1,
    ),
    "profile set": (["profile", "set", "small", "--by", "Ada Dev", "--reason", "x"], 1),
    "profile withdraw": (["profile", "withdraw", "--by", "Ada Dev", "--reason", "x"], 1),
    "overview": (["overview"], 1),
    "review serve": (["review", "serve", "--by", "Ada Dev"], 1),
    "review serve --status": (["review", "serve", "--status"], 0),
    "review serve --stop": (["review", "serve", "--stop"], 0),
}


def test_the_examples_cover_the_table() -> None:
    assert set(EXAMPLES) == set(cli.COMMAND_KINDS)
    for key, (_, expected) in EXAMPLES.items():
        kind = cli.COMMAND_KINDS[key]
        assert kind in ("writes", "read-only")
        assert (expected == 1) == (kind == "writes"), key


@pytest.mark.parametrize("key", [k for k, v in cli.COMMAND_KINDS.items() if v == "writes"])
def test_every_write_is_refused_when_ambiguous_and_touches_nothing(two_stories: TwoStories, key: str) -> None:
    before = files_snapshot(two_stories.project)
    code, payload, _ = run(two_stories.project, *EXAMPLES[key][0])
    assert code == 1, payload
    assert codes(payload) == ["ambiguous-story"]
    refusal = payload["refusals"][0]
    assert "001-a" in refusal["message"] and "002-b" in refusal["message"]
    assert "--feature-dir" in refusal["fix"]
    assert payload["story"] == "001-a"
    assert files_snapshot(two_stories.project) == before


@pytest.mark.parametrize("key", [k for k, v in cli.COMMAND_KINDS.items() if v == "read-only"])
def test_every_read_only_call_proceeds_and_names_the_story(two_stories: TwoStories, key: str) -> None:
    argv, expected = EXAMPLES[key]
    code, payload, _ = run(two_stories.project, *argv)
    assert "ambiguous-story" not in codes(payload)
    if expected is not None:
        assert code == expected, payload
    assert payload["story"] == "001-a"


def test_a_write_with_an_explicit_story_proceeds_and_names_it(two_stories: TwoStories) -> None:
    code, payload, _ = run(two_stories.project, "overview", "--feature-dir", "specs/002-b")
    assert code == 0 and payload["story"] == "002-b"


def test_the_text_form_names_the_story(two_stories: TwoStories) -> None:
    out = io.StringIO()
    code = cli.main(
        ["overview", "--feature-dir", "specs/002-b"],
        cwd=two_stories.project,
        env={},
        stdout=out,
        stderr=io.StringIO(),
    )
    assert code == 0 and out.getvalue().startswith("Story 002-b: ")


def test_a_pointer_to_an_in_progress_story_lets_writes_through(two_stories: TwoStories) -> None:
    two_stories.point_at(two_stories.b)
    code, payload, _ = run(two_stories.project, "overview")
    assert code == 0 and payload["story"] == "002-b"


def test_one_story_and_no_pointer_needs_no_flag(tmp_path: Path) -> None:
    install_templates(tmp_path)
    story = Story(tmp_path / "specs" / "001-only")
    with_functional(story)
    code, payload, _ = run(tmp_path, "overview")
    assert code == 0 and payload["story"] == "001-only"
