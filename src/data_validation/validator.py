from typing import Any, Dict, List


REQUIRED_FIELDS = [
    "timestamp",
    "can_id",
    "dlc",
    "payload",
    "label",
]


def validate_record(record: Dict[str, Any]) -> List[str]:
    errors = []

    # Missing fields
    for field in REQUIRED_FIELDS:
        if field not in record:
            errors.append(f"Missing field: {field}")
        elif record[field] is None:
            errors.append(f"Null field: {field}")
        elif isinstance(record[field], str) and not record[field].strip():
            errors.append(f"Empty field: {field}")

    if errors:
        return errors

    # Timestamp
    try:
        timestamp = float(record["timestamp"])

        if timestamp < 0:
            errors.append("Timestamp cannot be negative")

    except (TypeError, ValueError):
        errors.append("Invalid timestamp")

    # CAN ID
    can_id = str(record["can_id"]).strip()

    try:
        int(can_id, 16)
    except ValueError:
        errors.append("Invalid CAN ID format")

    # DLC
    try:
        dlc = int(record["dlc"])

        if not 0 <= dlc <= 8:
            errors.append("DLC must be between 0 and 8")

    except (TypeError, ValueError):
        errors.append("DLC must be an integer")
        dlc = None

    # Payload
    payload = record["payload"]

    if not isinstance(payload, list):
        errors.append("Payload must be a list")

    else:
        if dlc is not None and 0 <= dlc <= 8:
            if len(payload) != dlc:
                errors.append(
                    f"Payload length {len(payload)} "
                    f"does not match DLC {dlc}"
                )

        for byte in payload:

            if not isinstance(byte, str):
                errors.append(
                    f"Payload byte must be string: {byte}"
                )
                continue

            byte = byte.strip()

            if len(byte) != 2:
                errors.append(
                    f"Invalid payload byte length: {byte}"
                )
                continue

            try:
                int(byte, 16)

            except ValueError:
                errors.append(
                    f"Invalid hexadecimal payload byte: {byte}"
                )

    # Label
    if record["label"] not in (0, 1):
        errors.append("Label must be 0 or 1")

    return errors