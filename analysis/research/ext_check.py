from pathlib import Path as _P
_HERE = _P(__file__).resolve().parent
import sys as _s; _s.stdout.reconfigure(encoding="utf-8")
import sys; sys.path.insert(0, str(_HERE))
import io, contextlib
src = open(sys.path[0] + "/peak_exit.py", encoding="utf-8").read().split("RULES = {")[0]
exec(src)
grp = {"CK+NH": G["Chứng khoán"] + G["Ngân hàng"], "CK": G["Chứng khoán"], "NH": G["Ngân hàng"], "5 ngành": G["5 ngành chu kỳ (gộp)"]}
print("Độ nhạy ngưỡng 'giá > WMA45 + X% → bán hết' (CAGR / MDD / 2017-22 / 2023-26)")
for X in [.6, .7, .8, .9, 1.0, 1.1, 1.2, 1.5]:
    print(f"X={X:.0%}: " + " | ".join(f"{g} {r['CAGR']:.1f}/{r['MDD']:.0f}/{r['CAGR_17_22']:.1f}/{r['CAGR_23_26']:.1f}" for g, r in ((g, evaluate(t, {'ext': X})) for g, t in grp.items())))
b = {g: evaluate(t, {}) for g, t in grp.items()}
print("Gốc: " + " | ".join(f"{g} {r['CAGR']:.1f}/{r['MDD']:.0f}/{r['CAGR_17_22']:.1f}/{r['CAGR_23_26']:.1f}" for g, r in b.items()))
# list trigger events for X=100% in CK+NH
print("\nCác lần kích hoạt 'giá > WMA45 +100%' (CK+NH):")
rows = []
for t in grp["CK+NH"]:
    p = prep(t); c, w = p["c"], p["w45"]; tr = BASE[t]
    for _, b_ in tr.iterrows():
        a, z = int(b_.entry_i), int(b_.exit_i)
        hit = [i for i in range(a, z) if c[i] >= w[i] * 2]
        if not hit: continue
        i = hit[0]; sell = p["o"][i + 1] if i + 1 < len(c) else c[i]
        pk = c[a:max(a + 1, z)].max(); pk_i = a + int(np.argmax(c[a:max(a + 1, z)]))
        exit_px = b_.exit_px if not b_.open else c[-1]
        rows.append(dict(Mã=t, Mua=p["idx"][a].date(), Bán_sớm=p["idx"][min(i + 1, len(c) - 1)].date(), Đỉnh=p["idx"][pk_i].date(),
                         Lãi_bán_sớm=(sell * (1 - COMM) / b_.entry_px - 1) * 100, Lãi_đỉnh=(pk / b_.entry_px - 1) * 100,
                         Lãi_gốc=b_.ret * 100, Bán_sớm_cách_đỉnh=(sell / pk - 1) * 100, Gốc_cách_đỉnh=(exit_px / pk - 1) * 100))
print(pd.DataFrame(rows).round(0).sort_values("Mua").to_string(index=False))
