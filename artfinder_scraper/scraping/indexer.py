"""Coordinate pagination and listing page traversal for the Artfinder storefront."""

from __future__ import annotations

import logging
from collections import OrderedDict
from typing import AsyncIterator, Iterable, List
from urllib.parse import urljoin, urlparse, urlunparse

from bs4 import BeautifulSoup

LISTING_PRODUCT_CONTAINER_SELECTOR: str = "section[data-testid='product-grid']"
PAGINATION_CONTAINER_SELECTOR: str = '[data-testid="pagination"], nav[aria-label*="pagination" i]'
PRODUCT_PATH_PREFIX: str = "/product/"


def _normalize_product_href(listing_url: str, raw_href: str | None) -> str | None:
    """Return a canonical product URL from ``raw_href`` or ``None`` if invalid."""

    if raw_href is None:
        return None

    href = raw_href.strip()
    if not href or href.startswith("#"):
        return None

    scheme_prefix = href.split(":", 1)[0].lower()
    if scheme_prefix in {"javascript", "mailto", "tel"}:
        return None

    absolute_href = urljoin(listing_url, href)
    parsed = urlparse(absolute_href)
    if not parsed.scheme or not parsed.netloc:
        return None

    if not parsed.path.startswith(PRODUCT_PATH_PREFIX):
        return None

    slug = parsed.path[len(PRODUCT_PATH_PREFIX) :].strip("/")
    if not slug or "/" in slug:
        return None

    normalized_path = f"{PRODUCT_PATH_PREFIX}{slug}/"
    return urlunparse((parsed.scheme, parsed.netloc, normalized_path, "", "", ""))


def _normalize_navigation_href(listing_url: str, raw_href: str | None) -> str | None:
    """Return an absolute pagination URL from ``raw_href`` or ``None`` if invalid."""

    if raw_href is None:
        return None

    href = raw_href.strip()
    if not href or href.startswith("#"):
        return None

    scheme_prefix = href.split(":", 1)[0].lower()
    if scheme_prefix in {"javascript", "mailto", "tel"}:
        return None

    absolute_href = urljoin(listing_url, href)
    parsed = urlparse(absolute_href)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None

    return urlunparse(
        (parsed.scheme, parsed.netloc, parsed.path, parsed.params, parsed.query, "")
    )


async def _fetch_listing_html(listing_url: str, page) -> str:
    """Navigate to ``listing_url`` and return the rendered HTML."""

    goto_and_wait = getattr(page, "goto_and_wait", None)
    if callable(goto_and_wait):
        await goto_and_wait(
            listing_url,
            wait_for_selector=LISTING_PRODUCT_CONTAINER_SELECTOR,
        )
    else:
        await page.goto(listing_url, wait_until="networkidle")
        wait_for_selector = getattr(page, "wait_for_selector", None)
        if callable(wait_for_selector):
            try:
                await wait_for_selector(
                    LISTING_PRODUCT_CONTAINER_SELECTOR,
                    timeout=10_000,
                )
            except Exception:  # pragma: no cover - defensive fallback
                load_state = getattr(page, "wait_for_load_state", None)
                if callable(load_state):
                    await load_state("domcontentloaded")

    return await page.content()


def _extract_product_links(listing_url: str, html: str) -> List[str]:
    """Extract ordered, unique product URLs from the provided ``html``."""

    soup = BeautifulSoup(html, "html.parser")

    seen: OrderedDict[str, None] = OrderedDict()
    for anchor in soup.select(f"a[href*='{PRODUCT_PATH_PREFIX}']"):
        normalized = _normalize_product_href(listing_url, anchor.get("href"))
        if normalized and normalized not in seen:
            seen[normalized] = None

    return list(seen.keys())


async def collect_listing_product_links(listing_url: str, page) -> List[str]:
    """Return ordered, unique product URLs discovered on a listing page."""

    html = await _fetch_listing_html(listing_url, page)
    return _extract_product_links(listing_url, html)


def _resolve_next_page_url(
    current_url: str,
    html: str,
    current_page_index: int,
) -> str | None:
    """Return the absolute URL for the next pagination target, if any."""

    soup = BeautifulSoup(html, "html.parser")
    containers = soup.select(PAGINATION_CONTAINER_SELECTOR)
    anchors = []
    if containers:
        for container in containers:
            anchors.extend(container.select("a[href]"))
    else:
        anchors = soup.select("a[href]")

    explicit_next: List[str] = []
    numeric_links: List[tuple[int, str]] = []
    for anchor in anchors:
        text = anchor.get_text(strip=True)
        if not text:
            continue

        normalized_href = _normalize_navigation_href(current_url, anchor.get("href"))
        if not normalized_href:
            continue

        lower_text = text.casefold()
        if lower_text in {"next", "›", "»"}:
            explicit_next.append(normalized_href)
            continue

        if text.isdigit():
            try:
                numeric_links.append((int(text), normalized_href))
            except ValueError:  # pragma: no cover - defensive guard
                continue

    if explicit_next:
        return explicit_next[0]

    for page_number, href in sorted(numeric_links, key=lambda pair: pair[0]):
        if page_number > current_page_index:
            return href

    return None


async def iter_listing_product_urls(
    listing_url: str,
    page,
    *,
    logger: logging.Logger | None = None,
) -> AsyncIterator[str]:
    """Yield product URLs across all paginated listing pages."""

    logger = logger or logging.getLogger(__name__)
    emitted_slugs: set[str] = set()
    page_urls_seen: set[str] = set()

    current_page_index = 1
    current_url = listing_url

    while current_url and current_url not in page_urls_seen:
        page_urls_seen.add(current_url)

        html = await _fetch_listing_html(current_url, page)
        product_links = _extract_product_links(current_url, html)

        new_items = 0
        for product_url in product_links:
            slug = urlparse(product_url).path[len(PRODUCT_PATH_PREFIX) :].strip("/")
            if slug and slug not in emitted_slugs:
                emitted_slugs.add(slug)
                new_items += 1
                yield product_url

        logger.info(
            "Processed listing page %s (%s new items)",
            current_page_index,
            new_items,
        )

        next_url = _resolve_next_page_url(current_url, html, current_page_index)
        if not next_url or next_url in page_urls_seen:
            break

        current_page_index += 1
        current_url = next_url


__all__: Iterable[str] = [
    "collect_listing_product_links",
    "iter_listing_product_urls",
    "LISTING_PRODUCT_CONTAINER_SELECTOR",
    "PAGINATION_CONTAINER_SELECTOR",
    "PRODUCT_PATH_PREFIX",
]
