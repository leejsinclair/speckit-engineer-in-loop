from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

from tests.agent.claude import ClaudeRunner
from tests.agent.conftest import FEATURE, HELPER
from tests.agent.conversation import ProgressGuard, ScriptedPerson
from tests.agent.harness import TrialExpectation, TrialInput

pytestmark = [pytest.mark.agent, pytest.mark.slow]

TRIAL_ID = "AGENT-HAPPY-001"
DOCUMENTS = tuple(
    f"s{number:02d}-{name}.md"
    for number, name in enumerate(
        (
            "README",
            "requirements",
            "functional-spec",
            "technical-spec",
            "ai-spec",
            "plan",
            "tasks",
            "verification",
            "completion",
        )
    )
)
APPROVALS = {
    "requirements": "Yes, I approve the requirements as the problem I intend to solve.",
    "functional": "Yes, I approve the functional specification as the behaviour I require.",
    "technical": "Yes, I approve the technical specification as the solution I intend to build.",
    "completion": "Yes, I reviewed the evidence and confirm the story is complete.",
}
INITIAL_PROMPT = """\
/speckit-eil-1-requirements Add duplicate-email detection to the existing customer import module.
Create the governed story at `specs/001-duplicate-customer`.

I am Test Developer. Use the full workflow, not the small-story profile. Use chat for every review.
These are my complete requirements and decisions:

- `duplicate_index(existing_emails, candidate_email)` returns the zero-based index of the first
  duplicate, or None when there is no duplicate.
- Compare email addresses after trimming surrounding whitespace and Unicode-aware case folding.
- A blank candidate email raises ValueError. Existing blank values simply do not match.
- This is synchronous library behaviour with no UI, persistence, network, logging, migration, or
  deployment work.
- Keep the public function in `src/customer_import.py`; use a linear scan and Python's standard
  library only. I own and approve these observable and technical decisions.
- Acceptance is the existing `python3 -m unittest discover -s tests -p 'test_*.py'` suite passing.
- The implementation is not deployed. No diagrams outside the required Mermaid text are needed.

Draft the Requirements stage and stop whenever EIL requires my review, comprehension, validation,
decision, or approval. Never provide an answer on my behalf.
Call the Skill tool with `skill="speckit-eil-1-requirements"` and pass this request as its arguments.
Do not create substitute workflow scripts or reports.
"""


def test_agent_completes_a_whole_story_with_scripted_human_turns(
    happy_path_project: Path, pytestconfig: pytest.Config
) -> None:
    evidence = Path(pytestconfig.getoption("--agent-results")) / TRIAL_ID
    evidence.mkdir(parents=True, exist_ok=True)
    trial = TrialInput(
        id=TRIAL_ID,
        name="complete-story-happy-path",
        category="happy-path",
        prompt=INITIAL_PROMPT,
        workspace=happy_path_project,
        feature_dir=FEATURE,
        expect=TrialExpectation(stage="completion", state="approved"),
    )
    runner = ClaudeRunner(
        model=pytestconfig.getoption("--agent-model"),
        allowed_tools=("Bash", "Read", "Edit", "Write", "Skill"),
    )
    person = ScriptedPerson("Test Developer")
    progress = ProgressGuard()
    prompt = trial.prompt
    session_id: str | None = None

    try:
        for number in range(1, pytestconfig.getoption("--agent-max-turns") + 1):
            turn = runner.run_turn(trial, prompt=prompt, session_id=session_id)
            _write_turn(evidence, number, prompt, turn)
            assert turn.exit_status == 0, f"Claude exited {turn.exit_status}; evidence: {evidence}"
            session_id = turn.session_id
            status = _eil(happy_path_project, "status")
            _write_json(evidence / f"turn-{number:03d}-status.json", status)
            if status.get("next_action", {}).get("kind") == "done":
                break
            progress.observe(status)
            reply = person.reply(turn.transcript, status)
            prompt = reply.text
            _write_json(
                evidence / f"turn-{number:03d}-reply.json",
                {"kind": reply.kind, "text": reply.text},
            )
        else:
            pytest.fail(f"happy path exceeded the turn limit; evidence: {evidence}")

        _assert_complete(happy_path_project, evidence)
    except BaseException:
        if pytestconfig.getoption("--keep-failed") or pytestconfig.getoption("--keep-workspace"):
            shutil.copytree(happy_path_project, evidence / "workspace", dirs_exist_ok=True)
        raise
    else:
        if pytestconfig.getoption("--keep-workspace"):
            shutil.copytree(happy_path_project, evidence / "workspace", dirs_exist_ok=True)


def _assert_complete(project: Path, evidence: Path) -> None:
    status = _eil(project, "status")
    record = json.loads((project / FEATURE / "eil-record.json").read_text(encoding="utf-8"))
    _write_json(evidence / "state-final.json", status)
    _write_json(evidence / "record-final.json", record)

    assert status["current_stage"] is None
    assert status["next_action"]["kind"] == "done"
    assert status["outstanding"]["open_questions"] == []
    assert status["outstanding"]["open_challenges"] == []
    for stage, attestation in APPROVALS.items():
        approval = record["stages"][stage]["approval"]
        assert approval["by"] == "Test Developer"
        assert approval["attestation"] == attestation
    for stage in ("functional", "technical"):
        comprehension = record["stages"][stage]["comprehension"]
        assert comprehension["taken_by"] == "Test Developer"
        assert {row["level"] for row in comprehension["levels"]} == {
            "recognise",
            "explain",
            "apply",
            "trace",
            "evaluate",
        }
    for document in DOCUMENTS:
        assert (project / FEATURE / document).is_file(), document
    assert _eil(project, "check", "--chain")["gaps"] == []

    tests = subprocess.run(
        ["python3", "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py"],
        cwd=project,
        capture_output=True,
        text=True,
        check=False,
    )
    (evidence / "application-tests.txt").write_text(tests.stdout + tests.stderr, encoding="utf-8")
    assert tests.returncode == 0, tests.stdout + tests.stderr


def _eil(project: Path, *args: str) -> dict[str, Any]:
    proc = subprocess.run(
        ["python3", str(HELPER), *args, "--json"],
        cwd=project,
        capture_output=True,
        text=True,
        check=False,
    )
    value = json.loads(proc.stdout)
    assert isinstance(value, dict)
    if proc.returncode == 3 and args == ("status",):
        return value
    assert proc.returncode == 0, proc.stdout + proc.stderr
    return value


def _write_turn(evidence: Path, number: int, prompt: str, turn: Any) -> None:
    _write_json(
        evidence / f"turn-{number:03d}.json",
        {
            "session_id": turn.session_id,
            "exit_status": turn.exit_status,
            "duration_seconds": turn.duration_seconds,
            "prompt": prompt,
            "payload": turn.payload,
        },
    )
    (evidence / f"turn-{number:03d}-transcript.md").write_text(
        turn.transcript.rstrip() + "\n", encoding="utf-8"
    )


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
