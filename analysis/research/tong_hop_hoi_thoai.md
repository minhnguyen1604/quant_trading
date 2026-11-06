# Tổng hợp trao đổi: đánh giá EMA9/WMA45 khung tuần (11/2026)

Tóm tắt các câu hỏi và kết quả trong buổi làm việc với Claude (tháng 11/2026). Dữ liệu giá tuần HOSE đã điều chỉnh
cổ tức/chia tách (KBS, dự phòng SSI) đến 03/11/2026; kỳ backtest chính 06/11/2017 – 02/11/2026 (~9 năm).
Script tái tạo nằm trong `analysis/research/` (xem `README.md` cùng thư mục) và `analysis/0*_*.py`.

> Đây là thống kê backtest (mô phỏng quá khứ), không phải lời khuyên đầu tư. Kết quả chưa trừ thuế bán 0,1%,
> thuế lãi tiền gửi, trượt giá; chỉ gồm các mã đang niêm yết (thiên lệch sống sót); các quy tắc được chọn sau khi
> đã nhìn dữ liệu nên kết quả tương lai nhiều khả năng thấp hơn.

## Quy ước chung

- **Mua:** EMA9 cắt lên WMA45 khi chốt tuần (thứ 6) → mua giá mở cửa thứ 2. **Bán gốc:** EMA9 cắt xuống WMA45 → bán giá mở cửa thứ 2.
- Phí 0,15%/chiều. "Lãi/năm" = lãi kép bình quân năm (CAGR). "Sụt giảm lớn nhất" = MDD từ đỉnh trước đó.
- **Chia đều:** chia vốn đều cho từng mã từ đầu kỳ, mỗi mã chạy độc lập. **Vốn chung N mã:** một khoản vốn chung, tối đa N mã cùng lúc, mỗi lệnh = 1/N tổng tài sản lúc mua.
- **Tín hiệu dẫn dắt:** mã cắt lên khi EMA9 của chính VNINDEX còn nằm dưới WMA45 (thị trường chung chưa vào xu hướng tăng).
- **Ngân hàng bỏ Big4:** bỏ VCB, BID, CTG (Agribank chưa niêm yết) → 19 mã: ACB, BVB, EIB, HDB, KLB, LPB, MBB, MSB, NAB, OCB, SHB, SSB, STB, TCB, TPB, VAB, VBB, VIB, VPB.
- **Chứng khoán (20 mã):** AGR, APG, BSI, CTS, DSC, DSE, FTS, HCM, ORS, SSI, TCI, TCX, TVB, TVS, VCI, VCK, VDS, VIX, VND, VPX.

## 1. Đánh giá tổng quát (đã có trong `analysis/output/01..04`)

- Toàn HOSE (402 mã, 2.831 lệnh): thắng 36,7%, lãi TB/lệnh +14,7%, trung vị −4,2%; lãi kép danh mục ~9,5%/năm, MDD −21% (mua giữ −49%). Lợi thế yếu ở mã thanh khoản cao và phụ thuộc nhiều vào chu kỳ 2020–2021.
- Ngành chu kỳ hợp hơn. Lãi/năm 2018–2025: chứng khoán 23,4%, ngân hàng 15,7%, vận tải 14,5%, thép 11,1%, BĐS 10,5%, VN30 16,9%.
- Chốt lời cố định làm hỏng kết quả (lợi nhuận đến từ vài lệnh x2–x10). Trailing 25% là thay đổi duy nhất ổn định ở cả 2017–2022 và 2023–2026 (giảm MDD, lãi gần như không đổi).
- Cắt lỗ cố định 17–20% theo đóng cửa tuần cho kết quả gần như nhau; bán ATC thứ 6 thay vì ATO thứ 2 nhỉnh hơn ~0,1–0,15 điểm %/năm và giảm lỗ do gap đầu tuần.

## 2. Tiền nhàn rỗi và lãi tiền gửi (5 ngành chu kỳ, 130 mã, chia đều)

- Tiền nằm ngoài cổ phiếu nhiều nhất đúng lúc thị trường giảm: 2018, 3–5/2020, 5/2022–3/2023, từ 3/2026. Gần như đầu tư hết 9/2020–4/2022.
- Mỗi lần một mã đứng ngoài: trung vị 18 tuần (25%: 7 tuần, 75%: 40 tuần, 16% trên 1 năm).
- 1 tỷ, 11/2017–11/2026: không lãi gửi 2,64 tỷ (11,4%/năm); gửi 5% → 3,32 tỷ (14,3%); gửi 7% → 3,63 tỷ (15,4%). Mua giữ 2,51 tỷ (10,8%, MDD −51%). Gửi tiết kiệm 7% toàn bộ: 1,84 tỷ.

## 3. Ngành chứng khoán và ngân hàng (chia đều, gửi 7%)

| Nhóm | Cuối kỳ | Lãi/năm | MDD | Mua giữ |
|---|---|---|---|---|
| Chứng khoán (20 mã) | 5,96 tỷ | 22,0% | −27% | 3,95 tỷ (−66%) |
| Ngân hàng (22 mã, gồm Big4) | 3,43 tỷ | 14,7% | −18% | 3,42 tỷ (−44%) |
| CK + NH | 4,64 tỷ | 18,6% | −22% | 3,67 tỷ (−58%) |

- Chứng khoán: R:R ~11,6; 10/10 lệnh tốt nhất mua 2020, bán đầu 2022; 2024–2026 gần như đi ngang.
- Từng mã chứng khoán (1 tỷ/mã): VIX 18,8 tỷ, VND 14,6, SSI 10,0, VCI 9,9, FTS 9,8; HCM 4,2 (mua giữ 4,4).
- Ngân hàng: 11/22 mã thắng mua giữ. Hợp: LPB 13,5 tỷ, SHB 11,9, MBB 6,3, TCB 4,2. Không hợp (tăng đều, nhiều tín hiệu giả): BID 0,56 tỷ, VCB 0,97, CTG, ACB, STB, VIB.

## 4. Chốt lời gần đỉnh

- Cách gốc giữ được ~65% đỉnh (theo log) trên các sóng từng lãi ≥30%, trả lại trung vị ~45 điểm %.
- ~30 quy tắc đã thử (trailing 15–30%, chandelier ATR, RSI tuần, EMA9/SMA10/EMA5 sau khi có lãi, chốt 1/2 ở +100%, mua lại...): quy tắc chặt bán đúng đỉnh ngắn hạn nhưng mất sóng lớn; kết quả đảo chiều giữa 2017–2022 và 2023–2026.
- Duy nhất **giá đóng cửa tuần ≥ 2 lần WMA45 → bán** cải thiện ngành chứng khoán ở cả hai giai đoạn (6,9 tỷ so với 6,0), nhưng chỉ kích hoạt 11–12 lần (10 lần trong 2020–2021). Ngân hàng và cổ phiếu lớn (FPT, VIC, VHM) gần như không chạm ngưỡng này.

## 5. FPT, VIC, VHM (1 tỷ/mã, gửi 7%)

- FPT 6,77 tỷ (mua giữ 4,11), VHM 3,09 (2,04), VIC 5,84 (9,65; thua mua giữ).
- VIC: 6 lệnh lỗ liên tiếp 2019–2024 (có lệnh −38,8% mua 14/8/2023 vì EMA9 chưa kịp cắt xuống), sau đó 1 lệnh +918% (đang giữ). Với cắt lỗ 18%: lệnh đó còn −18% đến −21%.
- Với cổ phiếu lớn, các cách chốt sớm đều kém hoặc không đổi; nên giữ cách gốc + cắt lỗ rộng.

## 6. Cắt lỗ trong tuần, x2 WMA45, mua lại (ngành chứng khoán, chia đều, gửi 7%)

Bán theo điều kiện nào đến trước (cắt lỗ trong tuần / giá ≥ 2×WMA45 / EMA9 cắt xuống).

| Cách | Cuối kỳ | Lãi/năm | MDD | Lệnh tệ nhất |
|---|---|---|---|---|
| Gốc | 6,0 tỷ | 22,0% | −27,6% | −43% |
| Cắt lỗ −18% trong tuần | 5,3 | 20,5% | −25,7% | −26% |
| x2 WMA45 bán hết | 6,9 | 24,0% | −23,5% | −43% |
| Cắt lỗ −18% + x2 | 6,3 | 22,8% | −22,5% | −26% |
| Cắt lỗ −18% + x2 + mua lại khi giá đóng cửa tuần vượt giá mua cũ | 6,6 | 23,4% | −23,1% | −26% |

- Cắt lỗ trong tuần −18% quét mất AGR, TCI, DSC đầu sóng 2020 (sau đó +160% đến +365%); mua lại cứu được phần lớn. Mức −18% đến −25% cho kết quả gần như nhau; −15% quá chặt.

## 7. Chọn mã: tiêu chí đo được ngay lúc có tín hiệu (toàn HOSE, 2.831 lệnh)

- Vô dụng hoặc không ổn định: hiệu quả quá khứ của phương pháp trên chính mã đó, sức mạnh giá 26/52 tuần, % mã cùng ngành đang tăng, độ "thẳng" xu hướng.
- Giúp vừa phải: biên độ đỉnh/đáy 3 năm lớn (≥2 lần), thanh khoản đủ.
- **Mạnh và ổn định nhất: tín hiệu dẫn dắt.** Khi VNINDEX còn dưới xu hướng: thắng 45%, lãi TB/lệnh +25,8% (2023–2026: +15,0%); khi VNINDEX đã tăng: thắng 31%, +8,4% (2023–2026: −0,3%). Tốt hơn ở 7/8 năm.
- Hiện có 154 mã đạt thanh khoản ≥1 tỷ/tuần và biên độ 3 năm ≥2 lần (`watchlist.csv`, snapshot 02/11/2026); VCB, VNM, MSN, SAB, HPG, BID không đạt.

## 8. Vốn chung, chứng khoán + ngân hàng bỏ Big4

Toàn HOSE: dồn vốn vào 5–30 mã không tốt hơn chia đều (MDD gấp đôi). Nhưng trong nhóm CK + NH bỏ Big4, vốn chung tốt hơn chia đều (chia đều gốc: 4,9 tỷ, 19,3%/năm, MDD −22%).

Vốn chung, thanh khoản ≥1 tỷ/tuần, gửi 7% (số liệu sau khi sửa lỗi bộ lọc, xem lưu ý cuối mục):

| Cấu hình | Cuối kỳ | Lãi/năm | MDD | 2017–22 | 2023–26 | Thắng | Số lệnh |
|---|---|---|---|---|---|---|---|
| 10 mã, chỉ dẫn dắt | 6,0 tỷ | 22,1% | −22% | 21,8% | 22,5% | 49% | 45 |
| 15 mã, mọi tín hiệu | 5,2 | 20,2% | −24% | 21,5% | 18,6% | 38% | 120 |
| 15 mã, chỉ dẫn dắt | 5,9 | 21,8% | −17% | 22,9% | 20,3% | 53% | 57 |
| 20 mã, mọi tín hiệu | 6,1 | 22,2% | −24% | 25,0% | 18,6% | 42% | 142 |

- 15 là số mã **tối đa**: thực tế 30% thời gian không giữ mã nào, trung bình giữ ~6 mã, ~60% vốn nằm ngoài cổ phiếu.
- Độ bền: 10–15 mã cho kết quả gần như nhau; trên 18 mã lãi giảm dần. Bắt đầu từ 2021 trở đi chỉ còn ~15–18%/năm; từ 2024 ~9–10%. Chỉ mua tín hiệu dẫn dắt thắng ở mọi ngày bắt đầu từ 2021.
- Lưu ý: bản đầu của `pool.py` vô tình bỏ tín hiệu của mã có dưới ~2 năm dữ liệu khi tắt bộ lọc biên độ; đã sửa. Các bảng độ bền (số mã 6–30, ngày bắt đầu) trong trao đổi được tính trước khi sửa, cao hơn khoảng 0,3–0,6 điểm %/năm. `pool_cash.py` và `ledger.py` không bị lỗi này.

### Lãi tiền nhàn rỗi thực tế (12 mã dẫn dắt + cắt lỗ 22%, rút trước hạn chỉ được 0,5%/năm)

| Cách gửi | Cuối kỳ | Lãi/năm | Số lần rút sớm |
|---|---|---|---|
| Không kỳ hạn 0,5% | 4,8 tỷ | 19,2% | 0 |
| Quỹ thị trường tiền tệ 4% | 5,7 | 21,4% | 0 |
| Sổ 6 tháng 5%/năm | 5,5 | 20,9% | 49 |
| Sổ 6 tháng 5% + giữ 2 suất mua ở quỹ 4% | 5,7 | 21,3% | 21 |
| Sổ 12 tháng 6%/năm | 5,3 | 20,4% | 59 |

- Riêng phần cổ phiếu ~18–19%/năm; lãi tiền gửi cộng thêm ~2–4 điểm %. Sổ 12 tháng kém nhất vì phải rút sớm nhiều.

### Mức cắt lỗ (12 mã dẫn dắt, quỹ 4%)

| Cắt lỗ | Cuối kỳ | Lãi/năm | MDD | R:R | Lệnh tệ nhất |
|---|---|---|---|---|---|
| Không | 5,51 tỷ | 20,9% | −19% | 10,7 | −43% |
| −20% | 5,04 | 19,7% | −17% | 11,2 | −23% |
| −22% | 5,71 | 21,4% | −18% | 12,2 | −23% |
| −25% | 5,71 | 21,4% | −18% | 12,2 | −25% |

- Chênh lệch −20% với −22% đến từ đúng 1 lệnh (AGR 6/2020 rơi ~−21% trong tuần rồi lên +365%). Từ 2021 mọi mức gần như bằng nhau (~20,5%). Coi cắt lỗ là bảo hiểm; khoảng −20% đến −25% đều hợp lý.

### Sổ lệnh chi tiết: 12 mã dẫn dắt, cắt lỗ −25%, quỹ 4%

File `analysis/output/so_lenh_ck_nh_12ma_catlo25.xlsx` (sheet Lệnh, Dòng tiền, Theo năm, Tóm tắt, Quy tắc).

- 1.000.000.000 + lãi 49 lệnh đã bán 4.344.118.641 − lỗ tạm tính 6 lệnh đang giữ 147.662.268 + lãi quỹ 521.067.889 = **5.717.524.262 đồng** (21,4%/năm, MDD −18%).
- 49 lệnh đã bán: thắng 51%, lãi TB lệnh thắng +135%, lỗ TB lệnh thua −11%, R:R ~12,2; chỉ 4 lần khớp cắt lỗ.
- Tài sản cuối năm (tỷ): 2018 1,04 · 2019 1,07 · 2020 1,71 · 2021 3,29 · 2022 2,86 · 2023 4,09 · 2024 4,99 · 2025 5,91 · 2026 5,72.
- Lệnh lớn nhất: LPB mua 02/01/2023, 238 triệu → +979 triệu (~1/4 tổng lãi).

## 9. So sánh với tài sản khác (ước tính, kỳ không trùng hoàn toàn)

| Tài sản | Lãi/năm (VND) | Sụt giảm lớn nhất |
|---|---|---|
| Backtest 12 mã dẫn dắt, cắt lỗ 25% | 21,4% | −18% |
| Kỳ vọng thận trọng cho cách trên | ~14–18% | ~−20% |
| VNINDEX chỉ giá / cộng cổ tức | 7,8% / ~9–10% | −42% |
| Vàng SJC (36,5 → ~140 triệu/lượng) | ~15–16% | ~−15–20% |
| S&P 500 (gồm cổ tức, quy VND) | ~15–16% | ~−25% |
| Quỹ cổ phiếu tốt trong nước (DCDS, ước tính bên thứ ba) | ~15–17% | ~−35–45% |
| Gửi tiết kiệm | ~5–7% | 0% |

Kết luận: nếu là thực tế thì 21,4% rất tốt; sau khi trừ hao (chọn ngành/quy tắc sau khi thấy dữ liệu, thuế, trượt giá,
chu kỳ 2020 mạnh) mức hợp lý ~14–18%/năm, ngang quỹ tốt nhưng rủi ro thấp hơn rõ. Điểm mạnh là tỷ lệ lợi nhuận/rủi ro.

Nguồn tham khảo cho mục 9: [Finhay – quỹ Dragon Capital](https://www.finhay.com.vn/quy-dragon-capital-2),
[Motley Fool – S&P 500 annual returns](https://www.fool.com/investing/stock-market/indexes/sp-500/annual-returns),
[ChartRow – SPY returns](https://chartrow.com/quote/spy/returns), [Simplize – giá vàng SJC](https://simplize.vn/gia-vang/sjc).

## Bộ quy tắc rút ra

1. **Chọn mã:** chứng khoán + ngân hàng tư nhân (bỏ Big4); nói chung ưu tiên mã có biên độ chu kỳ lớn, thanh khoản đủ.
2. **Mua:** EMA9 cắt lên WMA45 khung tuần, ưu tiên/ chỉ nhận khi VNINDEX còn dưới xu hướng (tín hiệu dẫn dắt).
3. **Phân bổ:** vốn chung, tối đa ~12–15 mã, mỗi lệnh 1/12–1/15 tổng tài sản, không cân bằng lại.
4. **Bán:** EMA9 cắt xuống WMA45 (cách gốc), thêm cắt lỗ rộng −20% đến −25% làm bảo hiểm. Không chốt lời cố định, không trailing chặt. (Riêng ngành chứng khoán khi quá nóng: có thể bán khi giá ≥ 2×WMA45.)
5. **Tiền nhàn rỗi:** quỹ thị trường tiền tệ hoặc sổ 3–6 tháng chia nhiều sổ, giữ sẵn tiền cho ~2 lệnh mua.
6. **Kỳ vọng:** ~14–18%/năm, có những năm gần như không có lệnh; nên chạy thử trên giấy hoặc vốn nhỏ 6–12 tháng trước.
