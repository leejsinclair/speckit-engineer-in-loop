"""The release archives install (task T137): ``specify extension add --from`` and ``specify preset add
--from`` with the zip files ``tools/stage.py --archives`` writes, served over local HTTP, give the same
installed project as a staged ``--dev`` install."""

from __future__ import annotations

import functools
import http.server
import subprocess
import threading
import zipfile
from collections.abc import Iterator
from pathlib import Path

import pytest

from tests.helpers import scratch
from tools.stage import make_archives

pytestmark = pytest.mark.contract


@pytest.fixture
def archives(tmp_path: Path) -> tuple[Path, Path]:
    return make_archives(tmp_path / "release")


@pytest.fixture
def server(archives: tuple[Path, Path]) -> Iterator[str]:
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(archives[0].parent))
    handler.log_message = lambda *args, **kwargs: None  # type: ignore[attr-defined]
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{httpd.server_address[1]}"
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_the_archives_hold_only_what_ships(archives: tuple[Path, Path]) -> None:
    extension, preset = (set(zipfile.ZipFile(a).namelist()) for a in archives)
    assert "extension.yml" in extension and "scripts/python/eil/__main__.py" in extension
    assert "preset.yml" in preset and "commands/speckit.plan.md" in preset
    for names in (extension, preset):
        assert not [
            n for n in names if n.startswith((".venv", "specs/", "tests/", ".git")) or "__pycache__" in n
        ]


def test_installing_from_the_archives_gives_a_working_project(
    scratch_project: Path, archives: tuple[Path, Path], server: str
) -> None:
    extension, preset = archives
    scratch.require_specify()
    added = subprocess.run(
        [scratch.SPECIFY, "extension", "add", "eil", "--from", f"{server}/{extension.name}"],
        cwd=scratch_project,
        input="y\n",
        capture_output=True,
        text=True,
        check=False,
    )
    assert added.returncode == 0, added.stdout + added.stderr
    scratch.specify(scratch_project, "preset", "add", "--from", f"{server}/{preset.name}")
    helper = scratch_project / ".specify" / "extensions" / "eil" / "scripts" / "python" / "eil"
    assert (helper / "__main__.py").is_file()
    skills = {p.parent.name for p in (scratch_project / ".claude" / "skills").glob("speckit-eil-*/SKILL.md")}
    assert len(skills) == 27  # 20 commands and 7 numbered aliases
    plan = (scratch_project / ".claude" / "skills" / "speckit-plan" / "SKILL.md").read_text(encoding="utf-8")
    assert "source: preset:engineer-in-the-loop" in plan and "eil enter plan" in plan
    ran = scratch.run(["python3", str(helper), "status", "--json"], scratch_project, check=False)
    assert ran.returncode == 3, "an ungoverned project is left alone"
