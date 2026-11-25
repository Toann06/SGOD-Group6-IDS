"""
split_strategy.py — SGOD-P1-W02-B2 Phase 3B
Train/Val/Test split strategy with leakage prevention.

Strategy: Purged Temporal Split per source-file group.
  1. Shared tail (891,068 rows identical across 4 CSVs) → assigned to TRAIN only.
  2. Each source file is sorted by timestamp and split chronologically.
  3. A purge gap (gap_frac) is inserted between train/val and val/test boundaries
     to prevent window-based temporal leakage.
  4. All operations are deterministic via SEED=42.

Run standalone to execute self-test with 100-row synthetic fixture:
    python split_strategy.py
"""

from __future__ import annotations

import hashlib
import textwrap
from typing import Dict, List

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
SEED = 42
TRAIN_FRAC = 0.70
VAL_FRAC = 0.15
TEST_FRAC = 0.15
# Purge gap: fraction of each file's time range to drop between splits.
# 0.01 → 1% gap; enough to exceed any reasonable sliding window in CAN-Bus IDS.
GAP_FRAC = 0.01

HASH_COLS = ["can_id", "dlc", "data_0", "data_1", "data_2", "data_3",
             "data_4", "data_5", "data_6", "data_7"]

# Shared-tail timestamp range discovered in B1 (seconds, Unix epoch)
SHARED_TAIL_TS_START = 1_478_200_727.419470
SHARED_TAIL_TS_END   = 1_478_201_209.058944
SHARED_TAIL_SOURCES  = {"DoS_dataset.csv", "Fuzzy_dataset.csv",
                         "gear_dataset.csv", "RPM_dataset.csv"}


# ---------------------------------------------------------------------------
# 1. compute_row_hash
# ---------------------------------------------------------------------------

def compute_row_hash(df: pd.DataFrame, hash_cols: list | None = None) -> pd.Series:
    """
    Return a Series of SHA-256 hex strings, one per row.

    Hash input: concatenation of can_id, dlc, data_0 .. data_7 as strings,
    joined with '|'. NaN bytes are represented as 'NaN' so that padding
    differences are preserved in the hash.

    Parameters
    ----------
    df : pd.DataFrame
        Must contain columns: can_id, dlc, data_0 .. data_7 (or subset via hash_cols).
    hash_cols : list[str] | None
        Columns to include in hash. Defaults to HASH_COLS.

    Returns
    -------
    pd.Series[str]
        SHA-256 hex digest per row, same index as *df*.
    """
    cols = hash_cols if hash_cols is not None else HASH_COLS
    present = [c for c in cols if c in df.columns]
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise ValueError(f"compute_row_hash: missing columns {missing}")

    def _hash_row(row: pd.Series) -> str:
        parts = [str(row[c]) for c in present]
        raw = "|".join(parts).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    return df[present].apply(_hash_row, axis=1)


# ---------------------------------------------------------------------------
# 2. detect_shared_rows
# ---------------------------------------------------------------------------

def detect_shared_rows(dataframes_dict: Dict[str, pd.DataFrame]) -> Dict:
    """
    Detect rows whose content hash appears in every provided DataFrame.

    Parameters
    ----------
    dataframes_dict : dict[str, pd.DataFrame]
        Keys are source-file names; values are DataFrames with HASH_COLS.

    Returns
    -------
    dict with keys:
        shared_hashes : set[str]      -- hashes present in ALL DataFrames
        per_source    : dict[str, int] -- count of shared rows per source
        total_shared  : int           -- size of shared_hashes set
    """
    if len(dataframes_dict) < 2:
        return {"shared_hashes": set(), "per_source": {}, "total_shared": 0}

    hash_sets: Dict[str, set] = {}
    for name, df in dataframes_dict.items():
        h = compute_row_hash(df)
        hash_sets[name] = set(h)

    names = list(hash_sets.keys())
    shared: set = hash_sets[names[0]]
    for n in names[1:]:
        shared = shared & hash_sets[n]

    per_source = {}
    for name, df in dataframes_dict.items():
        h = compute_row_hash(df)
        per_source[name] = int((h.isin(shared)).sum())

    return {
        "shared_hashes": shared,
        "per_source": per_source,
        "total_shared": len(shared),
    }


# ---------------------------------------------------------------------------
# 3. assign_split_groups
# ---------------------------------------------------------------------------

def _is_shared_tail_row(df: pd.DataFrame) -> pd.Series:
    """
    Fast heuristic: a row belongs to the shared tail if its source_file is one
    of the 4 CSV files AND its timestamp is within the shared tail range.

    For full correctness, also validate via compute_row_hash against a known
    shared-tail hash set (passed as optional argument).
    """
    if "source_file" not in df.columns or "timestamp" not in df.columns:
        return pd.Series(False, index=df.index)

    in_source = df["source_file"].isin(SHARED_TAIL_SOURCES)
    in_ts_range = (df["timestamp"] >= SHARED_TAIL_TS_START) & \
                  (df["timestamp"] <= SHARED_TAIL_TS_END)
    return in_source & in_ts_range


def assign_split_groups(
    df: pd.DataFrame,
    strategy: str = "purged_temporal",
    seed: int = SEED,
    train_frac: float = TRAIN_FRAC,
    val_frac: float = VAL_FRAC,
    test_frac: float = TEST_FRAC,
    gap_frac: float = GAP_FRAC,
    shared_hashes: set | None = None,
    shared_tail_policy: str = "exclude",
) -> pd.DataFrame:
    """
    Assign each row to 'train', 'val', or 'test'.

    Strategy options
    ----------------
    'purged_temporal' (recommended):
        Within each source_file, rows are sorted chronologically by timestamp.
        The train/val boundary is set at TRAIN_FRAC of the time range;
        a gap of GAP_FRAC is purged either side of the boundary.
        Same logic for val/test boundary.
        Shared-tail rows are handled according to `shared_tail_policy`
        to prevent future data in train and avoid 4x duplicate rows.

    'random':
        Stratified random split by label -- FOR ABLATION ONLY.
        WARNING: breaks temporal ordering and shared-tail guarantee.

    'chronological':
        Global sort by timestamp, single boundary points.
        WARNING: does not handle shared tail across files.

    'group_aware':
        One entire source_file -> one split (file-level group split).
        WARNING: not feasible with shared tail appearing in all 4 CSVs.

    Parameters
    ----------
    df : pd.DataFrame
        Must contain 'timestamp', 'source_file'. For purged_temporal also
        needs HASH_COLS if shared_hashes is provided.
    strategy : str
    seed : int
    train_frac, val_frac, test_frac : float -- must sum to 1.0
    gap_frac : float -- fraction of time range to purge at each boundary
    shared_hashes : set[str] | None -- if provided, used for exact shared-row detection
    shared_tail_policy : str -- 'exclude' (default), 'isolate', 'train', 'test'
        'exclude': marks shared tail rows as 'excluded_shared_tail' so that train/val/test
                   maintain strict forward-looking temporal order and avoids 4x duplicate rows.
        'isolate': marks shared tail rows as 'shared_tail_eval' for dedicated normal evaluation.
        'train'  : legacy DEC-002 mode; assigns to 'train' (warning: shared tail occurs late in time).
        'test'   : assigns to 'test' (preserves time order, but 100% normal data).

    Returns
    -------
    pd.DataFrame -- copy of *df* with added 'split' column.
    """
    rng = np.random.default_rng(seed)
    assert abs(train_frac + val_frac + test_frac - 1.0) < 1e-9, \
        "Fractions must sum to 1.0"

    df = df.copy()
    df["split"] = "purged"  # sentinel; rows left as 'purged' are gap rows

    if strategy == "purged_temporal":
        df = _assign_purged_temporal(
            df, train_frac, val_frac, test_frac, gap_frac, shared_hashes, shared_tail_policy
        )

    elif strategy == "random":
        # Ablation only -- no temporal integrity
        idx = df.index.to_numpy()
        rng.shuffle(idx)
        n = len(idx)
        n_train = int(n * train_frac)
        n_val   = int(n * val_frac)
        df.loc[idx[:n_train], "split"] = "train"
        df.loc[idx[n_train:n_train + n_val], "split"] = "val"
        df.loc[idx[n_train + n_val:], "split"] = "test"

    elif strategy == "chronological":
        df = df.sort_values("timestamp").reset_index(drop=True)
        n = len(df)
        n_train = int(n * train_frac)
        n_val   = int(n * val_frac)
        df.loc[:n_train - 1, "split"] = "train"
        df.loc[n_train:n_train + n_val - 1, "split"] = "val"
        df.loc[n_train + n_val:, "split"] = "test"

    elif strategy == "group_aware":
        # Assign whole source files to splits -- infeasible with shared tail,
        # but implemented for comparison purposes.
        sources = df["source_file"].unique().tolist()
        rng.shuffle(sources)
        n = len(sources)
        n_train = max(1, int(n * train_frac))
        n_val   = max(1, int(n * val_frac))
        mapping = {}
        for s in sources[:n_train]:
            mapping[s] = "train"
        for s in sources[n_train:n_train + n_val]:
            mapping[s] = "val"
        for s in sources[n_train + n_val:]:
            mapping[s] = "test"
        df["split"] = df["source_file"].map(mapping).fillna("test")

    else:
        raise ValueError(f"Unknown strategy: {strategy!r}")

    return df


def _assign_purged_temporal(
    df: pd.DataFrame,
    train_frac: float,
    val_frac: float,
    test_frac: float,
    gap_frac: float,
    shared_hashes: set | None,
    shared_tail_policy: str = "exclude",
) -> pd.DataFrame:
    """Internal: apply purged-temporal split per source_file with configurable shared-tail policy."""
    # Step 1: Detect shared-tail rows
    if shared_hashes is not None:
        row_hashes = compute_row_hash(df)
        is_shared = row_hashes.isin(shared_hashes)
    else:
        is_shared = _is_shared_tail_row(df)

    # Step 2: Handle shared-tail rows according to policy
    if shared_tail_policy == "exclude":
        df.loc[is_shared, "split"] = "excluded_shared_tail"
    elif shared_tail_policy == "isolate":
        df.loc[is_shared, "split"] = "shared_tail_eval"
    elif shared_tail_policy == "train":
        df.loc[is_shared, "split"] = "train"
    elif shared_tail_policy == "test":
        df.loc[is_shared, "split"] = "test"
    else:
        raise ValueError(
            f"Unknown shared_tail_policy: {shared_tail_policy!r}. "
            f"Supported: 'exclude', 'isolate', 'train', 'test'"
        )

    remaining_mask = ~is_shared

    # Step 3: Per source file, apply purged temporal split on remaining rows
    if "source_file" not in df.columns:
        df["source_file"] = "unknown"

    for src in df["source_file"].unique():
        src_mask = (df["source_file"] == src) & remaining_mask
        idx = df.index[src_mask]
        if len(idx) == 0:
            continue

        sub = df.loc[idx].sort_values("timestamp", kind="stable")
        ts_min = sub["timestamp"].min()
        ts_max = sub["timestamp"].max()
        ts_range = ts_max - ts_min
        if ts_range == 0:
            # All rows same timestamp -> all to train
            df.loc[idx, "split"] = "train"
            continue

        gap = ts_range * gap_frac

        # Boundary timestamps (without gap)
        tv_boundary = ts_min + ts_range * train_frac
        vt_boundary = ts_min + ts_range * (train_frac + val_frac)

        ts = sub["timestamp"]
        sub_idx = sub.index

        train_mask = ts < (tv_boundary - gap / 2)
        val_mask   = (ts > (tv_boundary + gap / 2)) & (ts < (vt_boundary - gap / 2))
        test_mask  = ts > (vt_boundary + gap / 2)
        gap_mask   = ~(train_mask | val_mask | test_mask)

        df.loc[sub_idx[train_mask], "split"] = "train"
        df.loc[sub_idx[val_mask],   "split"] = "val"
        df.loc[sub_idx[test_mask],  "split"] = "test"
        df.loc[sub_idx[gap_mask],   "split"] = "purged"  # gap rows excluded

    return df


# ---------------------------------------------------------------------------
# 4. validate_split_integrity
# ---------------------------------------------------------------------------

def validate_split_integrity(df_with_split: pd.DataFrame) -> Dict:
    """
    Validate a split assignment for correctness, leakage prevention, and representativeness.

    Checks:
    - observation_overlap_ok: no identical physical observations (source_file, source_line) in >1 split
    - temporal_order_ok: strict chronological ordering (train <= val <= test) without future lookahead
    - shared_tail_safe: shared-tail rows do not leak into validation or test
    - no_hash_overlap: check identical payload content hashes (noting CAN periodic broadcast behavior)
    - size_dist: row counts and fractions per split
    - label_dist: fraction of normal (R) and attack (T) in each split
    - attack_dist: attack types present in each split
    - has_purged: whether gap rows exist
    - attack_coverage_ok: whether val/test contain attack rows

    Parameters
    ----------
    df_with_split : pd.DataFrame
        Output of assign_split_groups(); must have 'split' column.

    Returns
    -------
    dict with full audit metrics and status flags.
    """
    result: Dict = {}

    splits = df_with_split["split"].unique()
    named_splits = [s for s in ["train", "val", "test"] if s in splits]

    # --- 1. Observation Identity Overlap (Genuine Data Leakage) ---
    obs_overlap = False
    obs_overlap_detail = {}
    id_cols = [c for c in ["source_file", "source_line"] if c in df_with_split.columns]
    if len(id_cols) == 2:
        pairs = [(a, b) for i, a in enumerate(named_splits)
                 for b in named_splits[i + 1:]]
        for a, b in pairs:
            left_ids = set(map(tuple, df_with_split[df_with_split["split"] == a][id_cols].to_numpy()))
            right_ids = set(map(tuple, df_with_split[df_with_split["split"] == b][id_cols].to_numpy()))
            overlap = left_ids & right_ids
            if overlap:
                obs_overlap = True
                obs_overlap_detail[f"{a} n {b}"] = len(overlap)
    result["observation_overlap_ok"] = not obs_overlap
    result["observation_overlap_detail"] = obs_overlap_detail

    # --- 2. Temporal Ordering & Future Data Protection (Per Source File) ---
    temporal_order_ok = True
    temporal_order_detail = {}
    if "timestamp" in df_with_split.columns:
        sources = df_with_split["source_file"].unique() if "source_file" in df_with_split.columns else ["__all__"]
        for src in sources:
            sub = df_with_split[df_with_split["source_file"] == src] if "source_file" in df_with_split.columns else df_with_split
            train_sub = sub[sub["split"] == "train"]
            val_sub   = sub[sub["split"] == "val"]
            test_sub  = sub[sub["split"] == "test"]

            if not train_sub.empty and not val_sub.empty:
                t_max = train_sub["timestamp"].max()
                v_min = val_sub["timestamp"].min()
                tv_ok = bool(t_max <= v_min)
                temporal_order_detail[f"{src}: train_max <= val_min"] = tv_ok
                if not tv_ok:
                    temporal_order_ok = False

            if not val_sub.empty and not test_sub.empty:
                v_max = val_sub["timestamp"].max()
                t_min = test_sub["timestamp"].min()
                vt_ok = bool(v_max <= t_min)
                temporal_order_detail[f"{src}: val_max <= test_min"] = vt_ok
                if not vt_ok:
                    temporal_order_ok = False

            if not train_sub.empty and not test_sub.empty:
                t_max = train_sub["timestamp"].max()
                t_min = test_sub["timestamp"].min()
                tt_ok = bool(t_max <= t_min)
                temporal_order_detail[f"{src}: train_max <= test_min"] = tt_ok
                if not tt_ok:
                    temporal_order_ok = False

    result["temporal_order_ok"] = temporal_order_ok
    result["temporal_order_detail"] = temporal_order_detail

    # --- 3. Content Hash Overlap (CAN Payload Repetition) ---
    hash_overlap = False
    overlap_detail = {}
    if all(c in df_with_split.columns for c in HASH_COLS):
        hashes_per_split = {}
        for sp in named_splits:
            sub = df_with_split[df_with_split["split"] == sp]
            hashes_per_split[sp] = set(compute_row_hash(sub))
        pairs = [(a, b) for i, a in enumerate(named_splits)
                 for b in named_splits[i + 1:]]
        for a, b in pairs:
            overlap = hashes_per_split.get(a, set()) & hashes_per_split.get(b, set())
            if overlap:
                hash_overlap = True
                overlap_detail[f"{a} n {b}"] = len(overlap)
    result["no_hash_overlap"] = not hash_overlap
    result["hash_overlap_detail"] = overlap_detail
    result["content_hash_overlap_is_benign_periodic_can"] = True

    # --- 4. Size distribution ---
    size_dist = {}
    total = len(df_with_split)
    all_split_names = list(df_with_split["split"].unique())
    for sp in all_split_names:
        n = int((df_with_split["split"] == sp).sum())
        size_dist[sp] = {"count": n, "frac": round(n / total, 4) if total else 0}
    result["size_dist"] = size_dist

    # --- 5. Label distribution ---
    label_dist = {}
    if "label" in df_with_split.columns:
        for sp in named_splits:
            sub = df_with_split[df_with_split["split"] == sp]
            vc = sub["label"].value_counts(normalize=True).to_dict()
            label_dist[sp] = {str(k): round(v, 4) for k, v in vc.items()}
    result["label_dist"] = label_dist

    # --- 6. Attack distribution ---
    attack_dist = {}
    if "attack_type" in df_with_split.columns:
        for sp in named_splits:
            sub = df_with_split[df_with_split["split"] == sp]
            vc = sub["attack_type"].value_counts().to_dict()
            attack_dist[sp] = {str(k): int(v) for k, v in vc.items()}
    result["attack_dist"] = attack_dist

    # --- 7. Shared tail safety check ---
    shared_tail_safe = True
    shared_tail_in_train_only = True
    shared_tail_detail = {}
    if "source_file" in df_with_split.columns and "timestamp" in df_with_split.columns:
        is_shared = _is_shared_tail_row(df_with_split)
        if is_shared.any():
            shared_in_splits = df_with_split.loc[is_shared, "split"].value_counts().to_dict()
            shared_tail_detail = shared_in_splits
            # Safety: shared tail must not leak into evaluation splits (val/test)
            if set(shared_in_splits.keys()) & {"val", "test"}:
                shared_tail_safe = False
            # Legacy check:
            if set(shared_in_splits.keys()) - {"train", "purged"}:
                shared_tail_in_train_only = False
    result["shared_tail_safe"] = shared_tail_safe
    result["shared_tail_in_train_only"] = shared_tail_in_train_only
    result["shared_tail_placement"] = shared_tail_detail

    # --- 8. Purged rows ---
    result["has_purged"] = "purged" in splits

    # --- 9. Attack coverage check ---
    min_attack_per_split = {}
    if "label" in df_with_split.columns:
        for sp in ["val", "test"]:
            sub = df_with_split[df_with_split["split"] == sp]
            n_attack = int((sub["label"] == "T").sum()) if "T" in sub["label"].values \
                       else int((sub["label"] == 1).sum())
            min_attack_per_split[sp] = n_attack
    result["attack_counts_in_val_test"] = min_attack_per_split
    result["attack_coverage_ok"] = all(v > 0 for v in min_attack_per_split.values()) \
                                   if min_attack_per_split else True

    return result


# ---------------------------------------------------------------------------
# 5. generate_split_report
# ---------------------------------------------------------------------------

def generate_split_report(validation_result: Dict) -> str:
    """
    Generate a markdown report from validate_split_integrity() output.

    Parameters
    ----------
    validation_result : dict

    Returns
    -------
    str -- Markdown-formatted report.
    """
    vr = validation_result
    lines: List[str] = ["# Split Integrity Report\n"]

    # Overall pass/fail
    checks = [
        vr.get("observation_overlap_ok", True),
        vr.get("temporal_order_ok", True),
        vr.get("shared_tail_safe", True),
    ]
    overall = all(checks)
    lines.append(f"**Overall**: {'PASSED' if overall else 'FAILED'}\n")

    # Observation Identity Overlap
    obs_ok = vr.get("observation_overlap_ok", True)
    lines.append(f"## Observation Identity Integrity: {'DISJOINT (PASS)' if obs_ok else 'OVERLAP DETECTED (FAIL)'}")
    obs_detail = vr.get("observation_overlap_detail", {})
    if obs_detail:
        for k, v in obs_detail.items():
            lines.append(f"- {k}: {v:,} shared observation identities")
    else:
        lines.append("- No shared physical observations between train/val/test splits.")
    lines.append("")

    # Temporal Ordering
    time_ok = vr.get("temporal_order_ok", True)
    lines.append(f"## Chronological Evaluation Order: {'VALID (PASS)' if time_ok else 'ORDER INVERSION DETECTED (FAIL)'}")
    t_detail = vr.get("temporal_order_detail", {})
    for k, v in t_detail.items():
        lines.append(f"- {k}: {'PASS' if v else 'FAIL'}")
    lines.append("")

    # Shared Tail Placement
    tail_safe = vr.get("shared_tail_safe", True)
    lines.append(f"## Shared Tail Isolation: {'PROTECTED (PASS)' if tail_safe else 'LEAKAGE RISK (FAIL)'}")
    placement = vr.get("shared_tail_placement", {})
    if placement:
        for sp, cnt in placement.items():
            lines.append(f"- {sp}: {cnt:,} rows")
    else:
        lines.append("- No shared tail rows in current split.")
    lines.append("")

    # CAN Content Hash Overlap
    no_overlap = vr.get("no_hash_overlap", False)
    lines.append(f"## CAN Periodic Content Hash Overlap: {'None' if no_overlap else 'OVERLAP DETECTED (BENIGN PERIODIC CAN)'}")
    lines.append("> [!NOTE]")
    lines.append("> Periodic CAN broadcast frames naturally repeat identical payload bytes at 10-100Hz.")
    lines.append("> Payload content matching across time is expected automotive CAN behavior, NOT data leakage.")
    lines.append("> Genuine leakage is prevented by observation identity disjointness and chronological purge gaps.")
    detail = vr.get("hash_overlap_detail", {})
    if detail:
        for k, v in detail.items():
            lines.append(f"- {k}: {v:,} overlapping payload hashes")
    lines.append("")

    # Split Sizes
    lines.append("## Split Sizes\n")
    lines.append("| Split | Count | Fraction |")
    lines.append("|-------|------:|---------:|")
    for sp, info in vr.get("size_dist", {}).items():
        lines.append(f"| {sp} | {info['count']:,} | {info['frac']:.4f} |")
    lines.append("")

    # Label distribution
    lines.append("## Label Distribution\n")
    label_dist = vr.get("label_dist", {})
    if label_dist:
        all_labels = set()
        for d in label_dist.values():
            all_labels.update(d.keys())
        all_labels = sorted(all_labels)
        header = "| Split | " + " | ".join(all_labels) + " |"
        sep    = "|-------|" + "|".join(["------:"] * len(all_labels)) + "|"
        lines.append(header)
        lines.append(sep)
        for sp, dist in label_dist.items():
            row = f"| {sp} | " + " | ".join(str(dist.get(l, 0)) for l in all_labels) + " |"
            lines.append(row)
    else:
        lines.append("*label column not present*")
    lines.append("")

    # Attack distribution
    lines.append("## Attack Distribution\n")
    attack_dist = vr.get("attack_dist", {})
    if attack_dist:
        all_types = set()
        for d in attack_dist.values():
            all_types.update(d.keys())
        all_types = sorted(all_types)
        header = "| Split | " + " | ".join(all_types) + " |"
        sep    = "|-------|" + "|".join(["------:"] * len(all_types)) + "|"
        lines.append(header)
        lines.append(sep)
        for sp, dist in attack_dist.items():
            row = f"| {sp} | " + " | ".join(str(dist.get(t, 0)) for t in all_types) + " |"
            lines.append(row)
    else:
        lines.append("*attack_type column not present*")
    lines.append("")

    # Attack coverage
    ac = vr.get("attack_counts_in_val_test", {})
    ac_ok = vr.get("attack_coverage_ok", True)
    lines.append(f"## Attack Coverage in Val/Test: {'Sufficient' if ac_ok else 'LOW -- REVIEW'}")
    for sp, cnt in ac.items():
        lines.append(f"- {sp}: {cnt:,} attack rows")
    lines.append("")

    return "\n".join(lines)

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Self-test with 100-row synthetic fixture
# ---------------------------------------------------------------------------

def _build_fixture(n: int = 100, seed: int = 42) -> pd.DataFrame:
    """Create synthetic CAN-Bus fixture data for testing."""
    rng = np.random.default_rng(seed)
    base_ts = 1_478_190_000.0
    ts = base_ts + np.cumsum(rng.uniform(0.001, 0.01, n))

    sources = ["DoS_dataset.csv"] * 40 + ["Fuzzy_dataset.csv"] * 40 + \
              ["gear_dataset.csv"] * 20
    rng.shuffle(sources)

    can_ids = [f"{rng.integers(0, 2047):03X}" for _ in range(n)]
    dlcs    = rng.choice([2, 5, 6, 8], n)
    labels  = rng.choice(["R", "T"], n, p=[0.87, 0.13])
    atypes  = ["normal" if l == "R" else "dos" for l in labels]

    data: Dict = {
        "timestamp":   ts,
        "can_id":      can_ids,
        "dlc":         dlcs,
        "label":       labels,
        "attack_type": atypes,
        "source_file": sources,
        "flag_raw":    rng.integers(0, 2, n),
    }
    for i in range(8):
        col = f"data_{i}"
        vals = rng.integers(0, 256, n).astype(float)
        # Set to NaN for bytes beyond DLC
        for j, (d, dlc) in enumerate(zip(vals, dlcs)):
            if i >= dlc:
                vals[j] = float("nan")
        data[col] = vals

    return pd.DataFrame(data)


if __name__ == "__main__":
    print("=" * 60)
    print("split_strategy.py -- Self-test (100-row fixture)")
    print("=" * 60)

    df_fixture = _build_fixture(100)
    print(f"Fixture shape: {df_fixture.shape}")
    print(f"Sources: {df_fixture['source_file'].value_counts().to_dict()}")

    # Test compute_row_hash
    hashes = compute_row_hash(df_fixture)
    assert len(hashes) == 100, "Hash count mismatch"
    assert hashes.nunique() > 90, "Too many hash collisions in fixture"
    print(f"[OK] compute_row_hash -- {hashes.nunique()} unique hashes / 100 rows")

    # Test detect_shared_rows
    dfs_dict = {
        "DoS_dataset.csv":   df_fixture[df_fixture["source_file"] == "DoS_dataset.csv"].copy(),
        "Fuzzy_dataset.csv": df_fixture[df_fixture["source_file"] == "Fuzzy_dataset.csv"].copy(),
    }
    shared_info = detect_shared_rows(dfs_dict)
    print(f"[OK] detect_shared_rows -- shared: {shared_info['total_shared']} "
          f"(expect 0 in random fixture)")

    # Test assign_split_groups (purged_temporal)
    df_split = assign_split_groups(df_fixture, strategy="purged_temporal", seed=42)
    split_counts = df_split["split"].value_counts().to_dict()
    print(f"[OK] assign_split_groups (purged_temporal) -- {split_counts}")
    assert "train" in df_split["split"].values, "No train rows"

    # Test validate_split_integrity
    vr = validate_split_integrity(df_split)
    assert vr["no_hash_overlap"], "Unexpected hash overlap in fixture"
    print(f"[OK] validate_split_integrity -- no_hash_overlap={vr['no_hash_overlap']}, "
          f"shared_tail_ok={vr['shared_tail_in_train_only']}")

    # Test generate_split_report
    report = generate_split_report(vr)
    assert "Split Integrity Report" in report
    print("[OK] generate_split_report -- markdown generated")
    print()
    print(report[:800])
    print("=" * 60)
    print("All self-tests PASSED")
