# Artfinder Scraper

This project will crawl every artwork listed on an example artist's Artfinder shop, capture detailed metadata from each artwork page, and produce a spreadsheet plus downloaded imagery summarizing the collection. Upcoming modules in `artfinder_scraper/scraping/` will coordinate listing pagination, extract detail page content, normalize data, download media, and assemble spreadsheet outputs backed by typed models and runnable workflows.

## Environment requirements

* Python 3.11 or newer.
* Google Chrome or Microsoft Edge so Playwright can drive a Chromium browser.
* System libraries required by Playwright (see the [Playwright installation guide](https://playwright.dev/python/docs/intro) for your operating system).
* Project dependencies from `requirements.txt` installed inside a virtual environment:

  ```bash
  python -m venv .venv
  source .venv/bin/activate
  pip install -r requirements.txt
  playwright install chromium
  ```

All commands below assume the virtual environment is active so `python` resolves to the interpreter with these dependencies.

## Running parser tests

The extractor uses saved HTML fixtures to verify that titles, prices, size text, sold state, images, and materials used copy are detected correctly. Execute the focused test module with:

```bash
pytest artfinder_scraper/tests/test_extractor.py
pytest artfinder_scraper/tests/test_indexer.py
```

Add `-k <pattern>` to target a specific scenario (for example, sold items or duplicate listing links) when iterating on parsing logic.

The fixtures employ fictional artwork titles such as "Echoes of Dawn" and "Lantern Glow" with placeholder descriptions so anonymized sample data exercises the parser without referencing real-world listings.

## Listing page command

Use the Typer CLI to enumerate product links from a listing page. The command launches the Playwright helper, applies project politeness rules, and prints the canonical `/product/` URLs it discovers:

```bash
python scrape_artfinder.py list-page \
  https://www.artfinder.com/artist/example-artist/sort-newest/
```

Example output:

```
https://www.artfinder.com/product/echoes-of-dawn-canvas/
https://www.artfinder.com/product/lantern-glow-atrium-study/
https://www.artfinder.com/product/prism-tide-harbor-series/
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
* `--dry-run` – execute the crawl without downloading images or writing JSONL/Excel output.
* `--skip-images` – persist JSONL/Excel data while skipping image downloads.

The command prints a one-line summary when complete and lists any recoverable errors that were skipped along the way so you can iterate on extraction fidelity.

### Resuming a crawl

Use the `resume` subcommand to continue a crawl after an interrupted run. The command inspects the JSONL archive, collects the slugs that were already processed, and skips any matching items while the spreadsheet helper continues guarding against duplicates.

```bash
python scrape_artfinder.py resume --jsonl-path artfinder_scraper/data/artworks.jsonl --rate-limit 1.5
```

Combine the resume flow with `--dry-run` to verify that the CLI loads the expected slugs without mutating the on-disk JSONL or spreadsheet files:

```bash
python scrape_artfinder.py resume --jsonl-path artfinder_scraper/data/artworks.jsonl --dry-run --limit 5
```

If the JSONL file is missing the command prints a notice and starts a fresh crawl using the configured listing URL.

## Spreadsheet export

Each successful scrape run also maintains an Excel workbook at
`artfinder_scraper/data/artworks.xlsx`. Rows are appended in slug/title order
while ensuring duplicates are skipped when either identifier already exists in
the sheet. Images are embedded in the first column and resized so their longest
edge fits within roughly 320 pixels to keep the document compact. The remaining
columns appear in the following order:

1. image (embedded thumbnail)
2. title
3. size
4. medium
5. materials used
6. price (prefixed with £)
7. description
8. status (`sold` or `for sale`)
9. art finder link (hyperlinked to the source URL)

The workbook lives alongside the JSONL archive, making it easy to distribute a
human-friendly catalog while preserving normalized records for downstream
automation.

## Continuous integration

All pull requests trigger the GitHub Actions workflow defined in `.github/workflows/test.yml`. The workflow installs the project's Python
dependencies along with `pytest` before executing the full test suite to guard against regressions before merges.
