from pathlib import Path as _P
_HERE = _P(__file__).resolve().parent
import sys as _s; _s.stdout.reconfigure(encoding="utf-8")
import sys
SP = str(_HERE)
exec(open(SP + "/ck_sl_ext.py", encoding="utf-8").read().split("RULES = {")[0])
tks = G["Chứng khoán"]; rows = []
for lv in [.15, .18, .20, .22, .25, .30]:
    for ext in [None, 1.0]:
        R = {"sl_intra": lv}; 
        if ext: R["ext"] = ext
        V, T, _ = portfolio(tks, R); s = summary(V, T)
        rows.append(dict(Cắt_lỗ_trong_tuần=f"-{lv:.0%}", x2_WMA45="bán hết" if ext else "không", **{k: s[k] for k in ["Cuối_tỷ", "CAGR", "MDD", "CAGR_17_22", "CAGR_23_26", "Win", "Lỗ_tệ_nhất", "Lỗ_quá_20", "Lãi_x2"]}))
print(pd.DataFrame(rows).round(1).to_string(index=False))
