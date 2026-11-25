# Preprocessing Specification — SGOD-P1-W02-B2
**Version:** v1 | **Status:** PROPOSED  
**Date:** 2026-11-22

---

## 1. Pipeline Overview

```
RAW DATA (CSV / TXT)
       │
       ▼
  [STEP 1: PARSE]
  parse_csv_row() / parse_txt_row()
  - Timestamp: float64, seconds since epoch
  - CAN ID: lowercase hex string (e.g. "0316")
  - DLC: int [0,8]
  - Payload bytes: list[str|None], length 8
  - flag_raw: 'R'|'T'|None
       │
       ▼
  [STEP 2: VALIDATE]
  validate_row()
  - Required keys present
  - Timestamp: finite float
  - DLC: 0-8
  - Bytes consistent with DLC
  - Flag: R/T/None
  - Invalid → log via malformed_logger, skip row
       │
       ▼
  [STEP 3: NORMALIZE SCHEMA]
  - CAN ID → lowercase
  - Timestamp → float64
  - DLC → int8
  - Bytes → hex string | None
       │
       ▼
  [STEP 4: LABEL / PROVENANCE]
  normalize_label()
  - CSV 'R' → (label=0, provenance='observed')
  - CSV 'T' → (label=1, provenance='observed')
  - TXT      → (label=0, provenance='inferred')
       │
       ▼
  [STEP 5: SEGMENT / GROUP]
  - segment_id: timestamp gap > gap_seconds (mặc định 1.0 giây) → new segment
  - Dùng để reset temporal features tại ranh giới
  - [PENDING APPROVAL DEC-005] label_provenance, segment_id có vào schema v2?
       │
       ▼
  [STEP 6: SPLIT]
  assign_split_groups(strategy='purged_temporal', seed=42)
  - train 70% / val 15% / test 15% / purged (gap)
  - Shared tail → excluded_shared_tail (mặc định exclude)
       │
       ▼
  [STEP 7: FEATURE EXTRACTION]
  extract_frame_features() + extract_temporal_features()
  - Stateless transformations (no fitting needed)
  - Temporal: causal only, no future, reset at source/split/segment boundary and gap > 1s
       │
       ▼
  [STEP 8: TRAIN-ONLY FIT]
  PreprocessingPipeline.fit(train_df)
  - Fit IAT StandardScaler trên train only
  - Lưu mean, std để dùng cho val/test
       │
       ▼
  [STEP 9: TRANSFORM]
  PreprocessingPipeline.transform(split_df)
  - Apply fitted scalers (không refit)
  - Output: feature matrix X + label vector y
       │
       ▼
  [MODEL INPUT]
  X: float32/float64 matrix, shape (n_rows, n_features)
  y: int8 binary label (0=normal, 1=attack)
```

---

## 2. Phân loại Transformations

| Loại | Ví dụ | Fit cần không? | Áp dụng lúc nào? |
|------|-------|---------------|-----------------|
| **Stateless** | parse hex → int, DLC mask, timestamp format | Không | Mọi lúc (parse, transform, inference) |
| **Train-fitted** | IAT StandardScaler (mean, std) | Chỉ trên train | Fit: train only; Apply: train + val + test |
| **Model-specific** | CAN ID embedding, sequence windowing | Phụ thuộc model | Trong model, không trong pipeline |

---

## 3. Label Encoding

| Input (flag_raw) | Source Type | label_int | provenance |
|-----------------|------------|----------|-----------|
| 'R' hoặc 'r' | csv | 0 | 'observed' |
| 'T' hoặc 't' | csv | 1 | 'observed' |
| None / bất kỳ | txt | 0 | 'inferred' |
| Khác | csv | ERROR | — |

> [!IMPORTANT]
> `normal_run_data.txt` không có cột flag. Nhãn 0 được **suy ra** từ nguồn, không phải quan sát trực tiếp từ flag.

---

## 4. DLC / Payload Handling

| DLC | Bytes hợp lệ | Mask | Bytes ngoài DLC |
|-----|-------------|------|----------------|
| 0 | — | [0,0,0,0,0,0,0,0] | Tất cả → 0 |
| 2 | data_0, data_1 | [1,1,0,0,0,0,0,0] | data_2..7 → 0 |
| 5 | data_0..4 | [1,1,1,1,1,0,0,0] | data_5..7 → 0 |
| 6 | data_0..5 | [1,1,1,1,1,1,0,0] | data_6,7 → 0 |
| 8 | data_0..7 | [1,1,1,1,1,1,1,1] | — |

**Phân biệt '00' thật vs padding:**
- Byte 0x00 với mask=1: **thực sự là zero** trong payload
- Byte 0x00 với mask=0: **padding**, vị trí không được truyền trong frame

---

## 5. Malformed Row Handling

```
Malformed row detected
        │
        ├─→ log via malformed_logger.warning(f"line {N}: {reason}")
        │
        ├─→ skip row (KHÔNG thêm vào dataset)
        │
        └─→ ghi vào errors.csv nếu có output pipeline
```

**Không xóa malformed rows khỏi raw data.** Chỉ skip khi load.

Từ B1: `normal_run_data.txt` có **1 malformed row** (line không khớp NORMAL_RE pattern).

---

## 6. Reproducibility Requirements

| Yêu cầu | Chi tiết |
|---------|---------|
| Seed | SEED=42 cho tất cả random operations |
| Scaler persistence | PreprocessingPipeline.save() / .load() lưu mean, std |
| Feature order | Phải consistent giữa training và inference |
| DLC mask | Phải được áp dụng trước khi scale/embed |
| CAN ID | Giữ dạng hex trong schema; convert sang int khi feature extraction |
| Timestamp | Giữ float64 đầy đủ, không round |

---

## 7. PROPOSED / VERIFIED / PENDING APPROVAL

| Item | Trạng thái | Reviewer |
|------|-----------|---------|
| Label encoding R→0, T→1 | VERIFIED (từ W01-B2 schema) | — |
| DLC domain [0,8] | VERIFIED (từ HCRL dataset) | — |
| Shared tail → exclude | PROPOSED | DEC-002 |
| label_provenance field | PROPOSED (từ B1) | DEC-005 |
| segment_id field | PROPOSED (từ B1) | DEC-005 |
| IAT StandardScaler | PROPOSED | DEC-007 |
| gap_frac = 0.01 | PROPOSED | DEC-008 |
| Binary classification | PROPOSED | DEC-003 |
| Feature ablation default: Baseline-A | PROPOSED | A2/A3 |
