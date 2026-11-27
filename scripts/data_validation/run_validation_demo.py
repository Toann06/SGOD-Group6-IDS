
import json

from src.data_validation.validator import validate_record
from src.data_validation.logger import (
    setup_validation_logger,
    log_validation_errors,
)


sample_records = [
    {
        "timestamp": "0.001",
        "can_id": "00000123",
        "dlc": 2,
        "payload": ["AA", "BB"],
        "label": 0,
    },
    {
        "timestamp": "0.002",
        "can_id": "00000124",
        "dlc": 3,
        "payload": ["AA", "BB"],
        "label": 1,
    },
    {
        "timestamp": "invalid",
        "can_id": "00000125",
        "dlc": 1,
        "payload": ["ZZ"],
        "label": 2,
    },
]


def main():
    logger = setup_validation_logger()

    total_records = len(sample_records)
    valid_records = 0
    invalid_records = 0

    for index, record in enumerate(sample_records, start=1):
        errors = validate_record(record)

        if errors:
            invalid_records += 1

            log_validation_errors(
                logger,
                index,
                errors,
            )
        else:
            valid_records += 1
            logger.info(
                "Record %s | Validation passed",
                index,
            )

    print("\n===== Validation Summary =====")
    print(f"Total records: {total_records}")
    print(f"Valid records: {valid_records}")
    print(f"Invalid records: {invalid_records}")


if __name__ == "__main__":
    main()
