"""Tests for the listing page indexer utilities."""

from __future__ import annotations

import asyncio
from pathlib import Path
import logging
from typing import Any, Dict, List

from artfinder_scraper.scraping.indexer import (
    LISTING_PRODUCT_CONTAINER_SELECTOR,
    iter_listing_product_urls,
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


class DummyPaginatedPage:
    def __init__(self, pages: Dict[str, str]) -> None:
        self.pages = pages
        self.current_url: str | None = None
        self.goto_calls: List[Dict[str, Any]] = []

    async def goto_and_wait(
        self,
        url: str,
        *,
        wait_for_selector: str | None = None,
        wait_timeout_ms: int | None = None,
        wait_until: str | None = None,
    ) -> None:
        self.current_url = url
        self.goto_calls.append(
            {
                "url": url,
                "wait_for_selector": wait_for_selector,
                "wait_timeout_ms": wait_timeout_ms,
                "wait_until": wait_until,
            }
        )

    async def content(self) -> str:
        assert self.current_url is not None
        return self.pages[self.current_url]


def test_collect_listing_product_links_deduplicates_and_normalizes() -> None:
    html = (FIXTURES_DIR / "example_artist_listing.html").read_text(encoding="utf-8")
    page = DummyPolitePage(html)

    links = asyncio.run(
        collect_listing_product_links(
            "https://www.artfinder.com/artist/example-artist/sort-newest/",
            page,
        )
    )

    assert page.goto_calls == [
        {
            "url": "https://www.artfinder.com/artist/example-artist/sort-newest/",
            "wait_for_selector": LISTING_PRODUCT_CONTAINER_SELECTOR,
            "wait_timeout_ms": None,
            "wait_until": None,
        }
    ]
    assert links == [
        "https://www.artfinder.com/product/echoes-of-dawn-canvas/",
        "https://www.artfinder.com/product/lantern-glow-atrium-study/",
        "https://www.artfinder.com/product/prism-tide-harbor-series/",
        "https://www.artfinder.com/product/blue-horizon-limited-series/",
        "https://www.artfinder.com/product/coastal-sketch-studio-proof/",
        "https://www.artfinder.com/product/moonlit-field-nightscape/",
    ]
    assert len(links) == len(set(links))


def test_iter_listing_product_urls_paginates_until_exhausted(caplog) -> None:
    listing_url = "https://www.artfinder.com/artist/example/sort-newest/"
    pages = {
        listing_url: (
            FIXTURES_DIR / "listing_page_one.html"
        ).read_text(encoding="utf-8"),
        "https://www.artfinder.com/artist/example/sort-newest/?page=2": (
            FIXTURES_DIR / "listing_page_two.html"
        ).read_text(encoding="utf-8"),
        "https://www.artfinder.com/artist/example/sort-newest/?page=3": (
            FIXTURES_DIR / "listing_page_three.html"
        ).read_text(encoding="utf-8"),
    }

    page = DummyPaginatedPage(pages)

    async def collect_all() -> List[str]:
        caplog.set_level(logging.INFO)
        results: List[str] = []
        async for url in iter_listing_product_urls(listing_url, page):
            results.append(url)
        return results

    urls = asyncio.run(collect_all())

    assert urls == [
        "https://www.artfinder.com/product/first-item/",
        "https://www.artfinder.com/product/second-item/",
        "https://www.artfinder.com/product/third-item/",
        "https://www.artfinder.com/product/fourth-item/",
    ]

    assert page.goto_calls == [
        {
            "url": listing_url,
            "wait_for_selector": LISTING_PRODUCT_CONTAINER_SELECTOR,
            "wait_timeout_ms": None,
            "wait_until": None,
        },
        {
            "url": "https://www.artfinder.com/artist/example/sort-newest/?page=2",
            "wait_for_selector": LISTING_PRODUCT_CONTAINER_SELECTOR,
            "wait_timeout_ms": None,
            "wait_until": None,
        },
        {
            "url": "https://www.artfinder.com/artist/example/sort-newest/?page=3",
            "wait_for_selector": LISTING_PRODUCT_CONTAINER_SELECTOR,
            "wait_timeout_ms": None,
            "wait_until": None,
        },
    ]

    info_messages = [
        record.getMessage()
        for record in caplog.records
        if record.name == "artfinder_scraper.scraping.indexer"
    ]
    assert info_messages == [
        "Processed listing page 1 (2 new items)",
        "Processed listing page 2 (1 new items)",
        "Processed listing page 3 (1 new items)",
    ]


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
              <a href=\"/product/echoes-of-dawn-canvas/\">Echoes of Dawn</a>
            </article>
          </section>
        </main>
      </body>
    </html>
    """
    page = DummyRawPage(html)

    links = asyncio.run(
        collect_listing_product_links(
            "https://www.artfinder.com/artist/example-artist/sort-newest/",
            page,
        )
    )

    assert page.goto_calls == [
        {
            "url": "https://www.artfinder.com/artist/example-artist/sort-newest/",
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
        "https://www.artfinder.com/product/echoes-of-dawn-canvas/",
    ]
