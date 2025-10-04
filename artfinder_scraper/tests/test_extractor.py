"""Unit tests for the detail-page extractor."""

from __future__ import annotations

from pathlib import Path

import pytest

from artfinder_scraper.scraping.extractor import extract_artwork_fields
from artfinder_scraper.scraping.models import Artwork, ValidationError

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.mark.parametrize(
    "fixture_name",
    [
        "windswept_walk.html",
        "soft_light_sold.html",
        "sounds_of_the_sea.html",
    ],
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
        html, "https://www.artfinder.com/product/echoes-of-dawn-canvas/"
    )

    assert isinstance(artwork, Artwork)
    assert artwork.title == "Echoes of Dawn"
    assert artwork.description == (
        "Soft apricot light pools along the shoreline at sunrise.\n\n"
        "Feathery brushwork maps the breeze through distant grasses."
    )
    assert artwork.price_gbp and artwork.price_gbp == 475
    assert artwork.size == "46 x 46 x 2cm (unframed)"
    assert artwork.medium == "Oil painting"
    assert artwork.sold is False
    assert (
        str(artwork.image_url)
        == "https://cdn.example.com/images/windswept-walk.jpg"
    )
    assert (
        artwork.materials_used
        == "Oil on board with added texture"
    )
    assert (
        str(artwork.source_url)
        == "https://www.artfinder.com/product/echoes-of-dawn-canvas/"
    )
    assert artwork.slug == "echoes-of-dawn-canvas"
    assert artwork.scraped_at is not None


def test_extract_artwork_fields_handles_sold_item_with_missing_depth() -> None:
    html = _load_fixture("soft_light_sold.html")

    artwork = extract_artwork_fields(
        html,
        "https://www.artfinder.com/product/lantern-glow-atrium-study/",
    )

    assert artwork.title == "Lantern Glow"
    assert (
        artwork.description
        == "Amber reflections drift across still water beside the quay."
    )
    assert artwork.price_gbp is None
    assert artwork.size == "30 x 40 cm"
    assert artwork.medium == "Original painting"
    assert artwork.sold is True
    assert (
        str(artwork.image_url)
        == "https://cdn.example.com/images/soft-light-main.jpg"
    )
    assert (
        artwork.materials_used
        == "Oil on canvas with silver leaf highlights"
    )
    assert (
        str(artwork.source_url)
        == "https://www.artfinder.com/product/lantern-glow-atrium-study/"
    )


def test_extract_artwork_fields_handles_artwork_description_section() -> None:
    html = _load_fixture("sounds_of_the_sea.html")

    artwork = extract_artwork_fields(
        html, "https://www.artfinder.com/product/sounds-of-the-sea-a4bae/"
    )

    assert artwork.title == "Sounds of the Sea"
    assert (
        artwork.description
        == "A shimmering horizon captures the rhythm of the shoreline."
    )
    assert artwork.medium == "Oil on canvas"
    assert (
        artwork.materials_used
        == "Oil, pastel and charcoal layered on primed canvas."
    )


def test_description_extraction_stops_before_materials_section() -> None:
    html = """
    <html>
      <body>
        <main>
          <section class=\"hero\">
            <h1>Velvet Mirage (2024) Oil painting by Example Artist</h1>
          </section>
          <article>
            <h2>Original artwork description</h2>
            <p>Sunlit ribbons shimmer across a calm tidal plain.</p>
            <h5 class=\"header-art\">Materials used</h5>
            <p><a href=\"/medium/oil\">Oil</a> and <a href=\"/medium/wax\">wax</a> on panel</p>
          </article>
        </main>
      </body>
    </html>
    """

    artwork = extract_artwork_fields(
        html,
        "https://www.artfinder.com/product/driftwood-dreamscape/",
    )

    assert artwork.description == "Sunlit ribbons shimmer across a calm tidal plain."
    assert artwork.materials_used == "Oil and wax on panel"


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
            <h1>Silent Meadow (2022) Oil painting by Example Artist</h1>
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
            <img src=\"https://cdn.example.com/images/size-study.jpg\" alt=\"Silent Meadow painting by Example Artist\" />
          </section>
        </main>
      </body>
    </html>
    """

    artwork = extract_artwork_fields(html, "https://www.artfinder.com/product/size-study-demo/")

    assert artwork.size == "50 x 60 cm (framed)"


def test_invalid_source_url_raises_validation_error() -> None:
    html = """
    <html>
      <body>
        <h1>Prism Tide (2024) Oil painting by Example Artist</h1>
      </body>
    </html>
    """

    with pytest.raises(ValidationError):
        extract_artwork_fields(html, "not-a-valid-url")
