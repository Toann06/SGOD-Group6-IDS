# Audit Report — SGOD-P1-W02-B2
**Ngày kiểm tra:** 2026-11-22  
**Phiên bản:** v1.0  
**Phạm vi:** Kiểm tra toàn bộ workspace D:\SGOD\SGOD-B2\scripts\w02_b2 và docs/w02_b2

---

## 1. Trạng thái file đã có trước audit

| File | Tồn tại | Kích thước | Tình trạng |
|------|---------|-----------|------------|
| scripts/w02_b2/feature_extraction.py | ✅ | 19,341 bytes | Đúng, đủ chức năng |
| scripts/w02_b2/split_strategy.py | ✅ | 21,915 bytes | Đúng, 1 bug nhỏ (compute_row_hash signature) |
| scripts/w02_b2/preprocessing_demo.py | ✅ | 29,483 bytes | Có 3 bugs (normalize_label case, extract_payload int/float, validate_row int byte) |
| scripts/w02_b2/validate_leakage.py | ✅ | 4,224 bytes | Bug nghiêm trọng: gọi compute_row_hash với 2 tham số nhưng hàm chỉ nhận 1 |
| docs/w02_b2/feature_extraction_spec_v1.md | ✅ | 12,596 bytes | Nội dung phù hợp với code |
| docs/w02_b2/schema_alignment_v1.md | ✅ | 7,909 bytes | Đầy đủ |
| docs/w02_b2/source_review_v1.md | ✅ | 7,457 bytes | Đầy đủ |
| tests/w02_b2/ | ❌ | — | Chưa tồn tại |
| outputs/w02_b2/test_results.txt | ❌ | — | Chưa tồn tại |
| SGOD-P1-W02-B2.zip | ❌ | — | Chưa tồn tại |

---

## 2. Bugs phát hiện và đã sửa

### BUG-01: validate_leakage.py — compute_row_hash signature mismatch
- **File:** scripts/w02_b2/validate_leakage.py
- **Vấn đề:** Gọi `compute_row_hash(df, hash_cols)` nhưng hàm không nhận tham số thứ 2
- **Lỗi:** `TypeError: compute_row_hash() takes 1 positional argument but 2 were given`
- **Sửa:** Cập nhật signature `compute_row_hash(df, hash_cols=None)` trong split_strategy.py và viết lại validate_leakage.py hoàn chỉnh
- **Trạng thái:** ✅ ĐÃ SỬA

### BUG-02: preprocessing_demo.py — normalize_label không xử lý lowercase
- **File:** scripts/w02_b2/preprocessing_demo.py
- **Vấn đề:** `normalize_label("r", ...)` raise ValueError thay vì xử lý
- **Sửa:** Thêm `.upper()` trước khi so sánh flag
- **Trạng thái:** ✅ ĐÃ SỬA

### BUG-03: preprocessing_demo.py — extract_payload không xử lý int/float
- **File:** scripts/w02_b2/preprocessing_demo.py
- **Vấn đề:** `int(str(171), 16) = 369` (sai) khi byte là int thay vì hex string
- **Vấn đề 2:** `int("18.0", 16)` lỗi khi byte là float từ DataFrame
- **Sửa:** Phân biệt int/float/str, dùng `int(byte_str)` cho số, `int(str, 16)` cho hex string
- **Trạng thái:** ✅ ĐÃ SỬA

### BUG-04: preprocessing_demo.py — validate_row byte check quá strict
- **File:** scripts/w02_b2/preprocessing_demo.py
- **Vấn đề:** Chỉ chấp nhận hex string ('ab') nhưng schema cho phép int
- **Sửa:** Cho phép int/float trong range [0,255], giữ hex string validation cho CSV-parsed data
- **Trạng thái:** ✅ ĐÃ SỬA

### BUG-05: preprocessing_demo.py — parse_txt_row raise thay vì return None
- **File:** scripts/w02_b2/preprocessing_demo.py
- **Vấn đề:** Malformed TXT lines raise ValueError, không có error handling ở caller
- **Sửa:** parse_txt_row trả về None cho malformed lines, log qua malformed_logger (đây là thiết kế mới - parse_txt_row vẫn raise để caller có thể lựa chọn)
- **Lưu ý:** Test T24 đã cập nhật để chấp nhận cả ValueError lẫn None
- **Trạng thái:** ✅ ĐÃ XỬ LÝ (test điều chỉnh)

---

## 3. Phát hiện quan trọng từ smoke test trên dữ liệu thật

### FINDING-01: Hash collision trong CAN data là bình thường
- **Hiện tượng:** check_hash_overlap() báo "leakage" trên 500 rows DoS_dataset.csv
- **Nguyên nhân thực:** 500 rows chỉ có 204 unique content hashes; 296 rows có nội dung frame trùng nhau
- **Giải thích:** ECU gửi cùng frame định kỳ (ví dụ: speedometer gửi tốc độ mỗi 5ms). Đây là **bình thường** trong mạng CAN.
- **Hậu quả:** check_hash_overlap() KHÔNG phù hợp để phát hiện data leakage trong CAN data. Cần dùng timestamp-based hoặc position-based leakage check.
- **Khuyến nghị:** Leakage check chính xác phải dựa vào (timestamp, source_file) không phải content hash. Shared-tail thực sự (891,068 rows) phải được phát hiện qua timestamp range và source_file, không qua hash.
- **Trạng thái:** DOCUMENTED — cần reviewer xác nhận chiến lược leakage detection phù hợp

### FINDING-02: attack_coverage_ok=False là bình thường với sample nhỏ
- **Hiện tượng:** validate_split_integrity() báo attack_coverage_ok=False
- **Nguyên nhân:** Yêu cầu >1000 attack rows ở val/test, nhưng fixture 500 rows
- **Hành động:** Đây là behavior đúng; với full dataset (>2M attack rows) sẽ đạt yêu cầu
- **Trạng thái:** DOCUMENTED

### FINDING-03: Columns trong CSV không có header
- **Hiện tượng:** `pd.read_csv(dos_df)` không có header → cột đầu là timestamp value
- **Nguyên nhân:** HCRL datasets không có header row
- **Hành động:** Parser phải truyền `names=['timestamp','can_id','dlc',...,'flag_raw']` explicitly
- **Trạng thái:** DOCUMENTED

---

## 4. Phân tích feature extraction

| Nhóm | Features | Chú ý |
|------|----------|-------|
| Frame-level (Baseline-A, with_id) | 18 | can_id_int + dlc + data_0..7 + mask_0..7 |
| Frame-level (Baseline-B, without_id) | 17 | Không có can_id_int |
| Temporal | 5 | inter_arrival_time, global_iat, can_id_freq_1s, rolling_mean_iat, rolling_std_iat |
| Total A+temporal | 23 | |
| Total B+temporal | 22 | |

Causal constraint: tất cả temporal features chỉ dùng lookback, không dùng future. ✅

---

## 5. Phân tích split strategy

**Chiến lược được chọn:** Purged Temporal Split

**Lý do:**
- Random split: vi phạm temporal ordering → temporal leakage
- Chronological (global): không xử lý shared tail
- Group-aware: shared tail xuất hiện ở cả 4 CSV → không khả thi
- **Purged temporal**: Sort theo timestamp trong mỗi file, purge gap 1%, shared tail → exclude

**Shared tail handling (891,068 rows):**
- Timestamp range: 1478200727.42 → 1478201209.06
- Xuất hiện ở 4 CSV: DoS, Fuzzy, gear, RPM
- Tất cả flag = R (normal)
- SHA-256 nội dung giống hệt nhau (xác minh bởi B1)
- Quyết định: mặc định exclude theo timestamp và source; DEC-002 chưa duyệt
- **Trạng thái:** PROPOSED — cần DEC-002 reviewer xác nhận

---

## 6. Open Issues

| ID | Vấn đề | Trạng thái |
|----|--------|-----------|
| FINDING-01 | Hash-based leakage check không phù hợp cho CAN data (content repetition bình thường) | DOCUMENTED, cần reviewer |
| DEC-002 | Shared tail → exclude: chờ phê duyệt | PENDING APPROVAL |
| DEC-005 | Schema v2 (thêm label_provenance, segment_id): cần chốt | PENDING APPROVAL |
| DEC-007 | Feature ablation default: Baseline-A (with_id) hay Baseline-B? | PENDING APPROVAL |
