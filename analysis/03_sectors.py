"""Weekly EMA9/WMA45 by sector group (securities, real estate, banks, steel, transport, VN30) vs the rest."""
import numpy as np
import pandas as pd
import common as cm

cm.report("03_sectors")
rng = np.random.default_rng(11)
data = cm.load()
G = cm.groups(data)
vni_w = cm.vnindex_weekly()
for k in cm.SECTORS + ["VN30 (hiện tại)"]:
    print(f"{k}: {','.join(G[k])}")


def mc_random(C, sims=1000):
    arr = {t: (data[t]["Open"].values, int(np.argmax(~np.isnan(cm.wma(data[t]["Close"].values, 45))))) for t in C.ticker.unique()}
    tk, h = C.ticker.values, C.bars.values.astype(int)
    out = []
    for _ in range(sims):
        rr = np.empty(len(C))
        for k in range(len(C)):
            o, st = arr[tk[k]]; e = rng.integers(st, max(st, len(o) - 1 - h[k]) + 1)
            rr[k] = o[e + h[k]] * (1 - cm.COMM) / (o[e] * (1 + cm.COMM)) - 1
        out.append(rr.mean())
    return np.array(out)


summary, yearly, boots, grid, giveback = [], {}, {}, {}, []
for name, tks in G.items():
    S, B, T = cm.sleeves(data, tks)
    rs, rb = cm.port(S), cm.port(B)
    pos = {}
    for t in S.columns:
        tr = T[T.ticker == t]; p = pd.Series(False, index=data[t].index)
        for a, z in zip(tr.entry_i, tr.exit_i): p.iloc[a:z] = True
        pos[t] = p
    P = pd.DataFrame(pos).astype(float).sort_index().ffill().reindex(S.index)
    expo = ((S * P).sum(axis=1) / S.sum(axis=1)).reindex(rs.index).mean()
    C = T[~T.open]
    lo, hi, b = cm.cluster_ci(C, rng); boots[name] = (C, b)
    lo20, hi20, _ = cm.cluster_ci(C[C.entry_date.dt.year != 2020], rng)
    w, l = C.ret[C.ret > 0], C.ret[C.ret <= 0]
    wl, wh = cm.wilson((C.ret > 0).sum(), len(C))
    end = {t: (S[t].dropna().iloc[-1], B[t].dropna().iloc[-1], cm.mdd(S[t].dropna()), cm.mdd(B[t].dropna())) for t in S.columns}
    E = pd.DataFrame(end, index=["s", "b", "ms", "mb"]).T
    ps, pb, pm = cm.perf(rs), cm.perf(rb), cm.perf(expo * rb)
    rv = vni_w.reindex(rs.index.union([rs.index[0] - pd.Timedelta(days=7)])).ffill().pct_change().reindex(rs.index)
    mc = mc_random(C) if name not in ("Toàn bộ HOSE", "Các ngành còn lại") else None
    summary.append({
        "Nhóm": name, "Số mã": S.shape[1], "Số lệnh": len(C), "Win%": (C.ret > 0).mean() * 100, "Win CI": f"{wl*100:.0f}-{wh*100:.0f}",
        "Lãi TB/lệnh%": C.ret.mean() * 100, "CI95 TB": f"{lo:.1f}..{hi:.1f}", "Trung vị%": C.ret.median() * 100,
        "TB thắng%": w.mean() * 100, "TB thua%": l.mean() * 100, "PF": w.sum() / -l.sum(),
        "TB bỏ 2020%": C.ret[C.entry_date.dt.year != 2020].mean() * 100, "CI bỏ 2020": f"{lo20:.1f}..{hi20:.1f}",
        "Ngẫu nhiên TB%": mc.mean() * 100 if mc is not None else np.nan, "p(>ngẫu nhiên)": np.mean(mc >= C.ret.mean()) if mc is not None else np.nan,
        "P(mã lãi)": (E.s > 1).mean() * 100, "P(mã>B&H)": (E.s > E.b).mean() * 100, "P(MDD tốt hơn)": (E.ms > E.mb).mean() * 100,
        "CAGR CL": ps["CAGR"], "CAGR B&H": pb["CAGR"], "Sharpe CL": ps["Sharpe"], "Sharpe B&H": pb["Sharpe"],
        "MDD CL": ps["MDD"], "MDD B&H": pb["MDD"], "Expo%": expo * 100, "CAGR B&H×expo": pm["CAGR"], "Beta VNI": np.cov(rs, rv)[0, 1] / rv.var(),
    })
    yearly[name] = pd.DataFrame({"s": rs, "b": rb}).groupby(rs.index.year).apply(lambda x: (1 + x).prod() - 1) * 100
    grid[name] = {(f, s): cm.perf(cm.port(cm.sleeves(data, tks, fast=f, slow=s, path_stats=False)[0]))["Sharpe"] for f in [5, 9, 13] for s in [30, 45, 60]}
    wn = C[C.ret > 0]; m10 = C.peak_close > .10
    giveback.append({"Nhóm": name, "Lệnh": len(C), "Thắng lúc thoát%": (C.ret > 0).mean() * 100,
                     **{f"Từng>+{int(x*100)}%": (C.peak_close > x).mean() * 100 for x in [0, .05, .10, .20, .50, 1.0]},
                     "Từng>+10%→thắng": (C.ret[m10] > 0).mean() * 100, "Từng>+10%→lỗ>5%": (C.ret[m10] < -.05).mean() * 100,
                     "Thắng: đỉnh TV%": wn.peak_close.median() * 100, "Thắng: thoát TV%": wn.ret.median() * 100,
                     "Giữ được % đỉnh": (np.log1p(wn.ret) / np.log1p(wn.peak_close)).median() * 100,
                     "Trả lại TB(pp)": ((C.peak_close - C.ret) * 100).mean()})
    print(f"done {name}", flush=True)

S_ = pd.DataFrame(summary).set_index("Nhóm")
for title, cols in {
    "TRADE-LEVEL": ["Số mã", "Số lệnh", "Win%", "Win CI", "Lãi TB/lệnh%", "CI95 TB", "Trung vị%", "TB thắng%", "TB thua%", "PF"],
    "EDGE ROBUSTNESS": ["Lãi TB/lệnh%", "TB bỏ 2020%", "CI bỏ 2020", "Ngẫu nhiên TB%", "p(>ngẫu nhiên)"],
    "PER TICKER (%)": ["P(mã lãi)", "P(mã>B&H)", "P(MDD tốt hơn)"],
    "PORTFOLIO 2017-11..": ["CAGR CL", "CAGR B&H", "Sharpe CL", "Sharpe B&H", "MDD CL", "MDD B&H", "Expo%", "CAGR B&H×expo", "Beta VNI"],
}.items():
    print("\n" + "=" * 30, title); print(S_[cols].round(2).to_string())

print("\n" + "=" * 30, "PEAK WEEKLY CLOSE WHILE HOLDING vs EXIT")
print(pd.DataFrame(giveback).set_index("Nhóm").round(1).to_string())

print("\n" + "=" * 30, "FULL YEARS 2018-2025 (strategy)")
v = vni_w.pct_change().groupby(vni_w.index.year).apply(lambda x: (1 + x).prod() - 1).loc[2018:2025] * 100
rows = []
for g, y in yearly.items():
    f = y.loc[2018:2025]
    rows.append({"Nhóm": g, "CAGR CL": ((1 + f.s / 100).prod() ** (1 / len(f)) - 1) * 100, "TB cộng CL": f.s.mean(),
                 "CAGR B&H": ((1 + f.b / 100).prod() ** (1 / len(f)) - 1) * 100, "Tổng CL": ((1 + f.s / 100).prod() - 1) * 100,
                 "Tổng B&H": ((1 + f.b / 100).prod() - 1) * 100, "Năm tốt nhất": f"{f.s.max():.0f}% ({f.s.idxmax()})",
                 "Năm tệ nhất": f"{f.s.min():.0f}% ({f.s.idxmin()})", "Số năm lỗ": int((f.s < 0).sum())})
print(pd.DataFrame(rows).set_index("Nhóm").round(1).to_string())
print(f"VNINDEX 2018-2025: CAGR {((1+v/100).prod()**(1/len(v))-1)*100:.2f}%, total {((1+v/100).prod()-1)*100:.1f}%")

print("\n" + "=" * 30, "CALENDAR YEARS: strategy / B&H (%)")
print(pd.concat({k: v.apply(lambda r: f"{r.s:6.1f}/{r.b:6.1f}", axis=1) for k, v in yearly.items()}, axis=1).to_string())

print("\n" + "=" * 30, "PARAMETER NEIGHBOURHOOD: portfolio Sharpe (fast 5/9/13 x slow 30/45/60)")
for k, g in grid.items():
    vals = np.array(list(g.values())); r9 = g[(9, 45)]
    print(f"{k:24s} 9/45={r9:.2f} min={vals.min():.2f} median={np.median(vals):.2f} max={vals.max():.2f} rank={int((vals>r9).sum())+1}/9  "
          + " ".join(f"{f}/{s}:{x:.2f}" for (f, s), x in g.items()))

print("\n" + "=" * 30, "HYPOTHESIS: cyclical sectors vs the rest (mean trade, month-cluster bootstrap)")
bo = boots["Các ngành còn lại"][1]
for k in cm.SECTORS + ["VN30 (hiện tại)", "5 ngành chu kỳ (gộp)"]:
    d = boots[k][1] - bo
    print(f"  {k:22s} diff CI95 {np.percentile(d,2.5)*100:6.2f}..{np.percentile(d,97.5)*100:6.2f}  P(diff<=0)={np.mean(d<=0):.3f}")
