"""Cross-check the full local C1 run against the B1 audit and B3 handoff."""
import csv
import hashlib
import io
import json
import subprocess
import unittest
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "data/processed/w02_c1"
B1 = "14a7023:SGOD-P1-W03-B1/results/"
B3 = "2672e3e:outputs/w02_b3/"


def reference(path):
    return subprocess.check_output(["git", "show", path], cwd=ROOT).decode("utf-8")


class RealHandoffTests(unittest.TestCase):
    def test_real_data_and_handoff(self):
        manifest = json.loads(reference(B3 + "manifest.json"))
        summary = json.loads((RUN / "summary.json").read_text(encoding="utf-8"))
        files = {f["source_file"]: f for f in summary["files"]}
        for item in manifest["source_files"]:
            path = ROOT / "data/raw" / item["file"]
            with path.open("rb") as raw:
                digest = hashlib.sha256()
                for block in iter(lambda: raw.read(1024 * 1024), b""):
                    digest.update(block)
            self.assertEqual(digest.hexdigest(), item["sha256"], path.name)
            self.assertEqual(files[path.name]["sha256"], item["sha256"], path.name)

        sample = list(csv.DictReader(io.StringIO(reference(B3 + "labeled_sample.csv"))))
        expected = {(r["source_file"].encode(), r["source_line"].encode()): r for r in sample}
        counts = Counter()
        # All canonical C1 fields are comma-free. Split only the metadata suffix
        # for the full scan, then decode the 18 B3 reference rows as CSV.
        with (RUN / "frames.csv").open("rb") as frames:
            header = next(csv.reader([frames.readline().decode()]))
            self.assertEqual(header, manifest["mandatory_b2_columns"] + ["label_provenance"])
            for line in frames:
                _, label, _, filename, number, _ = line.rsplit(b",", 5)
                counts[filename, label] += 1
                key = (filename, number)
                if key in expected:
                    row = next(csv.reader([line.decode()]))
                    reference_row = expected.pop(key)
                    self.assertEqual(row, [reference_row[k] for k in header])
        self.assertFalse(expected, "B3 rows missing from clean data")
        audit = list(csv.DictReader(io.StringIO(reference(B1 + "file_summary.csv"))))
        for row in audit:
            stats = files[row["file"]]
            for key, reference_key in (("input", "lines_read"), ("valid", "valid"), ("invalid", "invalid")):
                self.assertEqual(stats[key], int(row[reference_key]), row["file"])
            name = row["file"].encode()
            self.assertEqual(counts[name, b"0"], int(row["normal_0"]))
            self.assertEqual(counts[name, b"1"], int(row["attack_1"]))
        self.assertEqual(sum(counts.values()), summary["totals"]["valid"])
        with (RUN / "errors.csv").open(encoding="utf-8", newline="") as errors:
            self.assertEqual(list(csv.DictReader(errors)), [
                {"source_file": row["file"], "source_line": row["line"], "reason": row["reason"],
                 "raw_line": row["content"]}
                for row in csv.DictReader(io.StringIO(reference(B1 + "errors_sample.csv")))
            ])


if __name__ == "__main__":
    unittest.main(verbosity=2)
