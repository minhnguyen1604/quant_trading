"""Shared pool (CK + private banks, leader-only) with realistic cash management:
liquid cash earns r_liq; excess cash is swept into term deposits (term weeks, annual rate r_term, simple interest);
when a buy needs more than the liquid cash, the newest deposits are broken and earn only r_break for the time held."""
from pathlib import Path as _P
_HERE = _P(__file__).resolve().parent
import sys as _s; _s.stdout.reconfigure(encoding="utf-8")
import sys
SP = str(_HERE)
sys.path.insert(0, SP)
import numpy as np, pandas as pd, pool
cm = pool.cm; M = pool.M; IDX = pool.IDX; TK = pool.TK; CLF = pool.CLF; VUP = pool.VUP; COMM = pool.COMM; P0 = pool.P0
pd.set_option("display.width", 250)
G = cm.groups(pool.data); U = set(G["Chứng khoán"] + [t for t in G["Ngân hàng"] if t not in {"VCB", "BID", "CTG"}])
UP = M["up"] & np.array([t in U for t in TK])[None, :]


def run(N=12, sl=None, r_liq=0.005, r_term=None, term=26, r_break=0.005, buffer=0.0):
    n, m = len(IDX), len(TK)
    L = 1.0; deps = []  # [principal, start_i]
    sh = np.zeros(m); ref = np.zeros(m); cost = np.zeros(m); ent_d = [None] * m
    pend_buy, pend_sell = [], set(); eq = np.zeros(n); trades = []; broken = 0; lost = 0.0; earned = 0.0
    wl = (1 + r_liq) ** (1 / 52)

    def dep_value(d, i):
        return d[0] * (1 + r_term * (i - d[1]) / 52)

    def need(amount, i):
        nonlocal L, broken, lost
        while L < amount and deps:
            d = deps.pop()  # newest first: least accrued interest lost
            got = d[0] * (1 + r_break * (i - d[1]) / 52)
            lost += dep_value(d, i) - got; broken += 1; L += got
        return min(amount, L)

    for i in range(n):
        # maturities
        if r_term is not None:
            keep = []
            for d in deps:
                if i - d[1] >= term:
                    v = d[0] * (1 + r_term * term / 52); L += v
                else: keep.append(d)
            deps = keep
        for j in list(pend_sell):
            if sh[j] > 0 and not np.isnan(M["o"][i, j]):
                p = sh[j] * M["o"][i, j] * (1 - COMM); L += p
                trades.append((TK[j], ent_d[j], IDX[i], p / cost[j] - 1)); sh[j] = 0; pend_sell.discard(j)
        for j, target in pend_buy:
            if sh[j] == 0 and not np.isnan(M["o"][i, j]):
                amt = need(target, i)
                if amt > 0.2 * target:
                    px = M["o"][i, j] * (1 + COMM); sh[j] = amt / px; L -= amt; ref[j] = M["o"][i, j]; cost[j] = amt; ent_d[j] = IDX[i]
        pend_buy = []
        if sl is not None:
            for j in np.where(sh > 0)[0]:
                lo = M["l"][i, j]
                if not np.isnan(lo) and lo <= ref[j] * (1 - sl):
                    fill = min(M["o"][i, j], ref[j] * (1 - sl)) if ent_d[j] != IDX[i] else ref[j] * (1 - sl)
                    p = sh[j] * fill * (1 - COMM); L += p; trades.append((TK[j], ent_d[j], IDX[i], p / cost[j] - 1)); sh[j] = 0
                    pend_sell.discard(j)
        held = np.where(sh > 0)[0]
        dv = sum(dep_value(d, i) for d in deps) if r_term is not None else 0.0
        eq[i] = L + dv + np.nansum(sh[held] * CLF[i, held])
        if i == n - 1: break
        L *= wl
        for j in held:
            if M["dn"][i, j] or False: pend_sell.add(j)
        free = N - (len(held) - len(pend_sell))
        if free > 0 and VUP[i] == 0:
            cand = [j for j in np.where(UP[i] & (sh == 0))[0] if M["liq"][i, j] >= 1.0]
            cand.sort(key=lambda j: M["dist"][i, j])
            pend_buy = [(j, eq[i] / N) for j in cand[:free]]
        # sweep excess liquid cash into a new term deposit (keep the buffer and the cash for known Monday buys)
        if r_term is not None:
            keep_liq = buffer * eq[i] + sum(t for _, t in pend_buy)
            ex = L - keep_liq
            if ex > 0.01 * eq[i]: deps.append([ex, i]); L -= ex
    E = pd.Series(eq, index=IDX); E = E[E.index >= P0] / E[E.index >= P0].iloc[0]
    yrs = (E.index[-1] - E.index[0]).days / 365.25
    s21 = E[E.index >= "2021-01-04"]; y21 = (s21.index[-1] - s21.index[0]).days / 365.25
    return dict(Cuối_tỷ=E.iloc[-1], CAGR=(E.iloc[-1] ** (1 / yrs) - 1) * 100, MDD=cm.mdd(E.values) * 100,
                CAGR_từ_2021=((s21.iloc[-1] / s21.iloc[0]) ** (1 / y21) - 1) * 100,
                Sổ_rút_trước_hạn=broken, Lãi_mất_do_rút_sớm_tr=lost * 1000)


SC = [
    ("Không kỳ hạn 0,5% (để nguyên tiền mặt)", dict(r_liq=.005)),
    ("Quỹ thị trường tiền tệ 4% (rút ngay được)", dict(r_liq=.04)),
    ("Sổ 6 tháng 5%/năm, rút sớm chỉ được 0,5%", dict(r_liq=.005, r_term=.05, term=26)),
    ("Sổ 6 tháng 5% + giữ 2 suất mua ở quỹ 4%", dict(r_liq=.04, r_term=.05, term=26, buffer=2 / 12)),
    ("Sổ 3 tháng 4,5%/năm, rút sớm 0,5%", dict(r_liq=.005, r_term=.045, term=13)),
    ("Sổ 12 tháng 6%/năm, rút sớm 0,5%", dict(r_liq=.005, r_term=.06, term=52)),
    ("Sổ 12 tháng 6% + giữ 2 suất ở quỹ 4%", dict(r_liq=.04, r_term=.06, term=52, buffer=2 / 12)),
    ("(Tham chiếu) 5% linh hoạt, lý tưởng", dict(r_liq=.05)),
]
for N, sl, lab in [(12, .22, "12 mã dẫn dắt + cắt lỗ 22%"), (15, None, "15 mã dẫn dắt")]:
    rows = [dict(Cách_gửi=k, **run(N=N, sl=sl, **kw)) for k, kw in SC]
    print(f"\n===== {lab} (CK + NH bỏ Big4), 1 tỷ, 11/2017 .. 11/2026")
    print(pd.DataFrame(rows).set_index("Cách_gửi").round(1).to_string())
