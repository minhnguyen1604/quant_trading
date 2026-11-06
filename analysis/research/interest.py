from pathlib import Path as _P
_HERE = _P(__file__).resolve().parent
import sys as _s; _s.stdout.reconfigure(encoding="utf-8")
import sys; sys.path.insert(0, str(_HERE.parent))
import numpy as np, pandas as pd, common as cm
from functools import partial
data = cm.load(); G = cm.groups(data)
CAP = 1e9
END = None
def money(tks, rate, runner, **kw):
    """Dollar portfolio: CAP split equally at PORT_START; cash (incl. before a ticker becomes tradable) earns `rate`."""
    wk = (1 + rate) ** (1 / 52)
    vals, bh = {}, {}
    for t in tks:
        df = data[t]; tr, eq, st = runner(df, **kw)
        idx = df.index; eq = pd.Series(np.asarray(eq, float), index=idx)
        inv = np.zeros(len(df), bool)
        for a, z, op in zip(tr.entry_i, tr.exit_i, tr.open):
            inv[a:(z + 1 if op else z)] = True
        g = (eq / eq.shift(1)).fillna(1.0).values
        g = np.where(inv, g, g * wk)               # cash week: earn deposit interest
        g[np.arange(len(df)) <= st] = wk           # not tradable yet: whole sleeve in deposit
        s = pd.Series(g, index=idx)
        s = s[s.index > pd.Timestamp(cm.PORT_START)]
        vals[t] = s
        b = df["Close"] / df["Close"].shift(1); b[np.arange(len(df)) <= st] = wk
        bh[t] = b[b.index > pd.Timestamp(cm.PORT_START)]
    V = pd.DataFrame(vals).sort_index(); Bh = pd.DataFrame(bh).sort_index()
    # weeks before a ticker's first bar: deposit
    V = V.fillna(wk); Bh = Bh.fillna(wk)
    return (V.cumprod() * CAP / len(tks)).sum(axis=1), (Bh.cumprod() * CAP / len(tks)).sum(axis=1)

names = cm.SECTORS + ["5 ngành chu kỳ (gộp)", "VN30 (hiện tại)"]
rules = {"Gốc (EMA9/WMA45)": (cm.run, {}), "Trailing 25%": (cm.run_exit, {"rule": {"trail": .25}}), "Cắt lỗ 20%": (cm.run_exit, {"rule": {"sl": .20}})}
yrs = None
rows = []
for nm in names:
    tks = [t for t in G[nm] if t in data]
    for rname, (fn, kw) in rules.items():
        for rate in [0.0, 0.05, 0.07]:
            v, b = money(tks, rate, fn, **kw)
            yrs = (v.index[-1] - pd.Timestamp(cm.PORT_START)).days / 365.25
            if rname == "Gốc (EMA9/WMA45)" and rate == 0.07:
                r = v.pct_change().dropna()
                # 2018-2025 full years
                y = v.groupby(v.index.year).last(); y0 = v[v.index.year == 2017].iloc[-1]
                c8 = (y.loc[2025] / y0) ** (1 / 8) - 1
            rows.append(dict(Nhóm=nm, Quy_tắc=rname, Lãi_gửi=f"{rate:.0%}", Số_mã=len(tks), Cuối_tỷ=v.iloc[-1] / 1e9,
                             CAGR=((v.iloc[-1] / CAP) ** (1 / yrs) - 1) * 100, MDD=cm.mdd(np.r_[CAP, v.values]) * 100,
                             BH_tỷ=b.iloc[-1] / 1e9, BH_CAGR=((b.iloc[-1] / CAP) ** (1 / yrs) - 1) * 100, BH_MDD=cm.mdd(np.r_[CAP, b.values]) * 100))
    print("done", nm, flush=True)
R = pd.DataFrame(rows)
pd.set_option("display.width", 250)
print(f"Kỳ: {cm.PORT_START} .. {v.index[-1].date()}  ({yrs:.2f} năm)")
print(R.round(2).to_string(index=False))
sav = (1.07) ** yrs; print(f"Gửi tiết kiệm 7% toàn bộ: {sav:.3f} tỷ")
sav5 = (1.05) ** yrs; print(f"Gửi tiết kiệm 5% toàn bộ: {sav5:.3f} tỷ")
# yearly path for the 5-sector pool, base, 7%
tks = G["5 ngành chu kỳ (gộp)"]
for rname, (fn, kw) in rules.items():
    v7, b = money(tks, .07, fn, **kw); v0, _ = money(tks, 0.0, fn, **kw)
    print("\n", rname, "– giá trị cuối năm (tỷ): 7% | 0% | B&H")
    print(pd.DataFrame({"lai7": v7.groupby(v7.index.year).last() / 1e9, "lai0": v0.groupby(v0.index.year).last() / 1e9, "BH": b.groupby(b.index.year).last() / 1e9}).round(3).to_string())
