"""
conftest.py — Shared fixtures for SGOD-P1-W02-B2 tests.

Fixtures
--------
sample_can_df       : 30-row DataFrame (mix DoS/normal, DLC 2/5/6/8, two source files)
attack_can_df       : 20-row DataFrame (all T attack rows)
normal_can_df       : 20-row DataFrame (all R normal rows)
shared_tail_df      : 20-row DataFrame with SHARED_TAIL_TS_START timestamps
mixed_split_df      : 60-row DataFrame already split (train/val/test)
preprocessing_rows  : list of raw CSV row lists for parse_csv_row tests
txt_lines           : list of raw TXT lines for parse_txt_row tests
"""
import numpy as np
import pandas as pd
import pytest

from scripts.w02_b2.split_strategy import (
    SHARED_TAIL_TS_START, SHARED_TAIL_TS_END, HASH_COLS
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_can_df(n: int, seed: int, label: str = "mixed", source: str = "DoS_dataset.csv"):
    rng = np.random.default_rng(seed)
    base_ts = 1_478_190_000.0
    ts = base_ts + np.cumsum(rng.uniform(0.001, 0.01, n))

    dlc_choices = [2, 5, 6, 8]
    dlcs = rng.choice(dlc_choices, n)

    if label == "mixed":
        labels = rng.choice(["R", "T"], n, p=[0.80, 0.20])
    elif label == "R":
        labels = np.array(["R"] * n)
    else:
        labels = np.array(["T"] * n)

    attack_types = ["dos" if lbl == "T" else "normal" for lbl in labels]
    can_ids = [f"{rng.integers(0x100, 0x7FF):03X}" for _ in range(n)]

    data = {
        "timestamp":   ts,
        "can_id":      can_ids,
        "dlc":         dlcs,
        "flag_raw":    labels,
        "label":       labels,
        "attack_type": attack_types,
        "source_file": [source] * n,
        "source_line": list(range(n)),
    }
    for i in range(8):
        col = [None] * n
        for j in range(n):
            col[j] = int(rng.integers(0, 256)) if i < dlcs[j] else None
        data[f"data_{i}"] = col

    return pd.DataFrame(data)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_can_df():
    """30-row mixed dataset, two source files, DLC 2/5/6/8."""
    df_a = _make_can_df(20, seed=1, label="mixed", source="DoS_dataset.csv")
    df_b = _make_can_df(10, seed=2, label="R", source="Fuzzy_dataset.csv")
    # Push file_b timestamps to after file_a
    df_b["timestamp"] += df_a["timestamp"].max() + 1.0
    df_b["source_line"] = list(range(10))
    return pd.concat([df_a, df_b], ignore_index=True)


@pytest.fixture
def attack_can_df():
    """20 rows all attack (T)."""
    return _make_can_df(20, seed=10, label="T", source="DoS_dataset.csv")


@pytest.fixture
def normal_can_df():
    """20 rows all normal (R)."""
    return _make_can_df(20, seed=11, label="R", source="normal_run_data.txt")


@pytest.fixture
def shared_tail_df():
    """20 rows with timestamps in the confirmed shared-tail range."""
    rng = np.random.default_rng(99)
    n = 20
    ts = np.linspace(SHARED_TAIL_TS_START, SHARED_TAIL_TS_END, n)
    dlcs = rng.choice([2, 5, 6, 8], n)
    data = {
        "timestamp":   ts,
        "can_id":      [f"{rng.integers(0x100, 0x7FF):03X}" for _ in range(n)],
        "dlc":         dlcs,
        "flag_raw":    ["R"] * n,
        "label":       ["R"] * n,
        "attack_type": ["normal"] * n,
        "source_file": ["DoS_dataset.csv"] * n,
        "source_line": list(range(n)),
    }
    for i in range(8):
        data[f"data_{i}"] = [
            int(rng.integers(0, 256)) if i < dlcs[j] else None
            for j in range(n)
        ]
    return pd.DataFrame(data)


@pytest.fixture
def mixed_split_df(sample_can_df):
    """60-row DataFrame with 'split' column (train/val/test 2:1:1 ratio, no purge)."""
    n = len(sample_can_df)
    split_labels = (
        ["train"] * int(n * 0.5)
        + ["val"]   * int(n * 0.25)
        + ["test"]  * (n - int(n * 0.5) - int(n * 0.25))
    )
    df = sample_can_df.copy().sort_values("timestamp").reset_index(drop=True)
    df["split"] = split_labels
    return df


@pytest.fixture
def preprocessing_rows():
    """Raw CSV rows (list-of-strings) for parse_csv_row tests."""
    return [
        # timestamp, can_id, dlc, [bytes...], flag
        ["1478200727.419470", "0316", "8", "00", "00", "00", "00", "00", "00", "00", "00", "R"],
        ["1478200727.420000", "0244", "2", "ab", "cd", "T"],
        ["1478200727.421000", "0158", "6", "11", "22", "33", "44", "55", "66", "R"],
        ["1478200727.422000", "0100", "5", "AA", "BB", "CC", "DD", "EE", "R"],
        # malformed: DLC out of range
        ["1478200727.423000", "0316", "9", "00", "00", "00", "00", "00", "00", "00", "00", "00", "R"],
    ]


@pytest.fixture
def txt_lines():
    """Raw normal_run_data.txt lines."""
    return [
        "Timestamp: 2.000000    ID: 0350    000    DLC: 5    05 28 84 66 6d",
        "Timestamp: 2.000300    ID: 02c0    000    DLC: 2    14 00",
        "Timestamp: 2.000",   # malformed line
    ]
