"""Portfolio test of pre-trade filters on all HOSE (equal sleeves, 7% on idle cash); entries skipped when the filter fails."""
from pathlib import Path as _P
_HERE = _P(__file__).resolve().parent
import sys as _s; _s.stdout.reconfigure(encoding="utf-8")
import sys; sys.path.insert(0, str(_HERE.parent))
import numpy as np, pandas as pd, common as cm
pd.set_option("display.width", 250)
data = cm.load(); P0 = pd.Timestamp(cm.PORT_START); COMM = cm.COMM; WK = 1.07 ** (1 / 52)
vni = cm.vnindex_weekly(); vup = pd.Series(cm.ema(vni.values, 9) > cm.wma(vni.values, 45), index=vni.index)
vup[vni.index[:44]] = np.nan

F = {}
for t, df in data.items():
    c = df["Close"]; tv = c * df["Volume"]
    F[t] = pd.DataFrame(dict(
        liq=tv.rolling(26, min_periods=8).median() / 1e9,
        amp=c.rolling(156, min_periods=100).max() / c.rolling(156, min_periods=100).min(),
        vol=np.log(c).diff().rolling(52, min_periods=20).std() * np.sqrt(52) * 100,
        dist=c / c.rolling(52, min_periods=1).max(),
        vup=vup.reindex(df.index, method="ffill")))


def sim(t, ok):
    df = data[t]; o, c = df["Open"].values, df["Close"].values; n = len(c)
    up, dn, st = cm._signals(c, 9, 45, "ema", "wma")
    cash, sh, pend, eq, trades, ent = 1.0, 0.0, None, np.ones(n), [], None
    for i in range(n):
        if pend == "buy": sh = cash / (o[i] * (1 + COMM)); ent = (i, cash); cash = 0.0
        elif pend == "sell": cash = sh * o[i] * (1 - COMM); sh = 0.0; trades.append((ent[0], i, cash / ent[1] - 1, df.index[ent[0]]))
        pend = None
        eq[i] = cash + sh * c[i]
        if i == n - 1: break
        cash *= WK
        if sh > 0 and dn[i]: pend = "sell"
        elif sh == 0 and up[i] and ok[i]: pend = "buy"
    return pd.Series(eq, index=df.index), st, pd.DataFrame(trades, columns=["a", "z", "ret", "date"])


def port(filt, tks=None):
    tks = tks or list(data); vals, Ts, expo = {}, [], {}
    for t in tks:
        f = F[t]; ok = filt(f).fillna(False).values.astype(bool)
        eq, st, T = sim(t, ok); idx = eq.index
        g = (eq / eq.shift(1)).fillna(1.0).values; g[np.arange(len(g)) <= st] = WK
        vals[t] = pd.Series(g, index=idx)[idx > P0]
        if len(T): Ts.append(T.assign(t=t))
    V = pd.DataFrame(vals).sort_index().fillna(WK).cumprod().sum(1) / len(tks)
    T = pd.concat(Ts) if Ts else pd.DataFrame(columns=["ret", "date"])
    sp = pd.Timestamp("2022-12-31"); a = V[V.index <= sp]; b = V[V.index > sp]
    return dict(Cuối_tỷ=V.iloc[-1], CAGR=(V.iloc[-1] ** (365.25 / (V.index[-1] - P0).days) - 1) * 100, MDD=cm.mdd(np.r_[1, V.values]) * 100,
                CAGR_17_22=(a.iloc[-1] ** (365.25 / (a.index[-1] - P0).days) - 1) * 100,
                CAGR_23_26=((b.iloc[-1] / a.iloc[-1]) ** (365.25 / (b.index[-1] - a.index[-1]).days) - 1) * 100,
                Lệnh=len(T), Win=(T.ret > 0).mean() * 100, TB_lệnh=T.ret.mean() * 100,
                TB_17_22=T[T.date.dt.year <= 2022].ret.mean() * 100, TB_23_26=T[T.date.dt.year > 2022].ret.mean() * 100)


FILTERS = {
    "0. Không lọc (toàn HOSE)": lambda f: f.liq.notna() | True,
    "1. Thanh khoản ≥1 tỷ/tuần": lambda f: f.liq >= 1,
    "2. Biên độ 3 năm ≥2 lần": lambda f: f.amp >= 2,
    "3. Biến động ≥30%/năm": lambda f: f.vol >= 30,
    "4. Giá thấp hơn đỉnh 52 tuần ≥15%": lambda f: f.dist <= .85,
    "5. VNINDEX chưa vào xu hướng tăng": lambda f: f.vup == 0,
    "6. = 1 + 2": lambda f: (f.liq >= 1) & (f.amp >= 2),
    "7. = 1 + 2 + 4": lambda f: (f.liq >= 1) & (f.amp >= 2) & (f.dist <= .85),
    "8. = 1 + 2 + 5": lambda f: (f.liq >= 1) & (f.amp >= 2) & (f.vup == 0),
    "9. = 1 + 4": lambda f: (f.liq >= 1) & (f.dist <= .85),
    "10. = 1 + 3": lambda f: (f.liq >= 1) & (f.vol >= 30),
}
rows = [dict(Bộ_lọc=k, **port(v)) for k, v in FILTERS.items()]
print("===== TOÀN HOSE (402 mã), 1 tỷ chia đều, tiền nhàn rỗi 7%, chỉ vào lệnh khi tiêu chí đúng tại tuần có tín hiệu")
print(pd.DataFrame(rows).set_index("Bộ_lọc").round(1).to_string())

# current watchlist: liquid, high-amplitude stocks; status now
last = []
for t, df in data.items():
    f = F[t].iloc[-1]; c = df["Close"].values
    e9, w45 = cm.ema(c, 9), cm.wma(c, 45)
    if np.isnan(w45[-1]): continue
    up, dn, st = cm._signals(c, 9, 45, "ema", "wma")
    lastup = np.where(up)[0]; wk_since = len(c) - 1 - lastup[-1] if len(lastup) else None
    last.append(dict(Mã=t, Thanh_khoản=f.liq, Biên_độ_3n=f.amp, Biến_động=f.vol, Giá_so_đỉnh52=f.dist * 100,
                     Trạng_thái="EMA9>WMA45" if e9[-1] > w45[-1] else "EMA9<WMA45",
                     Tuần_từ_lúc_cắt_lên=wk_since if e9[-1] > w45[-1] else None, Cách_WMA45=(c[-1] / w45[-1] - 1) * 100))
L = pd.DataFrame(last)
W = L[(L.Thanh_khoản >= 1) & (L.Biên_độ_3n >= 2)].sort_values("Biên_độ_3n", ascending=False)
print(f"\n===== Danh sách mã qua bộ lọc 6 (thanh khoản ≥1 tỷ/tuần, biên độ 3 năm ≥2 lần) tại tuần 2026-11-02: {len(W)} mã")
print(W.round(1).to_string(index=False))
W.to_csv(str(_HERE) + r"/watchlist.csv", index=False, encoding="utf-8-sig")
print("\nCác mã quen thuộc:")
print(L[L.Mã.isin(["VCB", "BID", "CTG", "VNM", "MSN", "GAS", "SAB", "PLX", "FPT", "VHM", "VIC", "SSI", "VND", "VIX", "HPG", "LPB", "SHB", "MBB", "TCB"])].round(1).to_string(index=False))
