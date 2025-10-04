# artfinder_scraper Package

This package will contain the scraping logic, tests, and storage helpers for the Artfinder project. The `scraping` subpackage will be populated with indexers, extractors, downloaders, spreadsheet utilities, normalization helpers, typed models, browser helpers, and a runner to orchestrate flows. The `tests` package will house unit and integration coverage for those components, while `data/` and `out/` will persist input caches and generated artifacts.

## Browser helper

`artfinder_scraper.scraping.browsers` exposes `fetch_page_html(url: str)` which drives a headless Chromium instance with the required user agent (`LB-Scraper/1.0`) and a jittered 300–800 ms delay before each navigation. The helper waits for the main content element to render before returning the HTML, making it a convenient building block for the extractor and higher-level orchestration code.

## Command-line interface

The root `scrape_artfinder.py` script hosts a Typer application. The first available subcommand mirrors the specification’s single-item workflow:

```bash
python scrape_artfinder.py fetch-item https://www.artfinder.com/product/echoes-of-dawn-canvas/
```

Pass `--out path/to/file.html` to store the rendered HTML instead of printing it to the terminal. Use `--download-image` to save the hero image to `out/images/` while reporting the stored path in the console output.

## Test fixtures

Tests exercise the parsing helpers with anonymized HTML fixtures. The fixtures reference fictional artist names, artwork titles, descriptions, and URLs to ensure the suite avoids real-world listings while still covering the expected extraction logic.
