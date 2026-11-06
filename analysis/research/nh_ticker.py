from pathlib import Path as _P
_HERE = _P(__file__).resolve().parent
import sys as _s; _s.stdout.reconfigure(encoding="utf-8")
import sys; sys.path.insert(0, str(_HERE.parent))
import numpy as np, pandas as pd, common as cm
data = cm.load(); G = cm.groups(data); P0 = pd.Timestamp(cm.PORT_START)
pd.set_option("display.width", 250)
def one(t, rate):
    wk = (1 + rate) ** (1 / 52); df = data[t]; tr, eq, st = cm.run(df); idx = df.index
    eq = pd.Series(np.asarray(eq, float), index=idx); inv = np.zeros(len(df), bool)
    for a, z, op in zip(tr.entry_i, tr.exit_i, tr.open): inv[a:(z + 1 if op else z)] = True
    g = (eq / eq.shift(1)).fillna(1.0).values; g = np.where(inv, g, g * wk); g[np.arange(len(df)) <= st] = wk
    v = pd.Series(g, index=idx)[idx > P0].cumprod()
    b = df["Close"] / df["Close"].shift(1); b[np.arange(len(df)) <= st] = wk; b = b[idx > P0].cumprod()
    return v, b, tr, st, inv
rows = []
for t in G["Ngân hàng"]:
    v7, b, tr, st, inv = one(t, .07); v0, _, _, _, _ = one(t, 0)
    yrs = (v7.index[-1] - P0).days / 365.25
    C = tr[~tr.open] if len(tr) else pd.DataFrame({"ret": []})
    rows.append(dict(Mã=t, Bắt_đầu=data[t].index[st + 1].date() if st + 1 < len(data[t]) else None, Lệnh=len(C), Win=f"{(C.ret>0).sum()}/{len(C)}",
                     KhôngLãi=v0.iloc[-1], Gửi7=v7.iloc[-1], CAGR7=(v7.iloc[-1] ** (1/yrs) - 1) * 100, MDD=cm.mdd(np.r_[1, v7.values]) * 100,
                     BH=b.iloc[-1], BH_CAGR=(b.iloc[-1] ** (1/yrs) - 1) * 100, BH_MDD=cm.mdd(np.r_[1, b.values]) * 100,
                     TiềnMặt=(1 - inv[data[t].index > P0].mean()) * 100, Đang_giữ=bool(tr.open.any()) if len(tr) else False))
R = pd.DataFrame(rows).sort_values("Gửi7", ascending=False)
print(R.round(2).to_string(index=False))
for t in R["Mã"].tolist():
    df = data[t]; tr, eq, st = cm.run(df); idx = df.index
    print(f"\n=== {t}  (giá điều chỉnh, VND)")
    for _, r in tr.iterrows():
        print(f"  mua {idx[r.entry_i].date()} @{r.entry_px/(1+cm.COMM):>9,.0f}  bán {idx[r.exit_i].date()} @{(r.exit_px if not r.open else df.Close.iloc[-1]):>9,.0f}  "
              f"{r.ret*100:+7.1f}%  {int(r.exit_i-r.entry_i):3d} tuần  đỉnh {r.peak_close*100:+6.1f}%  sâu nhất {r.mae*100:+6.1f}%{'  (ĐANG GIỮ)' if r.open else ''}")
    v7, b, _, _, _ = one(t, .07); v0, _, _, _, _ = one(t, 0)
    Y = pd.DataFrame({"PP+7%": v7.groupby(v7.index.year).last(), "PP": v0.groupby(v0.index.year).last(), "B&H": b.groupby(b.index.year).last()})
    print("  Giá trị cuối năm (1 tỷ ban đầu):", " | ".join(f"{y}: {r['PP+7%']:.2f}/{r['B&H']:.2f}" for y, r in Y.iterrows()))
