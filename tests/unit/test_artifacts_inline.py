"""ART item and attachment pairing, kind derivation and level findings (task T029;
FR-071, FR-076, FR-081, determinism 14)."""

from __future__ import annotations

import pytest
from eil.artifacts import PERMITTED_KINDS, ArtifactScan, scan_text
from eil.trace import item_hash

from tests.helpers.package import mermaid, record_block

CONTAINER = 'C4Container\n  Person(a, "Analyst")\n  System(s, "Platform")\n  Rel(a, s, "Uses")'
CONTEXT = 'C4Context\n  Person(a, "Analyst")\n  System(s, "Platform")\n  Rel(a, s, "Uses")'
COMPONENT = 'C4Component\n  Container_Boundary(api, "API") {\n    Component(c, "Ctl", "MVC")\n  }'
SEQUENCE = "sequenceDiagram\n  actor A\n  participant S as System\n  A->>S: go"
ER = "erDiagram\n  CUSTOMER ||--o{ ORDER : has"


def scan(text: str, stage: str) -> ArtifactScan:
    return scan_text(text, stage, path="doc.md")


def codes(found: ArtifactScan) -> list[str]:
    return [f.code for f in found.findings]


def art(item_id: str, *, traces: str = "FR-001", title: str = "A view", extra: str = "") -> str:
    clause = f" (traces: {traces})" if traces else ""
    return f"**{item_id}**: {title}{clause}{extra}\n"


# ---- pairing


def test_an_art_line_and_the_fence_after_it_form_one_artifact() -> None:
    found = scan(art("ART-001") + "\n" + mermaid(CONTAINER), "technical")
    assert codes(found) == []
    (artifact,) = found.artifacts
    assert (artifact.id, artifact.kind, artifact.form, artifact.stage) == (
        "ART-001",
        "c4-container",
        "inline",
        "technical",
    )
    assert artifact.traces == ["FR-001"]
    assert artifact.diagram is not None and artifact.diagram.kind == "c4-container"


def test_blank_lines_and_prose_may_sit_between_the_line_and_the_fence() -> None:
    text = (
        art("ART-001")
        + "\n\nSome explanatory prose about the diagram.\n\nMore prose.\n\n"
        + mermaid(CONTAINER)
    )
    found = scan(text, "technical")
    assert codes(found) == [] and len(found.artifacts) == 1


def test_a_heading_between_them_ends_the_association() -> None:
    text = art("ART-001") + "\n## Another section\n\n" + mermaid(CONTAINER)
    found = scan(text, "technical")
    assert sorted(codes(found)) == ["artifact-unregistered", "artifact-unregistered"]
    assert {f.where for f in found.findings} == {"ART-001", "doc.md:5"}


def test_another_item_line_ends_the_association_and_the_fence_pairs_with_the_nearer_art() -> None:
    text = art("ART-001") + "\n" + art("ART-002") + "\n" + mermaid(CONTAINER)
    found = scan(text, "technical")
    assert [(f.code, f.where) for f in found.findings] == [("artifact-unregistered", "ART-001")]
    assert [a.id for a in found.artifacts] == ["ART-001", "ART-002"]
    assert next(a for a in found.artifacts if a.id == "ART-002").form == "inline"
    assert next(a for a in found.artifacts if a.id == "ART-001").form is None


def test_a_non_art_item_between_them_also_ends_the_association() -> None:
    text = art("ART-001") + "\n**FR-002**: Something else\n\n" + mermaid(CONTAINER)
    found = scan(text, "technical")
    assert sorted(f.where for f in found.findings) == ["ART-001", "doc.md:5"]


def test_a_task_line_ends_the_association() -> None:
    text = art("ART-001") + "\n- [ ] T001 a task\n\n" + mermaid(CONTAINER)
    assert len(codes(scan(text, "technical"))) == 2


def test_a_mermaid_fence_with_no_art_line_is_unregistered() -> None:
    found = scan("# Container view\n\n" + mermaid(CONTAINER), "technical")
    assert [(f.code, f.where) for f in found.findings] == [("artifact-unregistered", "doc.md:3")]
    assert found.artifacts == []


def test_an_art_line_with_no_attachment_is_unregistered() -> None:
    found = scan(art("ART-001"), "technical")
    assert [(f.code, f.where) for f in found.findings] == [("artifact-unregistered", "ART-001")]
    assert found.artifacts[0].form is None


def test_only_one_attachment_belongs_to_an_art_line() -> None:
    text = art("ART-001") + "\n" + mermaid(CONTAINER) + "\n" + mermaid(COMPONENT)
    found = scan(text, "technical")
    assert [(f.code) for f in found.findings] == ["artifact-unregistered"]
    assert found.findings[0].where == "doc.md:10"


def test_other_fences_are_not_attachments() -> None:
    text = art("ART-001") + "\n```json\n{}\n```\n\n" + mermaid(CONTAINER)
    found = scan(text, "technical")
    assert codes(found) == [] and found.artifacts[0].form == "inline"


def test_fences_and_items_inside_html_comments_are_ignored() -> None:
    text = f"<!--\n{art('ART-001')}\n{mermaid(CONTAINER)}-->\n" + art("ART-002") + "\n" + mermaid(CONTAINER)
    found = scan(text, "technical")
    assert [a.id for a in found.artifacts] == ["ART-002"] and codes(found) == []


def test_a_file_form_record_is_an_attachment() -> None:
    record = {"file": "assets/a.png", "sha256": "sha256:" + "0" * 64, "kind": "wireframe"}
    found = scan(art("ART-001", traces="FR-001") + "\n" + record_block("artifact", record), "functional")
    assert codes(found) == []
    (artifact,) = found.artifacts
    assert (artifact.form, artifact.kind) == ("file", "wireframe")
    assert artifact.record == record


def test_a_record_block_with_no_art_line_is_unregistered() -> None:
    found = scan(record_block("artifact", {"file": "assets/a.png", "kind": "wireframe"}), "functional")
    assert codes(found) == ["artifact-unregistered"]


def test_other_record_kinds_are_not_attachments() -> None:
    text = art("ART-001") + "\n" + record_block("challenge", {"id": "CH-001"}) + "\n" + mermaid(CONTAINER)
    assert codes(scan(text, "technical")) == []


# ---- kind derivation


@pytest.mark.parametrize(
    ("stage", "diagram", "kind"),
    [
        ("requirements", CONTEXT, "c4-context"),
        ("technical", CONTAINER, "c4-container"),
        ("technical", COMPONENT, "c4-component"),
        ("functional", SEQUENCE, "sequence"),
        ("technical", SEQUENCE, "sequence"),
        ("technical", ER, "er"),
    ],
)
def test_the_kind_comes_from_the_fences_first_keyword(stage: str, diagram: str, kind: str) -> None:
    found = scan(art("ART-001") + "\n" + mermaid(diagram), stage)
    assert [a.kind for a in found.artifacts] == [kind]
    assert codes(found) == []


def test_an_unsupported_diagram_keyword_is_unparseable_and_has_no_kind() -> None:
    found = scan(art("ART-001") + "\n" + mermaid("flowchart TD\n  A --> B"), "technical")
    assert codes(found) == ["diagram-unparseable"]
    assert found.artifacts[0].kind is None  # level cannot be judged for what cannot be read


def test_diagram_findings_carry_the_document_line() -> None:
    text = art("ART-001") + "\n" + mermaid('C4Container\n  Person(a, "A")\n  Bogus(x)')
    found = scan(text, "technical")
    assert [(f.code, f.where) for f in found.findings] == [("diagram-unparseable", "doc.md:6")]


def test_the_attachment_is_part_of_the_items_hash() -> None:
    def hash_of(diagram: str) -> str:
        found = scan(art("ART-001") + "\n" + mermaid(diagram), "technical")
        return item_hash(found.artifacts[0].item)

    assert hash_of(CONTAINER) == hash_of(CONTAINER)
    assert hash_of(CONTAINER) != hash_of(CONTAINER.replace("Uses", "Calls"))


def test_er_artifacts_keep_their_store_clause() -> None:
    found = scan(art("ART-009", extra=" (store: Customer DB)") + "\n" + mermaid(ER), "technical")
    assert found.artifacts[0].store == "Customer DB"


# ---- level (FR-081, determinism 14)


@pytest.mark.parametrize(
    ("stage", "diagram"),
    [
        ("requirements", CONTAINER),
        ("requirements", SEQUENCE),
        ("requirements", ER),
        ("functional", ER),
        ("functional", CONTAINER),
        ("functional", CONTEXT),
        ("technical", CONTEXT),
    ],
)
def test_a_kind_in_a_stage_that_does_not_permit_it_is_wrong_level(stage: str, diagram: str) -> None:
    found = scan(art("ART-001") + "\n" + mermaid(diagram), stage)
    assert codes(found) == ["artifact-wrong-level"]
    assert found.findings[0].where == "ART-001"


def test_a_wireframe_in_requirements_or_technical_is_wrong_level() -> None:
    record = record_block("artifact", {"file": "assets/a.png", "kind": "wireframe"})
    for stage in ("requirements", "technical"):
        assert codes(scan(art("ART-001") + "\n" + record, stage)) == ["artifact-wrong-level"]


@pytest.mark.parametrize("stage", ["ai-spec", "plan", "tasks", "verification", "completion"])
def test_later_stages_define_no_artifacts(stage: str) -> None:
    found = scan(art("ART-001") + "\n" + mermaid(CONTAINER), stage)
    assert codes(found) == ["artifact-wrong-level"]


def test_the_permitted_table_matches_the_data_model() -> None:
    assert PERMITTED_KINDS == {
        "requirements": {"c4-context", "image"},
        "functional": {"sequence", "wireframe", "image"},
        "technical": {"c4-container", "c4-component", "sequence", "er", "image"},
    }


def test_an_image_is_permitted_where_what_it_depicts_is_permitted() -> None:
    def image(depicts: str | None) -> str:
        body = {"file": "assets/a.png", "kind": "image", **({"depicts": depicts} if depicts else {})}
        return art("ART-001") + "\n" + record_block("artifact", body)

    assert codes(scan(image("c4-container"), "technical")) == []
    assert codes(scan(image("c4-context"), "requirements")) == []
    assert codes(scan(image("sequence"), "functional")) == []
    assert codes(scan(image("c4-container"), "requirements")) == ["artifact-wrong-level"]
    assert codes(scan(image(None), "technical")) == ["artifact-wrong-level"]


def test_an_image_is_recorded_as_not_structurally_checked() -> None:
    body = {"file": "assets/a.png", "kind": "image", "depicts": "c4-container"}
    found = scan(art("ART-001") + "\n" + record_block("artifact", body), "technical")
    assert found.artifacts[0].checked is False
    inline = scan(art("ART-001") + "\n" + mermaid(CONTAINER), "technical")
    assert inline.artifacts[0].checked is True


# ---- traces (FR-071)


def test_an_art_line_with_no_traces_is_untraced() -> None:
    found = scan(art("ART-001", traces="") + "\n" + mermaid(CONTAINER), "technical")
    assert [(f.code, f.where) for f in found.findings] == [("artifact-untraced", "ART-001")]


def test_findings_come_in_document_order_of_the_artifact() -> None:
    text = art("ART-002", traces="") + "\n" + mermaid(CONTAINER) + "\n" + art("ART-001") + "\n" + mermaid(ER)
    found = scan(text, "requirements")
    assert [f.where for f in found.findings] == ["ART-002", "ART-002", "ART-001"]
