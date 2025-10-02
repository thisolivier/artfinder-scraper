"""Parse artwork detail pages to extract structured metadata fields."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional

from bs4 import BeautifulSoup, NavigableString, Tag


TITLE_ARTIST = "lizzie butler"
DESCRIPTION_HEADING = "original artwork description"
SIZE_PREFIX = "size:"
ADD_TO_BASKET_TEXT = "add to basket"
SOLD_INDICATORS = ("this artwork is sold", "sold out", "sold")

SIZE_PATTERN = re.compile(
    r"(?P<width>\d+(?:\.\d+)?)\s*x\s*(?P<height>\d+(?:\.\d+)?)(?:\s*x\s*(?P<depth>\d+(?:\.\d+)?))?\s*cm",
    flags=re.IGNORECASE,
)

YEAR_PAREN_PATTERN = re.compile(r"\(\s*\d{4}\s*\)")
MEDIUM_TRAILING_PATTERN = re.compile(
    r"\b(?:oil|acrylic|mixed media|ink|watercolour|watercolor|gouache|charcoal|pastel|print|painting|drawing|photograph|sculpture|artwork|original)\b.*$",
    flags=re.IGNORECASE,
)


@dataclass(frozen=True)
class ExtractedFields:
    """Container representing the parsed raw values from the artwork page."""

    title: str
    description: str | None
    price_text: str | None
    size_raw: str | None
    width_cm: float | None
    height_cm: float | None
    depth_cm: float | None
    sold: bool
    image_url: str | None
    source_url: str

    def as_dict(self) -> Dict[str, object]:
        """Serialize the dataclass to a dictionary for downstream consumers."""

        return {
            "title": self.title,
            "description": self.description,
            "price_text": self.price_text,
            "size_raw": self.size_raw,
            "width_cm": self.width_cm,
            "height_cm": self.height_cm,
            "depth_cm": self.depth_cm,
            "sold": self.sold,
            "image_url": self.image_url,
            "source_url": self.source_url,
        }


def _normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _extract_title(soup: BeautifulSoup) -> Optional[str]:
    candidate_headers: Iterable[Tag] = soup.find_all(["h1", "h2"])
    for header in candidate_headers:
        text = header.get_text(strip=True)
        if TITLE_ARTIST in text.lower():
            prefix = text.split(" by ", 1)[0]
            prefix = YEAR_PAREN_PATTERN.sub("", prefix)
            prefix = MEDIUM_TRAILING_PATTERN.sub("", prefix).strip()
            cleaned = _normalize_whitespace(prefix)
            if cleaned:
                return cleaned
    return None


def _collect_text_nodes(nodes: Iterable[Tag]) -> List[str]:
    pieces: List[str] = []
    for node in nodes:
        text = node.get_text(" ", strip=True)
        if text:
            pieces.append(text)
    return pieces


def _extract_description(soup: BeautifulSoup) -> Optional[str]:
    heading_candidates = soup.find_all(string=re.compile(DESCRIPTION_HEADING, re.IGNORECASE))
    for heading_text in heading_candidates:
        heading_element = heading_text.parent if isinstance(heading_text, NavigableString) else heading_text
        if not isinstance(heading_element, Tag):
            continue
        paragraphs: List[str] = []
        for sibling in heading_element.next_siblings:
            if isinstance(sibling, NavigableString):
                continue
            if isinstance(sibling, Tag):
                if sibling.name in {"h1", "h2", "h3"}:
                    break
                if sibling.find(string=re.compile("Specifications", re.IGNORECASE)):
                    # Stop once we reach the specifications/metadata panels
                    break
                if sibling.name in {"p", "div", "section"}:
                    paragraphs.extend(_collect_text_nodes(sibling.find_all("p")) or [_normalize_whitespace(sibling.get_text(" ", strip=True))])
        cleaned_paragraphs = [para for para in (_normalize_whitespace(p) for p in paragraphs) if para]
        if cleaned_paragraphs:
            return "\n\n".join(cleaned_paragraphs)
    return None


def _extract_price_text(soup: BeautifulSoup) -> Optional[str]:
    currency_pattern = re.compile(r"£\s*[0-9][0-9,]*", re.IGNORECASE)
    for element in soup.find_all(string=currency_pattern):
        text = _normalize_whitespace(element)
        if text:
            match = currency_pattern.search(text)
            if match:
                # Return the full matched currency expression (e.g., £475)
                return match.group(0).replace(" ", "")
    return None


def _extract_size_block(soup: BeautifulSoup) -> Optional[str]:
    size_pattern = re.compile(SIZE_PREFIX, re.IGNORECASE)
    for element in soup.find_all(string=size_pattern):
        text = _normalize_whitespace(element)
        if SIZE_PREFIX in text.lower():
            return text
    return None


def _parse_dimensions(size_text: str | None) -> tuple[float | None, float | None, float | None]:
    if not size_text:
        return (None, None, None)
    match = SIZE_PATTERN.search(size_text)
    if not match:
        return (None, None, None)
    width = float(match.group("width")) if match.group("width") else None
    height = float(match.group("height")) if match.group("height") else None
    depth = float(match.group("depth")) if match.group("depth") else None
    return (width, height, depth)


def _extract_sold_state(soup: BeautifulSoup) -> bool:
    page_text = soup.get_text(" ", strip=True).lower()
    for indicator in SOLD_INDICATORS:
        if indicator in page_text:
            return True
    add_to_basket = soup.find(string=re.compile(ADD_TO_BASKET_TEXT, re.IGNORECASE))
    return add_to_basket is None


def _extract_image_url(soup: BeautifulSoup, title: Optional[str]) -> Optional[str]:
    meta_tag = soup.find("meta", attrs={"property": "og:image"})
    if meta_tag and meta_tag.get("content"):
        return meta_tag["content"].strip()

    if title:
        img = soup.find("img", attrs={"alt": re.compile(re.escape(title), re.IGNORECASE)})
        if img and img.get("src"):
            return img["src"].strip()

    img_tag = soup.find("img", src=True)
    if img_tag:
        return img_tag["src"].strip()
    return None


def extract_artwork_fields(html: str, source_url: str) -> Dict[str, object]:
    """Extract raw artwork fields from a rendered HTML page."""

    soup = BeautifulSoup(html, "html.parser")

    title = _extract_title(soup)
    if not title:
        raise ValueError("Could not locate artwork title in HTML content.")

    description = _extract_description(soup)
    price_text = _extract_price_text(soup)
    size_raw = _extract_size_block(soup)
    width_cm, height_cm, depth_cm = _parse_dimensions(size_raw)
    sold = _extract_sold_state(soup)
    image_url = _extract_image_url(soup, title)

    fields = ExtractedFields(
        title=title,
        description=description,
        price_text=price_text,
        size_raw=size_raw,
        width_cm=width_cm,
        height_cm=height_cm,
        depth_cm=depth_cm,
        sold=sold,
        image_url=image_url,
        source_url=source_url,
    )
    return fields.as_dict()


__all__ = ["extract_artwork_fields"]
