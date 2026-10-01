"""Unsettled challenges and review findings (FR-026, FR-027; determinism requirement 37)."""

from __future__ import annotations

import pytest
from eil import corrections, overview, reviews
from eil.gates import check_stage
from eil.package import Package
from eil.records import approve
from eil.results import EilExit

from tests.helpers.derived import CONFIG, package_of
from tests.helpers.package import Story, record_block
from tests.unit.test_accept_changes import answer, prepared, reword_req2
from tests.unit.test_gates_completion import CONFIG as COMPLETION_CONFIG
from tests.unit.test_gates_completion import YES, crit, ready

REJECTED = {
    "id": "CH-005", "stage": "requirements", "raised_by": "ai", "raised_at": "2026-09-26T10:00:00Z",
    "target": "REQ-002", "text": "Should each pair carry a note?", "status": "closed",
    "responder": "Ada Dev", "response": "rejected", "reason": "Not needed", "at": "2026-09-26T10:05:00Z",
}  # fmt: skip


def rf(number: int = 1, status: str = "open", root: str = "implementation", extra: str = "") -> str:
    return (
        f"\n**RF-{number:03d}**: A reviewer found a fault in the merge step. (status: {status})\n"
        f"Root: {root}\n{extra}"
    )


def list_unsettled(story: Story) -> reviews.ReviewList:
    return reviews.build_list(package_of(story), "requirements", "unsettled-challenges")


def changed_after_rejection(story: Story) -> None:
    prepared(story)
    story.append("requirements", "\n" + record_block("challenge", REJECTED).rstrip("\n") + "\n")
    reword_req2(story)
    answer(story, summaries={"REQ-002": "Added a note to each pair."})
    reviews.confirm(package_of(story), CONFIG, "requirements", by="Ada Dev", confirmation="ok")


# ---- unsettled challenges


def test_a_rejected_challenge_whose_target_changed_is_listed_and_is_the_next_human_action(reference_story: Story) -> None:
    changed_after_rejection(reference_story)
    listed = list_unsettled(reference_story)
    assert [e.key for e in listed.entries] == ["CH-005"]
    assert "REQ-002 changed after this challenge was rejected" in listed.entries[0].why
    action = overview.status(package_of(reference_story))["next_action"]
    assert action["kind"] == "human" and "CH-005" in action["message"]


def test_a_challenge_about_an_unchanged_target_is_not_listed(reference_story: Story) -> None:
    prepared(reference_story)
    reference_story.append("requirements", "\n" + record_block("challenge", REJECTED).rstrip("\n") + "\n")
    assert list_unsettled(reference_story).entries == []


def test_a_confirmer_reconfirming_settles_the_entry(reference_story: Story) -> None:
    changed_after_rejection(reference_story)
    listed = list_unsettled(reference_story)
    reviews.answer(
        package_of(reference_story), CONFIG, "requirements", "unsettled-challenges",
        digest=listed.digest, by="Ada Dev", reply="still rejected", all_=True,
    )  # fmt: skip
    assert list_unsettled(reference_story).entries == []


def test_a_non_confirmer_cannot_reconfirm(reference_story: Story) -> None:
    changed_after_rejection(reference_story)
    listed = list_unsettled(reference_story)
    with pytest.raises(EilExit) as exc:
        reviews.answer(
            package_of(reference_story), CONFIG, "requirements", "unsettled-challenges",
            digest=listed.digest, by="Bob Guest", reply="fine", all_=True,
        )  # fmt: skip
    assert "not-a-confirmer" in [r["code"] for r in exc.value.payload["refusals"]]


def test_anyone_can_reopen_and_the_challenge_is_open_again(reference_story: Story) -> None:
    changed_after_rejection(reference_story)
    reviews.answer(
        package_of(reference_story), CONFIG, "requirements", "unsettled-challenges",
        digest=None, by="Bob Guest", reply="reopen CH-005", reopen=["CH-005"],
    )  # fmt: skip
    text = reference_story.read("requirements")
    assert '"status": "open"' in text.split('"id": "CH-005"')[1].split("```")[0]
    assert "CH-005" in overview.status(package_of(reference_story))["outstanding"]["open_challenges"]


# ---- review findings


def verification_with(story: Story, finding: str) -> Package:
    ready(story)
    story.append("verification", finding)
    return Package(story.root)


def test_an_open_finding_fails_ver_g07_and_completion_refuses(reference_story: Story) -> None:
    package = verification_with(reference_story, rf())
    assert crit(check_stage(package, "verification"), "VER-G07").status != "met"
    with pytest.raises(EilExit) as exc:
        approve(package, COMPLETION_CONFIG, "completion", "Ada Dev", YES)
    assert "review-finding-open" in [r["code"] for r in exc.value.payload["refusals"]]


def test_a_resolved_implementation_finding_passes(reference_story: Story) -> None:
    package = verification_with(reference_story, rf(status="resolved"))
    assert crit(check_stage(package, "verification"), "VER-G07").status == "met"
    assert approve(package, COMPLETION_CONFIG, "completion", "Ada Dev", YES)["approval"]["review_findings"]


def test_an_excepted_finding_needs_a_person_and_a_reason(reference_story: Story) -> None:
    package = verification_with(reference_story, rf(status="excepted", extra="Accepted by: claude\n"))
    assert crit(check_stage(package, "verification"), "VER-G07").status != "met"
    reference_story.write("verification", reference_story.read("verification").replace("Accepted by: claude\n", "Accepted by: Ada Dev\nReason: Cosmetic.\n"))
    assert crit(check_stage(Package(reference_story.root), "verification"), "VER-G07").status == "met"


def test_an_upstream_rooted_finding_must_be_the_origin_of_a_correction(reference_story: Story) -> None:
    package = verification_with(reference_story, rf(status="resolved", root="requirements"))
    assert crit(check_stage(package, "verification"), "VER-G07").status != "met"
    corrections.open_correction(package, "REQ-001", "code-review:RF-001", "vague", "Ada Dev")
    assert crit(check_stage(Package(reference_story.root), "verification"), "VER-G07").status == "met"


def test_a_finding_added_or_changed_after_completion_makes_it_needs_re_review(reference_story: Story) -> None:
    package = verification_with(reference_story, rf(status="resolved"))
    approve(package, COMPLETION_CONFIG, "completion", "Ada Dev", YES)
    assert Package(reference_story.root).state("completion").state == "approved"
    reference_story.append("verification", rf(2, status="resolved"))
    state = Package(reference_story.root).state("completion")
    assert state.state == "needs-re-review" and "RF-002" in (state.reason or "")


def test_an_unrelated_verification_edit_does_not_reopen_completion(reference_story: Story) -> None:
    package = verification_with(reference_story, rf(status="resolved"))
    approve(package, COMPLETION_CONFIG, "completion", "Ada Dev", YES)
    reference_story.write("verification", reference_story.read("verification").replace("\n## Open Tasks", "\nA remark.\n\n## Open Tasks", 1))
    state = Package(reference_story.root).state("completion")
    assert "review finding" not in (state.reason or "")
