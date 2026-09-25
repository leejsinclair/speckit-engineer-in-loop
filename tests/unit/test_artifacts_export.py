"""Exports: ``artifact register``, hashing, provenance and path confinement (task T059;
FR-047, FR-076 to FR-078, determinism 12, 13, 15)."""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

import pytest
from eil.artifacts import list_artifacts, orphan_findings, register
from eil.blocks import Doc
from eil.gates import check_stage
from eil.package import Package
from eil.results import EilExit

from tests.helpers.package import (
    ASSETS_FIXTURES,
    FIGMA_URL,
    Story,
    export_record,
    functional_doc,
    mermaid,
    requirements_doc,
    write_export,
)

TODAY = "2026-09-25"


def screen_story(story: Story) -> Path:
    """Requirements plus a Functional document that lists one screen but has no export yet, and a
    sample export sitting inside the story directory."""
    story.write("requirements", requirements_doc())
    text = functional_doc(wireframe=None).replace(
        "## Wireframes\n", "## Wireframes\n\n**ART-003**: Duplicate review screen (traces: FR-001, UC-001)\n"
    )
    story.write("functional", text)
    source = story.root / "exports" / "screen.png"
    source.parent.mkdir()
    shutil.copy(ASSETS_FIXTURES / "wireframe.png", source)
    return source


def do_register(story: Story, source: Path | str, **kw: object) -> dict:
    args: dict = {
        "art_id": "ART-003",
        "kind": "wireframe",
        "source_tool": "figma",
        "source_url": FIGMA_URL,
        "exported_on": TODAY,
        "exported_by": "Ada Dev",
        "cwd": story.root,
    }
    args.update(kw)
    return register(Package(story.root), file=str(source), **args)


def refusal_codes(exc: pytest.ExceptionInfo[EilExit]) -> list[str]:
    return [r["code"] for r in exc.value.payload["refusals"]]


def snapshot(root: Path) -> dict[str, bytes]:
    return {str(p.relative_to(root)): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


# ---- registering


def test_register_copies_hashes_and_writes_the_record_under_the_item(story_dir: Story) -> None:
    source = screen_story(story_dir)
    assert not (story_dir.root / "assets").exists()  # FR-047: not before the first export
    result = do_register(story_dir, source)
    copied = story_dir.root / "assets" / "screen.png"
    assert copied.read_bytes() == source.read_bytes() and source.exists()  # copied, not moved
    expected = "sha256:" + hashlib.sha256(source.read_bytes()).hexdigest()
    doc = Package(story_dir.root).doc("functional")
    (record,) = [r for r in doc.records() if r.kind == "artifact"]
    assert record.obj == {
        "file": "assets/screen.png",
        "sha256": expected,
        "kind": "wireframe",
        "source": {"tool": "figma", "url": FIGMA_URL, "exported_at": TODAY, "exported_by": "Ada Dev"},
    }
    assert result["ok"] is True and result["id"] == "ART-003" and result["sha256"] == expected
    text = story_dir.read("functional")
    assert text.index("**ART-003**") < text.index("```eil:artifact")


def test_a_registered_export_passes_the_gate_criterion(story_dir: Story) -> None:
    source = screen_story(story_dir)
    do_register(story_dir, source)
    result = check_stage(Package(story_dir.root), "functional")
    assert next(c for c in result.criteria if c.id == "FUN-G15").status == "met"


def test_a_file_already_in_assets_is_recorded_without_copying(story_dir: Story) -> None:
    screen_story(story_dir)
    write_export(story_dir.root, "screen.png")
    before = (story_dir.root / "assets" / "screen.png").read_bytes()
    do_register(story_dir, story_dir.root / "assets" / "screen.png")
    assert (story_dir.root / "assets" / "screen.png").read_bytes() == before
    assert sorted(p.name for p in (story_dir.root / "assets").iterdir()) == ["screen.png"]


def test_a_relative_file_path_is_taken_from_the_working_directory(story_dir: Story) -> None:
    screen_story(story_dir)
    do_register(story_dir, "exports/screen.png")
    assert (story_dir.root / "assets" / "screen.png").is_file()


def test_registering_twice_with_identical_inputs_is_byte_identical(story_dir: Story) -> None:
    source = screen_story(story_dir)
    do_register(story_dir, source)
    first = snapshot(story_dir.root)
    do_register(story_dir, source)
    assert snapshot(story_dir.root) == first


def test_defaults_for_the_date_and_person_are_kept_on_re_registration(story_dir: Story) -> None:
    source = screen_story(story_dir)
    do_register(story_dir, source)
    first = snapshot(story_dir.root)
    do_register(story_dir, source, exported_on=None, exported_by=None)
    assert snapshot(story_dir.root) == first


def test_registering_a_changed_file_changes_the_record_and_the_documents_fingerprint(
    story_dir: Story,
) -> None:
    source = screen_story(story_dir)
    do_register(story_dir, source)
    package = Package(story_dir.root)
    before = package.fingerprint("functional")
    source.write_bytes(source.read_bytes() + b"more")
    do_register(story_dir, source)
    assert package.fingerprint("functional") != before
    (record,) = [r for r in package.doc("functional").records() if r.kind == "artifact"]
    assert record.obj["sha256"] == "sha256:" + hashlib.sha256(source.read_bytes()).hexdigest()
    assert (
        story_dir.root / "assets" / "screen.png"
    ).read_bytes() == source.read_bytes()  # the file is replaced too


def test_a_new_export_for_an_approved_stage_needs_re_review(story_dir: Story) -> None:
    from tests.helpers.package import region

    source = screen_story(story_dir)
    do_register(story_dir, source)
    package = Package(story_dir.root)
    approval = {
        "stage": "functional",
        "by": "A",
        "at": "t",
        "fingerprint": package.fingerprint("functional"),
        "upstream": {},
    }
    story_dir.write(
        "functional",
        story_dir.read("functional").replace(
            "<!-- eil:begin approval -->\n<!-- eil:end approval -->",
            region("approval", approval).rstrip("\n"),
        ),
    )
    assert package.state("functional").state == "approved"
    source.write_bytes(source.read_bytes() + b"x")
    do_register(story_dir, source)
    assert package.state("functional").state == "needs-re-review"


def test_registration_touches_only_the_document_and_the_assets_directory(story_dir: Story) -> None:
    source = screen_story(story_dir)
    before = snapshot(story_dir.root)
    do_register(story_dir, source)
    changed = {k for k, v in snapshot(story_dir.root).items() if before.get(k) != v}
    assert changed == {"s02-functional-spec.md", "assets/screen.png"}


# ---- refusals write nothing


def refused(story: Story, source: Path | str, **kw: object) -> list[str]:
    before = snapshot(story.root)
    with pytest.raises(EilExit) as exc:
        do_register(story, source, **kw)
    assert exc.value.code == 1
    assert snapshot(story.root) == before
    assert not (story.root / "assets").exists()
    return refusal_codes(exc)


def test_an_unknown_art_item_is_refused(story_dir: Story) -> None:
    source = screen_story(story_dir)
    assert refused(story_dir, source, art_id="ART-099") == ["unknown-item"]
    assert refused(story_dir, source, art_id="nonsense") == ["unknown-item"]


def test_an_unreadable_source_file_is_refused(story_dir: Story) -> None:
    screen_story(story_dir)
    assert refused(story_dir, story_dir.root / "exports" / "missing.png") == ["artifact-missing"]
    assert refused(story_dir, story_dir.root / "exports") == ["artifact-missing"]  # a directory


def test_a_format_outside_the_allowed_set_is_refused(story_dir: Story) -> None:
    screen_story(story_dir)
    gif = story_dir.root / "exports" / "screen.gif"
    shutil.copy(ASSETS_FIXTURES / "wireframe.gif", gif)
    assert refused(story_dir, gif) == ["artifact-format-not-allowed"]


@pytest.mark.parametrize(
    "kw",
    [
        {"source_url": "https://www.figma.com/design/AbC/Name"},
        {"source_url": "https://www.figma.com/design/AbC/Name?node-id="},
        {"source_url": ""},
        {"source_tool": "FIGMA", "source_url": "https://www.figma.com/design/AbC/Name?page=2"},
        {"source_tool": ""},
    ],
)
def test_missing_or_incomplete_provenance_is_refused(story_dir: Story, kw: dict) -> None:
    source = screen_story(story_dir)
    assert refused(story_dir, source, **kw) == ["artifact-no-provenance"]


def test_a_figma_frame_link_may_carry_other_parameters_after_the_node_id(story_dir: Story) -> None:
    source = screen_story(story_dir)
    do_register(story_dir, source, source_url="https://www.figma.com/design/AbC/Name?t=xyz&node-id=1-2&m=dev")
    assert (story_dir.root / "assets" / "screen.png").is_file()


def test_a_non_figma_tool_needs_a_url_but_no_node_id(story_dir: Story) -> None:
    source = screen_story(story_dir)
    do_register(story_dir, source, source_tool="draw.io", source_url="https://example.test/d/1")
    assert (story_dir.root / "assets" / "screen.png").is_file()


def test_a_wireframe_is_wrong_level_outside_functional(story_dir: Story) -> None:
    source = screen_story(story_dir)
    story_dir.write("technical", "# T\n\n**ART-010**: A screen (traces: FR-001)\n")
    assert refused(story_dir, source, art_id="ART-010") == ["artifact-wrong-level"]


def test_an_image_must_depict_a_kind_permitted_in_the_stage(story_dir: Story) -> None:
    source = screen_story(story_dir)
    story_dir.write("technical", "# T\n\n**ART-010**: Containers (traces: FR-001)\n")
    assert refused(story_dir, source, art_id="ART-010", kind="image") == ["artifact-wrong-level"]
    assert refused(story_dir, source, art_id="ART-010", kind="image", depicts="wireframe") == [
        "artifact-wrong-level"
    ]
    do_register(story_dir, source, art_id="ART-010", kind="image", depicts="c4-container")
    (record,) = [r for r in Package(story_dir.root).doc("technical").records() if r.kind == "artifact"]
    assert record.obj["kind"] == "image" and record.obj["depicts"] == "c4-container"


@pytest.mark.parametrize("file", ["../outside.png", "exports/../../outside.png", "/etc/passwd.png"])
def test_a_file_outside_the_package_is_refused(story_dir: Story, tmp_path: Path, file: str) -> None:
    screen_story(story_dir)
    (tmp_path / "outside.png").write_bytes(b"x")
    assert refused(story_dir, file) == ["path-outside-package"]


def test_an_absolute_path_that_is_outside_the_package_is_refused_even_if_it_exists(
    story_dir: Story, tmp_path: Path
) -> None:
    screen_story(story_dir)
    outside = tmp_path / "elsewhere.png"
    outside.write_bytes((ASSETS_FIXTURES / "wireframe.png").read_bytes())
    assert refused(story_dir, outside) == ["path-outside-package"]


def test_a_symlink_that_escapes_the_package_is_refused(story_dir: Story, tmp_path: Path) -> None:
    screen_story(story_dir)
    outside = tmp_path / "target.png"
    outside.write_bytes((ASSETS_FIXTURES / "wireframe.png").read_bytes())
    link = story_dir.root / "exports" / "link.png"
    link.symlink_to(outside)
    assert refused(story_dir, link) == ["path-outside-package"]


def test_an_art_item_that_already_has_a_diagram_is_not_overwritten(story_dir: Story) -> None:
    source = screen_story(story_dir)
    story_dir.write(
        "technical",
        "# T\n\n**ART-010**: Containers (traces: FR-001)\n\n" + mermaid('C4Container\n  Person(a, "A")'),
    )
    assert refused(story_dir, source, art_id="ART-010", kind="image", depicts="c4-container") == [
        "already-exists"
    ]


def test_a_file_name_already_used_by_another_artifact_is_not_overwritten(story_dir: Story) -> None:
    source = screen_story(story_dir)
    do_register(story_dir, source)
    story_dir.write(
        "functional",
        story_dir.read("functional").replace(
            "## Not applicable", "**ART-004**: Another screen (traces: FR-001)\n\n## Not applicable"
        ),
    )
    other = story_dir.root / "exports2" / "screen.png"
    other.parent.mkdir()
    other.write_bytes(source.read_bytes() + b"different")
    before = snapshot(story_dir.root)
    with pytest.raises(EilExit) as exc:
        do_register(story_dir, other, art_id="ART-004")
    assert refusal_codes(exc) == ["already-exists"]
    assert snapshot(story_dir.root) == before


# ---- states, orphans and the list


def test_a_stray_file_in_assets_is_reported_as_an_orphan(story_dir: Story) -> None:
    source = screen_story(story_dir)
    do_register(story_dir, source)
    (story_dir.root / "assets" / "stray.png").write_bytes(b"x")
    found = orphan_findings(Package(story_dir.root))
    assert [(f.code, f.where) for f in found] == [("orphan-asset", "assets/stray.png")]
    assert "orphan-asset" in [f.code for f in check_stage(Package(story_dir.root), "functional").findings]


def test_no_assets_directory_means_no_orphans(story_dir: Story) -> None:
    screen_story(story_dir)
    assert orphan_findings(Package(story_dir.root)) == []


def test_the_list_shows_kind_stage_form_state_and_traces(story_dir: Story) -> None:
    source = screen_story(story_dir)
    do_register(story_dir, source)
    rows = {r["id"]: r for r in list_artifacts(Package(story_dir.root))}
    assert rows["ART-003"] == {
        "id": "ART-003",
        "kind": "wireframe",
        "stage": "functional",
        "form": "file",
        "state": "ok",
        "traces": ["FR-001", "UC-001"],
        "title": "Duplicate review screen",
    }
    assert rows["ART-001"]["form"] == "inline" and rows["ART-001"]["stage"] == "requirements"


def test_the_list_can_be_limited_to_a_stage(story_dir: Story) -> None:
    source = screen_story(story_dir)
    do_register(story_dir, source)
    assert {r["id"] for r in list_artifacts(Package(story_dir.root), stage="functional")} == {
        "ART-002",
        "ART-003",
    }


def test_the_states_of_a_file_form_artifact(story_dir: Story) -> None:
    story_dir.write("requirements", requirements_doc())
    story_dir.write("functional", functional_doc(wireframe=export_record(sha256="sha256:" + "0" * 64)))
    assert {r["id"]: r["state"] for r in list_artifacts(Package(story_dir.root))}["ART-003"] == "missing-file"
    sha = write_export(story_dir.root)
    story_dir.write("functional", functional_doc(wireframe=export_record(sha256=sha)))
    assert {r["id"]: r["state"] for r in list_artifacts(Package(story_dir.root))}["ART-003"] == "ok"
    (story_dir.root / "assets" / "duplicate-review.png").write_bytes(b"changed")
    assert {r["id"]: r["state"] for r in list_artifacts(Package(story_dir.root))}[
        "ART-003"
    ] == "hash-mismatch"


def test_an_image_export_is_recorded_as_not_structurally_checked(story_dir: Story) -> None:
    source = screen_story(story_dir)
    do_register(
        story_dir,
        source,
        kind="image",
        depicts="sequence",
        source_tool="draw.io",
        source_url="https://example.test/d/1",
    )
    doc = Doc(story_dir.read("functional"))
    assert [r.obj["kind"] for r in doc.records() if r.kind == "artifact"] == ["image"]
