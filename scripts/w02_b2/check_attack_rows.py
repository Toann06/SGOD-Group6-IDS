
from pathlib import Path

from scripts.w02_b2.can_parser import load_csv_chunk

ROOT = Path(r"D:\SGOD\SGOD-B2")

FILES = [
    "DoS_dataset.csv",
    "Fuzzy_dataset.csv",
    "gear_dataset.csv",
    "RPM_dataset.csv",
]

CHUNK_SIZE = 10000
MAX_ROWS_PER_FILE = 500000

for filename in FILES:
    print(f"\n{'=' * 60}")
    print(f"FILE: {filename}")

    path = ROOT / filename

    if not path.exists():
        print("ERROR: File not found")
        continue

    total_rows = 0
    normal_count = 0
    attack_count = 0
    first_attack = None

    for chunk in load_csv_chunk(
        path,
        chunksize=CHUNK_SIZE,
    ):
        total_rows += len(chunk)

        normal_count += int(
            (chunk["label"] == 0).sum()
        )

        attack_count += int(
            (chunk["label"] == 1).sum()
        )

        attacks = chunk[chunk["label"] == 1]

        if not attacks.empty:
            first_attack = attacks.iloc[0].to_dict()
            break

        if total_rows >= MAX_ROWS_PER_FILE:
            break

    print("Rows parsed:", total_rows)
    print("Normal rows:", normal_count)
    print("Attack rows:", attack_count)

    if first_attack is not None:
        print("FIRST ATTACK FOUND:")
        print(first_attack)
    else:
        print(
            "No attack found within inspected range."
        )

print("\nCHECK COMPLETED")
