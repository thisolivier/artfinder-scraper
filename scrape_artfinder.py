"""Command-line entry point for the Artfinder scraper."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer

from artfinder_scraper.scraping.browsers import fetch_page_html
from artfinder_scraper.scraping.extractor import extract_artwork_fields


try:
    from pprint import pformat
except ImportError:  # pragma: no cover - stdlib availability
    pformat = lambda obj: str(obj)

app = typer.Typer(help="Utility commands for interacting with the Artfinder scraper.")


@app.command("fetch-item")
def fetch_item(
    url: str = typer.Argument(..., help="Artwork detail page URL to download."),
    output: Optional[Path] = typer.Option(
        None,
        "--out",
        "-o",
        help="File to write the rendered HTML to.",
    ),
) -> None:
    """Fetch a single item URL and emit the rendered HTML."""

    html_content = fetch_page_html(url)
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(html_content, encoding="utf-8")
        typer.echo(f"Saved HTML to {output}")

    parsed_fields = extract_artwork_fields(html_content, url)
    typer.echo("Parsed fields:")
    typer.echo(pformat(parsed_fields))


def main() -> None:
    """Run the Typer CLI application."""

    app()


if __name__ == "__main__":
    main()
