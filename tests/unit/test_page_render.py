"""004 T018 and T064: the review page's HTML (research D-62; determinism 63; contracts/page.md).

The page is the clean view of the current review's document, block by block. Each block carries its
review key and hash; exactly the entries ``review list`` returns carry an answer control with the fixed
question. Everything from a document or a person is escaped, there is no inline event handler, and the
one inline script carries the response's nonce.
"""

from __future__ import annotations

import re
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from eil import pagerender, reviews
from eil.identity import Config
from eil.package import Package

from tests.fixtures import review_page

CONFIG = Config(default_developer="Ada Dev", approvers={"functional": ["Ada Dev"]})
NONCE = "n0nceN0nce"


def ctx(name: str = "Ada Dev", **extra: Any) -> Any:
    return SimpleNamespace(name=name, token="tok-123", config=extra.pop("config", CONFIG), **extra)


def render(root: Path, name: str = "Ada Dev", **extra: Any) -> str:
    return pagerender.review_page(Package(root), ctx(name, **extra), NONCE)


def controls(page: str) -> dict[str, str]:
    """``{entry key: the control's HTML}`` for every answer control on the page."""
    found = {}
    for match in re.finditer(
        r'<div class="control[^"]*" data-entry="([^"]+)"(.*?)</div><!--/control-->', page, re.S
    ):
        found[pagerender.html.unescape(match.group(1))] = match.group(0)
    return found


def footer(page: str) -> str:
    return page[page.index('<footer id="footer">') : page.index("</footer>")]


def text_of(html: str) -> str:
    return " ".join(re.sub(r"<[^>]+>", " ", html).split())


def blocks(page: str) -> dict[str, str]:
    return {
        pagerender.html.unescape(m.group(1)): m.group(2)
        for m in re.finditer(r'<div class="blk[^"]*" data-key="([^"]+)" data-hash="([^"]+)"', page)
    }


def page_answer(
    root: Path, key: str, disposition: str = "accept", comment: str | None = None, by: str = "Ada Dev"
) -> None:
    listed = reviews.build_list(Package(root), "functional", "inferred", session_view=False)
    entry = next(e for e in listed.entries if e.key == key)
    reviews.answer(
        Package(root), CONFIG, "functional", "inferred", digest=None, by=by, reply="", entry=key, disposition=disposition,
        shown=entry.hash, asked=reviews.entry_question("inferred", entry), comment=comment, via="page",
    )  # fmt: skip


def test_every_block_carries_its_key_and_hash(review_page_story: Any) -> None:
    from eil.content import blocks_of

    page = render(review_page_story.root)
    found = blocks(page)
    for block in blocks_of(Package(review_page_story.root).doc("functional")):
        assert found.get(block.key) == block.hash, block.key


def test_exactly_the_listed_entries_carry_controls(review_page_story: Any) -> None:
    page = render(review_page_story.root)
    assert sorted(controls(page)) == sorted(review_page_story.listed())


def test_a_scaffolding_entry_is_answered_on_its_heading(review_page_story: Any) -> None:
    page = render(review_page_story.root)
    heading = page.index('<h2 id="actors">')
    control = page.index('data-entry="§Actors"')
    first_member = page.index('class="blk member')
    assert heading < control < first_member


def test_each_control_shows_its_question_and_three_labelled_buttons(review_page_story: Any) -> None:
    page = render(review_page_story.root)
    for key, html in controls(page).items():
        listed = reviews.build_list(Package(review_page_story.root), "functional", "inferred")
        entry = next(e for e in listed.entries if e.key == key)
        assert pagerender.esc(reviews.entry_question("inferred", entry)) in html
        for label, act in (("Accept", "accept"), ("Send back", "except"), ("Question", "question")):
            assert re.search(
                rf'<button type="button" data-act="{act}" aria-label="{label} {re.escape(pagerender.esc(key))}">{label}</button>',
                html,
            ), (key, label)


def test_each_highlighted_block_says_it_needs_review(review_page_story: Any) -> None:
    page = render(review_page_story.root)
    for key in review_page_story.listed():
        assert f"Needs review: {pagerender.esc(key)}" in page


def test_the_header(review_page_story: Any) -> None:
    page = render(review_page_story.root)
    head = text_of(page[page.index("<header") : page.index("</header>")])
    assert "Duplicate customer analysis" in head
    assert "Functional Specification: blocks that need review" in head
    assert "0 of 5 answered" in head
    assert "Answering as Ada Dev" in head
    assert "<kbd>n</kbd>" in page[page.index("<header") : page.index("</header>")]


def test_the_footer_when_nothing_is_listed(tmp_path: Path) -> None:
    built = review_page.build(tmp_path / "specs" / "001-story")
    for key in built.listed():
        page_answer(built.root, key)
    page = render(built.root)
    assert "Nothing to answer now." in footer(page)
    assert controls(page) == {}


def test_the_footer_when_every_entry_is_answered_in_the_open_session(
    review_page_story: Any, monkeypatch: Any
) -> None:
    root = review_page_story.root
    for key in review_page_story.listed()[:-1]:
        page_answer(root, key)
    page = render(root)
    assert "List complete." not in footer(page)
    listed = reviews.build_list(Package(root), "functional", "inferred")
    assert pagerender.footer_text(listed) == ""
    listed.entries = []
    assert pagerender.footer_text(listed) == "List complete. Return to the chat and say done."


def test_the_token_is_in_a_meta_element(review_page_story: Any) -> None:
    page = render(review_page_story.root)
    assert '<meta name="eil-token" content="tok-123">' in page


def test_stored_answers_show_and_count(review_page_story: Any) -> None:
    root = review_page_story.root
    page_answer(root, "FR-001")
    page_answer(root, "FR-002", "except", comment="Name the pairs.")
    page = render(root)
    assert "2 of 5 answered" in page
    found = controls(page)
    assert "answered" in found["FR-001"].split('"')[1]
    assert "Accepted by Ada Dev" in found["FR-001"] and "Change" in found["FR-001"]
    assert "Sent back by Ada Dev" in found["FR-002"] and "Name the pairs." in found["FR-002"]
    first_open = re.search(r'<div class="control" data-entry="([^"]+)"', page)
    assert first_open is not None
    assert pagerender.html.unescape(first_open.group(1)) == "§Actors", (
        "the first unanswered control in document order"
    )


# ---- determinism 63


def test_determinism_63_everything_from_a_document_or_a_person_is_escaped(review_page_story: Any) -> None:
    root = review_page_story.root
    text = review_page_story.story.read("functional")
    review_page_story.story.write(
        "functional",
        text.replace("dismiss a flagged pair.", "dismiss a flagged pair. <script>alert(1)</script>"),
    )
    page_answer(root, "FR-001", "except", comment="<img src=x onerror=alert(1)>")
    page = render(root, name='"><b>x')
    assert "<script>alert(1)</script>" not in page
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in page
    assert "<img src=x" not in page and "&lt;img src=x onerror=alert(1)&gt;" in page
    assert '"><b>x' not in page and "&quot;&gt;&lt;b&gt;x" in page
    assert not re.search(r"<[a-zA-Z][^>]*\son[a-z]+\s*=", page), "no inline event-handler attribute"
    scripts = re.findall(r"<script\b[^>]*>", page)
    assert len(scripts) == 1 and "src=" not in scripts[0]
    assert f'nonce="{NONCE}"' in scripts[0]
    markup = re.sub(r"(<script\b[^>]*>).*?</script>", r"\1</script>", page, flags=re.S)
    styles = re.findall(r"<style\b[^>]*>", markup)
    assert all(f'nonce="{NONCE}"' in s for s in styles)


def test_the_embedded_state_is_an_attribute_not_a_script(review_page_story: Any) -> None:
    page = render(review_page_story.root)
    assert '<meta name="eil-state" content="' in page


# ---- T064: the changes list, its removed panel and the legacy entry (US6)


def test_the_changes_header_and_highlights(tmp_path: Path) -> None:
    built = review_page.build(tmp_path / "specs" / "001-story", changes=True)
    page = render(built.root)
    assert "Functional Specification: changes since approval" in page
    found = controls(page)
    assert {"FR-001", "FR-002", "legacy:functional"} <= set(found)
    assert "changed since it was approved" in found["FR-001"]


def test_the_legacy_entry_has_its_own_panel(tmp_path: Path) -> None:
    built = review_page.build(tmp_path / "specs" / "001-story", changes=True)
    page = render(built.root)
    panel = page[page.index('<section class="panel legacy"') :]
    panel = panel[: panel.index("</section>")]
    assert pagerender.esc(reviews.LEGACY_STATEMENT) in panel
    assert 'data-entry="legacy:functional"' in panel


def test_a_removed_entry_has_a_panel_with_its_full_text(tmp_path: Path) -> None:
    built = review_page.build(tmp_path / "specs" / "001-story", changes=True)
    package = Package(built.root)
    listed = reviews.build_list(package, "functional", "changes")
    removed_text = (
        "**FR-007**: The system shall email every analyst. Every word of the removed block is shown."
    )
    listed.entries.append(
        reviews.ListEntry("FR-007", "removed", removed_text, "removed since it was approved")
    )
    page = pagerender.review_page(package, ctx(), NONCE, listed=listed, current=("functional", "changes"))
    panel = page[page.index('<section class="panel removed"') :]
    panel = panel[: panel.index("</section>")]
    assert "Removed since approval" in panel
    assert "Every word of the removed block is shown." in panel
    assert 'data-entry="FR-007"' in panel
    assert "Accept the removal of FR-007?" in panel


def test_panel_controls_post_the_same_body(tmp_path: Path) -> None:
    built = review_page.build(tmp_path / "specs" / "001-story", changes=True)
    page = render(built.root)
    legacy = controls(page)["legacy:functional"]
    assert 'data-stage="functional"' in page and 'data-kind="changes"' in page
    assert "data-entry-hash=" in legacy
