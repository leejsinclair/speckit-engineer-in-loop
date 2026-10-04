"""Abbreviation and who may do what (task T124; FR-013, FR-040, FR-045).

A small story may abbreviate a stage, never skip it: the abbreviation, who authorised it and why is
recorded and shown, and the stage still passes a gate. Approvers are enforced per stage on approve,
override and challenge answers, with a machine-local file able to override the shared one.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from eil import overview, records
from eil.identity import Config, load_config
from eil.package import Package
from eil.records import abbreviate, approve, override
from eil.results import EilExit

from tests.helpers.package import Story, with_technical

NOW = "2026-09-25T10:14:03Z"
CONFIG = Config(default_developer="Ada Dev", approvers={}, abbreviation_authorisers=[])


@pytest.fixture(autouse=True)
def fixed_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(records, "utc_now", lambda: NOW)


@pytest.fixture
def package(story_dir: Story) -> Package:
    with_technical(story_dir)
    return Package(story_dir.root)


def codes(exc: pytest.ExceptionInfo[EilExit]) -> list[str]:
    return [r["code"] for r in exc.value.payload["refusals"]]


def blocks(package: Package, stage: str) -> list[dict]:
    return [r.obj for r in package.doc(stage).records() if r.kind == "abbreviation" and r.obj]


# ---- abbreviating a stage (FR-040)


def test_an_abbreviation_records_who_authorised_it_and_why(package: Package) -> None:
    result = abbreviate(package, CONFIG, "technical", "Ada Dev", "a one-line change, the design is the diff")
    assert blocks(package, "technical") == [
        {
            "stage": "technical",
            "by": "Ada Dev",
            "at": NOW,
            "reason": "a one-line change, the design is the diff",
        }
    ]
    assert result["abbreviation"]["by"] == "Ada Dev"


def test_the_record_sits_under_an_abbreviation_heading_and_is_part_of_the_document(
    package: Package, story_dir: Story
) -> None:
    before = package.fingerprint("technical")
    abbreviate(package, CONFIG, "technical", "Ada Dev", "small")
    text = story_dir.read("technical")
    assert "## Abbreviation" in text and text.index("## Abbreviation") < text.index("```eil:abbreviation")
    assert package.fingerprint("technical") != before, "an abbreviation is a change a reviewer must see"


def test_an_abbreviated_stage_is_flagged_and_still_passes_its_gate(package: Package) -> None:
    abbreviate(package, CONFIG, "technical", "Ada Dev", "small")
    state = package.state("technical")
    assert state.abbreviated is True and state.state in ("draft", "in-review")
    from eil.gates import check_stage

    result = check_stage(package, "technical")
    assert not [
        c for c in result.criteria if c.status == "not-met" and c.kind != "judgment" and c.id != "TEC-G19"
    ]


def test_the_overview_and_status_show_the_abbreviation(package: Package) -> None:
    abbreviate(package, CONFIG, "technical", "Ada Dev", "small")
    report = overview.status(package)
    assert report["stages"]["technical"]["abbreviated"] is True
    model = overview.collect(package)
    assert model.abbreviated == [{"stage": "technical", "by": "Ada Dev"}]


def test_abbreviating_again_replaces_the_record_instead_of_stacking_it(package: Package) -> None:
    abbreviate(package, CONFIG, "technical", "Ada Dev", "small")
    abbreviate(package, CONFIG, "technical", "Ada Dev", "smaller")
    assert [b["reason"] for b in blocks(package, "technical")] == ["smaller"]


def test_a_stage_may_be_abbreviated_only_once_it_has_a_document_never_skipped(package: Package) -> None:
    with pytest.raises(EilExit) as exc:
        abbreviate(package, CONFIG, "ai-spec", "Ada Dev", "not needed")
    assert codes(exc) == ["cannot-skip"]
    assert not (package.root / "s04-ai-spec.md").exists()


def test_an_unknown_stage_is_refused(package: Package) -> None:
    with pytest.raises(EilExit) as exc:
        abbreviate(package, CONFIG, "design", "Ada Dev", "x")
    assert codes(exc) == ["unknown-stage"]


def test_a_reason_is_required(package: Package) -> None:
    with pytest.raises(EilExit) as exc:
        abbreviate(package, CONFIG, "technical", "Ada Dev", "  ")
    assert codes(exc) == ["reason-required"]
    assert blocks(package, "technical") == []


def test_only_an_authoriser_may_abbreviate_and_by_default_that_is_the_developer(package: Package) -> None:
    with pytest.raises(EilExit) as exc:
        abbreviate(package, CONFIG, "technical", "Mallory", "small")
    assert codes(exc) == ["not-an-authoriser"]
    listed = Config(default_developer="Ada Dev", approvers={}, abbreviation_authorisers=["Grace Lead"])
    with pytest.raises(EilExit) as exc:
        abbreviate(package, listed, "technical", "Ada Dev", "small")
    assert codes(exc) == ["not-an-authoriser"]
    assert abbreviate(package, listed, "technical", "Grace Lead", "small")["ok"]


def test_the_ai_cannot_authorise_an_abbreviation(package: Package) -> None:
    with pytest.raises(EilExit) as exc:
        abbreviate(package, CONFIG, "technical", "Claude", "small")
    assert "ai-approval" in codes(exc)


def test_refusals_are_reported_together_and_nothing_is_written(package: Package, story_dir: Story) -> None:
    before = story_dir.read("technical")
    with pytest.raises(EilExit) as exc:
        abbreviate(package, CONFIG, "technical", "Mallory", "")
    assert sorted(codes(exc)) == ["not-an-authoriser", "reason-required"]
    assert story_dir.read("technical") == before


def test_an_approved_stage_that_is_abbreviated_needs_a_fresh_approval(
    package: Package, story_dir: Story
) -> None:
    from tests.helpers.package import approve_stages

    approve_stages(story_dir, "requirements")
    assert package.state("requirements").state == "approved"
    abbreviate(package, CONFIG, "requirements", "Ada Dev", "small")
    assert package.state("requirements").state == "needs-re-review"


# ---- who may approve, override and answer (FR-013, FR-045)


def write_config(project: Path, name: str, body: str) -> None:
    directory = project / ".specify" / "extensions" / "eil"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / name).write_text(body, encoding="utf-8")


def test_per_stage_approvers_are_enforced_on_approve(package: Package, tmp_path: Path) -> None:
    config = Config(
        default_developer="Ada Dev", approvers={"requirements": ["Grace Lead"]}, abbreviation_authorisers=[]
    )
    with pytest.raises(EilExit) as exc:
        approve(package, config, "requirements", "Ada Dev", "Yes.")
    assert "not-a-confirmer" in codes(exc)
    with pytest.raises(EilExit) as exc:
        approve(package, config, "requirements", "Grace Lead", "Yes.")
    assert "not-a-confirmer" not in codes(exc), "Grace is accepted; the refusals left are about the document"


def test_the_same_list_governs_override_authority(package: Package) -> None:
    config = Config(
        default_developer="Ada Dev", approvers={"requirements": ["Grace Lead"]}, abbreviation_authorisers=[]
    )
    with pytest.raises(EilExit) as exc:
        override(package, config, "requirements", "REQ-G01", "Ada Dev", "spike")
    assert codes(exc) == ["not-a-confirmer"]
    assert override(package, config, "requirements", "REQ-G01", "Grace Lead", "spike")["ok"]


def test_the_same_list_governs_who_answers_a_challenge(package: Package) -> None:
    config = Config(
        default_developer="Ada Dev", approvers={"functional": ["Grace Lead"]}, abbreviation_authorisers=[]
    )
    records.add_challenge(
        package, "functional", "FR-001", "What about duplicates arriving together?", None, "medium"
    )
    with pytest.raises(EilExit) as exc:
        records.answer_challenge(package, config, "CH-001", "accepted", "Ada Dev")
    assert codes(exc) == ["not-a-confirmer"]
    assert records.answer_challenge(package, config, "CH-001", "accepted", "Grace Lead")["ok"]


def test_the_shared_file_sets_the_approvers_and_the_local_file_wins_per_key(tmp_path: Path) -> None:
    write_config(
        tmp_path,
        "eil-config.yml",
        "approvers:\n  requirements: [Grace Lead]\n  technical: [Ada Dev]\nabbreviation_authorisers: [Grace Lead]\n",
    )
    shared = load_config(tmp_path)
    assert shared.approvers["requirements"] == ["Grace Lead"] and shared.abbreviation_authorisers == [
        "Grace Lead"
    ]
    write_config(tmp_path, "local-config.yml", "approvers:\n  requirements: [Ada Dev]\n")
    local = load_config(tmp_path)
    assert local.approvers["requirements"] == ["Ada Dev"], "the machine-local file wins"
    assert local.approvers["technical"] == ["Ada Dev"], "a key it does not set is left as it was"
    assert local.abbreviation_authorisers == ["Grace Lead"]


def test_a_malformed_config_is_a_named_error_not_a_silent_default(tmp_path: Path) -> None:
    from eil.identity import ConfigError

    write_config(tmp_path, "eil-config.yml", "approvers: [not, a, mapping\n")
    with pytest.raises(ConfigError):
        load_config(tmp_path)


def test_one_listed_persons_confirmation_is_enough(package: Package) -> None:
    config = Config(
        default_developer="Ada Dev",
        approvers={"technical": ["Grace Lead", "Ada Dev"]},
        abbreviation_authorisers=[],
    )
    with pytest.raises(EilExit) as exc:
        approve(package, config, "technical", "Ada Dev", "Yes.")
    assert "not-a-confirmer" not in codes(exc)
