from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from tests.helpers import scratch
from tests.helpers.package import functional_doc, requirements_doc
from tests.scenario.conftest import write_judgments

FEATURE = Path("specs/001-duplicate-customer")
HELPER = Path(".specify/extensions/eil/scripts/python/eil")


def eil(project: Path, *args: str) -> dict[str, object]:
    proc = subprocess.run(
        ["python3", str(HELPER), *args, "--json"],
        cwd=project,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise AssertionError(f"eil {' '.join(args)} failed\n{proc.stdout}\n{proc.stderr}")
    return json.loads(proc.stdout)


@pytest.fixture(scope="session")
def agent_installed_template(tmp_path_factory: pytest.TempPathFactory) -> Path:
    scratch.require_specify()
    root = tmp_path_factory.mktemp("agent-installed") / "project"
    scratch.make_scratch_project(root)
    scratch.install_extension(root)
    scratch.install_preset(root)
    scratch.git(root, "add", "-A")
    scratch.git(root, "commit", "-q", "-m", "installed")
    return root


@pytest.fixture
def approval_gate_project(agent_installed_template: Path, tmp_path: Path) -> Path:
    project = tmp_path / "project"
    shutil.copytree(agent_installed_template, project, symlinks=True)
    eil(
        project,
        "start",
        "--title",
        "Detect duplicate customers on import",
        "--owner",
        "Test Developer",
        "--feature-dir",
        FEATURE.as_posix(),
    )
    requirements = project / FEATURE / "s01-requirements.md"
    requirements.write_text(requirements_doc(), encoding="utf-8", newline="\n")
    judgments = write_judgments(project, "requirements", ["REQ-G01", "REQ-G11", "REQ-G12", "REQ-G13"])
    checked = eil(project, "check", "--stage", "requirements", "--judgments", str(judgments))
    assert checked["ok"] is True
    scratch.git(project, "add", "-A")
    scratch.git(project, "commit", "-q", "-m", "awaiting requirements approval")
    return project


def _approved_requirements(project: Path) -> Path:
    eil(
        project,
        "start",
        "--title",
        "Detect duplicate customers on import",
        "--owner",
        "Test Developer",
        "--feature-dir",
        FEATURE.as_posix(),
    )
    story = project / FEATURE
    (story / "s01-requirements.md").write_text(requirements_doc(), encoding="utf-8", newline="\n")
    judgments = write_judgments(project, "requirements", ["REQ-G01", "REQ-G11", "REQ-G12", "REQ-G13"])
    assert eil(project, "check", "--stage", "requirements", "--judgments", str(judgments))["ok"] is True
    eil(
        project,
        "approve",
        "requirements",
        "--by",
        "Test Developer",
        "--attestation",
        "Yes, this is the problem we intend to solve.",
    )
    return story


@pytest.fixture
def stale_approval_project(agent_installed_template: Path, tmp_path: Path) -> Path:
    project = tmp_path / "project"
    shutil.copytree(agent_installed_template, project, symlinks=True)
    story = _approved_requirements(project)
    requirements = story / "s01-requirements.md"
    requirements.write_text(
        requirements.read_text(encoding="utf-8").replace(
            "Detection on import.", "Detection on import and manual customer creation."
        ),
        encoding="utf-8",
        newline="\n",
    )
    assert eil(project, "status")["stages"]["requirements"]["state"] == "needs-re-review"
    scratch.git(project, "add", "-A")
    scratch.git(project, "commit", "-q", "-m", "requirements changed after approval")
    return project


@pytest.fixture
def challenged_requirements_project(agent_installed_template: Path, tmp_path: Path) -> Path:
    project = tmp_path / "project"
    shutil.copytree(agent_installed_template, project, symlinks=True)
    eil(
        project,
        "start",
        "--title",
        "Detect duplicate customers on import",
        "--owner",
        "Test Developer",
        "--feature-dir",
        FEATURE.as_posix(),
    )
    story = project / FEATURE
    (story / "s01-requirements.md").write_text(requirements_doc(), encoding="utf-8", newline="\n")
    judgments = write_judgments(project, "requirements", ["REQ-G01", "REQ-G11", "REQ-G12", "REQ-G13"])
    eil(project, "check", "--stage", "requirements", "--judgments", str(judgments))
    eil(
        project,
        "challenge",
        "add",
        "requirements",
        "--target",
        "REQ-001",
        "--text",
        "The matching threshold is undefined.",
        "--by",
        "ai",
        "--severity",
        "high",
    )
    scratch.git(project, "add", "-A")
    scratch.git(project, "commit", "-q", "-m", "awaiting challenge answer")
    return project


@pytest.fixture
def comprehension_gate_project(agent_installed_template: Path, tmp_path: Path) -> Path:
    project = tmp_path / "project"
    shutil.copytree(agent_installed_template, project, symlinks=True)
    story = _approved_requirements(project)
    eil(project, "stage-init", "functional")
    (story / "s02-functional-spec.md").write_text(
        functional_doc(wireframe=None, not_applicable="- Wireframes: batch import, no user interface"),
        encoding="utf-8",
        newline="\n",
    )
    functional_judgments = write_judgments(project, "functional", ["FUN-G10", "FUN-G12", "FUN-G13"])
    checked = eil(project, "check", "--stage", "functional", "--judgments", str(functional_judgments))
    assert checked["ok"] is False
    assert any(row["id"] == "FUN-G16" and row["status"] == "not-met" for row in checked["criteria"])
    scratch.git(project, "add", "-A")
    scratch.git(project, "commit", "-q", "-m", "awaiting developer comprehension")
    return project


@pytest.fixture
def happy_path_project(agent_installed_template: Path, tmp_path: Path) -> Path:
    project = tmp_path / "project"
    shutil.copytree(agent_installed_template, project, symlinks=True)
    source = project / "src"
    source.mkdir(exist_ok=True)
    (source / "customer_import.py").write_text(
        """\
def duplicate_index(existing_emails: list[str], candidate_email: str) -> int | None:
    \"\"\"Return the first matching customer index, or ``None`` when no duplicate exists.\"\"\"
    raise NotImplementedError
""",
        encoding="utf-8",
    )
    tests = project / "tests"
    tests.mkdir(exist_ok=True)
    (tests / "test_customer_import.py").write_text(
        """\
import unittest

from src.customer_import import duplicate_index


class DuplicateIndexTests(unittest.TestCase):
    def test_matches_after_trimming_and_case_folding(self) -> None:
        self.assertEqual(duplicate_index(["first@example.com", " Ada@Example.COM "], "ada@example.com"), 1)

    def test_returns_none_when_there_is_no_match(self) -> None:
        self.assertIsNone(duplicate_index(["first@example.com"], "other@example.com"))

    def test_rejects_a_blank_candidate(self) -> None:
        with self.assertRaises(ValueError):
            duplicate_index(["first@example.com"], "  ")


if __name__ == "__main__":
    unittest.main()
""",
        encoding="utf-8",
    )
    scratch.git(project, "add", "-A")
    scratch.git(project, "commit", "-q", "-m", "happy path fixture")
    return project
