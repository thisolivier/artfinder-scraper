"""Tests for the listing page indexer utilities."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Dict, List

from artfinder_scraper.scraping.indexer import (
    LISTING_PRODUCT_CONTAINER_SELECTOR,
    collect_listing_product_links,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"


class DummyPolitePage:
    def __init__(self, html: str) -> None:
        self.html = html
        self.goto_calls: List[Dict[str, Any]] = []

    async def goto_and_wait(
        self,
        url: str,
        *,
        wait_for_selector: str | None = None,
        wait_timeout_ms: int | None = None,
        wait_until: str | None = None,
    ) -> None:
        self.goto_calls.append(
            {
                "url": url,
                "wait_for_selector": wait_for_selector,
                "wait_timeout_ms": wait_timeout_ms,
                "wait_until": wait_until,
            }
        )

    async def content(self) -> str:
        return self.html


def test_collect_listing_product_links_deduplicates_and_normalizes() -> None:
    html = (FIXTURES_DIR / "lizzie_butler_listing.html").read_text(encoding="utf-8")
    page = DummyPolitePage(html)

    links = asyncio.run(
        collect_listing_product_links(
            "https://www.artfinder.com/artist/lizziebutler/sort-newest/",
            page,
        )
    )

    assert page.goto_calls == [
        {
            "url": "https://www.artfinder.com/artist/lizziebutler/sort-newest/",
            "wait_for_selector": LISTING_PRODUCT_CONTAINER_SELECTOR,
            "wait_timeout_ms": None,
            "wait_until": None,
        }
    ]
    assert links == [
        "https://www.artfinder.com/product/a-windswept-walk/",
        "https://www.artfinder.com/product/soft-light-kew-gardens-an-atmospheric-oil-painting/",
        "https://www.artfinder.com/product/shoreline-2024-oil-painting/",
        "https://www.artfinder.com/product/blue-horizon-limited-edition/",
        "https://www.artfinder.com/product/coastal-sketch-original-drawing/",
        "https://www.artfinder.com/product/moonlit-field-oil-on-board/",
    ]
    assert len(links) == len(set(links))


class DummyRawPage:
    def __init__(self, html: str) -> None:
        self.html = html
        self.goto_calls: List[Dict[str, Any]] = []
        self.selector_waits: List[Dict[str, Any]] = []
        self.load_state_waits: List[str] = []

    async def goto(self, url: str, wait_until: str = "load") -> None:
        self.goto_calls.append({"url": url, "wait_until": wait_until})

    async def wait_for_selector(self, selector: str, timeout: int = 0) -> None:
        self.selector_waits.append({"selector": selector, "timeout": timeout})

    async def wait_for_load_state(self, state: str) -> None:
        self.load_state_waits.append(state)

    async def content(self) -> str:
        return self.html


def test_collect_listing_product_links_without_polite_wrapper() -> None:
    html = """
    <html>
      <body>
        <main>
          <section data-testid=\"product-grid\">
            <article>
              <a href=\"/product/a-windswept-walk/\">A Windswept Walk</a>
            </article>
          </section>
        </main>
      </body>
    </html>
    """
    page = DummyRawPage(html)

    links = asyncio.run(
        collect_listing_product_links(
            "https://www.artfinder.com/artist/lizziebutler/sort-newest/",
            page,
        )
    )

    assert page.goto_calls == [
        {
            "url": "https://www.artfinder.com/artist/lizziebutler/sort-newest/",
            "wait_until": "networkidle",
        }
    ]
    assert page.selector_waits == [
        {
            "selector": LISTING_PRODUCT_CONTAINER_SELECTOR,
            "timeout": 10_000,
        }
    ]
    assert links == [
        "https://www.artfinder.com/product/a-windswept-walk/",
    ]
