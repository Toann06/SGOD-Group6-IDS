
from pathlib import Path

from scripts.w02_b2.can_parser import load_csv_chunk
from scripts.w02_b2.split_strategy import (
    assign_split_groups,
    SHARED_TAIL_TS_START,
    SHARED_TAIL_TS_END,
)

ROOT = Path(r"D:\SGOD\SGOD-B2")
FILE = ROOT / "DoS_dataset.csv"

# Read a small sample from the beginning of the file.
first = next(
    load_csv_chunk(FILE, chunksize=10000)
)

# Read a small sample from the shared-tail range directly using skiprows.
shared_chunk = next(
    load_csv_chunk(FILE, chunksize=1000, skiprows=2774703)
)
shared = shared_chunk.head(1000).copy()

# Diagnostic sample only: not a full dataset split.
import pandas as pd

df = pd.concat(
    [first, shared],
    ignore_index=True,
)

result = assign_split_groups(
    df,
    strategy="purged_temporal",
    seed=42,
)

print("\n=== SHARED-TAIL SPLIT DIAGNOSTIC ===")

for name in ["train", "val", "test", "purged"]:
    part = result[result["split"] == name]

    if part.empty:
        continue

    print(
        name,
        "rows=", len(part),
        "min_ts=", part["timestamp"].min(),
        "max_ts=", part["timestamp"].max(),
    )

train = result[result["split"] == "train"]
test = result[result["split"] == "test"]

if not train.empty and not test.empty:
    print(
        "\nTrain max timestamp > Test min timestamp:",
        bool(
            train["timestamp"].max()
            > test["timestamp"].min()
        ),
    )
else:
    print("\nTrain or Test is empty in this sample.")

print("\nCHECK COMPLETED")
