"""Trade-by-trade ledger for: securities + private banks (no VCB/BID/CTG), shared 1 tỷ, max 12 positions (1/12 each),
leader-only entries (VNINDEX weekly EMA9 < WMA45 at the signal week), exit on EMA9 crossing below WMA45 (next Monday open)
or an intraweek stop 25% below the buy price; idle cash in a 4%/yr money-market fund."""
from pathlib import Path as _P
_HERE = _P(__file__).resolve().parent
import sys as _s; _s.stdout.reconfigure(encoding="utf-8")
import sys, pickle
SP = str(_HERE)
sys.path.insert(0, SP)
import numpy as np, pandas as pd, pool
cm = pool.cm; M = pool.M; IDX = pool.IDX; TK = pool.TK; CLF = pool.CLF; VUP = pool.VUP; COMM = pool.COMM; P0 = pool.P0
G = cm.groups(pool.data); U = set(G["Chứng khoán"] + [t for t in G["Ngân hàng"] if t not in {"VCB", "BID", "CTG"}])
UP = M["up"] & np.array([t in U for t in TK])[None, :]
N, SL, R_LIQ, CAP = 12, 0.25, 0.04, 1_000_000_000

n, m = len(IDX), len(TK)
L = float(CAP); wl = (1 + R_LIQ) ** (1 / 52)
sh = np.zeros(m); ref = np.zeros(m); cur = [None] * m
pend_buy, pend_sell = [], {}
eq = np.zeros(n); stockv = np.zeros(n); npos = np.zeros(n, int); trades = []; interest = 0.0
for i in range(n):
    for j in list(pend_sell):
        if sh[j] > 0 and not np.isnan(M["o"][i, j]):
            px = M["o"][i, j]; p = sh[j] * px * (1 - COMM); L += p
            cur[j].update(exit_date=IDX[i], exit_px=px, reason=pend_sell[j], proceeds=p); trades.append(cur[j]); cur[j] = None; sh[j] = 0
            del pend_sell[j]
    for j, target in pend_buy:
        if sh[j] == 0 and not np.isnan(M["o"][i, j]) and L > 0.2 * target:
            amt = min(target, L); px = M["o"][i, j]
            sh[j] = amt / (px * (1 + COMM)); L -= amt; ref[j] = px
            cur[j] = dict(t=TK[j], sig_date=IDX[i - 1], entry_date=IDX[i], entry_px=px, amount=amt, shares=sh[j])
    pend_buy = []
    for j in np.where(sh > 0)[0]:
        lo = M["l"][i, j]; stop = ref[j] * (1 - SL)
        if not np.isnan(lo) and lo <= stop:
            fill = min(M["o"][i, j], stop) if cur[j]["entry_date"] != IDX[i] else stop
            p = sh[j] * fill * (1 - COMM); L += p
            cur[j].update(exit_date=IDX[i], exit_px=fill, reason="Cắt lỗ -25% (trong tuần)" + (" - mở cửa gap dưới mức cắt" if fill < stop - 1e-9 else ""), proceeds=p)
            trades.append(cur[j]); cur[j] = None; sh[j] = 0; pend_sell.pop(j, None)
    held = np.where(sh > 0)[0]
    stockv[i] = np.nansum(sh[held] * CLF[i, held]); eq[i] = L + stockv[i]; npos[i] = len(held)
    if i == n - 1: break
    interest += L * (wl - 1); L *= wl
    for j in held:
        if M["dn"][i, j]: pend_sell[j] = "EMA9 cắt xuống WMA45"
    free = N - (len(held) - len(pend_sell))
    if free > 0 and VUP[i] == 0:
        cand = [j for j in np.where(UP[i] & (sh == 0))[0] if M["liq"][i, j] >= 1.0]
        cand.sort(key=lambda j: M["dist"][i, j])
        pend_buy = [(j, eq[i] / N) for j in cand[:free]]
for j in np.where(sh > 0)[0]:
    cur[j].update(exit_date=None, exit_px=CLF[-1, j], reason="Đang giữ (định giá theo giá đóng cửa tuần cuối)", proceeds=sh[j] * CLF[-1, j], open=True)
    trades.append(cur[j])
T = pd.DataFrame(trades).sort_values(["entry_date", "t"]).reset_index(drop=True)
T["open"] = T.get("open", False).fillna(False).astype(bool) if "open" in T else False
W = pd.DataFrame(dict(date=IDX, stock=stockv, total=eq, npos=npos))
W = W[W.date >= P0 - pd.Timedelta(days=7)].reset_index(drop=True)
print("Cuối kỳ:", eq[-1] / 1e9, "tỷ; lãi quỹ:", interest / 1e9, "; tổng lãi/lỗ lệnh:", (T.proceeds - T.amount).sum() / 1e9)
print("Kiểm tra:", (CAP + (T.proceeds - T.amount).sum() + interest) / 1e9)
print(T[["t", "entry_date", "exit_date", "reason"]].tail(5).to_string())
pickle.dump(dict(T=T, W=W, interest=interest, final=eq[-1], first_week=IDX[IDX >= P0 - pd.Timedelta(days=7)][0]), open(SP + "/ledger.pkl", "wb"))
