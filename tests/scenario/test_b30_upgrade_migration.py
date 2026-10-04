"""B-30 (US7, FR-023 to FR-025, SC-006): an upgrade adopts approved work without re-asking.

On the `bd7a0d5`-shaped story (approvals with no section-level records, one paragraph and one diagram
changed since in each): nothing needs review, `accept` never refuses for want of section records, one
reply re-signs each stage marked "re-signed without comparison", judgments survive `sync`, and no
`[ai-draft]` tag appears in any document.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest

from tests.conftest import EilResult
from tests.fixtures import legacy_upgrade

pytestmark = pytest.mark.scenario
FEATURE = "specs/001-story"


def test_b30_upgrade_migration(project: Path, eil: Callable[..., EilResult], tmp_path: Path) -> None:
    legacy_upgrade.build(project / FEATURE)
    config = project / ".specify" / "extensions" / "eil" / "eil-config.yml"
    config.write_text("default_developer: Ada Dev\n", encoding="utf-8")

    def run(*argv: str) -> EilResult:
        return eil([*argv, "--feature-dir", FEATURE, "--json"])

    def judged(stage: str) -> dict[str, str]:
        record = json.loads((project / FEATURE / "eil-record.json").read_text())["stages"][stage][
            "assessment"
        ]
        return {c["id"]: c["status"] for c in record["criteria"] if c["kind"] == "judgment"}

    before = {s: judged(s) for s in ("functional", "technical")}
    assert run("sync").code == 0
    assert {s: judged(s) for s in ("functional", "technical")} == before  # judgments survive the upgrade

    status = run("status").json
    for stage in ("functional", "technical"):
        assert status["stages"][stage]["state"] == "needs-re-review"
        assert status["stages"][stage]["blocks"]["needs_review"] == 0
    assert "unreviewed-ai-content" not in json.dumps(status)

    for stage in ("functional", "technical"):
        listed = run("review", "list", "--stage", stage, "--kind", "changes").json
        keys = [e["key"] for e in listed["entries"]]
        assert keys[0] == f"legacy:{stage}" and keys.count(f"legacy:{stage}") == 1
        summaries = tmp_path / f"{stage}-summaries.json"
        rows = [{"key": k, "summary": f"Summary of {k}."} for k in keys if not k.startswith("legacy:")]
        summaries.write_text(json.dumps({"stage": stage, "summaries": rows}))
        answered = run("review", "answer", "--stage", stage, "--kind", "changes", "--digest", listed["digest"],
                       "--all", "--by", "Ada Dev", "--reply", "ok", "--summaries", str(summaries))  # fmt: skip
        assert answered.code == 0, answered.stdout
        confirmed = run("review", "confirm", "--stage", stage, "--by", "Ada Dev", "--confirmation", "ok",
                        "--summaries", str(summaries))  # fmt: skip
        assert confirmed.code == 0, confirmed.stdout
        assert confirmed.json["approval"]["reached"] == "re-signed-without-comparison"

    final = run("status").json
    for stage in ("functional", "technical"):
        assert final["stages"][stage]["state"] == "approved"
        assert final["stages"][stage]["approval"]["reached"] == "re-signed-without-comparison"
    overview = (project / FEATURE / "s00-README.md").read_text()
    assert "re-signed without comparison" in overview
    for name in ("s01-requirements.md", "s02-functional-spec.md", "s03-technical-spec.md", "s05-plan.md"):
        assert "[ai-draft]" not in (project / FEATURE / name).read_text(), name
