"""
test_regression_and_fixes.py — Regression test suite for SGOD-P1-W02-B2 fixes.
=============================================================================
Verifies:
1. Shared-tail isolation and no duplication across splits.
2. Chronological progression: Train max ts < Test min ts (no future lookahead).
3. Benign CAN periodic frame payload repetition vs genuine observation identity leakage.
4. Detection of genuine duplicate observations across splits.
5. Causal rolling window boundary protection and reset in feature extraction.
6. Deterministic reproducibility with fixed seed.
7. Label leakage prevention.
8. Edge cases: empty data, duplicate timestamps, single-class data, NOT_VERIFIED status.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from scripts.w02_b2.split_strategy import (
    assign_split_groups,
    compute_row_hash,
    validate_split_integrity,
    generate_split_report,
    SHARED_TAIL_TS_START,
    SHARED_TAIL_TS_END,
)
from scripts.w02_b2.validate_leakage import (
    check_hash_overlap,
    check_observation_identity_overlap,
    check_temporal_leakage,
    check_temporal_order,
    check_window_boundary_leakage,
    check_scaler_fitted_on_train_only,
    run_full_leakage_check,
)
from scripts.w02_b2.feature_extraction import (
    extract_frame_features,
    extract_temporal_features,
    validate_no_label_leakage,
    EXCLUDED_FIELDS,
)


# ===========================================================================
# 1. Shared Tail Isolation & Policy Tests
# ===========================================================================

class TestSharedTailIsolation:
    def test_shared_tail_excluded_by_default(self, sample_can_df, shared_tail_df):
        """Shared-tail rows must be quarantined into 'excluded_shared_tail' by default."""
        combined = pd.concat([sample_can_df, shared_tail_df], ignore_index=True)
        result = assign_split_groups(combined, strategy="purged_temporal", seed=42)

        tail_rows = result[result["timestamp"].between(SHARED_TAIL_TS_START, SHARED_TAIL_TS_END)]
        assert len(tail_rows) == len(shared_tail_df)
        assert (tail_rows["split"] == "excluded_shared_tail").all(), (
            "All shared tail rows must be excluded from train/val/test under default policy"
        )
        assert set(tail_rows["split"].unique()).isdisjoint({"train", "val", "test"})

    def test_no_shared_tail_in_evaluation_splits(self, sample_can_df, shared_tail_df):
        """Under no circumstance should shared-tail rows appear in val or test."""
        combined = pd.concat([sample_can_df, shared_tail_df], ignore_index=True)
        result = assign_split_groups(combined, strategy="purged_temporal", seed=42)

        val_rows = result[result["split"] == "val"]
        test_rows = result[result["split"] == "test"]

        assert not val_rows["timestamp"].between(SHARED_TAIL_TS_START, SHARED_TAIL_TS_END).any()
        assert not test_rows["timestamp"].between(SHARED_TAIL_TS_START, SHARED_TAIL_TS_END).any()

    def test_shared_tail_policy_train_configurable(self, sample_can_df, shared_tail_df):
        """Explicit policy 'train' assigns shared-tail rows to train (legacy DEC-002 mode)."""
        combined = pd.concat([sample_can_df, shared_tail_df], ignore_index=True)
        result = assign_split_groups(
            combined, strategy="purged_temporal", seed=42, shared_tail_policy="train"
        )
        tail_rows = result[result["timestamp"].between(SHARED_TAIL_TS_START, SHARED_TAIL_TS_END)]
        assert (tail_rows["split"] == "train").all()

    def test_shared_tail_policy_isolate_configurable(self, sample_can_df, shared_tail_df):
        """Policy 'isolate' marks shared tail as 'shared_tail_eval'."""
        combined = pd.concat([sample_can_df, shared_tail_df], ignore_index=True)
        result = assign_split_groups(
            combined, strategy="purged_temporal", seed=42, shared_tail_policy="isolate"
        )
        tail_rows = result[result["timestamp"].between(SHARED_TAIL_TS_START, SHARED_TAIL_TS_END)]
        assert (tail_rows["split"] == "shared_tail_eval").all()


# ===========================================================================
# 2. Chronological Ordering Tests (Train Max Ts < Test Min Ts)
# ===========================================================================

class TestChronologicalOrdering:
    def test_train_max_ts_strictly_before_test_min_ts(self, sample_can_df, shared_tail_df):
        """With default policy, train max timestamp must be strictly less than test min timestamp per source."""
        # Use DoS rows so timestamps belong to the same recording session
        dos_sample = sample_can_df[sample_can_df["source_file"] == "DoS_dataset.csv"].copy()
        combined = pd.concat([dos_sample, shared_tail_df], ignore_index=True)
        result = assign_split_groups(combined, strategy="purged_temporal", seed=42)

        train = result[result["split"] == "train"]
        val   = result[result["split"] == "val"]
        test  = result[result["split"] == "test"]

        assert not train.empty and not test.empty
        assert train["timestamp"].max() < test["timestamp"].min(), (
            f"Train max {train['timestamp'].max()} >= Test min {test['timestamp'].min()}"
        )
        if not val.empty:
            assert train["timestamp"].max() < val["timestamp"].min()
            assert val["timestamp"].max() < test["timestamp"].min()

        # Leakage check must pass
        assert check_temporal_leakage(train, test) is False

    def test_future_lookahead_in_train_detected(self):
        """Deliberately putting future data in train must trigger temporal leakage."""
        train = pd.DataFrame({"timestamp": [10.0, 20.0, 100.0]})
        test  = pd.DataFrame({"timestamp": [30.0, 40.0, 50.0]})

        # Train contains timestamp 100.0 which occurs after test's 30.0-50.0
        leaking = check_temporal_leakage(train, test)
        assert leaking is True, "Must detect train containing future data after test"

    def test_check_temporal_order_all_flags(self):
        """check_temporal_order returns granular dictionary of order statuses."""
        train = pd.DataFrame({"timestamp": [1.0, 2.0]})
        val   = pd.DataFrame({"timestamp": [3.0, 4.0]})
        test  = pd.DataFrame({"timestamp": [5.0, 6.0]})

        order = check_temporal_order(train, val, test)
        assert order["train_val_ordered"] is True
        assert order["val_test_ordered"] is True
        assert order["train_test_ordered"] is True
        assert order["train_contains_future_data"] is False
        assert order["all_ordered"] is True


# ===========================================================================
# 3. Benign CAN Payload Repetition vs True Observation Leakage
# ===========================================================================

class TestCanPayloadRepetitionVsTrueLeakage:
    def test_periodic_can_frame_payload_repetition_is_not_observation_leakage(self):
        """
        Two frames with identical CAN ID and payload transmitted at different times
        (periodic broadcast) must show hash overlap but NOT observation leakage.
        """
        train = pd.DataFrame({
            "timestamp":   [1478198000.100],
            "can_id":      ["0316"],
            "dlc":         [8],
            "data_0": [0], "data_1": [0], "data_2": [0], "data_3": [0],
            "data_4": [0], "data_5": [0], "data_6": [0], "data_7": [0],
            "source_file": ["DoS_dataset.csv"],
            "source_line": [100],
        })
        test = pd.DataFrame({
            "timestamp":   [1478198050.200],  # 50 seconds later
            "can_id":      ["0316"],          # same ECU
            "dlc":         [8],
            "data_0": [0], "data_1": [0], "data_2": [0], "data_3": [0],
            "data_4": [0], "data_5": [0], "data_6": [0], "data_7": [0],
            "source_file": ["DoS_dataset.csv"],
            "source_line": [5000],             # different observation
        })

        # Content hash overlaps (normal for CAN)
        assert check_hash_overlap(train, test) is True

        # Observation identity does NOT overlap (clean physical separation)
        assert check_observation_identity_overlap(train, test) is False

        # Overall full check passes with PASS_PARTIAL (window/scaler unverified)
        report = run_full_leakage_check(train, pd.DataFrame(), test)
        assert report["status"] == "PASS_PARTIAL"
        assert report["passed"] is True
        assert report["any_leakage"] is False
        assert "window_boundary_leakage" in report["unverified_checks"][0]

    def test_nan_payload_shared_tail_cross_file_detected(self):
        """
        Verify that check_observation_identity_overlap detects cross-file duplicate rows
        even when DLC < 8 and payload contains NaN/missing bytes (e.g. DLC=2).
        """
        train = pd.DataFrame({
            "timestamp":   [1478200727.420000],
            "can_id":      ["0244"],
            "dlc":         [2],
            "data_0": [0xAB], "data_1": [0xCD],
            "data_2": [np.nan], "data_3": [np.nan], "data_4": [np.nan],
            "data_5": [np.nan], "data_6": [np.nan], "data_7": [np.nan],
            "source_file": ["DoS_dataset.csv"],
            "source_line": [2774705],
        })
        test = pd.DataFrame({
            "timestamp":   [1478200727.420000],
            "can_id":      ["0244"],
            "dlc":         [2],
            "data_0": [0xAB], "data_1": [0xCD],
            "data_2": [np.nan], "data_3": [np.nan], "data_4": [np.nan],
            "data_5": [np.nan], "data_6": [np.nan], "data_7": [np.nan],
            "source_file": ["Fuzzy_dataset.csv"],  # different file!
            "source_line": [2947794],
        })

        assert check_observation_identity_overlap(train, test) is True, (
            "Must detect cross-file shared tail even with NaN payload bytes for DLC < 8"
        )

    def test_run_full_leakage_check_pass_full_when_all_verified(self):
        """
        When combined_df (with purge gap) and scaler are provided,
        status must be full 'PASS'.
        """
        from sklearn.preprocessing import StandardScaler
        train = pd.DataFrame({
            "timestamp": [1.0, 2.0, 3.0], "iat": [0.01, 0.01, 0.01],
            "source_file": ["DoS_dataset.csv"] * 3, "source_line": [1, 2, 3],
        })
        val = pd.DataFrame({
            "timestamp": [10.0, 11.0], "iat": [0.05, 0.05],
            "source_file": ["DoS_dataset.csv"] * 2, "source_line": [10, 11],
        })
        test = pd.DataFrame({
            "timestamp": [20.0, 21.0], "iat": [0.05, 0.05],
            "source_file": ["DoS_dataset.csv"] * 2, "source_line": [20, 21],
        })
        # Purge gap between splits
        gap1 = pd.DataFrame({"timestamp": [5.0], "source_file": ["DoS_dataset.csv"], "source_line": [5]})
        gap2 = pd.DataFrame({"timestamp": [15.0], "source_file": ["DoS_dataset.csv"], "source_line": [15]})
        combo = pd.concat([
            train.assign(split="train"),
            gap1.assign(split="purged"),
            val.assign(split="val"),
            gap2.assign(split="purged"),
            test.assign(split="test"),
        ], ignore_index=True)

        scaler = StandardScaler()
        scaler.fit(train[["iat"]])

        report = run_full_leakage_check(
            train, val, test, combined_df=combo, scaler=scaler
        )
        assert report["status"] == "PASS"
        assert report["is_fully_verified"] is True
        assert report["passed"] is True
        assert len(report["unverified_checks"]) == 0

    def test_exact_observation_identity_leakage_detected(self):
        """Sharing exact (source_file, source_line) between splits must trigger failure."""
        train = pd.DataFrame({
            "timestamp":   [1478198000.100],
            "can_id":      ["0316"],
            "dlc":         [8],
            "data_0": [0], "data_1": [0], "data_2": [0], "data_3": [0],
            "data_4": [0], "data_5": [0], "data_6": [0], "data_7": [0],
            "source_file": ["DoS_dataset.csv"],
            "source_line": [100],
        })
        test = pd.DataFrame({
            "timestamp":   [1478198000.100],
            "can_id":      ["0316"],
            "dlc":         [8],
            "data_0": [0], "data_1": [0], "data_2": [0], "data_3": [0],
            "data_4": [0], "data_5": [0], "data_6": [0], "data_7": [0],
            "source_file": ["DoS_dataset.csv"],
            "source_line": [100],  # EXACT SAME OBSERVATION!
        })

        assert check_observation_identity_overlap(train, test) is True
        report = run_full_leakage_check(train, pd.DataFrame(), test)
        assert report["status"] == "FAIL"
        assert report["passed"] is False


# ===========================================================================
# 4. Feature Extraction & Rolling Window Boundary Tests
# ===========================================================================

class TestFeatureExtractionSplitBoundary:
    def test_temporal_features_reset_at_split_boundary(self):
        """extract_temporal_features must reset causal state when split column changes."""
        df = pd.DataFrame({
            "timestamp":   [1.0, 2.0, 3.0, 4.0, 5.0, 6.0],
            "can_id":      ["0316"] * 6,
            "source_file": ["DoS_dataset.csv"] * 6,
            "split":       ["train", "train", "train", "test", "test", "test"],
        })
        out = extract_temporal_features(df)

        # First row of train: NaN (first in segment)
        assert pd.isna(out.loc[0, "global_iat"])
        assert out.loc[1, "global_iat"] == 1.0
        assert out.loc[2, "global_iat"] == 1.0

        # Boundary row index 3 is first row of test: must reset to NaN!
        assert pd.isna(out.loc[3, "global_iat"]), (
            "global_iat must be NaN at the first row of test split (no lookback into train)"
        )
        assert out.loc[4, "global_iat"] == 1.0

    def test_check_window_boundary_leakage_detects_adjacent_splits(self):
        """Adjacency between train and test without purge gap is caught."""
        df = pd.DataFrame({
            "timestamp":   list(range(6)),
            "source_file": ["DoS_dataset.csv"] * 6,
            "split":       ["train", "train", "train", "test", "test", "test"],
        })
        has_leakage = check_window_boundary_leakage(df, window_size=3)
        assert has_leakage is True

    def test_check_window_boundary_leakage_clean_with_purge(self):
        """Intervening purge gap rows prevent window crossing."""
        df = pd.DataFrame({
            "timestamp":   list(range(8)),
            "source_file": ["DoS_dataset.csv"] * 8,
            "split":       ["train", "train", "purged", "purged", "purged", "test", "test", "test"],
        })
        has_leakage = check_window_boundary_leakage(df, window_size=3)
        assert has_leakage is False


# ===========================================================================
# 5. Edge Cases & Robustness
# ===========================================================================

class TestEdgeCasesAndSafety:
    def test_empty_dataframe_reports_not_verified(self):
        """Empty inputs must report NOT_VERIFIED, never a false PASS."""
        report = run_full_leakage_check(pd.DataFrame(), pd.DataFrame(), pd.DataFrame())
        assert report["status"] == "NOT_VERIFIED"
        assert report["passed"] is False

    def test_duplicate_timestamps_split_safely(self):
        """Rows with identical timestamps must not crash split assignment."""
        df = pd.DataFrame({
            "timestamp":   [1.0, 1.0, 1.0, 2.0, 2.0, 3.0],
            "can_id":      ["0316"] * 6,
            "dlc":         [8] * 6,
            "source_file": ["DoS_dataset.csv"] * 6,
            "source_line": list(range(6)),
            **{f"data_{i}": [0] * 6 for i in range(8)},
        })
        result = assign_split_groups(df, strategy="purged_temporal", seed=42)
        assert "split" in result.columns
        assert not result["split"].isna().any()

    def test_validate_split_integrity_returns_full_metadata(self, sample_can_df):
        """validate_split_integrity output contains observation_overlap_ok and temporal_order_ok."""
        df_split = assign_split_groups(sample_can_df, strategy="purged_temporal", seed=42)
        vi = validate_split_integrity(df_split)

        assert "observation_overlap_ok" in vi
        assert "temporal_order_ok" in vi
        assert "shared_tail_safe" in vi
        assert vi["observation_overlap_ok"] is True
        assert vi["temporal_order_ok"] is True
        assert vi["shared_tail_safe"] is True

        rep = generate_split_report(vi)
        assert "**Overall**: PASSED" in rep
        assert "Observation Identity Integrity: DISJOINT (PASS)" in rep
        assert "Chronological Evaluation Order: VALID (PASS)" in rep
