# SGOD-P1-W02-B2 Delivery Package

**Task Title:** SGOD-P1-W02-B2 — Chốt feature extraction, chiến lược split train/validation/test chống data leakage; mô tả preprocessing.  
**Project:** Xây dựng hệ thống phát hiện xâm nhập bằng học liên kết và kiểm chứng tính toàn vẹn dữ liệu bằng Blockchain trong mạng điều khiển phân tán.  
**Deadline:** 29/11/2026.  
**Workspace:** `D:\SGOD\SGOD-B2`  

---

## 1. Tổng quan Gói Bàn giao

Gói bàn giao cung cấp giải pháp toàn diện và đã được kiểm chứng cho pipeline dữ liệu CAN Bus từ bộ dữ liệu HCRL Car-Hacking Dataset:

1. **Trích xuất Đặc trưng (Feature Extraction):**
   - **Baseline-A (Mặc định):** 23 đặc trưng (18 đặc trưng khung có CAN ID + 5 đặc trưng thời gian).
   - **Baseline-B (Ablation):** 22 đặc trưng (17 đặc trưng khung không có CAN ID + 5 đặc trưng thời gian).
   - Đảm bảo 100% không rò rỉ nhãn (`label`, `flag_raw`, `attack_type`).

2. **Chiến lược Phân hoạch Dữ liệu (Purged Temporal Split):**
   - Thứ tự thời gian nghiêm ngặt theo từng source: `Train <= Val <= Test`.
   - Purge Gap 1% tại các ranh giới để ngăn ngừa rò rỉ cửa sổ trượt.
   - Cơ chế xử lý **Shared-Tail 891.068 dòng**: cấu hình mặc định `shared_tail_policy="exclude"`, loại bỏ hoàn toàn lỗi đảo ngược thời gian (`Train max timestamp > Test min timestamp: False`) và tránh nhân bản 3.56 triệu dòng trùng lặp trong Federated Learning.

3. **Xác thực Chống Rò rỉ Dữ liệu (Leakage Validation):**
   - Phân biệt rõ ràng giữa **Observation Identity Overlap** (trùng thực thể quan sát: 0 dòng) và **CAN Content Hash Overlap** (trùng nội dung payload do chu kỳ broadcast của ECU: bình thường).
   - Trạng thái chi tiết: `PASS` / `PASS_PARTIAL` / `FAIL` / `NOT_VERIFIED`.
   - Reset trạng thái lịch sử tính toán thời gian tại ranh giới nguồn và ranh giới split.
   - Scaler chỉ được fit trên tập Train.

4. **Bộ Kiểm thử Tự động:**
   - **71 bài kiểm thử** với Pytest (49 bài cơ sở T01–T24 + 17 bài hồi quy R01–R05 + 5 bài kiểm thử gap), đạt tỷ lệ thành công **100% (71 PASS, 0 FAIL, 0 SKIP)**.

5. **Streaming Audit Đa Tập Dữ liệu:**
   - Đã streaming audit 50.000 dòng/CSV từ cả 4 dataset, không tải toàn bộ dữ liệu vào RAM.
   - Tất cả 4 dataset đạt `leakage_status: PASS`.
   - Test set có từ 1.488 đến 1.889 mẫu tấn công (đủ cho đánh giá thống kê).

---

## 2. Hướng dẫn Chạy Nhanh

```powershell
# 1. Kích hoạt môi trường ảo
.venv\Scripts\Activate.ps1

# 2. Kiểm tra biên dịch cú pháp
python -m compileall -q scripts

# 3. Chạy toàn bộ 71 tests
python -m pytest tests\w02_b2 -v -rs

# 4. Chạy smoke test trên dữ liệu thật (50k rows DoS)
python scripts\w02_b2\smoke_test_real_data.py

# 5. Chạy streaming audit đa CSV
python -m scripts.w02_b2.audit_multi_csv_streaming

# 6. Chạy kiểm tra chẩn đoán shared-tail
python -m scripts.w02_b2.check_shared_tail_split
```

---

## 3. Danh mục Tài liệu & Mã nguồn Chính

- Tài liệu bàn giao chi tiết: [handoff_README.md](docs/w02_b2/handoff_README.md)
- Báo cáo kiểm thử 71 tests: [test_report.md](docs/w02_b2/test_report.md)
- Báo cáo kiểm định rò rỉ dữ liệu: [leakage_audit.md](docs/w02_b2/leakage_audit.md)
- Đặc tả trích xuất đặc trưng: [feature_extraction_spec_v1.md](docs/w02_b2/feature_extraction_spec_v1.md)
- Đặc tả chiến lược phân hoạch: [split_strategy_spec_v1.md](docs/w02_b2/split_strategy_spec_v1.md)
- Đặc tả quy trình tiền xử lý: [preprocessing_spec_v1.md](docs/w02_b2/preprocessing_spec_v1.md)

---

## 4. Quyết định Kiến trúc Chờ Phê duyệt
- **DEC-002: PENDING REVIEWER APPROVAL** — Phê duyệt chính sách cô lập Shared-Tail 891k dòng (`exclude`).
- **DEC-005: PENDING REVIEWER APPROVAL** — Phê duyệt bổ sung cột `label_provenance` ('observed'/'inferred') vào Schema v2.
- **DEC-007: PENDING REVIEWER APPROVAL** — Phê duyệt Baseline-A (23 features) làm cấu hình chuẩn của hệ thống.
