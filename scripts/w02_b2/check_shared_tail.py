
from pathlib import Path
import pandas as pd

from scripts.w02_b2.can_parser import load_csv_chunk
from scripts.w02_b2.split_strategy import (
    SHARED_TAIL_TS_START,
    SHARED_TAIL_TS_END,
)

ROOT = Path(r"D:\SGOD\SGOD-B2")

FILES = [
    "DoS_dataset.csv",
    "Fuzzy_dataset.csv",
    "gear_dataset.csv",
    "RPM_dataset.csv",
]

CHUNK_SIZE = 50000

# Compare exact parsed observations, including timestamp.
# This is a sample-based check, not a full proof.
IDENTITY_COLS = [
    "timestamp",
    "can_id",
    "dlc",
    "data_0",
    "data_1",
    "data_2",
    "data_3",
    "data_4",
    "data_5",
    "data_6",
    "data_7",
]

samples = {}

for fname in FILES:
    print(f"\nReading: {fname}")

    selected = []
    total_in_range = 0

    for chunk in load_csv_chunk(
        ROOT / fname,
        chunksize=CHUNK_SIZE,
    ):
        in_range = chunk[
            chunk["timestamp"].between(
                SHARED_TAIL_TS_START,
                SHARED_TAIL_TS_END,
            )
        ]

        total_in_range += len(in_range)

        # Keep only a bounded sample in memory.
        if len(selected) < 2 and not in_range.empty:
            selected.append(
                in_range.head(500).copy()
            )

    if selected:
        sample = pd.concat(
            selected,
            ignore_index=True,
        )
    else:
        sample = pd.DataFrame(
            columns=IDENTITY_COLS
        )

    samples[fname] = sample

    print("Rows in shared-tail timestamp range:", total_in_range)
    print("Sampled rows:", len(sample))

print("\n=== CROSS-FILE EXACT OBSERVATION COMPARISON ===")

for i, left_name in enumerate(FILES):
    for right_name in FILES[i + 1:]:
        left = samples[left_name]
        right = samples[right_name]

        left_keys = set(
            map(
                tuple,
                left[IDENTITY_COLS]
                .fillna("<MISSING>")
                .to_numpy(),
            )
        )

        right_keys = set(
            map(
                tuple,
                right[IDENTITY_COLS]
                .fillna("<MISSING>")
                .to_numpy(),
            )
        )

        overlap = left_keys & right_keys

        print(
            f"{left_name} vs {right_name}: "
            f"{len(overlap)} matching observations "
            f"in sampled rows"
        )

print("\nSHARED-TAIL CHECK COMPLETED")
print("This is a sample diagnostic, not full validation.")
