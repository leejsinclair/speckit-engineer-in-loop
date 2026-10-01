"""B-06, B-07, B-08 and B-17 (task T086): the AI Specification, its aliases, plan and tasks, driving the
installed helper as the wrapped commands do. FR-004, FR-027, FR-039, FR-049 to FR-053, FR-057, FR-058,
FR-067, FR-082, FR-083."""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path

import pytest
from eil.package import Package

from tests.helpers.package import (
    AIS_SECTIONS,
    TASK_LINES,
    ai_spec_doc,
    mermaid,
    plan_doc,
    tasks_doc,
)
from tests.scenario.conftest import write_judgments
from tests.scenario.test_b04_b14_b16_functional import feature
from tests.scenario.test_b05_b15_technical import (
    YES,
    check,
    start_technical,
    take_the_check,
    write_technical,
)

pytestmark = pytest.mark.scenario

FORCED_MIRRORS = (
    os.environ.get("EIL_ALIAS_MODE", "").strip().lower() == "mirror"
    or os.environ.get("EIL_TEST_NO_SYMLINKS") == "1"
)


def is_alias(path: Path, target: str) -> bool:
    """A link to ``target``, or (where mirrors are forced) a read-only copy of it."""
    if FORCED_MIRRORS:
        return (
            path.is_file()
            and not path.is_symlink()
            and path.read_bytes() == path.with_name(target).read_bytes()
        )
    return path.is_symlink() and os.readlink(path) == target


PENDING = "**AIS-002**: Retention is 90 days. [pending-clarification]"


def approved_technical(project: Path, eil: Callable) -> None:
    start_technical(project, eil)
    write_technical(project)
    check(project, eil)
    take_the_check(eil, "technical")
    approved = eil(["approve", "technical", "--by", "Ada Dev", "--attestation", YES, "--json"])
    assert approved.code == 0, approved.stdout


def start_ai_spec(project: Path, eil: Callable) -> None:
    approved_technical(project, eil)
    result = eil(["stage-init", "ai-spec", "--json"])
    assert result.code == 0, result.stdout + result.stderr


def write(project: Path, name: str, text: str) -> None:
    (feature(project) / name).write_text(text, encoding="utf-8", newline="\n")


def read(project: Path, name: str) -> str:
    return (feature(project) / name).read_text(encoding="utf-8")


def gate(project: Path, eil: Callable, stage: str = "ai-spec"):
    return eil(["check", "--stage", stage, "--json"])


def unmet(result) -> dict[str, str]:
    return {c["id"]: c["reason"] for c in result.json["criteria"] if c["status"] == "not-met"}


# ---- B-06


def test_b06_the_ai_specification_cannot_start_before_technical_is_approved(
    project: Path, eil: Callable
) -> None:
    start_technical(project, eil)
    result = eil(["stage-init", "ai-spec", "--json"])
    assert result.code == 1 and result.refusal_codes == ["stage-not-approved"]
    assert not (feature(project) / "s04-ai-spec.md").exists() and not (feature(project) / "spec.md").exists()


def test_b06_stage_init_creates_the_document_from_the_template_and_then_its_alias(
    project: Path, eil: Callable
) -> None:
    start_ai_spec(project, eil)
    text = read(project, "s04-ai-spec.md")
    for heading in AIS_SECTIONS:
        assert f"## {heading}\n" in text, heading
    assert "{{" not in text
    assert is_alias(feature(project) / "spec.md", "s04-ai-spec.md")
    assert not (feature(project) / "plan.md").exists() and not (feature(project) / "tasks.md").exists()
    assert not gate(project, eil).json["ok"]  # an empty template never passes


def test_b06_a_traced_specification_passes_and_an_unsourced_item_does_not(
    project: Path, eil: Callable
) -> None:
    start_ai_spec(project, eil)
    write(project, "s04-ai-spec.md", ai_spec_doc())
    assert gate(project, eil).json["ok"]
    write(project, "s04-ai-spec.md", ai_spec_doc({"Business Rules": "**AIS-002**: Tax ids are unique."}))
    result = gate(project, eil)
    assert not result.json["ok"] and "AIS-002 traces to no approved source" in unmet(result)["AIS-G02"]
    assert eil(["approve", "ai-spec", "--by", "Ada Dev", "--attestation", "yes", "--json"]).refusal_codes == [
        "not-approvable"
    ]


def test_b06_a_pending_answer_fails_the_check_shows_in_the_overview_and_refuses_plan(
    project: Path, eil: Callable
) -> None:
    start_ai_spec(project, eil)
    write(project, "s04-ai-spec.md", ai_spec_doc({"Business Rules": PENDING}))
    result = gate(project, eil)
    assert "AIS-G03" in unmet(result)
    status = eil(["status", "--json"]).json
    assert status["outstanding"]["pending_clarifications"] == ["AIS-002"]
    assert "AIS-002" in read(project, "s00-README.md")
    before = sorted(p.name for p in feature(project).iterdir())
    entered = eil(["enter", "plan", "--json"])
    assert entered.code == 0 and [row["id"] for row in entered.json["blocked"]] == ["AIS-002"]
    assert sorted(p.name for p in feature(project).iterdir()) == before


def test_b06_resolve_carries_the_answer_upstream_and_a_named_override_lets_plan_proceed(
    project: Path, eil: Callable
) -> None:
    start_ai_spec(project, eil)
    write(project, "s04-ai-spec.md", ai_spec_doc({"Business Rules": PENDING}))
    resolved = eil(["resolve", "--id", "AIS-002", "--stage", "functional", "--json"])
    assert resolved.code == 0, resolved.stdout
    assert resolved.json["carried_to"] == "FR-002" and resolved.json["stage_state"] == "needs-re-review"
    assert "**FR-002**: Carried from AIS-002" in read(project, "s02-functional-spec.md")
    status = eil(["status", "--json"]).json
    assert status["stages"]["functional"]["state"] == "needs-re-review"
    # Nothing in the already-approved technical spec traces to the newly carried FR-002 (it could
    # not, since FR-002 did not exist when technical was approved), so per FR-043 ("depends on the
    # changed content") technical is not itself pulled into re-review — D-26.
    assert status["stages"]["technical"]["state"] == "approved"
    assert eil(["enter", "plan", "--json"]).code == 0, "a stage awaiting re-review blocks only what it reaches"
    again = eil(["resolve", "--id", "AIS-002", "--stage", "functional", "--json"])
    assert again.json["cleared"] is False
    for criterion in ("AIS-G02", "AIS-G03"):
        overridden = eil(
            [
                "override",
                "ai-spec",
                "--criterion",
                criterion,
                "--by",
                "Ada Dev",
                "--reason",
                "spike",
                "--json",
            ]
        )
        assert overridden.code == 0, overridden.stdout
    entered = eil(["enter", "plan", "--json"])
    stages = eil(["status", "--json"]).json["stages"]
    assert entered.code == 0 and stages["functional"]["state"] != "approved"
    overview = read(project, "s00-README.md")
    assert "AIS-G03" in overview and "OVR-" in overview


# ---- B-07: plan and tasks through aliases


def test_b07_plan_and_tasks_are_created_through_their_aliases_in_order(project: Path, eil: Callable) -> None:
    start_ai_spec(project, eil)
    write(project, "s04-ai-spec.md", ai_spec_doc())
    assert eil(["enter", "plan", "--json"]).code == 0
    planned = eil(["stage-init", "plan", "--json"])
    assert planned.code == 0, planned.stdout + planned.stderr
    assert (
        is_alias(feature(project) / "plan.md", "s05-plan.md") and not (feature(project) / "tasks.md").exists()
    )
    text = read(project, "s05-plan.md")
    assert "(traces: DEC-###)" in text and "{{" not in text
    write(project, "s05-plan.md", plan_doc())
    assert eil(["enter", "tasks", "--json"]).code == 0
    tasked = eil(["stage-init", "tasks", "--json"])
    assert tasked.code == 0, tasked.stdout + tasked.stderr
    for name, target in (
        ("spec.md", "s04-ai-spec.md"),
        ("plan.md", "s05-plan.md"),
        ("tasks.md", "s06-tasks.md"),
    ):
        assert is_alias(feature(project) / name, target)
    write(project, "s06-tasks.md", tasks_doc())
    result = gate(project, eil, "tasks")
    assert set(unmet(result)) == {"TSK-G03"}, unmet(result)
    assert all(line.endswith(")") and "(traces: AIS-" in line for line in TASK_LINES)


def test_b07_tasks_and_plan_refuse_to_start_out_of_order(project: Path, eil: Callable) -> None:
    start_ai_spec(project, eil)
    write(project, "s04-ai-spec.md", ai_spec_doc())
    result = eil(["stage-init", "tasks", "--json"])
    assert result.code == 1 and result.refusal_codes == ["plan-missing"]
    assert eil(["enter", "tasks", "--json"]).refusal_codes == ["plan-missing"]
    assert not (feature(project) / "tasks.md").exists()


@pytest.mark.skipif(FORCED_MIRRORS, reason="a mirror is read-only: edits go to the real document")
def test_b07_writing_through_an_alias_writes_the_real_document(project: Path, eil: Callable) -> None:
    start_ai_spec(project, eil)
    with (feature(project) / "spec.md").open("a", encoding="utf-8") as handle:
        handle.write("\n<!-- written through the alias -->\n")
    assert "written through the alias" in read(project, "s04-ai-spec.md")
    assert (feature(project) / "spec.md").is_symlink()


# ---- B-08: alias faults and mirrors


def test_b08_a_replaced_alias_is_reported_then_repaired_and_the_target_is_untouched(
    project: Path, eil: Callable
) -> None:
    start_ai_spec(project, eil)
    eil(["sync", "--json"])  # the first sync records the upgrade adoption (D-42) in the target
    target = (feature(project) / "s04-ai-spec.md").read_bytes()
    alias = feature(project) / "spec.md"
    alias.unlink()
    alias.write_text("a different spec\n", encoding="utf-8")
    result = eil(["sync", "--json"])
    assert result.code == 0 and result.json["alias_faults"][0]["fault"] == "diverged"
    assert alias.read_bytes() == target and (feature(project) / "s04-ai-spec.md").read_bytes() == target
    assert eil(["sync", "--json"]).json["alias_faults"] == []


def test_b08_a_deleted_alias_is_reported_missing_and_restored(project: Path, eil: Callable) -> None:
    start_ai_spec(project, eil)
    write(project, "s04-ai-spec.md", ai_spec_doc())
    eil(["stage-init", "plan", "--json"])
    (feature(project) / "plan.md").unlink()
    result = eil(["sync", "--json"])
    assert [f["fault"] for f in result.json["alias_faults"]] == ["missing"]
    assert (feature(project) / "plan.md").exists()


def test_b08_strict_mode_turns_a_fault_into_a_refusal_after_repairing_it(
    project: Path, eil: Callable
) -> None:
    start_ai_spec(project, eil)
    (feature(project) / "spec.md").unlink()
    result = eil(["sync", "--strict", "--json"])
    assert result.code == 1 and result.refusal_codes == ["alias-fault-strict"]


def test_b08_mirror_mode_makes_read_only_copies_listed_in_the_overview_and_refreshed_before_use(
    project: Path, eil: Callable
) -> None:
    start_ai_spec(project, eil)
    write(project, "s04-ai-spec.md", ai_spec_doc())
    mirror = {"EIL_ALIAS_MODE": "mirror"}
    assert eil(["sync", "--json"], mirror).code == 0
    alias = feature(project) / "spec.md"
    assert not alias.is_symlink() and alias.read_bytes() == (feature(project) / "s04-ai-spec.md").read_bytes()
    assert alias.stat().st_mode & 0o222 == 0
    assert "spec.md (mirror of s04-ai-spec.md)" in read(project, "s00-README.md")
    eil(["enter", "plan", "--json"], mirror)
    eil(["stage-init", "plan", "--json"], mirror)
    write(project, "s05-plan.md", plan_doc())
    entered = eil(["enter", "tasks", "--json"], mirror)
    assert entered.code == 0
    assert (feature(project) / "plan.md").read_bytes() == (feature(project) / "s05-plan.md").read_bytes()
    write(
        project, "s05-plan.md", plan_doc({"Summary (traces: DEC-001)": "Changed after the mirror was made."})
    )
    result = eil(["enter", "tasks", "--json"], mirror)
    faults = {f["name"]: f["fault"] for f in result.json["alias_faults"]}
    assert faults == {"plan.md": "mirror-differs"}, "reported before it was refreshed"
    assert (feature(project) / "plan.md").read_bytes() == (feature(project) / "s05-plan.md").read_bytes()


def test_b08_removing_the_helper_leaves_mirrors_as_ordinary_files(project: Path, eil: Callable) -> None:
    start_ai_spec(project, eil)
    eil(["sync", "--json"], {"EIL_ALIAS_MODE": "mirror"})
    assert (feature(project) / "spec.md").is_file()


# ---- B-17: artefacts through the AI specification and tasks


def test_b17_the_ai_specification_lists_artefacts_and_draws_none_of_its_own(
    project: Path, eil: Callable
) -> None:
    start_ai_spec(project, eil)
    write(project, "s04-ai-spec.md", ai_spec_doc())
    assert gate(project, eil).json["ok"]
    stray = ai_spec_doc({"Interfaces": mermaid("sequenceDiagram\n  A->>B: hi")})
    write(project, "s04-ai-spec.md", stray)
    result = gate(project, eil)
    assert (
        "artifact-wrong-level" in unmet(result)["AIS-G05"]
        or "artifact-unregistered" in unmet(result)["AIS-G05"]
    )


def test_b17_editing_an_approved_diagram_needs_the_stage_reviewed_and_names_the_artefact(
    project: Path, eil: Callable
) -> None:
    start_ai_spec(project, eil)
    write(project, "s04-ai-spec.md", ai_spec_doc())
    assert gate(project, eil).json["ok"]
    path = feature(project) / "s03-technical-spec.md"
    path.write_text(
        path.read_text(encoding="utf-8").replace('"REST", "[existing]', '"gRPC", "[existing]'),
        encoding="utf-8",
    )
    assert Package(feature(project)).state("technical").state == "needs-re-review"
    result = gate(project, eil)
    assert (
        "AIS-G04" in unmet(result)
        and "ART-004 changed since technical was approved" in unmet(result)["AIS-G04"]
    )
    assert "artifact-changed-since-approval" in [f["code"] for f in result.json["findings"]]
    refused = eil(["enter", "plan", "--json"])
    assert refused.code == 1 and "ai-spec-not-traceable" in refused.refusal_codes


def test_b17_a_task_list_that_misses_an_in_scope_er_diagram_is_flagged(project: Path, eil: Callable) -> None:
    start_ai_spec(project, eil)
    write(project, "s04-ai-spec.md", ai_spec_doc())
    eil(["stage-init", "plan", "--json"])
    write(project, "s05-plan.md", plan_doc())
    eil(["stage-init", "tasks", "--json"])
    write(project, "s06-tasks.md", tasks_doc([TASK_LINES[0], TASK_LINES[3]]))
    result = gate(project, eil, "tasks")
    assert "TSK-G02" in unmet(result) and "ART-007" in unmet(result)["TSK-G02"]
    assert "artifact-uncovered" in [f["code"] for f in result.json["findings"]]
    write(project, "s06-tasks.md", tasks_doc())
    assert "TSK-G02" not in unmet(gate(project, eil, "tasks"))


def test_b17_the_task_list_and_the_plan_are_judged_by_the_ai_and_show_as_such(
    project: Path, eil: Callable
) -> None:
    start_ai_spec(project, eil)
    write(project, "s04-ai-spec.md", ai_spec_doc())
    eil(["stage-init", "plan", "--json"])
    write(project, "s05-plan.md", plan_doc())
    eil(["stage-init", "tasks", "--json"])
    write(project, "s06-tasks.md", tasks_doc())
    judged = write_judgments(project, "tasks", ["TSK-G03"])
    result = eil(["check", "--stage", "tasks", "--judgments", str(judged), "--json"])
    assert result.json["ok"]
    assert Package(feature(project)).state("tasks").state == "in-review"
