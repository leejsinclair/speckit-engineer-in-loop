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


def test_determinism_55_a_stage_document_is_the_only_document_read(page: Page, review_page_story: Any, reads: list[Path]) -> None:
    status, _, _ = page.get("/doc/requirements")
    assert status == 200
    allowed = {review_page_story.root / name for name in ("s01-requirements.md", "s02-functional-spec.md", "eil-record.json", "s00-README.md")}
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
def test_every_response_carries_the_security_headers(page: Page, method: str, path: str, headers: dict[str, str] | None) -> None:
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
    for host, expected in ((f"127.0.0.1:{port}", 200), (f"localhost:{port}", 200), (f"attacker.example:{port}", 403), ("", 403)):
        status, _, _ = page.call("GET", f"/?t={page.token}", headers={"Host": host} if host else {"Host": ""})
        assert status == expected, host


def test_state_needs_the_token_header(page: Page) -> None:
    assert page.get("/state", token=False)[0] == 403
    assert page.call("GET", f"/state?t={page.token}")[0] == 403, "the token is a header on /state"
    assert page.get("/state")[0] == 200


def test_an_oversized_body_is_refused(page: Page, review_page_story: Any) -> None:
    before = files_snapshot(review_page_story.root)
    try:
        status, _, _ = page.call("POST", "/answer", b"{" + b" " * (2 * 1024 * 1024) + b"}", same_origin(page.origin, page.token))
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
