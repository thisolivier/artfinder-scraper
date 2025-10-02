"""Smoke tests for the Playwright browser helpers."""
from __future__ import annotations

from types import ModuleType
from typing import Any, Dict, List

import sys
import pytest

# Provide a lightweight stub for the Playwright imports used by the browser module.


class _StubTimeoutError(Exception):
    """Local stand-in for Playwright's TimeoutError during tests."""


async def _placeholder_async_playwright():  # pragma: no cover - patched in tests
    raise RuntimeError("async_playwright should be patched within tests")


fake_playwright_module = ModuleType("playwright")
fake_async_api_module = ModuleType("playwright.async_api")
fake_async_api_module.Page = object
fake_async_api_module.TimeoutError = _StubTimeoutError
fake_async_api_module.async_playwright = _placeholder_async_playwright
fake_playwright_module.async_api = fake_async_api_module
sys.modules.setdefault("playwright", fake_playwright_module)
sys.modules.setdefault("playwright.async_api", fake_async_api_module)

from artfinder_scraper.scraping import browsers


class DummyPage:
    def __init__(self) -> None:
        self.goto_calls: List[Dict[str, Any]] = []
        self.selector_waits: List[Dict[str, Any]] = []
        self.load_state_waits: List[str] = []
        self.closed: bool = False

    async def goto(self, url: str, wait_until: str = "load") -> None:
        self.goto_calls.append({"url": url, "wait_until": wait_until})

    async def wait_for_selector(self, selector: str, timeout: int = 0) -> None:
        self.selector_waits.append({"selector": selector, "timeout": timeout})

    async def wait_for_load_state(self, state: str) -> None:
        self.load_state_waits.append(state)

    async def content(self) -> str:
        return "<html><main>ok</main></html>"

    async def close(self) -> None:
        self.closed = True


class DummyContext:
    def __init__(self, page: DummyPage) -> None:
        self.page = page
        self.closed: bool = False

    async def new_page(self) -> DummyPage:
        return self.page

    async def close(self) -> None:
        self.closed = True


class DummyBrowser:
    def __init__(self, context: DummyContext) -> None:
        self.context = context
        self.closed: bool = False
        self.user_agent: str | None = None

    async def new_context(self, user_agent: str) -> DummyContext:
        self.user_agent = user_agent
        return self.context

    async def close(self) -> None:
        self.closed = True


class DummyChromiumLauncher:
    def __init__(self, browser: DummyBrowser) -> None:
        self.browser = browser
        self.launch_calls: List[Dict[str, Any]] = []

    async def launch(self, headless: bool = True) -> DummyBrowser:
        self.launch_calls.append({"headless": headless})
        return self.browser


class DummyPlaywright:
    def __init__(self, launcher: DummyChromiumLauncher) -> None:
        self.chromium = launcher


class DummyAsyncPlaywright:
    def __init__(self, playwright: DummyPlaywright) -> None:
        self.playwright = playwright
        self.exited: bool = False

    async def __aenter__(self) -> DummyPlaywright:
        return self.playwright

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        self.exited = True


def test_fetch_page_html_smoke(monkeypatch: pytest.MonkeyPatch) -> None:
    dummy_page = DummyPage()
    dummy_context = DummyContext(dummy_page)
    dummy_browser = DummyBrowser(dummy_context)
    dummy_launcher = DummyChromiumLauncher(dummy_browser)
    dummy_playwright = DummyPlaywright(dummy_launcher)
    dummy_async_playwright = DummyAsyncPlaywright(dummy_playwright)

    monkeypatch.setattr(browsers, "async_playwright", lambda: dummy_async_playwright)

    sleep_calls: List[float] = []

    async def fake_sleep(duration: float) -> None:
        sleep_calls.append(duration)

    monkeypatch.setattr(browsers.asyncio, "sleep", fake_sleep)
    monkeypatch.setattr(browsers.random, "uniform", lambda start, end: 0.5)

    html = browsers.fetch_page_html("https://example.com/item")

    assert html == "<html><main>ok</main></html>"
    assert dummy_page.goto_calls == [
        {"url": "https://example.com/item", "wait_until": "networkidle"}
    ]
    assert dummy_page.selector_waits == [
        {"selector": browsers.MAIN_CONTENT_SELECTOR, "timeout": 10_000}
    ]
    assert sleep_calls == [0.5]
    assert dummy_browser.user_agent == browsers.USER_AGENT
    assert dummy_page.closed is True
    assert dummy_context.closed is True
    assert dummy_browser.closed is True
    assert dummy_async_playwright.exited is True
