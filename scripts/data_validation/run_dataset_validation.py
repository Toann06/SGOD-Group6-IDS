import csv
import re
import sys
from pathlib import Path

# Project root: SGOD-Group6-IDS/
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from src.data_validation.validator import validate_record
from src.data_validation.logger import log_error, clear_log

# Dataset directory
DATASET_DIR = PROJECT_ROOT / "data" / "raw" / "HCRL"

# Validation output directory
OUTPUT_DIR = PROJECT_ROOT / "results" / "validation"

DATASETS = {
    "DoS": "DoS_dataset.csv",
    "Fuzzy": "Fuzzy_dataset.csv",
    "Gear": "gear_dataset.csv",
    "RPM": "RPM_dataset.csv",
    "Normal": "normal_run_data.txt",
}


def parse_payload(values):
    if isinstance(values, str):
        values = values.replace(",", " ").split()

    return [
        str(value).strip().upper()
        for value in values
        if str(value).strip()
    ]


def parse_row(row, dataset_name):
    """
    Convert a raw row into a normalized record.

    Expected format:
        Timestamp, CAN ID, DLC, DATA..., Flag

    Dataset format must be verified before final execution.
    """

    row = [str(value).strip() for value in row]

    if len(row) < 3:
        raise ValueError("Insufficient columns")

    timestamp = row[0]
    can_id = row[1]
    dlc = row[2]

    try:
        dlc_value = int(dlc)
    except ValueError:
        dlc_value = -1

    if dlc_value >= 0:
        payload_values = row[3:3 + dlc_value]
    else:
        payload_values = []

    payload = parse_payload(payload_values)

    # Flag position depends on the actual source format.
    flag_index = 3 + max(dlc_value, 0)

    if len(row) > flag_index:
        flag = row[flag_index].strip().upper()

        if flag == "R":
            label = 0
        elif flag == "T":
            label = 1
        else:
            label = flag

    else:
        # Do not silently assume unknown records are normal.
        label = 0 if dataset_name == "Normal" else "UNKNOWN"

    return {
        "timestamp": timestamp,
        "can_id": can_id,
        "dlc": dlc,
        "payload": payload,
        "label": label,
    }


def read_dataset(filepath):
    """
    Read CSV dataset line by line.
    """

    with filepath.open(
        "r",
        encoding="utf-8",
        errors="replace",
        newline=""
    ) as file:

        reader = csv.reader(file)

        for record_number, row in enumerate(reader, start=1):
            if row:
                yield record_number, row


def read_normal_dataset(filepath):
    """
    Read normal_run_data.txt line by line.
    """

    with filepath.open(
        "r",
        encoding="utf-8",
        errors="replace"
    ) as file:

        for record_number, line in enumerate(file, start=1):

            line = line.strip()

            if not line:
                continue

            yield record_number, line


def parse_normal_line(line):
    """
    Parse a normal CAN Bus record from normal_run_data.txt.

    Example:
    Timestamp: 1479121434.850202 ID: 0350 000 DLC: 8
    05 28 84 66 6d 00 00 a2
    """

    pattern = (
        r"Timestamp:\s*(\S+)"
        r"\s+ID:\s*([0-9a-fA-F]+)"
        r"\s+(\d+)"
        r"\s+DLC:\s*(\d+)"
        r"\s*(.*)"
    )

    match = re.match(pattern, line.strip())

    if not match:
        return None

    timestamp, can_id, _, dlc, payload = match.groups()

    payload_bytes = (
        payload.strip().split()
        if payload.strip()
        else []
    )

    return {
        "timestamp": timestamp,
        "can_id": can_id,
        "dlc": int(dlc),
        "payload": payload_bytes,
        "label": 0,
    }


def validate_dataset(dataset_name, filepath):

    total = 0
    valid = 0
    invalid = 0

    print(f"\nProcessing: {dataset_name}")
    print(f"File: {filepath}")

    if not filepath.exists():
        print("[ERROR] Dataset file not found")

        return {
            "dataset": dataset_name,
            "total": 0,
            "valid": 0,
            "invalid": 0,
        }

    # Normal dataset uses text format.
    if dataset_name == "Normal":
        dataset_reader = read_normal_dataset(filepath)
    else:
        dataset_reader = read_dataset(filepath)

    for record_number, row in dataset_reader:

        total += 1

        try:

            if dataset_name == "Normal":

                record = parse_normal_line(row)

                if record is None:
                    raise ValueError(
                        "Invalid Normal dataset format"
                    )

            else:

                # Skip header if present.
                if row[0].strip().lower() in (
                    "timestamp",
                    "time",
                    "time_stamp"
                ):
                    total -= 1
                    continue

                record = parse_row(
                    row,
                    dataset_name
                )

            errors = validate_record(record)

            if errors:

                invalid += 1

                log_error(
                    dataset=dataset_name,
                    record_number=record_number,
                    record=record,
                    errors=errors,
                )

            else:

                valid += 1

        except Exception as error:

            invalid += 1

            log_error(
                dataset=dataset_name,
                record_number=record_number,
                record=row,
                errors=[str(error)],
            )

        if total > 0 and total % 100000 == 0:

            print(
                f"Processed {total:,} | "
                f"Valid {valid:,} | "
                f"Invalid {invalid:,}"
            )

    print(f"Total: {total:,}")
    print(f"Valid: {valid:,}")
    print(f"Invalid: {invalid:,}")

    return {
        "dataset": dataset_name,
        "total": total,
        "valid": valid,
        "invalid": invalid,
    }


def save_report(results):

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    report_path = OUTPUT_DIR / "validation_report.csv"

    with report_path.open(
        "w",
        encoding="utf-8",
        newline=""
    ) as file:

        fieldnames = [
            "dataset",
            "total",
            "valid",
            "invalid",
            "error_rate_percent",
        ]

        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames
        )

        writer.writeheader()

        for result in results:

            total = result["total"]
            invalid = result["invalid"]

            error_rate = (
                invalid / total * 100
                if total > 0
                else 0
            )

            writer.writerow({
                "dataset": result["dataset"],
                "total": total,
                "valid": result["valid"],
                "invalid": invalid,
                "error_rate_percent": round(
                    error_rate,
                    4
                ),
            })

    print(f"\nReport saved: {report_path}")


def main():

    clear_log()

    results = []

    for dataset_name, filename in DATASETS.items():

        filepath = DATASET_DIR / filename

        result = validate_dataset(
            dataset_name,
            filepath
        )

        results.append(result)

    save_report(results)

    print("\n========== FINAL SUMMARY ==========")

    for result in results:

        print(
            f"{result['dataset']:10} | "
            f"Total: {result['total']:>12,} | "
            f"Valid: {result['valid']:>12,} | "
            f"Invalid: {result['invalid']:>12,}"
        )


if __name__ == "__main__":
    main()
