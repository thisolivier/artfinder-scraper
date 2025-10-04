"""Standardize scraped values and enforce consistent schema shapes."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Mapping

from .models import Artwork


def _artwork_to_mapping(artwork: Artwork) -> dict[str, Any]:
    """Return a dictionary representation of ``artwork`` suitable for JSON serialization."""

    if hasattr(artwork, "model_dump"):
        return artwork.model_dump()
    return artwork.dict()  # type: ignore[attr-defined]


def _convert_json_safe(value: Any) -> Any:
    """Convert ``value`` into a JSON-serializable representation."""

    if isinstance(value, dict):
        return {key: _convert_json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_convert_json_safe(item) for item in value]
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def normalize_artwork(artwork: Artwork, extra_fields: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Return a JSON-serializable mapping for ``artwork``.

    The returned dictionary merges the standard artwork fields with any
    ``extra_fields`` provided by upstream processing steps. Optional values are
    preserved so that downstream archives retain the original record fidelity.
    """

    payload = _artwork_to_mapping(artwork)
    if extra_fields:
        payload.update(extra_fields)
    return _convert_json_safe(payload)


__all__ = ["normalize_artwork"]
