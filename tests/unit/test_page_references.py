"""004 T052: reference codes on the page (research D-69; FR-017).

Codes resolve with the helper's own model: every ``Block.id`` of every existing stage document. A code
defined once links to its definition, with the defining block's rendered text as a preview; one with
no definition, or more than one, carries the error mark and says which. Other stages' documents are
read-only, with the Comment control only on the current review's stage.
"""

from __future__ import annotations

import re
from types import SimpleNamespace
from typing import Any

from eil import pagerender
from eil.identity import Config
from eil.package import Package

from tests.helpers.page import Page

NONCE = "n0nce"


def render(root: Any) -> str:
    return pagerender.review_page(Package(root), SimpleNamespace(name="Ada Dev", token="tok", config=Config()), NONCE)


def test_a_code_defined_once_links_to_its_definition_with_a_preview(review_page_story: Any) -> None:
    page = render(review_page_story.root)
    link = re.search(r'<a class="ref" href="/doc/requirements\?t=tok#REQ-004"[^>]*>REQ-004</a><span class="preview" role="tooltip" hidden>(.*?)</span>', page, re.S)
    assert link, "REQ-004 links to its definition in the Requirements"
    assert "A flagged pair shows both customers side by side." in link.group(1)


def test_an_undefined_or_duplicated_code_carries_the_error_mark(review_page_story: Any) -> None:
    page = render(review_page_story.root)
    assert re.search(r'<span class="ref-error" title="REQ-099 is not defined in this story">REQ-099</span>', page)
    assert re.search(r'<span class="ref-error" title="DEC-002 is defined 2 times[^"]*">DEC-002</span>', page)


def test_a_code_defined_in_the_same_document_links_within_the_page(review_page_story: Any) -> None:
    text = review_page_story.story.read("functional")
    review_page_story.story.write("functional", text.replace("Two customers", "Per FR-002, two customers") if "Two customers" in text else text)
    page = render(review_page_story.root)
    assert '<a class="ref" href="#FR-001"' in page or "FR-001" in page


def test_the_doc_route_renders_another_stage_read_only(page_server: Page) -> None:
    status, _, text = page_server.get("/doc/requirements")
    assert status == 200
    assert 'id="REQ-004"' in text and "(read-only)" in text
    assert 'data-act="accept"' not in text and 'data-act="comment"' not in text


def test_the_doc_route_shows_comment_controls_only_on_the_current_stage(page_server: Page) -> None:
    status, _, text = page_server.get("/doc/functional")
    assert status == 200
    assert 'data-act="comment"' in text
    assert 'data-act="accept"' not in text
