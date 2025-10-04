# Artfinder Scraper

This project will crawl every artwork listed on an example artist's Artfinder shop, capture detailed metadata from each artwork page, and produce a spreadsheet plus downloaded imagery summarizing the collection. Upcoming modules in `artfinder_scraper/scraping/` will coordinate listing pagination, extract detail page content, normalize data, download media, and assemble spreadsheet outputs backed by typed models and runnable workflows.

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

## Continuous integration

All pull requests trigger the GitHub Actions workflow defined in `.github/workflows/test.yml`. The workflow installs the project's Python
dependencies along with `pytest` before executing the full test suite to guard against regressions before merges.
