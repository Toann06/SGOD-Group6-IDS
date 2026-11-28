"""C2 Week 2 pipeline aligned to A2 handover v1.2 and B2 feature extraction.

Default profile is A2's proposed frame-only hcrl_frame_18. Temporal profiles are
supported as experimental options; B3's stratified 18-row fixture is not a
chronological dataset and must not be used to validate temporal/model quality.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import re
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
import pandas as pd

from scripts.w02_b2.feature_extraction import (
    extract_frame_features, extract_temporal_features, get_feature_names,
    validate_no_label_leakage,
)
try:
    from .loader import B2_REQUIRED_COLUMNS, validate_b2_schema
except ImportError:
    from loader import B2_REQUIRED_COLUMNS, validate_b2_schema

LOG = logging.getLogger("c2_week2")
OPTIONAL_COLUMNS = {"label_provenance", "segment_id"}

A2_FRAME18_ORDER = (
    "can_id_int", "dlc",
    "data_0", "data_1", "data_2", "data_3", "data_4", "data_5", "data_6", "data_7",
    "payload_mask_0", "payload_mask_1", "payload_mask_2", "payload_mask_3",
    "payload_mask_4", "payload_mask_5", "payload_mask_6", "payload_mask_7",
)
A2_TEMPORAL_ORDER = (
    "inter_arrival_time", "global_iat", "can_id_freq_1s", "rolling_mean_iat", "rolling_std_iat",
)
PROFILE_FEATURES = {
    "hcrl_frame_18": A2_FRAME18_ORDER,
    "b2_baseline_a_23": A2_FRAME18_ORDER + A2_TEMPORAL_ORDER,
    "b2_baseline_b_22": tuple(x for x in A2_FRAME18_ORDER if x != "can_id_int") + A2_TEMPORAL_ORDER,
}
PROFILE_STATUS = {
    "hcrl_frame_18": "PROPOSED (A2 v1.2; frame-only; pending approval)",
    "b2_baseline_a_23": "PENDING_APPROVAL (DEC-007/DEC-009)",
    "b2_baseline_b_22": "PENDING_APPROVAL (DEC-007/DEC-009)",
}
BINARY_MAPPING = {"normal": 0, "0": 0, "benign": 0, "attack": 1, "1": 1}
MULTICLASS_MAPPING = {"normal": 0, "dos": 1, "fuzzy": 2, "gear": 3, "rpm": 4}


def sha256_file(path: Path) -> str:
    """Calculate SHA-256 using canonical CRLF line endings."""
    raw = path.read_bytes()
    normalized = raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    canonical = normalized.replace(b"\n", b"\r\n")
    return hashlib.sha256(canonical).hexdigest()


def load_handoff_csv(path: str | Path) -> pd.DataFrame:
    """Load CSV as strings to preserve CAN ID hex and payload leading zeros."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(path)
    if path.suffix.lower() != ".csv":
        raise ValueError("Input must be CSV")
    df = pd.read_csv(path, encoding="utf-8-sig", dtype=str, keep_default_na=False)
    if df.empty:
        raise ValueError("Input CSV is empty")
    if df.columns.duplicated().any():
        raise ValueError(f"Duplicate columns: {df.columns[df.columns.duplicated()].tolist()}")
    missing = [c for c in B2_REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required B2 columns: {missing}")
    dlc = pd.to_numeric(df["dlc"], errors="coerce")
    if (dlc.isna() | (dlc < 0) | (dlc > 8) | (dlc % 1 != 0)).any():
        raise ValueError("Invalid DLC: expected integer 0..8")
    labels = pd.to_numeric(df["label"], errors="coerce")
    if (labels.isna() | ~labels.isin([0, 1])).any():
        raise ValueError("Invalid binary label: expected 0/1 in B3 handoff label column")
    for row_idx, raw_id in enumerate(df["can_id"]):
        raw_id = raw_id.strip()
        if not re.fullmatch(r"(?:0[xX])?[0-9a-fA-F]+", raw_id):
            raise ValueError(f"Invalid CAN ID at row {row_idx}: {raw_id!r}")
        can_id_int = int(raw_id, 16)
        if can_id_int > 0x1FFFFFFF:
            raise ValueError(f"CAN ID exceeds 29-bit range at row {row_idx}: {raw_id!r}")
    for row_idx, dlc_value in enumerate(dlc.astype(int)):
        for i in range(8):
            value = str(df.at[row_idx, f"data_{i}"]).strip()
            if i < dlc_value:
                if value == "":
                    raise ValueError(f"Missing payload byte data_{i} at row {row_idx} within DLC (A2 v1.2 reject policy)")
                if not re.fullmatch(r"(?:0[xX])?[0-9a-fA-F]{1,2}", value):
                    raise ValueError(f"Invalid hex payload byte data_{i} at row {row_idx}: {value!r}")
            else:
                # A2/B2 contract allows empty padding; reject non-zero bytes outside DLC.
                if value != "" and not re.fullmatch(r"(?:0[xX])?0{1,2}", value):
                    raise ValueError(f"Payload byte data_{i} present beyond DLC at row {row_idx}: {value!r}")
    df["label"] = labels.astype(np.int64)
    df["dlc"] = dlc.astype(np.int8)
    return df


def to_feature_numeric(df: pd.DataFrame) -> pd.DataFrame:
    """Decode CAN ID and payload explicitly as hexadecimal (A2 v1.2 contract)."""
    work = df.copy()
    work["timestamp"] = pd.to_numeric(work["timestamp"], errors="raise")
    work["can_id"] = work["can_id"].astype(str).str.strip().str.replace(r"^0[xX]", "", regex=True).str.lower()
    # Keep CAN ID as hexadecimal text for B2 parser; it converts using base 16.
    work["can_id_int_source"] = work["can_id"].map(lambda x: int(x, 16))
    for i in range(8):
        col = f"data_{i}"
        work[col] = work[col].map(lambda v: int(str(v).strip().removeprefix("0x").removeprefix("0X"), 16) if str(v).strip() else np.nan)
    return work


def map_labels(df: pd.DataFrame, mode: str) -> tuple[np.ndarray, dict]:
    if mode == "binary":
        y = pd.to_numeric(df["label"], errors="raise").to_numpy(dtype=np.int64)
        if not np.isin(y, [0, 1]).all():
            raise ValueError("Binary label mapping expects label values 0 and 1")
        return y, {"mode": "binary", "mapping": {"Normal": 0, "Attack": 1}, "source_column": "label"}
    if mode == "multiclass":
        raw = df["attack_type"].astype(str).str.strip().str.lower()
        unknown = sorted(set(raw) - set(MULTICLASS_MAPPING))
        if unknown:
            raise ValueError(f"Unknown attack_type for multiclass mapping: {unknown}")
        y = raw.map(MULTICLASS_MAPPING).to_numpy(dtype=np.int64)
        return y, {"mode": "multiclass", "mapping": MULTICLASS_MAPPING, "source_column": "attack_type"}
    raise ValueError("label mode must be binary or multiclass")


def extract_features(df: pd.DataFrame, profile: str = "hcrl_frame_18"):
    """Return ordered feature frame, labels, metadata and feature-order contract."""
    if profile not in PROFILE_FEATURES:
        raise ValueError(f"Unknown profile {profile!r}; choose {list(PROFILE_FEATURES)}")
    original = df.copy()
    original["_c2_row_index"] = np.arange(len(original))
    # Frame-only features are stateless and preserve input row order. Temporal features
    # require source-local chronological sorting before calculation.
    if profile == "hcrl_frame_18":
        ordered = original.reset_index(drop=True)
    else:
        original["_timestamp_numeric"] = pd.to_numeric(original["timestamp"], errors="raise")
        ordered = original.sort_values(["source_file", "_timestamp_numeric"], kind="stable").drop(columns=["_timestamp_numeric"]).reset_index(drop=True)
    numeric = to_feature_numeric(ordered)
    frame = extract_frame_features(numeric)
    if profile == "hcrl_frame_18":
        features = frame.loc[:, list(A2_FRAME18_ORDER)]
    elif profile == "b2_baseline_a_23":
        temporal = extract_temporal_features(numeric)
        features = pd.concat([frame, temporal], axis=1).loc[:, list(PROFILE_FEATURES[profile])]
    else:
        temporal = extract_temporal_features(numeric)
        features = pd.concat([frame, temporal], axis=1).loc[:, list(PROFILE_FEATURES[profile])]
    # Exact order assertion against A2 handover v1.2 feature definitions.
    expected = list(PROFILE_FEATURES[profile])
    if list(features.columns) != expected:
        raise AssertionError(f"Feature order mismatch: {list(features.columns)} != {expected}")
    if not validate_no_label_leakage(features):
        raise ValueError("Label/metadata leakage detected in X features")
    y, label_spec = map_labels(ordered, "binary")  # default output is B3 binary label
    metadata_cols = [c for c in ["timestamp", "source_file", "source_line", "attack_type", "label_provenance", "segment_id"] if c in ordered.columns]
    meta = ordered[metadata_cols].copy()
    return features, y, meta, ordered, expected, label_spec


def manifest_integrity(manifest_path: str | Path, csv_path: str | Path) -> dict:
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    actual = sha256_file(Path(csv_path))
    expected = manifest.get("sample_sha256")
    return {"expected_sha256": expected, "actual_sha256": actual, "matches": bool(expected and expected == actual)}


def run_pipeline(input_path: str | Path, output_dir: str | Path, batch_size: int = 8,
                 profile: str = "hcrl_frame_18", label_mode: str = "binary",
                 manifest_path: str | Path | None = None) -> dict:
    if batch_size <= 0:
        raise ValueError("batch_size must be > 0")
    input_path = Path(input_path)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    df = load_handoff_csv(input_path)
    schema = validate_b2_schema(df, strict=True)
    features, _, meta, ordered, names, _ = extract_features(df, profile)
    y, label_spec = map_labels(ordered, label_mode)
    # No fitted scaler/imputer is applied here. Frame-only profile is finite by contract.
    Xdf = features.replace([np.inf, -np.inf], np.nan)
    missing_feature_count = int(Xdf.isna().sum().sum())
    if missing_feature_count:
        # For the frame profile there should be no NaN. Temporal profiles have undefined
        # first-observation values; 0-fill is explicitly provisional and recorded.
        Xdf = Xdf.fillna(0)
    X = Xdf.to_numpy(dtype=np.float32)
    y = y.astype(np.int64)
    if not np.isfinite(X).all():
        raise ValueError("Tensor X contains NaN or Inf after tensorization")
    if X.ndim != 2 or X.shape[1] != len(names) or y.ndim != 1 or len(X) != len(y):
        raise ValueError(f"Tensor contract violation: X={X.shape}, y={y.shape}, features={len(names)}")
    if "label" in names or "attack_type" in names or "timestamp" in names:
        raise ValueError("Forbidden target/metadata column in feature order")
    np.save(out / "X.npy", X)
    np.save(out / "y.npy", y)
    features.assign(mapped_label=y).to_csv(out / "features_with_label.csv", index=False, encoding="utf-8-sig")
    meta.assign(mapped_label=y).to_csv(out / "metadata.csv", index=False, encoding="utf-8-sig")
    batches = []
    batch_dir = out / "batches"
    batch_dir.mkdir(exist_ok=True)
    for batch_idx, start in enumerate(range(0, len(X), batch_size), start=1):
        end = min(start + batch_size, len(X))
        xb, yb = X[start:end], y[start:end]
        np.save(batch_dir / f"X_batch_{batch_idx:04d}.npy", xb)
        np.save(batch_dir / f"y_batch_{batch_idx:04d}.npy", yb)
        batches.append({"batch": batch_idx, "rows": int(len(xb)), "X_shape": list(xb.shape), "y_shape": list(yb.shape)})
    
    report = {
        "artifact": "C2 Week2 A2 v1.2 integrated CAN loader/feature/tensor pipeline",
        "version": "0.3.0",
        "input": str(input_path),
        "rows": int(len(df)),
        "schema_validation": schema,
        "profile": profile,
        "profile_status": PROFILE_STATUS[profile],
        "schema_version": "1.0.0",
        "feature_order": names,
        "n_features": len(names),
        "label_mode": label_mode,
        "label_mapping": label_spec,
        "label_counts": {
            str(k): int(v)
            for k, v in pd.Series(y).value_counts().sort_index().items()
        },
        "X_dtype": str(X.dtype),
        "X_shape": list(X.shape),
        "y_dtype": str(y.dtype),
        "y_shape": list(y.shape),
        "nan_inf_before_fill": missing_feature_count,
        "nan_policy": (
            "Temporal profiles: fill undefined temporal features with 0 "
            "(PROVISIONAL); frame profile requires finite values; no scaler fitted."
        ),
        "payload_encoding": "hex (explicit; leading zero hex preserved at read)",
        "batch_size": batch_size,
        "n_batches": len(batches),
        "batches": batches,
        "leakage_check": "PASS - label and metadata excluded from X",
        "temporal_fixture_caveat": (
            "B3 handoff is stratified 18-row sample, not chronological corpus. "
            "Temporal profiles are smoke-test only; do not use for training/quality metrics."
        ),
        "split_scaling_status": (
            "NOT IMPLEMENTED - awaiting B2/A3 approved split and train-only scaling contract."
        ),
        "handover_integrity": "NOT_CHECKED - manifest not provided.",
    }

    if manifest_path:
        integrity = manifest_integrity(manifest_path, input_path)
        report["manifest_integrity"] = integrity

        if integrity["matches"]:
            report["handover_integrity"] = (
                "VERIFIED - SHA-256 matches after CRLF normalization."
            )
        else:
            report["handover_integrity"] = "UNVERIFIED - SHA-256 mismatch."
            report["warning"] = (
                "Manifest SHA-256 mismatch. Fixture used for smoke test only; "
                "source integrity not verified."
            )

    report_path = out / "report.json"
    report_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    return report

def build_parser():
    parser = argparse.ArgumentParser(
        description="C2 Week 2 CAN DataLoader pipeline"
    )

    parser.add_argument(
        "--input",
        required=True,
        help="Path to input B3 labeled CSV"
    )
    parser.add_argument(
        "--manifest",
        default=None,
        help="Path to B3 manifest JSON"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=8,
        help="Batch size"
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        help="Directory for pipeline outputs"
    )
    parser.add_argument(
        "--profile",
        choices=list(PROFILE_FEATURES.keys()),
        default="hcrl_frame_18",
        help="Feature profile"
    )
    parser.add_argument(
        "--label-mode",
        choices=["binary", "multiclass"],
        default="binary",
        help="Label mapping mode"
    )

    return parser

def main():
    parser = build_parser()
    args = parser.parse_args()

    report = run_pipeline(
        input_path=args.input,
        output_dir=args.output_dir,
        batch_size=args.batch_size,
        profile=args.profile,
        label_mode=args.label_mode,
        manifest_path=args.manifest,
    )

    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
