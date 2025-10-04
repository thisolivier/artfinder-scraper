# Scraping module

The `artfinder_scraper.scraping` package bundles the components used by the
command-line workflow to download and process Artfinder artwork pages.

* `browsers.py` exposes `fetch_page_html`, a thin Playwright wrapper that
  requests a detail page with the required user agent and politeness delay.
* `extractor.py` parses the rendered HTML into a dictionary of raw field
  values that higher-level flows can normalize later on. It now targets the
  dedicated `#product-original h1 .title` span for the artwork name,
  captures the medium from the paired subtitle block, and reads description
  plus materials copy from the structured
  `.artwork-description` section while still falling back to legacy markup.
  Marketing boilerplate beginning with sentences such as “This piece is
  signed”, “All artwork is carefully wrapped”, “Ready to hang”, or “Painted in
  oil on a stretched canvas.” is trimmed so only the artist's copy remains. The
  extractor continues consolidating size metadata from
  `product-attributes` spans, stripping inert comment fragments from the
  collected text, and flattening hyperlinks to plain text. Parsed values are
  materialized as an `Artwork` pydantic model so downstream components receive
  validated, typed data.
* `models.py` defines the `Artwork` schema used across the scraping
  workflow, handling GBP price normalization, slug derivation from
  `/product/<slug>/` URLs, and timestamping when a record was scraped.
* `indexer.py` navigates listing pages with a Playwright page handle,
  iterates through pagination, and yields canonical `/product/` links
  while removing duplicates across pages and logging crawl progress.
* `downloader.py` provides `ArtworkImageDownloader`, a retrying HTTP client
  that stores validated image responses under `out/images/` while populating
  each `Artwork.image_path` for downstream consumers.
* `normalize.py` contains helpers that convert the pydantic `Artwork` model
  into JSON-serializable dictionaries for archival storage.
* `spreadsheet.py` exposes helpers that maintain the Excel catalog. It creates
  the workbook when missing, enforces the canonical column order, embeds
  thumbnail images, and skips rows whose slug or title already exists so reruns
  do not produce duplicates.
* `runner.py` implements `ScraperRunner`, the orchestrator that walks listing
  pagination, fetches detail pages, normalizes the resulting records, downloads
  imagery, and appends JSONL entries. The CLI exposes a `run` command wired to
  this class so the entire flow can be exercised from the terminal.

## Fetching a single artwork

The root CLI script wires the browser helper with both the extractor and the
listing indexer. Use the `fetch-item` command to download an artwork detail
page, optionally save the HTML, and pretty-print the parsed fields:

```bash
python scrape_artfinder.py fetch-item \
  https://www.artfinder.com/product/lantern-glow-atrium-study/
```

Pass `--out path/to/file.html` to capture the HTML alongside the parsed output.

Invoke the `list-page` command to enumerate all product URLs that appear on a
listing:

```bash
python scrape_artfinder.py list-page \
  https://www.artfinder.com/artist/example-artist/sort-newest/
```

Links are normalized and deduplicated before printing so downstream crawlers
can feed them directly into the detail-page workflow.

### Orchestration commands

Run `python scrape_artfinder.py run` to execute the full pipeline. The command
now accepts `--dry-run` to exercise listing pagination, parsing, and
normalization without downloading images or mutating the JSONL/Excel outputs.

Resume a previously interrupted crawl with `python scrape_artfinder.py resume`.
It reads the JSONL archive to collect processed slugs, skips those URLs, and
continues crawling new items without duplicating spreadsheet rows. Combine the
resume command with `--dry-run` to confirm that the slug filtering works before
performing a full write.
