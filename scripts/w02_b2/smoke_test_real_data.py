"""
PHASE 4 — Real Data Smoke Test (SAMPLE VALIDATION)
====================================================
Reads 2000 rows per CSV file (not full dataset).
Results: SAMPLE VALIDATION only.
"""
import json
import sys
import pandas as pd
import numpy as np

sys.path.insert(0, "D:/SGOD/SGOD-B2")

from scripts.w02_b2.feature_extraction import (
    extract_frame_features, extract_temporal_features,
    validate_no_label_leakage, SCHEMA_COLS_W01_B2
)
from scripts.w02_b2.split_strategy import (
    assign_split_groups, validate_split_integrity, compute_row_hash
)
from scripts.w02_b2.validate_leakage import run_full_leakage_check
from scripts.w02_b2.preprocessing_demo import parse_txt_row

CHUNK = 2000
WORKSPACE = "D:/SGOD/SGOD-B2"

report = {
    "scope": "SAMPLE VALIDATION: 2000 parsed rows per CSV; 50000 DoS rows for feature/split/leakage; NOT full dataset",
    "datasets": {},
    "feature_extraction": {},
    "split_test": {},
    "leakage_check": {},
    "txt_parsing": {},
}

# ── 1. Read CSV headers & sample ─────────────────────────────────────────────
CSV_NAMES = ["DoS_dataset.csv", "Fuzzy_dataset.csv", "gear_dataset.csv", "RPM_dataset.csv"]


from pathlib import Path
from scripts.w02_b2.can_parser import load_csv_chunk

for fname in CSV_NAMES:
    path = Path(WORKSPACE) / fname

    try:
        df = next(load_csv_chunk(path, chunksize=CHUNK))
    except StopIteration:
        raise RuntimeError(f"No valid rows parsed: {fname}")

    label_vc = df["label"].value_counts().to_dict()

    report["datasets"][fname] = {
        "rows_read": int(len(df)),
        "columns": list(df.columns),
        "label_distribution_sample": {
            str(k): int(v) for k, v in label_vc.items()
        },
        "first_source_line": int(df.iloc[0]["source_line"]),
        "readable": True,
    }

    print(
        f"[OK] {fname}: {len(df)} rows | "
        f"labels={label_vc}"
    )

# Use 50,000 rows to ensure substantial attack coverage across train, val, and test.
dos_df = next(
    load_csv_chunk(
        Path(WORKSPACE) / "DoS_dataset.csv",
        chunksize=50000,
    )
)

dos_df = dos_df.sort_values(
    ["timestamp", "source_line"],
    kind="stable",
).reset_index(drop=True)


# ── 3. Feature extraction ─────────────────────────────────────────────────────
frame_f = extract_frame_features(dos_df)
temp_f  = extract_temporal_features(dos_df)
all_f   = pd.concat([frame_f, temp_f], axis=1)
no_leak = validate_no_label_leakage(all_f, SCHEMA_COLS_W01_B2)
report["feature_extraction"] = {
    "source": "DoS_dataset.csv (50000 rows)",
    "frame_shape": list(frame_f.shape),
    "temporal_shape": list(temp_f.shape),
    "total_features": int(all_f.shape[1]),
    "no_label_leakage": bool(no_leak),
    "frame_columns": list(frame_f.columns),
    "temporal_columns": list(temp_f.columns),
}
print(f"[OK] Feature extraction: frame={frame_f.shape}, temporal={temp_f.shape}, no_leakage={no_leak}")

# ── 4. Split strategy ─────────────────────────────────────────────────────────
df_split   = assign_split_groups(dos_df, strategy="purged_temporal", seed=42)
split_vc   = df_split["split"].value_counts().to_dict()
integrity  = validate_split_integrity(df_split)
report["split_test"] = {
    "source": "DoS_dataset.csv (50000 rows)",
    "split_counts": {str(k): int(v) for k, v in split_vc.items()},
    "no_hash_overlap": bool(integrity["no_hash_overlap"]),
    "shared_tail_in_train_only": bool(integrity["shared_tail_in_train_only"]),
    "has_purged": bool(integrity["has_purged"]),
    "attack_coverage_ok": bool(integrity["attack_coverage_ok"]),
    "attack_counts_in_val_test": {str(k): int(v) for k, v in integrity.get("attack_counts_in_val_test", {}).items()},
    "size_dist": {k: v for k, v in integrity.get("size_dist", {}).items()},
}
print(f"[OK] Split: {split_vc} | no_overlap={integrity['no_hash_overlap']}")
print(f"     attack_counts_in_val_test={integrity.get('attack_counts_in_val_test')}")

# ── 5. Leakage check ──────────────────────────────────────────────────────────
from sklearn.preprocessing import StandardScaler

train_df = df_split[df_split["split"] == "train"].copy()
val_df   = df_split[df_split["split"] == "val"].copy()
test_df  = df_split[df_split["split"] == "test"].copy()

# Add IAT column to train and val for scaler fitting check
train_df["iat"] = train_df["timestamp"].diff().fillna(0.001)
val_df["iat"]   = val_df["timestamp"].diff().fillna(0.001)

scaler = StandardScaler()
scaler.fit(train_df[["iat"]])

if len(train_df) > 0 and len(val_df) > 0 and len(test_df) > 0:
    leakage = run_full_leakage_check(
        train_df, val_df, test_df, combined_df=df_split, scaler=scaler
    )
    report["leakage_check"] = {
        str(k): (bool(v) if isinstance(v, (bool, np.bool_)) else v)
        for k, v in leakage.items() if k != "checks"
    }
    report["leakage_check"]["checks"] = {
        str(k): (bool(v) if isinstance(v, (bool, np.bool_)) else v)
        for k, v in leakage.get("checks", {}).items()
    }
    passed = leakage["passed"]
    status = leakage["status"]
    print(f"[{'OK' if passed else 'WARN'}] Leakage check: status={status}, passed={passed}")
else:
    report["leakage_check"] = {"skipped": "not enough rows in one or more splits"}
    print("[WARN] Leakage check skipped (too few rows in splits)")

# ── 6. TXT parsing ────────────────────────────────────────────────────────────
txt_valid = 0
txt_malformed = 0
with open(f"{WORKSPACE}/normal_run_data.txt", encoding="utf-8") as f:
    for i, line in enumerate(f):
        if i >= 100:
            break
        try:
            result = parse_txt_row(line.strip(), source_line=i)
            if result is not None:
                txt_valid += 1
            else:
                txt_malformed += 1
        except ValueError:
            txt_malformed += 1

report["txt_parsing"] = {
    "lines_read": 100,
    "valid": txt_valid,
    "malformed": txt_malformed,
    "sample_line": "Timestamp: ... ID: ... DLC: ... bytes...",
}
print(f"[OK] TXT parsing: {txt_valid}/100 valid, {txt_malformed} malformed")

# ── 7. Write report ───────────────────────────────────────────────────────────
out_path = "D:/SGOD/SGOD-B2/outputs/w02_b2/real_data_smoke_test.json"
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(report, f, indent=2, ensure_ascii=False)
print(f"\n[DONE] Smoke test report saved to: {out_path}")
print("SCOPE: SAMPLE VALIDATION — 2000 rows per CSV, 100 TXT lines. NOT FULL VALIDATION.")
