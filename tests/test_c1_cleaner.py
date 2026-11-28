import csv
import hashlib
import json
import shutil
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from src.c1_cleaner import COLUMNS, NORMAL_FILE, SOURCES, RowError, clean, parse_frame

FIXTURES = Path(__file__).parent / "fixtures" / "w02_c1"
DOS = "DoS_dataset.csv"


def read_rows(path):
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


class FrameTests(unittest.TestCase):
    def test_observed_and_inferred(self):
        for name, expected in zip(SOURCES[:4], ("dos", "fuzzy", "gear", "rpm")):
            with self.subTest(name=name):
                values = parse_frame("1.000010,001A,2,00,FA,T", name, 7)
                self.assertEqual(values, ("1.000010", "001a", 2, "00", "fa", *[""] * 6,
                                          "T", 1, expected, name, 7, "observed_flag"))
                self.assertEqual(parse_frame("1.0,001a,0,R", name, 8)[11:14], ("R", 0, "normal"))
        frame = parse_frame("Timestamp: 5.0   ID: 0123 000 DLC: 0", NORMAL_FILE, 3)
        self.assertEqual(frame[3:11], ("",) * 8)
        self.assertEqual(frame[11:], ("", 0, "normal", NORMAL_FILE, 3, "inferred_from_source"))

    def test_bounds_and_format(self):
        for line, reason in (
            ("  ", "empty_line"), ('"unterminated', "invalid_csv"),
            ("1.0,0316", "missing_fields"), ("NaN,0316,0,R", "invalid_timestamp"),
            ("9" * 500 + ",0316,0,R", "invalid_timestamp"),
            ("1.0,20000000,0,R", "invalid_can_id"), ("1.0,,0,R", "invalid_can_id"),
            ("1.0,0316,-1,R", "invalid_dlc"), ("1.0,0316,9,R", "invalid_dlc"),
            ("1.0,0316,1,,T", "invalid_payload_byte"), ("1.0,0316,1,A,T", "invalid_payload_byte"),
            ("1.0,0316,1,0G,T", "invalid_payload_byte"), ("1.0,0316,0,X", "invalid_flag"),
            ("1.0,0316,1,R", "payload_length_mismatch"), ("1.0,0316,0,00,R", "payload_length_mismatch"),
        ):
            with self.subTest(line=line), self.assertRaisesRegex(RowError, reason):
                parse_frame(line, DOS, 1)
        valid = parse_frame("1.0,1FFFFFFF,8,00,01,02,03,04,05,06,FF,R", DOS, 1)
        self.assertEqual(valid[1:11], ("1fffffff", 8, "00", "01", "02", "03", "04", "05", "06", "ff"))


class CleanerTests(unittest.TestCase):
    def setUp(self):
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.raw = Path(tmp.name) / "raw"
        shutil.copytree(FIXTURES, self.raw)
        self.output = Path(tmp.name) / "result"

    def test_fixture_handoff_and_accounting(self):
        before = {p: hashlib.sha256(p.read_bytes()).digest() for p in self.raw.iterdir()}
        report = clean(self.raw, self.output)
        self.assertEqual(report, json.loads((self.output / "summary.json").read_text()))
        self.assertEqual(report["totals"], {"input": 19, "valid": 7, "invalid": 12})
        frames = read_rows(self.output / "frames.csv")
        self.assertEqual(len(frames), 7)
        self.assertEqual(tuple(frames[0]), COLUMNS)
        self.assertEqual((frames[0]["data_0"], frames[0]["data_1"], frames[0]["data_2"]), ("00", "0a", ""))
        self.assertEqual([r["source_line"] for r in frames if r["source_file"] == DOS], ["1", "9"])
        errors = read_rows(self.output / "errors.csv")
        self.assertEqual(len(errors), 12)
        self.assertEqual(report["error_reasons"]["payload_length_mismatch"], 3)
        self.assertIn({"source_file": NORMAL_FILE, "source_line": "2", "reason": "invalid_normal_format",
                       "raw_line": "Timestamp: 5.000001"}, errors)
        for stats in report["files"]:
            self.assertEqual(stats["input"], stats["valid"] + stats["invalid"])
        self.assertTrue(all(hashlib.sha256(p.read_bytes()).digest() == h for p, h in before.items()))

    def test_bad_encoding_and_broken_quote_are_isolated(self):
        (self.raw / DOS).write_bytes(b'\xef\xbb\xbf1,0001,0,R\r\n\xff\n"open\n\n2,0001,0,T')
        clean(self.raw, self.output)
        frames = [r for r in read_rows(self.output / "frames.csv") if r["source_file"] == DOS]
        self.assertEqual([r["source_line"] for r in frames], ["1", "5"])
        errors = [r for r in read_rows(self.output / "errors.csv") if r["source_file"] == DOS]
        self.assertEqual([r["reason"] for r in errors], ["invalid_encoding", "invalid_csv", "empty_line"])

    def test_existing_output_and_raw_are_protected(self):
        self.output.mkdir()
        marker = self.output / "frames.csv"
        marker.write_bytes(b"old run")
        with self.assertRaises(FileExistsError):
            clean(self.raw, self.output)
        self.assertEqual(marker.read_bytes(), b"old run")
        with self.assertRaises(ValueError):
            clean(self.raw, self.raw / "nested")

    def test_missing_source_publishes_nothing(self):
        (self.raw / NORMAL_FILE).unlink()
        with self.assertRaises(FileNotFoundError):
            clean(self.raw, self.output)
        self.assertFalse(self.output.exists())
