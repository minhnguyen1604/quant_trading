#!/usr/bin/env python3
"""
Normalize price CSV files and store cleaned data into a single SQLite database table.

Behavior:
- Input CSVs are expected in the messy multi-row header format produced by
  the crawler (two header rows: metrics row and ticker row, followed by Date index).
- The script extracts the per-ticker metric columns (Close/High/Low/Open/Volume),
  drops the extra header rows, renames the index to `Date` and writes a single
  consolidated table `prices` in SQLite with columns:
    Ticker, Date, Close, High, Low, Open, Volume

Usage:
    python scripts/normalize_and_store.py --indir data_hose --db data_prices.db

Options:
    --indir   directory with CSV files (default: data_hose)
    --outdir  directory to write cleaned CSVs (optional)
    --db      sqlite file (default: data_prices.db)
    --limit   process only first N files (for testing)

"""
import argparse
import glob
import os
import sqlite3
from typing import Optional

import pandas as pd
from tqdm import tqdm


def clean_file(path: str, outdir: Optional[str] = None) -> Optional[pd.DataFrame]:
    """Read a messy CSV and return a cleaned DataFrame with Date index and
    columns [Close, High, Low, Open, Volume]. If outdir is provided, also
    write a cleaned CSV there (same filename).
    Returns DataFrame with a `Ticker` column (not index) ready for DB insert.
    """
    basename = os.path.basename(path)
    ticker = os.path.splitext(basename)[0]

    try:
        df = pd.read_csv(path, header=[0, 1], index_col=0, parse_dates=True)
    except Exception:
        # fallback: try reading single-row header and assume it's already OK
        try:
            df2 = pd.read_csv(path, header=0, index_col=0, parse_dates=True)
            df2.index.name = "Date"
            # ensure required columns exist
            cols = [c for c in ["Close", "High", "Low", "Open", "Volume"] if c in df2.columns]
            if not cols:
                return None
            cleaned = df2[[c for c in ["Close", "High", "Low", "Open", "Volume"] if c in df2.columns]]
            cleaned = cleaned.rename_axis("Date").reset_index()
            cleaned["Ticker"] = ticker
            return cleaned
        except Exception:
            return None

    # columns are MultiIndex: (metric, ticker)
    if df.columns.nlevels == 2:
        # try to select the block for our ticker
        lvl1_vals = list(df.columns.get_level_values(1))
        # exact match first
        if ticker in lvl1_vals:
            cleaned = df.xs(ticker, axis=1, level=1)
        else:
            # maybe filename contains suffix like .VN; try variations
            candidates = set(lvl1_vals)
            chosen = None
            for c in candidates:
                if c.replace(".VN", "") == ticker.replace(".VN", ""):
                    chosen = c
                    break
            if chosen:
                cleaned = df.xs(chosen, axis=1, level=1)
            else:
                # if only one ticker present in file, use it
                uniq = list(dict.fromkeys(lvl1_vals))
                if len(uniq) == 1:
                    cleaned = df.xs(uniq[0], axis=1, level=1)
                else:
                    # as a last resort, collapse by metric: pick first column matching metric
                    out = pd.DataFrame(index=df.index)
                    for metric in ["Close", "High", "Low", "Open", "Volume"]:
                        cols = [c for c in df.columns if c[0] == metric]
                        if cols:
                            out[metric] = df[cols[0]]
                    cleaned = out
    else:
        # single-level columns; try to pick metrics directly
        cleaned = df[[c for c in ["Close", "High", "Low", "Open", "Volume"] if c in df.columns]]

    # ensure index name is Date
    cleaned.index.name = "Date"

    # keep only required columns in order
    for col in ["Close", "High", "Low", "Open", "Volume"]:
        if col not in cleaned.columns:
            cleaned[col] = pd.NA
    cleaned = cleaned[["Close", "High", "Low", "Open", "Volume"]]

    # reset to have Date as a column for DB insertion
    outdf = cleaned.reset_index()
    outdf["Ticker"] = ticker

    if outdir:
        os.makedirs(outdir, exist_ok=True)
        outpath = os.path.join(outdir, basename)
        outdf.to_csv(outpath, index=False)

    return outdf


def store_to_sqlite(df: pd.DataFrame, conn: sqlite3.Connection, table: str = "daily_prices"):
    # Ensure columns order
    df = df[["Ticker", "Date", "Close", "High", "Low", "Open", "Volume"]]
    # Convert Date to ISO string
    if not pd.api.types.is_string_dtype(df["Date"]):
        df["Date"] = df["Date"].dt.strftime("%Y-%m-%d")

    # Use UPSERT to avoid duplicate (Ticker, Date) entries
    rows = df.to_records(index=False)
    
    # Convert numpy types to native Python types to prevent sqlite3 from inserting them as BLOBs
    cleaned_rows = []
    for r in rows:
        cleaned_row = []
        for val in r:
            if pd.isna(val):
                cleaned_row.append(None)
            elif hasattr(val, 'item'):
                cleaned_row.append(val.item())
            else:
                cleaned_row.append(val)
        cleaned_rows.append(cleaned_row)

    cur = conn.cursor()
    query = f"""
        INSERT INTO {table} (Ticker, Date, Close, High, Low, Open, Volume)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(Ticker, Date) DO UPDATE SET
            Close=excluded.Close,
            High=excluded.High,
            Low=excluded.Low,
            Open=excluded.Open,
            Volume=excluded.Volume
    """
    cur.executemany(query, cleaned_rows)
    conn.commit()


def dedupe_db(conn: sqlite3.Connection):
    # No-op: dedup is handled by UPSERT on insert
    return


def ensure_table(conn: sqlite3.Connection, table: str = "daily_prices"):
    cur = conn.cursor()
    cur.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {table} (
            Ticker TEXT NOT NULL,
            Date TEXT NOT NULL,
            Close REAL,
            High REAL,
            Low REAL,
            Open REAL,
            Volume REAL,
            Sector TEXT,
            Industry TEXT,
            PRIMARY KEY (Ticker, Date)
        )
        """
    )
    cur.execute(f"CREATE INDEX IF NOT EXISTS idx_{table}_ticker_date ON {table}(Ticker, Date)")
    conn.commit()


def backfill_sectors_in_db(conn: sqlite3.Connection, table: str):
    cur = conn.cursor()
    
    # 1. Ensure columns exist in case the table was created under old schema
    cur.execute(f"PRAGMA table_info({table})")
    columns = [col[1] for col in cur.fetchall()]
    if 'Sector' not in columns:
        cur.execute(f"ALTER TABLE {table} ADD COLUMN Sector TEXT")
    if 'Industry' not in columns:
        cur.execute(f"ALTER TABLE {table} ADD COLUMN Industry TEXT")
    conn.commit()

    # 2. Update new rows that have NULL Sector or Industry by copying from existing non-null rows of the same Ticker
    query = f"""
        UPDATE {table}
        SET 
            Sector = (
                SELECT t.Sector FROM {table} t 
                WHERE t.Ticker = {table}.Ticker AND t.Sector IS NOT NULL 
                LIMIT 1
            ),
            Industry = (
                SELECT t.Industry FROM {table} t 
                WHERE t.Ticker = {table}.Ticker AND t.Industry IS NOT NULL 
                LIMIT 1
            )
        WHERE Sector IS NULL OR Industry IS NULL
    """
    cur.execute(query)
    conn.commit()
    
    # 3. For any brand-new tickers that still have NULL, fetch via yfinance
    cur.execute(f"SELECT DISTINCT Ticker FROM {table} WHERE Sector IS NULL")
    new_tickers = [row[0] for row in cur.fetchall()]
    if new_tickers:
        print(f"Fetching sectors for {len(new_tickers)} new tickers...")
        import yfinance as yf
        sector_map = {
            'Financial Services': 'Dịch vụ Tài chính',
            'Real Estate': 'Bất động sản',
            'Basic Materials': 'Nguyên vật liệu',
            'Industrials': 'Công nghiệp',
            'Consumer Cyclical': 'Tiêu dùng chu kỳ',
            'Consumer Defensive': 'Tiêu dùng thiết yếu',
            'Healthcare': 'Y tế',
            'Utilities': 'Tiện ích công cộng',
            'Technology': 'Công nghệ',
            'Energy': 'Năng lượng',
            'Communication Services': 'Dịch vụ Truyền thông'
        }
        for ticker in new_tickers:
            yfinance_ticker = ticker
            if not ticker.endswith('.VN') and not ticker.endswith('.HO') and not ticker.endswith('.HS'):
                yfinance_ticker = ticker + '.VN'
            try:
                t = yf.Ticker(yfinance_ticker)
                sector_en = t.info.get('sector')
                industry_en = t.info.get('industry')
                
                sector_vi = sector_map.get(sector_en, sector_en) if sector_en else 'Khác'
                industry_vi = industry_en if industry_en else 'Khác'
                
                cur.execute(f"UPDATE {table} SET Sector = ?, Industry = ? WHERE Ticker = ?", (sector_vi, industry_vi, ticker))
                conn.commit()
            except Exception:
                cur.execute(f"UPDATE {table} SET Sector = 'Khác', Industry = 'Khác' WHERE Ticker = ?", (ticker,))
                conn.commit()


def main(indir: str, outdir: Optional[str], db: str, limit: Optional[int], table: str = "daily_prices"):
    files = sorted(glob.glob(os.path.join(indir, "*.csv")))
    if limit:
        files = files[:limit]

    conn = sqlite3.connect(db)
    ensure_table(conn, table=table)
    processed = 0
    for f in tqdm(files, desc="files"):
        df = clean_file(f, outdir)
        if df is None or df.empty:
            continue
        store_to_sqlite(df, conn, table=table)
        processed += 1
    
    # Backfill sectors for newly added price rows
    backfill_sectors_in_db(conn, table=table)
    
    conn.close()
    print(f"Processed {processed} files. Table: {table}, DB: {db}")


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--indir", default="data_hose_daily", help="Directory containing messy CSV files")
    p.add_argument("--outdir", help="Optional directory to write cleaned CSV files")
    p.add_argument("--db", default="data_prices.db", help="SQLite database file")
    p.add_argument("--limit", type=int, help="Process only first N files (for testing)")
    p.add_argument("--table", default="daily_prices", choices=["daily_prices", "weekly_prices"], help="Database table name")
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()
    main(args.indir, args.outdir, args.db, args.limit, table=getattr(args, "table", "daily_prices"))
