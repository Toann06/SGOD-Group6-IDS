
from pathlib import Path
import pandas as pd

from scripts.w02_b2.can_parser import load_csv_chunk

root = Path(r"D:\SGOD\SGOD-B2")

files = [
    "DoS_dataset.csv",
    "Fuzzy_dataset.csv",
    "gear_dataset.csv",
    "RPM_dataset.csv",
]

for filename in files:
    path = root / filename
    print(f"\n=== {filename} ===")

    if not path.exists():
        print("FILE MISSING")
        continue

    try:
        first_chunk = next(load_csv_chunk(path, chunksize=1000))
        print("Parsed rows:", len(first_chunk))
        print("Columns:", list(first_chunk.columns))
        print("Labels:", first_chunk["label"].value_counts().to_dict())
        print("First row:")
        print(first_chunk.iloc[0].to_dict())
    except StopIteration:
        print("NO VALID ROWS")
    except Exception as exc:
        print("ERROR:", repr(exc))
