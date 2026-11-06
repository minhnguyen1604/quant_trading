from pathlib import Path as _P
_HERE = _P(__file__).resolve().parent
import sys as _s; _s.stdout.reconfigure(encoding="utf-8")
import sys
SP = str(_HERE)
exec(open(SP + "/peak_exit.py", encoding="utf-8").read().split("RULES = {")[0])

TK = ["FPT", "VIC", "VHM"]
RULES = {"Gốc (cắt xuống)": {}, "Trailing 20%": {"trail": .20}, "Trailing 25%": {"trail": .25},
         "Giá>WMA45+100% → bán 1/2": {"ext": 1.0, "ext_frac": .5}, "Giá>WMA45+100% → bán hết": {"ext": 1.0},
         "Giá>WMA45+60% → bán 1/2": {"ext": .6, "ext_frac": .5}, "Lãi≥50% → trail 20%": {"trail": .2, "trail_after": .5},
         "Chandelier 4×ATR": {"chand": 4.0}, "RSI tuần≥80 → bán 1/2": {"rsi_hi": 80, "rsi_frac": .5}}
wk = 1.07 ** (1 / 52)
for t in TK:
    p = prep(t); st = p["st"]; idx = p["idx"]; c = p["c"]
    print(f"\n==================== {t}: dữ liệu {idx[0].date()} .. {idx[-1].date()}, giao dịch được từ {idx[st+1].date()}")
    b = pd.Series(c, index=idx) / pd.Series(c, index=idx).shift(1); b[np.arange(len(c)) <= st] = wk; b = b[idx > P0].cumprod()
    yrs = (b.index[-1] - P0).days / 365.25
    rows = []
    for name, R in RULES.items():
        eq, _ = sim(t, R, 0.07)
        g = (eq / eq.shift(1)).fillna(1.0).values; g[np.arange(len(g)) <= st] = wk
        v = pd.Series(g, index=idx)[idx > P0].cumprod()
        eq0, _ = sim(t, R, 0.0)
        rows.append(dict(Quy_tắc=name, Cuối_tỷ=v.iloc[-1], CAGR=(v.iloc[-1] ** (1 / yrs) - 1) * 100, MDD=cm.mdd(np.r_[1, v.values]) * 100,
                         Không_lãi_gửi=eq0.iloc[-1] / eq0.iloc[st] if False else None))
    rows.append(dict(Quy_tắc="Mua và giữ", Cuối_tỷ=b.iloc[-1], CAGR=(b.iloc[-1] ** (1 / yrs) - 1) * 100, MDD=cm.mdd(np.r_[1, b.values]) * 100))
    print(pd.DataFrame(rows).drop(columns="Không_lãi_gửi").set_index("Quy_tắc").round(2).to_string())
    tr = BASE[t]
    print("Lệnh theo cách gốc (giá điều chỉnh):")
    for _, r in tr.iterrows():
        a, z = int(r.entry_i), int(r.exit_i)
        seg = c[a:max(a + 1, z)]; pk_i = a + int(np.argmax(seg))
        ext = [i for i in range(a, z) if c[i] >= p["w45"][i] * 2]
        print(f"  mua {idx[a].date()} @{r.entry_px/(1+COMM):>9,.0f}  bán {idx[z].date()} @{(r.exit_px if not r.open else c[-1]):>9,.0f}  {r.ret*100:+7.1f}%  {z-a:3d} tuần"
              f"  đỉnh {r.peak_close*100:+6.1f}% ({idx[pk_i].date()})  sâu nhất {r.mae*100:+6.1f}%"
              f"{'  [>WMA45+100% lần đầu ' + str(idx[ext[0]].date()) + ']' if ext else ''}{'  (ĐANG GIỮ)' if r.open else ''}")
    dist = c / p["w45"] - 1
    print(f"  Khoảng cách lớn nhất giá/WMA45 từng đạt: {np.nanmax(dist)*100:.0f}% ({idx[int(np.nanargmax(dist))].date()})")
    yv = {}
    for name in ["Gốc (cắt xuống)", "Giá>WMA45+100% → bán 1/2"]:
        eq, _ = sim(t, RULES[name], 0.07); g = (eq / eq.shift(1)).fillna(1.0).values; g[np.arange(len(g)) <= st] = wk
        v = pd.Series(g, index=idx)[idx > P0].cumprod(); yv[name[:4]] = v.groupby(v.index.year).last()
    yv["B&H"] = b.groupby(b.index.year).last()
    print("  Giá trị cuối năm (tỷ): " + " | ".join(f"{y}: {r.iloc[0]:.2f}/{r.iloc[2]:.2f}" for y, r in pd.DataFrame(yv).iterrows()) + "   (gốc/B&H)")
