"""004 T020: ``eil review serve``, ``--status`` and ``--stop`` (research D-66; determinism 68).

The page runs in the foreground of its own process and prints one JSON line with its address. A
runtime file outside the project lets the agent find it again after a compaction. Starting, checking
and stopping change no file of the project.
"""

from __future__ import annotations

import json
import os
import socket
import stat
import subprocess
import sys
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from tests.conftest import HELPER_DIR, files_snapshot
from tests.fixtures import review_page
from tests.helpers.page import call


@pytest.fixture
def runtime_dir(tmp_path: Path) -> Path:
    found = tmp_path / "runtime"
    found.mkdir()
    return found


@pytest.fixture
def built(tmp_path: Path) -> Any:
    return review_page.build(tmp_path / "project" / "specs" / "001-story")


def env(runtime_dir: Path) -> dict[str, str]:
    return {**os.environ, "TMPDIR": str(runtime_dir), "TEMP": str(runtime_dir), "TMP": str(runtime_dir)}


def eil(root: Path, runtime_dir: Path, *argv: str) -> tuple[int, Any]:
    proc = subprocess.run(
        [sys.executable, str(HELPER_DIR), *argv, "--json", "--feature-dir", str(root)],
        capture_output=True, text=True, cwd=root, env=env(runtime_dir), check=False, timeout=30,
    )  # fmt: skip
    return proc.returncode, json.loads(proc.stdout) if proc.stdout.strip() else proc.stderr


@pytest.fixture
def serve(built: Any, runtime_dir: Path) -> Iterator[Any]:
    started: list[subprocess.Popen[str]] = []

    def start(*argv: str) -> tuple[subprocess.Popen[str], Any]:
        proc = subprocess.Popen(
            [sys.executable, str(HELPER_DIR), "review", "serve", *argv, "--json", "--feature-dir", str(built.root)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=built.root, env=env(runtime_dir),
        )  # fmt: skip
        started.append(proc)
        line = proc.stdout.readline() if proc.stdout else ""
        return proc, json.loads(line) if line.strip() else None

    yield start
    for proc in started:
        if proc.poll() is None:
            proc.terminate()
            proc.wait(timeout=10)


def runtime_files(runtime_dir: Path) -> list[Path]:
    return sorted(runtime_dir.glob("eil-review-*.json"))


def test_serve_prints_its_address_on_loopback_from_8100(serve: Any, built: Any, runtime_dir: Path) -> None:
    proc, line = serve("--by", "Ada Dev")
    assert line is not None, proc.stderr.read() if proc.stderr else ""
    assert set(line) >= {"story", "address", "pid"} and line["story"] == "001-story" and line["pid"] == proc.pid
    assert line["address"].startswith("http://127.0.0.1:")
    port = int(line["address"].split(":")[2].split("/")[0])
    assert port >= 8100
    assert "?t=" in line["address"] and len(line["address"].split("?t=")[1]) >= 40
    status, _, text = call("GET", line["address"])
    assert status == 200 and "Functional Specification" in text


def test_status_and_stop(serve: Any, built: Any, runtime_dir: Path) -> None:
    before = files_snapshot(built.root.parents[1])
    proc, line = serve("--by", "Ada Dev")
    (runtime,) = runtime_files(runtime_dir)
    assert runtime.parent == runtime_dir
    if os.name == "posix":
        assert stat.S_IMODE(runtime.stat().st_mode) == 0o600
    code, status = eil(built.root, runtime_dir, "review", "serve", "--status")
    assert code == 0 and status["running"] is True and status["address"] == line["address"] and status["pid"] == proc.pid
    assert status["started_at"]
    code, stopped = eil(built.root, runtime_dir, "review", "serve", "--stop")
    assert code == 0 and stopped["stopped"] is True
    proc.wait(timeout=10)
    assert runtime_files(runtime_dir) == []
    code, status = eil(built.root, runtime_dir, "review", "serve", "--status")
    assert code == 0 and status["running"] is False
    assert files_snapshot(built.root.parents[1]) == before, "determinism 68: no project file changes"


def test_status_removes_a_runtime_file_whose_process_is_gone(serve: Any, built: Any, runtime_dir: Path) -> None:
    proc, _ = serve("--by", "Ada Dev")
    proc.kill()
    proc.wait(timeout=10)
    assert len(runtime_files(runtime_dir)) == 1
    code, status = eil(built.root, runtime_dir, "review", "serve", "--status")
    assert code == 0 and status["running"] is False
    assert runtime_files(runtime_dir) == []


def test_stop_never_signals_a_live_pid_without_verifying_the_page(
    built: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from eil import reviewpage
    from eil.package import Package

    runtime = tmp_path / "forged-runtime.json"
    runtime.write_text(
        json.dumps(
            {
                "story": "001-story",
                "address": "http://127.0.0.1:1/?t=not-a-running-page",
                "pid": os.getpid(),
                "started_at": "2025-01-01T00:00:00Z",
            }
        )
    )
    monkeypatch.setattr(reviewpage, "runtime_path", lambda package: runtime)
    signals: list[tuple[int, int]] = []
    monkeypatch.setattr(os, "kill", lambda pid, sig: signals.append((pid, sig)))

    result = reviewpage.stop(Package(built.root), wait=0)

    assert result["stopped"] is False
    assert signals == []
    assert not runtime.exists()


def test_a_second_start_is_refused_page_running(serve: Any, built: Any, runtime_dir: Path) -> None:
    _, line = serve("--by", "Ada Dev")
    proc, second = serve("--by", "Ada Dev")
    proc.wait(timeout=10)
    assert proc.returncode == 1
    refusal = json.loads(second if isinstance(second, str) else json.dumps(second))["refusals"][0]
    assert refusal["code"] == "page-running" and line["address"] in refusal["message"] + refusal.get("fix", "")


@pytest.mark.parametrize("name", ["Claude", "AI", "assistant"])
def test_serve_refuses_the_ai_as_the_person(serve: Any, name: str) -> None:
    proc, payload = serve("--by", name)
    proc.wait(timeout=10)
    assert proc.returncode == 1 and payload["refusals"][0]["code"] == "ai-approval"


def test_serve_refuses_a_port_in_use(serve: Any) -> None:
    with socket.socket() as busy:
        busy.bind(("127.0.0.1", 0))
        busy.listen()
        proc, payload = serve("--by", "Ada Dev", "--port", str(busy.getsockname()[1]))
        proc.wait(timeout=10)
    assert proc.returncode == 1 and payload["refusals"][0]["code"] == "port-unavailable"


def test_serve_refuses_an_ambiguous_story(two_stories: Any, runtime_dir: Path) -> None:
    project = two_stories.project
    proc = subprocess.run(
        [sys.executable, str(HELPER_DIR), "review", "serve", "--by", "Ada Dev", "--json"],
        capture_output=True, text=True, cwd=project, env=env(runtime_dir), check=False, timeout=30,
    )  # fmt: skip
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert json.loads(proc.stdout)["refusals"][0]["code"] == "ambiguous-story"
    assert runtime_files(runtime_dir) == []


def test_stop_with_nothing_running_says_so(built: Any, runtime_dir: Path) -> None:
    code, payload = eil(built.root, runtime_dir, "review", "serve", "--stop")
    assert code == 0 and payload["stopped"] is False


def test_the_runtime_file_names_the_project_and_story(serve: Any, built: Any, runtime_dir: Path) -> None:
    import hashlib

    serve("--by", "Ada Dev")
    (runtime,) = runtime_files(runtime_dir)
    digest = hashlib.sha256(str(built.root.parents[1].resolve()).encode("utf-8")).hexdigest()[:12]
    assert runtime.name == f"eil-review-{digest}-001-story.json"
    data = json.loads(runtime.read_text())
    assert set(data) == {"story", "address", "pid", "started_at"}


def test_an_idle_page_stops_and_removes_its_runtime_file(serve: Any, runtime_dir: Path) -> None:
    proc, line = serve("--by", "Ada Dev", "--idle-minutes", "1")
    assert line is not None
    proc.terminate()
    proc.wait(timeout=10)
    deadline = time.monotonic() + 5
    while runtime_files(runtime_dir) and time.monotonic() < deadline:
        time.sleep(0.05)
    assert runtime_files(runtime_dir) == [], "a clean stop removes the runtime file"
