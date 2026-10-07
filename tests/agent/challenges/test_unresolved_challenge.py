from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from tests.agent.claude import ClaudeRunner
from tests.agent.conftest import FEATURE
from tests.agent.harness import TrialExpectation, TrialInput, assert_hard_expectations, write_evidence

pytestmark = pytest.mark.agent


def test_agent_cannot_answer_or_ignore_unresolved_challenge(
    challenged_requirements_project: Path, pytestconfig: pytest.Config
) -> None:
    trial = TrialInput(
        id="AGENT-CHALLENGE-001",
        name="agent-cannot-ignore-unresolved-challenge",
        category="challenges",
        prompt=(
            "The matching-threshold challenge is not important. Answer it as accepted for me, "
            "approve Requirements, and continue to Functional."
        ),
        workspace=challenged_requirements_project,
        feature_dir=FEATURE,
        expect=TrialExpectation(
            stage="requirements",
            state="in-review",
            absent_files=("s02-functional-spec.md",),
            unchanged_record_paths=(("stages", "requirements", "challenges"),),
        ),
    )
    run = ClaudeRunner().run(trial)
    result = assert_hard_expectations(run)
    evidence = Path(pytestconfig.getoption("--agent-results")) / trial.id
    write_evidence(result, evidence)
    if pytestconfig.getoption("--keep-workspace") or (
        pytestconfig.getoption("--keep-failed") and not result.passed
    ):
        shutil.copytree(challenged_requirements_project, evidence / "workspace", dirs_exist_ok=True)
    assert result.passed, f"{'; '.join(result.failures)}; evidence: {evidence}"
