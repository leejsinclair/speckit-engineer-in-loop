"""The one-reply review-list core (T008; determinism requirements 28, 29, 35, 36; FR-048, FR-050, D-36)."""

from __future__ import annotations

from typing import Any

import pytest
from eil import blockstatus, reviews
from eil.blocks import append_record, write_provenance
from eil.identity import Config
from eil.package import Package
from eil.results import EilExit

from tests.conftest import REPO_ROOT
from tests.helpers.package import Story, block_entry, with_approved_chain

STAGE = "requirements"
INFERRED = ("REQ-001", "UC-001", "OQ-001")
CONFIG = Config(default_developer="Ada Dev", approvers={"requirements": ["Ada Dev"]})


@pytest.fixture
def story(story_dir: Story) -> Story:
    with_approved_chain(story_dir)
    package = Package(story_dir.root)
    record = blockstatus.adopt(package, STAGE)
    assert record is not None
    for key in INFERRED:
        record["blocks"][key] = block_entry(record["blocks"][key]["hash"], "inferred")
    story_dir.write(STAGE, write_provenance(story_dir.read(STAGE), record))
    return story_dir


def package_of(story: Story) -> Package:
    return Package(story.root)


def the_list(story: Story) -> reviews.ReviewList:
    return reviews.build_list(package_of(story), STAGE, "inferred")


def answer(story: Story, by: str = "Ada Dev", reply: str = "ok", **kwargs: Any) -> dict[str, Any]:
    kwargs.setdefault("digest", the_list(story).digest)
    return reviews.answer(package_of(story), CONFIG, STAGE, "inferred", by=by, reply=reply, **kwargs)


def refused(story: Story, **kwargs: Any) -> list[str]:
    before = story.read(STAGE)
    with pytest.raises(EilExit) as exc:
        answer(story, **kwargs)
    assert story.read(STAGE) == before, "a refused answer must write nothing"
    return [r["code"] for r in exc.value.payload["refusals"]]


def record(story: Story) -> dict[str, Any]:
    obj = package_of(story).doc(STAGE).read_provenance().obj
    assert obj is not None
    return obj


def status_of(story: Story, key: str) -> str:
    return blockstatus.block_statuses(package_of(story))[STAGE][key].status


# ---- the list and its digest


def test_the_list_holds_the_unsettled_inferred_blocks(story: Story) -> None:
    listed = the_list(story)
    assert {e.key for e in listed.entries} == set(INFERRED)
    assert listed.kind == "inferred" and listed.stage == STAGE and listed.purpose == "validation"
    assert all(e.what and e.hash for e in listed.entries)


def test_the_digest_is_stable_for_the_same_state(story: Story) -> None:
    assert the_list(story).digest == the_list(story).digest
    assert the_list(story).digest.startswith("sha256:")


def test_the_digest_changes_when_any_entry_hash_changes(story: Story) -> None:
    before = the_list(story).digest
    text = story.read(STAGE)
    line = next(x for x in text.splitlines() if x.startswith("**REQ-001**"))
    story.write(STAGE, text.replace(line, line + " Also on export."))
    assert the_list(story).digest != before


def test_ai_views_are_shown_with_the_assessment_label(story: Story) -> None:
    listed = reviews.build_list(package_of(story), STAGE, "inferred", views={"REQ-001": "adds a retry policy"})
    view = next(e for e in listed.entries if e.key == "REQ-001").ai_view
    assert view == "AI assessment: adds a retry policy"


def test_every_list_carries_the_reply_check_limit(story: Story, monkeypatch: pytest.MonkeyPatch) -> None:
    assert reviews.REPLY_LIMIT in the_list(story).limits
    spec = reviews.KindSpec(purpose="awareness", build=lambda package, stage: [])
    monkeypatch.setitem(reviews.KINDS, "dummy", spec)
    for kind in reviews.KINDS:
        assert reviews.REPLY_LIMIT in reviews.build_list(package_of(story), STAGE, kind).limits


# ---- determinism 28


def test_a_stale_digest_gives_list_changed_and_writes_nothing(story: Story) -> None:
    stale = the_list(story).digest
    text = story.read(STAGE)
    line = next(x for x in text.splitlines() if x.startswith("**UC-001**"))
    story.write(STAGE, text.replace(line, line + " More."))
    assert refused(story, digest=stale, all_=True) == ["list-changed"]


# ---- recording answers


def test_all_records_one_acceptance_with_the_verbatim_reply(story: Story) -> None:
    result = answer(story, reply="ok to all, but note the typo", all_=True)
    acceptances = record(story)["acceptances"]
    assert len(acceptances) == 1
    one = acceptances[0]
    assert one["id"] == result["id"] == "RVW-001"
    assert one["reply"] == "ok to all, but note the typo"
    assert one["by"] == "Ada Dev" and one["kind"] == "inferred" and one["stage"] == STAGE
    assert sorted(one["accepted"]) == sorted(INFERRED)
    for key in INFERRED:
        assert status_of(story, key) == "settled"
        assert record(story)["blocks"][key]["reviewed"]["list"] == "RVW-001"
        assert record(story)["blocks"][key]["reviewed"]["reply"] == "ok to all, but note the typo"
    assert the_list(story).entries == []


def test_all_except_leaves_the_excepted_entry_for_rework(story: Story) -> None:
    answer(story, reply="fine except UC-001", all_except=["UC-001"])
    one = record(story)["acceptances"][0]
    assert one["except"] == ["UC-001"] and sorted(one["accepted"]) == ["OQ-001", "REQ-001"]
    assert status_of(story, "UC-001") == "needs-review"
    assert status_of(story, "REQ-001") == "settled"
    assert [e.key for e in the_list(story).entries] == ["UC-001"]


def test_question_is_recorded_and_settles_nothing(story: Story) -> None:
    answer(story, by="Priya Analyst", reply="why is this here?", question=["UC-001"])
    one = record(story)["acceptances"][0]
    assert one["questioned"] == ["UC-001"] and one["by"] == "Priya Analyst" and one["accepted"] == []
    assert status_of(story, "UC-001") == "needs-review"


def test_reopen_sends_a_settled_entry_back(story: Story) -> None:
    answer(story, all_=True)
    answer(story, by="Priya Analyst", reply="reopen this", reopen=["REQ-001"], digest=None)
    assert record(story)["acceptances"][1]["reopened"] == ["REQ-001"]
    assert status_of(story, "REQ-001") == "needs-review"


def test_an_id_on_no_list_and_not_settled_is_unknown(story: Story) -> None:
    assert refused(story, reply="huh", question=["FR-999"], digest=None) == ["unknown-item"]
    assert refused(story, reply="fine except FR-999", all_except=["FR-999"]) == ["unknown-item"]


# ---- reply and digest requirements


def test_a_blank_reply_is_refused(story: Story) -> None:
    assert refused(story, reply="   ", all_=True) == ["reply-required"]


def test_a_settling_answer_needs_a_digest(story: Story) -> None:
    assert refused(story, all_=True, digest=None) == ["digest-required"]


# ---- determinism 29


def test_a_settling_answer_by_a_non_confirmer_is_refused(story: Story) -> None:
    assert refused(story, by="Priya Analyst", all_=True) == ["not-a-confirmer"]


def test_a_settling_answer_by_the_ai_is_refused(story: Story) -> None:
    assert "ai-approval" in refused(story, by="AI", all_=True)


def test_question_and_reopen_from_anyone_record_the_name(story: Story) -> None:
    answer(story, by="Priya Analyst", reply="what does this add?", question=["REQ-001"])
    assert record(story)["acceptances"][0]["by"] == "Priya Analyst"


# ---- numbering


def test_rvw_numbering_continues_past_legacy_review_records(story: Story) -> None:
    text = story.read("functional")
    legacy = {"id": "RVW-007", "stage": "functional", "by": "Ada Dev", "at": "2026-09-01T00:00:00Z", "items": []}
    story.write("functional", append_record(text, "Reviews", "review", legacy))
    assert answer(story, all_=True)["id"] == "RVW-008"
    assert answer(story, by="Priya Analyst", reply="q", question=["REQ-001"], digest=None)["id"] == "RVW-009"


# ---- determinism 35


@pytest.mark.parametrize(
    "kwargs",
    [
        {"reply": "ok", "all_except": ["UC-001"]},
        {"reply": "ok to all", "question": ["UC-001"]},
        {"reply": "ok", "reopen": ["REQ-001"], "digest": None},
        {"reply": "ok except UC-001", "all_": True},
        {"reply": "Ok. Except OQ-001!", "all_": True},
    ],
)
def test_a_reply_that_contradicts_the_flags_is_refused(story: Story, kwargs: dict[str, Any]) -> None:
    assert refused(story, **kwargs) == ["reply-mismatch"]


@pytest.mark.parametrize("reply", ["ok to all.", "ok to all, but note the typo", "ok"])
def test_a_matching_all_reply_succeeds(story: Story, reply: str) -> None:
    answer(story, reply=reply, all_=True)
    assert record(story)["acceptances"][0]["reply"] == reply


# ---- determinism 36 (FR-050)


def test_a_reopen_with_no_digest_may_name_an_entry_settled_since_recorded(story: Story) -> None:
    answer(story, by="Ada Dev", reply="ok", all_=True)
    assert the_list(story).entries == []
    answer(story, by="Priya Analyst", reply="no, wrong", reopen=["REQ-001"], digest=None)
    assert record(story)["conflicts"] == [
        {
            "key": "REQ-001",
            "hash": record(story)["blocks"]["REQ-001"]["hash"],
            "answers": ["RVW-001", "RVW-002"],
        }
    ]
    assert reviews.conflicted_keys(package_of(story), STAGE) == {"REQ-001"}
    assert refused(story, all_=True, digest=None) == ["digest-required"]


def test_a_confirmers_new_answer_clears_the_conflict(story: Story) -> None:
    answer(story, all_=True)
    answer(story, by="Priya Analyst", reply="no", reopen=["REQ-001"], digest=None)
    result = answer(story, reply="I have checked; ok", all_=True)
    assert record(story)["conflicts"] == []
    assert record(story)["acceptances"][-1]["resolved_conflict"] is True
    assert result["resolved_conflict"] is True
    assert reviews.conflicted_keys(package_of(story), STAGE) == set()


def test_the_same_person_changing_their_mind_is_not_a_conflict(story: Story) -> None:
    answer(story, all_=True)
    answer(story, reply="on reflection no", reopen=["REQ-001"], digest=None)
    assert record(story).get("conflicts", []) == []


def test_a_question_does_not_clear_a_conflict(story: Story) -> None:
    answer(story, all_=True)
    answer(story, by="Priya Analyst", reply="no", reopen=["REQ-001"], digest=None)
    answer(story, reply="hm, why?", question=["REQ-001"])
    assert reviews.conflicted_keys(package_of(story), STAGE) == {"REQ-001"}


# ---- the command line (T018, T019)


def cli_run(story: Story, *argv: str) -> tuple[int, dict[str, Any]]:
    import io
    import json

    from eil import cli

    config = story.root / ".specify" / "extensions" / "eil" / "eil-config.yml"
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text("default_developer: Ada Dev\napprovers:\n  requirements: [Ada Dev]\n", encoding="utf-8")
    template = story.root / ".specify" / "templates" / "s00-readme-template.md"
    template.parent.mkdir(parents=True, exist_ok=True)
    template.write_text((REPO_ROOT / "templates" / "s00-readme-template.md").read_text(encoding="utf-8"), encoding="utf-8")
    out = io.StringIO()
    code = cli.main(
        [*argv, "--json", "--feature-dir", str(story.root)], cwd=story.root, env={}, stdout=out, stderr=io.StringIO()
    )
    return code, json.loads(out.getvalue())


def test_review_list_prints_the_list_and_its_digest(story: Story) -> None:
    code, out = cli_run(story, "review", "list", "--stage", STAGE, "--kind", "inferred")
    assert code == 0
    assert out["digest"] == the_list(story).digest
    assert {e["key"] for e in out["entries"]} == set(INFERRED)
    assert reviews.REPLY_LIMIT in out["limits"]


def test_review_list_shows_the_ai_views_with_their_label(story: Story, tmp_path: Any) -> None:
    import json

    views = tmp_path / "views.json"
    views.write_text(json.dumps({"stage": STAGE, "kind": "inferred", "views": [{"key": "UC-001", "view": "fine"}]}))
    _, out = cli_run(story, "review", "list", "--stage", STAGE, "--kind", "inferred", "--views", str(views))
    assert next(e for e in out["entries"] if e["key"] == "UC-001")["ai_view"] == "AI assessment: fine"


def test_review_answer_records_and_refuses_through_the_cli(story: Story) -> None:
    digest = the_list(story).digest
    args = ("review", "answer", "--stage", STAGE, "--kind", "inferred", "--by", "Ada Dev", "--reply", "ok to all.")
    code, out = cli_run(story, *args, "--digest", "sha256:0", "--all")
    assert code == 1 and out["refusals"][0]["code"] == "list-changed"
    code, out = cli_run(story, *args, "--digest", digest, "--all")
    assert code == 0 and out["id"] == "RVW-001", out
    assert status_of(story, "REQ-001") == "settled"


def test_blocks_list_reports_status_and_filters(story: Story) -> None:
    code, out = cli_run(story, "blocks", "list", "--stage", STAGE)
    assert code == 0
    by_key = {b["key"]: b for b in out["blocks"]}
    assert by_key["REQ-001"]["status"] == "needs-review" and by_key["REQ-001"]["class"] == "inferred"
    code, only = cli_run(story, "blocks", "list", "--stage", STAGE, "--status", "settled")
    assert code == 0 and "REQ-001" not in {b["key"] for b in only["blocks"]}
    assert {b["key"] for b in only["blocks"]}
