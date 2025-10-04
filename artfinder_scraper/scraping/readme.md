# Scraping module

The `artfinder_scraper.scraping` package bundles the components used by the
command-line workflow to download and process Artfinder artwork pages.

* `browsers.py` exposes `fetch_page_html`, a thin Playwright wrapper that
  requests a detail page with the required user agent and politeness delay.
* `extractor.py` parses the rendered HTML into a dictionary of raw field
  values that higher-level flows can normalize later on, including
  consolidating size metadata from `product-attributes` spans while
  stripping inert comment fragments from the collected text. It also
  captures the "materials used" copy surfaced beneath the dedicated
  `header-art` heading even when other `header-art` elements precede it,
  flattening hyperlinks to plain text. The extractor now materializes an
  `Artwork` pydantic model so that downstream components receive
  validated, typed data.
* `models.py` defines the `Artwork` schema used across the scraping
  workflow, handling GBP price normalization, slug derivation from
  `/product/<slug>/` URLs, and timestamping when a record was scraped.
* `indexer.py` navigates listing pages with a Playwright page handle,
  iterates through pagination, and yields canonical `/product/` links
  while removing duplicates across pages and logging crawl progress.
* `downloader.py`, `normalize.py`, `spreadsheet.py`, and
  `runner.py` are placeholders for the upcoming pagination, normalization, and
  orchestration layers described in the project spec.
* `downloader.py` provides `ArtworkImageDownloader`, a retrying HTTP client
  that stores validated image responses under `out/images/` while populating
  each `Artwork.image_path` for downstream consumers. `indexer.py`,
  `normalize.py`, `spreadsheet.py`, and `runner.py` remain placeholders for the
  upcoming pagination, normalization, and orchestration layers described in the
  project spec.

## Fetching a single artwork

The root CLI script wires the browser helper with both the extractor and the
listing indexer. Use the `fetch-item` command to download an artwork detail
page, optionally save the HTML, and pretty-print the parsed fields:

```bash
python scrape_artfinder.py fetch-item \
  https://www.artfinder.com/product/soft-light-kew-gardens-an-atmospheric-oil-painting/
```

Pass `--out path/to/file.html` to capture the HTML alongside the parsed output.

Invoke the `list-page` command to enumerate all product URLs that appear on a
listing:

```bash
python scrape_artfinder.py list-page \
  https://www.artfinder.com/artist/lizziebutler/sort-newest/
```

Links are normalized and deduplicated before printing so downstream crawlers
can feed them directly into the detail-page workflow.
