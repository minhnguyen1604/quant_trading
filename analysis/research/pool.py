"""Shared-capital portfolio: 1 tỷ, at most N positions, each sized equity/N at entry, idle cash earns 7%.
Signals: weekly EMA9 crosses above WMA45 (buy next Monday open) on stocks passing a universe filter at the signal week.
When more signals than free slots: priority (leader = VNINDEX still below its trend first, then deeper below the 52w high)."""
from pathlib import Path as _P
_HERE = _P(__file__).resolve().parent
import sys as _s; _s.stdout.reconfigure(encoding="utf-8")
import sys; sys.path.insert(0, str(_HERE.parent))
import numpy as np, pandas as pd, common as cm
pd.set_option("display.width", 250)
data = cm.load(); P0 = pd.Timestamp(cm.PORT_START); COMM = cm.COMM; WK = 1.07 ** (1 / 52)
vni = cm.vnindex_weekly(); vup_s = pd.Series(cm.ema(vni.values, 9) > cm.wma(vni.values, 45), index=vni.index).astype(float)
vup_s[vni.index[:44]] = np.nan
IDX = pd.DatetimeIndex(sorted(set().union(*[d.index for d in data.values()])))
IDX = IDX[IDX >= P0 - pd.Timedelta(days=7)]
TK = list(data)
A = {k: {} for k in ["o", "l", "c", "up", "dn", "w45", "liq", "amp", "dist"]}
for t, df in data.items():
    c = df["Close"].values; up, dn, st = cm._signals(c, 9, 45, "ema", "wma"); cs = df["Close"]; tv = cs * df["Volume"]
    fr = pd.DataFrame(dict(o=df["Open"], l=df["Low"], c=cs, up=up, dn=dn, w45=cm.wma(c, 45),
                           liq=tv.rolling(26, min_periods=8).median() / 1e9,
                           amp=cs.rolling(156, min_periods=100).max() / cs.rolling(156, min_periods=100).min(),
                           dist=cs / cs.rolling(52, min_periods=1).max()), index=df.index).reindex(IDX)
    for k in A: A[k][t] = fr[k].values
M = {k: pd.DataFrame(v, index=IDX).values for k, v in A.items()}
M["up"] = np.nan_to_num(M["up"].astype(float)).astype(bool); M["dn"] = np.nan_to_num(M["dn"].astype(float)).astype(bool)
CLF = pd.DataFrame(M["c"]).ffill().values  # last known close for marking
VUP = vup_s.reindex(IDX, method="ffill").values


def run(N=10, liq_min=5.0, amp_min=2.0, only_leader=False, prio="leader", sl=None, ext=None):
    n, m = len(IDX), len(TK)
    cash, sh = 1.0, np.zeros(m); ref = np.zeros(m); cost = np.zeros(m); ent_d = [None] * m
    pend_buy, pend_sell = [], set()
    eq = np.zeros(n); trades = []; npos = np.zeros(n)
    for i in range(n):
        # 1) executions at this week's open: sells first, then buys
        for j in list(pend_sell):
            if sh[j] > 0 and not np.isnan(M["o"][i, j]):
                p = sh[j] * M["o"][i, j] * (1 - COMM); cash += p
                trades.append((TK[j], ent_d[j], IDX[i], p / cost[j] - 1)); sh[j] = 0; pend_sell.discard(j)
        for j, target in pend_buy:
            if sh[j] == 0 and not np.isnan(M["o"][i, j]) and cash > 0.2 * target:
                amt = min(target, cash); px = M["o"][i, j] * (1 + COMM)
                sh[j] = amt / px; cash -= amt; ref[j] = M["o"][i, j]; cost[j] = amt; ent_d[j] = IDX[i]
        pend_buy = []
        # 2) intraweek stop
        if sl is not None:
            for j in np.where(sh > 0)[0]:
                lo = M["l"][i, j]
                if not np.isnan(lo) and lo <= ref[j] * (1 - sl):
                    fill = min(M["o"][i, j], ref[j] * (1 - sl)) if ent_d[j] != IDX[i] else ref[j] * (1 - sl)
                    p = sh[j] * fill * (1 - COMM); cash += p; trades.append((TK[j], ent_d[j], IDX[i], p / cost[j] - 1)); sh[j] = 0
                    pend_sell.discard(j)
        held = np.where(sh > 0)[0]
        eq[i] = cash + np.nansum(sh[held] * CLF[i, held]); npos[i] = len(held)
        if i == n - 1: break
        cash *= WK
        # 3) exit signals at close
        for j in held:
            if M["dn"][i, j] or (ext is not None and M["c"][i, j] >= M["w45"][i, j] * (1 + ext)):
                pend_sell.add(j)
        # 4) entry signals at close
        free = N - (len(held) - len(pend_sell))
        if free <= 0: continue
        cand = np.where(M["up"][i] & (sh == 0))[0]
        cand = [j for j in cand if (M["liq"][i, j] >= liq_min) and (amp_min <= 0 or M["amp"][i, j] >= amp_min)]
        if only_leader: cand = [j for j in cand if VUP[i] == 0]
        if not cand: continue
        if prio == "leader": cand.sort(key=lambda j: ((VUP[i] != 0), M["dist"][i, j]))
        elif prio == "liq": cand.sort(key=lambda j: -M["liq"][i, j])
        target = eq[i] / N
        pend_buy = [(j, target) for j in cand[:free]]
    E = pd.Series(eq, index=IDX); E = E[E.index >= P0] / E[E.index >= P0].iloc[0]
    T = pd.DataFrame(trades, columns=["t", "entry", "exit", "ret"])
    sp = pd.Timestamp("2022-12-31"); a = E[E.index <= sp]; b = E[E.index > sp]
    yrs = (E.index[-1] - E.index[0]).days / 365.25
    return E, T, dict(Cuối_tỷ=E.iloc[-1], CAGR=(E.iloc[-1] ** (1 / yrs) - 1) * 100, MDD=cm.mdd(E.values) * 100,
                      CAGR_17_22=(a.iloc[-1] ** (365.25 / (a.index[-1] - a.index[0]).days) - 1) * 100,
                      CAGR_23_26=((b.iloc[-1] / a.iloc[-1]) ** (365.25 / (b.index[-1] - a.index[-1]).days) - 1) * 100,
                      Lệnh=len(T), Win=(T.ret > 0).mean() * 100, TB_lệnh=T.ret.mean() * 100,
                      Số_mã_TB=pd.Series(npos, index=IDX)[IDX >= P0].mean())


if __name__ == "__main__":
    V = [
        ("A. 10 mã, mọi tín hiệu (ưu tiên mã dẫn dắt)", dict(N=10)),
        ("B. 10 mã, chỉ tín hiệu dẫn dắt (VNI còn yếu)", dict(N=10, only_leader=True)),
        ("C. 10 mã, mọi tín hiệu, ưu tiên thanh khoản", dict(N=10, prio="liq")),
        ("D. 5 mã, mọi tín hiệu (ưu tiên dẫn dắt)", dict(N=5)),
        ("E. 5 mã, chỉ tín hiệu dẫn dắt", dict(N=5, only_leader=True)),
        ("F. 20 mã, mọi tín hiệu (ưu tiên dẫn dắt)", dict(N=20)),
        ("G. 20 mã, chỉ tín hiệu dẫn dắt", dict(N=20, only_leader=True)),
        ("H. 10 mã, dẫn dắt + cắt lỗ 18% + x2", dict(N=10, only_leader=True, sl=.18, ext=1.0)),
        ("I. 10 mã, mọi tín hiệu + cắt lỗ 18% + x2", dict(N=10, sl=.18, ext=1.0)),
        ("J. 10 mã, không lọc biên độ, mọi tín hiệu", dict(N=10, amp_min=0)),
        ("K. 10 mã, không lọc biên độ, chỉ dẫn dắt", dict(N=10, amp_min=0, only_leader=True)),
        ("L. 10 mã, thanh khoản ≥20 tỷ/tuần, chỉ dẫn dắt", dict(N=10, liq_min=20, only_leader=True)),
    ]
    rows, curves = [], {}
    for name, kw in V:
        E, T, s = run(**kw); rows.append(dict(Cách=name, **s)); curves[name[:2]] = E
    v = vni[(vni.index >= P0)]; v = v / v.iloc[0]
    yrs = (v.index[-1] - v.index[0]).days / 365.25
    print("===== DANH MỤC CHUNG 1 TỶ (vũ trụ: thanh khoản ≥5 tỷ/tuần, biên độ 3 năm ≥2 lần; tiền mặt 7%; bán theo EMA9 cắt xuống WMA45 nếu không ghi khác)")
    print(pd.DataFrame(rows).set_index("Cách").round(1).to_string())
    print(f"VNINDEX (không cổ tức): x{v.iloc[-1]:.2f}, CAGR {(v.iloc[-1]**(1/yrs)-1)*100:.1f}%, MDD {cm.mdd(v.values)*100:.1f}%")
    print(f"Gửi tiết kiệm 7%: x{1.07**yrs:.2f}")
    print("\nGiá trị cuối năm (tỷ):")
    C = pd.DataFrame(curves); print(C.groupby(C.index.year).last().round(2).to_string())
    pd.to_pickle(curves, str(_HERE) + r"/pool_curves.pkl")
