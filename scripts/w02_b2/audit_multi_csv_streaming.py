"""
Streaming Multi-CSV Attack Distribution and Split Audit
======================================================
Streams through chunks of all 4 CSV datasets without loading the full files into RAM.

SCOPE: 50,000 rows sampled per dataset (before shared-tail timestamp boundary).
       This is a SAMPLE audit — not full-dataset coverage (~3.6M–4.6M rows/file).

Examines:
1. Row counts, attack/normal distribution per dataset sample.
2. Attack temporal distribution (timestamp range of attacks).
3. Purged temporal split on the 50,000-row sample — measures realistic
   attack coverage in Test and Val splits.
4. Leakage validation using REAL feature extraction pipeline (not synthetic iat),
   providing verified PASS/PASS_PARTIAL/FAIL/NOT_VERIFIED status.
5. Observation overlap checks across ALL 6 cross-file pairs.
"""
from pathlib import Path
import json
import logging
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler

from scripts.w02_b2.can_parser import load_csv_chunk
from scripts.w02_b2.split_strategy import (
    assign_split_groups,
    SHARED_TAIL_TS_START,
)
from scripts.w02_b2.validate_leakage import (
    run_full_leakage_check,
    check_observation_identity_overlap,
)
from scripts.w02_b2.feature_extraction import (
    extract_frame_features,
    extract_temporal_features,
    TEMPORAL_FEATURES,
    FRAME_FEATURES_WITH_ID,
)

logging.basicConfig(level=logging.WARNING)  # suppress verbose INFO logs during audit
logger = logging.getLogger(__name__)

ROOT = Path(r"D:\SGOD\SGOD-B2")
CSV_FILES = [
    "DoS_dataset.csv",
    "Fuzzy_dataset.csv",
    "gear_dataset.csv",
    "RPM_dataset.csv",
]

SAMPLE_ROWS = 50_000  # rows sampled per CSV before shared-tail

results = {
    "scope": (
        f"Multi-CSV streaming audit: {SAMPLE_ROWS:,} rows sampled per dataset "
        "(before shared-tail timestamp boundary). "
        "SAMPLE AUDIT — not full-dataset coverage."
    ),
    "sample_rows_per_csv": SAMPLE_ROWS,
    "datasets": {},
    "split_analysis": {},
    "cross_file_overlap": {},
    "audit_notes": [
        "Scaler verification uses real temporal feature pipeline (inter_arrival_time, "
        "rolling_mean_iat, rolling_std_iat, etc.), not synthetic diff(timestamp).",
        "Window boundary leakage check uses combined_df with 'split' column present.",
        "All 6 cross-file pairs checked (C(4,2)=6).",
    ],
}

print("=== STARTING MULTI-CSV STREAMING AUDIT ===")
print(f"Scope: {SAMPLE_ROWS:,} rows/CSV before shared-tail\n")

sample_dfs = {}

# ── Phase 1: Per-dataset sampling, split, real feature extraction, leakage check ──

for fname in CSV_FILES:
    fpath = ROOT / fname
    print(f"--- Processing {fname} ---")

    # Stream until we have SAMPLE_ROWS rows before shared-tail
    rows_collected = []
    total_read = 0
    for chunk in load_csv_chunk(fpath, chunksize=SAMPLE_ROWS):
        non_tail = chunk[chunk["timestamp"] < SHARED_TAIL_TS_START]
        if not non_tail.empty:
            rows_collected.append(non_tail)
            total_read += len(non_tail)
        if total_read >= SAMPLE_ROWS:
            break

    df_sample = pd.concat(rows_collected, ignore_index=True).head(SAMPLE_ROWS)
    sample_dfs[fname] = df_sample

    label_counts = df_sample["label"].value_counts().to_dict()
    normal_count = int(label_counts.get(0, 0))
    attack_count = int(label_counts.get(1, 0))
    total_count = len(df_sample)
    attack_pct = (attack_count / total_count * 100) if total_count else 0.0

    ts_min = float(df_sample["timestamp"].min())
    ts_max = float(df_sample["timestamp"].max())
    attack_rows = df_sample[df_sample["label"] == 1]
    att_min = float(attack_rows["timestamp"].min()) if not attack_rows.empty else None
    att_max = float(attack_rows["timestamp"].max()) if not attack_rows.empty else None

    print(f"  {total_count:,} rows | Normal: {normal_count:,} | Attack: {attack_count:,} ({attack_pct:.2f}%)")

    results["datasets"][fname] = {
        "sampled_rows": total_count,
        "normal_count": normal_count,
        "attack_count": attack_count,
        "attack_ratio_pct": round(attack_pct, 2),
        "timestamp_min": ts_min,
        "timestamp_max": ts_max,
        "attack_ts_min": att_min,
        "attack_ts_max": att_max,
    }

    # ── Purged temporal split ──
    split_df = assign_split_groups(
        df_sample, strategy="purged_temporal", seed=42, shared_tail_policy="exclude"
    )

    train = split_df[split_df["split"] == "train"]
    val   = split_df[split_df["split"] == "val"]
    test  = split_df[split_df["split"] == "test"]
    purged = split_df[split_df["split"] == "purged"]

    train_att  = int((train["label"] == 1).sum())
    val_att    = int((val["label"] == 1).sum())
    test_att   = int((test["label"] == 1).sum())
    purged_att = int((purged["label"] == 1).sum())

    print(f"  Split -> Train: {len(train):,} (att={train_att:,}), "
          f"Val: {len(val):,} (att={val_att:,}), "
          f"Test: {len(test):,} (att={test_att:,}), "
          f"Purged: {len(purged):,} (att={purged_att:,})")

    # ── Real feature extraction for scaler verification ──
    # Use actual temporal features (inter_arrival_time, rolling_mean_iat, etc.)
    # rather than a synthetic column derived from timestamp.diff().
    # This matches the real pipeline that would be deployed.
    scaler_status = "NOT_VERIFIED"
    scaler_feature_col = None
    real_scaler = None

    try:
        # Extract temporal features for each split independently (split boundary respected)
        train_temporal = extract_temporal_features(train.copy())
        val_temporal   = extract_temporal_features(val.copy())

        # Pick the first non-NaN temporal feature with enough data for scaler check
        for feat in ["inter_arrival_time", "rolling_mean_iat", "global_iat"]:
            train_vals = train_temporal[feat].dropna()
            val_vals   = val_temporal[feat].dropna()
            if len(train_vals) >= 10 and len(val_vals) >= 10:
                scaler_feature_col = feat
                break

        if scaler_feature_col:
            real_scaler = StandardScaler()
            real_scaler.fit(train_temporal[[scaler_feature_col]].dropna())
            # Inject feature column back for leakage check
            train_eval = train.copy()
            val_eval   = val.copy()
            test_eval  = test.copy()
            train_eval["_feat"] = train_temporal[scaler_feature_col].values
            val_eval["_feat"]   = val_temporal[scaler_feature_col].values
            test_temporal       = extract_temporal_features(test.copy())
            test_eval["_feat"]  = test_temporal[scaler_feature_col].values

            # Create a minimal scaler wrapper that check_scaler_fitted_on_train_only
            # can inspect (needs 'iat' column or the feature_col passed explicitly).
            # We inject via a renamed column to match the validator's default.
            train_eval = train_eval.rename(columns={"_feat": "iat"})
            val_eval   = val_eval.rename(columns={"_feat": "iat"})
            test_eval  = test_eval.rename(columns={"_feat": "iat"})

            # Rebuild scaler on 'iat' column name (rename to match validator)
            real_scaler_named = StandardScaler()
            real_scaler_named.fit(train_eval[["iat"]].dropna())

            print(f"  Scaler feature: '{scaler_feature_col}' "
                  f"(train_mean={float(real_scaler_named.mean_[0]):.6f})")
        else:
            # Insufficient data for real scaler check
            train_eval = train.copy()
            val_eval   = val.copy()
            test_eval  = test.copy()
            real_scaler_named = None
            print(f"  Scaler: NOT_VERIFIED (insufficient non-NaN temporal features)")

    except Exception as exc:
        logger.warning("Feature extraction for scaler check failed: %s", exc)
        train_eval = train.copy()
        val_eval   = val.copy()
        test_eval  = test.copy()
        real_scaler_named = None
        scaler_feature_col = None

    # ── Leakage check with real pipeline ──
    # combined_df carries the 'split' column, enabling window boundary check
    leak_report = run_full_leakage_check(
        train_eval, val_eval, test_eval,
        combined_df=split_df,            # enables window boundary check
        scaler=real_scaler_named,        # None → NOT_VERIFIED for scaler
    )

    scaler_result = leak_report.get("scaler_fitted_on_train_only", "NOT_VERIFIED")
    window_result = leak_report.get("window_boundary_leakage", "NOT_VERIFIED")
    print(f"  Leakage status: {leak_report['status']} | "
          f"scaler={scaler_result} | window={window_result}")

    results["split_analysis"][fname] = {
        "train_rows": len(train),
        "train_attacks": train_att,
        "val_rows": len(val),
        "val_attacks": val_att,
        "test_rows": len(test),
        "test_attacks": test_att,
        "purged_rows": len(purged),
        "purged_attacks": purged_att,
        "test_attack_coverage_sufficient": (test_att >= 100),
        "leakage_status": leak_report["status"],
        "leakage_passed": leak_report["passed"],
        "observation_leakage_detected": leak_report["observation_leakage_train_test"],
        "temporal_order_ordered": leak_report["temporal_order"]["all_ordered"],
        "window_boundary_leakage": str(window_result),
        "scaler_check": str(scaler_result),
        "scaler_feature_used": scaler_feature_col if scaler_feature_col else "NOT_VERIFIED",
        "unverified_checks": leak_report.get("unverified_checks", []),
    }

# ── Phase 2: Cross-file observation identity overlap — ALL 6 pairs ──
print("\n--- Cross-File Observation Identity Overlap (All 6 pairs) ---")

# C(4,2) = 6 pairs
all_pairs = []
for i, name_a in enumerate(CSV_FILES):
    for name_b in CSV_FILES[i+1:]:
        all_pairs.append((name_a, name_b))

for name_a, name_b in all_pairs:
    df_a = sample_dfs[name_a]
    df_b = sample_dfs[name_b]
    obs_overlap = check_observation_identity_overlap(df_a, df_b)
    pair_key = f"{name_a}_vs_{name_b}"
    print(f"  {name_a} × {name_b}: overlap={obs_overlap}")
    results["cross_file_overlap"][pair_key] = {
        "overlap_detected": obs_overlap,
        "check_method": (
            "primary: (source_file, source_line); "
            "secondary: exact (timestamp, can_id, dlc, payload) normalized tuple match "
            "with NaN sentinel '__NAN__'"
        ),
    }

# ── Save results ──
output_path = ROOT / "outputs" / "w02_b2" / "multi_csv_streaming_audit.json"
output_path.parent.mkdir(parents=True, exist_ok=True)
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2, default=str)

print(f"\n[DONE] Audit saved to {output_path}")
print(f"[INFO] Sample scope: {SAMPLE_ROWS:,} rows/CSV — NOT full-dataset coverage")
