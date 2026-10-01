"""Approvers for the derived stages (T009; research D-36)."""

from __future__ import annotations

from pathlib import Path

import pytest
from eil.identity import ConfigError, load_config, resolve_approvers

DERIVED = ("ai-spec", "plan", "tasks", "verification")


def _write(root: Path, body: str) -> None:
    folder = root / ".specify" / "extensions" / "eil"
    folder.mkdir(parents=True)
    (folder / "eil-config.yml").write_text(body, encoding="utf-8")


@pytest.mark.parametrize("stage", DERIVED)
def test_derived_stage_defaults_to_the_developer(stage: str, tmp_path: Path) -> None:
    config = load_config(tmp_path)
    assert resolve_approvers(config, stage, ["Ada Dev"]) == ["Ada Dev"]


@pytest.mark.parametrize("stage", DERIVED)
def test_derived_stage_defaults_to_the_technical_list(stage: str, tmp_path: Path) -> None:
    _write(tmp_path, "approvers:\n  technical: [Grace Lead]\n")
    config = load_config(tmp_path)
    assert resolve_approvers(config, stage, ["Ada Dev"]) == ["Grace Lead"]


@pytest.mark.parametrize("stage", DERIVED)
def test_an_explicit_list_wins_over_the_technical_list(stage: str, tmp_path: Path) -> None:
    _write(tmp_path, f"approvers:\n  technical: [Grace Lead]\n  {stage}: [Sam Reviewer]\n")
    config = load_config(tmp_path)
    assert resolve_approvers(config, stage, ["Ada Dev"]) == ["Sam Reviewer"]


def test_an_empty_derived_list_falls_back_like_an_absent_one(tmp_path: Path) -> None:
    _write(tmp_path, "approvers:\n  technical: [Grace Lead]\n  plan: []\n")
    config = load_config(tmp_path)
    assert resolve_approvers(config, "plan", ["Ada Dev"]) == ["Grace Lead"]


def test_an_unknown_stage_is_still_rejected(tmp_path: Path) -> None:
    _write(tmp_path, "approvers:\n  overview: [Grace Lead]\n")
    with pytest.raises(ConfigError):
        load_config(tmp_path)


def test_the_template_lists_the_derived_stages() -> None:
    template = Path(__file__).resolve().parents[2] / "extensions" / "eil" / "config-template.yml"
    text = template.read_text(encoding="utf-8")
    for stage in DERIVED:
        assert f"{stage}:" in text
