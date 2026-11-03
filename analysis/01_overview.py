"""Weekly EMA9/WMA45 on every HOSE stock: trade statistics, per-ticker vs buy & hold, portfolio vs VNINDEX."""
import numpy as np
import pandas as pd
import common as cm

cm.report("01_overview")
rng = np.random.default_rng(42)
data = cm.load()
vni_w = cm.vnindex_weekly()
vni_sma40 = vni_w.rolling(40).mean()

trades, sl_s, sl_b, inpos, rows = [], {}, {}, {}, []
for t, df in data.items():
    tr, eq, st = cm.run(df)
    if st >= len(df) - 1: continue
    idx, c = df.index, df["Close"].values
    e = eq.iloc[st:] / eq.iloc[st]; b = pd.Series(c[st:] / c[st], index=idx[st:])
    sl_s[t], sl_b[t] = e, b
    pos = np.zeros(len(df), bool)
    for a, z in zip(tr.entry_i, tr.exit_i): pos[a:z] = True
    inpos[t] = pd.Series(pos[st:], index=idx[st:])
    if len(tr):
        trades.append(tr.assign(ticker=t))
    rs_, rb_ = e.pct_change().dropna(), b.pct_change().dropna()
    rows.append(dict(ticker=t, n_tr=int((~tr.open).sum()) if len(tr) else 0, ret_s=(e.iloc[-1] - 1) * 100, ret_b=(b.iloc[-1] - 1) * 100,
                     mdd_s=cm.mdd(e) * 100, mdd_b=cm.mdd(b) * 100,
                     sh_s=rs_.mean() / rs_.std() * np.sqrt(52) if rs_.std() > 0 else np.nan,
                     sh_b=rb_.mean() / rb_.std() * np.sqrt(52) if rb_.std() > 0 else np.nan, expo=pos[st:].mean() * 100))
T = pd.concat(trades, ignore_index=True); K = pd.DataFrame(rows); C = T[~T.open].copy()

print("=" * 100); print("A. TRADE-LEVEL (closed trades, signal on Friday close, fill next Monday open)")
n = len(C); wins = (C.ret > 0).sum(); lo, hi = cm.wilson(wins, n)
w, l = C.ret[C.ret > 0], C.ret[C.ret <= 0]
print(f"tickers={len(K)}  closed trades={n}  open trades={T.open.sum()}  trades/ticker median={K.n_tr.median():.0f}")
print(f"Win rate = {wins/n*100:.1f}%  (95% CI {lo*100:.1f}-{hi*100:.1f}%)")
print(f"Mean trade = {C.ret.mean()*100:.2f}%  median = {C.ret.median()*100:.2f}%  std = {C.ret.std()*100:.1f}%  skew = {C.ret.skew():.2f}")
print(f"Avg win = {w.mean()*100:.1f}%  avg loss = {l.mean()*100:.1f}%  payoff = {w.mean()/-l.mean():.2f}  profit factor = {w.sum()/-l.sum():.2f}")
a, b_, boot = cm.cluster_ci(C, rng, 5000)
print(f"Expectancy 95% CI (month-cluster bootstrap) = {a:.2f}% .. {b_:.2f}%   P(mean<=0)={np.mean(boot<=0):.4f}")
print("Percentiles:", {f"p{int(k*100)}": round(v, 1) for k, v in (C.ret.quantile([.05, .1, .25, .5, .75, .9, .95]) * 100).items()})
lab = ["<-20%", "-20..-10", "-10..-5", "-5..0", "0..10", "10..25", "25..50", "50..100", ">100%"]
dist = pd.cut(C.ret, [-1, -.2, -.1, -.05, 0, .1, .25, .5, 1, 100], labels=lab).value_counts(normalize=True).reindex(lab) * 100
print("Outcome distribution (% of trades):", dist.round(1).to_dict())
print(f"Holding (weeks): median={C.bars.median():.0f} | winners {C.bars[C.ret>0].median():.0f}  losers {C.bars[C.ret<=0].median():.0f}")
print(f"MAE: median={C.mae.median()*100:.1f}%  P(<-10%)={(C.mae<-.1).mean()*100:.1f}%  P(<-20%)={(C.mae<-.2).mean()*100:.1f}% | winners P(MAE<-15%)={(C.mae[C.ret>0]<-.15).mean()*100:.1f}%")
srt = np.sort(C.ret.values)[::-1]; tot = srt.sum()
print(f"Concentration: top 5% trades = {srt[:int(.05*n)].sum()/tot*100:.0f}% of summed return; mean without top 10% = {srt[int(.1*n):].mean()*100:.2f}%")
print("\nBy entry year:\n", C.groupby(C.entry_date.dt.year).ret.agg(n="size", win=lambda x: (x > 0).mean() * 100,
      mean=lambda x: x.mean() * 100, median=lambda x: x.median() * 100).round(1).to_string())

print("\nPeak weekly close reached while holding -> final outcome")
for x in [0, .05, .10, .15, .20, .30, .50, 1.0]:
    m = C.peak_close > x
    print(f"  > +{x*100:>3.0f}%: {m.mean()*100:5.1f}% of trades | of those: won {(C.ret[m]>0).mean()*100:5.1f}%, ended < -5%: {(C.ret[m]<-.05).mean()*100:5.1f}%")
wn = C[C.ret > 0]
print(f"Winners: median peak {wn.peak_close.median()*100:.1f}% -> exit {wn.ret.median()*100:.1f}% (keep {(np.log1p(wn.ret)/np.log1p(wn.peak_close)).median()*100:.0f}% of peak); give-back median {((C.peak_close-C.ret)*100).median():.1f}pp, mean {((C.peak_close-C.ret)*100).mean():.1f}pp")

print("=" * 100); print("B. PER TICKER vs buy & hold over the same window")
def pci(mask):
    mask = mask.dropna(); k, nn = int(mask.sum()), len(mask); a_, b2 = cm.wilson(k, nn); return f"{k/nn*100:.1f}% (CI {a_*100:.1f}-{b2*100:.1f}%)"
print("P(strategy > 0)       =", pci(K.ret_s > 0))
print("P(strategy > B&H)     =", pci(K.ret_s > K.ret_b))
print("P(MDD shallower)      =", pci(K.mdd_s > K.mdd_b))
print("P(Sharpe > B&H)       =", pci((K.sh_s > K.sh_b)[K.sh_s.notna() & K.sh_b.notna()]))
print(f"Median: ret {K.ret_s.median():.1f}% vs {K.ret_b.median():.1f}% | MDD {K.mdd_s.median():.1f}% vs {K.mdd_b.median():.1f}% | exposure {K.expo.median():.0f}%")

print("=" * 100); print("C. PORTFOLIO (equal starting capital per ticker)")
S = pd.DataFrame(sl_s).sort_index().ffill(); B = pd.DataFrame(sl_b).sort_index().ffill(); P = pd.DataFrame(inpos).astype(float).sort_index().ffill()
S, B, P = S[S.index >= cm.PORT_START], B[B.index >= cm.PORT_START], P[P.index >= cm.PORT_START]
rs, rb = cm.port(S), cm.port(B)
expo = ((S * P).sum(axis=1) / S.sum(axis=1)).reindex(rs.index)
rv = vni_w.reindex(rs.index.union([rs.index[0] - pd.Timedelta(days=7)])).ffill().pct_change().reindex(rs.index)
tab = pd.DataFrame({"Strategy": cm.perf(rs), "Buy&Hold": cm.perf(rb), f"{expo.mean():.0%} B&H + cash": cm.perf(expo.mean() * rb), "VNINDEX": cm.perf(rv)}).T
print(f"{rs.index[0].date()} .. {rs.index[-1].date()} ({len(rs)} weeks), average invested {expo.mean()*100:.0f}%")
print(tab.round(2).to_string())
beta = np.cov(rs, rv)[0, 1] / rv.var()
print(f"beta vs VNINDEX {beta:.2f}, alpha {(rs.mean()-beta*rv.mean())*5200:.1f}%/yr, corr {np.corrcoef(rs, rv)[0,1]:.2f}")
yr = pd.DataFrame({"Strategy": rs, "B&H": rb, "VNINDEX": rv}).groupby(rs.index.year).apply(lambda x: (1 + x).prod() - 1) * 100
yr["expo%"] = expo.groupby(expo.index.year).mean() * 100
print("\nCalendar years (%):\n", yr.round(1).to_string())
roll = pd.DataFrame({"s": rs, "b": rb, "v": rv}).rolling(52).apply(lambda x: (1 + x).prod() - 1).dropna()
print(f"Rolling 52w: P(>0)={(roll.s>0).mean()*100:.0f}%  P(>VNINDEX)={(roll.s>roll.v).mean()*100:.0f}%  P(>B&H)={(roll.s>roll.b).mean()*100:.0f}%")
