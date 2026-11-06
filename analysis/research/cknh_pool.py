"""Universe: securities + commercial banks excluding the state-owned big banks (VCB, BID, CTG; Agribank is unlisted).
Equal sleeves vs shared pool; all signals vs leader-only; base exit vs stop 18% + 2x WMA45 (+ re-entry for sleeves)."""
from pathlib import Path as _P
_HERE = _P(__file__).resolve().parent
import sys as _s; _s.stdout.reconfigure(encoding="utf-8")
import sys
SP = str(_HERE)
sys.path.insert(0, SP)
import numpy as np, pandas as pd
import pool  # shared-pool engine (loads data)
cm = pool.cm; data = pool.data; P0 = pool.P0
pd.set_option("display.width", 250)
G = cm.groups(data)
BIG = {"VCB", "BID", "CTG"}
CK = G["Chứng khoán"]; NH = [t for t in G["Ngân hàng"] if t not in BIG]
U = CK + NH
print(f"Chứng khoán ({len(CK)}): {', '.join(CK)}")
print(f"Ngân hàng TM bỏ Big4 ({len(NH)}): {', '.join(NH)}\n")

# ---- equal sleeves with the ck_reentry engine, plus an entry filter (leader-only)
src = open(SP + "/ck_reentry.py", encoding="utf-8").read().split("tks = G[")[0]
src = src.replace("            if up[i]:\n                pend = (\"buy\", 1.0)", "            if up[i] and OK(t, i, R):\n                pend = (\"buy\", 1.0)")
ns = {"__file__": __file__}
exec(src, ns)
vni = cm.vnindex_weekly(); vup = pd.Series(cm.ema(vni.values, 9) > cm.wma(vni.values, 45), index=vni.index).astype(float)
LEAD = {t: (vup.reindex(d.index, method="ffill").values == 0) for t, d in data.items()}
ns["OK"] = lambda t, i, R: (not R.get("leader")) or bool(LEAD[t][i])


def sleeves(tks, R):
    V, T, E = ns["portfolio"](tks, R); s = ns["summary"](V, T); return V, s


SR = {
    "Chia đều, gốc": {},
    "Chia đều, cắt lỗ 18% + x2 + mua lại": {"sl_intra": .18, "ext": 1.0, "reenter": "entry"},
    "Chia đều, chỉ dẫn dắt, gốc": {"leader": True},
    "Chia đều, chỉ dẫn dắt, cắt lỗ 18% + x2 + mua lại": {"leader": True, "sl_intra": .18, "ext": 1.0, "reenter": "entry"},
}
rows, curves = [], {}
for gname, tks in [("CK + NH (bỏ Big4)", U), ("Chỉ CK", CK), ("Chỉ NH (bỏ Big4)", NH)]:
    for name, R in SR.items():
        V, s = sleeves(tks, R); curves[(gname, name)] = V
        rows.append(dict(Nhóm=gname, Cách=name, **{k: s[k] for k in ["Cuối_tỷ", "CAGR", "MDD", "CAGR_17_22", "CAGR_23_26", "Lệnh", "Win", "TB_lệnh", "Lỗ_tệ_nhất"]}))
print("===== CHIA ĐỀU 1 TỶ CHO MỌI MÃ TRONG NHÓM (mỗi mã một phần cố định), tiền nhàn rỗi 7%")
print(pd.DataFrame(rows).set_index(["Nhóm", "Cách"]).round(1).to_string())

# ---- shared pool restricted to the universe (no liquidity/amplitude filter beyond 1 tỷ/tuần)
uni = set(U)
orig_up = pool.M["up"].copy()
mask = np.array([t in uni for t in pool.TK])
pool.M["up"] = orig_up & mask[None, :]
rows = []
for name, kw in [("Vốn chung 10 mã, mọi tín hiệu", dict(N=10)), ("Vốn chung 10 mã, chỉ dẫn dắt", dict(N=10, only_leader=True)),
                 ("Vốn chung 15 mã, mọi tín hiệu", dict(N=15)), ("Vốn chung 15 mã, chỉ dẫn dắt", dict(N=15, only_leader=True)),
                 ("Vốn chung 20 mã, mọi tín hiệu", dict(N=20)), ("Vốn chung 20 mã, chỉ dẫn dắt", dict(N=20, only_leader=True)),
                 ("Vốn chung 15 mã, mọi tín hiệu + cắt lỗ 18% + x2", dict(N=15, sl=.18, ext=1.0)),
                 ("Vốn chung 15 mã, chỉ dẫn dắt + cắt lỗ 18% + x2", dict(N=15, only_leader=True, sl=.18, ext=1.0))]:
    E, T, s = pool.run(liq_min=1.0, amp_min=0, **kw); rows.append(dict(Cách=name, **s)); curves[("pool", name)] = E
print("\n===== VỐN CHUNG 1 TỶ, TỐI ĐA N MÃ (mỗi lệnh = 1/N giá trị danh mục), chỉ trong CK + NH bỏ Big4, thanh khoản ≥1 tỷ/tuần")
print(pd.DataFrame(rows).set_index("Cách").round(1).to_string())

print("\nGiá trị cuối năm (tỷ):")
pick = {"Chia đều gốc": curves[("CK + NH (bỏ Big4)", "Chia đều, gốc")],
        "Chia đều SL+x2+mua lại": curves[("CK + NH (bỏ Big4)", "Chia đều, cắt lỗ 18% + x2 + mua lại")],
        "Chia đều dẫn dắt SL+x2": curves[("CK + NH (bỏ Big4)", "Chia đều, chỉ dẫn dắt, cắt lỗ 18% + x2 + mua lại")],
        "Vốn chung 15 dẫn dắt": curves[("pool", "Vốn chung 15 mã, chỉ dẫn dắt")],
        "Vốn chung 15 dẫn dắt SL+x2": curves[("pool", "Vốn chung 15 mã, chỉ dẫn dắt + cắt lỗ 18% + x2")]}
Y = pd.DataFrame({k: v.groupby(v.index.year).last() for k, v in pick.items()})
print(Y.round(2).to_string())
