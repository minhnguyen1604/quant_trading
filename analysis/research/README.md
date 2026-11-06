# Research scripts (weekly EMA9/WMA45, Nov 2026)

Follow-up studies behind `tong_hop_hoi_thoai.md` (Vietnamese summary of the findings). They read `data_prices.db`
through `../common.py`, print their tables to stdout and are run from this folder:

```bash
cd analysis/research
python ledger.py && python build_xlsx.py ../output/so_lenh_ck_nh_12ma_catlo25.xlsx
```

Intermediate pickles (`*.pkl`) are written next to the scripts and are git-ignored. Several scripts reuse another
script's code (`exec` of its first part, or `import pool`), so keep them together.

| Script | Summary section | What it does |
|---|---|---|
| `stop_levels.py` | 1 | Fixed stop levels 15–22% (weekly close vs intraweek) on the 5 cyclical sectors |
| `interest.py` | 2 | 1 tỷ split equally, idle cash earning 0/5/7%, vs buy & hold, per sector |
| `cknh.py` | 3 | Securities and banks: rules, yearly values, per ticker, top trades |
| `ck_ticker.py`, `nh_ticker.py` | 3 | Per-ticker results and full trade lists (securities / banks) |
| `peak_exit.py` | 4 | ~30 exit rules aimed at selling nearer the top (trailing, ATR, RSI, MA, 2x WMA45, re-entry) |
| `ext_check.py` | 4 | Threshold sensitivity and trigger list for the "close ≥ 2x WMA45" exit |
| `fpt_vic.py`, `vic_sl.py` | 5 | FPT/VIC/VHM with exit variants; the VIC 8/2023 trade with 18% stops |
| `ck_sl_ext.py`, `ck_sl_lv.py`, `ck_reentry.py` | 6 | Securities: intraweek stop, 2x WMA45 exit, re-entry after a stop-out, stop-level sensitivity |
| `screen.py`, `screen_port.py` | 7 | Pre-trade stock-selection features on all HOSE trades; filtered portfolios; `watchlist.csv` snapshot |
| `pool.py` | 8 | Shared-capital engine (max N positions, leader priority) on all HOSE |
| `cknh_pool.py` | 8 | Securities + banks without VCB/BID/CTG: equal split vs shared pool |
| `pool_cash.py` | 8 | Shared pool with realistic cash: money-market fund vs 3/6/12-month deposits with early-withdrawal penalty |
| `ledger.py`, `build_xlsx.py` | 8 | Trade-by-trade ledger of the 12-slot, 25%-stop configuration and the Excel workbook built from it |

Numbers depend on the price snapshot in `data_prices.db` (prices up to 2026-11-03). Rebuild the DB from the committed
CSVs (see the main README) to reproduce them.
