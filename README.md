# Artfinder Scraper

This project will crawl every artwork listed on Lizzie Butler's Artfinder shop, capture detailed metadata from each artwork page, and produce a spreadsheet plus downloaded imagery summarizing the collection. Upcoming modules in `artfinder_scraper/scraping/` will coordinate listing pagination, extract detail page content, normalize data, download media, and assemble spreadsheet outputs backed by typed models and runnable workflows.

## Running extractor tests

The extractor uses saved HTML fixtures to verify that titles, prices, size text, sold state, and images are detected correctly. Execute the focused test module with:

```bash
pytest artfinder_scraper/tests/test_extractor.py
```

Add `-k <pattern>` to target a specific scenario (for example, sold items) when iterating on parsing logic.

## Continuous integration

All pull requests trigger the GitHub Actions workflow defined in `.github/workflows/test.yml`. The workflow installs the project's Python
dependencies along with `pytest` before executing the full test suite to guard against regressions before merges.
