#!/usr/bin/env python3
"""
Crawl historical daily prices for VNINDEX components and HOSE-listed symbols from 2017-01-01 to today.

Approach:
- Try to fetch index components from Yahoo Finance components page by default.
- When `--hose` is used, fetch HOSE-listed symbols from VNDIRECT or HSX search fallback.
- For each symbol, attempt downloads via `yfinance`. Try variants with common VN suffixes.
- Save per-ticker CSV into `data/`.

Usage:
    python scripts/crawl_vnindex.py --outdir data --start 2017-01-01
    python scripts/crawl_vnindex.py --outdir data_hose --hose --start 2017-01-01
"""
import argparse
import datetime as dt
import os
import time
from typing import List

import pandas as pd
import requests
import yfinance as yf
from bs4 import BeautifulSoup
from tqdm import tqdm


VNDIRECT_STOCKS_API = "https://finfo-api.vndirect.com.vn/v4/stocks"
HSX_SEARCH_URL = "https://api.hsx.vn/q/api/v1/search"
HSX_SEARCH_INDEX = "securities"
HSX_SEARCH_FIELDS = "code^2,isin,figi,introduction"
HSX_SEARCH_PAGE_SIZE = 100
HSX_SEARCH_PREFIX_CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"

YAHOO_COMPONENTS_URL = "https://finance.yahoo.com/quote/%5EVNINDEX/components?p=%5EVNINDEX"


def get_components_from_yahoo() -> List[str]:
    resp = requests.get(YAHOO_COMPONENTS_URL, headers={"User-Agent": "curl/7.64.1"}, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    # Yahoo lists components in a table; tickers are in the first column as links
    tickers = []
    table = soup.find("table")
    if not table:
        return tickers
    for row in table.find_all("tr"):
        cols = row.find_all("td")
        if not cols:
            continue
        a = cols[0].find("a")
        if a and a.text:
            tickers.append(a.text.strip())
    # Deduplicate
    return list(dict.fromkeys(tickers))


def get_hose_list_from_vndirect() -> List[str]:
    """Retrieve list of HOSE-listed symbols from VNDIRECT public API.

    Falls back to an empty list on error.
    """
    symbols = []
    try:
        params = {"exchange": "HOSE", "size": 1000}
        resp = requests.get(VNDIRECT_STOCKS_API, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        for item in data.get("data", []):
            sym = item.get("symbol")
            if sym:
                symbols.append(sym.strip())
    except Exception:
        return []
    return list(dict.fromkeys(symbols))


def get_hose_list_from_hsx(query_prefixes: List[str] = None, show_progress: bool = True) -> List[str]:
    """Retrieve HOSE-listed symbols by scraping HSX search API.

    This is a fallback when VNDIRECT is unavailable.
    """
    if query_prefixes is None:
        chars = HSX_SEARCH_PREFIX_CHARS
        query_prefixes = [a + b for a in chars for b in chars]

    session = requests.Session()
    session.headers.update({"User-Agent": "curl/7.64.1"})
    symbols = set()

    for prefix in tqdm(query_prefixes, desc="HOSE prefix scan", disable=not show_progress):
        params = {
            "indexName": HSX_SEARCH_INDEX,
            "field": HSX_SEARCH_FIELDS,
            "query": prefix,
            "page": 1,
            "pageSize": HSX_SEARCH_PAGE_SIZE,
        }
        try:
            resp = session.get(HSX_SEARCH_URL, params=params, timeout=15)
            if resp.status_code != 200:
                continue
            data = resp.json()
        except Exception:
            continue

        if not data or data.get("totalPages", 0) <= 0:
            continue

        total_pages = data.get("totalPages", 0)
        for page in range(1, total_pages + 1):
            if page > 1:
                params["page"] = page
                try:
                    resp = session.get(HSX_SEARCH_URL, params=params, timeout=15)
                    if resp.status_code != 200:
                        break
                    data = resp.json()
                except Exception:
                    break
            for item in data.get("items", []):
                if item.get("securitiesTypeId") == 1 and item.get("code"):
                    symbols.add(item["code"].strip())
        time.sleep(0.1)

    return sorted(symbols)


def get_hose_list() -> List[str]:
    symbols = get_hose_list_from_vndirect()
    if symbols:
        return symbols

    print("VNDIRECT unreachable or blocked; falling back to HSX search-based symbol discovery...")
    symbols = get_hose_list_from_hsx()
    return symbols


def normalize_candidate_symbols(sym: str) -> List[str]:
    # If symbol already contains a dot or suffix, try it as-is first
    candidates = []
    if "." in sym:
        candidates.append(sym)
    else:
        # common Yahoo Vietnam suffix
        # DO NOT append bare sym without suffix to avoid downloading US stocks (e.g. AMD instead of AMD.VN)
        candidates.extend([sym + ".VN", sym + ".HO", sym + ".HS"])
    # ensure uniqueness while preserving order
    seen = set()
    out = []
    for s in candidates:
        if s not in seen:
            seen.add(s)
            out.append(s)
    return out


def download_for_symbol(symbol: str, start: str, end: str, interval: str = "1d") -> pd.DataFrame:
    # try yfinance download for a ticker symbol
    try:
        df = yf.download(symbol, start=start, end=end, interval=interval, progress=False, threads=False)
        if isinstance(df, pd.DataFrame) and not df.empty:
            df.index = pd.to_datetime(df.index)
            return df
    except Exception:
        pass
    return pd.DataFrame()


def append_or_write_csv(fname: str, df: pd.DataFrame):
    if os.path.exists(fname):
        try:
            existing = pd.read_csv(fname, header=[0, 1], index_col=0)
            existing.index = pd.to_datetime(existing.index, errors="coerce")
            existing = existing[existing.index.notna()]
            
            # Ensure the newly downloaded df also has datetime index
            df.index = pd.to_datetime(df.index, errors="coerce")
            df = df[df.index.notna()]
            
            combined = pd.concat([existing, df])
            combined = combined[~combined.index.duplicated(keep="last")]
            combined.sort_index(inplace=True)
            combined.to_csv(fname, index_label="Date")
        except Exception:
            df.to_csv(fname, index_label="Date")
    else:
        df.to_csv(fname, index_label="Date")


def crawl_all(outdir: str, start: str, end: str, source_list: str = None, use_hose: bool = False, refresh: bool = False, interval: str = "1d"):
    os.makedirs(outdir, exist_ok=True)
    if source_list:
        with open(source_list, "r", encoding="utf-8") as f:
            symbols = [line.strip() for line in f if line.strip() and not line.startswith("#")]
    else:
        if use_hose:
            symbols = get_hose_list()
            if not symbols:
                print("Failed to fetch HOSE list from VNDIRECT, falling back to Yahoo scraping...")
                symbols = get_components_from_yahoo()
        else:
            symbols = get_components_from_yahoo()
    if not symbols:
        print("No symbols found from Yahoo. Provide --source-list with tickers.")
        return

    print(f"Found {len(symbols)} symbols, attempting downloads...")
    failures = []
    for sym in tqdm(symbols, desc="tickers"):
        tried = False
        for cand in normalize_candidate_symbols(sym):
            fname = os.path.join(outdir, f"{cand.replace('/', '_')}.csv")
            download_start = start
            if refresh and os.path.exists(fname):
                try:
                    existing = pd.read_csv(fname, header=[0, 1], index_col=0)
                    existing.index = pd.to_datetime(existing.index, errors="coerce")
                    valid_dates = existing.index[existing.index.notna()]
                    if not valid_dates.empty:
                        last_date = valid_dates.max()
                        download_start = last_date.strftime("%Y-%m-%d")
                        if download_start >= end:
                            tried = True
                            break
                except Exception:
                    pass
            df = download_for_symbol(cand, download_start, end, interval=interval)
            if not df.empty:
                if refresh and os.path.exists(fname):
                    append_or_write_csv(fname, df)
                else:
                    df.to_csv(fname, index_label="Date")
                tried = True
                # be polite
                time.sleep(0.5)
                break
        if not tried:
            failures.append(sym)

    if failures:
        print("Failed to download for these symbols:")
        for f in failures:
            print(" -", f)
    else:
        print("All downloads completed successfully.")


def parse_args():
    p = argparse.ArgumentParser(description="Crawl VNINDEX components historical daily data")
    p.add_argument("--outdir", default="data", help="Output directory for CSV files")
    p.add_argument("--start", default="2017-01-01", help="Start date YYYY-MM-DD")
    p.add_argument("--end", default=dt.datetime.today().strftime("%Y-%m-%d"), help="End date YYYY-MM-DD")
    p.add_argument("--source-list", help="Optional file with one ticker per line to use instead of scraping")
    p.add_argument("--hose", action="store_true", help="Use HOSE-listed tickers from VNDIRECT API instead of Yahoo components")
    p.add_argument("--refresh", action="store_true", help="Refresh existing CSV files by downloading only new data since the last saved date")
    p.add_argument("--interval", default="1d", choices=["1d", "1wk"], help="Download interval (1d for daily, 1wk for weekly)")
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()
    crawl_all(
        args.outdir,
        args.start,
        args.end,
        args.source_list,
        getattr(args, "hose", False),
        getattr(args, "refresh", False),
        getattr(args, "interval", "1d"),
    )
