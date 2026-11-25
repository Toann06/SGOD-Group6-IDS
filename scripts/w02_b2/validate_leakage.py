"""
Leakage Validation for CAN Bus IDS — SGOD-P1-W02-B2
=====================================================
Comprehensive data leakage validation for train/val/test splits.

Key Capabilities
----------------
1. check_observation_identity_overlap:
   True observation identity check via (source_file, source_line) and
   (timestamp, can_id, dlc, payload) to detect physical duplicate records
   and shared-tail leakage across files.
2. check_hash_overlap:
   Checks identical payload content (retains API compatibility).
   Distinguishes benign CAN periodic frame repetition from actual leakage.
3. check_temporal_leakage & check_temporal_order:
   Ensures strict forward-looking chronological progression (train <= val <= test)
   and detects if train contains future lookahead data relative to val/test.
4. check_window_boundary_leakage:
   Ensures causal rolling windows never cross split boundaries without purge gaps.
5. check_scaler_fitted_on_train_only:
   Verifies normalizers/scalers are fitted strictly on train data.
6. run_full_leakage_check:
   Executes all checks and generates an audit report with PASS/FAIL/NOT_VERIFIED states.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd

from scripts.w02_b2.split_strategy import compute_row_hash, HASH_COLS

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 1. check_observation_identity_overlap (Genuine Data Leakage)
# ---------------------------------------------------------------------------

def check_observation_identity_overlap(
    train_df: pd.DataFrame,
    test_df: pd.DataFrame,
    id_cols: Optional[List[str]] = None,
) -> bool:
    """
    Check whether any physical observation in test_df is identical to a row in train_df.

    Parameters
    ----------
    train_df, test_df : pd.DataFrame
        DataFrames representing splits to compare.
    id_cols : list[str] | None
        Columns defining observation identity.
        If None, prefers ('source_file', 'source_line') if present.
        Also checks exact (timestamp, can_id, payload) match across different files
        to detect leaked shared-tail traces.

    Returns
    -------
    True  if genuine observation leakage IS detected.
    False if clean.
    """
    if train_df.empty or test_df.empty:
        return False

    # Check 1: Provenance identity (source_file, source_line)
    provenance_cols = ["source_file", "source_line"]
    if all(c in train_df.columns and c in test_df.columns for c in provenance_cols):
        train_ids = set(zip(train_df["source_file"], train_df["source_line"]))
        test_ids  = set(zip(test_df["source_file"],  test_df["source_line"]))
        overlap = train_ids & test_ids
        if overlap:
            logger.error(
                "check_observation_identity_overlap: %d shared (source_file, source_line) "
                "record(s) found between splits! Example: %s",
                len(overlap), next(iter(overlap))
            )
            return True

    # Check 2: Exact timestamp + CAN ID + payload match across files (shared-tail leakage)
    exact_cols = ["timestamp", "can_id", "dlc"]
    payload_cols = [c for c in HASH_COLS if c in train_df.columns and c in test_df.columns]
    raw_cols = [c for c in (exact_cols + payload_cols) if c in train_df.columns and c in test_df.columns]
    match_cols = list(dict.fromkeys(raw_cols))  # deduplicate preserving order

    if len(match_cols) >= 3 and "timestamp" in match_cols:
        def _to_normalized_set(df: pd.DataFrame, cols: List[str]) -> set:
            sub = df[cols].copy()
            for c in cols:
                if c == "timestamp":
                    # Round timestamp to 6 decimal places to prevent float precision mismatches
                    sub[c] = pd.to_numeric(sub[c], errors="coerce").round(6).fillna(-1.0)
                elif c in ("can_id", "source_file"):
                    sub[c] = sub[c].astype(str).str.strip().str.lower()
                else:
                    # Replace NaN/None with sentinel so that missing payload bytes compare equal
                    sub[c] = sub[c].fillna("__NAN__")
            return set(map(tuple, sub.to_numpy()))

        train_tuples = _to_normalized_set(train_df, match_cols)
        test_tuples  = _to_normalized_set(test_df, match_cols)
        exact_overlap = train_tuples & test_tuples
        if exact_overlap:
            logger.error(
                "check_observation_identity_overlap: %d exact timestamp+payload observation(s) "
                "found in both train and test! Cross-file shared tail or duplicate trace leak.",
                len(exact_overlap)
            )
            return True

    logger.info("check_observation_identity_overlap: PASS — no observation overlap.")
    return False


# ---------------------------------------------------------------------------
# 2. check_hash_overlap (CAN Content Hash Overlap)
# ---------------------------------------------------------------------------

def check_hash_overlap(
    train_df: pd.DataFrame,
    test_df: pd.DataFrame,
    hash_cols: Optional[list] = None,
) -> bool:
    """
    Check whether any row in test_df has the same payload content hash as train_df.

    Note on Automotive CAN Bus:
    ---------------------------
    CAN ECUs broadcast periodic status messages (e.g., speed, gear, RPM) at fixed
    intervals (10-100Hz). When vehicle state does not change, frames contain identical
    CAN IDs and payload bytes over time. Content hash collisions across time are
    normal CAN behavior and do NOT inherently indicate data leakage unless they share
    identical timestamps, source identities, or causal feature windows.

    Parameters
    ----------
    train_df, test_df : split DataFrames to compare
    hash_cols         : columns to use for hashing; defaults to HASH_COLS

    Returns
    -------
    True  if content hash overlap IS detected.
    False if no overlap.
    """
    if train_df.empty or test_df.empty:
        return False

    cols = hash_cols if hash_cols is not None else HASH_COLS
    if not all(c in train_df.columns for c in cols) or not all(c in test_df.columns for c in cols):
        logger.info("check_hash_overlap: required hash columns not in both splits; skipping content hash check.")
        return False

    train_hashes = set(compute_row_hash(train_df, hash_cols))
    test_hashes  = set(compute_row_hash(test_df,  hash_cols))

    overlap = train_hashes & test_hashes
    if overlap:
        logger.info(
            "check_hash_overlap: %d payload hash(es) repeated across splits. "
            "(Note: Normal for periodic CAN broadcast messages).", len(overlap)
        )
        return True

    logger.info("check_hash_overlap: No content hash overlap.")
    return False


# ---------------------------------------------------------------------------
# 3. check_temporal_leakage & check_temporal_order
# ---------------------------------------------------------------------------

def check_temporal_leakage(
    train_df: pd.DataFrame,
    test_df: pd.DataFrame,
    timestamp_col: str = "timestamp",
    tolerance: float = 0.0,
) -> bool:
    """
    Check whether test timestamps leak into train, or train contains future data.

    Temporal leakage is detected if:
    a) Any test timestamp falls strictly within the training time window [train_min, train_max].
    b) Training data occurs strictly AFTER the earliest test timestamp (future lookahead).

    When 'source_file' is present in both DataFrames, checks are evaluated per source
    to respect independent recording sessions.

    Parameters
    ----------
    train_df, test_df : split DataFrames
    timestamp_col     : name of timestamp column
    tolerance         : seconds of allowed boundary overlap

    Returns
    -------
    True  if temporal leakage IS detected.
    False if clean.
    """
    if timestamp_col not in train_df.columns or timestamp_col not in test_df.columns:
        logger.warning("check_temporal_leakage: '%s' column not found.", timestamp_col)
        return False

    if train_df.empty or test_df.empty:
        logger.warning("check_temporal_leakage: Empty timestamp series in train or test.")
        return False

    has_source = "source_file" in train_df.columns and "source_file" in test_df.columns
    if has_source:
        common_sources = set(train_df["source_file"].dropna().unique()) & set(test_df["source_file"].dropna().unique())
        sources = list(common_sources) if common_sources else [None]
    else:
        sources = [None]

    for src in sources:
        train_sub = train_df[train_df["source_file"] == src] if src is not None else train_df
        test_sub  = test_df[test_df["source_file"] == src] if src is not None else test_df

        train_ts = pd.to_numeric(train_sub[timestamp_col], errors="coerce").dropna()
        test_ts  = pd.to_numeric(test_sub[timestamp_col],  errors="coerce").dropna()

        if train_ts.empty or test_ts.empty:
            continue

        train_min, train_max = train_ts.min(), train_ts.max()
        test_min, test_max   = test_ts.min(), test_ts.max()

        # Condition A: Test timestamps interleaved inside training window
        interleaved = test_ts[
            (test_ts > train_min + tolerance) & (test_ts < train_max - tolerance)
        ]
        if not interleaved.empty:
            logger.warning(
                "check_temporal_leakage: %d test timestamp(s) fall within training window [%.6f, %.6f] (source=%s)",
                len(interleaved), train_min, train_max, src
            )
            return True

        # Condition B: Train max exceeds test min (train contains future data)
        if train_max > test_min + tolerance:
            logger.warning(
                "check_temporal_leakage: Train max timestamp (%.6f) > Test min timestamp (%.6f) (source=%s)! "
                "Train contains future data.", train_max, test_min, src
            )
            return True

    logger.info("check_temporal_leakage: PASS — forward chronological progression confirmed.")
    return False


def check_temporal_order(
    train_df: pd.DataFrame,
    val_df: pd.DataFrame,
    test_df: pd.DataFrame,
    timestamp_col: str = "timestamp",
    tolerance: float = 0.0,
) -> Dict[str, Any]:
    """
    Verify chronological progression across train, val, and test splits.

    Evaluated per source_file if present, or globally if single-source.

    Returns
    -------
    dict with status flags for:
      - train_val_ordered: bool | 'NOT_VERIFIED'
      - val_test_ordered:  bool | 'NOT_VERIFIED'
      - train_test_ordered: bool | 'NOT_VERIFIED'
      - train_contains_future_data: bool
      - all_ordered: bool
    """
    result: Dict[str, Any] = {
        "train_val_ordered": "NOT_VERIFIED",
        "val_test_ordered":  "NOT_VERIFIED",
        "train_test_ordered": "NOT_VERIFIED",
        "train_contains_future_data": False,
        "all_ordered": False,
    }

    if timestamp_col not in train_df.columns:
        return result

    if train_df.empty or test_df.empty:
        return result

    has_source = "source_file" in train_df.columns and "source_file" in test_df.columns
    if has_source:
        sources = list(set(train_df["source_file"].dropna().unique()) | set(test_df["source_file"].dropna().unique()))
    else:
        sources = [None]

    all_tv_ok = True
    all_vt_ok = True
    all_tt_ok = True
    has_tv_data = False
    has_vt_data = False
    has_tt_data = False

    for src in sources:
        t_sub = train_df[train_df["source_file"] == src] if src is not None else train_df
        v_sub = val_df[val_df["source_file"] == src] if (src is not None and not val_df.empty and "source_file" in val_df.columns) else val_df
        e_sub = test_df[test_df["source_file"] == src] if src is not None else test_df

        train_ts = pd.to_numeric(t_sub[timestamp_col], errors="coerce").dropna() if not t_sub.empty else pd.Series(dtype=float)
        val_ts   = pd.to_numeric(v_sub[timestamp_col], errors="coerce").dropna() if not v_sub.empty else pd.Series(dtype=float)
        test_ts  = pd.to_numeric(e_sub[timestamp_col], errors="coerce").dropna() if not e_sub.empty else pd.Series(dtype=float)

        if not train_ts.empty and not test_ts.empty:
            has_tt_data = True
            if train_ts.max() > test_ts.min() + tolerance:
                all_tt_ok = False

        if not train_ts.empty and not val_ts.empty:
            has_tv_data = True
            if train_ts.max() > val_ts.min() + tolerance:
                all_tv_ok = False

        if not val_ts.empty and not test_ts.empty:
            has_vt_data = True
            if val_ts.max() > test_ts.min() + tolerance:
                all_vt_ok = False

    result["train_val_ordered"] = all_tv_ok if has_tv_data else "NOT_VERIFIED"
    result["val_test_ordered"]  = all_vt_ok if has_vt_data else "NOT_VERIFIED"
    result["train_test_ordered"] = all_tt_ok if has_tt_data else "NOT_VERIFIED"
    result["train_contains_future_data"] = not all_tt_ok if has_tt_data else False

    result["all_ordered"] = bool(
        all_tt_ok and
        (all_tv_ok or not has_tv_data) and
        (all_vt_ok or not has_vt_data) and
        has_tt_data
    )

    return result


# ---------------------------------------------------------------------------
# 4. check_window_boundary_leakage
# ---------------------------------------------------------------------------

def check_window_boundary_leakage(
    df: pd.DataFrame,
    window_size: int,
    split_col: str = "split",
    timestamp_col: str = "timestamp",
) -> bool:
    """
    Check whether a causal rolling window would cross an evaluation split boundary.

    Within each contiguous source_file, sorted by timestamp, checks if any window of
    `window_size` consecutive rows contains transitions between active evaluation
    splits ('train', 'val', 'test') without intervening purge gap rows.

    Parameters
    ----------
    df          : DataFrame with split_col and optionally timestamp_col, source_file
    window_size : number of consecutive rows in the rolling window
    split_col   : column holding split labels

    Returns
    -------
    True  if window crosses between evaluation splits without gap (leakage).
    False if clean.
    """
    if split_col not in df.columns or df.empty or window_size <= 1:
        return False

    sort_cols = []
    if "source_file" in df.columns:
        sort_cols.append("source_file")
    if timestamp_col in df.columns:
        sort_cols.append(timestamp_col)

    if sort_cols:
        df_sorted = df.sort_values(sort_cols, kind="stable").reset_index(drop=True)
    else:
        df_sorted = df.reset_index(drop=True)

    sources = df_sorted["source_file"].unique() if "source_file" in df_sorted.columns else ["__single__"]

    for src in sources:
        if "source_file" in df_sorted.columns:
            sub = df_sorted[df_sorted["source_file"] == src]
        else:
            sub = df_sorted

        splits_arr = sub[split_col].values
        n = len(splits_arr)
        if n < window_size:
            continue

        for i in range(n - window_size + 1):
            window = splits_arr[i : i + window_size]
            active_splits = set(s for s in window if s in ("train", "val", "test"))
            if len(active_splits) > 1:
                logger.warning(
                    "check_window_boundary_leakage: rolling window [%d:%d] crosses active splits %s "
                    "without purge gap in source %s!", i, i + window_size, active_splits, src
                )
                return True

    logger.info("check_window_boundary_leakage: PASS — no window boundary crossing.")
    return False


# ---------------------------------------------------------------------------
# 5. check_scaler_fitted_on_train_only
# ---------------------------------------------------------------------------

def check_scaler_fitted_on_train_only(
    scaler: Any,
    train_df: pd.DataFrame,
    val_df: pd.DataFrame,
    feature_col: str = "iat",
) -> Union[bool, str]:
    """
    Verify scaler statistics match training data only (not validation data).

    Parameters
    ----------
    scaler      : fitted sklearn-compatible scaler (must expose .mean_ or .scale_)
    train_df    : training DataFrame
    val_df      : validation DataFrame
    feature_col : column name to test

    Returns
    -------
    True            if scaler appears fitted on train only
    False           if scaler matches val data better (leakage suspected)
    'NOT_VERIFIED'  if data is missing or scaler lacks statistical attributes
    """
    if train_df.empty or val_df.empty:
        return "NOT_VERIFIED"

    if feature_col not in train_df.columns or feature_col not in val_df.columns:
        logger.warning("check_scaler_fitted_on_train_only: '%s' not found.", feature_col)
        return "NOT_VERIFIED"

    if not hasattr(scaler, "mean_"):
        logger.info("check_scaler_fitted_on_train_only: scaler has no mean_ attribute.")
        return "NOT_VERIFIED"

    train_series = pd.to_numeric(train_df[feature_col], errors="coerce").dropna()
    val_series   = pd.to_numeric(val_df[feature_col],   errors="coerce").dropna()

    if train_series.empty or val_series.empty:
        return "NOT_VERIFIED"

    train_mean = float(train_series.mean())
    val_mean   = float(val_series.mean())
    scaler_mean = float(np.atleast_1d(scaler.mean_)[0])

    err_train = abs(scaler_mean - train_mean)
    err_val   = abs(scaler_mean - val_mean)

    if err_train <= err_val + 1e-6:
        logger.info(
            "check_scaler_fitted_on_train_only: PASS (train_err=%.4f, val_err=%.4f)",
            err_train, err_val
        )
        return True

    logger.warning(
        "check_scaler_fitted_on_train_only: scaler mean (%.4f) closer to val (%.4f) than train (%.4f)!",
        scaler_mean, val_mean, train_mean
    )
    return False


# ---------------------------------------------------------------------------
# 6. run_full_leakage_check
# ---------------------------------------------------------------------------

def run_full_leakage_check(
    train_df: pd.DataFrame,
    val_df: pd.DataFrame,
    test_df: pd.DataFrame,
    hash_cols: Optional[list] = None,
    timestamp_col: str = "timestamp",
    window_size: int = 10,
    scaler: Optional[Any] = None,
    combined_df: Optional[pd.DataFrame] = None,
) -> Dict[str, Any]:
    """
    Run full leakage audit across train, val, and test splits.

    Returns
    -------
    dict with audit results, status ('PASS'|'FAIL'|'NOT_VERIFIED'), and details.
    """
    # 1. Observation Identity Overlap (Genuine Leakage)
    obs_tt = check_observation_identity_overlap(train_df, test_df)
    obs_tv = check_observation_identity_overlap(train_df, val_df)
    obs_vt = check_observation_identity_overlap(val_df,   test_df)
    any_obs_leakage = any([obs_tt, obs_tv, obs_vt])

    # 2. Temporal Ordering & Future Data Protection
    temp_tt = check_temporal_leakage(train_df, test_df, timestamp_col)
    temp_tv = check_temporal_leakage(train_df, val_df,  timestamp_col)
    order_report = check_temporal_order(train_df, val_df, test_df, timestamp_col)
    any_temp_leakage = temp_tt or temp_tv or (order_report.get("train_contains_future_data", False))

    # 3. CAN Periodic Content Hash Overlap (Benign payload repetitions)
    h_tt = check_hash_overlap(train_df, test_df, hash_cols)
    h_tv = check_hash_overlap(train_df, val_df,  hash_cols)
    h_vt = check_hash_overlap(val_df,   test_df, hash_cols)

    # 4. Window Boundary Leakage
    if combined_df is not None:
        window_leakage = check_window_boundary_leakage(
            combined_df, window_size, timestamp_col=timestamp_col
        )
    else:
        # Window boundary requires contiguous timeline including purge gaps
        window_leakage = "NOT_VERIFIED"

    # 5. Scaler fitting check
    scaler_check = (
        check_scaler_fitted_on_train_only(scaler, train_df, val_df)
        if scaler is not None else "NOT_VERIFIED"
    )

    # Status Determination:
    # Critical leakage faults: Observation identity overlap, temporal future lookahead,
    # window boundary breach, or scaler leakage
    critical_faults = (
        any_obs_leakage
        or any_temp_leakage
        or (window_leakage is True)
        or (scaler_check is False)
    )

    unverified_checks = []
    if window_leakage == "NOT_VERIFIED":
        unverified_checks.append("window_boundary_leakage (requires combined_df with purge gaps)")
    if scaler_check == "NOT_VERIFIED":
        unverified_checks.append("scaler_fitted_on_train_only (scaler not provided or insufficient data)")

    if train_df.empty or test_df.empty:
        status = "NOT_VERIFIED"
        passed = False
    elif critical_faults:
        status = "FAIL"
        passed = False
    elif unverified_checks:
        # Core checks passed; secondary checks unverified
        status = "PASS_PARTIAL"
        passed = True
    else:
        # All checks fully executed and clean
        status = "PASS"
        passed = True

    checks = {
        # Observation identity checks (critical)
        "observation_leakage_train_test": obs_tt,
        "observation_leakage_train_val":  obs_tv,
        "observation_leakage_val_test":   obs_vt,
        # Temporal checks (critical)
        "temporal_leakage_train_test": temp_tt,
        "temporal_leakage_train_val":  temp_tv,
        "temporal_order":              order_report,
        # Window boundary checks (critical)
        "window_boundary_leakage":     window_leakage,
        # Content hash overlap (informational for CAN periodic messages)
        "hash_overlap_train_test":     h_tt,
        "hash_overlap_train_val":      h_tv,
        "hash_overlap_val_test":       h_vt,
        "scaler_fitted_on_train_only": scaler_check,
    }

    report: Dict[str, Any] = {
        **checks,
        "status":            status,
        "passed":            passed,
        "any_leakage":       critical_faults,
        "unverified_checks": unverified_checks,
        "is_fully_verified": (status == "PASS"),
        "checks":            checks,
        "notes": [
            "Content hash overlap is expected in CAN networks due to periodic message broadcasts.",
            "Observation identity overlap and chronological ordering are the primary determinants of leakage.",
        ],
    }

    if status == "FAIL":
        logger.error("run_full_leakage_check: CRITICAL LEAKAGE DETECTED: %s", checks)
    elif status == "NOT_VERIFIED":
        logger.warning("run_full_leakage_check: NOT_VERIFIED (insufficient data to verify).")
    elif status == "PASS_PARTIAL":
        logger.info("run_full_leakage_check: PASS_PARTIAL — core checks passed; unverified: %s", unverified_checks)
    else:
        logger.info("run_full_leakage_check: PASS — all checks fully verified with no leakage.")

    return report
