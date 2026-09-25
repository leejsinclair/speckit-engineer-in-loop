"""The comprehension check (task T060; FR-087 to FR-094, research D-22, determinism 17 to 20)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
from eil import comprehension, records
from eil.comprehension import plan, record
from eil.gates import check_stage
from eil.identity import Config
from eil.package import Package
from eil.records import approve
from eil.results import EilExit

from tests.helpers.package import (
    Story,
    functional_doc,
    record_block,
    region,
    requirements_doc,
    with_functional,
)

LEVELS = ["recognise", "explain", "apply", "trace", "evaluate"]
JUDGED = ["FUN-G10", "FUN-G12", "FUN-G13"]
NOW = "2026-09-25T10:14:03Z"


@pytest.fixture(autouse=True)
def fixed_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(records, "utc_now", lambda: NOW)
    monkeypatch.setattr(comprehension, "utc_now", lambda: NOW)


@pytest.fixture
def config() -> Config:
    return Config(
        default_developer="Ada Dev",
        approvers={"functional": ["Ada Dev"], "requirements": ["Ada Dev"]},
        abbreviation_authorisers=[],
    )


def judgments(tmp: Path) -> Path:
    path = tmp / "j.json"
    path.write_text(
        json.dumps(
            {"stage": "functional", "judgments": [{"id": i, "status": "met", "reason": "ok"} for i in JUDGED]}
        )
    )
    return path


def approve_requirements_document(story: Story) -> None:
    text = story.read("requirements")
    record_ = {
        "stage": "requirements",
        "by": "Ada Dev",
        "at": NOW,
        "fingerprint": Package(story.root).fingerprint("requirements"),
        "attestation": "yes",
        "upstream": {},
        "items": {},
        "overrides_used": [],
    }
    story.write(
        "requirements",
        text.replace(
            "<!-- eil:begin approval -->\n<!-- eil:end approval -->", region("approval", record_).rstrip("\n")
        ),
    )


def ready(story: Story, tmp: Path, **kw: Any) -> Package:
    """A functional document whose gate is met except the comprehension check itself."""
    with_functional(story, **kw)
    approve_requirements_document(story)
    package = Package(story.root)
    check_stage(package, "functional", judgments_path=judgments(tmp))
    return package


def codes(exc: pytest.ExceptionInfo[EilExit]) -> list[str]:
    return [r["code"] for r in exc.value.payload["refusals"]]


def pick(fingerprint: str, level: str, attempt: int, eligible: list[str], taken: set[str]) -> str | None:
    pool = [i for i in sorted(eligible) if i not in taken] or sorted(eligible)
    if not pool:
        return None
    index = int(hashlib.sha256(f"{fingerprint}|{level}|{attempt}".encode()).hexdigest()[:8], 16) % len(pool)
    return pool[index]


# ---- the plan: deterministic targets (determinism 17)


def test_the_plan_lists_one_target_per_level(story_dir: Story, tmp_path: Path) -> None:
    package = ready(story_dir, tmp_path)
    result = plan(package, "functional")
    assert result["ok"] is True and result["stage"] == "functional" and result["attempt"] == 1
    assert [level["level"] for level in result["levels"]] == LEVELS
    assert result["fingerprint"] == package.fingerprint("functional")
    assert all(level["status"] == "ok" and level["target"] for level in result["levels"])


def test_repeated_runs_print_identical_targets(story_dir: Story, tmp_path: Path) -> None:
    package = ready(story_dir, tmp_path)
    assert plan(package, "functional") == plan(package, "functional")
    assert plan(package, "functional", attempt=3) == plan(package, "functional", attempt=3)


def test_the_targets_follow_the_normative_formula(story_dir: Story, tmp_path: Path) -> None:
    package = ready(story_dir, tmp_path)
    fingerprint = package.fingerprint("functional")
    eligible = {
        "recognise": ["FR-001", "NFR-001", "UC-001"],
        "explain": ["FR-001", "NFR-001"],
        "apply": ["FR-001", "UC-001"],
        "trace": ["ART-002", "ART-003", "FR-001", "NFR-001"],
        "evaluate": ["NFR-001"],
    }
    for attempt in (1, 2, 5):
        taken: set[str] = set()
        expected = {}
        for level in LEVELS:
            expected[level] = pick(fingerprint, level, attempt, eligible[level], taken)
            taken.add(expected[level])  # type: ignore[arg-type]
        got = {row["level"]: row["target"] for row in plan(package, "functional", attempt=attempt)["levels"]}
        assert got == expected, attempt


def test_a_different_attempt_can_give_a_different_target(story_dir: Story, tmp_path: Path) -> None:
    many = "\n\n".join(f"**FR-{n:03d}**: Requirement {n}. (traces: REQ-001)" for n in range(1, 13))
    package = ready(story_dir, tmp_path, sections={"Functional Requirements": many})
    targets = {
        plan(package, "functional", level="explain", attempt=k)["levels"][0]["target"] for k in range(1, 9)
    }
    assert len(targets) > 1


def test_the_targets_do_not_depend_on_formatting(story_dir: Story, tmp_path: Path) -> None:
    package = ready(story_dir, tmp_path)
    before = plan(package, "functional")
    path = story_dir.path("functional")
    path.write_bytes(path.read_bytes().replace(b"\n", b"  \r\n"))
    assert plan(package, "functional") == before


def test_a_content_change_gives_a_fresh_plan_for_the_new_version(story_dir: Story, tmp_path: Path) -> None:
    """FR-091: once a challenge is answered and the document changes, the plan is made again."""
    package = ready(story_dir, tmp_path)
    before = plan(package, "functional")
    story_dir.write(
        "functional", story_dir.read("functional").replace("within 60 seconds", "within 90 seconds")
    )
    check_stage(package, "functional", judgments_path=judgments(tmp_path))
    after = plan(package, "functional")
    assert after["fingerprint"] != before["fingerprint"]


def test_one_level_can_be_asked_for(story_dir: Story, tmp_path: Path) -> None:
    package = ready(story_dir, tmp_path)
    (row,) = plan(package, "functional", level="apply")["levels"]
    assert row["level"] == "apply" and row["target"] in {"FR-001", "UC-001"}


def test_the_plan_names_the_section_of_each_target_and_never_a_question(
    story_dir: Story, tmp_path: Path
) -> None:
    package = ready(story_dir, tmp_path)
    rows = {r["level"]: r for r in plan(package, "functional")["levels"]}
    sections = {
        "FR-001": "Functional Requirements",
        "NFR-001": "Non-Functional Requirements",
        "UC-001": "Use Cases",
    }
    for row in rows.values():
        if row["target"] in sections:
            assert row["section"] == sections[row["target"]]
        assert set(row) <= {"level", "status", "target", "section", "chain", "artifacts"}
    assert "question" not in json.dumps(plan(package, "functional")).lower()


def test_the_trace_target_carries_its_full_upstream_chain(story_dir: Story, tmp_path: Path) -> None:
    package = ready(story_dir, tmp_path)
    for attempt in range(1, 12):
        (row,) = plan(package, "functional", level="trace", attempt=attempt)["levels"]
        if row["target"] == "FR-001":
            assert row["chain"] == ["FR-001", "REQ-001"]
            assert row["artifacts"] == ["ART-002", "ART-003"]
            return
    pytest.fail("no attempt chose FR-001")


def test_a_level_with_nothing_eligible_is_no_material(story_dir: Story, tmp_path: Path) -> None:
    package = ready(
        story_dir,
        tmp_path,
        sections={"Non-Functional Requirements": None},
        not_applicable="- Non-Functional Requirements: none",
    )
    (row,) = plan(package, "functional", level="evaluate")["levels"]
    assert row == {"level": "evaluate", "status": "no-material"}


def test_an_id_chosen_for_an_earlier_level_is_skipped_when_something_else_is_eligible(
    story_dir: Story, tmp_path: Path
) -> None:
    package = ready(story_dir, tmp_path)
    rows = plan(package, "functional")["levels"]
    recognise, explain = rows[0]["target"], rows[1]["target"]
    assert not (recognise in {"FR-001", "NFR-001"} and explain == recognise)


# ---- prerequisites (FR-088) and eligibility


def test_only_functional_and_technical_are_eligible(story_dir: Story) -> None:
    for stage in ("requirements", "ai-spec", "plan", "completion"):
        story_dir.write(stage, "# x\n")
        with pytest.raises(EilExit) as exc:
            plan(Package(story_dir.root), stage)
        assert codes(exc) == ["stage-not-eligible"]


def test_an_unmet_criterion_blocks_the_check(story_dir: Story, tmp_path: Path) -> None:
    package = ready(story_dir, tmp_path, sections={"Business Rules": None})
    with pytest.raises(EilExit) as exc:
        plan(package, "functional")
    assert (
        codes(exc) == ["comprehension-prerequisites"]
        and "FUN-G03" in exc.value.payload["refusals"][0]["message"]
    )


def test_missing_ai_verdicts_block_the_check(story_dir: Story) -> None:
    with_functional(story_dir)
    with pytest.raises(EilExit) as exc:
        plan(Package(story_dir.root), "functional")
    assert codes(exc) == ["comprehension-prerequisites"]


def test_an_open_challenge_blocks_the_check(story_dir: Story, tmp_path: Path) -> None:
    challenge = record_block(
        "challenge",
        {"id": "CH-001", "stage": "functional", "status": "open", "target": "FR-001", "text": "gap"},
    )
    package = ready(story_dir, tmp_path, extra=challenge)
    with pytest.raises(EilExit) as exc:
        plan(package, "functional")
    assert (
        codes(exc) == ["comprehension-prerequisites"]
        and "CH-001" in exc.value.payload["refusals"][0]["message"]
    )


def test_an_overridden_criterion_does_not_block(story_dir: Story, tmp_path: Path) -> None:
    override = record_block(
        "override",
        {"id": "OVR-001", "stage": "functional", "criterion": "FUN-G03", "by": "Ada Dev", "reason": "r"},
    )
    package = ready(story_dir, tmp_path, sections={"Business Rules": None}, extra=override)
    assert plan(package, "functional")["ok"] is True


def test_the_comprehension_criterion_itself_is_not_a_prerequisite(story_dir: Story, tmp_path: Path) -> None:
    package = ready(story_dir, tmp_path)
    assert (
        next(c for c in check_stage(package, "functional", write=False).criteria if c.id == "FUN-G16").status
        == "not-met"
    )
    assert plan(package, "functional")["ok"] is True


# ---- recording (FR-092, determinism 18)


def take(package: Package, config: Config, level: str, outcome: str = "understood", **kw: Any) -> dict:
    args: dict = {"attempts": 1, "items": ["FR-001"], "reason": None}
    args.update(kw)
    return record(package, config, "functional", level, outcome, "Ada Dev", **args)


def region_of(package: Package) -> dict:
    return package.doc("functional").read_region("comprehension").obj


def test_a_record_holds_only_the_allowed_keys(story_dir: Story, tmp_path: Path, config: Config) -> None:
    package = ready(story_dir, tmp_path)
    take(package, config, "recognise")
    saved = region_of(package)
    assert set(saved) == {"stage", "fingerprint", "taken_by", "started_at", "updated_at", "levels"}
    assert saved["stage"] == "functional" and saved["taken_by"] == "Ada Dev"
    assert saved["fingerprint"] == package.fingerprint("functional")
    assert saved["started_at"] == saved["updated_at"] == NOW
    assert saved["levels"] == [
        {"level": "recognise", "outcome": "understood", "attempts": 1, "items": ["FR-001"]}
    ]


def test_the_record_never_holds_a_question_an_answer_a_hint_or_a_score(
    story_dir: Story, tmp_path: Path, config: Config
) -> None:
    package = ready(story_dir, tmp_path)
    for level in LEVELS:
        take(package, config, level, "coached", attempts=3)
    text = json.dumps(region_of(package)).lower()
    for word in ("question", "answer", "hint", "score", "points", "streak", "rank", "timer"):
        assert word not in text


def test_recording_a_level_again_replaces_that_level(
    story_dir: Story, tmp_path: Path, config: Config
) -> None:
    package = ready(story_dir, tmp_path)
    take(package, config, "recognise", "skipped")
    take(package, config, "explain")
    take(package, config, "recognise", "understood", attempts=2)
    levels = region_of(package)["levels"]
    assert [(lv["level"], lv["outcome"]) for lv in levels] == [
        ("recognise", "understood"),
        ("explain", "understood"),
    ]
    assert levels[0]["attempts"] == 2


def test_all_five_levels_make_a_complete_record(story_dir: Story, tmp_path: Path, config: Config) -> None:
    package = ready(story_dir, tmp_path)
    for level in LEVELS:
        take(package, config, level)
    assert (
        comprehension.summarise(region_of(package), package.fingerprint("functional"))["state"] == "complete"
    )
    assert (
        next(c for c in check_stage(package, "functional", write=False).criteria if c.id == "FUN-G16").status
        == "met"
    )


def test_recording_does_not_change_the_documents_fingerprint(
    story_dir: Story, tmp_path: Path, config: Config
) -> None:
    package = ready(story_dir, tmp_path)
    before = package.fingerprint("functional")
    take(package, config, "recognise")
    assert package.fingerprint("functional") == before


def test_a_stale_record_is_replaced_whole_not_merged(
    story_dir: Story, tmp_path: Path, config: Config
) -> None:
    package = ready(story_dir, tmp_path)
    take(package, config, "recognise")
    take(package, config, "explain")
    story_dir.write(
        "functional", story_dir.read("functional").replace("within 60 seconds", "within 90 seconds")
    )
    check_stage(package, "functional", judgments_path=judgments(tmp_path))
    take(package, config, "apply")
    saved = region_of(package)
    assert [lv["level"] for lv in saved["levels"]] == ["apply"]
    assert saved["fingerprint"] == package.fingerprint("functional")


def test_not_applicable_needs_a_reason(story_dir: Story, tmp_path: Path, config: Config) -> None:
    package = ready(story_dir, tmp_path)
    with pytest.raises(EilExit) as exc:
        take(package, config, "evaluate", "not-applicable", items=[])
    assert codes(exc) == ["reason-required"]
    take(
        package, config, "evaluate", "not-applicable", items=[], attempts=0, reason="one screen, no trade-off"
    )
    assert region_of(package)["levels"][0]["reason"] == "one screen, no trade-off"


def test_a_reason_is_only_allowed_with_not_applicable(
    story_dir: Story, tmp_path: Path, config: Config
) -> None:
    package = ready(story_dir, tmp_path)
    take(package, config, "recognise", "understood", reason="because")
    assert "reason" not in region_of(package)["levels"][0]


def test_only_a_configured_person_can_take_the_check(
    story_dir: Story, tmp_path: Path, config: Config
) -> None:
    package = ready(story_dir, tmp_path)
    with pytest.raises(EilExit) as exc:
        record(
            package,
            config,
            "functional",
            "recognise",
            "understood",
            "Mallory",
            attempts=1,
            items=["FR-001"],
            reason=None,
        )
    assert codes(exc) == ["not-a-confirmer"]
    assert region_of(package) is None


def test_the_ai_cannot_take_the_check(story_dir: Story, tmp_path: Path) -> None:
    open_config = Config(
        default_developer="Claude", approvers={"functional": ["Claude"]}, abbreviation_authorisers=[]
    )
    package = ready(story_dir, tmp_path)
    with pytest.raises(EilExit) as exc:
        record(
            package,
            open_config,
            "functional",
            "recognise",
            "understood",
            "Claude",
            attempts=1,
            items=[],
            reason=None,
        )
    assert "ai-approval" in codes(exc)


def test_items_must_exist_in_the_document_or_its_upstream(
    story_dir: Story, tmp_path: Path, config: Config
) -> None:
    package = ready(story_dir, tmp_path)
    with pytest.raises(EilExit) as exc:
        take(package, config, "recognise", items=["FR-999"])
    assert codes(exc) == ["unknown-item"]
    take(package, config, "recognise", items=["FR-001", "UC-001", "REQ-001"])  # upstream ids are fine


def test_an_unknown_level_is_refused(story_dir: Story, tmp_path: Path, config: Config) -> None:
    package = ready(story_dir, tmp_path)
    with pytest.raises(EilExit) as exc:
        take(package, config, "memorise")
    assert codes(exc) == ["unknown-level"]
    with pytest.raises(EilExit) as exc:
        plan(package, "functional", level="memorise")
    assert codes(exc) == ["unknown-level"]


def test_recording_is_refused_while_the_prerequisites_fail(story_dir: Story, config: Config) -> None:
    with_functional(story_dir)
    with pytest.raises(EilExit) as exc:
        take(Package(story_dir.root), config, "recognise")
    assert codes(exc) == ["comprehension-prerequisites"]


def test_a_stage_without_a_document_or_a_gate_is_not_eligible(story_dir: Story, config: Config) -> None:
    with pytest.raises(EilExit) as exc:
        record(
            Package(story_dir.root),
            config,
            "requirements",
            "recognise",
            "understood",
            "Ada Dev",
            attempts=1,
            items=[],
            reason=None,
        )
    assert codes(exc) == ["stage-not-eligible"]


# ---- malformed records (determinism 18, 19)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda r: r.update(score=3),
        lambda r: r["levels"][0].update(answer="the analyst uploads a file"),
        lambda r: r["levels"][0].update(hint="see the Business Rules"),
        lambda r: r["levels"][0].update(outcome="passed"),
        lambda r: r["levels"][0].update(level="memorise"),
        lambda r: r["levels"][0].update(outcome="understood", reason="x"),
        lambda r: r.pop("taken_by"),
    ],
)
def test_a_hand_edited_record_with_anything_else_is_malformed(
    story_dir: Story, tmp_path: Path, config: Config, mutate: Any
) -> None:
    package = ready(story_dir, tmp_path)
    for level in LEVELS:
        take(package, config, level)
    data = region_of(package)
    mutate(data)
    story_dir.write("functional", _replace_region(story_dir.read("functional"), data))
    result = check_stage(package, "functional", write=False)
    assert "malformed-comprehension" in [f.code for f in result.findings]
    assert next(c for c in result.criteria if c.id == "FUN-G16").status == "not-met"


def _replace_region(text: str, data: dict) -> str:
    start = text.index("<!-- eil:begin comprehension -->")
    end = text.index("<!-- eil:end comprehension -->") + len("<!-- eil:end comprehension -->")
    return text[:start] + region("comprehension", data).rstrip("\n") + text[end:]


# ---- approval needs a current, complete record, not a pass (FR-093, determinism 20)


def approve_functional(package: Package, config: Config) -> dict:
    return approve(
        package, config, "functional", by="Ada Dev", attestation="Yes, this is the behaviour we require."
    )


def test_approval_is_refused_without_a_record(story_dir: Story, tmp_path: Path, config: Config) -> None:
    package = ready(story_dir, tmp_path)
    before = story_dir.path("functional").read_bytes()
    with pytest.raises(EilExit) as exc:
        approve_functional(package, config)
    assert codes(exc) == ["unmet-criteria"] and "FUN-G16" in exc.value.payload["refusals"][0]["message"]
    assert story_dir.path("functional").read_bytes() == before


def test_approval_is_refused_with_an_incomplete_record(
    story_dir: Story, tmp_path: Path, config: Config
) -> None:
    package = ready(story_dir, tmp_path)
    take(package, config, "recognise")
    with pytest.raises(EilExit) as exc:
        approve_functional(package, config)
    assert "FUN-G16" in exc.value.payload["refusals"][0]["message"]


def test_approval_is_refused_when_the_document_changed_after_the_check(
    story_dir: Story, tmp_path: Path, config: Config
) -> None:
    package = ready(story_dir, tmp_path)
    for level in LEVELS:
        take(package, config, level)
    story_dir.write(
        "functional", story_dir.read("functional").replace("within 60 seconds", "within 90 seconds")
    )
    check_stage(package, "functional", judgments_path=judgments(tmp_path))
    with pytest.raises(EilExit) as exc:
        approve_functional(package, config)
    assert "FUN-G16" in exc.value.payload["refusals"][0]["message"]


def test_a_check_where_every_level_was_skipped_or_revealed_still_allows_approval(
    story_dir: Story, tmp_path: Path, config: Config
) -> None:
    package = ready(story_dir, tmp_path)
    for index, level in enumerate(LEVELS):
        take(package, config, level, "skipped" if index % 2 == 0 else "revealed")
    result = approve_functional(package, config)
    assert result["ok"] is True
    assert package.state("functional").state == "approved"


def test_the_counts_are_copied_into_the_approval_record(
    story_dir: Story, tmp_path: Path, config: Config
) -> None:
    package = ready(story_dir, tmp_path)
    outcomes = ["understood", "coached", "skipped", "understood", "understood"]
    for level, outcome in zip(LEVELS, outcomes, strict=True):
        take(package, config, level, outcome)
    approve_functional(package, config)
    approval = package.doc("functional").read_region("approval").obj
    assert approval["comprehension"] == {
        "understood": 3,
        "coached": 1,
        "revealed": 0,
        "skipped": 1,
        "not_applicable": 0,
    }


def test_the_approval_records_the_upstream_fingerprint(
    story_dir: Story, tmp_path: Path, config: Config
) -> None:
    package = ready(story_dir, tmp_path)
    for level in LEVELS:
        take(package, config, level)
    approve_functional(package, config)
    approval = package.doc("functional").read_region("approval").obj
    assert approval["upstream"] == {"requirements": package.fingerprint("requirements")}


def test_approving_requirements_is_unaffected_by_the_comprehension_rule(
    story_dir: Story, tmp_path: Path, config: Config
) -> None:
    story_dir.write("requirements", requirements_doc())
    path = tmp_path / "r.json"
    path.write_text(
        json.dumps(
            {
                "stage": "requirements",
                "judgments": [
                    {"id": i, "status": "met", "reason": "ok"}
                    for i in ("REQ-G01", "REQ-G11", "REQ-G12", "REQ-G13")
                ],
            }
        )
    )
    package = Package(story_dir.root)
    check_stage(package, "requirements", judgments_path=path)
    result = approve(package, config, "requirements", by="Ada Dev", attestation="yes")
    assert (
        result["ok"] is True
        and "comprehension" not in package.doc("requirements").read_region("approval").obj
    )


def test_functional_document_helper_leaves_the_region_empty_by_default() -> None:
    assert "<!-- eil:begin comprehension -->\n<!-- eil:end comprehension -->" in functional_doc()
