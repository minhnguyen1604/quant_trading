from pathlib import Path as _P
_HERE = _P(__file__).resolve().parent
import sys as _s; _s.stdout.reconfigure(encoding="utf-8")
import pickle, sys
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.comments import Comment
from openpyxl.utils import get_column_letter

SP = str(_HERE)
OUT = sys.argv[1]
D = pickle.load(open(SP + "/ledger.pkl", "rb"))
T, W = D["T"], D["W"]

F = "Arial"
BLUE = Font(name=F, color="0000FF"); BLACK = Font(name=F); GREEN = Font(name=F, color="008000")
BOLD = Font(name=F, bold=True); HDR = Font(name=F, bold=True, color="FFFFFF"); TITLE = Font(name=F, bold=True, size=14)
HFILL = PatternFill("solid", fgColor="1F4E78"); KEY = PatternFill("solid", fgColor="FFFF00"); LIGHT = PatternFill("solid", fgColor="DDEBF7")
VND = '#,##0;(#,##0);"-"'; PCT = '0.0%;(0.0%);"-"'; DATE = "dd/mm/yyyy"; PX = '#,##0.0'
thin = Side(style="thin", color="BFBFBF")

wb = Workbook()
ws = wb.active; ws.title = "Tóm tắt"
wl = wb.create_sheet("Lệnh"); wc = wb.create_sheet("Dòng tiền"); wy = wb.create_sheet("Theo năm"); wr = wb.create_sheet("Quy tắc")
S = "'Tóm tắt'!"; LS = "'Lệnh'!"; CS = "'Dòng tiền'!"


def header(sheet, row, names, widths):
    for k, (name, w) in enumerate(zip(names, widths), 1):
        c = sheet.cell(row=row, column=k, value=name); c.font = HDR; c.fill = HFILL
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        sheet.column_dimensions[get_column_letter(k)].width = w
    sheet.row_dimensions[row].height = 45


# ---------------- Tóm tắt: inputs
ws["A1"] = "Sổ lệnh backtest: EMA9/WMA45 tuần, chứng khoán + ngân hàng TM (bỏ VCB, BID, CTG)"; ws["A1"].font = TITLE
ws["A2"] = "Ô chữ xanh dương là giả định đầu vào; ô chữ đen là công thức. Giá cổ phiếu là giá đã điều chỉnh cổ tức/chia tách (KBS/SSI)."
ws["A2"].font = Font(name=F, italic=True, color="595959")
inputs = [
    ("Vốn ban đầu (VND)", 1_000_000_000, VND, "Do anh chọn."),
    ("Số mã tối đa giữ cùng lúc", 12, "0", "Mỗi lệnh mua = 1/12 tổng tài sản tại tuần có tín hiệu."),
    ("Cắt lỗ trong tuần (dưới giá mua)", 0.25, PCT, "Lệnh dừng đặt sẵn; nếu mở cửa đã thấp hơn mức cắt thì khớp giá mở cửa."),
    ("Phí giao dịch mỗi chiều", 0.0015, '0.00%', "Giả định 0,15%/chiều; chưa gồm thuế bán 0,1%."),
    ("Lãi tiền nhàn rỗi (quỹ thị trường tiền tệ, %/năm)", 0.04, PCT, "Giả định 4%/năm, cộng dồn theo tuần, rút được ngay."),
    ("Ngày bắt đầu", T.entry_date.min().to_pydatetime().replace(day=6, month=11, year=2017), DATE, "Tuần đầu tiên của kỳ backtest."),
    ("Ngày định giá cuối", W.date.iloc[-1].to_pydatetime(), DATE, "Tuần cuối có dữ liệu (dữ liệu giá đến 03/11/2026)."),
]
ws["A4"] = "GIẢ ĐỊNH"; ws["A4"].font = BOLD
for k, (lab, val, fmt, note) in enumerate(inputs, 5):
    ws.cell(row=k, column=1, value=lab).font = BLACK
    c = ws.cell(row=k, column=2, value=val); c.font = BLUE; c.number_format = fmt; c.fill = KEY
    ws.cell(row=k, column=3, value=note).font = Font(name=F, italic=True, color="595959")
CAP, NMAX, SLC, FEE, RLIQ, START, END = (f"{S}$B${r}" for r in range(5, 12))
ws.column_dimensions["A"].width = 52; ws.column_dimensions["B"].width = 22; ws.column_dimensions["C"].width = 70

nT = len(T); r0, r1 = 2, 1 + nT  # Lệnh data rows
nW = len(W); c0, c1 = 2, 1 + nW  # Dòng tiền data rows
rng = lambda col: f"{LS}${col}${r0}:${col}${r1}"
crng = lambda col: f"{CS}${col}${c0}:${col}${c1}"

ws["A13"] = "ĐỐI CHIẾU: VỐN BAN ĐẦU → GIÁ TRỊ CUỐI KỲ"; ws["A13"].font = BOLD
recon = [
    ("Vốn ban đầu", f"={CAP}", VND),
    ("+ Lãi/lỗ các lệnh đã bán (sau phí)", f'=SUMIFS({rng("M")},{rng("K")},"Đã bán")', VND),
    ("+ Lãi/lỗ tạm tính các lệnh đang giữ (theo giá đóng cửa tuần cuối)", f'=SUMIFS({rng("M")},{rng("K")},"Đang giữ")', VND),
    ("+ Lãi quỹ thị trường tiền tệ trên tiền nhàn rỗi", f"=SUM({crng('H')})", VND),
    ("GIÁ TRỊ DANH MỤC CUỐI KỲ (tổng 4 dòng trên)", "=SUM(B14:B17)", VND),
    ("Kiểm tra: tổng tài sản tuần cuối ở sheet Dòng tiền", f"={CS}G{c1}", VND),
    ("Chênh lệch (phải bằng 0)", "=ROUND(B18-B19,0)", VND),
    ("Giá trị cuối kỳ (tỷ VND)", "=B18/1000000000", '0.00'),
    ("Lãi kép mỗi năm (CAGR)", f"=(B18/{CAP})^(365.25/({END}-{START}))-1", PCT),
]
for k, (lab, f, fmt) in enumerate(recon, 14):
    ws.cell(row=k, column=1, value=lab).font = BOLD if lab.startswith("GIÁ TRỊ") else BLACK
    c = ws.cell(row=k, column=2, value=f); c.number_format = fmt; c.font = BOLD if lab.startswith("GIÁ TRỊ") else BLACK
ws["B18"].fill = LIGHT; ws["B21"].fill = LIGHT; ws["B22"].fill = LIGHT

ws["A24"] = "THỐNG KÊ LỆNH (chỉ lệnh đã bán)"; ws["A24"].font = BOLD
st = [
    ("Số lệnh đã bán", f'=COUNTIFS({rng("K")},"Đã bán")', "0"),
    ("Số lệnh đang giữ", f'=COUNTIFS({rng("K")},"Đang giữ")', "0"),
    ("Số lệnh thắng", f'=COUNTIFS({rng("K")},"Đã bán",{rng("N")},">0")', "0"),
    ("Tỷ lệ thắng", "=B27/B25", PCT),
    ("Lãi trung bình lệnh thắng", f'=AVERAGEIFS({rng("N")},{rng("K")},"Đã bán",{rng("N")},">0")', PCT),
    ("Lỗ trung bình lệnh thua", f'=AVERAGEIFS({rng("N")},{rng("K")},"Đã bán",{rng("N")},"<=0")', PCT),
    ("R:R (lãi TB thắng / lỗ TB thua)", "=B29/-B30", '0.0"x"'),
    ("Kỳ vọng mỗi lệnh", f'=AVERAGEIFS({rng("N")},{rng("K")},"Đã bán")', PCT),
    ("Lệnh lãi lớn nhất", f'=_xlfn.MAXIFS({rng("N")},{rng("K")},"Đã bán")', PCT),
    ("Lệnh lỗ lớn nhất", f'=_xlfn.MINIFS({rng("N")},{rng("K")},"Đã bán")', PCT),
    ("Số lần khớp cắt lỗ", f'=COUNTIFS({rng("J")},"Cắt lỗ*")', "0"),
    ("Tổng lãi quỹ tiền tệ (VND)", "=B17", VND),
]
for k, (lab, f, fmt) in enumerate(st, 25):
    ws.cell(row=k, column=1, value=lab).font = BLACK
    c = ws.cell(row=k, column=2, value=f); c.number_format = fmt; c.font = BLACK
ws.freeze_panes = "A4"

# ---------------- Lệnh
cols = ["STT", "Mã", "Tuần có tín hiệu (chốt thứ 6)", "Ngày mua (ATO thứ 2)", "Giá mua (giá mở cửa, VND)", "Tiền mua (VND)",
        "Số cổ phiếu", "Ngày bán (tuần)", "Giá bán (VND)", "Lý do bán", "Trạng thái", "Tiền thu về (VND, sau phí)",
        "Lãi/lỗ (VND)", "Lãi/lỗ (%)", "Số tuần giữ"]
header(wl, 1, cols, [6, 8, 14, 14, 14, 16, 14, 14, 14, 44, 11, 18, 17, 11, 9])
for k, r in T.iterrows():
    row = k + 2
    wl.cell(row=row, column=1, value=k + 1).font = BLACK
    wl.cell(row=row, column=2, value=r.t).font = BLACK
    c = wl.cell(row=row, column=3, value=r.sig_date.to_pydatetime()); c.number_format = DATE; c.font = BLUE
    c = wl.cell(row=row, column=4, value=r.entry_date.to_pydatetime()); c.number_format = DATE; c.font = BLUE
    c = wl.cell(row=row, column=5, value=float(r.entry_px)); c.number_format = PX; c.font = BLUE
    c = wl.cell(row=row, column=6, value=float(r.amount)); c.number_format = VND; c.font = BLUE
    c = wl.cell(row=row, column=7, value=f"=F{row}/(E{row}*(1+{FEE}))"); c.number_format = '#,##0'
    is_open = bool(r.get("open", False)) if not pd.isna(r.get("open", False)) else False
    c = wl.cell(row=row, column=8, value=None if is_open else r.exit_date.to_pydatetime()); c.number_format = DATE; c.font = BLUE
    c = wl.cell(row=row, column=9, value=float(r.exit_px)); c.number_format = PX; c.font = BLUE
    wl.cell(row=row, column=10, value=r.reason).font = BLUE
    wl.cell(row=row, column=11, value="Đang giữ" if is_open else "Đã bán").font = BLUE
    c = wl.cell(row=row, column=12, value=f'=IF(K{row}="Đang giữ",G{row}*I{row},G{row}*I{row}*(1-{FEE}))'); c.number_format = VND
    c = wl.cell(row=row, column=13, value=f"=L{row}-F{row}"); c.number_format = VND
    c = wl.cell(row=row, column=14, value=f"=M{row}/F{row}"); c.number_format = PCT
    c = wl.cell(row=row, column=15, value=f'=IF(K{row}="Đang giữ",({END}-D{row})/7,(H{row}-D{row})/7)'); c.number_format = "0"
    for col in range(1, 16): wl.cell(row=row, column=col).border = Border(bottom=thin)
tr = r1 + 2
wl.cell(row=tr, column=1, value="Tổng").font = BOLD
for col, f in [(6, f"=SUM(F{r0}:F{r1})"), (12, f"=SUM(L{r0}:L{r1})"), (13, f"=SUM(M{r0}:M{r1})")]:
    c = wl.cell(row=tr, column=col, value=f); c.number_format = VND; c.font = BOLD
wl.cell(row=tr + 2, column=1, value=("Ghi chú: Tiền mua, ngày, giá mua/bán và lý do bán lấy từ mô phỏng (chữ xanh dương). Tiền mua = 1/12 tổng tài sản "
                                     "tại tuần có tín hiệu (hoặc phần tiền mặt còn lại nếu ít hơn). Lệnh cắt lỗ ghi theo tuần chạm mức cắt; giá bán = mức cắt "
                                     "(hoặc giá mở cửa nếu mở cửa đã thấp hơn). Lệnh 'Đang giữ' định giá theo giá đóng cửa tuần cuối, chưa trừ phí bán. "
                                     "Số cổ phiếu là số lẻ (chưa làm tròn lô 100) và theo giá đã điều chỉnh.")).font = Font(name=F, italic=True, color="595959")
wl.freeze_panes = "C2"

# ---------------- Dòng tiền (weekly)
cols = ["Tuần (thứ 2)", "Tiền mặt đầu tuần", "Tiền bán thu về", "Tiền mua", "Tiền mặt sau giao dịch",
        "Giá trị cổ phiếu (giá đóng cửa)", "Tổng tài sản", "Lãi quỹ trong tuần", "Tiền mặt chuyển sang tuần sau", "Số mã đang giữ", "Tỷ lệ tiền mặt"]
header(wc, 1, cols, [13, 17, 16, 16, 18, 18, 18, 14, 18, 10, 10])
for k, r in W.iterrows():
    row = k + 2
    c = wc.cell(row=row, column=1, value=r.date.to_pydatetime()); c.number_format = DATE
    c = wc.cell(row=row, column=2, value=f"={CAP}" if k == 0 else f"=I{row-1}"); c.number_format = VND
    if k == 0: c.font = GREEN
    c = wc.cell(row=row, column=3, value=f'=SUMIFS({rng("L")},{rng("H")},A{row},{rng("K")},"Đã bán")'); c.number_format = VND; c.font = GREEN
    c = wc.cell(row=row, column=4, value=f'=SUMIFS({rng("F")},{rng("D")},A{row})'); c.number_format = VND; c.font = GREEN
    c = wc.cell(row=row, column=5, value=f"=B{row}+C{row}-D{row}"); c.number_format = VND
    c = wc.cell(row=row, column=6, value=float(r.stock)); c.number_format = VND; c.font = BLUE
    c = wc.cell(row=row, column=7, value=f"=E{row}+F{row}"); c.number_format = VND
    c = wc.cell(row=row, column=8, value=f"=IF(A{row}={END},0,E{row}*((1+{RLIQ})^(1/52)-1))"); c.number_format = VND
    c = wc.cell(row=row, column=9, value=f"=E{row}+H{row}"); c.number_format = VND
    c = wc.cell(row=row, column=10, value=f'=COUNTIFS({rng("D")},"<="&A{row},{rng("H")},">"&A{row})+COUNTIFS({rng("D")},"<="&A{row},{rng("K")},"Đang giữ")'); c.number_format = "0"; c.font = GREEN
    c = wc.cell(row=row, column=11, value=f"=E{row}/G{row}"); c.number_format = PCT
wc.cell(row=c1 + 2, column=1, value=("Ghi chú: 'Giá trị cổ phiếu' = tổng (số cổ phiếu đang giữ × giá đóng cửa tuần) từ dữ liệu giá (chữ xanh dương). "
                                     "Tiền bán/mua lấy theo ngày từ sheet Lệnh. Thứ tự trong tuần: bán (ATO) → mua (ATO) → cắt lỗ trong tuần → định giá cuối tuần → cộng lãi quỹ.")).font = Font(name=F, italic=True, color="595959")
wc.freeze_panes = "B2"

# ---------------- Theo năm
cols = ["Năm", "Tuần cuối năm", "Tổng tài sản cuối năm", "Tiền mặt", "Giá trị cổ phiếu", "Số mã đang giữ", "Lãi/lỗ trong năm (%)", "Lãi quỹ trong năm",
        "Số lệnh mua trong năm", "Số lệnh bán trong năm"]
header(wy, 1, cols, [8, 14, 20, 18, 18, 10, 12, 16, 12, 12])
years = sorted(W.date.dt.year.unique())
for k, y in enumerate(years):
    row = k + 2
    wy.cell(row=row, column=1, value=str(y)).font = BLACK
    lo, hi = f"DATE({y},1,1)", f"DATE({y},12,31)"
    c = wy.cell(row=row, column=2, value=f'=_xlfn.MAXIFS({crng("A")},{crng("A")},">="&{lo},{crng("A")},"<="&{hi})'); c.number_format = DATE
    m = f"MATCH(B{row},{crng('A')},0)"
    for col, src, fmt in [(3, "G", VND), (4, "E", VND), (5, "F", VND), (6, "J", "0")]:
        c = wy.cell(row=row, column=col, value=f"=INDEX({crng(src)},{m})"); c.number_format = fmt; c.font = GREEN
    prev = f"{CAP}" if k == 0 else f"C{row-1}"
    c = wy.cell(row=row, column=7, value=f"=C{row}/{prev}-1"); c.number_format = PCT
    c = wy.cell(row=row, column=8, value=f'=SUMIFS({crng("H")},{crng("A")},">="&{lo},{crng("A")},"<="&{hi})'); c.number_format = VND
    c = wy.cell(row=row, column=9, value=f'=COUNTIFS({rng("D")},">="&{lo},{rng("D")},"<="&{hi})'); c.number_format = "0"
    c = wy.cell(row=row, column=10, value=f'=COUNTIFS({rng("H")},">="&{lo},{rng("H")},"<="&{hi})'); c.number_format = "0"
wy.freeze_panes = "B2"

# ---------------- Quy tắc
lines = [
    ("QUY TẮC CỦA BACKTEST", True),
    ("Vũ trụ: 20 công ty chứng khoán + 19 ngân hàng thương mại niêm yết HOSE, bỏ VCB, BID, CTG (Agribank chưa niêm yết).", False),
    ("Chứng khoán: AGR, APG, BSI, CTS, DSC, DSE, FTS, HCM, ORS, SSI, TCI, TCX, TVB, TVS, VCI, VCK, VDS, VIX, VND, VPX", False),
    ("Ngân hàng: ACB, BVB, EIB, HDB, KLB, LPB, MBB, MSB, NAB, OCB, SHB, SSB, STB, TCB, TPB, VAB, VBB, VIB, VPB", False),
    ("Mua: giá đóng cửa tuần (thứ 6) cho EMA9 cắt lên WMA45, và tại tuần đó EMA9 của VNINDEX còn nằm dưới WMA45 (tín hiệu 'dẫn dắt'); thanh khoản trung vị 26 tuần ≥ 1 tỷ/tuần. Mua giá mở cửa thứ 2 tuần sau.", False),
    ("Quy mô lệnh: 1/12 tổng tài sản tại tuần có tín hiệu; tối đa 12 mã cùng lúc. Nhiều tín hiệu hơn chỗ trống: ưu tiên mã đang thấp hơn đỉnh 52 tuần nhiều hơn.", False),
    ("Bán (cái nào đến trước): (1) giá chạm -25% so với giá mua trong tuần → bán ngay ở mức đó (hoặc giá mở cửa nếu đã gap thấp hơn); (2) EMA9 cắt xuống WMA45 khi chốt tuần → bán giá mở cửa thứ 2.", False),
    ("Không mua lại sau khi bị cắt lỗ cho tới tín hiệu cắt lên mới. Không cân bằng lại tỷ trọng.", False),
    ("Tiền nhàn rỗi: quỹ thị trường tiền tệ 4%/năm, cộng theo tuần, rút được ngay.", False),
    ("", False),
    ("LƯU Ý", True),
    ("Giá là giá đã điều chỉnh cổ tức/chia tách (nguồn KBS, dự phòng SSI), nên khác giá trên bảng điện tại thời điểm đó; cổ tức đã nằm trong giá điều chỉnh.", False),
    ("Số cổ phiếu là số lẻ, chưa làm tròn lô 100; chưa trừ thuế bán 0,1%, thuế 5% trên lãi tiền gửi, trượt giá.", False),
    ("Đây là kết quả backtest (mô phỏng quá khứ), không phải lời khuyên đầu tư; Claude không phải chuyên gia tư vấn tài chính được cấp phép.", False),
    ("Nguồn: D:\\quant-trading (data_prices.db), mô phỏng scratchpad ledger.py.", False),
]
wr.column_dimensions["A"].width = 160
for k, (txt, b) in enumerate(lines, 1):
    c = wr.cell(row=k, column=1, value=txt); c.font = BOLD if b else BLACK; c.alignment = Alignment(wrap_text=True)

for sh in [ws, wl, wc, wy]:
    for row in sh.iter_rows():
        for c in row:
            if c.font is None or c.font.name != F:
                c.font = Font(name=F, bold=c.font.bold if c.font else False, color=c.font.color if c.font else None)
wb.calculation.fullCalcOnLoad = True
wb.save(OUT)
print("saved", OUT, "rows", nT, nW)
