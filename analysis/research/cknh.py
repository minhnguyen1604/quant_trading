from pathlib import Path as _P
_HERE = _P(__file__).resolve().parent
import sys as _s; _s.stdout.reconfigure(encoding="utf-8")
import sys; sys.path.insert(0, str(_HERE.parent))
import numpy as np, pandas as pd, common as cm
data = cm.load(); G = cm.groups(data)
CAP = 1e9; P0 = pd.Timestamp(cm.PORT_START)
pd.set_option("display.width", 250)

def money(tks, rate, runner, **kw):
    wk = (1 + rate) ** (1 / 52); vals, bh, inv_d, trs = {}, {}, {}, []
    for t in tks:
        df = data[t]; tr, eq, st = runner(df, **kw); idx = df.index
        eq = pd.Series(np.asarray(eq, float), index=idx)
        inv = np.zeros(len(df), bool)
        for a, z, op in zip(tr.entry_i, tr.exit_i, tr.open): inv[a:(z + 1 if op else z)] = True
        g = (eq / eq.shift(1)).fillna(1.0).values; g = np.where(inv, g, g * wk); g[np.arange(len(df)) <= st] = wk
        vals[t] = pd.Series(g, index=idx)[idx > P0]
        b = df["Close"] / df["Close"].shift(1); b[np.arange(len(df)) <= st] = wk; bh[t] = b[idx > P0]
        inv_d[t] = pd.Series(inv, index=idx)[idx > P0]
        if len(tr): trs.append(tr.assign(ticker=t, entry_date=idx[tr.entry_i.values], exit_date=idx[tr.exit_i.values]))
    V = pd.DataFrame(vals).sort_index().fillna(wk).cumprod() * CAP / len(tks)
    Bh = pd.DataFrame(bh).sort_index().fillna(wk).cumprod() * CAP / len(tks)
    I = pd.DataFrame(inv_d).sort_index().fillna(False).astype(bool)
    return V, Bh, I, pd.concat(trs, ignore_index=True)

yrs = lambda v: (v.index[-1] - P0).days / 365.25
cagr = lambda v: ((v.iloc[-1] / CAP) ** (1 / yrs(v)) - 1) * 100
groups = {"Chứng khoán": G["Chứng khoán"], "Ngân hàng": G["Ngân hàng"], "CK + NH": G["Chứng khoán"] + G["Ngân hàng"]}
rules = {"Gốc": (cm.run, {}), "Trailing25": (cm.run_exit, {"rule": {"trail": .25}}),
         "SL20": (cm.run_exit, {"rule": {"sl": .20}}), "SL18 ATC": (cm.run_exit, {"rule": {"sl": .18, "exit_on_close": True}})}
print("A. TỔNG HỢP (1 tỷ/nhóm, kỳ", P0.date(), "..)")
rows = []
for gn, tks in groups.items():
    for rn, (fn, kw) in rules.items():
        for rate in [0, .05, .07]:
            V, Bh, I, T = money(tks, rate, fn, **kw); v, b = V.sum(1), Bh.sum(1)
            rows.append(dict(Nhóm=gn, Quy_tắc=rn, Lãi=f"{rate:.0%}", Cuối=v.iloc[-1]/1e9, CAGR=cagr(v), MDD=cm.mdd(np.r_[CAP, v.values])*100,
                             BH=b.iloc[-1]/1e9, BH_CAGR=cagr(b), BH_MDD=cm.mdd(np.r_[CAP, b.values])*100))
print(pd.DataFrame(rows).round(2).to_string(index=False))
print("năm:", round(yrs(v), 2), "cuối", v.index[-1].date())

for gn, tks in groups.items():
    V, Bh, I, T = money(tks, .07, cm.run); V0, _, _, _ = money(tks, 0, cm.run); v, b, v0 = V.sum(1), Bh.sum(1), V0.sum(1)
    C = T[~T.open]
    print("\n" + "=" * 20, gn, f"({len(tks)} mã)")
    w, l = C.ret[C.ret > 0], C.ret[C.ret <= 0]
    print(f"Lệnh đóng {len(C)}, mở {T.open.sum()} | win {(C.ret>0).mean()*100:.1f}% | TB {C.ret.mean()*100:.1f}% TV {C.ret.median()*100:.1f}% | TB thắng {w.mean()*100:.1f}% TB thua {l.mean()*100:.1f}% R:R {w.mean()/-l.mean():.2f} PF {w.sum()/-l.sum():.2f}")
    print(f"Lỗ >20%: {(C.ret<-.2).mean()*100:.1f}% | lãi >50%: {(C.ret>.5).mean()*100:.1f}% | lãi >100%: {(C.ret>1).mean()*100:.1f}% | giữ TV {C.bars.median():.0f} tuần (thắng {C.bars[C.ret>0].median():.0f}, thua {C.bars[C.ret<=0].median():.0f})")
    cash = 1 - (V * I).sum(1) / V.sum(1)
    Y = pd.DataFrame({"CL+7%": v.groupby(v.index.year).last()/1e9, "CL 0%": v0.groupby(v0.index.year).last()/1e9, "B&H": b.groupby(b.index.year).last()/1e9,
                      "Tiền mặt%": cash.groupby(cash.index.year).mean()*100})
    yr = v.groupby(v.index.year).last(); yb = b.groupby(b.index.year).last()
    Y["CL năm%"] = (yr / yr.shift(1).fillna(CAP) - 1) * 100; Y["B&H năm%"] = (yb / yb.shift(1).fillna(CAP) - 1) * 100
    print(Y.round(2).to_string())
    E = pd.DataFrame({"CL+7%": V.iloc[-1] / (CAP/len(tks)), "B&H": Bh.iloc[-1] / (CAP/len(tks)),
                      "MDD CL": [cm.mdd(np.r_[1, V[t].values])*100 for t in V], "MDD B&H": [cm.mdd(np.r_[1, Bh[t].values])*100 for t in Bh],
                      "Lệnh": C.groupby("ticker").size().reindex(V.columns).fillna(0).astype(int),
                      "Win%": C.groupby("ticker").ret.apply(lambda x: (x>0).mean()*100).reindex(V.columns),
                      "Lệnh tốt nhất%": C.groupby("ticker").ret.max().reindex(V.columns)*100,
                      "Đang giữ": I.iloc[-1]}).sort_values("CL+7%", ascending=False)
    print(E.round(2).to_string())
    print("Top 10 lệnh:"); print(C.nlargest(10, "ret")[["ticker", "entry_date", "exit_date", "ret"]].assign(ret=lambda x: (x.ret*100).round(0)).to_string(index=False))
    print(f"Nếu bỏ 5 lệnh tốt nhất: TB/lệnh {C.ret.drop(C.ret.nlargest(5).index).mean()*100:.1f}%")
