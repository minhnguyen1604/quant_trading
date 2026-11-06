"""Which stocks suit weekly EMA9/WMA45? Pre-trade features measured at the signal close (no look-ahead), all HOSE trades."""
from pathlib import Path as _P
_HERE = _P(__file__).resolve().parent
import sys as _s; _s.stdout.reconfigure(encoding="utf-8")
import sys; sys.path.insert(0, str(_HERE.parent))
import numpy as np, pandas as pd, common as cm
pd.set_option("display.width", 250); pd.set_option("display.max_columns", 30)
data = cm.load()
ind = pd.read_csv(str(_HERE.parent / "industries.csv")).set_index("Ticker")
vni = cm.vnindex_weekly()
Cl = pd.DataFrame({t: d["Close"] for t, d in data.items()}).sort_index()
Vl = pd.DataFrame({t: d["Close"] * d["Volume"] for t, d in data.items()}).sort_index()
ret26 = Cl.pct_change(26, fill_method=None)
rs26 = ret26.rank(axis=1, pct=True)
ret52 = Cl.pct_change(52, fill_method=None)
rs52 = ret52.rank(axis=1, pct=True)
above = pd.DataFrame({t: pd.Series(cm.ema(d["Close"].values, 9) > cm.wma(d["Close"].values, 45), index=d.index) for t, d in data.items()}).sort_index()
above = above.where(Cl.notna())
# industry breadth: share of tickers in the same industry with EMA9 > WMA45
breadth = {}
for g, members in ind[ind.index.isin(Cl.columns)].groupby("Industry").groups.items():
    m = list(members)
    if len(m) >= 4:
        b = above[m].astype(float).mean(axis=1)
        for t in m: breadth[t] = b
vlog = np.log(vni); vw45 = pd.Series(cm.wma(vni.values, 45), index=vni.index); ve9 = pd.Series(cm.ema(vni.values, 9), index=vni.index)

rows = []
for t, df in data.items():
    tr, _, _ = cm.run(df)
    if not len(tr): continue
    c = df["Close"].values; idx = df.index; lr = np.diff(np.log(c), prepend=np.nan)
    tv = (df["Close"] * df["Volume"]).values
    for k, r in tr.iterrows():
        i = int(r.sig_i); d = idx[i]
        prev = tr[(tr.exit_i <= i) & ~tr.open]
        lo52 = max(0, i - 51); lo156 = max(0, i - 155)
        w = lr[max(1, i - 51):i + 1]
        er_den = np.nansum(np.abs(np.diff(c[lo52:i + 1])))
        rows.append(dict(
            t=t, date=d, ret=r.ret, open=r.open,
            vol52=np.nanstd(w) * np.sqrt(52) * 100 if len(w) > 20 else np.nan,
            amp156=c[lo156:i + 1].max() / c[lo156:i + 1].min() if i - lo156 >= 100 else np.nan,
            er52=abs(c[i] - c[lo52]) / er_den if er_den > 0 and i - lo52 >= 40 else np.nan,
            liq=np.nanmedian(tv[max(0, i - 25):i + 1]) / 1e9,
            rs26=rs26.at[d, t] if d in rs26.index else np.nan, rs52=rs52.at[d, t] if d in rs52.index else np.nan,
            dist_hi=c[i] / c[lo52:i + 1].max(),
            ret26=c[i] / c[max(0, i - 26)] - 1,
            breadth=breadth[t].get(d, np.nan) if t in breadth else np.nan,
            vni_up=float(ve9.asof(d) > vw45.asof(d)) if d >= vni.index[44] else np.nan,
            prev_n=len(prev), prev_mean=prev.ret.mean() if len(prev) else np.nan,
            prev_big=float((prev.ret > .5).any()) if len(prev) else np.nan,
            prev_max=prev.ret.max() if len(prev) else np.nan,
        ))
X = pd.DataFrame(rows)
X = X[~X.open].copy()
X["period"] = np.where(X.date.dt.year <= 2022, "2017-22", "2023-26")
X.to_pickle(str(_HERE) + r"/screen.pkl")


def stats(s):
    return pd.Series(dict(n=len(s), win=(s > 0).mean() * 100, mean=s.mean() * 100, median=s.median() * 100,
                          p_x2=(s >= 1).mean() * 100, p_loss20=(s < -.2).mean() * 100,
                          trim_mean=s.clip(upper=s.quantile(.95)).mean() * 100))


FEAT = {"vol52": "Biến động 52 tuần (%/năm)", "amp156": "Biên độ đỉnh/đáy 3 năm (lần)", "er52": "Độ 'thẳng' xu hướng 52 tuần",
        "liq": "Thanh khoản (tỷ VND/tuần, TV 26 tuần)", "rs26": "Sức mạnh giá 26 tuần (xếp hạng toàn sàn)",
        "rs52": "Sức mạnh giá 52 tuần (xếp hạng)", "dist_hi": "Giá / đỉnh 52 tuần", "breadth": "% mã cùng ngành đang EMA9>WMA45",
        "prev_mean": "Lãi TB các lệnh trước của mã", "prev_max": "Lệnh tốt nhất trước đó của mã"}
print(f"Tổng số lệnh đã đóng: {len(X)}  ({(X.period=='2017-22').sum()} lệnh 2017-22, {(X.period=='2023-26').sum()} lệnh 2023-26)")
print("Cột: số lệnh | % thắng | lãi TB | trung vị | % lệnh ≥x2 | % lệnh lỗ >20% | lãi TB cắt đuôi 5% trên\n")
summ = []
for f, name in FEAT.items():
    S = X.dropna(subset=[f]).copy()
    S["q"] = pd.qcut(S[f].rank(method="first"), 5, labels=["Q1 thấp", "Q2", "Q3", "Q4", "Q5 cao"])
    print(f"===== {name} [{f}]")
    edges = S.groupby("q", observed=True)[f].agg(["min", "max"]).round(2)
    out = []
    for per in ["2017-22", "2023-26"]:
        g = S[S.period == per].groupby("q", observed=True).ret.apply(stats).unstack()
        g.columns = pd.MultiIndex.from_product([[per], g.columns]); out.append(g)
    tab = pd.concat([edges] + out, axis=1)
    print(tab.round(1).to_string(), "\n")
    for per in ["2017-22", "2023-26"]:
        P = S[S.period == per]
        summ.append(dict(feature=name, period=per, spearman=P[f].corr(P.ret, method="spearman"),
                         q5_minus_q1_median=(P[P.q == "Q5 cao"].ret.median() - P[P.q == "Q1 thấp"].ret.median()) * 100,
                         q5_minus_q1_mean=(P[P.q == "Q5 cao"].ret.mean() - P[P.q == "Q1 thấp"].ret.mean()) * 100))
print("===== TÓM TẮT: tương quan hạng (Spearman) giữa tiêu chí và lãi lệnh")
print(pd.DataFrame(summ).pivot(index="feature", columns="period").round(3).to_string())
print("\n===== Thị trường chung (VNINDEX EMA9>WMA45 lúc có tín hiệu)")
for per in ["2017-22", "2023-26"]:
    P = X[X.period == per].dropna(subset=["vni_up"])
    print(per, pd.concat({"VNI xu hướng tăng": stats(P[P.vni_up == 1].ret), "VNI xu hướng giảm": stats(P[P.vni_up == 0].ret)}, axis=1).T.round(1).to_string(), sep="\n")
