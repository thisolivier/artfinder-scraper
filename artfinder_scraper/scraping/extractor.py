"""Parse artwork detail pages to extract structured metadata fields."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional

from bs4 import BeautifulSoup, NavigableString, Tag


TITLE_ARTIST = "lizzie butler"
DESCRIPTION_HEADING = "original artwork description"
ADD_TO_BASKET_TEXT = "add to basket"
SOLD_INDICATORS = ("this artwork is sold", "sold out", "sold")

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
    size: str | None
    sold: bool
    image_url: str | None
    source_url: str

    def as_dict(self) -> Dict[str, object]:
        """Serialize the dataclass to a dictionary for downstream consumers."""

        return {
            "title": self.title,
            "description": self.description,
            "price_text": self.price_text,
            "size": self.size,
            "sold": self.sold,
            "image_url": self.image_url,
            "source_url": self.source_url,
        }


def _normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _apply_description_line_break_rules(text: str) -> str:
    """Remove existing line breaks while honoring explicit ``"\n"`` markers."""

    without_line_breaks = text.replace("\r\n", " ").replace("\r", " ").replace("\n", " ")
    collapsed_whitespace = re.sub(r"\s+", " ", without_line_breaks).strip()
    restored_line_breaks = collapsed_whitespace.replace("\\n", "\n")
    normalized_line_break_spacing = re.sub(r"[ \t]*\n[ \t]*", "\n", restored_line_breaks)
    return normalized_line_break_spacing.strip()


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
            combined = " ".join(cleaned_paragraphs)
            return _apply_description_line_break_rules(combined)
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


_COMMENT_FRAGMENT_PATTERN = re.compile(r"<!--\s*-->")


def _clean_size_text(text: str, *, remove_size_keyword: bool) -> str:
    """Normalize whitespace and drop common non-content fragments."""

    without_comments = _COMMENT_FRAGMENT_PATTERN.sub(" ", text)
    cleaned = without_comments
    if remove_size_keyword:
        cleaned = re.sub(r"(?i)\bsize\b", " ", cleaned)
        cleaned = cleaned.replace(":", " ")
    normalized = _normalize_whitespace(cleaned)
    return normalized


def _extract_size_text(soup: BeautifulSoup) -> Optional[str]:
    attribute_sections = soup.find_all(class_="product-attributes")
    for section in attribute_sections:
        for span in section.find_all("span"):
            label = span.get_text(" ", strip=True)
            if label.lower().startswith("size"):
                sibling_texts: List[str] = []
                for sibling in span.next_siblings:
                    if isinstance(sibling, NavigableString):
                        text = _normalize_whitespace(str(sibling))
                    elif isinstance(sibling, Tag):
                        text = _normalize_whitespace(
                            sibling.get_text(" ", strip=True)
                        )
                    else:
                        text = ""
                    if text:
                        sibling_texts.append(text)
                if sibling_texts:
                    combined = _clean_size_text(" ".join(sibling_texts), remove_size_keyword=False)
                    combined = re.sub(r"^:\s*", "", combined)
                    combined = combined.strip()
                    return combined if combined else None

                size_text = span.get_text(" ", strip=True)
                combined = _clean_size_text(size_text, remove_size_keyword=True)
                combined = combined.strip()
                return combined if combined else None
    return None


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
    size = _extract_size_text(soup)
    sold = _extract_sold_state(soup)
    image_url = _extract_image_url(soup, title)

    fields = ExtractedFields(
        title=title,
        description=description,
        price_text=price_text,
        size=size,
        sold=sold,
        image_url=image_url,
        source_url=source_url,
    )
    return fields.as_dict()


__all__ = ["extract_artwork_fields"]
