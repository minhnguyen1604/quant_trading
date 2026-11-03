#!/usr/bin/env python3
"""
Crawl historical daily prices for HOSE-listed stocks from 2017-01-01 to today.

Approach:
- Get the list of HOSE stocks from SSI iBoard (fallback: HSX search API).
- For each symbol, download adjusted daily OHLCV from KBS (fallback: SSI iBoard chart API).
  Both are the public endpoints behind the brokers' web price boards; prices are in VND
  and back-adjusted for dividends, bonus shares and splits.
- Save per-ticker CSV (columns: Date,Open,High,Low,Close,Volume) into `--outdir`, and
  optionally weekly bars resampled from the daily data into `--weekly-outdir`.

Because adjusted history changes after every corporate action, each run re-downloads the
full range and overwrites the CSV instead of appending.

Usage:
    python scripts/crawl_vnindex.py --hose --outdir data_hose_daily --weekly-outdir data_hose_weekly
    python scripts/crawl_vnindex.py --source-list tickers.txt --outdir data_hose_daily
"""
import argparse
import datetime as dt
import os
import time
from typing import List, Optional

import pandas as pd
import requests
from tqdm import tqdm


USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"

SSI_HOSE_LIST_URL = "https://iboard-query.ssi.com.vn/stock/exchange/hose"
SSI_CHART_URL = "https://iboard-api.ssi.com.vn/statistics/charts/history"
KBS_DAILY_URL = "https://kbbuddywts.kbsec.com.vn/iis-server/investment/stocks/{symbol}/data_day"

HSX_SEARCH_URL = "https://api.hsx.vn/q/api/v1/search"
HSX_SEARCH_INDEX = "securities"
HSX_SEARCH_FIELDS = "code^2,isin,figi,introduction"
HSX_SEARCH_PAGE_SIZE = 100
HSX_SEARCH_PREFIX_CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"

VN_TZ = "Asia/Ho_Chi_Minh"
MARKET_CLOSE_HOUR = 15
PRICE_COLUMNS = ["Open", "High", "Low", "Close", "Volume"]

session = requests.Session()
session.headers.update({"User-Agent": USER_AGENT})


def get_hose_list_from_ssi() -> List[str]:
    """Retrieve HOSE-listed stock symbols (excluding fund certificates) from SSI iBoard.

    Falls back to an empty list on error.
    """
    try:
        resp = session.get(SSI_HOSE_LIST_URL, headers={"Referer": "https://iboard.ssi.com.vn/"}, timeout=20)
        resp.raise_for_status()
        items = resp.json().get("data", [])
    except Exception:
        return []
    symbols = [item["stockSymbol"].strip() for item in items if item.get("stockType") == "s" and item.get("stockSymbol")]
    return sorted(set(symbols))


def get_hose_list_from_hsx(query_prefixes: List[str] = None, show_progress: bool = True) -> List[str]:
    """Retrieve HOSE-listed symbols by scraping HSX search API.

    This is a fallback when SSI is unavailable.
    """
    if query_prefixes is None:
        chars = HSX_SEARCH_PREFIX_CHARS
        query_prefixes = [a + b for a in chars for b in chars]

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
    symbols = get_hose_list_from_ssi()
    if symbols:
        return symbols

    print("SSI unreachable or blocked; falling back to HSX search-based symbol discovery...")
    return get_hose_list_from_hsx()


def _empty_prices() -> pd.DataFrame:
    return pd.DataFrame(columns=PRICE_COLUMNS, index=pd.DatetimeIndex([], name="Date"))


def fetch_kbs(symbol: str, start: str, end: str) -> pd.DataFrame:
    """Adjusted daily OHLCV from KBS, prices in VND."""
    params = {
        "sdate": dt.datetime.strptime(start, "%Y-%m-%d").strftime("%d-%m-%Y"),
        "edate": dt.datetime.strptime(end, "%Y-%m-%d").strftime("%d-%m-%Y"),
    }
    resp = session.get(KBS_DAILY_URL.format(symbol=symbol), params=params, timeout=30)
    resp.raise_for_status()
    rows = resp.json().get("data_day") or []
    if not rows:
        return _empty_prices()
    df = pd.DataFrame(rows).rename(columns={"o": "Open", "h": "High", "l": "Low", "c": "Close", "v": "Volume"})
    df["Date"] = pd.to_datetime(df["t"]).dt.normalize()
    # KBS may return two rows for the latest session; keep the settled one (largest volume)
    df = df.sort_values(["Date", "Volume"]).drop_duplicates("Date", keep="last")
    return df.set_index("Date")[PRICE_COLUMNS]


def fetch_ssi(symbol: str, start: str, end: str) -> pd.DataFrame:
    """Adjusted daily OHLCV from SSI iBoard. SSI quotes prices in thousand VND; convert to VND."""
    start_ts = int(pd.Timestamp(start, tz=VN_TZ).timestamp())
    end_ts = int((pd.Timestamp(end, tz=VN_TZ) + pd.Timedelta(days=1)).timestamp())
    params = {"resolution": "1D", "symbol": symbol, "from": start_ts, "to": end_ts}
    resp = session.get(SSI_CHART_URL, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json().get("data") or {}
    if not data.get("t"):
        return _empty_prices()
    df = pd.DataFrame({
        "Date": pd.to_datetime(data["t"], unit="s", utc=True).tz_convert(VN_TZ).normalize().tz_localize(None),
        "Open": data["o"], "High": data["h"], "Low": data["l"], "Close": data["c"], "Volume": data["v"],
    })
    df[["Open", "High", "Low", "Close"]] = (df[["Open", "High", "Low", "Close"]] * 1000).round(2)
    df = df.drop_duplicates("Date", keep="last")
    return df.set_index("Date")[PRICE_COLUMNS]


def clean_prices(df: pd.DataFrame, end: str) -> pd.DataFrame:
    df = df.apply(pd.to_numeric, errors="coerce").dropna()
    df = df[(df[["Open", "High", "Low", "Close"]] > 0).all(axis=1)]
    # Zero-volume rows are filler bars (price carried over from the previous session), not trades
    df = df[df["Volume"] > 0].copy()
    # A small share of upstream bars have Open/Close outside High/Low; widen the range to contain them
    df["High"] = df[["Open", "High", "Close"]].max(axis=1)
    df["Low"] = df[["Open", "Low", "Close"]].min(axis=1)
    # Drop today's bar while the session is still running, it is not final yet
    now = pd.Timestamp.now(tz=VN_TZ)
    if end >= now.strftime("%Y-%m-%d") and now.hour < MARKET_CLOSE_HOUR:
        df = df[df.index < now.normalize().tz_localize(None)]
    df = df[df.index <= pd.Timestamp(end)]
    return df.sort_index()


def download_for_symbol(symbol: str, start: str, end: str) -> pd.DataFrame:
    for fetch in (fetch_kbs, fetch_ssi):
        try:
            df = clean_prices(fetch(symbol, start, end), end)
        except Exception:
            continue
        if not df.empty:
            return df
    return _empty_prices()


def to_weekly(df: pd.DataFrame) -> pd.DataFrame:
    """Resample daily bars into weekly bars labelled with the Monday of each week."""
    week = df.index - pd.to_timedelta(df.index.weekday, unit="D")
    weekly = df.groupby(week).agg({"Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"})
    weekly.index.name = "Date"
    return weekly


def write_csv(df: pd.DataFrame, fname: str):
    df.to_csv(fname, index_label="Date", date_format="%Y-%m-%d")


def crawl_all(outdir: str, start: str, end: str, source_list: Optional[str] = None, weekly_outdir: Optional[str] = None):
    os.makedirs(outdir, exist_ok=True)
    if weekly_outdir:
        os.makedirs(weekly_outdir, exist_ok=True)

    if source_list:
        with open(source_list, "r", encoding="utf-8") as f:
            symbols = [line.strip() for line in f if line.strip() and not line.startswith("#")]
    else:
        symbols = get_hose_list()
    if not symbols:
        print("No symbols found. Provide --source-list with tickers.")
        return

    print(f"Found {len(symbols)} symbols, attempting downloads...")
    failures = []
    for sym in tqdm(symbols, desc="tickers"):
        df = download_for_symbol(sym, start, end)
        if df.empty:
            failures.append(sym)
            continue
        write_csv(df, os.path.join(outdir, f"{sym}.csv"))
        if weekly_outdir:
            write_csv(to_weekly(df), os.path.join(weekly_outdir, f"{sym}.csv"))
        # be polite
        time.sleep(0.3)

    if failures:
        print("Failed to download for these symbols:")
        for f in failures:
            print(" -", f)
    else:
        print("All downloads completed successfully.")


def parse_args():
    p = argparse.ArgumentParser(description="Crawl HOSE historical daily (and weekly) prices from KBS / SSI")
    p.add_argument("--outdir", default="data_hose_daily", help="Output directory for daily CSV files")
    p.add_argument("--weekly-outdir", help="Optional output directory for weekly CSV files resampled from daily data")
    p.add_argument("--start", default="2017-01-01", help="Start date YYYY-MM-DD")
    p.add_argument("--end", default=dt.datetime.today().strftime("%Y-%m-%d"), help="End date YYYY-MM-DD")
    p.add_argument("--source-list", help="Optional file with one ticker per line instead of the HOSE list")
    p.add_argument("--hose", action="store_true", help="Crawl all HOSE-listed stocks (default when --source-list is not given)")
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()
    crawl_all(args.outdir, args.start, args.end, args.source_list, args.weekly_outdir)
