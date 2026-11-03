"""Is the edge real? Random-entry Monte Carlo, parameter grid, MA types, costs, liquidity, market regime, sub-periods."""
import numpy as np
import pandas as pd
import common as cm

cm.report("02_robustness")
rng = np.random.default_rng(7)
data = cm.load()
vni_w = cm.vnindex_weekly(); vni_sma40 = vni_w.rolling(40).mean()
GRID_START = pd.Timestamp("2018-08-06")  # every slow length up to 80 weeks has warmed up

rows = []
for t, df in data.items():
    tr, _, st = cm.run(df)
    if not len(tr): continue
    val = (df["Close"] * df["Volume"]).rolling(20, min_periods=8).mean().shift(1).values  # prior 20w traded value
    idx = df.index
    rows.append(tr.assign(ticker=t, liq=val[tr.sig_i.values],
                          vni_up=[vni_w.get(idx[i], np.nan) > vni_sma40.get(idx[i], np.nan) for i in tr.sig_i]))
C = pd.concat(rows, ignore_index=True); C = C[~C.open].copy()


def summary(**kw):
    S, B, T = cm.sleeves(data, data, start=GRID_START, path_stats=False, **kw)
    r = T[~T.open].ret.values; w, l = r[r > 0], r[r <= 0]
    p = cm.perf(cm.port(S))
    beat = np.mean([S[c].dropna().iloc[-1] > B[c].dropna().iloc[-1] for c in S.columns if S[c].notna().any()]) * 100
    return dict(CAGR=p["CAGR"], Sharpe=p["Sharpe"], MDD=p["MDD"], Calmar=p["Calmar"], BH_CAGR=cm.perf(cm.port(B))["CAGR"],
                trades=len(r), win=(r > 0).mean() * 100, mean_tr=r.mean() * 100, PF=w.sum() / -l.sum(), beat_BH=beat)


print("=" * 100); print("D. TIMING vs RANDOM ENTRY (2,000 runs; same tickers, holding lengths and costs)")
print("   Trades are treated as independent here, so p-values are optimistic; compare with the month-cluster CI in 01_overview.")
arr = {t: (d["Open"].values, int(np.argmax(~np.isnan(cm.wma(d["Close"].values, 45))))) for t, d in data.items()}
act = dict(mean=C.ret.mean(), median=C.ret.median(), win=(C.ret > 0).mean(), logm=np.log1p(C.ret).mean())
tk, h = C.ticker.values, C.bars.values.astype(int)
sims = []
for _ in range(2000):
    rr = np.empty(len(C))
    for k in range(len(C)):
        o, st = arr[tk[k]]; e = rng.integers(st, max(st, len(o) - 1 - h[k]) + 1)
        rr[k] = o[e + h[k]] * (1 - cm.COMM) / (o[e] * (1 + cm.COMM)) - 1
    sims.append((rr.mean(), np.median(rr), (rr > 0).mean(), np.log1p(rr).mean()))
sims = np.array(sims)
for i, k in enumerate(["mean", "median", "win", "logm"]):
    s = sims[:, i]
    print(f"  {k:6s}: actual={act[k]*100:7.2f}  random={s.mean()*100:7.2f} [5%..95% {np.percentile(s,5)*100:.2f}..{np.percentile(s,95)*100:.2f}]  p={np.mean(s>=act[k]):.4f}")

print("=" * 100); print(f"E1. PARAMETER GRID (portfolio from {GRID_START.date()})")
G = pd.DataFrame([dict(fast=f, slow=s, **summary(fast=f, slow=s)) for f in [5, 7, 9, 11, 13, 15, 20] for s in [20, 30, 40, 45, 50, 60, 80] if f < s])
for m in ["Sharpe", "CAGR", "MDD", "mean_tr", "beat_BH"]:
    print(f"\n{m}:\n", G.pivot(index="fast", columns="slow", values=m).round(2).to_string())
g9 = G[(G.fast == 9) & (G.slow == 45)].iloc[0]
print(f"\nEMA9/WMA45 Sharpe rank {int((G.Sharpe > g9.Sharpe).sum()) + 1}/{len(G)}, grid median {G.Sharpe.median():.2f}")

print("\nE2. MA TYPES (9/45)")
V = [dict(variant=f"{fk.upper()}9/{sk.upper()}45", **summary(fk=fk, sk=sk)) for fk, sk in [("ema", "wma"), ("ema", "sma"), ("ema", "ema"), ("sma", "sma"), ("sma", "wma")]]
V.append(dict(variant="EMA9/WMA45 entry Fri close", **summary(entry_on_close=True)))
print(pd.DataFrame(V).round(2).to_string(index=False))

print("\nE3. COST PER SIDE")
print(pd.DataFrame([dict(cost=c * 100, **summary(comm=c)) for c in [0.0, 0.0015, 0.0025, 0.005, 0.01]])[["cost", "CAGR", "Sharpe", "MDD", "mean_tr", "PF"]].round(2).to_string(index=False))


def bucket_stats(x):
    return pd.Series(dict(n=len(x), win=(x > 0).mean() * 100, mean=x.mean() * 100, median=x.median() * 100, PF=x[x > 0].sum() / -x[x <= 0].sum()))


print("\nE4. LIQUIDITY AT ENTRY (avg weekly traded value, prior 20 weeks, bn VND)")
C["lb"] = pd.cut(C.liq / 1e9, [0, 5, 25, 100, 500, 1e9], labels=["<5", "5-25", "25-100", "100-500", ">500"])
print(C.groupby("lb", observed=True).ret.apply(bucket_stats).unstack().round(2).to_string())
for th in [25, 100]:
    a, b, _ = cm.cluster_ci(C[C.liq >= th * 1e9], rng)
    print(f"  liquidity >= {th}bn/week: mean {C[C.liq>=th*1e9].ret.mean()*100:.2f}%  CI95 {a:.2f}..{b:.2f}")
a, b, _ = cm.cluster_ci(C[C.entry_date.dt.year != 2020], rng)
print(f"  excluding 2020 entries: mean {C[C.entry_date.dt.year!=2020].ret.mean()*100:.2f}%  CI95 {a:.2f}..{b:.2f}")

print("\nE5. MARKET REGIME AT SIGNAL (VNINDEX vs 40-week SMA)")
print(C.groupby(C.vni_up.map({True: "above", False: "below"})).ret.apply(bucket_stats).unstack().round(2).to_string())

print("\nE6. SUB-PERIODS (portfolio, from 2017-11)")
S, B, _ = cm.sleeves(data, data, path_stats=False)
rs, rb = cm.port(S), cm.port(B)
rv = vni_w.reindex(rs.index.union([rs.index[0] - pd.Timedelta(days=7)])).ffill().pct_change().reindex(rs.index)
sub = []
for a, b in [("2017-11-01", "2020-12-31"), ("2021-01-01", "2023-12-31"), ("2024-01-01", "2026-12-31")]:
    m = (rs.index >= a) & (rs.index <= b)
    sub.append(dict(period=f"{a[:4]}-{b[:4]}", **{f"{k}_{nm}": v for nm, r in [("strat", rs[m]), ("bh", rb[m]), ("vni", rv[m])]
                                                  for k, v in cm.perf(r).items() if k in ("CAGR", "Sharpe", "MDD")}))
print(pd.DataFrame(sub).round(2).to_string(index=False))
