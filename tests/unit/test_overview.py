"""The generated overview (task T051; FR-054 to FR-056, contracts/document-format.md §Overview)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from eil import overview
from eil.fingerprint import fingerprint_file
from eil.package import Package

from tests.helpers.package import Story, record_block, region, requirements_doc

TEMPLATE = (Path(__file__).resolve().parents[2] / "templates" / "s00-readme-template.md").read_text(
    encoding="utf-8"
)
SECTIONS = [
    "Story",
    "Status",
    "Documents",
    "Artefacts",
    "Approvals",
    "Outstanding",
    "Accepted risks",
    "Abbreviated stages",
    "Mirrors",
]
CANARY = "PROSE-CANARY-do-not-copy-me"


def render(story: Story, title: str = "Dup", owner: str = "Ada Dev") -> str:
    return overview.render(Package(story.root), TEMPLATE, title, owner)


def section(text: str, name: str) -> str:
    match = re.search(rf"^## {re.escape(name)}\n(.*?)(?=^## |\Z)", text, re.S | re.M)
    assert match, f"no section {name!r} in:\n{text}"
    return match.group(1).strip("\n")


def approved_requirements(story: Story, **extra: Any) -> None:
    text = requirements_doc(**extra)
    story.write("requirements", text)
    fp = fingerprint_file(story.path("requirements"))
    record = {
        "stage": "requirements",
        "by": "Ada Dev",
        "at": "2026-09-25T10:14:03Z",
        "fingerprint": fp,
        "attestation": "yes",
        "upstream": {},
        "items": {},
        "overrides_used": [],
    }
    story.write(
        "requirements",
        text.replace(
            "<!-- eil:begin approval -->\n<!-- eil:end approval -->", region("approval", record).rstrip("\n")
        ),
    )


# ---- grammar


def test_the_first_line_is_the_generated_notice(story_dir: Story) -> None:
    assert (
        render(story_dir).splitlines()[0]
        == "<!-- eil:generated — edit the stage documents, not this file -->"
    )


def test_sections_come_in_the_fixed_order(story_dir: Story) -> None:
    text = render(story_dir)
    assert re.findall(r"^## (.+)$", text, re.M) == SECTIONS


def test_story_and_status(story_dir: Story) -> None:
    story_dir.write("requirements", requirements_doc())
    text = render(story_dir, "Detect duplicates", "Ada Dev")
    assert section(text, "Story") == "- Title: Detect duplicates\n- Owner: Ada Dev"
    assert section(text, "Status") == "- Current stage: requirements\n- Overall status: draft"


def test_nine_document_rows_in_order_with_derived_state(story_dir: Story) -> None:
    story_dir.write("requirements", requirements_doc())
    rows = [
        line
        for line in section(render(story_dir), "Documents").splitlines()
        if line.startswith("| ") and "---" not in line
    ][1:]
    assert len(rows) == 9
    assert [r.split("|")[1].strip() for r in rows] == [
        "[s00-README.md](s00-README.md)",
        "[s01-requirements.md](s01-requirements.md)",
        "s02-functional-spec.md",
        "s03-technical-spec.md",
        "s04-ai-spec.md",
        "s05-plan.md",
        "s06-tasks.md",
        "s07-verification.md",
        "s08-completion.md",
    ]
    assert [r.split("|")[2].strip() for r in rows] == [
        "generated",
        "draft",
        "not-started",
        "not-started",
        "not-started",
        "not-started",
        "not-started",
        "not-started",
        "not-started",
    ]


def test_an_approved_stage_shows_in_documents_and_status(story_dir: Story) -> None:
    approved_requirements(story_dir)
    story_dir.write("functional", "# Functional\n")
    text = render(story_dir)
    assert "| [s01-requirements.md](s01-requirements.md) | approved |" in text
    assert section(text, "Status") == "- Current stage: functional\n- Overall status: draft"


# ---- artefacts


def test_artefacts_are_none_when_there_are_none(story_dir: Story) -> None:
    assert section(render(story_dir), "Artefacts") == "none"


def test_an_artefact_row_shows_id_kind_stage_state_and_a_link(story_dir: Story) -> None:
    story_dir.write("requirements", requirements_doc())
    body = section(render(story_dir), "Artefacts")
    assert "| ART-001 | c4-context | requirements | ok | [System context](s01-requirements.md) |" in body


def test_an_unparseable_diagram_is_shown_as_unparsed(story_dir: Story) -> None:
    from tests.helpers.package import CONTEXT_DIAGRAM

    story_dir.write("requirements", requirements_doc(diagram=CONTEXT_DIAGRAM + "\n  Bogus(x)"))
    assert "| ART-001 | c4-context | requirements | unparsed |" in section(render(story_dir), "Artefacts")


def test_an_artefact_edited_after_approval_is_shown_as_changed(story_dir: Story) -> None:
    from eil.artifacts import scan_document
    from eil.trace import item_hash, parse_document

    approved_requirements(story_dir)
    doc = Package(story_dir.root).doc("requirements")
    parsed = parse_document(doc)
    scan_document(doc, "requirements", parsed)
    hashes = {i.id: item_hash(i) for i in parsed.items}
    text = story_dir.read("requirements")
    record = {
        "stage": "requirements",
        "by": "Ada Dev",
        "at": "t",
        "fingerprint": "sha256:" + "0" * 64,
        "attestation": "y",
        "upstream": {},
        "items": hashes,
        "overrides_used": [],
    }
    text = re.sub(
        r"<!-- eil:begin approval -->.*<!-- eil:end approval -->",
        region("approval", record).rstrip("\n"),
        text,
        flags=re.S,
    )
    text = text.replace("Reads customers", "Queries customers")
    story_dir.write("requirements", text)
    assert "| ART-001 | c4-context | requirements | changed-since-approval |" in section(
        render(story_dir), "Artefacts"
    )


# ---- approvals


def test_approvals_are_none_before_any(story_dir: Story) -> None:
    story_dir.write("requirements", requirements_doc())
    assert section(render(story_dir), "Approvals") == "none"


def test_an_approval_row_shows_who_when_and_a_short_fingerprint(story_dir: Story) -> None:
    approved_requirements(story_dir)
    fingerprint = Package(story_dir.root).fingerprint("requirements")
    body = section(render(story_dir), "Approvals")
    assert f"| requirements | Ada Dev | 2026-09-25T10:14:03Z | {fingerprint[7:19]} |" in body


def test_functional_and_technical_approvals_show_the_comprehension_counts(story_dir: Story) -> None:
    story_dir.write("functional", "# F\n")
    fp = fingerprint_file(story_dir.path("functional"))
    counts = {"understood": 3, "coached": 1, "revealed": 0, "skipped": 1, "not_applicable": 0}
    record = {
        "stage": "functional",
        "by": "Ada Dev",
        "at": "t",
        "fingerprint": fp,
        "attestation": "y",
        "upstream": {},
        "items": {},
        "overrides_used": [],
        "comprehension": counts,
    }
    story_dir.append("functional", region("approval", record))
    body = section(render(story_dir), "Approvals")
    assert "understood 3 · coached 1 · skipped 1" in body
    assert "revealed" not in body


# ---- outstanding


def test_nothing_outstanding_reads_none(story_dir: Story) -> None:
    story_dir.write("requirements", requirements_doc())
    assert section(render(story_dir), "Outstanding") == (
        "- Open questions: none\n- Open challenges: none\n- Pending clarifications: none\n- Overrides: none\n- Issues: none"
    )


def test_open_questions_challenges_pending_clarifications_and_overrides_are_listed(story_dir: Story) -> None:
    question = "**OQ-004**: Keep history? (status: open) (material: yes)"
    challenge = record_block(
        "challenge",
        {"id": "CH-002", "stage": "requirements", "status": "open", "target": "OQ-004", "text": "x"},
    )
    closed = record_block("challenge", {"id": "CH-001", "stage": "requirements", "status": "closed"})
    override = record_block(
        "override",
        {"id": "OVR-001", "stage": "requirements", "criterion": "REQ-G06", "by": "Ada Dev", "reason": "r"},
    )
    story_dir.write(
        "requirements",
        requirements_doc({"Open Questions": question}, extra="\n".join([challenge, closed, override])),
    )
    story_dir.write("ai-spec", "# AI\n\n**AIS-001**: An answer [pending-clarification]\n")
    body = section(render(story_dir), "Outstanding")
    assert "- Open questions: OQ-004" in body
    assert "- Open challenges: CH-002" in body
    assert "- Pending clarifications: AIS-001" in body
    assert "- Overrides: OVR-001 (requirements REQ-G06 by Ada Dev)" in body


def test_document_errors_are_listed_as_issues(story_dir: Story) -> None:
    story_dir.write("requirements", requirements_doc() + "\n**FR-7**: malformed\n")
    body = section(render(story_dir), "Outstanding")
    assert "- Issues: malformed-item" in body and "s01-requirements.md" in body


# ---- accepted risks, abbreviations, mirrors


def test_accepted_open_questions_are_carried_as_accepted_risks(story_dir: Story) -> None:
    accepted = "**OQ-004**: Keep history? (status: accepted) (accepted-by: Ada Dev) (material: yes)"
    story_dir.write("requirements", requirements_doc({"Open Questions": accepted}))
    assert section(render(story_dir), "Accepted risks") == "- OQ-004 (accepted by Ada Dev, requirements)"


def test_accepted_risks_none(story_dir: Story) -> None:
    story_dir.write("requirements", requirements_doc())
    assert section(render(story_dir), "Accepted risks") == "none"


def test_abbreviated_stages_are_listed_with_who_authorised_them(story_dir: Story) -> None:
    rec = record_block("abbreviation", {"stage": "requirements", "by": "Lead Dev", "reason": "a spike"})
    story_dir.write("requirements", requirements_doc(extra=rec))
    assert section(render(story_dir), "Abbreviated stages") == "- requirements (authorised by Lead Dev)"
    assert section(render(story_dir), "Mirrors") == "none"


# ---- what may appear (FR-055)


def test_document_prose_is_never_copied_into_the_overview(story_dir: Story) -> None:
    sections = {
        "Background": CANARY,
        "Problem Statement": CANARY,
        "Desired Outcome": f"**REQ-001**: {CANARY}",
        "Open Questions": f"**OQ-004**: {CANARY} (status: accepted) (accepted-by: Ada Dev) (material: yes)",
    }
    story_dir.write("requirements", requirements_doc(sections, extra=f"{CANARY} in the overrides section"))
    story_dir.write("functional", f"# F\n\n**FR-001**: {CANARY} (traces: REQ-001)\n")
    assert CANARY not in render(story_dir)


def test_only_an_artefacts_own_title_is_copied_and_never_its_diagram(story_dir: Story) -> None:
    story_dir.write("requirements", requirements_doc())
    text = render(story_dir)
    assert "System context" in text
    assert "Person(analyst" not in text and "C4Context" not in text


# ---- derived, regenerable, authoritative documents win (FR-056)


def test_regeneration_is_byte_identical(story_dir: Story) -> None:
    approved_requirements(story_dir)
    assert render(story_dir) == render(story_dir)
    overview.write(Package(story_dir.root), TEMPLATE, "Dup", "Ada Dev")
    first = story_dir.path("overview").read_bytes()
    assert overview.write(Package(story_dir.root), TEMPLATE) is False
    assert story_dir.path("overview").read_bytes() == first


def test_title_and_owner_survive_regeneration(story_dir: Story) -> None:
    story_dir.write("requirements", requirements_doc())
    package = Package(story_dir.root)
    overview.write(package, TEMPLATE, "Detect duplicates", "Ada Dev")
    story_dir.write("requirements", requirements_doc() + "\nedit\n")
    overview.write(package, TEMPLATE)
    assert overview.read_story(package) == ("Detect duplicates", "Ada Dev")


def test_a_hand_edited_overview_is_overridden_by_the_derived_state_and_the_disagreement_is_reported(
    story_dir: Story,
) -> None:
    story_dir.write("requirements", requirements_doc())
    package = Package(story_dir.root)
    overview.write(package, TEMPLATE, "Dup", "Ada Dev")
    assert overview.drifted(package, TEMPLATE) is False
    story_dir.write("overview", story_dir.read("overview").replace("| draft |", "| approved |"))
    assert overview.drifted(package, TEMPLATE) is True
    assert overview.write(package, TEMPLATE) is True
    assert "| [s01-requirements.md](s01-requirements.md) | draft |" in story_dir.read("overview")
    assert overview.drifted(package, TEMPLATE) is False


def test_the_overview_reflects_a_stage_needing_re_review(story_dir: Story) -> None:
    approved_requirements(story_dir)
    story_dir.append("requirements", "\nA change after approval.\n")
    assert "| [s01-requirements.md](s01-requirements.md) | needs-re-review |" in render(story_dir)
