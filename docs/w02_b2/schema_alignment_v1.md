# Schema Alignment v1 — SGOD-P1-W02-B2

Ngày: 2026-11-22  
Thực hiện bởi: auditor (swarm SGOD-P1-W02-B2)  
Trạng thái: **Bản nháp — PENDING APPROVAL. Schema v2 CHƯA được chốt.**

> **Quan trọng:** Tài liệu này chỉ ghi nhận tình trạng thực tế và đề xuất tích hợp. Mọi mục có nhãn **[ĐỀ XUẤT]** hoặc **PENDING APPROVAL** chưa được bất kỳ reviewer hay mentor nào chốt chính thức.

---

## 1. Bảng đối chiếu schema

| # | Cột | Kiểu (W01-B2 schema_v1.md) | Có trong W01-B2 (15 cột) | Có trong W02-B1 output (17 cột) | Ghi chú |
|---|---|---|---|---|---|
| 1 | `timestamp` | string (decimal) | ✅ | ✅ | Giữ dạng chuỗi để so khớp chính xác, tránh sai số float |
| 2 | `can_id` | string (hex) | ✅ | ✅ | Lowercase hex trong W02-B1 (`can_id.lower()`) |
| 3 | `dlc` | integer | ✅ | ✅ | 0–8; {2, 5, 6, 8} trong dữ liệu thực |
| 4 | `data_0` | string (hex), nullable | ✅ | ✅ | Null/rỗng khi i ≥ DLC |
| 5 | `data_1` | string (hex), nullable | ✅ | ✅ | |
| 6 | `data_2` | string (hex), nullable | ✅ | ✅ | |
| 7 | `data_3` | string (hex), nullable | ✅ | ✅ | |
| 8 | `data_4` | string (hex), nullable | ✅ | ✅ | |
| 9 | `data_5` | string (hex), nullable | ✅ | ✅ | |
| 10 | `data_6` | string (hex), nullable | ✅ | ✅ | |
| 11 | `data_7` | string (hex), nullable | ✅ | ✅ | |
| 12 | `flag_raw` | string, nullable | ✅ | ✅ | `""` (rỗng) thay vì `null` trong CSV của W02-B1 |
| 13 | `label` | integer | ✅ | ✅ | 0=normal, 1=attack |
| 14 | `attack_type` | string | ✅ | ✅ | normal/dos/fuzzy/gear/rpm |
| 15 | `source_file` | string | ✅ | ✅ | Tên file nguồn |
| 16 | `source_line` | integer | ✅ | ✅ | Số dòng trong file nguồn |
| 17 | `label_provenance` | string | ❌ (không có) | ✅ **[ĐỀ XUẤT]** | `observed_flag` hoặc `inferred_from_source`; **D6 chưa chốt** |
| 18 | `segment_id` | integer | ❌ (không có) | ✅ **[ĐỀ XUẤT]** | 0,1,… tăng sau mỗi gap >1s; **D6 chưa chốt** |

**Nguồn W01-B2:** `D:\SGOD\SGOD-B2\SGOD-P1-W01-B2\docs\schema_v1.md` (15 cột, trang thái chờ reviewer)  
**Nguồn W02-B1 output thực tế:** `preprocess.py` COLUMNS list và `preprocess_summary.json` (cả fixture lẫn real run đều ghi 17 cột)

---

## 2. Điểm khác biệt chi tiết

### 2.1 Điểm đồng thuận (tương thích hoàn toàn)
- 15 cột cốt lõi từ W01-B2 được W02-B1 kế thừa không thay đổi về tên và ý nghĩa.
- Quy tắc parse DLC-dependent (data_i = null khi i ≥ dlc) khớp giữa hai phía.
- Label mapping R→0, T→1, normal TXT→0 khớp nhau.
- `flag_raw = null` cho normal TXT được W02-B1 giữ (ghi rỗng trong CSV).

### 2.2 Điểm khác biệt nhỏ cần lưu ý
| Khía cạnh | W01-B2 (schema_v1.md) | W02-B1 (preprocess.py) | Rủi ro |
|---|---|---|---|
| `can_id` case | "chuỗi hex" (không chỉ định case) | lowercase (`.lower()` trong can_parser.py) | Thấp — W01 mô tả, W02 thực thi lowercase |
| `flag_raw` null | "null" khi normal TXT | `""` (rỗng) trong CSV output | Thấp — phụ thuộc cách đọc downstream; cần nhất quán |
| `data_i` null | "null" khi i≥dlc | `""` (rỗng) trong CSV output | Thấp — tương tự flag_raw |
| Trường phụ normal TXT | Không đề cập | `extra_field` trong Record.extra dict (không ghi vào CSV chính) | Không có rủi ro — extra không xuất ra schema |

---

## 3. Đánh giá tác động 2 trường mới **[ĐỀ XUẤT]**

### 3.1 `label_provenance` (string)
- **Mục đích:** Phân biệt nhãn quan sát (Flag R/T từ CSV) khỏi nhãn suy ra (normal TXT).
- **Giá trị:** `observed_flag` cho 4 file CSV (16.569.475 bản ghi), `inferred_from_source` cho normal TXT (988.871 bản ghi).
- **Tác động tích cực:** Cho phép thống kê và đánh giá tách nhóm nhãn suy ra — yêu cầu bắt buộc theo data_specification §5 và eda_report §1.
- **Tác động tiêu cực/rủi ro:** Cột mới làm pipeline đọc schema cũ sẽ thiếu cột này; cần cập nhật validator W01-B2.
- **Trạng thái:** **[ĐỀ XUẤT]** — D6 chờ B2 đồng ý. preprocess.py đã ghi thực tế nhưng không có nghĩa đã chốt.

### 3.2 `segment_id` (integer)
- **Mục đích:** Đánh dấu khoảng gap timestamp > 1 giây trong từng file, không cắt dữ liệu.
- **Giá trị:** 0 = trước gap (đoạn chính với attack), 1 = sau gap (đoạn đuôi 891.068 dòng ở 4 file CSV).
- **Tác động tích cực:** Cho phép quyết định D3 (cách xử lý đoạn đuôi) được thực hiện sau mà không phải chạy lại parse. Giá trị `segment_id = 1` xác định chính xác đoạn đuôi trùng.
- **Tác động tiêu cực/rủi ro:** Không tự động loại đoạn đuôi — cần logic downstream đọc và lọc. Pipeline chưa có logic này.
- **Trạng thái:** **[ĐỀ XUẤT]** — D6/D3 chờ mentor chốt. Quyết định D3 (giữ 1 bản hay loại) chưa có.

---

## 4. Đề xuất schema tích hợp **[PENDING APPROVAL]**

> **CẢNH BÁO:** Đây là ĐỀ XUẤT để reviewer thảo luận. Schema v2 **CHƯA được chốt**. Không triển khai pipeline dựa trên schema này trước khi có quyết định chính thức.

Nếu D6 được phê duyệt, schema tích hợp đề xuất là **17 cột** như sau:

```
timestamp, can_id, dlc,
data_0, data_1, data_2, data_3, data_4, data_5, data_6, data_7,
flag_raw, label, attack_type, source_file, source_line,
label_provenance, segment_id
```

Thứ tự cột: giữ nguyên 15 cột W01-B2, nối thêm 2 cột mới ở cuối để tương thích ngược.

**Quy tắc bổ sung đề xuất:**
- `label_provenance`: NOT NULL; giá trị cho phép: `{"observed_flag", "inferred_from_source"}`.
- `segment_id`: NOT NULL; integer ≥ 0; chỉ có ý nghĩa khi kết hợp với `source_file`.
- `flag_raw`: ghi `""` trong CSV khi null (không ghi `null` literal) — nhất quán với W02-B1.
- `can_id`: lowercase hex, không có prefix `0x`.
- `data_i`: ghi `""` trong CSV khi null (i ≥ dlc).

---

## 5. PENDING APPROVAL

| # | Nội dung | Người cần quyết định | Trạng thái |
|---|---|---|---|
| PA-1 | **D6**: Thêm `label_provenance` và `segment_id` vào schema chính thức (schema v2) | B2 (W02), Mentor | ⏳ Chưa chốt |
| PA-2 | **D3**: Cách xử lý đoạn đuôi 891.068 dòng: giữ 1 bản hay loại hẳn | Mentor, nhóm B | ⏳ Chưa chốt |
| PA-3 | `flag_raw` null: ghi `""` hay `null` literal trong CSV? Chọn một chuẩn thống nhất | B2, C | ⏳ Chưa thống nhất |
| PA-4 | `data_i` null: ghi `""` hay `null` literal? Cùng quyết định với PA-3 | B2, C | ⏳ Chưa thống nhất |
| PA-5 | **D1**: License HCRL — mentor xác nhận bằng văn bản | Mentor | ⏳ Chưa có |
| PA-6 | Schema v2 khi chốt cần version tag, ngày tháng, và reviewer ký off | Reviewer, Mentor | ⏳ Chưa thực hiện |

---

## 6. Bằng chứng thực tế

| Khẳng định | Bằng chứng (file + dòng) |
|---|---|
| W01-B2 có đúng 15 cột | `schema_v1.md` §3 bảng cột 1–16 (timestamp đến source_line) |
| W02-B1 output có 17 cột | `preprocess.py` dòng 24–25: `COLUMNS = ["timestamp", ..., "label_provenance", "segment_id"]` |
| preprocess_summary.json (real) liệt kê 17 cột | `preprocess_real/preprocess_summary.json` key `"columns"` (18 phần tử: 17 cột) |
| `segment_id=1` = đoạn đuôi | `data_specification_v0.2.md` §3: "[ĐO] trong 4 file CSV, `segment_id = 1` chính là đoạn đuôi dùng chung ở phần 7" |
| label_provenance vẫn là ĐỀ XUẤT | `data_specification_v0.2.md` §9 D6: "Thêm cột `label_provenance` và `segment_id` vào schema v2 | B2 | Thêm cả hai" |
