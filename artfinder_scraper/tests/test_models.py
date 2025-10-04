"""Unit tests for the Pydantic models."""

from __future__ import annotations

from decimal import Decimal

import pytest

from artfinder_scraper.scraping.models import Artwork, ValidationError


def test_artwork_model_parses_price_and_slug() -> None:
    artwork = Artwork(
        title="Evening Glow",
        description="Warm tones capture the final light of the day.",
        price_gbp="£1,234",
        size="50 x 70 cm",
        sold=False,
        image_url="https://cdn.example.com/images/evening-glow.jpg",
        materials_used="Oil on canvas ",
        source_url="https://www.artfinder.com/product/evening-glow-sample/",
    )

    assert artwork.price_gbp == Decimal("1234")
    assert artwork.slug == "evening-glow-sample"
    assert artwork.scraped_at.tzinfo is not None
    assert artwork.materials_used == "Oil on canvas"


@pytest.mark.parametrize(
    "invalid_price",
    ["not-a-number", object(), []],
)
def test_artwork_model_rejects_invalid_price_types(invalid_price: object) -> None:
    with pytest.raises(ValidationError):
        Artwork(
            title="Skyline",
            description=None,
            price_gbp=invalid_price,
            size=None,
            sold=True,
            image_url="https://cdn.example.com/images/skyline.jpg",
            source_url="https://www.artfinder.com/product/skyline-study/",
        )


def test_artwork_model_requires_slug_in_source_url() -> None:
    with pytest.raises(ValidationError):
        Artwork(
            title="Misty Morning",
            description="",
            price_gbp=None,
            size=None,
            sold=False,
            image_url="https://cdn.example.com/images/misty-morning.jpg",
            source_url="https://www.artfinder.com/artist/example-artist/",
        )
