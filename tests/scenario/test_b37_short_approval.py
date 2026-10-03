"""B-37 (US10, FR-047 to FR-049): approving takes one word.

`status` offers the helper's own approval question; "ok" approves; the record holds "ok" verbatim with
that question and the person's name; the document's approval line shows both; an empty reply is refused.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest

from tests.conftest import EilResult
from tests.helpers.package import Story, requirements_doc

pytestmark = pytest.mark.scenario
FEATURE = "specs/001-short"
QUESTION = "Approve the Requirements as the problem we intend to solve?"


def test_b37_short_approval(project: Path, eil: Callable[..., EilResult], tmp_path: Path) -> None:
    story = Story(project / FEATURE)
    story.write("requirements", requirements_doc())

    def run(*argv: str) -> EilResult:
        return eil([*argv, "--feature-dir", FEATURE, "--json"])

    judgments = tmp_path / "j.json"
    judgments.write_text(json.dumps({"stage": "requirements", "judgments": [{"id": i, "status": "met", "reason": "ok"} for i in ("REQ-G01", "REQ-G11", "REQ-G12", "REQ-G13")]}))
    assert run("check", "--stage", "requirements", "--judgments", str(judgments)).code == 0
    assert run("status").json["next_action"]["question"] == QUESTION

    empty = run("approve", "requirements", "--by", "Test Developer", "--attestation", " ")
    assert empty.code == 1 and "attestation-required" in empty.refusal_codes
    approved = run("approve", "requirements", "--by", "Test Developer", "--attestation", "ok")
    assert approved.code == 0, approved.stdout
    record = json.loads((project / FEATURE / "eil-record.json").read_text())["stages"]["requirements"]["approval"]
    assert record["attestation"] == "ok" and record["question"] == QUESTION and record["by"] == "Test Developer"
    assert f'"ok" to "{QUESTION}"' in story.read("requirements")
