"""Approver identity and configuration (task T032; FR-013, FR-045, FR-066, research D-11)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from eil import identity
from eil.identity import (
    Config,
    ConfigError,
    confirmer_refusal,
    is_ai_actor,
    load_config,
    parse_simple_yaml,
    resolve_approvers,
    same_person,
    story_identities,
)


def write_config(project: Path, name: str, text: str) -> None:
    directory = project / ".specify" / "extensions" / "eil"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / name).write_text(text, encoding="utf-8")


# ---- the small YAML subset (the helper may use only the standard library)


def test_yaml_subset_scalars_lists_and_nesting() -> None:
    text = """
# a comment
default_developer: null
approvers:
  requirements: []
  functional: [Ada Dev, "Sam Lee"]
  technical:
    - Ada Dev   # trailing comment
    - 'Priya N'
  completion: ["Ada Dev"]
abbreviation_authorisers: [Lead]
flag: true
count: 3
"""
    assert parse_simple_yaml(text) == {
        "default_developer": None,
        "approvers": {
            "requirements": [],
            "functional": ["Ada Dev", "Sam Lee"],
            "technical": ["Ada Dev", "Priya N"],
            "completion": ["Ada Dev"],
        },
        "abbreviation_authorisers": ["Lead"],
        "flag": True,
        "count": 3,
    }


def test_yaml_subset_reads_the_shipped_template() -> None:
    template = Path(__file__).resolve().parents[2] / "extensions" / "eil" / "config-template.yml"
    data = parse_simple_yaml(template.read_text(encoding="utf-8"))
    assert data["default_developer"] is None
    assert data["approvers"] == {"requirements": [], "functional": [], "technical": [], "completion": []}
    assert data["abbreviation_authorisers"] == []


@pytest.mark.parametrize(
    "text", ["key value without colon\n", "a:\n\t- tabbed\n", "- orphan item\n", "a: [unclosed\n"]
)
def test_yaml_it_cannot_read_is_a_config_error_not_a_guess(text: str) -> None:
    with pytest.raises(ConfigError):
        parse_simple_yaml(text)


# ---- loading


def test_defaults_when_no_config_exists(tmp_path: Path) -> None:
    config = load_config(tmp_path)
    assert config == Config(
        default_developer=None,
        approvers={"requirements": [], "functional": [], "technical": [], "completion": []},
        abbreviation_authorisers=[],
    )


def test_reads_the_extension_config(tmp_path: Path) -> None:
    write_config(
        tmp_path,
        "eil-config.yml",
        "default_developer: Ada Dev\napprovers:\n  requirements: [Ada Dev]\n  technical: [Ada Dev, Sam Lee]\n"
        "abbreviation_authorisers: [Lead]\n",
    )
    config = load_config(tmp_path)
    assert config.default_developer == "Ada Dev"
    assert config.approvers["requirements"] == ["Ada Dev"]
    assert config.approvers["functional"] == []  # unlisted stages keep their default
    assert config.approvers["technical"] == ["Ada Dev", "Sam Lee"]
    assert config.abbreviation_authorisers == ["Lead"]


def test_the_local_config_overrides_per_key(tmp_path: Path) -> None:
    write_config(
        tmp_path, "eil-config.yml", "approvers:\n  requirements: [Ada Dev]\n  functional: [Ada Dev]\n"
    )
    write_config(
        tmp_path, "local-config.yml", "approvers:\n  functional: [Sam Lee]\ndefault_developer: Sam Lee\n"
    )
    config = load_config(tmp_path)
    assert config.approvers["requirements"] == ["Ada Dev"]
    assert config.approvers["functional"] == ["Sam Lee"]
    assert config.default_developer == "Sam Lee"


def test_a_broken_config_is_reported_with_its_file(tmp_path: Path) -> None:
    write_config(tmp_path, "eil-config.yml", "approvers: [unclosed\n")
    with pytest.raises(ConfigError, match="eil-config.yml"):
        load_config(tmp_path)


def test_unknown_stage_names_in_approvers_are_rejected(tmp_path: Path) -> None:
    write_config(tmp_path, "eil-config.yml", "approvers:\n  designing: [Ada]\n")
    with pytest.raises(ConfigError, match="designing"):
        load_config(tmp_path)


def test_approvers_must_be_lists_of_names(tmp_path: Path) -> None:
    write_config(tmp_path, "eil-config.yml", "approvers:\n  requirements: Ada Dev\n")
    with pytest.raises(ConfigError, match="requirements"):
        load_config(tmp_path)


# ---- who counts as the story's developer


def test_the_story_developer_is_every_known_identity_of_the_developer() -> None:
    config = Config(default_developer="Ada L", approvers={}, abbreviation_authorisers=[])
    found = story_identities(config, owner="Ada Dev", git_name="Ada Lovelace", git_email="ada@example.test")
    assert found == ["Ada Dev", "Ada L", "Ada Lovelace", "ada@example.test"]


def test_missing_identities_are_left_out() -> None:
    config = Config(default_developer=None, approvers={}, abbreviation_authorisers=[])
    assert story_identities(config, owner=None, git_name=None, git_email=None) == []


def test_an_empty_approver_list_means_the_story_developer() -> None:
    config = Config(default_developer=None, approvers={"requirements": []}, abbreviation_authorisers=[])
    assert resolve_approvers(config, "requirements", ["Ada Dev", "ada@example.test"]) == [
        "Ada Dev",
        "ada@example.test",
    ]


def test_a_configured_list_replaces_the_developer() -> None:
    config = Config(default_developer=None, approvers={"technical": ["Sam Lee"]}, abbreviation_authorisers=[])
    assert resolve_approvers(config, "technical", ["Ada Dev"]) == ["Sam Lee"]


@pytest.mark.parametrize(
    ("a", "b", "same"),
    [
        ("Ada Dev", "ada dev", True),
        ("  Ada   Dev ", "Ada Dev", True),
        ("Ada Dev", "Ada Devs", False),
        ("ADA@EXAMPLE.TEST", "ada@example.test", True),
        ("Ada Dev", "Mallory", False),
    ],
)
def test_names_are_compared_case_insensitively_with_whitespace_collapsed(a: str, b: str, same: bool) -> None:
    assert same_person(a, b) is same


# ---- the refusals (FR-013)


def test_a_listed_person_may_confirm() -> None:
    assert confirmer_refusal("ada dev", ["Ada Dev"], "requirements") is None


def test_anyone_else_is_refused_with_a_fix() -> None:
    refusal = confirmer_refusal("Mallory", ["Ada Dev"], "requirements")
    assert refusal is not None and refusal.code == "not-a-confirmer"
    assert "Mallory" in refusal.message and "requirements" in refusal.message
    assert "Ada Dev" in refusal.fix


def test_with_no_known_developer_and_no_list_nobody_can_confirm() -> None:
    refusal = confirmer_refusal("Ada Dev", [], "requirements")
    assert refusal is not None and refusal.code == "not-a-confirmer"
    assert "git config" in refusal.fix or "default_developer" in refusal.fix


def test_abbreviation_uses_its_own_code() -> None:
    refusal = confirmer_refusal("Mallory", ["Lead"], "requirements", authorising=True)
    assert refusal is not None and refusal.code == "not-an-authoriser"


# ---- the AI cannot record an approval (FR-012)


@pytest.mark.parametrize(
    "name",
    [
        "AI",
        "ai",
        "Claude",
        "claude code",
        "Assistant",
        "AI Agent",
        "agent",
        "Copilot",
        "ChatGPT",
        "LLM",
        "bot",
    ],
)
def test_names_that_are_the_ai_are_recognised(name: str) -> None:
    assert is_ai_actor(name)


@pytest.mark.parametrize("name", ["Ada Dev", "Ai Nguyen", "Claude Monet", "Bo Tran", "Mallory"])
def test_ordinary_names_are_not_mistaken_for_the_ai(name: str) -> None:
    assert not is_ai_actor(name)


# ---- git identity


def test_git_identity_reads_the_local_configuration(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "Local Person"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "local@example.test"], cwd=tmp_path, check=True)
    assert identity.git_identity(tmp_path) == ("Local Person", "local@example.test")


def test_git_identity_uses_the_nearest_existing_parent_of_a_directory_not_created_yet(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "Parent Person"], cwd=tmp_path, check=True)
    assert identity.git_identity(tmp_path / "specs" / "001-new")[0] == "Parent Person"


def test_git_identity_survives_git_being_absent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def missing(*args: object, **kwargs: object) -> None:
        raise FileNotFoundError("git")

    monkeypatch.setattr(identity.subprocess, "run", missing)
    assert identity.git_identity(tmp_path) == (None, None)
