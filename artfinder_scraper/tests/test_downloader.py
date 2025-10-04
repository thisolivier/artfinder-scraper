"""Unit tests for the artwork image downloader."""

from __future__ import annotations

import urllib.error
from dataclasses import dataclass
from typing import Dict

import pytest

from artfinder_scraper.scraping.downloader import (
    ArtworkImageDownloader,
    ImageDownloadError,
)
from artfinder_scraper.scraping.models import Artwork


@dataclass
class DummyResponse:
    """Minimal HTTP response stub for downloader tests."""

    data: bytes
    headers: Dict[str, str]

    def read(self) -> bytes:
        return self.data

    def info(self) -> Dict[str, str]:  # pragma: no cover - compatibility hook
        return self.headers

    def __enter__(self) -> "DummyResponse":
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:  # pragma: no cover - context protocol
        return None


def _make_artwork(image_url: str | None = "https://cdn.example.com/image.jpg") -> Artwork:
    return Artwork(
        title="Example",
        description=None,
        price_gbp=None,
        size=None,
        sold=False,
        image_url=image_url,
        source_url="https://www.artfinder.com/product/example-artwork/",
    )


def test_download_artwork_image_retries_then_succeeds(tmp_path) -> None:
    """The downloader should retry failed requests with backoff delays."""

    request_urls: list[str] = []
    sleep_calls: list[float] = []

    def fake_opener(request):
        request_urls.append(request.full_url)
        if len(request_urls) == 1:
            raise urllib.error.URLError("temporary network issue")
        return DummyResponse(data=b"binary-image", headers={"Content-Type": "image/jpeg"})

    def fake_sleep(duration: float) -> None:
        sleep_calls.append(duration)

    downloader = ArtworkImageDownloader(
        max_retries=3,
        backoff_factor=0.2,
        output_directory=tmp_path,
        opener=fake_opener,
        sleep_function=fake_sleep,
    )

    artwork = _make_artwork()
    updated_artwork = downloader.download_artwork_image(artwork)

    assert request_urls == ["https://cdn.example.com/image.jpg", "https://cdn.example.com/image.jpg"]
    assert sleep_calls == [0.2]
    expected_path = tmp_path / "example-artwork.jpg"
    assert updated_artwork.image_path == str(expected_path)
    assert expected_path.read_bytes() == b"binary-image"


def test_download_artwork_image_rejects_invalid_content_type(tmp_path) -> None:
    """Non-image responses should raise a validation error."""

    def fake_opener(request):
        return DummyResponse(data=b"not-image", headers={"Content-Type": "text/html"})

    downloader = ArtworkImageDownloader(
        output_directory=tmp_path,
        opener=fake_opener,
    )

    with pytest.raises(ImageDownloadError) as error_info:
        downloader.download_artwork_image(_make_artwork())

    assert "Content type" in str(error_info.value)
    assert list(tmp_path.iterdir()) == []


def test_download_artwork_image_returns_original_when_missing_url(tmp_path) -> None:
    """Artworks without an image URL should be skipped without errors."""

    downloader = ArtworkImageDownloader(output_directory=tmp_path)

    artwork = _make_artwork(image_url=None)
    result = downloader.download_artwork_image(artwork)

    assert result is artwork
    assert list(tmp_path.iterdir()) == []


def test_download_artwork_image_rejects_empty_payload(tmp_path) -> None:
    """Zero-byte downloads must be treated as failures."""

    def fake_opener(request):
        return DummyResponse(data=b"", headers={"Content-Type": "image/png"})

    downloader = ArtworkImageDownloader(
        output_directory=tmp_path,
        opener=fake_opener,
    )

    with pytest.raises(ImageDownloadError) as error_info:
        downloader.download_artwork_image(_make_artwork())

    assert "empty" in str(error_info.value)
    assert list(tmp_path.iterdir()) == []
