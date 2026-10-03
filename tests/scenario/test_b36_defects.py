"""B-36 (US9, FR-036 to FR-040): the helper does not get in its own way.

The plan's own Change Log and Record headings pass its gate; classification is additive and skips an
unknown key; derived stages reach `reviewed`; after completion is approved, status says the story is
done and never "Continue verification".
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest

from tests.conftest import EilResult
from tests.fixtures import two_stories
from tests.helpers import derived

pytestmark = pytest.mark.scenario


def test_b36_defects(project: Path, eil: Callable[..., EilResult], tmp_path: Path) -> None:
    stories = two_stories.build(project)
    a = "specs/001-a"

    def run(*argv: str, feature: str = a) -> EilResult:
        return eil([*argv, "--feature-dir", feature, "--json"])

    # Completion approved: done, and no "Continue verification".
    status = run("status")
    assert status.json["next_action"]["kind"] == "done"
    assert status.json["next"].startswith("Story complete; approved by")
    assert "Continue verification" not in status.stdout

    # The plan's own record headings are never "not derivable".
    derived.settle_derived(stories.a)
    plan = run("check", "--stage", "plan")
    assert "## Record" in stories.a.read("plan")
    assert not [f for f in plan.json["findings"] if f["code"] == "plan-not-derivable" and "Record" in f["message"]]

    # Classification is additive and skips an unknown key.
    b = "specs/002-b"
    blocks = run("blocks", "list", "--stage", "functional", feature=b).json["blocks"]
    first, second = blocks[0]["key"], blocks[1]["key"]
    for chosen in ([first, second], [second]):
        path = tmp_path / "classes.json"
        path.write_text(json.dumps({"stage": "functional", "blocks": [{"block": k, "adds": "x"} for k in chosen] + [{"block": "FR-999", "adds": None}]}))
        result = run("blocks", "classify", "--stage", "functional", "--file", str(path), feature=b)
        assert result.code == 0, result.stdout + result.stderr
        assert [s["key"] for s in result.json["skipped"]] == ["FR-999"]
    record = json.loads((project / b / "eil-record.json").read_text())["stages"]["functional"]["provenance"]
    assert record["blocks"][first]["adds"] == "x"

    # A derived stage whose blocks are all reviewed is `reviewed`.
    assert run("status").json["stages"]["plan"]["state"] == "reviewed"
