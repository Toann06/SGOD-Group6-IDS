import unittest

from src.data_validation.validator import validate_record


class TestCANBusValidator(unittest.TestCase):

    def valid_record(self):
        return {
            "timestamp": 1.0,
            "can_id": "123",
            "dlc": 2,
            "payload": ["AA", "BB"],
            "label": 0,
        }

    def test_valid_record(self):
        self.assertEqual(
            validate_record(self.valid_record()),
            []
        )

    def test_missing_timestamp(self):
        record = self.valid_record()
        del record["timestamp"]

        errors = validate_record(record)

        self.assertIn("Missing field: timestamp", errors)

    def test_missing_can_id(self):
        record = self.valid_record()
        del record["can_id"]

        errors = validate_record(record)

        self.assertIn("Missing field: can_id", errors)

    def test_missing_dlc(self):
        record = self.valid_record()
        del record["dlc"]

        errors = validate_record(record)

        self.assertIn("Missing field: dlc", errors)

    def test_missing_payload(self):
        record = self.valid_record()
        del record["payload"]

        errors = validate_record(record)

        self.assertIn("Missing field: payload", errors)

    def test_missing_label(self):
        record = self.valid_record()
        del record["label"]

        errors = validate_record(record)

        self.assertIn("Missing field: label", errors)

    def test_dlc_zero(self):
        record = self.valid_record()
        record["dlc"] = 0
        record["payload"] = []

        self.assertEqual(validate_record(record), [])

    def test_dlc_eight(self):
        record = self.valid_record()
        record["dlc"] = 8
        record["payload"] = [
            "00", "11", "22", "33",
            "44", "55", "66", "77"
        ]

        self.assertEqual(validate_record(record), [])

    def test_dlc_negative(self):
        record = self.valid_record()
        record["dlc"] = -1

        errors = validate_record(record)

        self.assertIn(
            "DLC must be between 0 and 8",
            errors
        )

    def test_dlc_above_eight(self):
        record = self.valid_record()
        record["dlc"] = 9

        errors = validate_record(record)

        self.assertIn(
            "DLC must be between 0 and 8",
            errors
        )

    def test_dlc_invalid_type(self):
        record = self.valid_record()
        record["dlc"] = "abc"

        errors = validate_record(record)

        self.assertIn(
            "DLC must be an integer",
            errors
        )

    def test_payload_length_mismatch(self):
        record = self.valid_record()
        record["payload"] = ["AA"]

        errors = validate_record(record)

        self.assertTrue(
            any("does not match DLC" in error for error in errors)
        )

    def test_invalid_payload_hex(self):
        record = self.valid_record()
        record["payload"] = ["GG", "BB"]

        errors = validate_record(record)

        self.assertIn(
            "Invalid hexadecimal payload byte: GG",
            errors
        )

    def test_invalid_payload_byte_length(self):
        record = self.valid_record()
        record["payload"] = ["A", "BB"]

        errors = validate_record(record)

        self.assertIn(
            "Invalid payload byte length: A",
            errors
        )

    def test_payload_not_list(self):
        record = self.valid_record()
        record["payload"] = "AABB"

        errors = validate_record(record)

        self.assertIn(
            "Payload must be a list",
            errors
        )

    def test_valid_attack_label(self):
        record = self.valid_record()
        record["label"] = 1

        self.assertEqual(validate_record(record), [])

    def test_invalid_label(self):
        record = self.valid_record()
        record["label"] = 2

        errors = validate_record(record)

        self.assertIn(
            "Label must be 0 or 1",
            errors
        )


if __name__ == "__main__":
    unittest.main()