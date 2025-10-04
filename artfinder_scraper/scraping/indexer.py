"""Coordinate pagination and listing page traversal for the Artfinder storefront."""

from __future__ import annotations

from typing import Iterable, List, Set
from urllib.parse import urljoin, urlparse, urlunparse

from bs4 import BeautifulSoup

LISTING_PRODUCT_CONTAINER_SELECTOR: str = "section[data-testid='product-grid']"
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


async def collect_listing_product_links(listing_url: str, page) -> List[str]:
    """Return ordered, unique product URLs discovered on a listing page."""

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

    html = await page.content()
    soup = BeautifulSoup(html, "html.parser")

    seen: Set[str] = set()
    product_links: List[str] = []
    for anchor in soup.select(f"a[href*='{PRODUCT_PATH_PREFIX}']"):
        normalized = _normalize_product_href(listing_url, anchor.get("href"))
        if normalized and normalized not in seen:
            seen.add(normalized)
            product_links.append(normalized)

    return product_links


__all__: Iterable[str] = [
    "collect_listing_product_links",
    "LISTING_PRODUCT_CONTAINER_SELECTOR",
    "PRODUCT_PATH_PREFIX",
]
