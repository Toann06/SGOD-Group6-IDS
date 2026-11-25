
from pathlib import Path
import json

from scripts.w02_b2.can_parser import load_csv_chunk
from scripts.w02_b2.split_strategy import (
    assign_split_groups,
    compute_row_hash,
)

ROOT = Path(r"D:\SGOD\SGOD-B2")
OUTPUT = ROOT / "outputs" / "w02_b2" / "split_audit.json"

df = next(
    load_csv_chunk(
        ROOT / "DoS_dataset.csv",
        chunksize=10000,
    )
)

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

splits = {
    name: df[df["split"] == name]
    for name in ["train", "val", "test", "purged"]
}

report = {
    "scope": "DoS first 10000 parsed rows only",
    "split_statistics": {},
    "pairwise_checks": {},
}

for name, part in splits.items():
    report["split_statistics"][name] = {
        "rows": int(len(part)),
        "normal": int((part["label"] == 0).sum()),
        "attack": int((part["label"] == 1).sum()),
        "min_timestamp": (
            float(part["timestamp"].min())
            if not part.empty else None
        ),
        "max_timestamp": (
            float(part["timestamp"].max())
            if not part.empty else None
        ),
    }

pairs = [
    ("train", "val"),
    ("train", "test"),
    ("val", "test"),
]

for a, b in pairs:
    left = splits[a]
    right = splits[b]

    left_ids = set(
        zip(left["source_file"], left["source_line"])
    )
    right_ids = set(
        zip(right["source_file"], right["source_line"])
    )

    content_overlap = (
        set(left["content_hash"])
        & set(right["content_hash"])
    )

    # The first split must end before the second begins.
    ordered = (
        not left.empty
        and not right.empty
        and left["timestamp"].max()
        < right["timestamp"].min()
    )

    report["pairwise_checks"][f"{a}_vs_{b}"] = {
        "shared_observation_ids": len(
            left_ids & right_ids
        ),
        "shared_content_hashes": len(content_overlap),
        "strict_temporal_order": bool(ordered),
    }

# These checks are limited to the single-file sample.
identity_ok = all(
    item["shared_observation_ids"] == 0
    for item in report["pairwise_checks"].values()
)

temporal_ok = all(
    item["strict_temporal_order"]
    for item in report["pairwise_checks"].values()
)

test_attack_count = report[
    "split_statistics"
]["test"]["attack"]

report["assessment"] = {
    "observation_identity_disjoint": identity_ok,
    "strict_temporal_order": temporal_ok,
    "test_attack_count": test_attack_count,
    "test_attack_coverage_sufficient": (
        test_attack_count >= 100
    ),
    "full_dataset_leakage_verified": False,
    "shared_tail_cross_file_verified": False,
    "window_feature_leakage_verified": False,
}

OUTPUT.parent.mkdir(parents=True, exist_ok=True)

with OUTPUT.open("w", encoding="utf-8") as f:
    json.dump(report, f, indent=2)

print(json.dumps(report, indent=2))
print("\nReport saved:", OUTPUT)
