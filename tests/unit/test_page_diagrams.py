"""004 T053: diagrams on the page (research D-69; determinism 64; FR-018).

A diagram is shown as source. Only when the project names ``review.diagram_script`` does the page load
that one script, say so under the first diagram, and widen the CSP by exactly that script's origin.
The helper never fetches anything.
"""

from __future__ import annotations

import re
import socket
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from eil import pagerender
from eil.identity import Config, ConfigError
from eil.package import Package

NONCE = "n0nce"
URL = "https://cdn.example/m.mjs"


def render(root: Any, script: str | None = None) -> str:
    config = Config(diagram_script=script)
    return pagerender.review_page(
        Package(root), SimpleNamespace(name="Ada Dev", token="tok", config=config), NONCE
    )


def text_of(html: str) -> str:
    without = re.sub(r"<script\b.*?</script>|<style\b.*?</style>", " ", html, flags=re.S)
    return re.sub(r"<[^>]+>", " ", without)


def test_a_mermaid_fence_is_shown_as_source(review_page_story: Any) -> None:
    page = render(review_page_story.root)
    assert '<pre class="mermaid-src">flowchart LR\n  Import --&gt; Flag --&gt; Review</pre>' in page


def test_determinism_64_without_a_script_nothing_from_elsewhere(review_page_story: Any) -> None:
    page = render(review_page_story.root)
    assert not re.search(r"\b[a-z][a-z0-9+.-]*://", page), "no URL with a scheme"
    assert '<meta name="eil-diagram-script"' not in page and "Diagrams drawn by" not in text_of(page)
    assert (
        pagerender.csp("N", pagerender.script_origin(None)).split("script-src ")[1].split(";")[0]
        == "'self' 'nonce-N'"
    )


def test_determinism_64_with_a_script_the_url_is_named_once_and_the_csp_widens_exactly(
    review_page_story: Any,
) -> None:
    page = render(review_page_story.root, URL)
    assert text_of(page).count(URL) == 1 and f"Diagrams drawn by {URL}" in text_of(page)
    assert page.index("Diagrams drawn by") > page.index('<pre class="mermaid-src">')
    assert f'<meta name="eil-diagram-script" content="{URL}">' in page
    policy = pagerender.csp("N", pagerender.script_origin(URL))
    assert policy.split("script-src ")[1].split(";")[0] == "'self' 'nonce-N' https://cdn.example"
    assert "https://cdn.example" not in policy.split("script-src")[0] + policy.split(";", 2)[2]


def test_the_page_sends_the_widened_policy(tmp_path: Path, review_page_story: Any) -> None:
    from tests.helpers.page import start_page

    page = start_page(review_page_story.root, config=Config(diagram_script=URL))
    try:
        _, headers, _ = page.get("/")
        assert "script-src 'self' 'nonce-" in headers["Content-Security-Policy"]
        assert headers["Content-Security-Policy"].count("https://cdn.example") == 1
    finally:
        page.stop()


@pytest.mark.parametrize(
    "value",
    ["http://cdn.example/m.mjs", "javascript:alert(1)", "cdn.example/m.mjs", "https://", '"https://x/a b"'],
)
def test_a_script_that_is_not_an_https_url_is_refused(tmp_path: Path, value: str) -> None:
    from eil.identity import load_config

    where = tmp_path / ".specify" / "extensions" / "eil"
    where.mkdir(parents=True)
    (where / "eil-config.yml").write_text(f"review:\n  diagram_script: {value}\n")
    with pytest.raises(ConfigError):
        load_config(tmp_path)


def test_an_https_script_is_read(tmp_path: Path) -> None:
    from eil.identity import load_config

    where = tmp_path / ".specify" / "extensions" / "eil"
    where.mkdir(parents=True)
    (where / "eil-config.yml").write_text(f"review:\n  diagram_script: {URL}\n")
    assert load_config(tmp_path).diagram_script == URL
    assert Config().diagram_script is None


def test_the_helper_never_opens_a_connection(review_page_story: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("the helper tried to open a network connection")

    monkeypatch.setattr(socket, "create_connection", refuse)
    monkeypatch.setattr(socket.socket, "connect", refuse)
    assert URL in render(review_page_story.root, URL)
