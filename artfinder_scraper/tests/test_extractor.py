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
        "size": "46 x 46 x 2cm (unframed)",
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
    assert fields["size"] == "30 x 40 cm"
    assert fields["sold"] is True
    assert fields["image_url"] == "https://cdn.example.com/images/soft-light-main.jpg"
    assert fields["source_url"] == "https://www.artfinder.com/product/soft-light-kew-gardens-an-atmospheric-oil-painting/"


def test_missing_title_raises_value_error() -> None:
    html = "<html><body><h1>No artist reference here</h1></body></html>"

    with pytest.raises(ValueError):
        extract_artwork_fields(html, "https://example.com/item")


def test_extract_size_when_value_is_embedded_in_label_span() -> None:
    html = """
    <html>
      <body>
        <main>
          <section class=\"hero\">
            <h1>Size Study (2022) Oil painting by Lizzie Butler</h1>
            <div class=\"pricing\">
              <button type=\"button\">Add to Basket</button>
            </div>
          </section>
          <section class=\"specifications\">
            <div class=\"product-attributes\">
              <span>Size<!-- -->:<!-- --> 50 x 60 cm <!-- -->(framed)</span>
            </div>
          </section>
          <section class=\"gallery\">
            <img src=\"https://cdn.example.com/images/size-study.jpg\" alt=\"Size Study painting by Lizzie Butler\" />
          </section>
        </main>
      </body>
    </html>
    """

    fields = extract_artwork_fields(html, "https://www.artfinder.com/product/size-study/")

    assert fields["size"] == "50 x 60 cm (framed)"
