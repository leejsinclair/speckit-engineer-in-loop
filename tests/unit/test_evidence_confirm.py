"""Evidence the helper can confirm from files alone (determinism requirement 34; FR-034, FR-035)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from eil import evidence


@pytest.fixture(autouse=True)
def no_subprocess(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(*args: object, **kwargs: object) -> None:
        raise AssertionError("evidence confirmation started a process")

    for name in ("run", "Popen", "call", "check_call", "check_output"):
        monkeypatch.setattr(subprocess, name, fail)


@pytest.fixture
def project(tmp_path: Path) -> Path:
    tests = tmp_path / "tests" / "unit"
    tests.mkdir(parents=True)
    (tests / "test_x.py").write_text("def test_y():\n    pass\n\nclass TestZ:\n    def test_w(self): ...\n")
    (tests / "widget.test.ts").write_text(
        "describe('suite', () => {\n  it('flags duplicates', () => {});\n});\n"
    )
    return tmp_path


def test_pytest_node_id_is_confirmed_when_the_file_defines_the_name(project: Path) -> None:
    found = evidence.confirm(project, "tests/unit/test_x.py::test_y")
    assert found.confirmed
    assert "exists; result attested" in found.note


def test_class_and_method_chain_needs_every_part_defined(project: Path) -> None:
    assert evidence.confirm(project, "tests/unit/test_x.py::TestZ::test_w").confirmed
    assert not evidence.confirm(project, "tests/unit/test_x.py::TestZ::test_missing").confirmed


def test_path_plus_name_forms(project: Path) -> None:
    assert evidence.confirm(project, "tests/unit/test_x.py test_y").confirmed
    assert evidence.confirm(project, "test_y in tests/unit/test_x.py").confirmed
    assert evidence.confirm(project, "tests/unit/test_x.py (test_y)").confirmed


def test_missing_name_is_unconfirmed(project: Path) -> None:
    found = evidence.confirm(project, "tests/unit/test_x.py::test_nope")
    assert not found.confirmed
    assert "test_nope" in found.reason


def test_missing_file_is_unconfirmed(project: Path) -> None:
    found = evidence.confirm(project, "tests/unit/test_gone.py::test_y")
    assert not found.confirmed
    assert "test_gone.py" in found.reason


def test_a_path_alone_names_no_test_and_is_unconfirmed(project: Path) -> None:
    assert not evidence.confirm(project, "tests/unit/test_x.py").confirmed


def test_path_outside_the_project_is_unconfirmed(
    project: Path, tmp_path_factory: pytest.TempPathFactory
) -> None:
    outside = tmp_path_factory.mktemp("outside")
    (outside / "test_o.py").write_text("def test_o(): ...\n")
    assert evidence.confirm(project, f"{outside}/test_o.py::test_o").confirmed is False
    assert evidence.confirm(project, "../" + outside.name + "/test_o.py::test_o").confirmed is False
    assert evidence.confirm(project, "tests/../../escape.py::test_o").confirmed is False


def test_a_symlink_out_of_the_project_is_unconfirmed(
    project: Path, tmp_path_factory: pytest.TempPathFactory
) -> None:
    outside = tmp_path_factory.mktemp("outside")
    (outside / "test_o.py").write_text("def test_o(): ...\n")
    (project / "link.py").symlink_to(outside / "test_o.py")
    assert not evidence.confirm(project, "link.py::test_o").confirmed


def test_javascript_style_names_are_found(project: Path) -> None:
    assert evidence.confirm(project, 'tests/unit/widget.test.ts "flags duplicates"').confirmed


def test_free_text_with_no_path_is_unconfirmed(project: Path) -> None:
    assert not evidence.confirm(project, "CI run 4821 was green").confirmed
    assert not evidence.confirm(project, "").confirmed


def test_a_comment_mentioning_the_name_is_not_a_definition(project: Path) -> None:
    (project / "tests" / "unit" / "test_c.py").write_text("# test_ghost is planned\n")
    assert not evidence.confirm(project, "tests/unit/test_c.py::test_ghost").confirmed
