"""Unit tests for the detail-page extractor."""

from __future__ import annotations

from pathlib import Path

import pytest

from artfinder_scraper.scraping.extractor import extract_artwork_fields

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.mark.parametrize(
    "fixture_name",
    ["windswept_walk.html", "soft_light_sold.html"],
)
def test_fixtures_exist(fixture_name: str) -> None:
    """Ensure fixtures referenced in the tests are present on disk."""

    fixture_path = FIXTURES_DIR / fixture_name
    assert fixture_path.exists(), f"Missing fixture {fixture_name}"


def _load_fixture(name: str) -> str:
    return (FIXTURES_DIR / name).read_text(encoding="utf-8")


def test_extract_artwork_fields_for_available_item() -> None:
    html = _load_fixture("windswept_walk.html")

    fields = extract_artwork_fields(html, "https://www.artfinder.com/product/a-windswept-walk/")

    assert fields == {
        "title": "A Windswept Walk",
        "description": (
            "This windswept walk captures the energy of the coastline.\n\n"
            "Layers of oil paint bring movement to the clouds and surf."
        ),
        "price_text": "£475",
        "size_raw": "Size: 46 x 46 x 2cm (unframed)",
        "width_cm": 46.0,
        "height_cm": 46.0,
        "depth_cm": 2.0,
        "sold": False,
        "image_url": "https://cdn.example.com/images/windswept-walk.jpg",
        "source_url": "https://www.artfinder.com/product/a-windswept-walk/",
    }


def test_extract_artwork_fields_handles_sold_item_with_missing_depth() -> None:
    html = _load_fixture("soft_light_sold.html")

    fields = extract_artwork_fields(html, "https://www.artfinder.com/product/soft-light-kew-gardens-an-atmospheric-oil-painting/")

    assert fields["title"] == "Soft Light"
    assert fields["description"] == "Delicate hues describe the gentle evening light across the bay."
    assert fields["price_text"] is None
    assert fields["size_raw"] == "Size: 30 x 40 cm"
    assert fields["width_cm"] == pytest.approx(30.0)
    assert fields["height_cm"] == pytest.approx(40.0)
    assert fields["depth_cm"] is None
    assert fields["sold"] is True
    assert fields["image_url"] == "https://cdn.example.com/images/soft-light-main.jpg"
    assert fields["source_url"] == "https://www.artfinder.com/product/soft-light-kew-gardens-an-atmospheric-oil-painting/"


def test_missing_title_raises_value_error() -> None:
    html = "<html><body><h1>No artist reference here</h1></body></html>"

    with pytest.raises(ValueError):
        extract_artwork_fields(html, "https://example.com/item")
