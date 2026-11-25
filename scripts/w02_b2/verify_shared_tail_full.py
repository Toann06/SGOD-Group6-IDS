
from pathlib import Path
import hashlib
import json

from scripts.w02_b2.can_parser import load_csv_chunk
from scripts.w02_b2.split_strategy import (
    SHARED_TAIL_TS_START,
    SHARED_TAIL_TS_END,
)

ROOT = Path(r"D:\SGOD\SGOD-B2")
OUTPUT = ROOT / "outputs" / "w02_b2" / "shared_tail_full_verification.json"

FILES = [
    "DoS_dataset.csv",
    "Fuzzy_dataset.csv",
    "gear_dataset.csv",
    "RPM_dataset.csv",
]

COLS = [
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

def canonical_value(value):
    if value is None:
        return None

    try:
        import pandas as pd
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass

    return str(value)

def compute_shared_tail_digest(path):
    digest = hashlib.sha256()
    count = 0
    first_line = None
    last_line = None
    first_ts = None
    last_ts = None

    for chunk in load_csv_chunk(path, chunksize=50000):
        selected = chunk[
            chunk["timestamp"].between(
                SHARED_TAIL_TS_START,
                SHARED_TAIL_TS_END,
                inclusive="both",
            )
        ]

        if selected.empty:
            continue

        for row in selected[COLS + ["source_line"]].itertuples(
            index=False,
            name=None,
        ):
            values = row[:-1]
            source_line = int(row[-1])

            payload = json.dumps(
                [canonical_value(v) for v in values],
                ensure_ascii=False,
                separators=(",", ":"),
            ).encode("utf-8")

            digest.update(len(payload).to_bytes(4, "big"))
            digest.update(payload)

            if first_line is None:
                first_line = source_line
                first_ts = float(values[0])

            last_line = source_line
            last_ts = float(values[0])
            count += 1

    return {
        "rows": count,
        "sha256": digest.hexdigest(),
        "first_source_line": first_line,
        "last_source_line": last_line,
        "first_timestamp": first_ts,
        "last_timestamp": last_ts,
    }

report = {
    "scope": "Full shared-tail range, parsed observations",
    "files": {},
}

for name in FILES:
    print(f"\nProcessing {name}...", flush=True)

    result = compute_shared_tail_digest(ROOT / name)
    report["files"][name] = result

    print("Rows:", result["rows"], flush=True)
    print("SHA-256:", result["sha256"], flush=True)

counts = {
    item["rows"]
    for item in report["files"].values()
}

digests = {
    item["sha256"]
    for item in report["files"].values()
}

report["verification"] = {
    "all_counts_equal": len(counts) == 1,
    "all_digests_equal": len(digests) == 1,
    "expected_row_count": 891068,
    "expected_count_matches": counts == {891068},
}

report["verification"]["passed"] = all([
    report["verification"]["all_counts_equal"],
    report["verification"]["all_digests_equal"],
    report["verification"]["expected_count_matches"],
])

OUTPUT.parent.mkdir(parents=True, exist_ok=True)

with OUTPUT.open("w", encoding="utf-8") as f:
    json.dump(report, f, indent=2, ensure_ascii=False)

print("\n=== FULL SHARED-TAIL VERIFICATION ===")
print(json.dumps(report["verification"], indent=2))
print("Report saved:", OUTPUT)
