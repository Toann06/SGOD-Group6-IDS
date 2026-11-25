# Source Review v1 — SGOD-P1-W02-B2

Ngày kiểm định: 2026-11-22  
Thực hiện bởi: auditor (swarm SGOD-P1-W02-B2)  
Trạng thái: **Bản nháp — chờ reviewer (coordinator) xem xét**

---

## 1. Danh sách file đã đọc

| # | Path thực tế | Tồn tại | Kích thước | Phiên bản / Mô tả |
|---|---|---|---|---|
| 1 | `D:\SGOD\SGOD-B2\SGOD-P1-W01-B2\docs\schema_v1.md` | ✅ | 5.974 B | Schema v1 — bản sơ bộ, 15 cột, chờ reviewer |
| 2 | `D:\SGOD\SGOD-B2\SGOD-P1-W01-B2\outputs\sample_10.csv` | ✅ | 937 B | 10 bản ghi mẫu, header 15 cột, ALL TESTS PASSED |
| 3 | `D:\SGOD\SGOD-B2\SGOD-P1-W01-B2\README.md` | ✅ | 1.421 B | README W01-B2, source verification 10/10 PASS |
| 4 | `D:\SGOD\SGOD-B2\references\SGOD-P1-W02-B1\docs\data_specification_v0.2.md` | ✅ | 11.870 B | v0.2 (16/11/2026) — bản nháp, 17 cột (15+2 đề xuất) |
| 5 | `D:\SGOD\SGOD-B2\references\SGOD-P1-W02-B1\docs\eda_report_v0.2.md` | ✅ | 6.259 B | EDA v0.2 (16/11/2026) — chờ reviewer |
| 6 | `D:\SGOD\SGOD-B2\references\SGOD-P1-W02-B1\scripts\can_parser.py` | ✅ | 3.477 B | Parser HCRL — kế thừa schema v1 B2, thêm label_provenance |
| 7 | `D:\SGOD\SGOD-B2\references\SGOD-P1-W02-B1\scripts\preprocess.py` | ✅ | 5.902 B | Preprocessing — 17 cột output (15+2 đề xuất) |
| 8 | `D:\SGOD\SGOD-B2\references\SGOD-P1-W02-B1\outputs\tail_overlap\report.md` | ✅ | 714 B | Tail overlap 891.068 dòng giống hệt, 100% R |
| 9 | `D:\SGOD\SGOD-B2\references\SGOD-P1-W02-B1\outputs\preprocess_fixture\preprocess_summary.json` | ✅ | 2.060 B | Fixture run: 15 đọc, 12 ghi, 3 malformed |
| 10 | `D:\SGOD\SGOD-B2\references\SGOD-P1-W02-B1\outputs\preprocess_real\preprocess_summary.json` | ✅ | 2.394 B | Real run: 17.558.347 đọc, 17.558.346 ghi, 1 malformed |

**Tổng tài liệu tham chiếu đã đọc: 10/10** — không có file MISSING trong danh sách bắt buộc.

> **Lưu ý:** `data_specification_v0.2.md` và `eda_report_v0.2.md` đều được liệt kê "(nếu tồn tại)" nhưng thực tế có mặt đầy đủ trong `references/SGOD-P1-W02-B1/docs/`.

---

## 2. Datasets đã đọc header và mẫu

| File | Tồn tại | Kích thước (MB) | Số cột raw | DLC mẫu dòng 0 | Readable |
|---|---|---|---|---|---|
| `DoS_dataset.csv` | ✅ | 181,3 | 12 (không header) | 8 | ✅ |
| `Fuzzy_dataset.csv` | ✅ | 189,3 | 12 (không header) | 8 | ✅ |
| `gear_dataset.csv` | ✅ | 219,7 | 12 (không header) | 8 | ✅ |
| `RPM_dataset.csv` | ✅ | 228,4 | 12 (không header) | 8 | ✅ |
| `normal_run_data.txt` | ✅ | 83,3 | n/a (text format) | 8 | ✅ |

**Cấu trúc raw CSV** (12 cột): `timestamp, can_id, dlc, data_0..data_7, flag` (layout DLC=8 cho dòng mẫu).  
**normal_run_data.txt** format: `Timestamp: <ts>  ID: <id>  <extra_000>  DLC: <n>  <bytes...>`

---

## 3. Phiên bản xác định từ file

| Tài liệu | Phiên bản |
|---|---|
| schema_v1.md (W01-B2) | v1 (không có ngày tháng trong file) |
| data_specification_v0.2.md (W02-B1) | v0.2 (16/11/2026) |
| eda_report_v0.2.md (W02-B1) | v0.2 (16/11/2026) |
| can_parser.py | Không có version tag rõ ràng; docstring đề "schema v1 (B2) va input contract (B3)" |
| preprocess.py | Không có version tag; note trong JSON output: "segment_id chi danh dau gap, khong cat du lieu; label_provenance va segment_id la cot de xuat" |
| preprocess_summary.json (fixture) | gap_seconds=1.0, max_rows=null |
| preprocess_summary.json (real) | gap_seconds=1.0, max_rows=null, chạy 16/11/2026 |

---

## 4. Phát hiện quan trọng

### 4.1 Đoạn đuôi dùng chung (Critical)
**[ĐO từ tail_overlap/report.md và data_specification_v0.2.md §7]**  
891.068 dòng cuối của 4 file CSV giống hệt nhau (timestamp, CAN ID, DLC, data, flag) — SHA-256 đoạn đuôi trùng nhau ở cả 4 file (`8dc026b6...`). Toàn bộ đoạn đuôi là flag `R` (normal), không có T nào. Đây là rò rỉ dữ liệu nghiêm trọng: nếu chia train/test theo file hoặc dòng ngẫu nhiên, 2.673.204 bản sao của 891.068 dòng sẽ xuất hiện ở cả train lẫn test.

### 4.2 Schema W02-B1 thêm 2 cột đề xuất (D6 chưa chốt)
`preprocess.py` đã **thực tế** ghi output 17 cột (15 từ W01-B2 + `label_provenance` + `segment_id`). Tuy nhiên, `data_specification_v0.2.md` §9 mục D6 vẫn ghi **[ĐỀ XUẤT]** và cần B2 đồng ý. Schema v2 chưa được chốt chính thức.

### 4.3 pytest không có trong venv
`D:\SGOD\SGOD-B2\.venv` **không** có pytest. `pip show pytest` trả về `WARNING: Package(s) not found`. Các test trong `references/SGOD-P1-W02-B1/tests/` sẽ không chạy được trong venv hiện tại.

### 4.4 Nhãn normal TXT là nhãn suy ra — không phải flag quan sát
Label 0 của `normal_run_data.txt` (988.871 bản ghi) được suy ra từ tên file, không có Flag R/T. `label_provenance = "inferred_from_source"`. Mọi thống kê và đánh giá phải tách rõ nhóm này.

### 4.5 Dữ liệu raw có 1 dòng malformed
Dòng 988.872 của `normal_run_data.txt` bị cụt (`Timestamp: 1479121941.287013` thiếu phần còn lại). Đã được log và loại trong preprocess_real.

### 4.6 DoS attack CAN ID 0000 gần như là quyết định nhãn
587.521 bản ghi attack trong DoS đều có CAN ID `0000`; không có normal nào dùng ID này. Feature thô CAN ID sẽ gây rò rỉ nhãn trong mô hình DoS.

---

## 5. Điểm chưa thống nhất

| # | Mô tả | Nguồn |
|---|---|---|
| U1 | Schema W01-B2 có 15 cột; preprocess.py W02-B1 thực tế xuất 17 cột. Schema v2 chưa được chốt. | data_spec §3, D6 |
| U2 | Cách xử lý đoạn đuôi 891.068 dòng: giữ 1 bản hay loại hẳn chưa được mentor chốt (D3). | data_spec §9, D3 |
| U3 | Phần trước gap của 4 file CSV có trùng nhau hay không — chưa kiểm tra. | data_spec §7 |
| U4 | License HCRL khi có công ty SGOD tham gia chưa được mentor xác nhận bằng văn bản (D1). | data_spec §9, D1 |
| U5 | pytest không có trong venv hiện tại — ảnh hưởng khả năng chạy test suite. | Môi trường |
| U6 | Dataset chính và dự phòng chưa được mentor/nhóm trưởng chốt (D2). | data_spec §9, D2 |
| U7 | Trường phụ `000` trong normal TXT chưa xác định ý nghĩa (gọi là extra_field, không dùng làm feature). | data_spec §2 |

---

## 6. Quyết định cần reviewer xác nhận

| # | Nội dung | Mức độ ưu tiên |
|---|---|---|
| R1 | **D6 — Thêm `label_provenance` và `segment_id` vào schema v2**: preprocess.py đã ghi 17 cột trên thực tế; B2 cần đồng ý chính thức để schema_alignment_v1.md phản ánh đúng. | Cao — blocking schema v2 |
| R2 | **D3 — Cách xử lý đoạn đuôi 891.068 dòng**: cắt hay giữ 1 bản cần quyết định trước khi xây dựng train/test split. | Cao — blocking pipeline |
| R3 | **D1 — License HCRL**: cần mentor xác nhận bằng văn bản trước khi sử dụng dữ liệu trong context SGOD. | Cao — compliance |
| R4 | **pytest thiếu trong venv**: xác nhận có cần cài pytest để chạy test suite W02-B1 trong workspace này không. | Trung bình |
| R5 | **D5 — Cách chia client FL**: chưa có đề xuất cụ thể; ảnh hưởng preprocessing và cách tổ chức dataset. | Thấp (giai đoạn sau) |
