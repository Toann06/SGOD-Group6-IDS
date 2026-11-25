# Báo cáo Kiểm thử Toàn diện Hệ thống Tiền xử lý & Chống Data Leakage (SGOD-P1-W02-B2)

**Workspace:** `D:\SGOD\SGOD-B2`  
**Giai đoạn:** Phase 1 / Tuần 2 (W02) — Task B2  
**Môi trường thực thi:**
- Hệ điều hành: Windows 11
- Python: 3.10.11 (virtual environment: `.venv`)
- Thư viện cốt lõi: Pandas 2.3.3, NumPy 2.2.6, Pytest 9.2.0, Scikit-learn 1.7.2, SciPy 1.15.3, Joblib 1.6.0
**Ngày kiểm thử:** 24/11/2026  
**Lệnh thực thi chính:**
- `python -m compileall -q scripts` (ExitCode = 0)
- `python -m pytest tests\w02_b2 -v -rs`
- Log lưu tại: `outputs/w02_b2/test_results.txt`

---

## 1. Kết quả Tổng quan (Test Suite Summary)

```
============================= test session starts =============================
platform win32 -- Python 3.10.11, pytest-9.2.0, pluggy-1.7.0
rootdir: D:\SGOD\SGOD-B2
collected 71 items

============================= 71 passed in 1.87s ==============================
```

- **Tổng số test cases:** 71
- **Số lượng PASSED:** 71 (100%)
- **Số lượng FAILED:** 0 (0%)
- **Số lượng SKIPPED:** 0 (0%)

---

## 2. Chi tiết Từng Nhóm Kiểm thử (Test Breakdown)

### A. Bộ Kiểm thử Cơ sở (Baseline Suite — `tests/w02_b2/test_w02_b2.py`, 49 tests)

| Mã | Nhóm Kiểm thử | Số Test | Trạng thái | Nội dung kiểm tra |
| :---: | :--- | :---: | :---: | :--- |
| **T01** | `TestT01SchemaValidation` | 3 | PASS | Xác thực schema 15 cột W01-B2, bắt lỗi thiếu timestamp/can_id |
| **T02** | `TestT02LabelMappingR` | 2 | PASS | Cờ 'R' chuẩn hóa thành label 0, không phân biệt hoa thường |
| **T03** | `TestT03LabelMappingT` | 2 | PASS | Cờ 'T' chuẩn hóa thành label 1, không phân biệt hoa thường |
| **T04** | `TestT04NormalProvenance` | 2 | PASS | Dữ liệu TXT có label_provenance='inferred' và label=0 |
| **T05** | `TestT05DLC2Payload` | 3 | PASS | DLC=2: mask [1,1,0,0,0,0,0,0], byte ngoài cửa sổ gán về 0 |
| **T06** | `TestT06DLC5Payload` | 1 | PASS | DLC=5: mask_0..4 = 1, mask_5..7 = 0 |
| **T07** | `TestT07DLC6Payload` | 1 | PASS | DLC=6: mask_0..5 = 1, mask_6..7 = 0 |
| **T08** | `TestT08DLC8Payload` | 2 | PASS | DLC=8: toàn bộ mask = 1, giá trị 0x00 là payload thực |
| **T09** | `TestT09InvalidDLC` | 2 | PASS | Từ chối DLC < 0 hoặc DLC > 8 |
| **T10** | `TestT10InvalidPayload` | 1 | PASS | Từ chối byte > 255 hoặc chuỗi hex không hợp lệ |
| **T11** | `TestT11MissingBytesPerDLC`| 2 | PASS | Xử lý khuyết byte theo DLC, zero-fill an toàn ngoài cửa sổ |
| **T12** | `TestT12TimestampOrdering` | 2 | PASS | Kiểm tra thứ tự thời gian tăng đơn điệu, global_iat >= 0 |
| **T13** | `TestT13SegmentBoundary` | 1 | PASS | Reset IAT về NaN tại ranh giới chuyển file/segment |
| **T14** | `TestT14DuplicateFrameDetection` | 3 | PASS | Tính hash SHA-256 nhất quán, phát hiện trùng lặp bản ghi |
| **T15** | `TestT15SharedTailLeakage` | 2 | PASS | Phát hiện leakage khi cố tình đưa bản ghi trùng vào cả train & test |
| **T16** | `TestT16GroupOverlap` | 1 | PASS | Phát hiện leakage khi trùng lặp source giữa train và val |
| **T17** | `TestT17ScalerTrainOnly` | 2 | PASS | Xác minh PreprocessingPipeline và StandardScaler chỉ fit trên train |
| **T18** | `TestT18LabelExclusion` | 3 | PASS | Loại trừ tuyệt đối cột label, flag_raw khỏi ma trận feature |
| **T19** | `TestT19MetadataExclusion` | 3 | PASS | Loại trừ source_file, source_line, label_provenance khỏi feature |
| **T20** | `TestT20WindowBoundary` | 2 | PASS | Kiểm tra cửa sổ trượt không vượt ranh giới split khi có purge gap |
| **T21** | `TestT21DeterministicSplit`| 1 | PASS | Cùng seed=42 tạo ra phân hoạch train/val/test hoàn toàn giống nhau |
| **T22** | `TestT22FixedSeedReproducibility`| 2 | PASS | Tính tất định của hash và sự khác biệt khi thay đổi seed |
| **T23** | `TestT23EmptySingleClassSplit` | 2 | PASS | Xử lý an toàn dữ liệu nhỏ (3 dòng) hoặc 1 lớp duy nhất |
| **T24** | `TestT24ParserCompatibility` | 4 | PASS | Parser tương thích schema W01-B2, xử lý biến thiên cột theo DLC |

---

### B. Bộ Kiểm thử Chống Hồi quy & Khắc phục Lỗi (Regression Suite — `tests/w02_b2/test_regression_and_fixes.py`, 17 tests)

| Mã | Nhóm Kiểm thử | Số Test | Trạng thái | Mục tiêu kiểm chứng |
| :---: | :--- | :---: | :---: | :--- |
| **R01** | `TestSharedTailIsolation` | 4 | PASS | Cô lập 891.068 dòng shared-tail vào `excluded_shared_tail`, ngăn chặn rò rỉ vào val/test và hỗ trợ các policy `exclude`, `isolate`, `train` |
| **R02** | `TestChronologicalOrdering` | 3 | PASS | Đảm bảo `Train max timestamp < Test min timestamp` (khắc phục hoàn toàn lỗi đảo ngược thời gian trước đó); phát hiện future lookahead |
| **R03** | `TestCanPayloadRepetitionVsTrueLeakage` | 4 | PASS | Phân định rõ trùng hash CAN tuần hoàn với trùng thực thể `(source_file, source_line)`; phát hiện trùng quan sát chứa NaN (DLC < 8); kiểm chứng trạng thái `PASS` và `PASS_PARTIAL` |
| **R04** | `TestFeatureExtractionSplitBoundary` | 3 | PASS | Reset trạng thái lịch sử (`global_iat`, `rolling_mean_iat`) tại ranh giới split; phát hiện vi phạm cửa sổ khi thiếu purge gap |
| **R05** | `TestEdgeCasesAndSafety` | 3 | PASS | Xử lý dữ liệu rỗng trả về trạng thái `NOT_VERIFIED` thay vì báo PASS ảo; kiểm tra timestamp trùng lặp; báo cáo đầy đủ metadata |

---

### C. Bổ sung B1 (5 tests)

`test_b1_gap.py`: reset temporal khi gap; reset frequency theo segment; scaler loại IAT xuyên gap; reset source/split; loại segment metadata khỏi features. 5/5 PASS.

## 3. Kết quả Kiểm định trên Dữ liệu Thật (Real Data Verification)

### 3.1. Phân loại Trạng thái Kiểm định Rò rỉ (Granular Status Definition)
Nhằm đảm bảo tính trung thực kỹ thuật và không che giấu các kiểm tra chưa được thực hiện, hàm `run_full_leakage_check()` áp dụng 4 cấp độ trạng thái rõ ràng:
- **`PASS`**: Mọi kiểm tra (observation identity, temporal order, label exclusion, window boundary, scaler fit) đều được xác minh đầy đủ và không phát hiện bất kỳ dấu hiệu rò rỉ nào.
- **`PASS_PARTIAL`**: Các kiểm tra cốt lõi (observation identity, temporal order, label exclusion) đã PASS, nhưng kiểm tra phụ (như `window_boundary_leakage` khi không truyền `combined_df`, hoặc `scaler_fitted_on_train_only` khi không truyền `scaler`) mang trạng thái `NOT_VERIFIED`.
- **`FAIL`**: Phát hiện vi phạm rò rỉ thực tế (như trùng lặp dòng quan sát giữa các split, đảo ngược thời gian train/test, hoặc rò rỉ nhãn vào ma trận đặc trưng).
- **`NOT_VERIFIED`**: Dữ liệu rỗng hoặc không đủ ngữ cảnh để tiến hành kiểm tra.

### 3.2. Smoke Test Mở rộng trên DoS Dataset (50.000 dòng)
- **Thực hiện bởi:** `scripts/w02_b2/smoke_test_real_data.py`
- **Output lưu tại:** `outputs/w02_b2/real_data_smoke_test.json`
- **Quy mô mẫu:** 50.000 dòng đầu tiên của `DoS_dataset.csv`.
- **Phân bổ split:**
  - Tập Train: 32.794 dòng (Normal: 24.796, Attack: 7.998)
  - Purge Gap Train/Val: 466 dòng (bảo vệ cửa sổ trượt)
  - Tập Val: 7.725 dòng (Normal: 6.455, Attack: 1.270)
  - Tập Test: 9.015 dòng (Normal: 7.126, **Attack: 1.889**)
- **Đánh giá mật độ tấn công:** Tập test có **1.889 mẫu tấn công** (tỷ lệ 20.95%), xóa bỏ hoàn toàn hiện tượng thiếu mẫu tấn công từng xuất hiện khi cắt lát quá nhỏ (10.000 dòng chỉ có 3 mẫu tấn công).
- **Trạng thái rò rỉ:** `status: PASS`, `passed: True`, 0 observation identity overlap, window boundary sạch, scaler chỉ fit trên train.

### 3.3. Kiểm thử Streaming Đa Tập Dữ liệu (Multi-CSV Streaming Audit)
- **Thực hiện bởi:** `scripts/w02_b2/audit_multi_csv_streaming.py`
- **Output lưu tại:** `outputs/w02_b2/multi_csv_streaming_audit.json`
- **Phương pháp tiếp cận:** Streaming đọc 50.000 dòng từ từng file CSV trước khoảng shared-tail (tránh nạp toàn bộ 17.55 triệu dòng vào RAM gây tràn bộ nhớ), kết hợp phân tích 100 dòng TXT.
- **Kết quả chi tiết:**

| Tập dữ liệu | Train Rows (Attacks) | Val Rows (Attacks) | Test Rows (Attacks) | Tỷ lệ Attack Test | Temporal Order | Window Leakage | Scaler Leakage | Leakage Status |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **DoS** | 32.794 (7.998) | 7.725 (1.270) | 9.015 (**1.889**) | 20.95% | PASS (Strict) | PASS | PASS | **PASS** |
| **Fuzzy** | 31.783 (3.457) | 8.540 (1.011) | 9.361 (**1.488**) | 15.90% | PASS (Strict) | PASS | PASS | **PASS** |
| **Gear** | 34.571 (6.764) | 7.017 (683) | 7.480 (**1.557**) | 20.82% | PASS (Strict) | PASS | PASS | **PASS** |
| **RPM** | 35.024 (7.080) | 6.878 (547) | 7.202 (**1.665**) | 23.12% | PASS (Strict) | PASS | PASS | **PASS** |

- **Kiểm tra trùng lặp quan sát xuyên file (Cross-file Observation Overlap):**
  - Đã đối chiếu toàn bộ các cặp file: DoS vs Fuzzy, DoS vs Gear, DoS vs RPM, Fuzzy vs Gear, Fuzzy vs RPM, Gear vs RPM.
  - Sử dụng thuật toán chuẩn hóa `.fillna("__NAN__")` để bảo đảm các frame có DLC < 8 (chứa NaN ở các byte đuôi) vẫn được so sánh chính xác.
  - **Kết quả:** `cross_file_observation_overlap = False` (0 bản ghi trùng lặp trước đoạn shared-tail).
- **Kết luận về số lượng mẫu tấn công:** Cả 4 tập test đều có **trên 1.400 mẫu tấn công thực tế**, đạt ngưỡng test của audit mẫu; Gear/RPM val chỉ có 683/547 attack, chưa xác minh tính đại diện toàn bộ.

---

## 4. Trạng thái Quyết định Kỹ thuật (Architecture Decision Records)

Các quyết định kiến trúc quan trọng tiếp tục được duy trì ở trạng thái chờ Reviewer phê duyệt:
- **DEC-002: PENDING REVIEWER APPROVAL** — Đề xuất mặc định `shared_tail_policy="exclude"` để bảo toàn thứ tự thời gian và tránh trùng lặp 3.56 triệu dòng trong FL.
- **DEC-005: PENDING REVIEWER APPROVAL** — Bổ sung `segment_id` và cột `label_provenance` ('observed' cho CSV, 'inferred' cho TXT) vào Schema v2.
- **DEC-007: PENDING REVIEWER APPROVAL** — Lựa chọn cấu hình Baseline-A (23 đặc trưng, bao gồm `can_id_int`) làm cấu hình mặc định, Baseline-B (22 đặc trưng, loại bỏ `can_id_int`) làm cấu hình phụ.

---

## 5. Kết luận Đảm bảo Chất lượng (QA Sign-off)

- Toàn bộ 71 unit tests và regression tests đạt 100% tỷ lệ PASS.
- Mọi kết luận kỹ thuật đều có bằng chứng số liệu và log đối chiếu cụ thể.
- Hệ thống sẵn sàng cho công tác đóng gói và nghiệm thu kỹ thuật.
