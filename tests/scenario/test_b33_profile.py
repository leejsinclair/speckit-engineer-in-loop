"""B-33 (US4, FR-019 to FR-022): a small story takes a short path, authorised once.

`profile set` is refused for a non-authoriser and needs a reason. Once set, the wireframe criterion is met
by it, plan and task entry run under its recorded override, there is one `derived` list, implementation
waits for it, comprehension asks two levels, and every approval is still required. `withdraw` restores it.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest

from tests.conftest import EilResult
from tests.fixtures import reference_story
from tests.helpers.package import Story, with_functional, with_record_sections

pytestmark = pytest.mark.scenario
SMALL = "specs/002-small"
REF = "specs/001-story"


def test_b33_profile(project: Path, eil: Callable[..., EilResult]) -> None:
    (project / ".specify" / "extensions" / "eil" / "eil-config.yml").write_text(
        "default_developer: Test Developer\nabbreviation_authorisers: [Test Developer]\n", encoding="utf-8"
    )
    small = Story(project / SMALL)
    with_functional(small, wireframe=None)
    ref = reference_story.build(project / REF)
    for stage in ("ai-spec", "plan", "tasks"):
        ref.write(stage, with_record_sections(ref.read(stage)))

    def run(feature: str, *argv: str) -> EilResult:
        return eil([*argv, "--feature-dir", feature, "--json"])

    refused = run(SMALL, "profile", "set", "small", "--by", "Mallory", "--reason", "small")
    assert refused.code == 1 and refused.refusal_codes == ["not-an-authoriser"]
    assert run(SMALL, "profile", "set", "small", "--by", "Test Developer", "--reason", "").refusal_codes == ["reason-required"]

    def wireframe() -> dict:
        checked = run(SMALL, "check", "--stage", "functional", "--full").json
        return next(c for c in checked["criteria"] if c["id"] == "FUN-G15")

    assert wireframe()["status"] == "not-met"
    assert run(SMALL, "profile", "set", "small", "--by", "Test Developer", "--reason", "One screen, detailed request").code == 0
    assert wireframe()["status"] == "met" and "small-story profile" in wireframe()["reason"]
    approve = run(SMALL, "approve", "functional", "--by", "Test Developer", "--attestation", "ok")
    assert approve.code == 1, "every approval is still required, with its gate"

    set_ref = run(REF, "profile", "set", "small", "--by", "Test Developer", "--reason", "Small change")
    assert set_ref.code == 0
    override = set_ref.json["override"]["id"]
    for command in ("plan", "tasks"):
        entered = run(REF, "enter", command)
        assert entered.code == 0 and entered.json["overrides_used"] == [override]
    blocked = run(REF, "enter", "implement")
    assert blocked.code == 1 and "unreviewed-ai-content" in blocked.refusal_codes
    derived = run(REF, "review", "list", "--stage", "derived", "--kind", "inferred").json
    assert derived["entries"] and {e["stage"] for e in derived["entries"]} <= {"ai-spec", "plan", "tasks"}
    answered = run(REF, "review", "answer", "--stage", "derived", "--kind", "inferred", "--digest", derived["digest"],
                   "--all", "--by", "Test Developer", "--reply", "ok")  # fmt: skip
    assert answered.code == 0, answered.stdout
    after = run(REF, "enter", "implement")
    assert "unreviewed-ai-content" not in after.refusal_codes
    status = run(REF, "status").json
    assert override in status["outstanding"]["overrides"] and status["profile"]["by"] == "Test Developer"

    assert run(SMALL, "profile", "withdraw", "--by", "Test Developer", "--reason", "it grew").code == 0
    assert wireframe()["status"] == "not-met"
    record = json.loads((project / SMALL / "eil-record.json").read_text())
    assert record["story"]["profile"]["withdrawn"]["reason"] == "it grew"
    assert run(SMALL, "review", "list", "--stage", "derived", "--kind", "inferred").refusal_codes == ["no-profile"]
