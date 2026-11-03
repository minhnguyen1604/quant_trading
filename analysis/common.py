"""Shared helpers for the analysis scripts: data loading, a fast re-implementation of the
EMA/WMA crossover backtest (matches backtesting.py to ~0.01pp), exit-rule variants, portfolio maths
and the sector groups.

The engine is long-only and all-in per ticker: signal on a bar's close, fill at the next bar's open,
commission charged on both sides. Each ticker is an independent "sleeve"; portfolios combine sleeves
that all start with the same capital (no rebalancing).
"""
import os
import sqlite3
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent
DB = Path(os.environ.get("PRICES_DB", ROOT / "data_prices.db"))
OUT = HERE / "output"
COMM = 0.0015
PORT_START = pd.Timestamp("2017-11-06")  # first weeks after the 45-week warm-up of the 2017 tickers

SECTORS = ["Chứng khoán", "Bất động sản", "Ngân hàng", "Thép", "Vận tải"]
# VN30 basket as of 2026-11-03 (SSI iBoard). Using today's members for the past is a look-ahead bias.
VN30 = {"ACB", "BID", "BSR", "CTG", "FPT", "GAS", "GVR", "HDB", "HPG", "LPB", "MBB", "MCH", "MSN", "MWG", "SAB",
        "SHB", "SSB", "SSI", "STB", "TCB", "TCX", "VCB", "VHM", "VIB", "VIC", "VJC", "VNM", "VPB", "VPL", "VRE"}


# ---------------------------------------------------------------- data
def load(table="weekly_prices", min_bars=46):
    if not DB.exists():
        sys.exit(f"{DB} not found - build it first (see README: normalize_and_store.py)")
    con = sqlite3.connect(DB)
    df = pd.read_sql(f"SELECT Ticker, Date, Open, High, Low, Close, Volume FROM {table} ORDER BY Ticker, Date", con)
    df["Date"] = pd.to_datetime(df["Date"])
    out = {t: g.set_index("Date")[["Open", "High", "Low", "Close", "Volume"]].astype(float) for t, g in df.groupby("Ticker")}
    return {t: d for t, d in out.items() if len(d) >= min_bars}


def vnindex_weekly():
    """VNINDEX weekly closes (Monday label), from the snapshot in analysis/vnindex_daily.csv."""
    v = pd.read_csv(HERE / "vnindex_daily.csv", parse_dates=["Date"]).set_index("Date").Close
    return v.groupby(v.index - pd.to_timedelta(v.index.weekday, unit="D")).last()


def groups(tickers):
    """Sector groups from analysis/industries.csv (yfinance industries, snapshot) with manual fixes."""
    ind = pd.read_csv(HERE / "industries.csv").set_index("Ticker").Industry
    g = {
        "Chứng khoán": set(ind[ind == "Capital Markets"].index) | {"TCX"},
        # HAG is listed as real estate by yfinance but its business is now agriculture
        "Bất động sản": set(ind[ind.isin(["Real Estate - Development", "Real Estate - Diversified", "Real Estate Services"])].index) - {"HAG"},
        "Ngân hàng": set(ind[ind == "Banks - Regional"].index),
        "Thép": set(ind[ind == "Steel"].index),
        "Vận tải": set(ind[ind.isin(["Marine Shipping", "Integrated Freight & Logistics", "Airlines", "Airports & Air Services"])].index) | {"VNS"},
        "VN30 (hiện tại)": set(VN30),
    }
    cyc = set().union(*[g[k] for k in SECTORS])
    g["5 ngành chu kỳ (gộp)"] = cyc
    g["Các ngành còn lại"] = set(tickers) - cyc
    g["Toàn bộ HOSE"] = set(tickers)
    return {k: sorted(v & set(tickers)) for k, v in g.items()}


# ---------------------------------------------------------------- indicators
def ema(x, n):
    return pd.Series(x).ewm(span=n, adjust=False).mean().values


def wma(x, n):
    w = np.arange(1, n + 1, dtype=float)
    out = np.full(len(x), np.nan)
    if len(x) >= n:
        out[n - 1:] = np.convolve(x, w[::-1], mode="valid") / w.sum()
    return out


def sma(x, n):
    return pd.Series(x).rolling(n).mean().values


MA = {"ema": ema, "wma": wma, "sma": sma}


def _signals(c, fast, slow, fk, sk):
    f, s = MA[fk](c, fast), MA[sk](c, slow)
    valid = ~np.isnan(f) & ~np.isnan(s)
    up = np.r_[False, (f[:-1] < s[:-1]) & valid[:-1]] & (f > s) & valid
    dn = np.r_[False, (f[:-1] > s[:-1]) & valid[:-1]] & (f < s) & valid
    start = int(np.argmax(valid)) if valid.any() else len(c)
    return up, dn, start


# ---------------------------------------------------------------- crossover backtest
def run(df, fast=9, slow=45, comm=COMM, fk="ema", sk="wma", entry_on_close=False, path_stats=True):
    """Plain crossover. Returns (trades, equity normalised to 1, index of the first tradable bar)."""
    o, c = df["Open"].values, df["Close"].values
    n = len(c)
    up, dn, start = _signals(c, fast, slow, fk, sk)
    trades = []
    pos, ent_i, ent_px, cash, sig_i = False, -1, 0.0, 1.0, -1
    eq = np.ones(n)
    for i in range(n):
        eq[i] = cash * c[i] / ent_px if pos else cash
        if i == n - 1:
            break
        if not pos and up[i]:
            j, px = (i, c[i]) if entry_on_close else (i + 1, o[i + 1])
            pos, ent_i, ent_px, sig_i = True, j, px * (1 + comm), i
            if entry_on_close:
                eq[i] = cash * c[i] / ent_px
        elif pos and dn[i]:
            px = o[i + 1] * (1 - comm)
            ret = px / ent_px - 1
            trades.append((sig_i, ent_i, i + 1, ent_px, px, ret, False))
            cash *= 1 + ret
            pos = False
    if pos:
        trades.append((sig_i, ent_i, n - 1, ent_px, c[-1], c[-1] / ent_px - 1, True))
    tr = pd.DataFrame(trades, columns=["sig_i", "entry_i", "exit_i", "entry_px", "exit_px", "ret", "open"])
    if len(tr) and path_stats:
        idx = df.index
        tr["entry_date"] = idx[tr.entry_i.values]
        tr["exit_date"] = idx[tr.exit_i.values]
        tr["bars"] = tr.exit_i - tr.entry_i
        lo, hi, cl = df["Low"].values, df["High"].values, df["Close"].values
        # MAE/MFE/peak close vs the entry cost, over the bars actually held (the exit fills at the open of exit_i)
        span = list(zip(tr.entry_i, tr.exit_i, tr.entry_px))
        tr["mae"] = [lo[a:max(a + 1, b)].min() / p - 1 for a, b, p in span]
        tr["mfe"] = [hi[a:max(a + 1, b)].max() / p - 1 for a, b, p in span]
        tr["peak_close"] = [cl[a:max(a + 1, b)].max() / p - 1 for a, b, p in span]
    return tr, pd.Series(eq, index=df.index), start


def run_exit(df, rule=None, fast=9, slow=45, comm=COMM):
    """Same entries as run(); exit on the crossover OR the extra rule, whichever comes first.

    rule keys: trail (fraction below the highest close since entry), be_after/be_level (once the peak
    close is be_after above entry, exit below entry*(1+be_level)), tp/tp_frac (limit take-profit),
    sl (stop below entry, on close), fast_after/fast_ma (once up fast_after, exit on a close below fast_ma).
    Close-based exits fill at the next open. Returns (trades, equity, start).
    """
    rule = rule or {}
    trail, be_after, be_level = rule.get("trail"), rule.get("be_after"), rule.get("be_level", 0.0)
    tp, tp_frac, sl = rule.get("tp"), rule.get("tp_frac", 1.0), rule.get("sl")
    fast_after, fast_ma = rule.get("fast_after"), rule.get("fast_ma", ("ema", 9))
    o, h, c = df["Open"].values, df["High"].values, df["Close"].values
    n = len(c)
    up, dn, start = _signals(c, fast, slow, "ema", "wma")
    fm = MA[fast_ma[0]](c, fast_ma[1]) if fast_after is not None else None
    cash, sh, pend, cur = 1.0, 0.0, None, None
    eq = np.ones(n)
    trades = []
    for i in range(n):
        if pend == "buy":
            px = o[i] * (1 + comm); sh = cash / px
            cur = dict(entry_i=i, entry_px=px, cost=cash, proceeds=0.0, peak=o[i], tp_done=False, open=False)
            cash = 0.0
        elif pend == "sell" and sh > 0:
            cash += sh * o[i] * (1 - comm); cur["proceeds"] += sh * o[i] * (1 - comm); sh = 0.0
            cur["exit_i"] = i; trades.append(cur); cur = None
        pend = None
        if sh > 0 and tp is not None and not cur["tp_done"]:
            target = cur["entry_px"] / (1 + comm) * (1 + tp)
            if h[i] >= target:
                fill = max(target, o[i]) if i > cur["entry_i"] else target
                q = sh * tp_frac
                cash += q * fill * (1 - comm); cur["proceeds"] += q * fill * (1 - comm); sh -= q
                cur["tp_done"] = True
                if sh <= 1e-12:
                    sh = 0.0; cur["exit_i"] = i; trades.append(cur); cur = None
        eq[i] = cash + sh * c[i]
        if i == n - 1:
            break
        if sh > 0:
            cur["peak"] = max(cur["peak"], c[i])
            base = cur["entry_px"] / (1 + comm)
            ex = dn[i]
            if trail is not None and c[i] <= cur["peak"] * (1 - trail): ex = True
            if be_after is not None and cur["peak"] >= base * (1 + be_after) and c[i] < base * (1 + be_level): ex = True
            if sl is not None and c[i] <= base * (1 - sl): ex = True
            if fast_after is not None and cur["peak"] >= base * (1 + fast_after) and c[i] < fm[i]: ex = True
            if ex: pend = "sell"
        elif cur is None and up[i]:
            pend = "buy"
    if cur is not None and sh > 0:
        cur["proceeds"] += sh * c[-1]; cur.update(exit_i=n - 1, open=True); trades.append(cur)
    tr = pd.DataFrame(trades, columns=["entry_i", "exit_i", "entry_px", "cost", "proceeds", "open"])
    if len(tr):
        tr["ret"] = tr.proceeds / tr.cost - 1
        tr["entry_date"] = df.index[tr.entry_i.values]
    else:
        tr["ret"], tr["entry_date"] = [], []
    return tr, pd.Series(eq, index=df.index), start


# ---------------------------------------------------------------- stats
def wilson(k, n, z=1.96):
    if n == 0: return (np.nan, np.nan)
    p = k / n; d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d; h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (c - h, c + h)


def mdd(x):
    x = np.asarray(x, float); return (x / np.maximum.accumulate(x) - 1).min()


def perf(r, freq=52):
    r = pd.Series(r).dropna(); eq = (1 + r).cumprod()
    cagr = eq.iloc[-1] ** (freq / len(r)) - 1
    down = r[r < 0].std() * np.sqrt(freq)
    m = mdd(np.r_[1, eq.values])
    return dict(CAGR=cagr * 100, Vol=r.std() * np.sqrt(freq) * 100, Sharpe=r.mean() / r.std() * np.sqrt(freq),
                Sortino=r.mean() * freq / down, MDD=m * 100, Calmar=cagr / -m, PosWeeks=(r > 0).mean() * 100, Total=(eq.iloc[-1] - 1) * 100)


def port(X):
    """Weekly returns of equal-start sleeves (columns), each sleeve normalised to 1 when it starts."""
    act = X.shift(1).notna() & X.notna()
    return (X.where(act).sum(axis=1) / X.shift(1).where(act).sum(axis=1) - 1).iloc[1:]


def sleeves(data, tickers, runner=run, start=PORT_START, **kw):
    """Run a backtest per ticker; return (strategy sleeves, buy&hold sleeves, trades) from the first tradable bar."""
    S, B, T = {}, {}, []
    for t in tickers:
        df = data[t]
        tr, eq, st = runner(df, **kw)
        if st >= len(df) - 1: continue
        S[t] = eq.iloc[st:] / eq.iloc[st]
        B[t] = df["Close"].iloc[st:] / df["Close"].iloc[st]
        if len(tr): T.append(tr.assign(ticker=t))
    S = pd.DataFrame(S).sort_index().ffill(); B = pd.DataFrame(B).sort_index().ffill()
    T = pd.concat(T, ignore_index=True) if T else pd.DataFrame()
    return S[S.index >= start], B[B.index >= start], T


def cluster_ci(trades, rng, reps=3000):
    """95% CI of the mean trade return, bootstrapping whole entry months (trades in a month are correlated)."""
    g = [x.ret.values for _, x in trades.groupby(trades.entry_date.dt.to_period("M"))]
    b = np.array([np.concatenate([g[i] for i in rng.integers(0, len(g), len(g))]).mean() for _ in range(reps)])
    return np.percentile(b, 2.5) * 100, np.percentile(b, 97.5) * 100, b


# ---------------------------------------------------------------- reporting
class _Tee:
    def __init__(self, *streams): self.streams = streams
    def write(self, s):
        for st in self.streams: st.write(s)
    def flush(self):
        for st in self.streams: st.flush()


def report(name):
    """Mirror everything printed from here on into analysis/output/<name>.txt."""
    OUT.mkdir(exist_ok=True)
    sys.stdout.reconfigure(encoding="utf-8")
    f = open(OUT / f"{name}.txt", "w", encoding="utf-8")
    sys.stdout = _Tee(sys.__stdout__, f)
    pd.set_option("display.width", 250); pd.set_option("display.max_columns", 40); pd.set_option("display.max_rows", 200)
    print(f"# {name}  |  data: {DB.name}, commission {COMM*100:.2f}%/side")
