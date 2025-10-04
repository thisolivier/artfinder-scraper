"""Define dataclasses and typed models representing Artfinder entities."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.parse import urlparse

from pydantic import BaseModel, Field, HttpUrl, ValidationError, validator


def _normalize_optional_text(value: str | None) -> str | None:
    """Collapse blank strings to ``None`` for optional text fields."""

    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


class Artwork(BaseModel):
    """Typed representation of an Artfinder artwork detail page."""

    title: str = Field(..., description="Artwork title displayed on the detail page.")
    description: str | None = Field(
        default=None,
        description="Narrative description of the artwork, joined from the page paragraphs.",
    )
    price_gbp: Decimal | None = Field(
        default=None,
        description="Listed price in GBP. Normalized by removing the currency symbol and commas.",
    )
    size: str | None = Field(
        default=None,
        description="Raw size text such as '46 x 46 x 2cm (unframed)'.",
    )
    sold: bool = Field(..., description="Whether the artwork is sold or unavailable.")
    image_url: HttpUrl | None = Field(
        default=None,
        description="Primary image URL sourced from OpenGraph or the hero carousel.",
    )
    image_path: str | None = Field(
        default=None,
        description="Local filesystem path of the downloaded image, if available.",
    )
    materials_used: str | None = Field(
        default=None,
        description="Materials listed for the artwork, captured from the specification panel.",
    )
    source_url: HttpUrl = Field(..., description="Canonical URL of the artwork detail page.")
    scraped_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp when the artwork data was scraped.",
    )
    slug: str = Field(
        default=None,
        description="Slug extracted from the artwork source URL.",
    )

    @validator("title")
    def _validate_title(cls, value: str) -> str:
        """Ensure the title is populated after trimming whitespace."""

        cleaned = value.strip()
        if not cleaned:
            raise ValueError("title must not be empty")
        return cleaned

    @validator("description", "size", "image_path", "materials_used", pre=True)
    def _strip_optional_fields(cls, value: Any) -> Any:
        """Collapse blank optional strings to ``None``."""

        if isinstance(value, str):
            return _normalize_optional_text(value)
        return value

    @validator("price_gbp", pre=True)
    def _parse_price(cls, value: Any) -> Any:
        """Normalize GBP price values from strings such as '£475'."""

        if value in (None, ""):
            return None
        if isinstance(value, Decimal):
            return value
        if isinstance(value, (int, float)):
            return Decimal(str(value))
        if isinstance(value, str):
            normalized = value.strip()
            if not normalized:
                return None
            normalized = normalized.replace("£", "").replace(",", "")
            try:
                return Decimal(normalized)
            except InvalidOperation as exc:  # pragma: no cover - guard against invalid decimals
                raise ValueError("price_gbp must be a valid decimal value") from exc
        raise ValueError("Unsupported type for price_gbp")

    @validator("slug", pre=True, always=True)
    def _derive_slug(cls, value: str | None, values: dict[str, Any]) -> str:
        """Derive the slug from the source URL when not explicitly provided."""

        if value:
            slug_candidate = value.strip()
            if slug_candidate:
                return slug_candidate

        source_url = values.get("source_url")
        if source_url is None:
            raise ValueError("source_url is required to derive slug")

        parsed = urlparse(str(source_url))
        path_segments = [segment for segment in parsed.path.split("/") if segment]
        if not path_segments:
            raise ValueError("source_url does not contain a slug segment")

        try:
            product_index = path_segments.index("product")
        except ValueError as exc:
            raise ValueError("source_url must contain a /product/<slug>/ path") from exc

        if len(path_segments) <= product_index + 1:
            raise ValueError("source_url does not include a slug after /product/")

        slug_candidate = path_segments[product_index + 1]

        slug_candidate = slug_candidate.strip()
        if not slug_candidate:
            raise ValueError("slug could not be derived from source_url")
        return slug_candidate

    class Config:
        anystr_strip_whitespace = True
        allow_mutation = False
        validate_assignment = True


__all__ = ["Artwork", "ValidationError"]
