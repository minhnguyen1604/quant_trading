#!/usr/bin/env python3
"""
Run full daily update: crawl HOSE (full adjusted history) then normalize CSVs and store into SQLite.

Usage:
    python scripts/run_daily_update.py --outdir data_hose_daily --db data_prices.db

This script calls `crawl_vnindex.py` and then `normalize_and_store.py` using
the same Python interpreter. It writes a small log file `daily_run.log` by
default in the repo root.
"""
import argparse
import datetime as dt
import subprocess
import sys
from pathlib import Path


def run(cmd, log_file=None):
    print("Running:", " ".join(cmd))
    res = subprocess.run(cmd)
    if res.returncode != 0:
        raise SystemExit(f"Command failed: {' '.join(cmd)} (rc={res.returncode})")


def main(outdir: str, db: str, start: str, end: str, limit: int, log: str):
    repo = Path(__file__).resolve().parents[1]
    py = sys.executable
    if outdir.endswith("_daily"):
        outdir_weekly = outdir.replace("_daily", "_weekly")
    else:
        outdir_weekly = outdir + "_weekly"


    # one crawl writes both daily and weekly (resampled) CSVs
    crawl_cmd = [py, str(repo / "scripts" / "crawl_vnindex.py"), "--outdir", outdir, "--weekly-outdir", outdir_weekly, "--start", start, "--end", end, "--hose"]
    if limit:
        crawl_cmd += ["--source-list", "tickers.txt"]

    normalize_cmd = [py, str(repo / "scripts" / "normalize_and_store.py"), "--indir", outdir, "--db", db, "--table", "daily_prices"]
    if limit:
        normalize_cmd += ["--limit", str(limit)]

    normalize_cmd_weekly = [py, str(repo / "scripts" / "normalize_and_store.py"), "--indir", outdir_weekly, "--db", db, "--table", "weekly_prices"]
    if limit:
        normalize_cmd_weekly += ["--limit", str(limit)]

    try:
        print("--- RUNNING CRAWL (DAILY + WEEKLY) ---")
        run(crawl_cmd, log)

        print("--- STORING DAILY ---")
        run(normalize_cmd, log)

        print("--- STORING WEEKLY ---")
        run(normalize_cmd_weekly, log)
    except SystemExit as e:
        print(e)
        raise


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--outdir", default="data_hose_daily")
    p.add_argument("--db", default="data_prices.db")
    p.add_argument("--start", default="2017-01-01")
    p.add_argument("--end", default=None)
    p.add_argument("--limit", type=int, help="Process only first N files (testing)")
    p.add_argument("--log", default="daily_run.log")
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()
    end = args.end if args.end is not None else dt.datetime.today().strftime("%Y-%m-%d")
    main(args.outdir, args.db, args.start, end, args.limit, args.log)
