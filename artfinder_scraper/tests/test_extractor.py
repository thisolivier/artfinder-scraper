"""Unit tests for the detail-page extractor."""

from __future__ import annotations

from pathlib import Path

import pytest

from artfinder_scraper.scraping.extractor import extract_artwork_fields
from artfinder_scraper.scraping.models import Artwork, ValidationError

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

    artwork = extract_artwork_fields(
        html, "https://www.artfinder.com/product/a-windswept-walk/"
    )

    assert isinstance(artwork, Artwork)
    assert artwork.title == "A Windswept Walk"
    assert artwork.description == (
        "This windswept walk captures the energy of the coastline.\n\n"
        "Layers of oil paint bring movement to the clouds and surf."
    )
    assert artwork.price_gbp and artwork.price_gbp == 475
    assert artwork.size == "46 x 46 x 2cm (unframed)"
    assert artwork.sold is False
    assert (
        str(artwork.image_url)
        == "https://cdn.example.com/images/windswept-walk.jpg"
    )
    assert (
        str(artwork.source_url)
        == "https://www.artfinder.com/product/a-windswept-walk/"
    )
    assert artwork.slug == "a-windswept-walk"
    assert artwork.scraped_at is not None


def test_extract_artwork_fields_handles_sold_item_with_missing_depth() -> None:
    html = _load_fixture("soft_light_sold.html")

    artwork = extract_artwork_fields(
        html,
        "https://www.artfinder.com/product/soft-light-kew-gardens-an-atmospheric-oil-painting/",
    )

    assert artwork.title == "Soft Light"
    assert (
        artwork.description
        == "Delicate hues describe the gentle evening light across the bay."
    )
    assert artwork.price_gbp is None
    assert artwork.size == "30 x 40 cm"
    assert artwork.sold is True
    assert (
        str(artwork.image_url)
        == "https://cdn.example.com/images/soft-light-main.jpg"
    )
    assert (
        str(artwork.source_url)
        == "https://www.artfinder.com/product/soft-light-kew-gardens-an-atmospheric-oil-painting/"
    )


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

    artwork = extract_artwork_fields(html, "https://www.artfinder.com/product/size-study/")

    assert artwork.size == "50 x 60 cm (framed)"


def test_invalid_source_url_raises_validation_error() -> None:
    html = """
    <html>
      <body>
        <h1>Shoreline (2024) Oil painting by Lizzie Butler</h1>
      </body>
    </html>
    """

    with pytest.raises(ValidationError):
        extract_artwork_fields(html, "not-a-valid-url")
