"""Securities sector: base EMA9/WMA45 weekly, + intraweek stop -18%, + sell when close >= 2x WMA45 (all or half)."""
from pathlib import Path as _P
_HERE = _P(__file__).resolve().parent
import sys as _s; _s.stdout.reconfigure(encoding="utf-8")
import sys; sys.path.insert(0, str(_HERE.parent))
import numpy as np, pandas as pd, common as cm
data = cm.load(); G = cm.groups(data); P0 = pd.Timestamp(cm.PORT_START); COMM = cm.COMM
pd.set_option("display.width", 260)


def sim(t, R, rate=0.0):
    """R: sl_intra (resting stop below entry price, fills at stop or at the open on a gap), sl (close-based, next open),
    ext/ext_frac (sell ext_frac once when close >= WMA45*(1+ext), next open). Crossover exit always on."""
    df = data[t]; o, h, l, c = (df[k].values for k in ["Open", "High", "Low", "Close"]); n = len(c)
    up, dn, st = cm._signals(c, 9, 45, "ema", "wma"); w45 = cm.wma(c, 45); wk = (1 + rate) ** (1 / 52)
    cash, sh, pend, cur, eq, trades = 1.0, 0.0, None, None, np.ones(n), []
    def close_trade(i, why):
        nonlocal cur
        cur.update(exit_i=i, why=why); trades.append(cur); cur = None
    for i in range(n):
        if pend is not None:
            kind, q = pend; pend = None
            if kind == "buy":
                px = o[i] * (1 + COMM); sh = cash / px
                cur = dict(entry_i=i, ref=o[i], cost=cash, proceeds=0.0, ext_done=False, low=l[i], peak=c[i]); cash = 0.0
            elif sh > 0:
                qq = sh * q; cash += qq * o[i] * (1 - COMM); cur["proceeds"] += qq * o[i] * (1 - COMM); sh -= qq
                if sh < 1e-12: sh = 0.0; close_trade(i, kind)
        if sh > 0 and "sl_intra" in R:
            stop = cur["ref"] * (1 - R["sl_intra"])
            if l[i] <= stop:
                fill = min(o[i], stop) if i > cur["entry_i"] else stop
                cash += sh * fill * (1 - COMM); cur["proceeds"] += sh * fill * (1 - COMM); sh = 0.0; close_trade(i, "sl_intra")
        if cur is not None: cur["low"] = min(cur["low"], l[i]); cur["peak"] = max(cur["peak"], c[i])
        eq[i] = cash + sh * c[i]
        if i == n - 1: break
        cash *= wk
        if sh > 0:
            if dn[i]: pend = ("cross", 1.0)
            elif "sl" in R and c[i] <= cur["ref"] * (1 - R["sl"]): pend = ("sl", 1.0)
            elif "ext" in R and not cur["ext_done"] and c[i] >= w45[i] * (1 + R["ext"]):
                cur["ext_done"] = True; pend = ("ext", R.get("ext_frac", 1.0))
        elif cur is None and up[i]:
            pend = ("buy", 1.0)
        elif cur is not None and sh == 0:  # partial leftovers cannot happen; safety
            pass
    if cur is not None:
        cur["proceeds"] += sh * c[-1]; cur.update(exit_i=n - 1, why="open"); trades.append(cur)
    T = pd.DataFrame(trades)
    if len(T):
        T["ret"] = T.proceeds / T.cost - 1; T["t"] = t
        T["entry_date"] = df.index[T.entry_i.values]; T["exit_date"] = df.index[T.exit_i.values]
        T["mae"] = T.low / T.ref - 1; T["peak_ret"] = T.peak / T.ref - 1
    return pd.Series(eq, index=df.index), st, T


def portfolio(tks, R):
    wk = 1.07 ** (1 / 52); vals, ends, Ts = {}, {}, []
    for t in tks:
        eq, st, T = sim(t, R, 0.07); idx = eq.index
        g = (eq / eq.shift(1)).fillna(1.0).values; g[np.arange(len(g)) <= st] = wk
        s = pd.Series(g, index=idx)[idx > P0]; vals[t] = s; ends[t] = s.cumprod()
        _, _, T0 = sim(t, R, 0.0)
        if len(T0): Ts.append(T0)
    V = pd.DataFrame(vals).sort_index().fillna(wk).cumprod().sum(1) / len(tks)
    return V, pd.concat(Ts, ignore_index=True), pd.DataFrame(ends).sort_index()


def summary(V, T):
    C = T[T.why != "open"]; split = pd.Timestamp("2022-12-31")
    a = V[V.index <= split]; b = V[V.index > split]
    w, l = C.ret[C.ret > 0], C.ret[C.ret <= 0]
    return dict(Cuối_tỷ=V.iloc[-1], CAGR=(V.iloc[-1] ** (365.25 / (V.index[-1] - P0).days) - 1) * 100, MDD=cm.mdd(np.r_[1, V.values]) * 100,
                CAGR_17_22=(a.iloc[-1] ** (365.25 / (a.index[-1] - P0).days) - 1) * 100,
                CAGR_23_26=((b.iloc[-1] / a.iloc[-1]) ** (365.25 / (b.index[-1] - a.index[-1]).days) - 1) * 100,
                Lệnh=len(C), Win=(C.ret > 0).mean() * 100, TB_lệnh=C.ret.mean() * 100, TB_thắng=w.mean() * 100, TB_thua=l.mean() * 100,
                RR=w.mean() / -l.mean(), Lỗ_tệ_nhất=C.ret.min() * 100, Lỗ_quá_20=int((C.ret < -.2).sum()), Lãi_x2=int((C.ret >= 1).sum()))


RULES = {
    "1. Gốc": {},
    "2. Cắt lỗ -18% trong tuần": {"sl_intra": .18},
    "3. Cắt lỗ -18% đóng cửa tuần": {"sl": .18},
    "4. x2 WMA45 bán hết": {"ext": 1.0},
    "5. x2 WMA45 bán 1/2": {"ext": 1.0, "ext_frac": .5},
    "6. Cắt -18% trong tuần + x2 bán hết": {"sl_intra": .18, "ext": 1.0},
    "7. Cắt -18% trong tuần + x2 bán 1/2": {"sl_intra": .18, "ext": 1.0, "ext_frac": .5},
}
tks = G["Chứng khoán"]
res, store = [], {}
for name, R in RULES.items():
    V, T, E = portfolio(tks, R); store[name] = (V, T, E)
    res.append(dict(Cách=name, **summary(V, T)))
print("===== NGÀNH CHỨNG KHOÁN (20 mã), 1 tỷ chia đều, tiền nhàn rỗi 7%, 2017-11-06 .. 2026-11-02")
print(pd.DataFrame(res).set_index("Cách").round(1).to_string())

# Yearly value
print("\nGiá trị cuối năm (tỷ):")
print(pd.DataFrame({k[:2]: v[0].groupby(v[0].index.year).last() for k, v in store.items()}).round(2).to_string())

# Per ticker: base vs 2 vs 6 vs 7
print("\nTừng mã (1 tỷ mỗi mã, gửi 7%):")
per = pd.DataFrame({k: v[2].iloc[-1] for k, v in store.items() if k[0] in "124567"})
per.columns = ["Gốc", "SL18 tuần", "x2 bán hết", "x2 bán 1/2", "SL18+x2 hết", "SL18+x2 1/2"]
print(per.sort_values("Gốc", ascending=False).round(2).to_string())

# Stop-loss events
T2 = store["2. Cắt lỗ -18% trong tuần"][1]; T1 = store["1. Gốc"][1]
s = T2[T2.why == "sl_intra"]
print(f"\nSố lần lệnh dừng -18% khớp: {len(s)}; lỗ khi khớp: TB {s.ret.mean()*100:.1f}%, tệ nhất {s.ret.min()*100:.1f}% (do gap)")
print("Chi tiết các lần khớp cắt lỗ (so với cách gốc cùng lệnh):")
for _, r in s.iterrows():
    b = T1[(T1.t == r.t) & (T1.entry_i == r.entry_i)]
    bret = b.ret.iloc[0] * 100 if len(b) else np.nan
    print(f"  {r.t:4s} mua {r.entry_date.date()} cắt {r.exit_date.date()} {r.ret*100:+6.1f}%   | cách gốc: {bret:+7.1f}%")
x = store["4. x2 WMA45 bán hết"][1]; x = x[x.why == "ext"]
print(f"\nSố lần bán do x2 WMA45: {len(x)}")
for _, r in x.iterrows():
    b = T1[(T1.t == r.t) & (T1.entry_i == r.entry_i)]
    print(f"  {r.t:4s} mua {r.entry_date.date()} bán {r.exit_date.date()} {r.ret*100:+6.1f}%   | cách gốc: {b.ret.iloc[0]*100:+7.1f}%  (đỉnh {r.peak_ret*100:+.0f}% tới lúc bán)")
