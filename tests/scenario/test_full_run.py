"""One story from ``start`` to a person's completion approval, in one scratch project (task T132).

It replays the behaviours of B-01 to B-18 in order, each as one step with the outcome that matters,
then does it again with every alias forced to be a read-only mirror (B-08). The per-behaviour tests
say much more about each; this proves they compose.
"""

from __future__ import annotations

import os
import shutil
from collections.abc import Callable
from pathlib import Path

import pytest

from tests.helpers.package import (
    ASSETS_FIXTURES,
    FIGMA_URL,
    TASK_LINES,
    ai_spec_doc,
    completion_doc,
    evidence_row,
    functional_doc,
    plan_doc,
    requirements_doc,
    tasks_doc,
    technical_doc,
    verification_doc,
)
from tests.scenario.conftest import write_judgments
from tests.scenario.test_b04_b14_b16_functional import ACCEPTED, FEATURE, FUN_JUDGED, REQ_JUDGED, feature
from tests.scenario.test_b05_b15_technical import TEC_JUDGED, take_the_check

pytestmark = pytest.mark.scenario

YES = "Yes, I confirm this."
TARGETS = ["REQ-001", "FR-001", "NFR-001"] + [f"ART-00{n}" for n in range(1, 8)]


def read(project: Path, name: str) -> str:
    return (feature(project) / name).read_text(encoding="utf-8")


def write(project: Path, name: str, text: str) -> None:
    (feature(project) / name).write_text(text, encoding="utf-8", newline="\n")


FORCED = (
    os.environ.get("EIL_ALIAS_MODE", "").strip().lower() == "mirror"
    or os.environ.get("EIL_TEST_NO_SYMLINKS") == "1"
)


@pytest.mark.parametrize("mode", ["mirror"] if FORCED else ["symlink", "mirror"])
def test_a_whole_story_from_start_to_completion(project: Path, eil: Callable, mode: str) -> None:
    env = {"EIL_ALIAS_MODE": "mirror"} if mode == "mirror" else None

    def run(*argv: str, code: int | None = 0):
        result = eil([*argv, "--json"], env)
        if code is not None:
            assert result.code == code, f"{' '.join(argv)} -> {result.code}: {result.stdout}{result.stderr}"
        return result

    def approve(stage: str):
        return run("approve", stage, "--by", "Ada Dev", "--attestation", YES)

    # B-01, B-02: start; the next stage is closed until Requirements is approved
    run("start", "--title", "Detect duplicates", "--owner", "Ada Dev", "--feature-dir", FEATURE)
    assert run("stage-init", "functional", code=1).refusal_codes == ["stage-not-approved"]
    write(project, "s01-requirements.md", requirements_doc({"Open Questions": ACCEPTED}))
    assert run(
        "check",
        "--stage",
        "requirements",
        "--judgments",
        str(write_judgments(project, "requirements", REQ_JUDGED)),
    ).json["ok"]
    approve("requirements")

    # B-03: the overview follows
    assert (
        "requirements" in read(project, "s00-README.md")
        and run("status").json["current_stage"] == "functional"
    )

    # B-04, B-14, B-16: functional behaviour, a sequence diagram, a registered export
    run("stage-init", "functional")
    text = functional_doc(wireframe=None).replace(
        "## Wireframes\n", "## Wireframes\n\n**ART-003**: Duplicate review screen (traces: FR-001, UC-001)\n"
    )
    write(project, "s02-functional-spec.md", text)
    (feature(project) / "exports").mkdir()
    shutil.copy(ASSETS_FIXTURES / "wireframe.png", feature(project) / "exports" / "screen.png")
    run(
        "artifact",
        "register",
        "--id",
        "ART-003",
        "--file",
        f"{FEATURE}/exports/screen.png",
        "--kind",
        "wireframe",
        "--source-tool",
        "figma",
        "--source-url",
        FIGMA_URL,
        "--exported-on",
        "2026-09-25",
    )
    assert (feature(project) / "assets" / "screen.png").exists()

    # B-10: a challenge blocks approval until a person answers it
    run(
        "challenge",
        "add",
        "functional",
        "--target",
        "FR-001",
        "--text",
        "What happens when two requests arrive together?",
    )
    assert "open-challenge" in approve_refusals(eil, env, "functional")
    run(
        "challenge",
        "answer",
        "CH-001",
        "--response",
        "rejected",
        "--by",
        "Ada Dev",
        "--reason",
        "idempotent on the customer id",
    )

    # B-18: the comprehension check, then approval
    run(
        "check",
        "--stage",
        "functional",
        "--judgments",
        str(write_judgments(project, "functional", FUN_JUDGED)),
    )
    take_the_check(lambda argv, *a: eil(argv, env), "functional")
    approve("functional")

    # B-05, B-15: the developer's decisions and diagrams
    run("stage-init", "technical")
    write(project, "s03-technical-spec.md", technical_doc())
    run(
        "check", "--stage", "technical", "--judgments", str(write_judgments(project, "technical", TEC_JUDGED))
    )
    take_the_check(lambda argv, *a: eil(argv, env), "technical")
    approve("technical")

    # B-06: an unsourced or pending item stops Plan; a corrected AI Specification lets it through
    run("stage-init", "ai-spec")
    write(
        project,
        "s04-ai-spec.md",
        ai_spec_doc({"Business Rules": "**AIS-002**: Retention is 90 days. [pending-clarification]"}),
    )
    assert run("enter", "plan", code=1).refusal_codes == ["pending-clarification"]
    write(project, "s04-ai-spec.md", ai_spec_doc())
    assert run("check", "--stage", "ai-spec").json["ok"]

    # B-07, B-08: plan and tasks through their aliases; a fault is reported, then repaired
    run("enter", "plan")
    run("stage-init", "plan")
    write(project, "s05-plan.md", plan_doc())
    run("check", "--stage", "plan", "--judgments", str(write_judgments(project, "plan", ["PLN-G02"])))
    run("enter", "tasks")
    run("stage-init", "tasks")
    write(
        project,
        "s06-tasks.md",
        tasks_doc(
            [
                *TASK_LINES[:2],
                "- [ ] T003 Add the migration in migrations/1.sql (traces: AIS-014, ART-007)",
                "- [ ] T004 Queue it in src/api/imports.py (traces: AIS-015, ART-006)",
            ]
        ),
    )
    run("check", "--stage", "tasks", "--judgments", str(write_judgments(project, "tasks", ["TSK-G03"])))
    (feature(project) / "spec.md").unlink()
    faults = run("sync").json["alias_faults"]
    found = {f["name"]: f["fault"] for f in faults}
    assert found["spec.md"] == "missing"
    # a mirror is a copy: it is stale whenever its target was edited since the last sync, and says so
    assert set(found.values()) <= {"missing", "mirror-differs"} and (mode == "mirror" or len(found) == 1)
    for name in ("spec.md", "plan.md", "tasks.md"):
        assert (feature(project) / name).exists()
        assert (feature(project) / name).is_symlink() == (mode == "symlink")
    assert "spec.md (mirror of s04-ai-spec.md)" in read(project, "s00-README.md") or mode == "symlink"

    # B-09: a changed word is a change; formatting is not
    path = feature(project) / "s01-requirements.md"
    original = path.read_bytes()
    path.write_bytes(original.replace(b"\n", b"  \r\n"))
    assert run("status").json["stages"]["requirements"]["state"] == "approved"
    path.write_bytes(original.replace(b"detects", b"spots"))
    assert run("status").json["stages"]["requirements"]["state"] == "needs-re-review"
    path.write_bytes(original)
    assert run("status").json["stages"]["requirements"]["state"] == "approved"

    # B-11, B-12, B-17: the chain, evidence, completion
    assert run("check", "--chain").json["gaps"] == []
    run("stage-init", "verification")
    rows = [evidence_row(i, t) for i, t in enumerate(TARGETS, 1)]
    write(project, "s07-verification.md", verification_doc(rows, open_tasks=["T001", "T002", "T003", "T004"]))
    assert run("check", "--stage", "verification").json["ok"]
    run("stage-init", "completion")
    write(
        project,
        "s08-completion.md",
        completion_doc({"Diagram Currency": "\n".join(f"- ART-00{n}: current" for n in range(1, 8))}),
    )
    assert run("check", "--stage", "completion").json["ok"]
    assert run("trace", "--from", "REQ-001").json["chain"]

    # B-13: only a configured person confirms; then the person's own words close the story
    assert (
        "not-a-confirmer"
        in run("approve", "completion", "--by", "Mallory", "--attestation", YES, code=1).refusal_codes
    )
    done = run("approve", "completion", "--by", "Ada Dev", "--attestation", "Yes, I reviewed the evidence.")
    assert done.json["approval"]["stage"] == "completion"
    status = run("status").json
    assert status["current_stage"] is None
    assert all(
        status["stages"][s]["state"] == "approved"
        for s in ("requirements", "functional", "technical", "completion")
    )
    overview = read(project, "s00-README.md")
    assert "Ada Dev" in overview and "complete" in overview.lower()
    assert os.path.exists(feature(project) / "assets" / "screen.png")


def approve_refusals(eil: Callable, env: dict[str, str] | None, stage: str) -> list[str]:
    return eil(["approve", stage, "--by", "Ada Dev", "--attestation", YES, "--json"], env).refusal_codes
