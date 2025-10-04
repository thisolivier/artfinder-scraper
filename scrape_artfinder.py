"""Command-line entry point for the Artfinder scraper."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer

from artfinder_scraper.scraping.browsers import fetch_page_html
from artfinder_scraper.scraping.downloader import (
    ArtworkImageDownloader,
    ImageDownloadError,
)
from artfinder_scraper.scraping.extractor import extract_artwork_fields


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


def main() -> None:
    """Run the Typer CLI application."""

    app()


if __name__ == "__main__":
    main()
