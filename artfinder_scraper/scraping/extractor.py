"""Parse artwork detail pages to extract structured metadata fields."""

from __future__ import annotations

import re
from typing import Iterable, List, Optional

from bs4 import BeautifulSoup, NavigableString, Tag

from artfinder_scraper.scraping.models import Artwork


TITLE_ARTIST = "lizzie butler"
DESCRIPTION_HEADING = "original artwork description"
ADD_TO_BASKET_TEXT = "add to basket"
SOLD_INDICATORS = ("this artwork is sold", "sold out", "sold")

YEAR_PAREN_PATTERN = re.compile(r"\(\s*\d{4}\s*\)")
MEDIUM_TRAILING_PATTERN = re.compile(
    r"\b(?:oil|acrylic|mixed media|ink|watercolour|watercolor|gouache|charcoal|pastel|print|painting|drawing|photograph|sculpture|artwork|original)\b.*$",
    flags=re.IGNORECASE,
)


def _normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _find_product_header(soup: BeautifulSoup) -> Optional[Tag]:
    product_original = soup.find("div", id="product-original")
    if not product_original:
        return None
    header = product_original.find("h1")
    if isinstance(header, Tag):
        return header
    return None


def _extract_title(soup: BeautifulSoup) -> Optional[str]:
    header = _find_product_header(soup)
    if header:
        title_span = header.find("span", class_="title")
        if title_span:
            title_text = _normalize_whitespace(
                title_span.get_text(" ", strip=True)
            )
            if title_text:
                return title_text

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


def _extract_medium(soup: BeautifulSoup) -> Optional[str]:
    header = _find_product_header(soup)
    if not header:
        return None

    subtitle_span = header.find("span", class_="subtitle")
    if not subtitle_span:
        subtitle_span = header.find("span", class_="medium")
    if not subtitle_span:
        return None

    subtitle_text = subtitle_span.get_text("\n", strip=True)
    if not subtitle_text:
        return None

    for line in subtitle_text.splitlines():
        cleaned = _normalize_whitespace(line)
        if cleaned:
            return cleaned
    return None


def _parse_artwork_description_section(
    soup: BeautifulSoup,
) -> tuple[Optional[str], Optional[str]]:
    def _has_artwork_description_class(value: object) -> bool:
        if isinstance(value, list):
            return "artwork-description" in value
        if isinstance(value, str):
            return "artwork-description" in value.split()
        return False

    description_container = soup.find(
        class_=lambda value: _has_artwork_description_class(value)
    )
    if not description_container:
        return None, None

    paragraphs: List[str] = []
    heading_seen = False
    for element in description_container.descendants:
        if isinstance(element, Tag):
            if element.name == "h5" and not heading_seen:
                heading_seen = True
                continue
            if heading_seen and element.name == "p":
                text = _normalize_whitespace(element.get_text(" ", strip=True))
                if text:
                    paragraphs.append(text)

    if not paragraphs:
        return None, None

    description_text = paragraphs[0]
    materials_text = paragraphs[1] if len(paragraphs) > 1 else None
    return description_text, materials_text


def _extract_description(soup: BeautifulSoup) -> Optional[str]:
    description_text, _ = _parse_artwork_description_section(soup)
    if description_text:
        return description_text

    heading_candidates = soup.find_all(
        string=re.compile(DESCRIPTION_HEADING, re.IGNORECASE)
    )
    for heading_text in heading_candidates:
        heading_element = (
            heading_text.parent if isinstance(heading_text, NavigableString) else heading_text
        )
        if not isinstance(heading_element, Tag):
            continue
        paragraphs: List[str] = []
        for sibling in heading_element.next_siblings:
            if isinstance(sibling, NavigableString):
                continue
            if isinstance(sibling, Tag):
                sibling_classes = sibling.get("class") or []
                if sibling.name == "h5" and "header-art" in sibling_classes:
                    break
                if sibling.find("h5", class_="header-art"):
                    break
                if sibling.name in {"h1", "h2", "h3"}:
                    break
                if sibling.find(string=re.compile("Specifications", re.IGNORECASE)):
                    # Stop once we reach the specifications/metadata panels
                    break
                if sibling.name in {"p", "div", "section"}:
                    paragraphs.extend(
                        _collect_text_nodes(sibling.find_all("p"))
                        or [_normalize_whitespace(sibling.get_text(" ", strip=True))]
                    )
        cleaned_paragraphs = [
            para for para in (_normalize_whitespace(p) for p in paragraphs) if para
        ]
        if cleaned_paragraphs:
            return "\n\n".join(cleaned_paragraphs)
    return None


def _extract_materials_used(soup: BeautifulSoup) -> Optional[str]:
    _, materials_text = _parse_artwork_description_section(soup)
    if materials_text:
        return materials_text

    for heading in soup.find_all("h5", class_="header-art"):
        heading_text = heading.get_text(" ", strip=True)
        if "material" not in heading_text.lower():
            continue

        for sibling in heading.next_siblings:
            if isinstance(sibling, NavigableString):
                continue
            if isinstance(sibling, Tag):
                if sibling.name == "p":
                    text = sibling.get_text(" ", strip=True)
                    cleaned = _normalize_whitespace(text)
                    return cleaned or None
                break
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


def extract_artwork_fields(html: str, source_url: str) -> Artwork:
    """Extract structured artwork fields from a rendered HTML page."""

    soup = BeautifulSoup(html, "html.parser")

    title = _extract_title(soup)
    if not title:
        raise ValueError("Could not locate artwork title in HTML content.")

    description = _extract_description(soup)
    price_text = _extract_price_text(soup)
    size = _extract_size_text(soup)
    medium = _extract_medium(soup)
    sold = _extract_sold_state(soup)
    image_url = _extract_image_url(soup, title)
    materials_used = _extract_materials_used(soup)

    artwork = Artwork(
        title=title,
        description=description,
        price_gbp=price_text,
        size=size,
        medium=medium,
        sold=sold,
        image_url=image_url,
        materials_used=materials_used,
        source_url=source_url,
    )
    return artwork


__all__ = ["extract_artwork_fields"]
