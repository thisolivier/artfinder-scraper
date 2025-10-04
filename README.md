# Artfinder Scraper

This project will crawl every artwork listed on Lizzie Butler's Artfinder shop, capture detailed metadata from each artwork page, and produce a spreadsheet plus downloaded imagery summarizing the collection. Upcoming modules in `artfinder_scraper/scraping/` will coordinate listing pagination, extract detail page content, normalize data, download media, and assemble spreadsheet outputs backed by typed models and runnable workflows.

## Running parser tests

The extractor uses saved HTML fixtures to verify that titles, prices, size text, sold state, images, and materials used copy are detected correctly. Execute the focused test module with:

```bash
pytest artfinder_scraper/tests/test_extractor.py
pytest artfinder_scraper/tests/test_indexer.py
```

Add `-k <pattern>` to target a specific scenario (for example, sold items or duplicate listing links) when iterating on parsing logic.

## Listing page command

Use the Typer CLI to enumerate product links from a listing page. The command launches the Playwright helper, applies project politeness rules, and prints the canonical `/product/` URLs it discovers:

```bash
python scrape_artfinder.py list-page \
  https://www.artfinder.com/artist/lizziebutler/sort-newest/
```

Example output:

```
https://www.artfinder.com/product/a-windswept-walk/
https://www.artfinder.com/product/soft-light-kew-gardens-an-atmospheric-oil-painting/
https://www.artfinder.com/product/shoreline-2024-oil-painting/
```

The URLs are deduplicated and normalized by slug so downstream crawlers can feed them directly into the detail-page workflow.

## Run the orchestration pipeline

A smoke-test `run` command wires the orchestrator together so you can validate end-to-end progress without writing custom scripts. It paginates through the configured listing, fetches each detail page, normalizes records, downloads images, and appends JSONL rows under `artfinder_scraper/data/artworks.jsonl` by default.

```bash
python scrape_artfinder.py run --limit 3 --rate-limit 1.5
```

Key options:

* `--limit` – cap how many artworks are processed during the run (omit to crawl the entire listing).
* `--listing-url` – change which artist listing is crawled.
* `--jsonl-path` – store the JSONL output somewhere other than the default project location.
* `--rate-limit` – control the minimum delay between detail page fetches.

The command prints a one-line summary when complete and lists any recoverable errors that were skipped along the way so you can iterate on extraction fidelity.

## Continuous integration

All pull requests trigger the GitHub Actions workflow defined in `.github/workflows/test.yml`. The workflow installs the project's Python
dependencies along with `pytest` before executing the full test suite to guard against regressions before merges.
