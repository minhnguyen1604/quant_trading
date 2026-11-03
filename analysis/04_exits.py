"""Alternative exits for weekly EMA9/WMA45 on the five cyclical sectors.
Rules are compared in 2017-11..2022 (selection) and 2023..2026 (check), then per sector, then on the big winners."""
import numpy as np
import pandas as pd
import common as cm

cm.report("04_exits")
SPLIT = pd.Timestamp("2023-01-01")
data = cm.load()
G = cm.groups(data)
CYC = G["5 ngành chu kỳ (gộp)"]

RULES = {"Gốc (EMA9 cắt xuống WMA45)": {}}
for x in [.10, .15, .20, .25, .30]: RULES[f"Trailing {int(x*100)}% từ đỉnh"] = {"trail": x}
for y in [.10, .15, .20]: RULES[f"Hoà vốn sau +{int(y*100)}%"] = {"be_after": y}
RULES["Khoá +10% sau +20%"] = {"be_after": .20, "be_level": .10}
RULES["Khoá +15% sau +30%"] = {"be_after": .30, "be_level": .15}
for z in [.20, .30, .50, 1.0]: RULES[f"Chốt hết tại +{int(z*100)}%"] = {"tp": z}
for z in [.20, .30, .50, 1.0]: RULES[f"Chốt 50% tại +{int(z*100)}%"] = {"tp": z, "tp_frac": .5}
for s in [.10, .15, .20]: RULES[f"Cắt lỗ -{int(s*100)}%"] = {"sl": s}
for y in [.15, .20, .30]: RULES[f"Sau +{int(y*100)}%: đóng cửa < EMA9"] = {"fast_after": y}
RULES["Sau +20%: đóng cửa < WMA20"] = {"fast_after": .20, "fast_ma": ("wma", 20)}

rows = []
for name, rule in RULES.items():
    S, _, T = cm.sleeves(data, CYC, runner=cm.run_exit, rule=rule)
    rs = cm.port(S); C = T[~T.open]
    row = {"Quy tắc": name}
    for lab, mr, mt in [("IS", rs.index < SPLIT, C.entry_date < SPLIT), ("OOS", rs.index >= SPLIT, C.entry_date >= SPLIT), ("Full", rs.index >= rs.index[0], C.entry_date >= C.entry_date.min())]:
        p = cm.perf(rs[mr]); c = C[mt]; w, l = c.ret[c.ret > 0], c.ret[c.ret <= 0]
        row.update({f"{lab}_CAGR": p["CAGR"], f"{lab}_Sharpe": p["Sharpe"], f"{lab}_MDD": p["MDD"], f"{lab}_Calmar": p["Calmar"],
                    f"{lab}_n": len(c), f"{lab}_win": (c.ret > 0).mean() * 100, f"{lab}_mean": c.ret.mean() * 100,
                    f"{lab}_PF": w.sum() / -l.sum() if len(l) else np.nan, f"{lab}_x2": int((c.ret >= 1).sum())})
    rows.append(row)
R = pd.DataFrame(rows).set_index("Quy tắc")
for lab, title in [("IS", "2017-11..2022 (selection)"), ("OOS", "2023..2026-11 (check)"), ("Full", "whole period")]:
    print(f"\n===== {title}")
    print(R[[c for c in R.columns if c.startswith(lab + "_")]].rename(columns=lambda c: c.split("_", 1)[1]).round(2).to_string())
b = R.iloc[0]
D = pd.DataFrame({"dSharpe_IS": R.IS_Sharpe - b.IS_Sharpe, "dSharpe_OOS": R.OOS_Sharpe - b.OOS_Sharpe,
                  "dCAGR_IS": R.IS_CAGR - b.IS_CAGR, "dCAGR_OOS": R.OOS_CAGR - b.OOS_CAGR})
print("\n===== Change vs the original exit"); print(D.round(2).sort_values("dSharpe_IS", ascending=False).to_string())
print(f"Rank correlation of Sharpe change, selection vs check period: {D.dSharpe_IS.corr(D.dSharpe_OOS, method='spearman'):.2f}")

print("\n===== Trailing stop per sector (whole period / selection / check)")
rows = []
for g in cm.SECTORS + ["VN30 (hiện tại)", "Các ngành còn lại"]:
    for rn, r in {"Gốc": {}, "Trailing 20%": {"trail": .2}, "Trailing 25%": {"trail": .25}, "Trailing 30%": {"trail": .3}}.items():
        S, _, T = cm.sleeves(data, G[g], runner=cm.run_exit, rule=r); rs = cm.port(S)
        f, i, o = cm.perf(rs), cm.perf(rs[rs.index < SPLIT]), cm.perf(rs[rs.index >= SPLIT])
        rows.append(dict(Nhóm=g, Quy_tắc=rn, CAGR=f["CAGR"], Sharpe=f["Sharpe"], MDD=f["MDD"], Calmar=f["Calmar"],
                         Sharpe_IS=i["Sharpe"], Sharpe_OOS=o["Sharpe"], CAGR_IS=i["CAGR"], CAGR_OOS=o["CAGR"], lệnh_x2=int((T.ret >= 1).sum())))
print(pd.DataFrame(rows).round(2).to_string(index=False))

print("\n===== Big winners: original exit vs trailing 25% (same entries, five sectors)")
rows = []
sect_of = {t: s for s in cm.SECTORS for t in G[s]}
for t, s in sect_of.items():
    d = data[t]
    b_, _, _ = cm.run_exit(d, {}); r_, _, _ = cm.run_exit(d, {"trail": .25})
    if not len(b_): continue
    m = b_.merge(r_[["entry_i", "ret"]], on="entry_i", suffixes=("_b", "_t"))
    c = d["Close"].values
    m["peak"] = [c[a:max(a + 1, z)].max() / (p / (1 + cm.COMM)) for a, z, p in zip(m.entry_i, m.exit_i, m.entry_px)]
    rows.append(m.assign(ticker=t, sector=s, date=d.index[m.entry_i]))
M = pd.concat(rows, ignore_index=True)
for lab, mask in [("peak >= x2", M.peak >= 2), ("peak >= x3", M.peak >= 3)]:
    x = M[mask]
    print(f"{lab}: n={len(x)} | original mean {x.ret_b.mean()*100:.0f}% median {x.ret_b.median()*100:.0f}% | trailing25 mean {x.ret_t.mean()*100:.0f}% median {x.ret_t.median()*100:.0f}%"
          f" | trailing better {(x.ret_t > x.ret_b + 1e-9).sum()}, same {(abs(x.ret_t - x.ret_b) < 1e-9).sum()}, worse {(x.ret_t < x.ret_b - 1e-9).sum()}")
print(f"Realised >= x2 / >= x3: original {(M.ret_b>=1).sum()} / {(M.ret_b>=2).sum()}, trailing25 {(M.ret_t>=1).sum()} / {(M.ret_t>=2).sum()}")
big = M[M.peak >= 2]
print(big.groupby("sector").agg(n=("ret_b", "size"), original=("ret_b", lambda x: x.mean() * 100), trailing25=("ret_t", lambda x: x.mean() * 100)).round(0).to_string())
print(big.assign(peak=(big.peak - 1) * 100, original=big.ret_b * 100, trailing25=big.ret_t * 100)
      .sort_values("peak", ascending=False)[["ticker", "sector", "date", "peak", "original", "trailing25"]].head(25).round(0).to_string(index=False))
