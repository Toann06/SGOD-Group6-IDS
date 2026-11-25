# Tài liệu Bàn giao Kỹ thuật — Task SGOD-P1-W02-B2

**Nhiệm vụ:** SGOD-P1-W02-B2 — "Chốt feature extraction, chiến lược split train/val/test chống data leakage; mô tả preprocessing."  
**Dự án:** Xây dựng hệ thống phát hiện xâm nhập bằng học liên kết và kiểm chứng tính toàn vẹn dữ liệu bằng Blockchain trong mạng điều khiển phân tán.  
**Giai đoạn:** Phase 1 / Tuần 2 (23–29/11/2026).  
**Hạn chót:** 29/11/2026.  
**Workspace:** `D:\SGOD\SGOD-B2`  
**Trạng thái:** HOÀN TẤT THỰC THI & KIỂM THỬ NỘI BỘ (Chờ Reviewer nghiệm thu)

---

## 1. Cấu trúc Gói Bàn giao (Delivery Package Structure)

```
D:\SGOD\SGOD-B2\
├── README_W02_B2.md                        # Hướng dẫn tổng quan bàn giao ở cấp root
├── requirements_w02_b2.txt                 # Danh mục thư viện Python bắt buộc
├── docs\w02_b2\                            # Tài liệu đặc tả kỹ thuật & báo cáo
│   ├── audit_report.md                     # Báo cáo audit trạng thái đầu vào
│   ├── feature_extraction_spec_v1.md       # Đặc tả 23 đặc trưng (18 khung + 5 thời gian)
│   ├── leakage_audit.md                    # Báo cáo chuyên sâu về chống Data Leakage
│   ├── preprocessing_spec_v1.md            # Đặc tả quy trình tiền xử lý chuẩn hóa
│   ├── schema_alignment_v1.md              # Đối sánh schema W01-B2 và định dạng HCRL
│   ├── source_review_v1.md                 # Đánh giá 5 file dữ liệu CAN gốc
│   ├── split_strategy_spec_v1.md           # Đặc tả chiến lược Purged Temporal Split
│   ├── test_report.md                      # Báo cáo 71 unit & regression tests
│   └── handoff_README.md                   # Tài liệu bàn giao chi tiết này
├── scripts\w02_b2\                         # Mã nguồn Python thực thi chuẩn
│   ├── can_parser.py                       # Parser đọc CSV & TXT tối ưu (C engine)
│   ├── feature_extraction.py               # Trích xuất 23 features, kiểm tra rò rỉ nhãn
│   ├── split_strategy.py                   # Phân hoạch dữ liệu có purge gap & cô lập đuôi
│   ├── validate_leakage.py                 # Validator kiểm tra 6 chiều rò rỉ dữ liệu
│   ├── preprocessing_demo.py               # Pipeline demo: validate, fit, transform
│   ├── smoke_test_real_data.py             # Script chạy smoke test dữ liệu thật
│   ├── verify_shared_tail_full.py          # Script xác minh 891.068 dòng trùng lặp
│   ├── check_shared_tail_split.py          # Chẩn đoán phân bổ shared-tail trong split
│   ├── diagnose_split.py                   # Chẩn đoán chi tiết phân bố nhãn & hash
│   └── audit_split.py                      # Sinh split_audit.json
├── tests\w02_b2\                           # Bộ kiểm thử tự động (Pytest)
│   ├── conftest.py                         # Fixtures dữ liệu CAN và shared-tail
│   ├── test_w02_b2.py                      # 49 tests cơ sở (T01 đến T24)
│   └── test_regression_and_fixes.py        # 17 regression tests cho các lỗi đã fix
└── outputs\w02_b2\                         # Bằng chứng thực nghiệm & logs
    ├── test_results.txt                    # Log chạy 71/71 pytest tests (PASS 100%)
    ├── real_data_smoke_test.json           # Kết quả smoke test trên 50k dòng DoS
    ├── multi_csv_streaming_audit.json      # Audit streaming 50k rows/CSV trên 4 dataset
    ├── shared_tail_full_verification.json  # Bằng chứng SHA-256 của 891.068 dòng đuôi
    ├── split_audit.json                    # Báo cáo chi tiết phân hoạch & overlap
    └── validation_summary.json             # Bản tóm tắt kiểm định dạng JSON
```

---

## 2. Hướng dẫn Môi trường & Chạy Kiểm thử

### 2.1. Thiết lập Môi trường
```powershell
cd D:\SGOD\SGOD-B2
# Kích hoạt virtual environment hiện có
.venv\Scripts\Activate.ps1

# Cài đặt / kiểm tra thư viện nếu cần
pip install -r requirements_w02_b2.txt
```

### 2.2. Biên dịch Kiểm tra Cú pháp
```powershell
python -m compileall -q scripts
# Kỳ vọng: ExitCode = 0 (không có lỗi cú pháp)
```

### 2.3. Chạy Toàn bộ 71 Tests
```powershell
python -m pytest tests\w02_b2 -v -rs
# Kỳ vọng: 71 passed, 0 failed, 0 skipped
```

### 2.4. Tái hiện Smoke Test Dữ liệu Thật
```powershell
python scripts\w02_b2\smoke_test_real_data.py
# Kết quả ghi nhận tại: outputs\w02_b2\real_data_smoke_test.json (status: PASS)
```

### 2.5. Kiểm tra Đoạn Đuôi Trùng lặp (Shared-Tail Diagnostic)
```powershell
python -m scripts.w02_b2.check_shared_tail_split
# Xác nhận: Train max timestamp > Test min timestamp: False
```

### 2.6. Chạy Streaming Audit Đa Tập Dữ liệu
```powershell
python -m scripts.w02_b2.audit_multi_csv_streaming
# Kết quả lưu tại: outputs\w02_b2\multi_csv_streaming_audit.json
```

---

## 3. Các Vấn đề Kỹ thuật Đã Xử lý Triệt để

1. **Khắc phục lỗi đảo ngược thứ tự thời gian (`Train max timestamp > Test min timestamp`):**
   - *Nguyên nhân:* Đoạn shared-tail 891.068 dòng ở cuối file CSV bị gán cứng vào Train trong khi Val và Test nằm ở khoảng thời gian trước đó.
   - *Khắc phục:* Bổ sung `shared_tail_policy="exclude"` (mặc định) đưa các dòng này vào `excluded_shared_tail`, khôi phục thứ tự thời gian nghiêm ngặt `train < val < test`.

2. **Xử lý hiện tượng trùng Hash Payload CAN:**
   - *Nguyên nhân:* Trong giao thức CAN, ECU phát quảng bá tuần hoàn (periodic heartbeat/telemetry) cùng một nội dung khi trạng thái xe không đổi.
   - *Khắc phục:* Phân biệt rành mạch giữa **Observation Identity Overlap** (trùng dòng dữ liệu vật lý `(source_file, source_line)` - rò rỉ nguy hiểm) và **Content Hash Overlap** (trùng nội dung payload tuần hoàn - hiện tượng bình thường).

3. **Chống rò rỉ ranh giới cửa sổ trượt (Rolling Window Breach):**
   - *Khắc phục:* Thiết lập purge gap 1% giữa các split; đồng thời trong `feature_extraction.py`, phân đoạn gom nhóm kết hợp `source_file`, `split`, `segment_id` và gap > 1 giây, reset toàn bộ lịch sử IAT về `NaN` tại điểm chuyển tiếp split.

4. **Trích xuất đúng vị trí cờ và byte HCRL CSV:**
   - *Khắc phục:* Xử lý định dạng CSV không tiêu đề, vị trí cờ biến thiên tại cột `3 + DLC`, tránh hiện tượng lấy dòng dữ liệu đầu tiên làm tiêu đề cột.

---

## 4. Các Quyết định Kỹ thuật Cần Mentor / Reviewer Phê duyệt

| Mã | Tên Quyết định | Đề xuất của Nhóm Kỹ thuật | Lý do & Căn cứ |
| :---: | :--- | :--- | :--- |
| **DEC-002** | Xử lý Shared-Tail (891.068 dòng) | **Chuyển sang `exclude` (loại khỏi train/val/test chính)** thay vì gán vào train | Tránh lỗi đảo ngược thời gian và tránh nhân bản 3.56 triệu dòng trùng lặp khi huấn luyện FL |
| **DEC-003** | Bài toán Phân loại | **Hỗ trợ song song Binary (R/T) và Multiclass (5 lớp)** | Đáp ứng linh hoạt cả bài toán phát hiện dị thường nhị phân và nhận diện dạng tấn công |
| **DEC-004** | Phân bổ Dữ liệu Client FL | **1 CSV = 1 Client cục bộ** (có cô lập shared-tail) | Mô phỏng sát thực tế mạng phân tán (mỗi xe hoặc mỗi gateway điều khiển) |
| **DEC-005** | Bổ sung Cột Schema v2 | **Thêm `label_provenance` ('observed'/'inferred') và `segment_id`** | Minh bạch nguồn gốc nhãn giữa file CSV gắn nhãn thật và TXT suy diễn |
| **DEC-007** | Cấu hình Đặc trưng Chuẩn | **Baseline-A (23 đặc trưng, bao gồm `can_id_int`)** làm mặc định | Tối ưu hóa độ chính xác nhận diện ECU nguồn; kèm Baseline-B để đánh giá ablation |
| **DEC-008** | Tỷ lệ Phân hoạch | **70% Train, 15% Val, 15% Test** kèm **1% Purge Gap** | Tỷ lệ chuẩn công nghiệp cho dữ liệu chuỗi thời gian lớn |
| **DEC-009** | Cửa sổ Đặc trưng Thời gian | **`IAT_WINDOW = 10` frames** và **`FREQ_WINDOW_S = 1.0` giây** | Phù hợp chu kỳ bus 10-100Hz của các ECU trên ô tô |

---

## 5. Giới hạn Nghiệm thu (Known Limitations)

- **Phạm vi kiểm thử dữ liệu:** Kiểm thử tự động trên bộ test fixture tổng hợp (71 tests) và streaming audit trên 50.000 dòng mỗi CSV (tổng ~200.000 dòng thực, ngoài shared-tail). Phương pháp streaming đảm bảo an toàn bộ nhớ; không tải toàn bộ 17.55 triệu dòng vào RAM.
- **Attack coverage trong test set đã xác minh:** Với 50.000 dòng mỗi CSV, test set chứa từ 1.488 đến 1.889 mẫu tấn công (DoS: 1.889, Fuzzy: 1.488, Gear: 1.557, RPM: 1.665), đạt ngưỡng test của audit mẫu; chưa chứng minh tính đại diện toàn bộ.
- **Trạng thái bàn giao:** Bàn giao có điều kiện chờ Reviewer chính thức phê duyệt các quyết định kiến trúc nêu trên (DEC-002/003/004/005/007/008/009).
