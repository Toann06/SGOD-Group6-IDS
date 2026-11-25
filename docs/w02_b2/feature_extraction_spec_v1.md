# Feature Extraction Specification — CAN Bus IDS
**Document**: `feature_extraction_spec_v1.md`  
**Phase**: SGOD-P1-W02-B2 / Phase 3A  
**Schema baseline**: W01-B2 (15 columns)  
**Status**: DRAFT — pending reviewer sign-off on PENDING APPROVAL items  

---

## 1. Frame-Level Baseline Features (Group A)

These features are derived purely from a single CAN frame. No temporal context is needed.

| Feature | Type | Description | Source Column(s) | Notes |
|---|---|---|---|---|
| `can_id_int` | uint32 | CAN Arbitration ID parsed from hex string to unsigned integer | `can_id` | Hex string with or without `0x` prefix. Returns -1 on parse error. Range: [0, 0x7FF] for standard; [0, 0x1FFFFFFF] for extended frames. Present only in **Baseline-A**. |
| `dlc` | int8 | Data Length Code — number of valid payload bytes | `dlc` | Expected domain [0, 8]. Passed through as-is; NaN coerced to 0. |
| `data_0` | float32 | Byte 0 of CAN payload | `data_0` | 0 if `dlc < 1`; NaN→0 if byte should be present (dlc ≥ 1) but is missing in source. |
| `data_1` | float32 | Byte 1 of CAN payload | `data_1` | 0 if `dlc < 2`. Same NaN policy. |
| `data_2` | float32 | Byte 2 of CAN payload | `data_2` | 0 if `dlc < 3`. |
| `data_3` | float32 | Byte 3 of CAN payload | `data_3` | 0 if `dlc < 4`. |
| `data_4` | float32 | Byte 4 of CAN payload | `data_4` | 0 if `dlc < 5`. |
| `data_5` | float32 | Byte 5 of CAN payload | `data_5` | 0 if `dlc < 6`. |
| `data_6` | float32 | Byte 6 of CAN payload | `data_6` | 0 if `dlc < 7`. |
| `data_7` | float32 | Byte 7 of CAN payload | `data_7` | 0 if `dlc < 8`. |
| `payload_mask_0` | int8 | 1 if byte 0 is within DLC, 0 otherwise | `dlc` | Computed as `int(dlc > 0)`. Allows model to distinguish real zeros from DLC-padding zeros. |
| `payload_mask_1` | int8 | 1 if byte 1 is within DLC | `dlc` | `int(dlc > 1)` |
| `payload_mask_2` | int8 | 1 if byte 2 is within DLC | `dlc` | `int(dlc > 2)` |
| `payload_mask_3` | int8 | 1 if byte 3 is within DLC | `dlc` | `int(dlc > 3)` |
| `payload_mask_4` | int8 | 1 if byte 4 is within DLC | `dlc` | `int(dlc > 4)` |
| `payload_mask_5` | int8 | 1 if byte 5 is within DLC | `dlc` | `int(dlc > 5)` |
| `payload_mask_6` | int8 | 1 if byte 6 is within DLC | `dlc` | `int(dlc > 6)` |
| `payload_mask_7` | int8 | 1 if byte 7 is within DLC | `dlc` | `int(dlc > 7)` |

**Total (Baseline-A, with CAN ID)**: 18 features  
**Total (Baseline-B, without CAN ID)**: 17 features  

### Rationale

- **can_id_int**: CAN ID is a primary discriminator for DoS attacks (single ID flooding) and RPM/gear injection (specific well-known IDs). The ablation without CAN ID tests whether temporal patterns alone suffice, reducing risk of overfitting to dataset-specific ID assignments.
- **dlc**: Variable DLC is rare on a healthy CAN bus for a given ID; unexpected DLC changes are a known Fuzzy attack signature.
- **data_0..data_7**: Raw payload bytes carry sensor readings; replay and injection attacks typically exhibit anomalous byte patterns. All 8 columns are retained to avoid information loss.
- **payload_mask_0..7**: Without the mask, a model cannot distinguish `data_3=0` because `dlc=3` (legitimate padding) from `data_3=0` because the sensor value is actually zero. The mask resolves this ambiguity without leaking any label information.

---

## 2. Temporal Features (Group B)

These features capture the inter-frame timing dynamics of the CAN bus. All computations are **causal-only**: only past frames (index ≤ current) are used.

| Feature | Type | Window / Params | Description | Source Column(s) | Causal Constraint | Notes |
|---|---|---|---|---|---|---|
| `inter_arrival_time` | float64 | Per CAN ID | Time difference (seconds) between the current frame and the immediately preceding frame **with the same CAN ID**, within the same source, split and segment (reset also on gap > 1s). | `timestamp`, `can_id`, `source_file` | Yes — uses `diff()` on sorted past frames only | NaN for the first frame of each ID in each segment. |
| `global_iat` | float64 | Global | Time difference (seconds) between the current frame and the immediately preceding frame **of any CAN ID**, within the same source, split and segment (reset also on gap > 1s). | `timestamp`, `source_file` | Yes — `diff()` on sequential past frames | NaN at segment boundaries. Captures overall bus load. |
| `can_id_freq_1s` | float64 | 1-second rolling window | Count of frames with the same CAN ID in the past 1.0 second (inclusive of current frame), within the same source, split and segment (reset also on gap > 1s). | `timestamp`, `can_id`, `source_file` | Yes — counts only past frames `t ∈ (current_t - 1s, current_t]` | Key indicator for DoS (high frequency on one ID). Window size = 1 s. |
| `rolling_mean_iat` | float64 | Last 10 IATs, same CAN ID | Rolling mean of `inter_arrival_time` over the previous 10 frames with the same CAN ID, within the same source, split and segment (reset also on gap > 1s). | `inter_arrival_time`, `can_id`, `source_file` | Yes — rolling with `min_periods=1`, no look-ahead | `min_periods=1` ensures early frames receive an estimate. |
| `rolling_std_iat` | float64 | Last 10 IATs, same CAN ID | Rolling standard deviation of `inter_arrival_time` over the previous 10 frames with the same CAN ID, within the same source, split and segment (reset also on gap > 1s). | `inter_arrival_time`, `can_id`, `source_file` | Yes — rolling with `min_periods=1`, no look-ahead | NaN when fewer than 2 observations exist (std undefined). `min_periods=1` applied. |

**Total temporal features**: 5

### Rationale

- **inter_arrival_time**: DoS attacks compress IAT for the targeted ID dramatically. This is the most direct indicator.
- **global_iat**: Bus-level throughput changes (global flooding) are not captured by per-ID IAT alone.
- **can_id_freq_1s**: A fixed-window count complements rolling IAT by providing an absolute rate rather than a relative timing measure; tunable for different attack speeds.
- **rolling_mean_iat / rolling_std_iat**: Together these approximate the per-ID IAT distribution. High std may indicate Fuzzy injection; near-zero std with very small mean indicates DoS; near-zero std with normal mean indicates healthy periodic transmission.

---

## 3. Ablation Designs

| Design | CAN ID | Frame Features (N) | + Temporal | Total |
|---|---|---|---|---|
| **Baseline-A** (default) | ✅ included as `can_id_int` | 18 | +5 | 23 |
| **Baseline-B** | ❌ excluded | 17 | +5 | 22 |

### Baseline-A: `ablation='with_id'`
Full feature set including `can_id_int`. Appropriate when the model should learn ID-specific behaviour (e.g., gradient boosting, tree-based models). Most informative but risks overfitting to ID distributions specific to the OTIDS dataset.

### Baseline-B: `ablation='without_id'`
Excludes `can_id_int`. Forces the model to rely on payload content and temporal patterns. Useful for evaluating generalisability to new CAN networks where ID assignments differ. Also suitable for embedding-based neural models that handle the ID separately.

> **Usage**: Call `get_feature_names(ablation='with_id')` or `get_feature_names(ablation='without_id')` to retrieve the ordered column list for model training.

---

## 4. Excluded Fields

The following columns from the W01-B2 schema (and B1 proposals) are explicitly **excluded** from the feature matrix.

| Column | Reason |
|---|---|
| `flag_raw` | Directly encodes attack status (column 3 of original OTIDS dataset). Including it would be trivial data leakage. |
| `label` | Ground-truth label. Must never appear in the feature matrix. |
| `attack_type` | Fine-grained label; derived from `label`. Leakage. |
| `source_file` | Dataset provenance metadata. Used internally as a segment boundary marker but must not be a model input feature. |
| `source_line` | Row index in source file. No predictive signal; purely provenance. |
| `label_provenance` | Proposed by B1; pending approval (see §5). Even if approved, it carries label derivation information and must be excluded. |
| `segment_id` | Proposed by B1; pending approval (see §5). Used internally as a boundary marker; must not be a model feature. |

> [!CAUTION]
> Any column whose name matches or is derived from these excluded fields will be flagged by `validate_no_label_leakage()`. Always run this validator before saving features to disk.

---

## 5. PROPOSED / PENDING APPROVAL Items

The following items have been proposed by prior work (B1) or in this design but have **not yet been approved** by A2/A3 (reviewer).

| Item | Proposed by | Description | Action Required |
|---|---|---|---|
| `label_provenance` column | B1 (W02-B1 data_specification_v0.2) | Tracks how each label was assigned (original file vs. inferred). Useful for auditing but must remain excluded from features. | **A2/A3 to confirm**: add to schema W02 or keep as internal metadata only? |
| `segment_id` column | B1 (W02-B1 data_specification_v0.2) | Integer segment identifier for temporal window boundary enforcement. Used internally together with source_file and split; inferred IDs are batch-local. | **A2/A3 to confirm**: approve schema addition? If yes, `segment_id` complements `source_file`-based boundary logic. |
| `can_id_freq_1s` window size (1 s) | Phase 3A (this doc) | 1-second window chosen heuristically. OTIDS DoS attacks generate ~1000 frames/s on a targeted ID; a 1 s window captures ~1000 events vs. ~100 for a normal ID. | **A2/A3 to review**: confirm window size, or provide alternative (e.g., 0.5 s, 2 s). |
| `rolling_iat` window size (10 frames) | Phase 3A (this doc) | Window of 10 same-ID frames chosen to balance responsiveness vs. stability. | **A2/A3 to review**: confirm or adjust. |
| Extended CAN ID support | Phase 3A (this doc) | Current parser supports both standard (11-bit, [0, 0x7FF]) and extended (29-bit, [0, 0x1FFFFFFF]) CAN IDs. OTIDS dataset appears to use standard IDs only, but extended IDs are not rejected. | **A2/A3 to confirm**: are extended IDs present in any source file? Should they be rejected or treated separately? |

---

## 6. Edge Cases

### 6.1 DLC = 2 — Partial Payload

When `dlc = 2`, only `data_0` and `data_1` are valid payload bytes.  
`data_2` through `data_7` will be:
- Set to `0.0` in the feature matrix.
- Their corresponding `payload_mask_2` through `payload_mask_7` will be `0`.

A model that sees `payload_mask_2 = 0` knows that `data_2 = 0` is padding, not a sensor reading of zero. **This is the key purpose of the mask columns.**

Similarly for DLC = 5 (data_0..data_4 valid, mask_5..mask_7 = 0) and DLC = 6 (data_0..data_5 valid).

### 6.2 Byte Padding vs. Missing Data

Two distinct situations result in a byte column containing `0`:

| Situation | `data_i` value | `payload_mask_i` |
|---|---|---|
| Byte is outside DLC window (padding) | `0.0` (forced) | `0` |
| Byte is within DLC window but was `NaN` in source CSV | `0.0` (NaN→0 filled) | `1` |

The mask resolves the ambiguity. Models should weight `data_i` by `payload_mask_i` or use the mask as a separate input.

### 6.3 Timestamp Precision

OTIDS timestamps are recorded as floating-point seconds with microsecond precision (e.g., `0.004995`). `inter_arrival_time` and `global_iat` are therefore in seconds with float64 precision.

Potential issues:
- **Duplicate timestamps**: Two frames with identical timestamps yield `inter_arrival_time = 0.0`. This is valid (burst frames) but can inflate `can_id_freq_1s` counts.
- **Timestamp gaps at segment boundaries**: IAT is set to `NaN` when the `source_file` changes. The first frame of each segment has `inter_arrival_time = NaN` and `global_iat = NaN`. Downstream models must handle NaN (imputation or masking).
- **Clock drift / resets**: Not currently detected. If timestamps decrease within a segment, `inter_arrival_time` will be negative. Validation of monotonicity is recommended as a pre-processing step (out of scope for this script).

### 6.4 New / Unseen CAN IDs

A CAN ID that appears for the first time in a segment will have:
- `inter_arrival_time = NaN` (no prior frame of the same ID)
- `rolling_mean_iat = NaN`, `rolling_std_iat = NaN`
- `can_id_freq_1s = 1.0` (the frame itself is the only count in the window)

This is correct behaviour. Downstream models must handle NaN.

### 6.5 normal_run_data.txt Label Encoding

For `.txt` source files, `label = '0'` maps to normal (equivalent to `'R'` in CSV files). Non-zero label values map to attack. The feature extraction pipeline does **not** re-encode labels (they are excluded from features). The label normalisation responsibility lies with the ingestion / preprocessing layer (W01-B2 / B1 scripts).

---

*Generated by Phase 3A feat-engineer agent — SGOD-P1-W02-B2*  
*Last updated: 2026-11-22*
