"""Command-line entry point for the Artfinder scraper."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Iterable, Optional, Set
from urllib.parse import urlparse

import typer

from artfinder_scraper.scraping.browsers import chromium_page, fetch_page_html
from artfinder_scraper.scraping.downloader import (
    ArtworkImageDownloader,
    ImageDownloadError,
)
from artfinder_scraper.scraping.extractor import extract_artwork_fields
from artfinder_scraper.scraping.indexer import collect_listing_product_links
from artfinder_scraper.scraping.runner import DEFAULT_LISTING_URL, ScraperRunner


try:
    from pprint import pformat
except ImportError:  # pragma: no cover - stdlib availability
    pformat = lambda obj: str(obj)

app = typer.Typer(help="Utility commands for interacting with the Artfinder scraper.")


@app.callback()
def cli_root() -> None:
    """Root command group for scraper utilities."""



@app.command("fetch-item")
def fetch_item(
    url: str = typer.Argument(..., help="Artwork detail page URL to download."),
    output: Optional[Path] = typer.Option(
        None,
        "--out",
        "-o",
        help="File to write the rendered HTML to.",
    ),
    download_image: bool = typer.Option(
        False,
        "--download-image",
        help="Download the primary artwork image after extraction.",
        is_flag=True,
    ),
) -> None:
    """Fetch a single item URL and emit the rendered HTML."""

    html_content = fetch_page_html(url)
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(html_content, encoding="utf-8")
        typer.echo(f"Saved HTML to {output}")

    artwork = extract_artwork_fields(html_content, url)

    if download_image:
        downloader = ArtworkImageDownloader()
        try:
            artwork = downloader.download_artwork_image(artwork)
            if artwork.image_path:
                typer.echo(f"Saved image to {artwork.image_path}")
            else:
                typer.echo("Artwork did not include an image URL; nothing downloaded.")
        except ImageDownloadError as error:
            typer.echo(f"Failed to download image: {error}", err=True)

    typer.echo("Parsed fields:")
    if hasattr(artwork, "model_dump"):
        serialized = artwork.model_dump()
    else:  # pragma: no cover - pydantic v1 fallback
        serialized = artwork.dict()
    typer.echo(pformat(serialized))


@app.command("list-page")
def list_page(
    url: str = typer.Argument(
        ..., help="Listing page URL to enumerate product links from."
    ),
) -> None:
    """Print the product URLs discovered on a listing page."""

    async def _gather() -> list[str]:
        async with chromium_page() as page:
            return await collect_listing_product_links(url, page)

    product_links = asyncio.run(_gather())
    if not product_links:
        typer.echo("No product URLs found.")
        return

    for product_url in product_links:
        typer.echo(product_url)


def _create_runner(
    *,
    listing_url: str,
    jsonl_path: Optional[Path],
    rate_limit: float,
    dry_run: bool,
    skip_slugs: Iterable[str] | None = None,
) -> ScraperRunner:
    return ScraperRunner(
        listing_url=listing_url,
        jsonl_path=jsonl_path,
        rate_limit_seconds=rate_limit,
        skip_slugs=skip_slugs,
        persist_outputs=not dry_run,
    )


def _print_summary(runner: ScraperRunner, processed_count: int) -> None:
    if runner.persist_outputs:
        typer.echo(
            f"Processed {processed_count} artwork(s); records appended to {runner.jsonl_path}"
        )
    else:
        typer.echo(
            f"Processed {processed_count} artwork(s); dry-run mode left existing files untouched"
        )

    if runner.errors:
        typer.echo("Encountered the following errors:", err=True)
        for error in runner.errors:
            typer.echo(f"- [{error.stage}] {error.product_url}: {error.message}", err=True)


def _load_processed_slugs(jsonl_path: Path) -> Set[str]:
    if not jsonl_path.exists():
        return set()

    processed_slugs: set[str] = set()
    with jsonl_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            text = line.strip()
            if not text:
                continue
            try:
                payload = json.loads(text)
            except json.JSONDecodeError:
                continue
            slug = payload.get("slug")
            if isinstance(slug, str) and slug.strip():
                processed_slugs.add(slug.strip())
                continue
            source_url = payload.get("source_url")
            if isinstance(source_url, str):
                parsed = urlparse(source_url)
                slug_candidate = parsed.path.split("/product/", 1)[-1].strip("/") if "/product/" in parsed.path else ""
                if slug_candidate:
                    processed_slugs.add(slug_candidate)
    return processed_slugs


def _execute_pipeline(runner: ScraperRunner, limit: Optional[int]) -> None:
    processed_artworks = runner.run(max_items=limit)
    _print_summary(runner, len(processed_artworks))


def _resolve_jsonl_path(jsonl_path: Optional[Path]) -> Path:
    return jsonl_path or ScraperRunner.DEFAULT_JSONL_PATH


@app.command("run")
def run_pipeline(
    limit: Optional[int] = typer.Option(
        None,
        "--limit",
        help="Number of items to process before stopping.",
    ),
    listing_url: str = typer.Option(
        DEFAULT_LISTING_URL,
        "--listing-url",
        help="Listing URL to crawl for product links.",
    ),
    jsonl_path: Optional[Path] = typer.Option(
        None,
        "--jsonl-path",
        help="Location where JSONL records should be written.",
    ),
    rate_limit: float = typer.Option(
        1.0,
        "--rate-limit",
        help="Minimum delay (in seconds) between detail page fetches.",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Process items without downloading images or writing JSONL/spreadsheet files.",
        is_flag=True,
    ),
) -> None:
    """Execute the end-to-end scraping pipeline for a limited number of items."""

    runner = _create_runner(
        listing_url=listing_url,
        jsonl_path=jsonl_path,
        rate_limit=rate_limit,
        dry_run=dry_run,
        skip_slugs=None,
    )
    _execute_pipeline(runner, limit)


@app.command("resume")
def resume_pipeline(
    limit: Optional[int] = typer.Option(
        None,
        "--limit",
        help="Number of new items to process before stopping.",
    ),
    listing_url: str = typer.Option(
        DEFAULT_LISTING_URL,
        "--listing-url",
        help="Listing URL to crawl for product links.",
    ),
    jsonl_path: Optional[Path] = typer.Option(
        None,
        "--jsonl-path",
        help="Path to the JSONL archive generated by previous runs.",
    ),
    rate_limit: float = typer.Option(
        1.0,
        "--rate-limit",
        help="Minimum delay (in seconds) between detail page fetches.",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Continue the crawl without writing files; useful for verifying resume logic.",
        is_flag=True,
    ),
) -> None:
    """Continue the scraping pipeline while skipping previously processed slugs."""

    resolved_jsonl_path = _resolve_jsonl_path(jsonl_path)
    processed_slugs = _load_processed_slugs(resolved_jsonl_path)
    if processed_slugs:
        typer.echo(f"Loaded {len(processed_slugs)} processed slug(s) from {resolved_jsonl_path}")
    else:
        typer.echo(f"No processed slug information found in {resolved_jsonl_path}; starting fresh")

    runner = _create_runner(
        listing_url=listing_url,
        jsonl_path=jsonl_path,
        rate_limit=rate_limit,
        dry_run=dry_run,
        skip_slugs=processed_slugs,
    )
    _execute_pipeline(runner, limit)


def main() -> None:
    """Run the Typer CLI application."""

    app()


if __name__ == "__main__":
    main()
