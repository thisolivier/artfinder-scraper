"""Integration coverage for the scraper runner orchestration pipeline."""

from __future__ import annotations

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator, List

from pathlib import Path

from artfinder_scraper.scraping.models import Artwork
from artfinder_scraper.scraping.runner import ScraperRunner


def _build_artwork(product_url: str, index: int) -> Artwork:
    """Return a deterministic :class:`Artwork` instance for the given URL."""

    return Artwork(
        title=f"Artwork {index}",
        description=f"Description {index}",
        price_gbp="£10",
        size="10 x 10 cm",
        sold=False,
        image_url=None,
        materials_used=None,
        source_url=product_url,
    )


def test_runner_processes_items_and_writes_jsonl(tmp_path) -> None:
    listing_url = "https://example.com/listing/"
    product_urls: List[str] = [
        "https://example.com/product/one/",
        "https://example.com/product/two/",
    ]

    call_log: list[tuple[str, str]] = []

    async def fake_listing_iterator(listing: str, page, *, logger=None) -> AsyncIterator[str]:
        assert listing == listing_url
        for product_url in product_urls:
            call_log.append(("index", product_url))
            yield product_url

    async def fake_fetch(product_url: str) -> str:
        call_log.append(("fetch", product_url))
        return f"<html>{product_url}</html>"

    def fake_extractor(html: str, product_url: str) -> Artwork:
        call_log.append(("extract", product_url))
        slug_position = product_urls.index(product_url) + 1
        return _build_artwork(product_url, slug_position)

    class FakeDownloader:
        def __init__(self) -> None:
            self.downloaded: list[str] = []

        def download_artwork_image(self, artwork: Artwork) -> Artwork:
            self.downloaded.append(artwork.slug)
            call_log.append(("download", artwork.slug))
            return artwork

    downloader = FakeDownloader()

    def fake_normalizer(artwork: Artwork) -> dict[str, object]:
        call_log.append(("normalize", artwork.slug))
        return {
            "title": artwork.title,
            "slug": artwork.slug,
            "source_url": str(artwork.source_url),
            "scraped_at": artwork.scraped_at,
            "price_gbp": artwork.price_gbp,
        }

    def fake_spreadsheet_writer(artwork: Artwork, path) -> bool:
        call_log.append(("spreadsheet", artwork.slug))
        spreadsheet_calls.append(path)
        return True

    sleep_durations: list[float] = []

    async def fake_sleep(duration: float) -> None:
        sleep_durations.append(duration)

    time_counter = {"value": 0.0}

    def fake_time() -> float:
        time_counter["value"] += 0.1
        return time_counter["value"]

    @asynccontextmanager
    async def fake_page_factory():
        yield object()

    jsonl_path = tmp_path / "data" / "artworks.jsonl"
    spreadsheet_path = tmp_path / "data" / "artworks.xlsx"
    spreadsheet_calls: list[Path] = []

    runner = ScraperRunner(
        listing_url=listing_url,
        fetch_html=fake_fetch,
        extractor=fake_extractor,
        normalizer=fake_normalizer,
        downloader=downloader,
        listing_iterator=fake_listing_iterator,
        page_factory=fake_page_factory,
        jsonl_path=jsonl_path,
        spreadsheet_path=spreadsheet_path,
        rate_limit_seconds=0.5,
        sleep_function=fake_sleep,
        time_function=fake_time,
        logger=logging.getLogger("scraper-runner-test"),
        spreadsheet_writer=fake_spreadsheet_writer,
    )

    processed_artworks = asyncio.run(runner.crawl(max_items=2))

    assert [artwork.slug for artwork in processed_artworks] == ["one", "two"]
    assert sleep_durations, "Rate limiting hook should be invoked between requests"

    expected_sequence = [
        ("index", product_urls[0]),
        ("fetch", product_urls[0]),
        ("extract", product_urls[0]),
        ("download", "one"),
        ("normalize", "one"),
        ("spreadsheet", "one"),
        ("index", product_urls[1]),
        ("fetch", product_urls[1]),
        ("extract", product_urls[1]),
        ("download", "two"),
        ("normalize", "two"),
        ("spreadsheet", "two"),
    ]
    assert call_log == expected_sequence

    assert jsonl_path.exists()
    json_lines = jsonl_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(json_lines) == 2
    parsed_records = [json.loads(line) for line in json_lines]
    assert {record["slug"] for record in parsed_records} == {"one", "two"}
    assert spreadsheet_calls == [spreadsheet_path, spreadsheet_path]


def test_runner_can_skip_image_downloads(tmp_path) -> None:
    listing_url = "https://example.com/listing/"
    product_urls: List[str] = [
        "https://example.com/product/one/",
        "https://example.com/product/two/",
    ]

    call_log: list[tuple[str, str]] = []

    async def fake_listing_iterator(listing: str, page, *, logger=None) -> AsyncIterator[str]:
        assert listing == listing_url
        for product_url in product_urls:
            call_log.append(("index", product_url))
            yield product_url

    async def fake_fetch(product_url: str) -> str:
        call_log.append(("fetch", product_url))
        return f"<html>{product_url}</html>"

    def fake_extractor(html: str, product_url: str) -> Artwork:
        call_log.append(("extract", product_url))
        slug_position = product_urls.index(product_url) + 1
        return _build_artwork(product_url, slug_position)

    class FakeDownloader:
        def __init__(self) -> None:
            self.downloaded: list[str] = []

        def download_artwork_image(self, artwork: Artwork) -> Artwork:
            self.downloaded.append(artwork.slug)
            call_log.append(("download", artwork.slug))
            return artwork

    downloader = FakeDownloader()

    def fake_normalizer(artwork: Artwork) -> dict[str, object]:
        call_log.append(("normalize", artwork.slug))
        return {
            "title": artwork.title,
            "slug": artwork.slug,
            "source_url": str(artwork.source_url),
            "scraped_at": artwork.scraped_at,
            "price_gbp": artwork.price_gbp,
        }

    def fake_spreadsheet_writer(artwork: Artwork, path) -> bool:
        call_log.append(("spreadsheet", artwork.slug))
        spreadsheet_calls.append(path)
        return True

    @asynccontextmanager
    async def fake_page_factory():
        yield object()

    jsonl_path = tmp_path / "data" / "artworks.jsonl"
    spreadsheet_path = tmp_path / "data" / "artworks.xlsx"
    spreadsheet_calls: list[Path] = []

    runner = ScraperRunner(
        listing_url=listing_url,
        fetch_html=fake_fetch,
        extractor=fake_extractor,
        normalizer=fake_normalizer,
        downloader=downloader,
        listing_iterator=fake_listing_iterator,
        page_factory=fake_page_factory,
        jsonl_path=jsonl_path,
        spreadsheet_path=spreadsheet_path,
        logger=logging.getLogger("scraper-runner-test"),
        spreadsheet_writer=fake_spreadsheet_writer,
        download_images=False,
    )

    processed_artworks = asyncio.run(runner.crawl(max_items=2))

    assert [artwork.slug for artwork in processed_artworks] == ["one", "two"]
    assert downloader.downloaded == []

    expected_sequence = [
        ("index", product_urls[0]),
        ("fetch", product_urls[0]),
        ("extract", product_urls[0]),
        ("normalize", "one"),
        ("spreadsheet", "one"),
        ("index", product_urls[1]),
        ("fetch", product_urls[1]),
        ("extract", product_urls[1]),
        ("normalize", "two"),
        ("spreadsheet", "two"),
    ]
    assert call_log == expected_sequence

    assert jsonl_path.exists()
    json_lines = jsonl_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(json_lines) == 2
    parsed_records = [json.loads(line) for line in json_lines]
    assert {record["slug"] for record in parsed_records} == {"one", "two"}
    assert spreadsheet_calls == [spreadsheet_path, spreadsheet_path]


def test_runner_records_errors_and_continues(tmp_path, caplog) -> None:
    listing_url = "https://example.com/listing/"
    product_urls = [
        "https://example.com/product/invalid/",
        "https://example.com/product/valid/",
    ]

    async def fake_listing_iterator(listing: str, page, *, logger=None) -> AsyncIterator[str]:
        for product_url in product_urls:
            yield product_url

    async def fake_fetch(product_url: str) -> str:
        return "<html/>"

    def failing_extractor(html: str, product_url: str) -> Artwork:
        if product_url.endswith("invalid/"):
            raise ValueError("missing title")
        return _build_artwork(product_url, 1)

    def fake_normalizer(artwork: Artwork) -> dict[str, object]:
        return {
            "title": artwork.title,
            "slug": artwork.slug,
            "source_url": str(artwork.source_url),
            "scraped_at": artwork.scraped_at,
        }

    @asynccontextmanager
    async def fake_page_factory():
        yield object()

    jsonl_path = tmp_path / "data" / "artworks.jsonl"
    spreadsheet_path = tmp_path / "data" / "artworks.xlsx"
    spreadsheet_calls: list[str] = []

    def fake_spreadsheet_writer(artwork: Artwork, path) -> bool:
        spreadsheet_calls.append(artwork.slug)
        return True

    runner = ScraperRunner(
        listing_url=listing_url,
        fetch_html=fake_fetch,
        extractor=failing_extractor,
        normalizer=fake_normalizer,
        listing_iterator=fake_listing_iterator,
        page_factory=fake_page_factory,
        jsonl_path=jsonl_path,
        spreadsheet_path=spreadsheet_path,
        logger=logging.getLogger("scraper-runner-test"),
        spreadsheet_writer=fake_spreadsheet_writer,
    )

    with caplog.at_level(logging.ERROR):
        processed_artworks = asyncio.run(runner.crawl())

    assert len(processed_artworks) == 1
    assert runner.errors
    first_error = runner.errors[0]
    assert first_error.stage == "extract"
    assert first_error.product_url.endswith("invalid/")

    json_lines = jsonl_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(json_lines) == 1
    remaining_record = json.loads(json_lines[0])
    assert remaining_record["slug"] == "valid"
    assert spreadsheet_calls == ["valid"]

