# Split Strategy Specification — SGOD-P1-W02-B2
**Version:** v1 | **Status:** PROPOSED — Pending reviewer approval  
**Date:** 2026-11-22

---

## 1. Mục tiêu

Phân chia dataset thành train/validation/test theo cách:
- **Không có data leakage** giữa các split
- **Bảo toàn temporal ordering** (mạng CAN có tính thời gian cao)
- **Xử lý đúng shared tail** (891,068 rows giống nhau ở 4 CSV)
- **Đảm bảo representativeness** (đủ attack samples ở val/test)
- **Tái lập hoàn toàn** (seed cố định)

---

## 2. Phân tích 4 chiến lược

| Chiến lược | Mô tả | Temporal Leakage | Shared Tail | Khuyến nghị |
|-----------|-------|-----------------|-------------|------------|
| **Random row split** | Shuffle toàn bộ → split ngẫu nhiên | ❌ NGHIÊM TRỌNG | ❌ Rows giống nhau ở train+test | Chỉ dùng ablation |
| **Chronological** | Sort global by timestamp, cut at 70% | ⚠️ Moderate (window overlap) | ❌ Không xử lý inter-file | Không phù hợp |
| **Group-aware** | Mỗi source_file → 1 split | ✅ Tốt | ❌ 4 CSV đều có shared tail | Không khả thi |
| **Purged Temporal** | Per-file chrono, purge gap, shared tail → exclude | ✅ Tốt nhất | ✅ Xử lý explicit | **Được chọn** |

---

## 3. Chiến lược được chọn: Purged Temporal Split

### 3.1 Thuật toán

```
INPUT: df (tất cả sources), seed=42, train=0.70, val=0.15, test=0.15, gap=0.01

STEP 1: Phát hiện shared tail rows
  → Heuristic: source_file ∈ {4 CSV files} AND timestamp ∈ [1478200727.419470, 1478201209.058944]
  → Phân bổ: split = 'excluded_shared_tail' (default exclude)

STEP 2: Per source_file, sort remaining non-tail rows by timestamp
  FOR EACH source_file:
    ts_range = max_ts - min_ts
    gap      = ts_range × gap_frac
    tv_cut   = min_ts + ts_range × 0.70  # train/val boundary
    vt_cut   = min_ts + ts_range × 0.85  # val/test boundary
    
    train: ts < tv_cut - gap/2
    val:   ts ∈ (tv_cut + gap/2, vt_cut - gap/2)
    test:  ts > vt_cut + gap/2
    purged: gap rows (không dùng trong training/evaluation)

STEP 3: Validate split integrity
  → check_hash_overlap() [NOTE: nhiều false positives với CAN data]
  → check_temporal_leakage()
  → verify shared-tail excluded from train/val/test
```

### 3.2 Tham số

| Tham số | Giá trị | Lý do |
|---------|---------|-------|
| `seed` | 42 | Determinism |
| `train_frac` | 0.70 | Tiêu chuẩn ML |
| `val_frac` | 0.15 | Đủ cho hyperparameter tuning |
| `test_frac` | 0.15 | Đủ cho evaluation |
| `gap_frac` | 0.01 | 1% time range ≈ vài giây, đủ để loại bỏ window leakage |

---

## 4. Xử lý Shared Tail (891,068 rows)

### 4.1 Bằng chứng (từ B1)
- **Source:** references/SGOD-P1-W02-B1/outputs/tail_overlap/report.md
- **Rows:** 891,068 rows xuất hiện ở cả 4 CSV (DoS, Fuzzy, gear, RPM)
- **Timestamp range:** 1478200727.419470 → 1478201209.058944
- **SHA-256 nội dung:** `8dc026b6b...` (giống hệt nhau ở 4 files)
- **Label:** tất cả R (normal), không có attack rows trong shared tail
- **normal_run_data.txt:** KHÔNG có shared tail (timestamp ranges khác)

### 4.2 Quyết định phân bổ: [PENDING APPROVAL — DEC-002]

**Đề xuất hiện tại:** `shared_tail_policy="exclude"` (mặc định trong code), loại cả bốn bản sao khỏi train/val/test chính. Chính sách train-only trước đây là legacy, có nguy cơ đảo thứ tự thời gian và nhân trọng số normal. `isolate` cho đánh giá riêng; mọi lựa chọn thay thế cần reviewer xác nhận. Audit toàn bộ bốn CSV ngày 24/11 xác nhận segment 0 tương đương non-tail, 0 mismatch và 0 attack trong tail. Không áp dụng quy tắc segment 0 máy móc cho TXT.

---

## 5. Quy tắc cứng (không được vi phạm)

```python
# 1. Seed phải cố định
assign_split_groups(df, seed=42)

# 2. Scaler chỉ được fit trên train
pipeline.fit(train_df)  # KHÔNG fit(all_df) hay fit(val_df)

# 3. Không oversample trước split
# Oversample (nếu cần) phải thực hiện SAU khi đã split

# 4. Không tạo window xuyên split boundary
# Temporal features phải được tính riêng cho mỗi split

# 5. Không dùng test để chọn hyperparameter
# Test chỉ dùng 1 lần duy nhất, sau khi model đã finalized
```

---

## 6. Giới hạn đã biết

| Giới hạn | Mô tả | Tác động |
|---------|-------|---------|
| attack_coverage_ok=False với small sample | Yêu cầu >1000 attack rows ở val/test | Gear/RPM val mẫu có 683/547 attack; full dataset chưa kiểm tra |
| Hash-based leakage check: false positives | CAN frames lặp lại (normal) → hash trùng | Không dùng hash check để detect leakage; dùng timestamp-based |
| Shared tail detection: heuristic | Dựa trên timestamp range, không phải exact hash | Có thể false negative nếu có rows ngoài range |

---

## 7. Pending Approval

| DEC-ID | Vấn đề | Reviewer |
|--------|--------|---------|
| DEC-002 | Shared tail → exclude vs. alternative policy | A2/A3/mentor |
| DEC-003 | Binary (R/T) hay multiclass (normal/dos/fuzzy/gear/rpm)? | A2/A3 |
| DEC-004 | FL client split: mỗi client = 1 source file? | A2/A3 |
| DEC-008 | Tỷ lệ 70/15/15 có phù hợp không? | mentor |
