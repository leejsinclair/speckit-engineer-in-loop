"""Execute the browser review page's generated JavaScript under its real CSP."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from eil import reviews
from eil.package import Package
from playwright.sync_api import Page as BrowserPage
from playwright.sync_api import expect, sync_playwright

from tests.fixtures import review_page
from tests.helpers.page import Page, start_page

pytestmark = [pytest.mark.browser, pytest.mark.slow]


@pytest.fixture
def browser_page() -> Iterator[BrowserPage]:
    with sync_playwright() as playwright:
        if not Path(playwright.chromium.executable_path).exists():
            pytest.skip("Playwright Chromium is not installed; run `python -m playwright install chromium`")
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()
        yield page
        browser.close()


def test_controls_execute_under_csp_and_store_answers(
    browser_page: BrowserPage, page_server: Page, review_page_story: Any
) -> None:
    errors: list[str] = []
    browser_page.on("pageerror", lambda error: errors.append(str(error)))
    browser_page.goto(page_server.address)

    browser_page.get_by_role("button", name="Change", exact=True).click()
    browser_page.locator("#name-input").fill("Grace Dev")
    browser_page.get_by_role("button", name="Save").click()
    expect(browser_page.locator("#name")).to_have_text("Grace Dev")
    browser_page.get_by_role("button", name="Change", exact=True).click()
    browser_page.locator("#name-input").fill("Ada Dev")
    browser_page.get_by_role("button", name="Save").click()

    first = browser_page.locator('[data-entry="FR-001"]')
    first.get_by_role("button", name="Accept FR-001").click()
    expect(first.locator(".stored-text")).to_contain_text("Accepted by Ada Dev")

    second = browser_page.locator('[data-entry="FR-002"]')
    second.get_by_role("button", name="Send back FR-002").click()
    second.locator("textarea").fill("Clarify the dismissal outcome.")
    second.get_by_role("button", name="Send the answer to FR-002").click()
    expect(second.locator(".stored-text")).to_contain_text("Sent back by Ada Dev")

    browser_page.keyboard.press("n")
    assert browser_page.locator(":focus").get_attribute("data-act") in {"accept", "except", "question"}
    assert errors == []

    (session,) = Package(review_page_story.root).story_record()["review_sessions"].values()
    assert session["answers"]["FR-001"]["by"] == "Ada Dev"
    assert session["answers"]["FR-002"]["comment"] == "Clarify the dismissal outcome."


def test_stale_entry_refusal_is_rendered_in_place(
    browser_page: BrowserPage, page_server: Page, review_page_story: Any
) -> None:
    browser_page.goto(page_server.address)
    changed = "The system shall flag likely duplicate customers on import."
    document = review_page_story.story.read("functional")
    review_page_story.story.write(
        "functional",
        document.replace("The system shall flag duplicate customers on import.", changed),
    )

    control = browser_page.locator('[data-entry="FR-001"]')
    control.get_by_role("button", name="Accept FR-001").click()

    expect(control.locator(".changed")).to_be_visible()
    expect(control.locator(".changed pre")).to_contain_text(changed)
    assert Package(review_page_story.root).story_record().get("review_sessions", {}) == {}


def test_polling_shows_a_reload_notice_for_an_external_answer(
    browser_page: BrowserPage, page_server: Page, review_page_story: Any
) -> None:
    browser_page.goto(page_server.address)
    entry = next(
        item
        for item in reviews.build_list(Package(review_page_story.root), "functional", "inferred").entries
        if item.key == "FR-002"
    )
    status, result = page_server.post(
        "/answer",
        {
            "stage": "functional",
            "kind": "inferred",
            "entry": entry.key,
            "disposition": "accept",
            "shown": entry.hash,
            "question": entry.question,
            "comment": None,
        },
    )
    assert status == 200 and result["ok"] is True

    notice = browser_page.locator("#notice")
    expect(notice).to_be_visible(timeout=6000)
    expect(notice).to_contain_text("FR-002 was answered elsewhere")
    expect(notice.get_by_role("button", name="Reload")).to_be_visible()


def test_successful_answer_does_not_absorb_an_unrelated_change(
    browser_page: BrowserPage, page_server: Page, review_page_story: Any
) -> None:
    browser_page.goto(page_server.address)
    entry = next(
        item
        for item in reviews.build_list(Package(review_page_story.root), "functional", "inferred").entries
        if item.key == "FR-002"
    )
    status, result = page_server.post(
        "/answer",
        {
            "stage": "functional",
            "kind": "inferred",
            "entry": entry.key,
            "disposition": "accept",
            "shown": entry.hash,
            "question": entry.question,
            "comment": None,
        },
    )
    assert status == 200 and result["ok"] is True

    browser_page.locator('[data-entry="FR-001"]').get_by_role("button", name="Accept FR-001").click()

    notice = browser_page.locator("#notice")
    expect(notice).to_be_visible()
    expect(notice).to_contain_text("FR-002 was answered elsewhere")


def test_section_action_needs_two_clicks_and_submits_shown_hashes(
    browser_page: BrowserPage, tmp_path: Path
) -> None:
    built = review_page.build(tmp_path / "specs" / "001-story", entries=12)
    server = start_page(built.root)
    try:
        browser_page.goto(server.address)
        button = browser_page.locator('button[data-act="section"][data-section="Functional Requirements"]')
        button.click()
        expect(button).to_have_text("Accept the 4 unanswered blocks under Functional Requirements?")
        assert Package(built.root).story_record().get("review_sessions", {}) == {}

        button.click()
        expect(button).to_be_hidden()
        (session,) = Package(built.root).story_record()["review_sessions"].values()
        assert set(session["answers"]) == {"FR-001", "FR-002", "FR-003", "FR-004"}
    finally:
        server.stop()
