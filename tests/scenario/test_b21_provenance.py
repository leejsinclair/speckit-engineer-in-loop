"""B-21 (T036): review effort follows provenance. Only the inferred blocks are listed, a hand-removed tag
changes nothing, "ok except" settles the rest, and an unreviewed inferred item blocks only its dependants.
FR-009 to FR-014, FR-046, FR-049."""

from __future__ import annotations

import json
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from eil import cli

from tests.helpers.derived import edit, package_of
from tests.helpers.package import AIS_SECTIONS, Story, ai_spec_doc

pytestmark = pytest.mark.scenario
REPO = Path(__file__).resolve().parents[2]
Eil = Callable[..., tuple[int, Any]]

UNCITED = ("AIS-028", "AIS-029", "AIS-030", "AIS-031")
INFERRED = {"AIS-007", *UNCITED}
DEC2_RESTATERS = {13, 14, 15, 16}
TARGETS = [f"FR-{n:03d}" for n in range(1, 13)]


class Driver:
    def __init__(self, story: Story, eil_json: Eil, tmp: Path) -> None:
        self.story, self.eil_json, self.tmp = story, eil_json, tmp

    def __call__(self, *args: str) -> tuple[int, Any]:
        return self.eil_json([*args, "--feature-dir", str(self.story.root)], self.story.root)

    def statuses(self, stage: str, wanted: str | None = None) -> dict[str, str]:
        code, data = self("blocks", "list", "--stage", stage)
        assert code == 0, data
        return {r["key"]: r["status"] for r in data["blocks"] if wanted in (None, r["status"])}

    def classify(self, stage: str, verdicts: list[dict[str, Any]]) -> tuple[int, Any]:
        path = self.tmp / f"{stage}-verdicts.json"
        path.write_text(json.dumps({"stage": stage, "blocks": verdicts}))
        return self("blocks", "classify", "--stage", stage, "--file", str(path))

    def answer(self, stage: str, reply: str, *flags: str) -> tuple[int, Any]:
        digest = self("review", "list", "--stage", stage, "--kind", "inferred")[1]["digest"]
        return self(
            "review", "answer", "--stage", stage, "--kind", "inferred", "--digest", digest,
            "--reply", reply, "--by", "Ada Dev", *flags,
        )  # fmt: skip


def draft_ai_spec() -> str:
    """31 blocks: 26 restate an approved source, AIS-007 cites DEC-002 but adds a retry policy, and four cite nothing."""
    lines = []
    for n in range(1, 28):
        if n == 7:
            lines.append("**AIS-007**: Retry each failed analysis three times. (traces: DEC-002)")
        else:
            target = "DEC-002" if n in DEC2_RESTATERS else TARGETS[(n - 1) % 12]
            lines.append(f"**AIS-{n:03d}**: Implement behaviour {n}. (traces: {target})")
    lines += [f"**{key}**: A thing the AI decided on its own." for key in UNCITED]
    return ai_spec_doc({**{name: None for name in AIS_SECTIONS}, "Functional Requirements": "\n\n".join(lines)})


@pytest.fixture
def eil(reference_story: Story, eil_json: Eil, tmp_path: Path) -> Driver:
    reference_story.write("ai-spec", draft_ai_spec())
    project = reference_story.root.parent.parent
    config = project / ".specify" / "extensions" / "eil" / "eil-config.yml"
    config.parent.mkdir(parents=True)
    config.write_text(
        "default_developer: Ada Dev\napprovers:\n  requirements: [Ada Dev]\n  functional: [Ada Dev]\n"
        "  technical: [Ada Dev]\n  completion: [Ada Dev]\n",
        encoding="utf-8",
    )
    (project / ".specify" / "templates").mkdir(parents=True)
    shutil.copy(REPO / "templates" / "s00-readme-template.md", project / ".specify" / "templates")
    return Driver(reference_story, eil_json, tmp_path)


def tagged(story: Story) -> set[str]:
    return {line.split("**")[1] for line in story.read("ai-spec").splitlines() if "[ai-draft]" in line and "**AIS-" in line}


def test_b21_review_effort_follows_provenance(eil: Driver) -> None:
    story = eil.story
    # 1-2: classify; five inferred (with AIS-007's reason), 26 restated, a tag on exactly the five
    verdicts = [{"block": f"AIS-{n:03d}", "adds": "a retry policy" if n == 7 else None} for n in range(1, 28)]
    code, data = eil.classify("ai-spec", verdicts)
    assert code == 0, data
    statuses = eil.statuses("ai-spec")
    assert {k for k, s in statuses.items() if s == "needs-review"} == INFERRED
    assert sum(1 for s in statuses.values() if s == "settled") == 26
    assert tagged(story) == INFERRED
    listed = eil("review", "list", "--stage", "ai-spec", "--kind", "inferred")[1]
    assert {e["key"] for e in listed["entries"]} == INFERRED
    assert next(e for e in listed["entries"] if e["key"] == "AIS-007")["why"] == "adds a retry policy"

    # 3: a tag removed by hand changes no status, and sync puts it back
    story.write("ai-spec", story.read("ai-spec").replace("Retry each failed analysis three times. (traces: DEC-002) [ai-draft]", "Retry each failed analysis three times. (traces: DEC-002)"))
    assert "AIS-007" not in tagged(story) and eil.statuses("ai-spec") == statuses
    assert eil("sync")[0] == 0
    assert tagged(story) == INFERRED and eil.statuses("ai-spec") == statuses

    # 4: a task tracing to AIS-007 is blocked; others proceed
    edit(story, "tasks", "T011 Build part 11 in src/part11.py (traces: AIS-011)", "T011 Build part 11 in src/part11.py (traces: AIS-007)")
    cli._persist_adoption(package_of(story))
    for stage in ("plan", "tasks", "verification"):
        listed = eil("review", "list", "--stage", stage, "--kind", "unknown-currency")[1]
        if listed["entries"]:
            eil("review", "answer", "--stage", stage, "--kind", "unknown-currency", "--digest", listed["digest"], "--reply", "ok", "--by", "Ada Dev", "--all")
    code, data = eil("enter", "implement", "--task", "T011")
    assert code == 1 and data["refusals"][0]["code"] == "work-blocked"
    assert "AIS-007" in data["refusals"][0]["message"]
    assert eil("enter", "implement", "--task", "T012")[0] == 0

    # 5: "ok except AIS-003" analogue: except one of the four, the other four settle by hash
    code, data = eil.answer("ai-spec", "ok except AIS-029", "--all-except", "AIS-029")
    assert code == 0, data
    assert sorted(data["accepted"]) == sorted(INFERRED - {"AIS-029"})
    after = eil("review", "list", "--stage", "ai-spec", "--kind", "inferred")[1]
    assert [e["key"] for e in after["entries"]] == ["AIS-029"]
    assert tagged(story) == {"AIS-029"}
    assert eil("enter", "implement", "--task", "T011")[0] == 0

    # 6: edit DEC-002; the restated blocks citing it become source-changed, the others stay settled
    edit(story, "technical", "Reason for decision 2.", "A changed reason for decision 2.")
    statuses = eil.statuses("ai-spec")
    assert {k for k, s in statuses.items() if s == "source-changed"} == {"AIS-007", "AIS-013", "AIS-014", "AIS-015", "AIS-016"}
    assert statuses["AIS-001"] == "settled"

    # 7: anyone may reclassify a restated block as inferred, recorded with the name
    code, data = eil("blocks", "reclassify", "--stage", "ai-spec", "--block", "AIS-001", "--to", "inferred", "--by", "Sam QA")
    assert code == 0, data
    assert eil.statuses("ai-spec")["AIS-001"] == "needs-review"
    assert "Sam QA" in json.dumps(package_of(story).doc("ai-spec").read_provenance().obj)
