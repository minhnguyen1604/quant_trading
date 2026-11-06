"""Ways to sell closer to the top: weekly EMA9/WMA45 entries, base crossover exit always on, plus an extra rule.
Within one base episode (EMA9 above WMA45) the extra rule may sell part/all early and optionally re-enter."""
from pathlib import Path as _P
_HERE = _P(__file__).resolve().parent
import sys as _s; _s.stdout.reconfigure(encoding="utf-8")
import sys; sys.path.insert(0, str(_HERE.parent))
import numpy as np, pandas as pd, common as cm
data = cm.load(); G = cm.groups(data); P0 = pd.Timestamp(cm.PORT_START); COMM = cm.COMM
pd.set_option("display.width", 260); pd.set_option("display.max_rows", 200)


def rsi(c, n=14):
    d = np.diff(c, prepend=c[0])
    up = pd.Series(np.maximum(d, 0)).ewm(alpha=1 / n, adjust=False).mean()
    dn = pd.Series(np.maximum(-d, 0)).ewm(alpha=1 / n, adjust=False).mean()
    return (100 - 100 / (1 + up / dn.replace(0, 1e-12))).values


def atr(h, l, c, n=14):
    pc = np.r_[c[0], c[:-1]]
    tr = np.maximum(h - l, np.maximum(abs(h - pc), abs(l - pc)))
    return pd.Series(tr).ewm(alpha=1 / n, adjust=False).mean().values


PRE = {}
def prep(t):
    if t in PRE: return PRE[t]
    df = data[t]; o, h, l, c = (df[k].values for k in ["Open", "High", "Low", "Close"])
    up, dn, st = cm._signals(c, 9, 45, "ema", "wma")
    PRE[t] = dict(o=o, h=h, l=l, c=c, up=up, dn=dn, st=st, w45=cm.wma(c, 45), e9=cm.ema(c, 9), e5=cm.ema(c, 5), s10=cm.sma(c, 10),
                  rsi=rsi(c), atr=atr(h, l, c), idx=df.index)
    return PRE[t]


def sim(t, R, rate=0.0):
    """R keys (all optional):
       trail, trail_after : full exit when close <= peak*(1-trail), armed once peak >= entry*(1+trail_after)
       ma, ma_after       : full exit on a close below that MA ('e5','e9','s10'), armed once peak gain >= ma_after
       chand, chand_after : full exit when close <= peak - chand*ATR14
       ext, ext_frac      : sell ext_frac once when close >= WMA45*(1+ext)
       rsi_hi, rsi_frac   : sell rsi_frac once when weekly RSI >= rsi_hi
       rsi_fall           : (hi, lo) sell all once RSI has been >= hi and then closes < lo
       tp, tp_frac        : sell tp_frac at +tp (limit order, intraweek)
       reenter            : None | 'e9' (close crosses back above EMA9) | 'high' (close above the peak before the early exit)
    Base crossover exit always applies. Returns (equity, episodes)."""
    p = prep(t); o, h, c, n = p["o"], p["h"], p["c"], len(p["c"]); wk = (1 + rate) ** (1 / 52)
    cash, sh, pend, epi, peak, base, done, out_peak, rsi_arm = 1.0, 0.0, None, False, 0.0, 0.0, set(), None, False
    eq = np.ones(n); episodes = []; ep = None
    for i in range(n):
        if pend is not None:
            kind, q = pend
            if kind == "buy" and cash > 0:
                px = o[i] * (1 + COMM); sh += cash / px; cash = 0.0; base = o[i]; peak = o[i]; done = set(); rsi_arm = False
            elif kind == "sell" and sh > 0:
                qq = sh * q; cash += qq * o[i] * (1 - COMM); sh -= qq
                if sh < 1e-12: sh = 0.0
            elif kind == "endep":
                if sh > 0: cash += sh * o[i] * (1 - COMM); sh = 0.0
                ep["eq_end"] = cash; episodes.append(ep); ep = None
            pend = None
        if sh > 0 and "tp" in R and "tp" not in done and h[i] >= base * (1 + R["tp"]):
            fill = max(base * (1 + R["tp"]), o[i]); qq = sh * R.get("tp_frac", 1.0)
            cash += qq * fill * (1 - COMM); sh -= qq; done.add("tp")
            if sh < 1e-12: sh = 0.0; out_peak = peak
        eq[i] = cash + sh * c[i]
        if i == n - 1: break
        cash *= wk
        if not epi:
            if p["up"][i]:
                epi = True; pend = ("buy", 1.0); ep = dict(t=t, eq_start=eq[i]); out_peak = None
            continue
        if p["dn"][i]:
            epi = False; pend = ("endep", 1.0); continue
        if sh > 0:
            peak = max(peak, c[i]); g = peak / base - 1; sell = 0.0
            if "trail" in R and g >= R.get("trail_after", 0) and c[i] <= peak * (1 - R["trail"]): sell = 1.0
            if "ma" in R and g >= R.get("ma_after", 0) and c[i] < p[R["ma"]][i]: sell = 1.0
            if "chand" in R and g >= R.get("chand_after", 0) and c[i] <= peak - R["chand"] * p["atr"][i]: sell = 1.0
            if "ext" in R and "ext" not in done and c[i] >= p["w45"][i] * (1 + R["ext"]):
                sell = max(sell, R.get("ext_frac", 1.0)); done.add("ext")
            if "rsi_hi" in R and "rsi" not in done and p["rsi"][i] >= R["rsi_hi"]:
                sell = max(sell, R.get("rsi_frac", 1.0)); done.add("rsi")
            if "rsi_fall" in R:
                if p["rsi"][i] >= R["rsi_fall"][0]: rsi_arm = True
                if rsi_arm and p["rsi"][i] < R["rsi_fall"][1]: sell = 1.0
            if sell > 0:
                pend = ("sell", sell)
                if sell >= 1.0: out_peak = peak
        elif R.get("reenter") and cash > 0:
            if R["reenter"] == "e9": ok = c[i] > p["e9"][i] and c[i - 1] <= p["e9"][i - 1]
            else: ok = out_peak is not None and c[i] > out_peak
            if ok: pend = ("buy", 1.0)
    if ep is not None: ep.update(eq_end=eq[-1], open=True); episodes.append(ep)
    return pd.Series(eq, index=p["idx"]), episodes


BASE = {t: cm.run(data[t])[0] for t in data}


def evaluate(tks, R):
    vals, caps = {}, []
    wk = 1.07 ** (1 / 52)
    for t in tks:
        p = prep(t); st = p["st"]
        eq, _ = sim(t, R, 0.07)
        g = (eq / eq.shift(1)).fillna(1.0).values; g[np.arange(len(g)) <= st] = wk
        vals[t] = pd.Series(g, index=p["idx"])[p["idx"] > P0]
        _, eps0 = sim(t, R, 0.0)
        tr = BASE[t]
        assert len(eps0) == len(tr), (t, len(eps0), len(tr))
        for e, (_, b) in zip(eps0, tr.iterrows()):
            if b.open: continue
            caps.append(dict(t=t, peak=b.peak_close, base=b.ret, got=e["eq_end"] / e["eq_start"] - 1))
    V = pd.DataFrame(vals).sort_index().fillna(wk).cumprod().sum(1) / len(tks)
    E = pd.DataFrame(caps)
    split = pd.Timestamp("2022-12-31")
    v_is = V[V.index <= split]; v_oos = V[V.index > split]
    cis = (v_is.iloc[-1] ** (365.25 / (v_is.index[-1] - P0).days) - 1) * 100
    coos = ((v_oos.iloc[-1] / v_is.iloc[-1]) ** (365.25 / (v_oos.index[-1] - v_is.index[-1]).days) - 1) * 100
    big = E[E.peak >= .3]
    return dict(Cuối_tỷ=V.iloc[-1], CAGR=(V.iloc[-1] ** (365.25 / (V.index[-1] - P0).days) - 1) * 100, MDD=cm.mdd(np.r_[1, V.values]) * 100,
                CAGR_17_22=cis, CAGR_23_26=coos,
                Giữ_đỉnh=(np.log1p(big.got) / np.log1p(big.peak)).median() * 100,
                Trả_lại_pp=((big.peak - big.got) * 100).median(),
                TB_sóng=E.got.mean() * 100, TV_sóng=E.got.median() * 100,
                x2=f"{int((E.got >= 1).sum())}/{int((E.peak >= 1).sum())}")


RULES = {
    "Gốc (cắt xuống)": {},
    "Trailing 15%": {"trail": .15}, "Trailing 20%": {"trail": .20}, "Trailing 25%": {"trail": .25}, "Trailing 30%": {"trail": .30},
    "Lãi≥50% → trail 15%": {"trail": .15, "trail_after": .5}, "Lãi≥50% → trail 20%": {"trail": .20, "trail_after": .5},
    "Lãi≥100% → trail 15%": {"trail": .15, "trail_after": 1.0}, "Lãi≥100% → trail 20%": {"trail": .20, "trail_after": 1.0},
    "Chandelier 3×ATR": {"chand": 3.0}, "Chandelier 4×ATR": {"chand": 4.0},
    "Lãi≥50% → đóng<EMA9": {"ma": "e9", "ma_after": .5}, "Lãi≥100% → đóng<EMA9": {"ma": "e9", "ma_after": 1.0},
    "Lãi≥50% → đóng<SMA10": {"ma": "s10", "ma_after": .5}, "Lãi≥100% → đóng<EMA5": {"ma": "e5", "ma_after": 1.0},
    "Giá>WMA45+60% → bán 1/2": {"ext": .6, "ext_frac": .5}, "Giá>WMA45+80% → bán 1/2": {"ext": .8, "ext_frac": .5},
    "Giá>WMA45+100% → bán 1/2": {"ext": 1.0, "ext_frac": .5}, "Giá>WMA45+100% → bán hết": {"ext": 1.0, "ext_frac": 1.0},
    "RSI tuần≥80 → bán 1/2": {"rsi_hi": 80, "rsi_frac": .5}, "RSI tuần≥85 → bán 1/2": {"rsi_hi": 85, "rsi_frac": .5},
    "RSI từng≥80 rồi<70 → bán hết": {"rsi_fall": (80, 70)},
    "Chốt 1/2 ở +100%": {"tp": 1.0, "tp_frac": .5},
    "Trail 15% + mua lại >EMA9": {"trail": .15, "reenter": "e9"}, "Trail 20% + mua lại >EMA9": {"trail": .20, "reenter": "e9"},
    "Trail 15% + mua lại vượt đỉnh": {"trail": .15, "reenter": "high"}, "Trail 20% + mua lại vượt đỉnh": {"trail": .20, "reenter": "high"},
    "Lãi≥50%→<EMA9, mua lại >EMA9": {"ma": "e9", "ma_after": .5, "reenter": "e9"},
    "Lãi≥50%→trail15, mua lại >EMA9": {"trail": .15, "trail_after": .5, "reenter": "e9"},
    "RSI≥80 rồi<70, mua lại >EMA9": {"rsi_fall": (80, 70), "reenter": "e9"},
}
grp = {"CK+NH": G["Chứng khoán"] + G["Ngân hàng"], "CK": G["Chứng khoán"], "NH": G["Ngân hàng"], "5 ngành": G["5 ngành chu kỳ (gộp)"]}
for gn, tks in grp.items():
    rows = [dict(Quy_tắc=name, **evaluate(tks, R)) for name, R in RULES.items()]
    print(f"\n===== {gn} ({len(tks)} mã) — 1 tỷ, tiền mặt 7%; Giữ_đỉnh/Trả_lại tính trên các sóng từng lãi ≥30%")
    print(pd.DataFrame(rows).set_index("Quy_tắc").round(1).to_string(), flush=True)
