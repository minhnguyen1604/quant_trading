from pathlib import Path as _P
_HERE = _P(__file__).resolve().parent
import sys as _s; _s.stdout.reconfigure(encoding="utf-8")
import sys, numpy as np, pandas as pd
sys.path.insert(0, str(_HERE.parent))
import common as cm
sys.stdout.reconfigure(encoding="utf-8"); pd.set_option("display.width",260); pd.set_option("display.max_rows",200)
SPLIT=pd.Timestamp("2023-01-01")
data=cm.load(); G=cm.groups(data); CYC=G["5 ngành chu kỳ (gộp)"]
base_T={t:cm.run_exit(data[t],{})[0] for t in CYC}
LEVELS=[.15,.16,.17,.18,.19,.20,.21,.22]
rules=[("Không cắt lỗ (gốc)",{})]+[(f"Đóng cửa tuần -{int(x*100)}%",{"sl":x}) for x in LEVELS]+[(f"Lệnh dừng -{int(x*100)}%",{"sl_intra":x}) for x in LEVELS]
rows=[]
for name,rule in rules:
    S,_,T=cm.sleeves(data,CYC,runner=cm.run_exit,rule=rule); rs=cm.port(S); C=T[~T.open]
    f,i,o=cm.perf(rs),cm.perf(rs[rs.index<SPLIT]),cm.perf(rs[rs.index>=SPLIT])
    w,l=C.ret[C.ret>0],C.ret[C.ret<=0]
    # entries are identical to the base run, so compare trade by trade
    B=pd.concat([base_T[t].assign(ticker=t) for t in CYC if len(base_T[t])]); B=B[~B.open]
    m=C.merge(B[["ticker","entry_i","ret","exit_i"]],on=["ticker","entry_i"],suffixes=("","_b"))
    cut=m[m.exit_i<m.exit_i_b]  # exited earlier than the crossover would have
    rows.append({"Quy tắc":name,"CAGR":f["CAGR"],"Sharpe":f["Sharpe"],"MDD":f["MDD"],"Calmar":f["Calmar"],
                 "CAGR 17-22":i["CAGR"],"CAGR 23-26":o["CAGR"],"Sharpe 17-22":i["Sharpe"],"Sharpe 23-26":o["Sharpe"],
                 "Win%":(C.ret>0).mean()*100,"Lỗ TB%":l.mean()*100,"Lỗ max%":C.ret.min()*100,"% lệnh lỗ>20%":(C.ret<-.2).mean()*100,
                 "R:R":w.mean()/-l.mean(),"Kỳ vọng R":C.ret.mean()/-l.mean(),"Lệnh x2":int((C.ret>=1).sum()),
                 "Bị cắt":len(cut),"Cắt nhầm (gốc lãi)":int((cut.ret_b>0).sum()),"Lãi bị mất (đ%)":cut.ret_b[cut.ret_b>0].sum()*100,
                 "Lỗ tiết kiệm (đ%)":(cut.ret-cut.ret_b)[cut.ret_b<=0].sum()*100})
R=pd.DataFrame(rows).set_index("Quy tắc")
print("== Danh mục 5 ngành"); print(R[["CAGR","Sharpe","MDD","Calmar","CAGR 17-22","CAGR 23-26","Sharpe 17-22","Sharpe 23-26"]].round(2).to_string())
print("\n== Theo lệnh"); print(R[["Win%","Lỗ TB%","Lỗ max%","% lệnh lỗ>20%","R:R","Kỳ vọng R","Lệnh x2","Bị cắt","Cắt nhầm (gốc lãi)","Lãi bị mất (đ%)","Lỗ tiết kiệm (đ%)"]].round(2).to_string())
print("\n== Theo ngành (Calmar | CAGR | MDD), đóng cửa tuần")
out=[]
for g in cm.SECTORS:
    r={"Ngành":g}
    for x in [None,.17,.18,.19,.20]:
        S,_,_=cm.sleeves(data,G[g],runner=cm.run_exit,rule={} if x is None else {"sl":x}); p=cm.perf(cm.port(S))
        r["gốc" if x is None else f"-{int(x*100)}%"]=f"{p['Calmar']:.2f} | {p['CAGR']:.1f} | {p['MDD']:.1f}"
    out.append(r)
print(pd.DataFrame(out).set_index("Ngành").to_string())
