"""
Feature Extraction for CAN Bus Intrusion Detection System
==========================================================
Phase: SGOD-P1-W02-B2 / Phase 3A
Schema: W01-B2 (15 cols) — timestamp, can_id, dlc, data_0..data_7,
        flag_raw, label, attack_type, source_file, source_line

Two feature groups:
  Group A — Frame-level baseline  (18 features per row)
  Group B — Temporal features     (5 features per row, causal-only)

Ablation variants:
  'with_id'    — includes can_id_int  (Group A: 18 features)
  'without_id' — excludes can_id_int  (Group A: 17 features)

EXCLUDED fields (label leakage / metadata):
  flag_raw, label, attack_type, source_file, source_line,
  label_provenance, segment_id
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SCHEMA_COLS_W01_B2 = [
    "timestamp", "can_id", "dlc",
    "data_0", "data_1", "data_2", "data_3",
    "data_4", "data_5", "data_6", "data_7",
    "flag_raw", "label", "attack_type", "source_file", "source_line",
]

# Fields that must NEVER appear in the feature matrix
EXCLUDED_FIELDS = frozenset([
    "flag_raw", "label", "attack_type",
    "source_file", "source_line",
    "label_provenance",   # B1 proposed, pending approval
    "segment_id",          # B1 proposed, pending approval
])

BYTE_COLS = [f"data_{i}" for i in range(8)]
MASK_COLS = [f"payload_mask_{i}" for i in range(8)]

FRAME_FEATURES_WITH_ID = (
    ["can_id_int", "dlc"]
    + BYTE_COLS
    + MASK_COLS
)  # 2 + 8 + 8 = 18

FRAME_FEATURES_WITHOUT_ID = (
    ["dlc"]
    + BYTE_COLS
    + MASK_COLS
)  # 1 + 8 + 8 = 17

TEMPORAL_FEATURES = [
    "inter_arrival_time",
    "global_iat",
    "can_id_freq_1s",
    "rolling_mean_iat",
    "rolling_std_iat",
]

IAT_WINDOW = 10          # frames for rolling IAT statistics (same CAN ID)
FREQ_WINDOW_S = 1.0      # seconds for can_id_freq_1s


# ---------------------------------------------------------------------------
# Input loading
# ---------------------------------------------------------------------------

def load_input(source: "str | Path | pd.DataFrame") -> pd.DataFrame:
    """Accept a DataFrame or a path to a CSV file."""
    if isinstance(source, pd.DataFrame):
        return source.copy()
    path = Path(source)
    if not path.exists():
        raise FileNotFoundError(f"Input file not found: {path}")
    df = pd.read_csv(path)
    logger.info("Loaded %d rows from %s", len(df), path)
    return df


# ---------------------------------------------------------------------------
# Group A — Frame-level baseline features
# ---------------------------------------------------------------------------

def extract_frame_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Extract frame-level baseline features.

    Parameters
    ----------
    df : DataFrame with at minimum columns: can_id, dlc, data_0..data_7

    Returns
    -------
    DataFrame with columns:
        can_id_int, dlc, data_0..data_7, payload_mask_0..payload_mask_7

    Design notes
    ------------
    - can_id_int   : hex CAN ID parsed to uint32; 0x000 and 0x7FF are valid.
    - dlc          : passed through as-is; expected domain [0, 8].
    - data_0..7    : NaN→0 for bytes WITHIN the DLC window (they should be
                     present but were missing in source); bytes OUTSIDE the
                     DLC window are set to 0 and their mask is set to 0 to
                     distinguish padding from actual payload.
    - payload_mask : 1 if byte index < dlc, 0 otherwise.  This lets a model
                     distinguish real zeros (payload) from DLC-padding zeros.
    """
    out = pd.DataFrame(index=df.index)

    # --- can_id_int ---
    out["can_id_int"] = (
        df["can_id"]
        .astype(str)
        .str.strip()
        .apply(_parse_hex_id)
    )

    # --- dlc ---
    out["dlc"] = pd.to_numeric(df["dlc"], errors="coerce").fillna(0).astype(np.int8)

    # --- payload_mask and data bytes ---
    dlc_arr = out["dlc"].values
    byte_vals: dict[str, np.ndarray] = {}
    mask_vals: dict[str, np.ndarray] = {}

    for i, col in enumerate(BYTE_COLS):
        mask_col = f"payload_mask_{i}"
        present_mask = (dlc_arr > i).astype(np.int8)
        mask_vals[mask_col] = present_mask

        if col in df.columns:
            raw = pd.to_numeric(df[col], errors="coerce")
            # Within DLC window: NaN → 0 (byte should be there but is missing)
            # Outside DLC window: force 0 (padding, mask already 0)
            filled = raw.fillna(0).astype(np.float32)
            byte_vals[col] = np.where(present_mask, filled, np.float32(0))
        else:
            byte_vals[col] = np.zeros(len(df), dtype=np.float32)

    # Write in canonical order: data_0..data_7 then payload_mask_0..payload_mask_7
    for col in BYTE_COLS:
        out[col] = byte_vals[col]
    for mask_col in MASK_COLS:
        out[mask_col] = mask_vals[mask_col]

    return out


def _parse_hex_id(val: str) -> int:
    """Parse a hex CAN ID string (with or without '0x') to int; -1 on error."""
    try:
        return int(val, 16)
    except (ValueError, TypeError):
        return -1


# ---------------------------------------------------------------------------
# Group B — Temporal features (causal-only)
# ---------------------------------------------------------------------------

def extract_temporal_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Extract temporal / statistical features.

    Parameters
    ----------
    df : DataFrame with at minimum columns: timestamp, can_id, source_file
         (source_file is used as the segment boundary marker — windows must
          not cross segment/source boundaries)

    Returns
    -------
    DataFrame with columns:
        inter_arrival_time, global_iat, can_id_freq_1s,
        rolling_mean_iat, rolling_std_iat

    Causal constraint
    -----------------
    All computations use only past frames (lookback).  No future information
    is ever used.  Rolling operations are performed with min_periods=1 so that
    early frames receive a valid (if noisy) estimate.

    Boundary constraint
    -------------------
    IAT and rolling windows are reset at source_file boundaries.  Frames from
    different source files are never mixed in the same window.  When a new
    source file starts the inter-arrival time is set to NaN (no valid prior).
    """
    df = df.copy()

    # --- parse timestamp ---
    ts = pd.to_numeric(df["timestamp"], errors="coerce")
    if ts.isna().all():
        logger.warning("All timestamps are NaN — temporal features will be NaN.")

    from scripts.w02_b2.segment_utils import segment_context
    _, segment, global_iat = segment_context(df)

    # CAN ID as string key (keep hex format for groupby)
    can_id_str = df["can_id"].astype(str).str.strip()

    # Composite key for per-ID per-segment grouping
    group_key = segment + "|" + can_id_str

    out = pd.DataFrame(index=df.index)

    # --- global_iat ---
    # Time diff between consecutive frames (any ID), reset at segment boundary
    out["global_iat"] = global_iat.astype(np.float64)

    # --- inter_arrival_time ---
    # Time diff between consecutive frames of the SAME CAN ID within segment
    inter_arr = _group_diff(ts, group_key)
    out["inter_arrival_time"] = inter_arr.astype(np.float64)

    # --- rolling_mean_iat and rolling_std_iat ---
    # Rolling statistics over the last IAT_WINDOW IATs for same CAN ID+segment
    rolling_mean, rolling_std = _rolling_iat_stats(inter_arr, group_key, IAT_WINDOW)
    out["rolling_mean_iat"] = rolling_mean.astype(np.float64)
    out["rolling_std_iat"] = rolling_std.astype(np.float64)

    # --- can_id_freq_1s ---
    out["can_id_freq_1s"] = _can_id_freq(ts, can_id_str, segment, FREQ_WINDOW_S)

    return out


def _segment_diff(ts: pd.Series, segment: pd.Series) -> pd.Series:
    """Compute timestamp diff, zeroing across segment boundaries."""
    result = ts.diff()
    boundary = segment != segment.shift(1)
    result[boundary] = np.nan
    return result


def _group_diff(ts: pd.Series, group_key: pd.Series) -> pd.Series:
    """Compute per-group timestamp diff (causal, no cross-boundary)."""
    result = pd.Series(np.nan, index=ts.index, dtype=np.float64)
    for key, idx in ts.groupby(group_key).groups.items():
        sorted_idx = idx  # assume df is already time-sorted within segment
        vals = ts.loc[sorted_idx]
        result.loc[sorted_idx] = vals.diff().values
    return result


def _rolling_iat_stats(
    iat: pd.Series,
    group_key: pd.Series,
    window: int,
) -> tuple[pd.Series, pd.Series]:
    """Compute rolling mean/std of IAT for each group, causal only."""
    mean_s = pd.Series(np.nan, index=iat.index, dtype=np.float64)
    std_s = pd.Series(np.nan, index=iat.index, dtype=np.float64)
    for key, idx in iat.groupby(group_key).groups.items():
        vals = iat.loc[idx]
        mean_s.loc[idx] = vals.rolling(window=window, min_periods=1).mean().values
        std_s.loc[idx] = vals.rolling(window=window, min_periods=1).std().values
    return mean_s, std_s


def _can_id_freq(
    ts: pd.Series,
    can_id: pd.Series,
    segment: pd.Series,
    window_s: float,
) -> pd.Series:
    """
    Count how many times the same CAN ID appeared in the last `window_s`
    seconds (causal — only past frames, within same segment).

    Uses a rolling count on the original index after groupby.
    """
    result = pd.Series(np.nan, index=ts.index, dtype=np.float64)
    group_key = segment + "|" + can_id

    for key, idx in ts.groupby(group_key).groups.items():
        sorted_idx = idx
        t_vals = ts.loc[sorted_idx].values
        counts = np.zeros(len(t_vals), dtype=np.float64)
        for j, t_j in enumerate(t_vals):
            # count frames with timestamp in (t_j - window_s, t_j]
            lo = t_j - window_s
            counts[j] = np.sum((t_vals[:j + 1] > lo) & (t_vals[:j + 1] <= t_j))
        result.loc[sorted_idx] = counts

    return result


# ---------------------------------------------------------------------------
# Feature name registry
# ---------------------------------------------------------------------------

def get_feature_names(
    ablation: Literal["with_id", "without_id"] = "with_id",
    include_temporal: bool = True,
) -> list[str]:
    """
    Return the ordered list of feature names for a given ablation design.

    Parameters
    ----------
    ablation : 'with_id'    — include can_id_int (Baseline-A, default)
               'without_id' — exclude can_id_int (Baseline-B)
    include_temporal : whether to append temporal features

    Returns
    -------
    list of feature name strings
    """
    if ablation == "with_id":
        frame_names = list(FRAME_FEATURES_WITH_ID)
    elif ablation == "without_id":
        frame_names = list(FRAME_FEATURES_WITHOUT_ID)
    else:
        raise ValueError(f"ablation must be 'with_id' or 'without_id', got {ablation!r}")

    if include_temporal:
        return frame_names + list(TEMPORAL_FEATURES)
    return frame_names


# ---------------------------------------------------------------------------
# Label-leakage validator
# ---------------------------------------------------------------------------

def validate_no_label_leakage(
    features_df: pd.DataFrame,
    schema_cols: list[str] | None = None,
) -> bool:
    """
    Confirm that no excluded / leakage columns appear in features_df.

    Parameters
    ----------
    features_df : the feature matrix to validate
    schema_cols : optional list of full schema column names; defaults to
                  SCHEMA_COLS_W01_B2 union EXCLUDED_FIELDS

    Returns
    -------
    True  — no leakage detected
    False — at least one forbidden column found (details logged as ERROR)
    """
    if schema_cols is not None:
        # Build excluded set as intersection of provided schema and EXCLUDED_FIELDS
        forbidden = EXCLUDED_FIELDS.intersection(schema_cols)
    else:
        forbidden = set(EXCLUDED_FIELDS)

    present = forbidden.intersection(features_df.columns)
    if present:
        logger.error(
            "LABEL LEAKAGE DETECTED: columns %s found in feature matrix", sorted(present)
        )
        return False

    # Also warn if any column name *contains* a forbidden keyword (typo check)
    suspicious = [
        c for c in features_df.columns
        if any(excl in c for excl in EXCLUDED_FIELDS)
        and c not in forbidden
    ]
    if suspicious:
        logger.warning(
            "Suspicious column names (may be derived from excluded fields): %s",
            suspicious,
        )

    logger.info("validate_no_label_leakage: PASS — no forbidden columns found.")
    return True


# ---------------------------------------------------------------------------
# Combined pipeline helper
# ---------------------------------------------------------------------------

def extract_all_features(
    source: "str | Path | pd.DataFrame",
    ablation: Literal["with_id", "without_id"] = "with_id",
) -> pd.DataFrame:
    """
    Full pipeline: load → frame features → temporal features → join.

    Returns a DataFrame aligned to the input index.
    """
    df = load_input(source)
    frame_df = extract_frame_features(df)
    temp_df = extract_temporal_features(df)
    result = pd.concat([frame_df, temp_df], axis=1)

    # Drop can_id_int for without_id ablation
    if ablation == "without_id" and "can_id_int" in result.columns:
        result = result.drop(columns=["can_id_int"])

    return result


# ---------------------------------------------------------------------------
# __main__ — inline fixture smoke test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    # ------------------------------------------------------------------ #
    # Inline fixture                                                        #
    # Simulates mixed DLC frames from two source files, two CAN IDs        #
    # ------------------------------------------------------------------ #
    fixture_data = {
        "timestamp": [
            0.000, 0.005, 0.010, 0.015, 0.020,
            0.025, 0.030, 0.035, 0.040, 0.045,
            0.100, 0.105, 0.110,
        ],
        "can_id": [
            "0158", "0244", "0158", "0244", "0158",
            "0244", "0158", "0244", "0158", "0244",
            "0158", "0244", "0158",         # second source file starts at index 10
        ],
        "dlc": [
            8,    6,    8,    6,    8,
            6,    8,    6,    8,    6,
            2,    2,    2,
        ],
        # data_0..data_7
        "data_0": [0x12, 0xAB, 0x34, 0xCD, 0x56, 0xEF, 0x78, 0x01, 0x9A, 0x23, 0x11, 0x22, 0x33],
        "data_1": [0x34, 0x56, 0x78, 0x90, 0xBC, 0xDE, 0xF0, 0x12, 0x34, 0x56, 0x44, 0x55, 0x66],
        "data_2": [0x56, 0x78, 0x9A, 0xBC, 0xDE, 0xF0, 0x12, 0x34, 0x56, 0x78, None, None, None],
        "data_3": [0x78, 0x9A, 0xBC, 0xDE, 0xF0, 0x12, 0x34, 0x56, 0x78, 0x9A, None, None, None],
        "data_4": [0x9A, None, 0xBC, None, 0xDE, None, 0xF0, None, 0x12, None, None, None, None],
        "data_5": [0xBC, None, 0xDE, None, 0xF0, None, 0x12, None, 0x34, None, None, None, None],
        "data_6": [0xDE, None, 0xF0, None, 0x12, None, 0x34, None, 0x56, None, None, None, None],
        "data_7": [0xF0, None, 0x12, None, 0x34, None, 0x56, None, 0x78, None, None, None, None],
        # metadata / excluded fields
        "flag_raw": ["R", "R", "T", "T", "T", "R", "R", "T", "R", "R", "R", "R", "R"],
        "label":    ["R", "R", "T", "T", "T", "R", "R", "T", "R", "R", "R", "R", "R"],
        "attack_type": [
            "normal", "normal", "DoS", "DoS", "DoS",
            "normal", "normal", "Fuzzy", "normal", "normal",
            "normal", "normal", "normal",
        ],
        "source_file": (["file_A"] * 10) + (["file_B"] * 3),
        "source_line": list(range(13)),
    }

    df_fixture = pd.DataFrame(fixture_data)

    print("=" * 60)
    print("FIXTURE SHAPE:", df_fixture.shape)
    print("=" * 60)

    # --- Frame features ---
    frame_df = extract_frame_features(df_fixture)
    print("\n[Group A] Frame features shape:", frame_df.shape)
    print("Columns:", list(frame_df.columns))
    print(frame_df.to_string(index=True))

    # --- Temporal features ---
    temp_df = extract_temporal_features(df_fixture)
    print("\n[Group B] Temporal features shape:", temp_df.shape)
    print("Columns:", list(temp_df.columns))
    print(temp_df.to_string(index=True))

    # --- Feature name registry ---
    print("\n[get_feature_names] ablation='with_id' (all features):")
    names_with = get_feature_names("with_id", include_temporal=True)
    print(f"  Count: {len(names_with)}")
    print(f"  Names: {names_with}")

    print("\n[get_feature_names] ablation='without_id' (all features):")
    names_without = get_feature_names("without_id", include_temporal=True)
    print(f"  Count: {len(names_without)}")
    print(f"  Names: {names_without}")

    print("\n[get_feature_names] frame only, with_id:")
    names_frame_only = get_feature_names("with_id", include_temporal=False)
    print(f"  Count: {len(names_frame_only)}")

    # --- Label leakage validation ---
    print("\n[validate_no_label_leakage] Testing clean feature matrix...")
    combined = pd.concat([frame_df, temp_df], axis=1)
    result_clean = validate_no_label_leakage(combined, SCHEMA_COLS_W01_B2)
    print(f"  PASS (no leakage): {result_clean}")

    print("\n[validate_no_label_leakage] Testing polluted matrix (should FAIL)...")
    polluted = combined.copy()
    polluted["label"] = df_fixture["label"]
    polluted["flag_raw"] = df_fixture["flag_raw"]
    result_polluted = validate_no_label_leakage(polluted, SCHEMA_COLS_W01_B2)
    print(f"  PASS (no leakage): {result_polluted}  ← should be False")

    # --- Summary ---
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    n_frame_with = len(get_feature_names("with_id", include_temporal=False))
    n_frame_without = len(get_feature_names("without_id", include_temporal=False))
    n_temporal = len(TEMPORAL_FEATURES)
    print(f"  Frame features (Baseline-A, with_id):    {n_frame_with}")
    print(f"  Frame features (Baseline-B, without_id): {n_frame_without}")
    print(f"  Temporal features:                       {n_temporal}")
    print(f"  Total (Baseline-A + temporal):           {n_frame_with + n_temporal}")
    print(f"  Total (Baseline-B + temporal):           {n_frame_without + n_temporal}")
    print(f"  Label leakage (clean):   {'PASS' if result_clean else 'FAIL'}")
    print(f"  Label leakage (polluted): {'PASS (unexpected)' if result_polluted else 'FAIL (expected)'}")

    sys.exit(0 if (result_clean and not result_polluted) else 1)
