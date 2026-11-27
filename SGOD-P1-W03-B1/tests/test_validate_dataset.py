"""Test bien cho validate_dataset.py (SGOD-P1-W03-B1). Chay: python -m unittest discover -s tests -v"""
import sys, tempfile, unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import validate_dataset as v  # noqa: E402

GOOD = [
    "1478198376.389427,0316,8,05,21,68,09,21,21,00,6f,R",   # 1 hop le, DLC 8, R
    "1478198376.389636,018f,2,fe,5b,R",                      # 2 hop le, DLC 2
    "1478198376.389900,0000,8,00,00,00,00,00,00,00,00,T",   # 3 hop le, attack
]
BAD = {
    "invalid_flag": "1478198376.4,0316,2,00,01,X",
    "field_count_not_equal_4_plus_dlc": "1478198376.5,0316,8,00,01,R",       # thieu byte
    "invalid_payload_byte": "1478198376.6,0316,2,zz,01,R",                   # byte khong hex
    "invalid_can_id": "1478198376.7,03g6,2,00,01,R",                         # id khong hex
    "invalid_or_out_of_range_dlc": "1478198376.8,0316,9,00,00,00,00,00,00,00,00,00,R",  # DLC 9
    "invalid_timestamp": "abc,0316,2,00,01,R",
}


def run_csv(lines):
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "DoS_dataset.csv"
        p.write_bytes(("\r\n".join(lines) + "\r\n").encode("utf-8"))  # ghi bytes: tranh Windows doi \n thanh \r\r\n
        return v.process_csv(p, "dos", 1000, 1.0)


class TestCsv(unittest.TestCase):
    def test_good_rows_all_valid(self):
        st = run_csv(GOOD)
        self.assertEqual((st.lines, st.valid, sum(st.errors.values())), (3, 3, 0))
        self.assertEqual(dict(st.label_counts), {0: 2, 1: 1})

    def test_each_bad_row_reported_with_reason(self):
        for reason, row in BAD.items():
            with self.subTest(reason=reason):
                st = run_csv(GOOD + [row])
                self.assertEqual(st.valid, 3)
                self.assertEqual(st.errors[reason], 1, dict(st.errors))
                self.assertEqual(st.error_examples[0]["line"], 4)

    def test_timestamp_going_backwards_and_gap(self):
        st = run_csv([GOOD[0], "1478198300.0,0316,2,00,01,R", "1478198400.0,0316,2,00,01,R"])
        self.assertEqual(st.ts_backwards, 1)
        self.assertEqual(len(st.gaps), 1)

    def test_dlc_lt_8_is_not_an_error(self):
        st = run_csv([GOOD[1]])
        self.assertEqual((st.valid, sum(st.errors.values())), (1, 0))


class TestNormalTxt(unittest.TestCase):
    def run_txt(self, lines):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "normal_run_data.txt"
            p.write_bytes(("\n".join(lines) + "\n").encode("utf-8"))
            return v.process_normal(p, 1.0)

    def test_valid_and_truncated_last_line(self):
        st = self.run_txt([
            "Timestamp: 1479121434.850202        ID: 0350    000    DLC: 8    05 28 84 66 6d 00 00 a2",
            "Timestamp: 1479121941.287013     ",
        ])
        self.assertEqual(st.valid, 1)
        self.assertEqual(st.errors["invalid_normal_format"], 1)
        self.assertEqual(dict(st.label_counts), {0: 1})

    def test_payload_count_mismatch(self):
        st = self.run_txt(["Timestamp: 1479121434.85        ID: 0350    000    DLC: 8    05 28"])
        self.assertEqual(st.errors["payload_count_not_equal_dlc"], 1)


if __name__ == "__main__":
    unittest.main()