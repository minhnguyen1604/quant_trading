"""Securities sector: intraweek stop + re-entry while EMA9 is still above WMA45, + optional 2x WMA45 exit."""
from pathlib import Path as _P
_HERE = _P(__file__).resolve().parent
import sys as _s; _s.stdout.reconfigure(encoding="utf-8")
SP = str(_HERE)
exec(open(SP + "/ck_sl_ext.py", encoding="utf-8").read().split("RULES = {")[0])


def sim(t, R, rate=0.0):
    """Exits (whichever first): crossover down (next open), intraweek stop sl_intra below the buy price,
    ext: close >= WMA45*(1+ext) -> sell ext_frac (next open).
    reenter (only after a stop-out, only while EMA9 is still above WMA45, i.e. before the cross down):
      'entry' = weekly close back above the previous buy price; 'e9' = weekly close crosses back above EMA9.
    Each re-entry gets its own stop at sl_intra below its own buy price."""
    df = data[t]; o, h, l, c = (df[k].values for k in ["Open", "High", "Low", "Close"]); n = len(c)
    up, dn, st = cm._signals(c, 9, 45, "ema", "wma"); w45 = cm.wma(c, 45); e9 = cm.ema(c, 9); wk = (1 + rate) ** (1 / 52)
    cash, sh, pend, cur, eq, trades = 1.0, 0.0, None, None, np.ones(n), []
    epi, stopped, last_ref, n_re = False, False, None, 0
    maxre = R.get("max_reenter", 99)
    def close_trade(i, why):
        nonlocal cur
        cur.update(exit_i=i, why=why); trades.append(cur); cur = None
    for i in range(n):
        if pend is not None:
            kind, q = pend; pend = None
            if kind in ("buy", "rebuy"):
                px = o[i] * (1 + COMM); sh = cash / px
                cur = dict(entry_i=i, ref=o[i], cost=cash, proceeds=0.0, ext_done=False, low=l[i], peak=c[i], kind=kind); cash = 0.0
                last_ref = o[i]; stopped = False
            elif sh > 0:
                qq = sh * q; cash += qq * o[i] * (1 - COMM); cur["proceeds"] += qq * o[i] * (1 - COMM); sh -= qq
                if sh < 1e-12: sh = 0.0; close_trade(i, kind)
        if sh > 0 and "sl_intra" in R:
            stop = cur["ref"] * (1 - R["sl_intra"])
            if l[i] <= stop:
                fill = min(o[i], stop) if i > cur["entry_i"] else stop
                cash += sh * fill * (1 - COMM); cur["proceeds"] += sh * fill * (1 - COMM); sh = 0.0; close_trade(i, "sl_intra")
                stopped = True
        if cur is not None: cur["low"] = min(cur["low"], l[i]); cur["peak"] = max(cur["peak"], c[i])
        eq[i] = cash + sh * c[i]
        if i == n - 1: break
        cash *= wk
        if dn[i]:
            epi = False; stopped = False
            if sh > 0: pend = ("cross", 1.0)
            continue
        if sh > 0:
            if "sl" in R and c[i] <= cur["ref"] * (1 - R["sl"]): pend = ("sl", 1.0)
            elif "ext" in R and not cur["ext_done"] and c[i] >= w45[i] * (1 + R["ext"]):
                cur["ext_done"] = True; pend = ("ext", R.get("ext_frac", 1.0))
        elif cur is None:
            if up[i]:
                pend = ("buy", 1.0); epi = True; n_re = 0
            elif epi and stopped and R.get("reenter") and n_re < maxre:
                if R["reenter"] == "entry": ok = c[i] > last_ref
                else: ok = c[i] > e9[i] and c[i - 1] <= e9[i - 1]
                if ok: pend = ("rebuy", 1.0); n_re += 1
    if cur is not None:
        cur["proceeds"] += sh * c[-1]; cur.update(exit_i=n - 1, why="open"); trades.append(cur)
    T = pd.DataFrame(trades)
    if len(T):
        T["ret"] = T.proceeds / T.cost - 1; T["t"] = t
        T["entry_date"] = df.index[T.entry_i.values]; T["exit_date"] = df.index[T.exit_i.values]
        T["mae"] = T.low / T.ref - 1; T["peak_ret"] = T.peak / T.ref - 1
    return pd.Series(eq, index=df.index), st, T


tks = G["Chứng khoán"]
RULES = {
    "Gốc": {},
    "x2 bán hết": {"ext": 1.0},
    "SL18": {"sl_intra": .18},
    "SL18 + mua lại vượt giá mua cũ": {"sl_intra": .18, "reenter": "entry"},
    "SL18 + mua lại khi giá vượt EMA9": {"sl_intra": .18, "reenter": "e9"},
    "SL18 + x2": {"sl_intra": .18, "ext": 1.0},
    "SL18 + x2 + mua lại vượt giá mua cũ": {"sl_intra": .18, "ext": 1.0, "reenter": "entry"},
    "SL18 + x2 + mua lại khi giá vượt EMA9": {"sl_intra": .18, "ext": 1.0, "reenter": "e9"},
    "SL20 + x2 + mua lại vượt giá mua cũ": {"sl_intra": .20, "ext": 1.0, "reenter": "entry"},
    "SL22 + x2 + mua lại vượt giá mua cũ": {"sl_intra": .22, "ext": 1.0, "reenter": "entry"},
    "SL18 + x2 + mua lại (tối đa 1 lần)": {"sl_intra": .18, "ext": 1.0, "reenter": "entry", "max_reenter": 1},
}
res, store = [], {}
for name, R in RULES.items():
    V, T, E = portfolio(tks, R); store[name] = (V, T, E)
    s = summary(V, T)
    s["Số_lần_mua_lại"] = int((T.kind == "rebuy").sum()) if "kind" in T else 0
    res.append(dict(Cách=name, **s))
print("===== NGÀNH CHỨNG KHOÁN (20 mã), 1 tỷ, tiền nhàn rỗi 7%, 2017-11-06 .. 2026-11-02")
print(pd.DataFrame(res).set_index("Cách").drop(columns=["TB_thắng", "TB_thua"]).round(1).to_string())

print("\nGiá trị cuối năm (tỷ):")
keys = ["Gốc", "SL18", "SL18 + mua lại vượt giá mua cũ", "SL18 + x2", "SL18 + x2 + mua lại vượt giá mua cũ"]
print(pd.DataFrame({k: store[k][0].groupby(store[k][0].index.year).last() for k in keys}).round(2).to_string())

print("\nTừng mã (1 tỷ mỗi mã):")
per = pd.DataFrame({k: store[k][2].iloc[-1] for k in ["Gốc", "x2 bán hết", "SL18", "SL18 + mua lại vượt giá mua cũ", "SL18 + x2", "SL18 + x2 + mua lại vượt giá mua cũ"]})
per.columns = ["Gốc", "x2", "SL18", "SL18+mua lại", "SL18+x2", "SL18+x2+mua lại"]
print(per.sort_values("Gốc", ascending=False).round(2).to_string())

T = store["SL18 + x2 + mua lại vượt giá mua cũ"][1]
print("\nCác lần mua lại (SL18 + x2 + mua lại vượt giá mua cũ):")
for _, r in T[T.kind == "rebuy"].iterrows():
    print(f"  {r.t:4s} mua lại {r.entry_date.date()} @{r.ref:>8,.0f}  bán {r.exit_date.date()} ({r.why})  {r.ret*100:+7.1f}%")
for tk in ["AGR", "DSC", "TCI", "VND"]:
    print(f"\n{tk} — các lệnh (SL18 + x2 + mua lại):")
    for _, r in T[T.t == tk].iterrows():
        print(f"  {'mua lại' if r.kind=='rebuy' else 'mua   '} {r.entry_date.date()} @{r.ref:>8,.0f}  bán {r.exit_date.date()} ({r.why:8s})  {r.ret*100:+7.1f}%")
