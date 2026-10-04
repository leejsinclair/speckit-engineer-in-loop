"""004 T005: record writes are atomic and serialised (research D-67; determinism 67, CLI half).

``recordfile.save`` replaces the file in one step, so a failure part-way leaves the old file. Every
read-modify-write holds ``eil-record.json.lock``, created exclusively: a second writer waits up to
5 seconds and then refuses ``record-busy``, writing nothing. A lock left by a process that died is
broken after 60 seconds, and the result says so. No lock file outlives a call.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import pytest
from eil import recordfile
from eil.results import EilExit

from tests.conftest import HELPER_DIR
from tests.fixtures import review_page
from tests.helpers.package import install_templates


def lock_path(root: Path) -> Path:
    return root / "eil-record.json.lock"


def leftovers(root: Path) -> list[str]:
    return sorted(p.name for p in root.iterdir() if p.name.endswith((".tmp", ".lock")))


def dead_pid() -> int:
    proc = subprocess.Popen([sys.executable, "-c", "pass"])
    proc.wait()
    return proc.pid


def test_save_replaces_the_file_atomically(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    recordfile.save(tmp_path, {"version": 1, "story": {"profile": {"name": "small"}}, "stages": {}})
    before = recordfile.path(tmp_path).read_bytes()
    replaced: list[tuple[str, str]] = []
    real = os.replace
    monkeypatch.setattr(os, "replace", lambda a, b: (replaced.append((str(a), str(b))), real(a, b))[1])
    recordfile.save(tmp_path, {"version": 1, "story": {}, "stages": {}})
    assert len(replaced) == 1 and replaced[0][1] == str(recordfile.path(tmp_path))
    assert Path(replaced[0][0]).parent == tmp_path
    assert recordfile.path(tmp_path).read_bytes() != before
    assert leftovers(tmp_path) == []


def test_a_failure_mid_write_leaves_the_old_file_and_no_temporary(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    recordfile.save(tmp_path, {"version": 1, "story": {"profile": {"name": "small"}}, "stages": {}})
    before = recordfile.path(tmp_path).read_bytes()

    def boom(*args: Any) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(os, "replace", boom)
    with pytest.raises(OSError):
        recordfile.save(tmp_path, {"version": 1, "story": {}, "stages": {}})
    assert recordfile.path(tmp_path).read_bytes() == before
    assert leftovers(tmp_path) == []


def test_the_lock_is_exclusive_and_removed_after(tmp_path: Path) -> None:
    with recordfile.record_lock(tmp_path) as held:
        assert lock_path(tmp_path).is_file()
        body = json.loads(lock_path(tmp_path).read_text())
        assert body["pid"] == os.getpid() and body["at"]
        assert held.broken is None
    assert not lock_path(tmp_path).exists()


def test_the_lock_is_reentrant_in_one_thread(tmp_path: Path) -> None:
    with recordfile.record_lock(tmp_path), recordfile.record_lock(tmp_path):
        assert lock_path(tmp_path).is_file()
    assert not lock_path(tmp_path).exists()


def test_a_second_holder_waits_then_refuses_record_busy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    lock_path(tmp_path).write_text(json.dumps({"pid": os.getpid(), "at": "2026-10-04T00:00:00Z"}))
    clock = iter(range(0, 1000))
    monkeypatch.setattr(recordfile, "_monotonic", lambda: float(next(clock)))
    naps: list[float] = []
    monkeypatch.setattr(recordfile, "_sleep", naps.append)
    with pytest.raises(EilExit) as caught:
        with recordfile.record_lock(tmp_path):
            raise AssertionError("must not get the lock")
    assert [r["code"] for r in caught.value.payload["refusals"]] == ["record-busy"]
    assert naps, "it waited before refusing"
    assert lock_path(tmp_path).is_file(), "another holder's lock is left alone"


def test_a_second_thread_waits_for_the_first(tmp_path: Path) -> None:
    order: list[str] = []
    entered = threading.Event()

    def first() -> None:
        with recordfile.record_lock(tmp_path):
            entered.set()
            order.append("first in")
            threading.Event().wait(0.3)
            order.append("first out")

    worker = threading.Thread(target=first)
    worker.start()
    entered.wait(5)
    with recordfile.record_lock(tmp_path):
        order.append("second in")
    worker.join()
    assert order == ["first in", "first out", "second in"]
    assert not lock_path(tmp_path).exists()


def test_a_stale_lock_of_a_dead_process_is_broken_and_said(tmp_path: Path) -> None:
    lock_path(tmp_path).write_text(json.dumps({"pid": dead_pid(), "at": "2026-10-04T00:00:00Z"}))
    old = recordfile._now() - 120
    os.utime(lock_path(tmp_path), (old, old))
    with recordfile.record_lock(tmp_path) as held:
        assert held.broken and "stale" in held.broken
    assert not lock_path(tmp_path).exists()


def test_a_young_lock_of_a_dead_process_is_not_broken(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    lock_path(tmp_path).write_text(json.dumps({"pid": dead_pid(), "at": "2026-10-04T00:00:00Z"}))
    clock = iter(range(0, 1000))
    monkeypatch.setattr(recordfile, "_monotonic", lambda: float(next(clock)))
    monkeypatch.setattr(recordfile, "_sleep", lambda s: None)
    with pytest.raises(EilExit):
        with recordfile.record_lock(tmp_path):
            pass


def test_an_old_lock_of_a_live_process_is_not_broken(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    lock_path(tmp_path).write_text(json.dumps({"pid": os.getpid(), "at": "2026-10-04T00:00:00Z"}))
    old = recordfile._now() - 120
    os.utime(lock_path(tmp_path), (old, old))
    clock = iter(range(0, 1000))
    monkeypatch.setattr(recordfile, "_monotonic", lambda: float(next(clock)))
    monkeypatch.setattr(recordfile, "_sleep", lambda s: None)
    with pytest.raises(EilExit):
        with recordfile.record_lock(tmp_path):
            pass


def test_the_lock_is_released_when_the_write_fails(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError), recordfile.record_lock(tmp_path):
        raise RuntimeError("the write failed")
    assert not lock_path(tmp_path).exists()


def test_a_cli_write_refuses_record_busy_and_writes_nothing(tmp_path: Path) -> None:
    built = review_page.build(tmp_path / "specs" / "001-story")
    from tests.conftest import files_snapshot

    lock_path(built.root).write_text(json.dumps({"pid": os.getpid(), "at": "2026-10-04T00:00:00Z"}))
    before = files_snapshot(built.root)
    result = run_answer(built.root, "FR-001")
    assert result.returncode == 1, result.stderr
    assert [r["code"] for r in json.loads(result.stdout)["refusals"]] == ["record-busy"]
    assert files_snapshot(built.root) == before


def run_answer(root: Path, key: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable, str(HELPER_DIR), "review", "answer", "--stage", "functional", "--kind", "inferred",
            "--entry", key, "--by", "Ada Dev", "--reply", "ok", "--feature-dir", str(root), "--json",
        ],
        capture_output=True, text=True, cwd=root, env={**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, **(env or {})},
        check=False,
    )  # fmt: skip


@pytest.mark.slow
def test_determinism_67_cli_half_twenty_concurrent_writers(tmp_path: Path) -> None:
    install_templates(tmp_path)
    built = review_page.build(tmp_path / "specs" / "001-story", entries=38)
    keys = [f"FR-{n:03d}" for n in range(1, 21)]
    with ThreadPoolExecutor(max_workers=20) as pool:
        results = list(pool.map(lambda k: run_answer(built.root, k), keys))
    assert [r.returncode for r in results] == [0] * 20, [r.stdout + r.stderr for r in results if r.returncode]
    data = json.loads(recordfile.path(built.root).read_text())
    (session,) = data["story"]["review_sessions"].values()
    assert sorted(session["answers"]) == keys
    assert not lock_path(built.root).exists()
    assert leftovers(built.root) == []
