"""Orchestrate scraping workflow execution and high-level control flow."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import AsyncIterator, Awaitable, Callable, Iterable, Mapping
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .browsers import _fetch_page_html_async, chromium_page
from .downloader import ArtworkImageDownloader, ImageDownloadError
from .extractor import extract_artwork_fields
from .indexer import iter_listing_product_urls
from .models import Artwork, ValidationError
from .normalize import normalize_artwork
from .spreadsheet import append_artwork_to_spreadsheet

DEFAULT_LISTING_URL: str = "https://www.artfinder.com/artist/lizziebutler/sort-newest/"


@dataclass(frozen=True)
class RunnerError:
    """Represents a recoverable error encountered while processing an item."""

    product_url: str
    stage: str
    message: str


class ScraperRunner:
    """Coordinate the high-level scraping pipeline end-to-end."""

    DEFAULT_JSONL_PATH: Path = Path(__file__).resolve().parents[1] / "data" / "artworks.jsonl"
    DEFAULT_SPREADSHEET_PATH: Path = Path(__file__).resolve().parents[1] / "data" / "artworks.xlsx"

    def __init__(
        self,
        listing_url: str = DEFAULT_LISTING_URL,
        *,
        fetch_html: Callable[[str], Awaitable[str]] = _fetch_page_html_async,
        extractor: Callable[[str, str], Artwork] = extract_artwork_fields,
        normalizer: Callable[[Artwork], Mapping[str, Any]] = normalize_artwork,
        downloader: ArtworkImageDownloader | None = None,
        listing_iterator: Callable[
            [str, Any], AsyncIterator[str]
        ] = iter_listing_product_urls,
        page_factory: Callable[[], Any] = chromium_page,
        jsonl_path: Path | None = None,
        spreadsheet_path: Path | None = None,
        rate_limit_seconds: float = 0.0,
        sleep_function: Callable[[float], Awaitable[None]] = asyncio.sleep,
        time_function: Callable[[], float] = time.monotonic,
        logger: logging.Logger | None = None,
        spreadsheet_writer: Callable[[Artwork, Path], bool] | None = None,
        skip_slugs: Iterable[str] | None = None,
        persist_outputs: bool = True,
    ) -> None:
        self.listing_url = listing_url
        self.fetch_html = fetch_html
        self.extractor = extractor
        self.normalizer = normalizer
        self.downloader = downloader or ArtworkImageDownloader()
        self.listing_iterator = listing_iterator
        self.page_factory = page_factory
        self.jsonl_path = Path(jsonl_path) if jsonl_path else self.DEFAULT_JSONL_PATH
        self.spreadsheet_path = (
            Path(spreadsheet_path) if spreadsheet_path else self.DEFAULT_SPREADSHEET_PATH
        )
        self.rate_limit_seconds = max(rate_limit_seconds, 0.0)
        self.sleep_function = sleep_function
        self.time_function = time_function
        self.logger = logger or logging.getLogger(__name__)
        self.spreadsheet_writer = spreadsheet_writer or append_artwork_to_spreadsheet
        self.skip_slugs: set[str] = {slug.strip() for slug in skip_slugs or [] if slug.strip()}
        self.persist_outputs = persist_outputs
        self.errors: list[RunnerError] = []

    async def crawl(self, *, max_items: int | None = None) -> list[Artwork]:
        """Run the scraping pipeline and return processed artworks."""

        self.errors.clear()
        processed_artworks: list[Artwork] = []
        processed_count = 0
        last_request_timestamp: float | None = None

        if self.persist_outputs:
            self.jsonl_path.parent.mkdir(parents=True, exist_ok=True)
            self.spreadsheet_path.parent.mkdir(parents=True, exist_ok=True)

        async with self.page_factory() as page:
            async for product_url in self._iter_product_urls(page):
                if max_items is not None and processed_count >= max_items:
                    break

                slug = self._slug_from_product_url(product_url)
                if slug and slug in self.skip_slugs:
                    self.logger.info("Skipping %s (already processed)", product_url)
                    continue

                self.logger.info("Processing %s", product_url)
                try:
                    last_request_timestamp = await self._respect_rate_limit(last_request_timestamp)
                    html = await self.fetch_html(product_url)
                    last_request_timestamp = self.time_function()
                except Exception as error:  # pragma: no cover - network errors handled generically
                    self._record_error(product_url, "fetch", error)
                    continue

                try:
                    artwork = self.extractor(html, product_url)
                except (ValidationError, ValueError) as error:
                    self._record_error(product_url, "extract", error)
                    continue

                if self.persist_outputs:
                    try:
                        artwork = self._download_artwork_image(artwork)
                    except ImageDownloadError as error:
                        self._record_error(product_url, "download", error)
                        continue

                try:
                    normalized_record = self.normalizer(artwork)
                    json_ready_record = self._prepare_json_record(normalized_record, artwork)
                except Exception as error:
                    self._record_error(product_url, "normalize", error)
                    continue

                if self.persist_outputs:
                    try:
                        self._append_jsonl_record(json_ready_record)
                    except OSError as error:
                        self._record_error(product_url, "persist", error)
                        continue

                    try:
                        self.spreadsheet_writer(artwork, self.spreadsheet_path)
                    except Exception as error:  # pragma: no cover - spreadsheet errors handled gracefully
                        self._record_error(product_url, "spreadsheet", error)

                processed_artworks.append(artwork)
                processed_count += 1
                if slug:
                    self.skip_slugs.add(slug)
                self.logger.info("Processed %s (%s total)", product_url, processed_count)

        return processed_artworks

    def run(self, *, max_items: int | None = None) -> list[Artwork]:
        """Synchronous convenience wrapper around :meth:`crawl`."""

        return asyncio.run(self.crawl(max_items=max_items))

    async def _iter_product_urls(self, page) -> AsyncIterator[str]:
        async for product_url in self.listing_iterator(
            self.listing_url, page, logger=self.logger
        ):
            yield product_url

    async def _respect_rate_limit(self, last_timestamp: float | None) -> float | None:
        if last_timestamp is None:
            return self.time_function()

        if self.rate_limit_seconds <= 0:
            return self.time_function()

        current_timestamp = self.time_function()
        elapsed = current_timestamp - last_timestamp
        remaining = self.rate_limit_seconds - elapsed
        if remaining > 0:
            await self.sleep_function(remaining)
            current_timestamp = self.time_function()
        return current_timestamp

    def _download_artwork_image(self, artwork: Artwork) -> Artwork:
        downloader_callable = getattr(self.downloader, "download_artwork_image", None)
        if callable(downloader_callable):
            return downloader_callable(artwork)
        if callable(self.downloader):  # pragma: no cover - fallback for functional mocks
            return self.downloader(artwork)  # type: ignore[return-value]
        raise TypeError("downloader must be callable or expose download_artwork_image")

    def _prepare_json_record(
        self, normalized_record: Mapping[str, Any], artwork: Artwork
    ) -> dict[str, Any]:
        record = dict(normalized_record)
        if "slug" not in record:
            record["slug"] = artwork.slug
        if "source_url" not in record:
            record["source_url"] = str(artwork.source_url)
        return self._make_json_safe(record)

    def _make_json_safe(self, value: Any) -> Any:
        if isinstance(value, Mapping):
            return {key: self._make_json_safe(item) for key, item in value.items()}
        if isinstance(value, Iterable) and not isinstance(value, (str, bytes, bytearray)):
            return [self._make_json_safe(item) for item in value]
        if isinstance(value, Artwork):
            return self._make_json_safe(normalize_artwork(value))
        if isinstance(value, (datetime, date)):
            return value.isoformat()
        if isinstance(value, Decimal):
            return str(value)
        if isinstance(value, (str, bytes, bytearray, int, float, bool)) or value is None:
            return value
        if hasattr(value, "__str__"):
            return str(value)
        return value

    def _append_jsonl_record(self, record: Mapping[str, Any]) -> None:
        if not self.persist_outputs:
            return
        with self.jsonl_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    def _slug_from_product_url(self, product_url: str) -> str | None:
        try:
            parsed = urlparse(product_url)
        except Exception:  # pragma: no cover - invalid URLs guarded upstream
            return None
        slug = parsed.path.split("/product/", 1)[-1].strip("/") if "/product/" in parsed.path else None
        return slug or None

    def _record_error(self, product_url: str, stage: str, error: Exception) -> None:
        message = f"{stage} failed for {product_url}: {error}"
        self.logger.error(message)
        self.errors.append(RunnerError(product_url=product_url, stage=stage, message=str(error)))


__all__ = [
    "ScraperRunner",
    "RunnerError",
    "DEFAULT_LISTING_URL",
    "DEFAULT_SPREADSHEET_PATH",
]
