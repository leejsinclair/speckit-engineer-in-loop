"""B-41 (004 quickstart; US4): references and diagrams on the page, with and without the opt-in."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from eil.identity import Config

from tests.fixtures import review_page
from tests.helpers.page import start_page

pytestmark = pytest.mark.scenario
URL = "https://cdn.example/m.mjs"


def test_b41_references_and_diagrams(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import tempfile

    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    built = review_page.build(tmp_path / "specs" / "001-story")
    for script in (None, URL):
        page = start_page(built.root, config=Config(diagram_script=script))
        try:
            status, headers, html = page.get("/")
            assert status == 200
            assert re.search(rf'href="/doc/requirements\?t={re.escape(page.token)}#REQ-004"', html)
            assert 'title="REQ-099 is not defined in this story"' in html
            assert 'title="DEC-002 is defined 2 times' in html
            assert '<pre class="mermaid-src">' in html
            policy = headers["Content-Security-Policy"]
            if script is None:
                assert "cdn.example" not in html and "cdn.example" not in policy
            else:
                assert f"Diagrams drawn by {URL}" in html and "https://cdn.example" in policy
            status, _, doc = page.get("/doc/requirements")
            assert status == 200 and 'id="REQ-004"' in doc
        finally:
            page.stop()
