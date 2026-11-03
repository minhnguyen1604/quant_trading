# HOSE Daily Crawler & Backtests

Script to crawl adjusted historical daily OHLCV data for HOSE-listed stocks from 2017-01-01 to present,
store it in SQLite and backtest moving-average crossover strategies on it.

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
python scripts/crawl_vnindex.py --hose --outdir data_hose_daily --weekly-outdir data_hose_weekly --start 2017-01-01
```

Data sources
------------
- **Symbol list:** SSI iBoard (`iboard-query.ssi.com.vn`), stocks only (no fund certificates, ETFs or
  covered warrants). Falls back to the HSX public search API.
- **Prices:** KBS (`kbbuddywts.kbsec.com.vn`), falling back to SSI iBoard's chart API
  (`iboard-api.ssi.com.vn`). These are the public, unofficial endpoints behind the brokers' web price
  boards, so they may change without notice. Prices are in VND and back-adjusted for cash dividends,
  bonus shares and splits. KBS is preferred because it returns prices to the đồng, while SSI rounds to
  10 đồng.
- Zero-volume rows (filler bars that carry the previous price) are dropped, and today's bar is skipped
  while the session is still open (before 15:00 Vietnam time).
- Weekly bars are resampled from the daily data and labelled with the Monday of each week.
- Adjusted history changes after every corporate action, so each run re-downloads the full range and
  overwrites the CSVs instead of appending. `normalize_and_store.py` likewise replaces each ticker's rows.
- Only currently listed stocks are crawled, so backtests still carry survivorship bias.

Use `--source-list tickers.txt` (one ticker per line, e.g. `FPT`) to crawl a custom list.

Normalize & store into SQLite
-----------------------------

After you have collected CSVs, load them into a single SQLite DB with:

```bash
# Daily prices
python scripts/normalize_and_store.py --indir data_hose_daily --db data_prices.db --table daily_prices

# Weekly prices
python scripts/normalize_and_store.py --indir data_hose_weekly --db data_prices.db --table weekly_prices
```

For testing you can process only a few files with `--limit N` and optionally
write cleaned CSVs to `--outdir cleaned_data`.

The script creates/updates table `daily_prices` and `weekly_prices` in the SQLite file with columns:
`Ticker, Date, Close, High, Low, Open, Volume` (plus `Sector, Industry`, looked up once per ticker via yfinance).

`run_daily.bat` (or `python scripts/run_daily_update.py`) runs the crawl and both store steps in one go.

Backtests
---------

Each script reads `data_prices.db` and writes one `results` table per output DB, one row per ticker:

```bash
python scripts/backtesting_ema9wma45_strategy.py      # EMA9/WMA45, daily + weekly
python scripts/backtesting_ma5ma20_strategy.py        # SMA5/SMA20, daily + weekly
python scripts/backtesting_daily_optimize.py          # EMA9/WMA45 daily, buy on close / sell on open
python scripts/backtesting_weekly_optimize.py         # EMA9/WMA45 weekly, buy Friday close / sell Monday open
python scripts/backtesting_weekly_optimize_ma5ma20.py # SMA5/SMA20 weekly, buy Friday close / sell Monday open
```
