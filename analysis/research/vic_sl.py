from pathlib import Path as _P
_HERE = _P(__file__).resolve().parent
import sys as _s; _s.stdout.reconfigure(encoding="utf-8")
import sys; sys.path.insert(0, str(_HERE.parent))
import numpy as np, pandas as pd, common as cm
data = cm.load(); df = data["VIC"]; idx = df.index
print("Đường giá tuần lệnh VIC 8/2023 (giá điều chỉnh):")
s = df.loc["2023-08-07":"2023-10-16"]
e9 = pd.Series(cm.ema(df.Close.values, 9), index=idx); w45 = pd.Series(cm.wma(df.Close.values, 45), index=idx)
ent = 37450
for d, r in s.iterrows():
    print(f"  tuần {d.date()}: O {r.Open:>7,.0f} H {r.High:>7,.0f} L {r.Low:>7,.0f} C {r.Close:>7,.0f}  | so giá mua: đóng {(r.Close/ent-1)*100:+6.1f}% thấp nhất {(r.Low/ent-1)*100:+6.1f}% | EMA9 {e9[d]:,.0f} WMA45 {w45[d]:,.0f}")
d = pd.read_sql if False else None
import sqlite3
con = sqlite3.connect(cm.DB)
dd = pd.read_sql("select Date, Open, High, Low, Close from daily_prices where Ticker='VIC' and Date between '2023-08-14' and '2023-10-13' order by Date", con)
print("\nGiá ngày:")
for _, r in dd.iterrows():
    print(f"  {r.Date[:10]}  O {r.Open:>7,.0f} H {r.High:>7,.0f} L {r.Low:>7,.0f} C {r.Close:>7,.0f}  {(r.Close/ent-1)*100:+6.1f}%")
print()
for name, rule in {"Gốc": {}, "SL18 đóng cửa tuần, bán ATO thứ 2": {"sl": .18}, "SL18 đóng cửa tuần, bán ATC thứ 6": {"sl": .18, "exit_on_close": True},
                   "SL18 lệnh dừng trong tuần": {"sl_intra": .18}}.items():
    tr, eq, st = cm.run_exit(df, rule)
    t = tr[(tr.entry_date >= "2023-08-01") & (tr.entry_date <= "2023-08-31")]
    for _, r in t.iterrows():
        print(f"{name:38s}: mua {idx[r.entry_i].date()} bán {idx[r.exit_i].date()} lãi/lỗ {r.ret*100:+.1f}%")
    worst = tr[~tr.open].nsmallest(3, "ret")
    print(f"{'':38s}  3 lệnh tệ nhất cả kỳ: " + ", ".join(f"{idx[a].date()} {x*100:+.1f}%" for a, x in zip(worst.entry_i, worst.ret)) + f" | cuối kỳ x{eq.iloc[-1]/eq.iloc[st]:.2f}")
