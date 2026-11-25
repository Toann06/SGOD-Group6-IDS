
from pathlib import Path
import pandas as pd

from scripts.w02_b2.can_parser import load_csv_chunk
from scripts.w02_b2.split_strategy import (
    assign_split_groups,
    compute_row_hash,
)

ROOT = Path(r"D:\SGOD\SGOD-B2")
PATH = ROOT / "DoS_dataset.csv"

# Same sample used by the current smoke test.
df = next(load_csv_chunk(PATH, chunksize=10000))

df = df.sort_values(
    ["timestamp", "source_line"],
    kind="stable",
).reset_index(drop=True)

df = assign_split_groups(
    df,
    strategy="purged_temporal",
    seed=42,
)

df["content_hash"] = compute_row_hash(df)

# A more specific observation identity for diagnostics.
# This is not a replacement for provenance verification
# across different source files.
identity_cols = [
    "source_file",
    "source_line",
]

print("\n=== SPLIT LABEL DISTRIBUTION ===")

for split in ["train", "val", "test", "purged"]:
    sub = df[df["split"] == split]

    print(f"\n{split.upper()}")
    print("Total:", len(sub))
    print("Labels:", sub["label"].value_counts().to_dict())

    if not sub.empty:
        print("Min timestamp:", sub["timestamp"].min())
        print("Max timestamp:", sub["timestamp"].max())
        print("Min source line:", sub["source_line"].min())
        print("Max source line:", sub["source_line"].max())

print("\n=== CROSS-SPLIT OVERLAP ===")

pairs = [
    ("train", "val"),
    ("train", "test"),
    ("val", "test"),
]

for a, b in pairs:
    left = df[df["split"] == a]
    right = df[df["split"] == b]

    content_a = set(left["content_hash"])
    content_b = set(right["content_hash"])

    identity_a = set(
        map(tuple, left[identity_cols].to_numpy())
    )
    identity_b = set(
        map(tuple, right[identity_cols].to_numpy())
    )

    print(f"\n{a} vs {b}")
    print(
        "Shared content hashes:",
        len(content_a & content_b),
    )
    print(
        "Shared source-file/line identities:",
        len(identity_a & identity_b),
    )

print("\n=== DUPLICATE CONTENT EXAMPLES ===")

train = df[df["split"] == "train"]
test = df[df["split"] == "test"]

shared = set(train["content_hash"]) & set(
    test["content_hash"]
)

if shared:
    example_hash = next(iter(sorted(shared)))

    columns = [
        "split",
        "timestamp",
        "source_file",
        "source_line",
        "can_id",
        "dlc",
        "label",
    ]

    example = df[
        df["content_hash"] == example_hash
    ][columns]

    print(example.head(10).to_string(index=False))
else:
    print("No shared content hashes.")

print("\nDIAGNOSIS COMPLETED")
