"""004 T008 and T047: the page's request checks (research D-66, D-69; determinism 54, 55, 56 and 67).

Every request checks the Host header and the token; every POST also needs the page's own Origin and a
JSON body. A failed check is ``403`` and writes nothing. Only the routes in the contract are served:
nothing is read from disk but the story's stage documents and its record file. Every response carries
the security headers.
"""

from __future__ import annotations

import json
import pathlib
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from tests.conftest import files_snapshot
from tests.helpers.page import Page, call, same_origin

LOCK = "eil-record.json.lock"
ANSWER = {"stage": "functional", "kind": "inferred", "entry": "FR-001", "disposition": "accept"}


@pytest.fixture
def page(page_server: Page) -> Page:
    return page_server


def attempt(page: Page, headers: dict[str, str], body: Any = ANSWER) -> int:
    status, _, _ = page.call("POST", "/answer", body, headers)
    return status


@pytest.mark.parametrize(
    "change",
    [
        {"X-EIL-Token": None},
        {"X-EIL-Token": "wrong-token"},
        {"Origin": "http://evil.example"},
        {"Origin": None},
        {"Host": "attacker.example"},
        {"Content-Type": "text/plain"},
        {"Content-Type": "application/x-www-form-urlencoded"},
    ],
)
def test_determinism_54_a_forged_answer_is_refused_and_writes_nothing(
    page: Page, review_page_story: Any, change: dict[str, str | None]
) -> None:
    headers = same_origin(page.origin, page.token)
    for key, value in change.items():
        if value is None:
            headers.pop(key, None)
        else:
            headers[key] = value
    before = files_snapshot(review_page_story.root)
    assert attempt(page, headers) == 403
    assert files_snapshot(review_page_story.root) == before
    assert not (review_page_story.root / LOCK).exists()


@pytest.mark.parametrize("method", ["PUT", "DELETE", "PATCH", "OPTIONS", "HEAD", "TRACE"])
def test_any_other_method_is_405(page: Page, method: str) -> None:
    status, headers, _ = page.call(method, f"/?t={page.token}")
    assert status == 405
    assert headers.get("X-Content-Type-Options") == "nosniff"


@pytest.fixture
def reads(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[Path]]:
    seen: list[Path] = []
    real = pathlib.Path.read_bytes

    def spy(self: Path) -> bytes:
        seen.append(Path(self))
        return real(self)

    monkeypatch.setattr(pathlib.Path, "read_bytes", spy)
    yield seen


@pytest.mark.parametrize(
    "path",
    ["/doc/../../etc/passwd", "/doc/..%2F..%2Fetc%2Fpasswd", "/doc/notastage", "/eil-record.json", "/static/x.js",
     "/s02-functional-spec.md", "/doc/functional/../../eil-record.json", "/favicon.ico"],
)  # fmt: skip
def test_determinism_55_no_path_reaches_another_file(page: Page, reads: list[Path], path: str) -> None:
    status, _, text = page.get(path)
    assert status in (403, 404)
    assert "root:" not in text and '"stages"' not in text
    assert reads == [], f"read {reads}"


def test_determinism_55_a_stage_document_is_the_only_document_read(
    page: Page, review_page_story: Any, reads: list[Path]
) -> None:
    status, _, _ = page.get("/doc/requirements")
    assert status == 200
    allowed = {
        review_page_story.root / name
        for name in ("s01-requirements.md", "s02-functional-spec.md", "eil-record.json", "s00-README.md")
    }
    outside = [p for p in reads if p.resolve().parent != review_page_story.root.resolve() or p not in allowed]
    assert outside == [], f"read outside the story's documents: {outside}"


@pytest.mark.parametrize(
    ("method", "path", "headers"),
    [
        ("GET", "/", None),
        ("GET", "/?t=wrong", None),
        ("GET", "/nothing", None),
        ("POST", "/answer", {}),
        ("PUT", "/", None),
    ],
)
def test_every_response_carries_the_security_headers(
    page: Page, method: str, path: str, headers: dict[str, str] | None
) -> None:
    _, got, _ = page.call(method, path, ANSWER if method == "POST" else None, headers)
    assert got.get("X-Content-Type-Options") == "nosniff"
    assert got.get("Referrer-Policy") == "no-referrer"
    assert got.get("Cache-Control") == "no-store"
    assert "default-src 'none'" in got.get("Content-Security-Policy", "")
    assert "frame-ancestors 'none'" in got.get("Content-Security-Policy", "")


def test_a_get_without_the_token_says_to_open_the_address(page: Page, review_page_story: Any) -> None:
    for path in ("/", "/?t=", "/?t=wrong", "/doc/requirements"):
        status, _, text = page.get(path, token=False) if "t=" not in path else page.call("GET", path)
        assert status == 403
        assert "open the address the agent gave" in text.lower()
        assert page.token not in text
        assert "flag duplicate customers" not in text and "Functional Specification" not in text


def test_the_host_check_accepts_loopback_names_only(page: Page) -> None:
    port = page.origin.rsplit(":", 1)[1]
    for host, expected in (
        (f"127.0.0.1:{port}", 200),
        (f"localhost:{port}", 200),
        (f"attacker.example:{port}", 403),
        ("", 403),
    ):
        status, _, _ = page.call("GET", f"/?t={page.token}", headers={"Host": host} if host else {"Host": ""})
        assert status == expected, host


def test_state_needs_the_token_header(page: Page) -> None:
    assert page.get("/state", token=False)[0] == 403
    assert page.call("GET", f"/state?t={page.token}")[0] == 403, "the token is a header on /state"
    assert page.get("/state")[0] == 200


def test_an_oversized_body_is_refused(page: Page, review_page_story: Any) -> None:
    before = files_snapshot(review_page_story.root)
    try:
        status, _, _ = page.call(
            "POST", "/answer", b"{" + b" " * (2 * 1024 * 1024) + b"}", same_origin(page.origin, page.token)
        )
    except OSError:
        status = 413  # the server answered and closed before the client finished sending
    assert status in (400, 413)
    assert files_snapshot(review_page_story.root) == before


def test_a_body_that_is_not_json_is_400(page: Page, review_page_story: Any) -> None:
    before = files_snapshot(review_page_story.root)
    status, _, text = page.call("POST", "/answer", b"not json", same_origin(page.origin, page.token))
    assert status == 400
    assert json.loads(text)["ok"] is False
    assert files_snapshot(review_page_story.root) == before


def test_call_helper_reports_refused_connections() -> None:
    with pytest.raises(OSError):
        call("GET", "http://127.0.0.1:9/")


# ---- T047: stale answers, binding and concurrent writers


def test_determinism_56_page_half_a_stale_answer_is_refused(page: Page, review_page_story: Any) -> None:
    from eil import reviews
    from eil.package import Package

    root = review_page_story.root
    entry = next(
        e for e in reviews.build_list(Package(root), "functional", "inferred").entries if e.key == "FR-001"
    )
    text = review_page_story.story.read("functional")
    review_page_story.story.write(
        "functional",
        text.replace("flag duplicate customers on import.", "flag duplicate customers on each import."),
    )
    before = files_snapshot(root)
    status, payload = page.post("/answer", {**ANSWER, "shown": entry.hash, "question": entry.question})
    assert status == 200 and [r["code"] for r in payload["refusals"]] == ["entry-changed"]
    current = payload["refusals"][0]["current"]
    assert current["key"] == "FR-001" and "each import" in current["what"] and current["hash"] != entry.hash
    assert files_snapshot(root) == before


def test_the_default_bind_is_loopback(review_page_story: Any) -> None:
    from eil import reviewpage

    server = reviewpage.make_server(review_page_story.root, "Ada Dev", port=0)
    try:
        assert server.server_address[0] == "127.0.0.1"
        assert server.address.startswith("http://127.0.0.1:")
        assert server.public_name is None
    finally:
        server.server_close()


def test_a_public_name_is_accepted_only_off_loopback(review_page_story: Any) -> None:
    from tests.helpers.page import start_page

    loopback = start_page(review_page_story.root, public_name="box.local")
    try:
        port = loopback.origin.rsplit(":", 1)[1]
        assert loopback.call("GET", f"/?t={loopback.token}", headers={"Host": f"box.local:{port}"})[0] == 403
    finally:
        loopback.stop()
    everywhere = start_page(review_page_story.root, host="0.0.0.0", public_name="box.local")
    try:
        port = everywhere.origin.rsplit(":", 1)[1]
        assert everywhere.address.startswith("http://box.local:")
        origin = f"http://127.0.0.1:{port}"
        assert call("GET", f"{origin}/?t={everywhere.token}", headers={"Host": f"box.local:{port}"})[0] == 200
        assert (
            call("GET", f"{origin}/?t={everywhere.token}", headers={"Host": f"attacker.example:{port}"})[0]
            == 403
        )
    finally:
        everywhere.stop()


@pytest.mark.slow
def test_determinism_67_page_half_page_and_cli_writers_together(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import os
    import subprocess
    import sys
    import tempfile
    from concurrent.futures import ThreadPoolExecutor

    from eil import recordfile, reviews
    from eil.package import Package

    from tests.conftest import HELPER_DIR
    from tests.fixtures import review_page
    from tests.helpers.page import start_page

    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    built = review_page.build(tmp_path / "specs" / "001-story", entries=38)
    root = built.root
    entries = {e.key: e for e in reviews.build_list(Package(root), "functional", "inferred").entries}
    on_page, in_cli = [f"FR-{n:03d}" for n in range(1, 11)], [f"FR-{n:03d}" for n in range(11, 21)]
    page = start_page(root)

    def by_page(key: str) -> bool:
        _, payload = page.post(
            "/answer", {**ANSWER, "entry": key, "shown": entries[key].hash, "question": entries[key].question}
        )
        return bool(payload.get("ok"))

    def by_cli(key: str) -> bool:
        proc = subprocess.run(
            [sys.executable, str(HELPER_DIR), "review", "answer", "--stage", "functional", "--kind", "inferred", "--entry", key,
             "--by", "Ada Dev", "--reply", "ok", "--feature-dir", str(root), "--json"],
            capture_output=True, text=True, env={**os.environ}, check=False,
        )  # fmt: skip
        return proc.returncode == 0

    try:
        with ThreadPoolExecutor(max_workers=20) as pool:
            done = list(
                pool.map(
                    lambda job: job[0](job[1]),
                    [(by_page, k) for k in on_page] + [(by_cli, k) for k in in_cli],
                )
            )
    finally:
        page.stop()
    assert all(done)
    data = json.loads(recordfile.path(root).read_text())
    (session,) = data["story"]["review_sessions"].values()
    assert sorted(session["answers"]) == sorted(on_page + in_cli)
    assert not (root / LOCK).exists()
