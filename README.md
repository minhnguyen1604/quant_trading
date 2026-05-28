# VNIndex Daily Crawler

Script to crawl historical daily OHLCV data for VNINDEX components from 2017-01-01 to present.

Usage
------
1. Create a virtualenv and install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
```

2. Run the crawler:

```bash
python scripts/crawl_vnindex.py --outdir data --start 2017-01-01
```

Notes
-----
- The script scrapes the VNINDEX components page on Yahoo Finance. If scraping fails, provide a ticker list with `--source-list` (one ticker per line).
- The downloader uses `yfinance` and attempts common Vietnam suffixes like `.VN`, `.HO`, and `.HS` when needed.
- When `--hose` is passed, the script first tries VNDIRECT to get all HOSE symbols; if that fails, it automatically falls back to querying HSX public search endpoints.
- To refresh daily data without re-downloading the full history, use `--refresh`.

Daily refresh example
---------------------

```bash
python scripts/crawl_vnindex.py --outdir data_hose --start 2017-01-01 --hose --refresh
```

This will append only new rows to existing CSV files based on the last saved `Date`. If a ticker file does not exist yet, it downloads the full requested range.

Normalize & store into SQLite
-----------------------------

After you have collected CSVs (for example in `data_hose`), you can normalize
their messy header format and load them into a single SQLite DB with:

```bash
# Normalize Daily prices
python scripts/normalize_and_store.py --indir data_hose --db data_prices.db --table daily_prices

# Normalize Weekly prices
python scripts/normalize_and_store.py --indir data_hose_weekly --db data_prices.db --table weekly_prices
```

For testing you can process only a few files with `--limit N` and optionally
write cleaned CSVs to `--outdir cleaned_data`.

Example (test 5 files and write cleaned CSVs):

```bash
python scripts/normalize_and_store.py --indir data_hose --outdir cleaned_data --db data_prices_test.db --limit 5
```

The script creates/updates table `daily_prices` and `weekly_prices` in the SQLite file with columns:
`Ticker, Date, Close, High, Low, Open, Volume`.
