"""Provide browser automation utilities for navigating Artfinder pages.

This module centralizes Playwright configuration so that the rest of the
codebase can rely on a single, polite Chromium driver.  The helper functions
defined here are intentionally lightweight so they can be mocked during unit
tests while still exercising the high-level fetching flow.
"""

from __future__ import annotations

import asyncio
import random
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import AsyncIterator, Tuple

from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError, async_playwright

USER_AGENT: str = "LB-Scraper/1.0"
POLITENESS_DELAY_SECONDS: Tuple[float, float] = (0.3, 0.8)
MAIN_CONTENT_SELECTOR: str = "main"


@dataclass
class PolitePage:
    """Wrap a Playwright page with the project politeness policy applied."""

    page: Page
    delay_range: Tuple[float, float] = POLITENESS_DELAY_SECONDS

    async def goto_and_wait(
        self,
        url: str,
        *,
        wait_for_selector: str | None = MAIN_CONTENT_SELECTOR,
        wait_timeout_ms: int = 10_000,
        wait_until: str = "networkidle",
    ) -> None:
        """Navigate to ``url`` while respecting configured politeness rules."""

        await asyncio.sleep(random.uniform(*self.delay_range))
        await self.page.goto(url, wait_until=wait_until)
        if wait_for_selector is not None:
            try:
                await self.page.wait_for_selector(wait_for_selector, timeout=wait_timeout_ms)
            except PlaywrightTimeoutError:
                await self.page.wait_for_load_state("domcontentloaded")

    async def content(self) -> str:
        """Return the current page HTML."""

        return await self.page.content()

    async def close(self) -> None:
        """Close the underlying Playwright page."""

        await self.page.close()

    def __getattr__(self, attribute_name: str):
        return getattr(self.page, attribute_name)


@asynccontextmanager
async def chromium_page(delay_range: Tuple[float, float] = POLITENESS_DELAY_SECONDS) -> AsyncIterator[PolitePage]:
    """Launch a Chromium page configured with the project defaults."""

    async with async_playwright() as playwright_driver:
        browser = await playwright_driver.chromium.launch(headless=True)
        context = await browser.new_context(user_agent=USER_AGENT)
        page = await context.new_page()
        wrapped_page = PolitePage(page=page, delay_range=delay_range)
        try:
            yield wrapped_page
        finally:
            await wrapped_page.close()
            await context.close()
            await browser.close()


async def _fetch_page_html_async(url: str, *, main_selector: str = MAIN_CONTENT_SELECTOR) -> str:
    """Return the rendered HTML for ``url`` once the main content is visible."""

    async with chromium_page() as page:
        await page.goto_and_wait(url, wait_for_selector=main_selector)
        return await page.content()


def fetch_page_html(url: str, *, main_selector: str = MAIN_CONTENT_SELECTOR) -> str:
    """Synchronously fetch ``url`` and return its rendered HTML."""

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        raise RuntimeError(
            "fetch_page_html cannot be called while an event loop is running. "
            "Use the `_fetch_page_html_async` coroutine instead."
        )
    return asyncio.run(_fetch_page_html_async(url, main_selector=main_selector))
