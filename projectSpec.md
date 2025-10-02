# Spec: **Artfinder Artist Scraper** (Lizzie Butler)

Goal: crawl every artwork listed on **Lizzie Butler’s** Artfinder shop (sorted “Newest”), visit each artwork’s detail page, and export a spreadsheet with **Title, Description, Listed Price, Size, Sold status, Main Image (embedded), Source URL, Date scraped**. Images are also saved to disk. Pagination continues until completion.

Scope is limited to this artist’s pages:
- Listing entry point: `https://www.artfinder.com/artist/lizziebutler/sort-newest/` (shows grid, price, pagination).
- Artwork detail pages (contain title, description, size, price, etc.). Example live items:
  - `https://www.artfinder.com/product/a-windswept-walk/`
  - `https://www.artfinder.com/product/west-wittering-7e032/`
  - `https://www.artfinder.com/product/sunshine-awakening/`
  - `https://www.artfinder.com/product/let-the-sun-warm-you/`
  - `https://www.artfinder.com/product/waterside-6333/`
  - `https://www.artfinder.com/product/settled-e4dc9/`
  - `https://www.artfinder.com/product/meditations-in-green/`

> Legal & considerate use: We’re scraping your client’s public listings, but we should still be polite: set low concurrency, respect caching, and identify a contact email via the User-Agent. If Artfinder’s robots/ToS restrict scraping or if they request pausing, the runner must support a quick “dry-run mode” and a domain allowlist.

---

## 1) Deliverables

1. **Spreadsheet (.xlsx)** with embedded thumbnail images and columns:  
   `title | description | price_gbp | size_raw | width_cm | height_cm | depth_cm | sold | image_path | source_url | scraped_at`
   - Apple **Numbers** can open `.xlsx` with embedded images, so we’ll standardize on `.xlsx` for automation. (If needed, we can also export a `.csv` without embedded images.)
2. **Images folder** with one saved image per artwork (`images/<slug>.jpg`).
3. **A JSONL archive** (`data/artworks.jsonl`) mirroring the spreadsheet rows for re-runs/diffs.
4. **CLI tool** (`scrape_artfinder.py`) with commands:  
   - `list-page` (index links), `fetch-item` (single URL), `run` (full crawl), `resume` (continue from last).
5. **Unit tests** (pytest) for each component.
6. **README** explaining setup, and test matrix.

---

## 2) Tech choices

- **Language:** Python 3.11+
- **Fetching:** Always **Playwright** (Chromium, headless) for page rendering and resilience.
- **Parse:** `BeautifulSoup4` + targeted **XPath/CSS**; robust regex for text blocks (e.g., “Size:”).
- **Spreadsheet w/ embedded images:** `openpyxl` (+ `Pillow`).
- **CLI & logging:** `typer` or `argparse`; `rich` for logs.
- **Data model:** `pydantic` for schema validation & normalization.

---

## 3) Data model & normalization

```python
class Artwork(BaseModel):
    title: str
    description: str
    price_gbp: Decimal | None           # numeric; strip currency symbol & commas
    size_raw: str | None                # full “Size: 46 x 46 x 2cm (unframed) …”
    width_cm: float | None
    height_cm: float | None
    depth_cm: float | None
    sold: bool
    image_url: HttpUrl | None
    image_path: str | None              # local file path
    source_url: HttpUrl
    scraped_at: datetime
    slug: str                           # derived from source_url (/product/<slug>/)
```

**Parsing rules**
- **Title:** From artwork page heading line like: `# A Windswept Walk (2025) Oil painting by Lizzie Butler`. Extract substring before “by Lizzie Butler”, strip year/medium if combined.
- **Description:** Under “Original artwork description” section; join paragraphs.
- **Price (GBP):** Monetary text near title; normalize by removing “£” and commas (e.g., “£475”).
- **Size:** Line beginning “Size: … cm …”. Extract width/height/depth in **cm**; keep `size_raw`. If only width×height present, set `depth_cm=None`.
- **Sold status:**  
  True if any of:
  - “This artwork is sold …” blurb present; or
  - “Add to Basket” button **absent**; or
  - page shows “Sold”/“Unavailable” badge near price.
- **Image URL:** Prefer **OpenGraph** `og:image` if present; else first gallery image `<img>` in hero carousel; else the first CDN image in page body. **Fallback** to the listing thumbnail if detail fails.
- **Listing URL discovery:** On the artist listing page(s), each card links to a `/product/<slug>/` page. If a direct selector is unstable, use a regex over the HTML for `href="/product/[^"?#]+"` and `urljoin` to absolute URLs. Pagination nav has numeric pages and “Next”.

---

## 4) Page structure & selectors (initial heuristics)

> These are resilient **text-label** and **path-based** strategies rather than brittle classnames.

**Listing (grid) page** (`/artist/lizziebutler/sort-newest/`):  
- **Pagination links:** find anchors whose text is `Next` or digits; follow until “Next” missing.  
- **Artwork links:** search for `/product/…/` hrefs within the grid container region below `# Artworks by Lizzie Butler`.

**Detail page (`/product/<slug>/`)**:  
- **Title:** first H1/H2 block that contains `(year)` and “by Lizzie Butler” → capture the left segment as title.  
- **Price:** nearest currency text (e.g., “£475”) between title block and bullet list.  
- **Size:** list item beginning with `Size:`; parse `(?P<w>\d+(?:\.\d+)?)\s*x\s*(?P<h>\d+(?:\.\d+)?)(?:\s*x\s*(?P<d>\d+(?:\.\d+)?))?\s*cm`. Unit is **cm**.  
- **Description:** paragraphs directly under the “Original artwork description” heading.  
- **Sold state:** presence of “This artwork is sold …” or absence of “Add to Basket”.  
- **Main image:** meta `og:image` (if available), else first hero `<img>` with alt containing the title.

---

## 5) Components (independently testable)

1) **Indexer**  
   - **Input:** listing URL (defaults to “sort-newest”).  
   - **Output:** ordered list of **unique** artwork URLs.  
   - **Done when:** it collects all pages until no **Next** link.

2) **Item Extractor**  
   - **Input:** one artwork URL.  
   - **Output:** one `Artwork` object (all fields populated; `sold` computed; `image_url` chosen).  
   - **Validation:** strict pydantic; raise on missing required fields (title, source_url).

3) **Image Downloader**  
   - **Input:** `Artwork.image_url`, `slug`.  
   - **Output:** `images/<slug>.jpg` (or original extension), path stored on the `Artwork`.  
   - **Rules:** retry/backoff, 2xx only, limit max size (e.g., 10 MB), verify JPEG/PNG signature.

4) **Spreadsheet Writer**  
   - **Input:** list of `Artwork`.  
   - **Output:** `.xlsx` with images embedded in a fixed **Image** column (scaled to max height 120 px), plus all text columns.  
   - **Behavior:** create if not exists, else **append** deduping by `slug|title`.

5) **Runner / Orchestrator**  
   - **Flow:** Index → for each URL: Extract → Download image → Append to sheet → Save JSONL row.  
   - **Resume:** reads `data/artworks.jsonl`, skips known slugs unless logic indicates content changed.

---

## 6) Test plan (live site; no mocks)

- ✅ **Single artwork URL loads & fields extracted** (live requests, Playwright):  
  Examples to use directly:
  - `https://www.artfinder.com/product/a-windswept-walk/`  
  - `https://www.artfinder.com/product/west-wittering-7e032/`  
  - `https://www.artfinder.com/product/let-the-sun-warm-you/`

- ✅ **Image can be downloaded** (live request):  
  Resolve `og:image` (or first hero image) from the above pages and download. Validate file exists and is embeddable.

- ✅ **Spreadsheet append incl. embedded image** (local I/O):  
  Create temp `.xlsx`; append two rows with images from the live downloads; reopen and assert image presence and cell text.

- ✅ **Artworks on a page can be indexed** (live listing page):  
  Hit entry page `https://www.artfinder.com/artist/lizziebutler/sort-newest/`; assert ≥ 12 links; verify `/product/<slug>/` format.

- ✅ **We can paginate until completion** (live):  
  Walk the pagination by following numeric links and “Next” until absent. Keep a running count and ensure no duplicate slugs.

*(Edge tests skipped per instructions.)*

---

## 7) CLI

```
# full run
python scrape_artfinder.py run --out ./out/ --xlsx lizzie_butler.xlsx

# resume existing dataset
python scrape_artfinder.py resume --out ./out/

# test a single item
python scrape_artfinder.py fetch-item https://www.artfinder.com/product/a-windswept-walk/

# list & print URLs we will visit (no fetch)
python scrape_artfinder.py list-page https://www.artfinder.com/artist/lizziebutler/sort-newest/
```

**Defaults (no flags required):**
- Concurrency: **1**
- Per-request delay: **300–800 ms** jittered
- User-Agent: **`LB-Scraper/1.0`**
- JavaScript engine: **Playwright** (Chromium)

---

## 8) File & package layout

```
artfinder_scraper/
  scraping/
    indexer.py          # pagination, link discovery (Playwright page.evaluate/selectors)
    extractor.py        # parse item fields (bs4 + regex)
    downloader.py       # images with validation
    spreadsheet.py      # openpyxl embed & append
    normalize.py        # price/size parsing utils
    models.py           # pydantic Artwork
    runner.py           # Orchestrator
    browsers.py         # Playwright driver
  tests/
    test_indexer.py
    test_extractor.py
    test_downloader.py
    test_spreadsheet.py
  data/
    artworks.jsonl      # append-only archive
  out/
    lizzie_butler.xlsx
    images/
  scrape_artfinder.py   # CLI entrypoint
  README.md
  requirements.txt
```

---

## 9) Normalization details

- **Price:** `£2,200` → `2200.00` (Decimal). Currency fixed to GBP.
- **Size:**
  - Accept strings like `W x H x Dcm (unframed) / W x Hcm (actual image size)`; parse the **first** triplet/pair.
  - If units differ (e.g., inches), convert to cm (primary expectation is **cm**).
- **Slug:** last path segment from `/product/<slug>/`.
- **Image:** save as `.jpg` unless remote indicates PNG (`Content-Type`).

---

## 10) Robustness & ops

- **Request etiquette:** Random delay 300–800ms between fetches; concurrency = 1; backoff on 429/5xx.
- **Idempotency:** Dedup by slug; store `etag`/`last-modified` if available to avoid re-downloading images.
- **Configuration:** **Hard-code** all directories (use `./out`, `./data`); assume **no proxy**.
- **Logging:** INFO progress; DEBUG for parse decisions; per-item HTML snapshot when parser fails.
- **Playwright only:** No alternate HTTP client; all page fetches through Chromium driver.

---

## 12) Example parsing anchors (from live pages)

- Listing page shows “Artworks by Lizzie Butler”, 12 cards per page, with pagination including **Next**. Use this block to bound link scraping.  
- Detail pages surface typical anchors:
  - **Title + year + medium + artist** in a single heading block.
  - **Price** just under the heading.
  - **Size** line beginning “Size: … cm …”.
  - **Description** under “Original artwork description”.
  - Older/sold works can include explicit “This artwork is sold …” wording.

