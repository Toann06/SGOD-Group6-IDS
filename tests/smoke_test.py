#!/usr/bin/env python3
"""End-to-end environment & data-contract smoke test for SGOD-Group6-IDS (Task C4)."""

from __future__ import annotations

import csv
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

REQUIRED_DIRS = [
    "configs",
    "data/raw",
    "data/processed",
    "data/clients",
    "src",
    "models",
    "training",
    "federated",
    "blockchain",
    "security",
    "infrastructure",
    "tests",
    "docs",
]

MANDATORY_COLS = [
    "timestamp",
    "can_id",
    "dlc",
    *[f"data_{i}" for i in range(8)],
    "flag_raw",
    "label",
    "attack_type",
    "source_file",
    "source_line",
]
OPTIONAL_COLS = ["label_provenance", "segment_id"]
ALL_EXPECTED_COLS = MANDATORY_COLS + OPTIONAL_COLS

SHARED_START = "1478200727.419470"
SHARED_END = "1478201209.058944"


def compute_sha256(file_path: Path) -> str:
    h = hashlib.sha256()
    with file_path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


class SGODSmokeTest(unittest.TestCase):
    def test_01_repository_layout_and_infra(self):
        """Verify unified directory layout and core environment files exist."""
        for rel_dir in REQUIRED_DIRS:
            target = REPO_ROOT / rel_dir
            self.assertTrue(target.is_dir(), f"Missing required directory: {rel_dir}")

        self.assertTrue((REPO_ROOT / "requirements.txt").is_file(), "Missing requirements.txt")
        self.assertTrue((REPO_ROOT / "README.md").is_file(), "Missing README.md")
        self.assertTrue(
            (REPO_ROOT / "infrastructure" / "Dockerfile").is_file(),
            "Missing infrastructure/Dockerfile",
        )

    def test_02_core_packages_importable(self):
        """Verify required Python packages can be imported cleanly."""
        for pkg in ("numpy", "pandas", "sklearn", "torch", "matplotlib", "requests", "yaml", "pytest"):
            with self.subTest(package=pkg):
                __import__(pkg)

    def test_03_pipeline_or_contract_fixture(self):
        """Run B3 sample builder if present in repo, otherwise validate synthetic fixture contract."""
        candidate_scripts = list(REPO_ROOT.rglob("build_labeled_sample.py"))
        raw_dir = REPO_ROOT / "data" / "raw"
        has_raw_data = any(
            (raw_dir / fname).is_file()
            for fname in (
                "dos_dataset.csv",
                "fuzzy_dataset.csv",
                "gear_dataset.csv",
                "rpm_dataset.csv",
                "normal_run_data.txt",
            )
        )

        tmp_out = Path(tempfile.mkdtemp(prefix="sgod_smoketest_"))
        try:
            if candidate_scripts and has_raw_data:
                script_path = candidate_scripts[0]
                subprocess.run(
                    [
                        sys.executable,
                        str(script_path),
                        "--data-dir",
                        str(raw_dir),
                        "--output-dir",
                        str(tmp_out),
                        "--seed",
                        "42",
                        "--per-stratum",
                        "1",
                    ],
                    check=True,
                )
            else:
                sample_csv = tmp_out / "labeled_sample.csv"
                rows = [
                    {
                        "timestamp": "1478198376.389427",
                        "can_id": "0316",
                        "dlc": "8",
                        "data_0": "00",
                        "data_1": "21",
                        "data_2": "68",
                        "data_3": "09",
                        "data_4": "21",
                        "data_5": "21",
                        "data_6": "00",
                        "data_7": "6f",
                        "flag_raw": "R",
                        "label": "0",
                        "attack_type": "normal",
                        "source_file": "dos_dataset.csv",
                        "source_line": "1",
                        "label_provenance": "observed_flag",
                        "segment_id": "0",
                    },
                    {
                        "timestamp": "1478198377.100000",
                        "can_id": "0000",
                        "dlc": "8",
                        "data_0": "00",
                        "data_1": "00",
                        "data_2": "00",
                        "data_3": "00",
                        "data_4": "00",
                        "data_5": "00",
                        "data_6": "00",
                        "data_7": "00",
                        "flag_raw": "T",
                        "label": "1",
                        "attack_type": "dos",
                        "source_file": "dos_dataset.csv",
                        "source_line": "2",
                        "label_provenance": "observed_flag",
                        "segment_id": "0",
                    },
                ]
                with sample_csv.open("w", newline="", encoding="utf-8") as f:
                    writer = csv.DictWriter(f, fieldnames=ALL_EXPECTED_COLS)
                    writer.writeheader()
                    writer.writerows(rows)

                manifest = {
                    "artifact": "SGOD-P1-W02-C4 smoke fixture",
                    "seed": 42,
                    "rows": len(rows),
                    "sample_sha256": compute_sha256(sample_csv),
                }
                (tmp_out / "manifest.json").write_text(
                    json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
                )

            sample_path = tmp_out / "labeled_sample.csv"
            manifest_path = tmp_out / "manifest.json"
            self.assertTrue(sample_path.is_file(), "labeled_sample.csv was not generated")
            self.assertTrue(manifest_path.is_file(), "manifest.json was not generated")

            manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
            actual_sha256 = compute_sha256(sample_path)
            self.assertEqual(
                manifest_data.get("sample_sha256"),
                actual_sha256,
                "SHA-256 mismatch between labeled_sample.csv and manifest.json",
            )

            with sample_path.open("r", newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                self.assertEqual(
                    reader.fieldnames,
                    ALL_EXPECTED_COLS,
                    "CSV columns do not match 18-column B2/B3 contract",
                )
                parsed_rows = list(reader)

            self.assertGreater(len(parsed_rows), 0, "labeled_sample.csv must not be empty")

            for row in parsed_rows:
                dlc = int(row["dlc"])
                for i in range(dlc):
                    val = row[f"data_{i}"]
                    self.assertEqual(len(val), 2, f"Payload byte data_{i} lost 2-char hex width: {val!r}")
                if row["source_file"].lower() in {
                    "dos_dataset.csv",
                    "fuzzy_dataset.csv",
                    "gear_dataset.csv",
                    "rpm_dataset.csv",
                }:
                    self.assertFalse(
                        SHARED_START <= row["timestamp"] <= SHARED_END,
                        f"Shared tail row leaked: {row['timestamp']}",
                    )
        finally:
            shutil.rmtree(tmp_out, ignore_errors=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
    