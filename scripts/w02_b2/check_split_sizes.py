
from pathlib import Path
import pandas as pd

from scripts.w02_b2.can_parser import load_csv_chunk
from scripts.w02_b2.split_strategy import assign_split_groups

ROOT = Path(r"D:\SGOD\SGOD-B2")
FILE = ROOT / "DoS_dataset.csv"

SAMPLE_SIZES = [10000, 50000, 100000, 200000]
MAX_ROWS = max(SAMPLE_SIZES)

chunks = []
rows = 0

for chunk in load_csv_chunk(FILE, chunksize=10000):
    chunks.append(chunk)
    rows += len(chunk)

    if rows >= MAX_ROWS:
        break

df_all = pd.concat(chunks, ignore_index=True)
df_all = df_all.iloc[:MAX_ROWS].copy()

print("\n=== SPLIT SIZE COMPARISON ===")

for n in SAMPLE_SIZES:
    df = df_all.iloc[:n].copy()

    df = df.sort_values(
        ["timestamp", "source_line"],
        kind="stable",
    ).reset_index(drop=True)

    split_df = assign_split_groups(
        df,
        strategy="purged_temporal",
        seed=42,
    )

    print(f"\nSAMPLE SIZE: {n:,}")
    print("-" * 55)

    for name in ["train", "val", "test", "purged"]:
        part = split_df[split_df["split"] == name]

        total = len(part)
        attacks = int((part["label"] == 1).sum())
        normal = int((part["label"] == 0).sum())

        attack_pct = (
            attacks / total * 100 if total else 0
        )

        print(
            f"{name:8s} "
            f"total={total:7,d} "
            f"normal={normal:7,d} "
            f"attack={attacks:7,d} "
            f"attack_rate={attack_pct:6.2f}%"
        )

print("\nCHECK COMPLETED")
