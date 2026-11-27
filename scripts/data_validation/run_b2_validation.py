
import csv
import logging
from pathlib import Path

from src.data_validation.validator import validate_record


# Project root: SGOD-IDS/
PROJECT_ROOT = Path(__file__).resolve().parents[1]

# HCRL dataset directory
DATA_DIR = PROJECT_ROOT / "data" / "raw" / "HCRL"

# Validation log directory
LOG_DIR = PROJECT_ROOT / "results" / "data_validation" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

LOG_FILE = LOG_DIR / "b2_validation.log"

CSV_FILES = [
    "DoS_dataset.csv",
    "Fuzzy_dataset.csv",
    "gear_dataset.csv",
    "RPM_dataset.csv",
]


logging.basicConfig(
    filename=LOG_FILE,
    level=logging.ERROR,
    format="%(asctime)s | %(levelname)s | %(message)s",
    encoding="utf-8",
)

logger = logging.getLogger("b2_validation")


def convert_row(row, filename, line_number):
    """
    Convert a raw HCRL CSV row into a preliminary
    normalized record for validation.
    """

    # Expected raw format:
    # Timestamp, CAN ID, DLC, DATA0...DATA7, Flag

    if len(row) < 12:
        raise ValueError(
            f"Invalid column count: expected 12, got {len(row)}"
        )

    timestamp = row[0].strip()
    can_id = row[1].strip()
    dlc_raw = row[2].strip()

    try:
        dlc = int(dlc_raw)
    except ValueError:
        dlc = dlc_raw

    # DATA bytes are located at columns 3..10
    raw_payload = row[3:11]

    # Flag is the last expected column
    flag = row[11].strip()

    # Only collect non-empty payload values
    payload = [
        value.strip()
        for value in raw_payload
        if value.strip()
    ]

    # Preliminary mapping based on B2 investigation
    if flag == "R":
        label = 0
    elif flag == "T":
        label = 1
    else:
        label = -1

    return {
        "timestamp": timestamp,
        "can_id": can_id,
        "dlc": dlc,
        "payload": payload,
        "label": label,
        "source_file": filename,
        "source_line": line_number,
        "flag_raw": flag,
    }


def validate_file(filename):
    file_path = DATA_DIR / filename

    total = 0
    valid = 0
    invalid = 0

    print(f"\n===== Validating {filename} =====")

    with file_path.open(
        "r",
        encoding="utf-8",
        newline=""
    ) as file:

        reader = csv.reader(file)

        for line_number, row in enumerate(reader, start=1):
            total += 1

            try:
                record = convert_row(
                    row,
                    filename,
                    line_number
                )

                errors = validate_record(record)

            except Exception as exc:
                errors = [
                    f"Parsing error: {exc}"
                ]

            if errors:
                invalid += 1

                for error in errors:
                    logger.error(
                        "File=%s | Line=%s | Reason=%s",
                        filename,
                        line_number,
                        error,
                    )

            else:
                valid += 1

    print(f"Total records: {total}")
    print(f"Valid records: {valid}")
    print(f"Invalid records: {invalid}")

    return {
        "file": filename,
        "total": total,
        "valid": valid,
        "invalid": invalid,
    }


def main():
    results = []

    for filename in CSV_FILES:
        file_path = DATA_DIR / filename

        if not file_path.exists():
            print(f"File not found: {file_path}")
            continue

        results.append(
            validate_file(filename)
        )

    print("\n===== FINAL SUMMARY =====")

    total_records = sum(
        result["total"]
        for result in results
    )

    total_valid = sum(
        result["valid"]
        for result in results
    )

    total_invalid = sum(
        result["invalid"]
        for result in results
    )

    print(f"Total records: {total_records}")
    print(f"Valid records: {total_valid}")
    print(f"Invalid records: {total_invalid}")

    print("\n===== PER-FILE SUMMARY =====")

    for result in results:
        print(
            f"{result['file']}: "
            f"{result['valid']}/{result['total']} valid, "
            f"{result['invalid']} invalid"
        )


if __name__ == "__main__":
    main()
